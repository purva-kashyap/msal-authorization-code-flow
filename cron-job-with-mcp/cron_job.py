"""
Main cron job script using MCP tools for Teams and Zoom operations.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db_session, create_tables
from models import UserToken, UserProcessingStatus, MeetingRecord, ProcessingLog
from services import MCPClient, TeamsMCPService, ZoomMCPService
from summary_service import SummaryService
from utils import TokenDecryptor, format_duration


logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MeetingProcessor:
    """Main processor that uses MCP services."""

    def __init__(self):
        self.token_decryptor = TokenDecryptor(settings.encryption_key)
        self.summary_service = None
        if settings.openai_api_key:
            self.summary_service = SummaryService(settings.openai_api_key, settings.openai_model)

        self.mcp_client = MCPClient(settings.mcp_server_url, settings.mcp_auth_token)
        self.teams_service = TeamsMCPService(self.mcp_client)
        self.zoom_service = ZoomMCPService(self.mcp_client)

    async def process_user_teams_meetings(
        self,
        session: AsyncSession,
        user: UserToken,
        user_status: UserProcessingStatus,
    ) -> int:
        try:
            access_token = self.token_decryptor.decrypt_token(user.access_token)
            meetings = await self.teams_service.get_online_meetings(
                access_token=access_token,
                lookback_hours=settings.lookback_hours,
            )

            if not meetings:
                logger.info("No Teams meetings found for user %s", user.email)
                return 0

            processed_count = 0

            for meeting in meetings[: settings.max_meetings_per_user]:
                meeting_id = str(meeting.get("id"))
                if not meeting_id:
                    continue

                meeting_title = meeting.get("subject", "Untitled Meeting")

                existing = (
                    await session.execute(
                        select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                meeting_record = MeetingRecord(
                    user_id=user.user_id,
                    meeting_id=meeting_id,
                    platform="teams",
                    meeting_title=meeting_title,
                    transcript_status="pending",
                    summary_status="pending",
                )
                session.add(meeting_record)
                await session.flush()

                transcript = await self.teams_service.get_call_transcript(
                    access_token=access_token,
                    meeting_id=meeting_id,
                )
                if not transcript:
                    meeting_record.transcript_status = "no_transcript"
                    continue

                meeting_record.transcript_status = "downloaded"

                if self.summary_service:
                    summary = await self.summary_service.generate_summary(transcript, meeting_title)
                    if summary:
                        meeting_record.summary_text = summary
                        meeting_record.summary_status = "generated"

                        chat_id = meeting.get("chat_id") or meeting.get("chatId")
                        if chat_id:
                            message = self.summary_service.format_summary_message(
                                meeting_title, summary, "teams"
                            )
                            posted = await self.teams_service.post_message_to_chat(
                                access_token=access_token,
                                chat_id=chat_id,
                                message=message,
                            )
                            if posted:
                                meeting_record.summary_status = "posted"

                        meeting_record.processed_at = datetime.utcnow()
                        processed_count += 1
                    else:
                        meeting_record.summary_status = "failed"
                        meeting_record.error_message = "Summary generation failed"

            user_status.last_teams_check = datetime.utcnow()
            return processed_count

        except Exception as exc:
            logger.error("Error processing Teams meetings for %s: %s", user.email, exc)
            return 0

    async def process_user_zoom_meetings(
        self,
        session: AsyncSession,
        user: UserToken,
        user_status: UserProcessingStatus,
    ) -> int:
        try:
            recordings = await self.zoom_service.get_recordings(
                user_email=user.email or user.user_id,
                lookback_hours=settings.lookback_hours,
            )

            if not recordings:
                logger.info("No Zoom recordings found for user %s", user.email)
                return 0

            processed_count = 0
            for recording in recordings[: settings.max_meetings_per_user]:
                meeting_id = str(recording.get("id"))
                if not meeting_id:
                    continue
                meeting_title = recording.get("topic", "Untitled Meeting")

                existing = (
                    await session.execute(
                        select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                meeting_record = MeetingRecord(
                    user_id=user.user_id,
                    meeting_id=meeting_id,
                    platform="zoom",
                    meeting_title=meeting_title,
                    transcript_status="pending",
                    summary_status="pending",
                )
                session.add(meeting_record)
                await session.flush()

                transcript = await self.zoom_service.get_meeting_transcript(meeting_id)
                if not transcript:
                    meeting_record.transcript_status = "no_transcript"
                    continue

                meeting_record.transcript_status = "downloaded"

                if self.summary_service:
                    summary = await self.summary_service.generate_summary(transcript, meeting_title)
                    if summary:
                        meeting_record.summary_text = summary
                        meeting_record.summary_status = "generated"
                        meeting_record.processed_at = datetime.utcnow()
                        processed_count += 1
                    else:
                        meeting_record.summary_status = "failed"
                        meeting_record.error_message = "Summary generation failed"

            user_status.last_zoom_check = datetime.utcnow()
            return processed_count

        except Exception as exc:
            logger.error("Error processing Zoom meetings for %s: %s", user.email, exc)
            return 0

    async def process_all_users(self):
        start_time = datetime.utcnow()
        stats = {
            "users_processed": 0,
            "meetings_found": 0,
            "meetings_processed": 0,
            "errors_count": 0,
            "status": "success",
        }

        try:
            async with get_db_session() as session:
                users = (await session.execute(select(UserToken))).scalars().all()
                logger.info("Found %s users to process", len(users))

                for user in users:
                    try:
                        user_status = (
                            await session.execute(
                                select(UserProcessingStatus).where(
                                    UserProcessingStatus.user_id == user.user_id
                                )
                            )
                        ).scalar_one_or_none()

                        if not user_status:
                            user_status = UserProcessingStatus(user_id=user.user_id, is_active=True)
                            session.add(user_status)
                            await session.flush()

                        if not user_status.is_active:
                            continue

                        teams_count = await self.process_user_teams_meetings(session, user, user_status)
                        zoom_count = await self.process_user_zoom_meetings(session, user, user_status)

                        stats["users_processed"] += 1
                        stats["meetings_processed"] += teams_count + zoom_count

                        await session.commit()
                    except Exception as exc:
                        stats["errors_count"] += 1
                        logger.error("Error processing user %s: %s", user.email, exc)
                        await session.rollback()

                duration = (datetime.utcnow() - start_time).total_seconds()
                if stats["errors_count"] > 0:
                    stats["status"] = "partial" if stats["meetings_processed"] > 0 else "failed"

                session.add(
                    ProcessingLog(
                        run_timestamp=start_time,
                        status=stats["status"],
                        users_processed=stats["users_processed"],
                        meetings_found=stats["meetings_found"],
                        meetings_processed=stats["meetings_processed"],
                        errors_count=stats["errors_count"],
                        duration_seconds=duration,
                    )
                )
                await session.commit()

                logger.info(
                    "Processing complete: %s users, %s meetings processed, %s errors in %s",
                    stats["users_processed"],
                    stats["meetings_processed"],
                    stats["errors_count"],
                    format_duration(duration),
                )

        except Exception as exc:
            stats["status"] = "failed"
            stats["errors_count"] += 1
            logger.error("Fatal error in process_all_users: %s", exc)

        return stats


async def main():
    logger.info("=" * 80)
    logger.info("Starting MCP-based meeting transcript processing cron job")
    logger.info("=" * 80)

    await create_tables()

    processor = MeetingProcessor()
    try:
        stats = await processor.process_all_users()
    finally:
        await processor.mcp_client.aclose()

    logger.info("=" * 80)
    logger.info("Cron job completed")
    logger.info("Statistics: %s", stats)
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

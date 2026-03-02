"""
MeetingProcessor — orchestrates transcript processing for all users.

Coordinates:
- Token refresh via MSAL (TokenManager)
- Fetching Teams meetings & transcripts via Graph API (GraphService)
- Fetching Zoom recordings & transcripts (ZoomService)
- Generating summaries via LLM (LLMService)
- Posting summaries back to Teams chats
- Persisting results and last-processed timestamps to the database

Concurrency Model
-----------------
Users are processed concurrently (up to ``settings.user_concurrency``)
using ``asyncio.Semaphore`` + ``asyncio.gather``.  Each user gets its
own short-lived database session so a rollback for one user does not
affect the others.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db_session
from exceptions import TokenExpiredError
from models import UserToken, UserProcessingStatus, MeetingRecord, ProcessingLog
from services.token_manager import TokenManager
from services.graph_service import GraphService
from services.zoom_service import ZoomService
from services.llm_service import LLMService
from utils import format_duration

logger = logging.getLogger(__name__)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Best-effort ISO datetime parsing."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class MeetingProcessor:
    """Orchestrates meeting transcript processing for all users."""

    def __init__(self, shutdown_event: Optional[asyncio.Event] = None):
        self.token_manager = TokenManager()
        self._shutdown = shutdown_event or asyncio.Event()

        # LLM service (optional)
        self.llm: Optional[LLMService] = None
        if settings.openai_api_key:
            self.llm = LLMService(settings.openai_api_key, settings.openai_model)

        # Zoom service (optional)
        self.zoom: Optional[ZoomService] = None
        if settings.is_zoom_configured:
            self.zoom = ZoomService(
                settings.zoom_client_id,
                settings.zoom_client_secret,
                settings.zoom_account_id,
            )

    async def close(self) -> None:
        """Release service resources."""
        if self.llm:
            await self.llm.close()
        if self.zoom:
            await self.zoom.close()

    # ------------------------------------------------------------------
    # Token refresh helper (used by both Teams and Zoom-post flows)
    # ------------------------------------------------------------------
    async def _refresh_and_update_graph(
        self,
        session: AsyncSession,
        user: UserToken,
        graph: GraphService,
    ) -> str:
        """Refresh Graph tokens, update the Graph client, and persist to DB."""
        new_access, new_enc_refresh, expires_at = self.token_manager.refresh_tokens(
            user.refresh_token
        )
        graph.update_token(new_access)
        await self.token_manager.persist_tokens(
            session, user.user_id, new_access, new_enc_refresh, expires_at
        )
        # Keep in-memory model in sync for the remainder of this run
        user.refresh_token = new_enc_refresh
        user.expires_at = expires_at
        return new_access

    # ------------------------------------------------------------------
    # Teams processing
    # ------------------------------------------------------------------
    async def process_user_teams(
        self,
        session: AsyncSession,
        user: UserToken,
        user_status: UserProcessingStatus,
        graph: GraphService,
    ) -> int:
        """Process Teams meetings for a single user. Returns count processed."""
        since = user_status.last_teams_processed_at  # may be None → uses lookback

        try:
            meetings = await graph.get_online_meetings(
                since=since, lookback_hours=settings.lookback_hours
            )
        except TokenExpiredError:
            await self._refresh_and_update_graph(session, user, graph)
            meetings = await graph.get_online_meetings(
                since=since, lookback_hours=settings.lookback_hours
            )

        if not meetings:
            logger.info("No Teams meetings for %s", user.email)
            return 0

        processed = 0
        for meeting in meetings[: settings.max_meetings_per_user]:
            meeting_id = meeting.get("id")
            if not meeting_id:
                continue
            title = meeting.get("subject", "Untitled Meeting")

            # Skip already-processed meetings
            exists = (
                await session.execute(
                    select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                )
            ).scalar_one_or_none()
            if exists:
                continue

            record = MeetingRecord(
                user_id=user.user_id,
                meeting_id=meeting_id,
                platform="teams",
                meeting_title=title,
                meeting_start_time=_parse_dt(meeting.get("start", {}).get("dateTime")),
                meeting_end_time=_parse_dt(meeting.get("end", {}).get("dateTime")),
                transcript_status="pending",
                summary_status="pending",
            )
            session.add(record)
            await session.flush()

            # --- Transcript ---
            transcript = await self._get_teams_transcript(graph, session, user, meeting_id)
            if not transcript:
                record.transcript_status = "no_transcript"
                continue
            record.transcript_status = "downloaded"

            # --- Summary ---
            if not self.llm:
                logger.warning("LLM not configured — skipping summary")
                continue

            summary = await self.llm.generate_summary(transcript, title)
            if not summary:
                record.summary_status = "failed"
                record.error_message = "Summary generation failed"
                continue

            record.summary_text = summary
            record.summary_status = "generated"

            # --- Post to chat ---
            chat_id = (meeting.get("onlineMeeting") or {}).get("chatId")
            if chat_id:
                message = LLMService.format_summary_message(title, summary, "teams")
                try:
                    posted = await graph.post_message_to_chat(chat_id, message)
                except TokenExpiredError:
                    await self._refresh_and_update_graph(session, user, graph)
                    posted = await graph.post_message_to_chat(chat_id, message)
                if posted:
                    record.summary_status = "posted"

            record.processed_at = datetime.now(timezone.utc)
            processed += 1
            logger.info("Processed Teams meeting: %s", title)

        # Mark last successful processing timestamp
        if processed > 0:
            user_status.last_teams_processed_at = datetime.now(timezone.utc)

        return processed

    async def _get_teams_transcript(
        self,
        graph: GraphService,
        session: AsyncSession,
        user: UserToken,
        meeting_id: str,
    ) -> Optional[str]:
        """Fetch the first available transcript for a meeting, handling 401."""
        try:
            transcripts = await graph.list_transcripts(meeting_id)
        except TokenExpiredError:
            await self._refresh_and_update_graph(session, user, graph)
            transcripts = await graph.list_transcripts(meeting_id)

        if not transcripts:
            return None

        transcript_id = transcripts[0].get("id")
        if not transcript_id:
            return None

        try:
            return await graph.get_transcript(meeting_id, transcript_id)
        except TokenExpiredError:
            await self._refresh_and_update_graph(session, user, graph)
            return await graph.get_transcript(meeting_id, transcript_id)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Zoom processing (summary posted to Teams via Graph)
    # ------------------------------------------------------------------
    async def process_user_zoom(
        self,
        session: AsyncSession,
        user: UserToken,
        user_status: UserProcessingStatus,
        graph: GraphService,
    ) -> int:
        """Process Zoom recordings for a user. Posts summaries to Teams."""
        if not self.zoom:
            return 0

        since = user_status.last_zoom_processed_at
        recordings = await self.zoom.get_recordings(
            user_id=user.email or user.user_id,
            since=since,
            lookback_hours=settings.lookback_hours,
        )
        if not recordings:
            logger.info("No Zoom recordings for %s", user.email)
            return 0

        processed = 0
        for rec in recordings[: settings.max_meetings_per_user]:
            meeting_id = str(rec.get("id", ""))
            if not meeting_id:
                continue
            title = rec.get("topic", "Untitled Meeting")

            exists = (
                await session.execute(
                    select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                )
            ).scalar_one_or_none()
            if exists:
                continue

            record = MeetingRecord(
                user_id=user.user_id,
                meeting_id=meeting_id,
                platform="zoom",
                meeting_title=title,
                meeting_start_time=_parse_dt(rec.get("start_time")),
                transcript_status="pending",
                summary_status="pending",
            )
            session.add(record)
            await session.flush()

            transcript = await self.zoom.get_meeting_transcript(meeting_id)
            if not transcript:
                record.transcript_status = "no_transcript"
                continue
            record.transcript_status = "downloaded"

            if not self.llm:
                logger.warning("LLM not configured — skipping summary")
                continue

            summary = await self.llm.generate_summary(transcript, title)
            if not summary:
                record.summary_status = "failed"
                record.error_message = "Summary generation failed"
                continue

            record.summary_text = summary
            record.summary_status = "generated"

            # Post Zoom summary to Teams chat (user's 1:1 "Saved Messages" or a
            # dedicated channel). For now we just mark it generated. If a chat_id
            # mapping exists in the future it can be posted here using graph.post_message_to_chat().

            record.processed_at = datetime.now(timezone.utc)
            processed += 1
            logger.info("Processed Zoom meeting: %s", title)

        if processed > 0:
            user_status.last_zoom_processed_at = datetime.now(timezone.utc)

        return processed

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    async def process_all_users(self) -> dict:
        start = datetime.now(timezone.utc)
        stats = {
            "users_processed": 0,
            "meetings_processed": 0,
            "errors_count": 0,
            "status": "success",
        }

        semaphore = asyncio.Semaphore(settings.user_concurrency)

        async def _process_one(user_snapshot: UserToken) -> dict:
            """Process a single user with its own DB session."""
            local = {"processed": 0, "error": False}
            async with semaphore:
                graph: Optional[GraphService] = None
                try:
                    async with get_db_session() as session:
                        # Re-fetch the user inside this new session so it's attached
                        user = (
                            await session.execute(
                                select(UserToken).where(
                                    UserToken.user_id == user_snapshot.user_id
                                )
                            )
                        ).scalar_one_or_none()
                        if not user:
                            return local

                        # --- Get or create processing status ---
                        user_status = (
                            await session.execute(
                                select(UserProcessingStatus).where(
                                    UserProcessingStatus.user_id == user.user_id
                                )
                            )
                        ).scalar_one_or_none()
                        if not user_status:
                            user_status = UserProcessingStatus(
                                user_id=user.user_id, is_active=True
                            )
                            session.add(user_status)
                            await session.flush()
                        if not user_status.is_active:
                            return local

                        # --- Refresh tokens up-front if near expiry ---
                        access_token: str
                        if self.token_manager.is_token_expired(user.expires_at):
                            access_token, enc_refresh, expires_at = (
                                self.token_manager.refresh_tokens(user.refresh_token)
                            )
                            user.refresh_token = enc_refresh
                            user.expires_at = expires_at
                            await self.token_manager.persist_tokens(
                                session, user.user_id, access_token, enc_refresh, expires_at
                            )
                        else:
                            access_token = self.token_manager.decrypt(user.access_token)

                        graph = GraphService(access_token)

                        # --- Process platforms ---
                        teams_count = await self.process_user_teams(
                            session, user, user_status, graph
                        )
                        zoom_count = await self.process_user_zoom(
                            session, user, user_status, graph
                        )

                        local["processed"] = teams_count + zoom_count
                        logger.info(
                            "User %s: %d Teams + %d Zoom meetings processed",
                            user.email,
                            teams_count,
                            zoom_count,
                        )
                        await session.commit()

                except Exception as exc:
                    local["error"] = True
                    logger.error(
                        "Error processing user %s: %s",
                        user_snapshot.email,
                        exc,
                        exc_info=True,
                    )
                finally:
                    if graph:
                        await graph.close()

            return local

        try:
            # Fetch all user IDs in a lightweight read-only session
            async with get_db_session() as session:
                users = (await session.execute(select(UserToken))).scalars().all()
                logger.info("Found %d users to process", len(users))

            # Process in batches to avoid creating too many tasks at once
            for batch_start in range(0, len(users), settings.batch_size):
                if self._shutdown.is_set():
                    logger.info("Shutdown requested — stopping after current batch")
                    stats["status"] = "interrupted"
                    break

                batch = users[batch_start : batch_start + settings.batch_size]
                results = await asyncio.gather(
                    *[_process_one(u) for u in batch],
                    return_exceptions=True,
                )

                for res in results:
                    if isinstance(res, Exception):
                        stats["errors_count"] += 1
                        logger.error("Unhandled user error: %s", res, exc_info=res)
                    else:
                        if res.get("error"):
                            stats["errors_count"] += 1
                        meetings = res.get("processed", 0)
                        if meetings or not res.get("error"):
                            stats["users_processed"] += 1
                        stats["meetings_processed"] += meetings

            # --- Write processing log ---
            duration = (datetime.now(timezone.utc) - start).total_seconds()
            if stats["errors_count"]:
                stats["status"] = "partial" if stats["meetings_processed"] else "failed"

            async with get_db_session() as session:
                session.add(
                    ProcessingLog(
                        run_timestamp=start,
                        status=stats["status"],
                        users_processed=stats["users_processed"],
                        meetings_found=0,
                        meetings_processed=stats["meetings_processed"],
                        errors_count=stats["errors_count"],
                        duration_seconds=duration,
                    )
                )
                await session.commit()

            logger.info(
                "Run complete: %d users, %d meetings, %d errors in %s",
                stats["users_processed"],
                stats["meetings_processed"],
                stats["errors_count"],
                format_duration(duration),
            )

        except Exception as exc:
            stats["status"] = "failed"
            stats["errors_count"] += 1
            logger.error("Fatal error: %s", exc, exc_info=True)

        return stats

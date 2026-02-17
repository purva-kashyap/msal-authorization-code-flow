"""
Main cron job script for processing Teams and Zoom meeting recordings.

This script:
1. Fetches all active users from the database
2. For each user, checks for new recorded meetings (Teams & Zoom)
3. Downloads transcripts
4. Generates summaries using AI
5. Posts summaries to meeting chats
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db_session, create_tables
from models import UserToken, UserProcessingStatus, MeetingRecord, ProcessingLog
from config import settings
from teams_service import TeamsService
from zoom_service import ZoomService
from summary_service import SummaryService
from utils import TokenDecryptor, format_duration

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MeetingProcessor:
    """Main processor for handling meeting transcripts and summaries."""
    
    def __init__(self):
        """Initialize the meeting processor."""
        self.token_decryptor = TokenDecryptor(settings.encryption_key)
        self.summary_service = None
        if settings.openai_api_key:
            self.summary_service = SummaryService(
                settings.openai_api_key,
                settings.openai_model
            )
        
        self.zoom_service = None
        if all([settings.zoom_client_id, settings.zoom_client_secret, settings.zoom_account_id]):
            self.zoom_service = ZoomService(
                settings.zoom_client_id,
                settings.zoom_client_secret,
                settings.zoom_account_id
            )
    
    async def process_user_teams_meetings(
        self, 
        session: AsyncSession,
        user: UserToken,
        user_status: UserProcessingStatus
    ) -> int:
        """
        Process Teams meetings for a user.
        
        Args:
            session: Database session
            user: User token information
            user_status: User processing status
            
        Returns:
            Number of meetings processed
        """
        try:
            # Decrypt access token
            access_token = self.token_decryptor.decrypt_token(user.access_token)
            
            # Initialize Teams service
            teams_service = TeamsService(access_token)
            
            # Fetch online meetings
            meetings = await teams_service.get_online_meetings(settings.lookback_hours)
            
            if not meetings:
                logger.info(f"No Teams meetings found for user {user.email}")
                return 0
            
            processed_count = 0
            
            for meeting in meetings[:settings.max_meetings_per_user]:
                meeting_id = meeting.get("id")
                meeting_title = meeting.get("subject", "Untitled Meeting")
                
                # Check if already processed
                result = await session.execute(
                    select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.debug(f"Meeting {meeting_id} already processed, skipping")
                    continue
                
                # Create meeting record
                meeting_record = MeetingRecord(
                    user_id=user.user_id,
                    meeting_id=meeting_id,
                    platform="teams",
                    meeting_title=meeting_title,
                    meeting_start_time=datetime.fromisoformat(meeting["start"]["dateTime"].replace("Z", "+00:00")) if meeting.get("start") else None,
                    meeting_end_time=datetime.fromisoformat(meeting["end"]["dateTime"].replace("Z", "+00:00")) if meeting.get("end") else None,
                    transcript_status="pending",
                    summary_status="pending"
                )
                session.add(meeting_record)
                await session.flush()
                
                # Try to get recordings
                recordings = await teams_service.get_call_recordings(meeting_id)
                
                if not recordings:
                    logger.info(f"No recordings found for Teams meeting {meeting_title}")
                    meeting_record.transcript_status = "no_recording"
                    continue
                
                # Get transcript from first recording
                recording = recordings[0]
                recording_id = recording.get("id")
                
                transcript = await teams_service.get_call_transcript(recording_id)
                
                if not transcript:
                    logger.warning(f"No transcript available for Teams meeting {meeting_title}")
                    meeting_record.transcript_status = "no_transcript"
                    continue
                
                meeting_record.transcript_status = "downloaded"
                
                # Generate summary if OpenAI is configured
                if self.summary_service:
                    summary = await self.summary_service.generate_summary(
                        transcript,
                        meeting_title
                    )
                    
                    if summary:
                        meeting_record.summary_text = summary
                        meeting_record.summary_status = "generated"
                        
                        # Format message
                        message = self.summary_service.format_summary_message(
                            meeting_title,
                            summary,
                            "teams"
                        )
                        
                        # Try to post to chat (if chat_id is available)
                        online_meeting = meeting.get("onlineMeeting", {})
                        chat_id = online_meeting.get("chatId")
                        
                        if chat_id:
                            posted = await teams_service.post_message_to_chat(chat_id, message)
                            if posted:
                                meeting_record.summary_status = "posted"
                        
                        meeting_record.processed_at = datetime.utcnow()
                        processed_count += 1
                        logger.info(f"Successfully processed Teams meeting: {meeting_title}")
                    else:
                        meeting_record.summary_status = "failed"
                        meeting_record.error_message = "Summary generation failed"
                else:
                    logger.warning("OpenAI not configured, skipping summary generation")
            
            # Update user processing status
            user_status.last_teams_check = datetime.utcnow()
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing Teams meetings for {user.email}: {str(e)}")
            return 0
    
    async def process_user_zoom_meetings(
        self,
        session: AsyncSession,
        user: UserToken,
        user_status: UserProcessingStatus
    ) -> int:
        """
        Process Zoom meetings for a user.
        
        Args:
            session: Database session
            user: User token information
            user_status: User processing status
            
        Returns:
            Number of meetings processed
        """
        if not self.zoom_service:
            logger.debug("Zoom service not configured, skipping")
            return 0
        
        try:
            # Get Zoom recordings
            # Note: This assumes user has Zoom linked. You might need user-specific Zoom tokens
            recordings = await self.zoom_service.get_recordings(
                user_id="me",
                lookback_hours=settings.lookback_hours
            )
            
            if not recordings:
                logger.info(f"No Zoom recordings found for user {user.email}")
                return 0
            
            processed_count = 0
            
            for recording in recordings[:settings.max_meetings_per_user]:
                meeting_id = str(recording.get("id"))
                meeting_title = recording.get("topic", "Untitled Meeting")
                
                # Check if already processed
                result = await session.execute(
                    select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.debug(f"Zoom meeting {meeting_id} already processed, skipping")
                    continue
                
                # Create meeting record
                meeting_record = MeetingRecord(
                    user_id=user.user_id,
                    meeting_id=meeting_id,
                    platform="zoom",
                    meeting_title=meeting_title,
                    meeting_start_time=datetime.fromisoformat(recording["start_time"].replace("Z", "+00:00")) if recording.get("start_time") else None,
                    transcript_status="pending",
                    summary_status="pending"
                )
                session.add(meeting_record)
                await session.flush()
                
                # Get transcript
                transcript = await self.zoom_service.get_meeting_transcript(meeting_id)
                
                if not transcript:
                    logger.warning(f"No transcript available for Zoom meeting {meeting_title}")
                    meeting_record.transcript_status = "no_transcript"
                    continue
                
                meeting_record.transcript_status = "downloaded"
                
                # Generate summary if OpenAI is configured
                if self.summary_service:
                    summary = await self.summary_service.generate_summary(
                        transcript,
                        meeting_title
                    )
                    
                    if summary:
                        meeting_record.summary_text = summary
                        meeting_record.summary_status = "generated"
                        
                        # Format message
                        message = self.summary_service.format_summary_message(
                            meeting_title,
                            summary,
                            "zoom"
                        )
                        
                        # Note: Posting to Zoom chat requires additional setup
                        # For now, just mark as generated
                        
                        meeting_record.processed_at = datetime.utcnow()
                        processed_count += 1
                        logger.info(f"Successfully processed Zoom meeting: {meeting_title}")
                    else:
                        meeting_record.summary_status = "failed"
                        meeting_record.error_message = "Summary generation failed"
                else:
                    logger.warning("OpenAI not configured, skipping summary generation")
            
            # Update user processing status
            user_status.last_zoom_check = datetime.utcnow()
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing Zoom meetings for {user.email}: {str(e)}")
            return 0
    
    async def process_all_users(self):
        """
        Main function to process all users.
        
        Returns:
            Processing log with statistics
        """
        start_time = datetime.utcnow()
        stats = {
            "users_processed": 0,
            "meetings_found": 0,
            "meetings_processed": 0,
            "errors_count": 0,
            "status": "success"
        }
        
        try:
            async with get_db_session() as session:
                # Get all users with tokens
                result = await session.execute(select(UserToken))
                users = result.scalars().all()
                
                logger.info(f"Found {len(users)} users to process")
                
                for user in users:
                    try:
                        # Get or create user processing status
                        status_result = await session.execute(
                            select(UserProcessingStatus).where(
                                UserProcessingStatus.user_id == user.user_id
                            )
                        )
                        user_status = status_result.scalar_one_or_none()
                        
                        if not user_status:
                            user_status = UserProcessingStatus(
                                user_id=user.user_id,
                                is_active=True
                            )
                            session.add(user_status)
                            await session.flush()
                        
                        if not user_status.is_active:
                            logger.info(f"User {user.email} is inactive, skipping")
                            continue
                        
                        logger.info(f"Processing user: {user.email}")
                        
                        # Process Teams meetings
                        teams_count = await self.process_user_teams_meetings(
                            session, user, user_status
                        )
                        
                        # Process Zoom meetings
                        zoom_count = await self.process_user_zoom_meetings(
                            session, user, user_status
                        )
                        
                        total_processed = teams_count + zoom_count
                        stats["users_processed"] += 1
                        stats["meetings_processed"] += total_processed
                        
                        logger.info(
                            f"User {user.email}: processed {teams_count} Teams + "
                            f"{zoom_count} Zoom meetings"
                        )
                        
                        # Commit after each user
                        await session.commit()
                        
                    except Exception as e:
                        logger.error(f"Error processing user {user.email}: {str(e)}")
                        stats["errors_count"] += 1
                        await session.rollback()
                
                # Create processing log
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                if stats["errors_count"] > 0:
                    stats["status"] = "partial" if stats["meetings_processed"] > 0 else "failed"
                
                log_entry = ProcessingLog(
                    run_timestamp=start_time,
                    status=stats["status"],
                    users_processed=stats["users_processed"],
                    meetings_found=stats["meetings_found"],
                    meetings_processed=stats["meetings_processed"],
                    errors_count=stats["errors_count"],
                    duration_seconds=duration
                )
                session.add(log_entry)
                await session.commit()
                
                logger.info(
                    f"Processing complete: {stats['users_processed']} users, "
                    f"{stats['meetings_processed']} meetings processed, "
                    f"{stats['errors_count']} errors in {format_duration(duration)}"
                )
                
        except Exception as e:
            logger.error(f"Fatal error in process_all_users: {str(e)}")
            stats["status"] = "failed"
            stats["errors_count"] += 1
        
        return stats


async def main():
    """Main entry point for the cron job."""
    logger.info("=" * 80)
    logger.info("Starting meeting transcript processing cron job")
    logger.info("=" * 80)
    
    try:
        # Ensure tables exist
        await create_tables()
        
        # Process all users
        processor = MeetingProcessor()
        stats = await processor.process_all_users()
        
        logger.info("=" * 80)
        logger.info("Cron job completed successfully")
        logger.info(f"Statistics: {stats}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Cron job failed with error: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())

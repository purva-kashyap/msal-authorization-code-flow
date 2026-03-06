"""
Meeting-related database models.
"""
from sqlalchemy import Column, String, Integer, Text, DateTime
from datetime import datetime, timezone
from models.base import Base


class MeetingRecord(Base):
    """Record of processed meetings to avoid duplicates."""
    
    __tablename__ = 'meeting_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    meeting_id = Column(String(500), nullable=False, unique=True, index=True)
    platform = Column(String(50), nullable=False)  # 'teams' or 'zoom'
    meeting_title = Column(String(500), nullable=True)
    meeting_start_time = Column(DateTime(timezone=True), nullable=True)
    meeting_end_time = Column(DateTime(timezone=True), nullable=True)
    recording_url = Column(Text, nullable=True)
    transcript_status = Column(String(50), default='pending')  # pending, downloaded, processed, failed
    summary_status = Column(String(50), default='pending')  # pending, generated, posted, failed
    summary_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<MeetingRecord(id={self.id}, meeting_id='{self.meeting_id}', platform='{self.platform}')>"

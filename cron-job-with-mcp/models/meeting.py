"""
Meeting-related database models.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime
from models.base import Base


class MeetingRecord(Base):
    """Record of processed meetings to avoid duplicates."""

    __tablename__ = "meeting_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    meeting_id = Column(String(500), nullable=False, unique=True, index=True)
    platform = Column(String(50), nullable=False)
    meeting_title = Column(String(500), nullable=True)
    meeting_start_time = Column(DateTime, nullable=True)
    meeting_end_time = Column(DateTime, nullable=True)
    recording_url = Column(Text, nullable=True)
    transcript_status = Column(String(50), default="pending")
    summary_status = Column(String(50), default="pending")
    summary_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

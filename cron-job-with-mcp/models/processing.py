"""
Processing status and logging models.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Float
from models.base import Base


class UserProcessingStatus(Base):
    """Track last processing time for each user."""

    __tablename__ = "user_processing_status"

    user_id = Column(String(255), primary_key=True, index=True)
    last_teams_check = Column(DateTime, nullable=True, index=True)
    last_zoom_check = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessingLog(Base):
    """Log of cron job executions."""

    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = Column(String(50), nullable=False)
    users_processed = Column(Integer, default=0)
    meetings_found = Column(Integer, default=0)
    meetings_processed = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

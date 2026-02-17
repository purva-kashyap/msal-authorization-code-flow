"""
Database configuration and models for the cron job service.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Float, Integer, Text, Boolean, DateTime
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/entra_tokens"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "false").lower() == "true",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


class UserToken(Base):
    """User token model - shared with the main application."""
    
    __tablename__ = 'user_tokens'
    
    user_id = Column(String(255), primary_key=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    access_token = Column(String(4096), nullable=False)  # Encrypted
    refresh_token = Column(String(4096), nullable=True)  # Encrypted
    expires_at = Column(Float, nullable=False)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
    
    def __repr__(self):
        return f"<UserToken(user_id='{self.user_id}', email='{self.email}')>"


class UserProcessingStatus(Base):
    """Track last processing time for each user."""
    
    __tablename__ = 'user_processing_status'
    
    user_id = Column(String(255), primary_key=True, index=True)
    last_teams_check = Column(DateTime, nullable=True, index=True)
    last_zoom_check = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserProcessingStatus(user_id='{self.user_id}', last_teams_check='{self.last_teams_check}')>"


class MeetingRecord(Base):
    """Record of processed meetings to avoid duplicates."""
    
    __tablename__ = 'meeting_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    meeting_id = Column(String(500), nullable=False, unique=True, index=True)
    platform = Column(String(50), nullable=False)  # 'teams' or 'zoom'
    meeting_title = Column(String(500), nullable=True)
    meeting_start_time = Column(DateTime, nullable=True)
    meeting_end_time = Column(DateTime, nullable=True)
    recording_url = Column(Text, nullable=True)
    transcript_status = Column(String(50), default='pending')  # pending, downloaded, processed, failed
    summary_status = Column(String(50), default='pending')  # pending, generated, posted, failed
    summary_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<MeetingRecord(id={self.id}, meeting_id='{self.meeting_id}', platform='{self.platform}')>"


class ProcessingLog(Base):
    """Log of cron job executions."""
    
    __tablename__ = 'processing_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = Column(String(50), nullable=False)  # success, partial, failed
    users_processed = Column(Integer, default=0)
    meetings_found = Column(Integer, default=0)
    meetings_processed = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ProcessingLog(id={self.id}, run_timestamp='{self.run_timestamp}', status='{self.status}')>"


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables in the database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Drop all tables from the database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

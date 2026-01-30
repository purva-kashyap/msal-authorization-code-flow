"""
Database configuration and session management using SQLAlchemy async.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Float
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
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
    """User token model for storing encrypted OAuth tokens."""
    
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


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ PostgreSQL database initialized")
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print("⚠️  Running without database - some features will be disabled")
        print("⚠️  To fix: Ensure PostgreSQL is running and database 'entra_tokens' exists")
        # Don't raise - allow app to start without DB


async def close_db():
    """Close database connections."""
    try:
        await engine.dispose()
        print("✓ Database connections closed")
    except Exception:
        pass  # Ignore errors on shutdown


async def close_db():
    """Close database connections."""
    await engine.dispose()
    print("✓ Database connections closed")

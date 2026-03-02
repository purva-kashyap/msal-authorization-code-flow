"""
Database engine configuration.
"""
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
)

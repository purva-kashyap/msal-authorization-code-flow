#!/usr/bin/env python3
"""
Database initialization script for the cron job service.
Run this to create the required database tables.
"""
import asyncio
import logging
from db import create_tables, drop_tables

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_db():
    """Initialize database tables."""
    logger.info("Creating database tables...")
    try:
        await create_tables()
        logger.info("✓ Database tables created successfully!")
        logger.info("")
        logger.info("Created tables:")
        logger.info("  - user_processing_status")
        logger.info("  - meeting_records")
        logger.info("  - processing_logs")
        logger.info("")
        logger.info("Note: user_tokens table should already exist from the main app")
    except Exception as e:
        logger.error(f"✗ Error creating tables: {str(e)}")
        raise


async def reset_db():
    """Drop and recreate all tables. WARNING: This deletes all data!"""
    logger.warning("=" * 80)
    logger.warning("WARNING: This will DELETE ALL DATA in the cron job tables!")
    logger.warning("=" * 80)
    
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() != "yes":
        logger.info("Operation cancelled.")
        return
    
    logger.info("Dropping all cron job tables...")
    try:
        await drop_tables()
        logger.info("✓ Tables dropped")
        
        logger.info("Creating fresh tables...")
        await create_tables()
        logger.info("✓ Database reset successfully!")
    except Exception as e:
        logger.error(f"✗ Error resetting database: {str(e)}")
        raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_db())
    else:
        asyncio.run(init_db())

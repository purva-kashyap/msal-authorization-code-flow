#!/usr/bin/env python3
"""
Database initialization script for MCP-based cron job service.
"""
import asyncio
import logging
from db import create_tables, drop_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def init_db() -> None:
    logger.info("Creating database tables...")
    await create_tables()
    logger.info("Database tables created successfully")


async def reset_db() -> None:
    logger.warning("This will DELETE ALL DATA in cron-job-with-mcp tables")
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Operation cancelled")
        return

    await drop_tables()
    await create_tables()
    logger.info("Database reset complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_db())
    else:
        asyncio.run(init_db())

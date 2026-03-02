"""
Cron job entry point for processing Teams and Zoom meeting recordings.

Features:
- PostgreSQL advisory lock prevents overlapping runs
- Graceful shutdown on SIGTERM / SIGINT
"""
import asyncio
import logging
import signal
from contextlib import asynccontextmanager

from sqlalchemy import text

from config import settings
from db import create_tables, engine
from meeting_processor import MeetingProcessor

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Unique advisory-lock ID (arbitrary 64-bit int)
_ADVISORY_LOCK_ID = 738_291_045

# Global event for signalling graceful shutdown
_shutdown_event = asyncio.Event()


def _handle_signal(sig: signal.Signals) -> None:
    logger.info("Received %s — initiating graceful shutdown", sig.name)
    _shutdown_event.set()


@asynccontextmanager
async def advisory_lock():
    """
    Acquire a PostgreSQL session-level advisory lock.

    If another process already holds the lock, ``pg_try_advisory_lock``
    returns ``False`` immediately (non-blocking) and we abort the run.
    The lock is automatically released when the connection is returned.
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": _ADVISORY_LOCK_ID},
        )
        acquired = result.scalar()
        if not acquired:
            logger.warning("Another cron instance is already running — exiting")
            raise SystemExit(0)
        logger.info("Advisory lock acquired")
        try:
            yield
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": _ADVISORY_LOCK_ID},
            )
            logger.info("Advisory lock released")


async def main():
    # Install signal handlers (SIGTERM for container orchestrators, SIGINT for Ctrl-C)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    logger.info("=" * 80)
    logger.info("Starting meeting transcript processing cron job")
    logger.info("=" * 80)

    await create_tables()

    async with advisory_lock():
        processor = MeetingProcessor(shutdown_event=_shutdown_event)
        try:
            stats = await processor.process_all_users()
        finally:
            await processor.close()

    logger.info("=" * 80)
    logger.info("Cron job completed — %s", stats)
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

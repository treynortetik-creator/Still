"""Background scheduler for autopilot monitoring."""
import asyncio
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


class AutopilotScheduler:
    """
    Background scheduler for autopilot feed monitoring.

    Runs as an asyncio task within the FastAPI process.
    """

    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval = check_interval_seconds
        self.is_running = False
        self.task = None

    async def start(self):
        """Start the scheduler background task."""
        if self.is_running:
            return

        self.is_running = True
        self.task = asyncio.create_task(self._run())
        logger.info("Autopilot scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Autopilot scheduler stopped")

    async def _run(self):
        """Main scheduler loop."""
        # Initial delay to let app fully start
        await asyncio.sleep(10)

        while self.is_running:
            try:
                await self._check_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def _check_cycle(self):
        """Run a single check cycle."""
        from app.services.autopilot import check_due_sources, process_pending_items

        # 1. Check sources that are due for update
        sources_checked = await check_due_sources()
        if sources_checked > 0:
            logger.info(f"Checked {sources_checked} sources")

        # 2. Process pending feed items (create jobs)
        jobs_created = await process_pending_items(limit=3)
        if jobs_created > 0:
            logger.info(f"Created {jobs_created} jobs from feed items")


# Global scheduler instance
_scheduler = None


async def get_scheduler() -> AutopilotScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AutopilotScheduler(check_interval_seconds=60)
    return _scheduler


async def start_scheduler():
    """Start the global scheduler."""
    scheduler = await get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler."""
    scheduler = await get_scheduler()
    await scheduler.stop()

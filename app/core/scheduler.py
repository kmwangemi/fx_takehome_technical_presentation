import asyncio
from app.core.config import settings
from app.core.logging import logger
from app.services.rate_service import fetch_and_store_rates
from app.db.database import ASYNC_SESSION_LOCAL

_scheduler_task = None

async def _poll_rates():
    while True:
        try:
            async with ASYNC_SESSION_LOCAL() as db:
                await fetch_and_store_rates(db)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("scheduler.error", error=str(e))
            
        await asyncio.sleep(settings.RATE_POLL_INTERVAL_SECONDS)

def start_scheduler():
    global _scheduler_task
    if _scheduler_task is None:
        loop = asyncio.get_running_loop()
        _scheduler_task = loop.create_task(_poll_rates())
        logger.info("scheduler.started")

def stop_scheduler():
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("scheduler.stopped")

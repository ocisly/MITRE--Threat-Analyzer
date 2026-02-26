import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import update

from app.config import settings
from app.database import SessionLocal
from app.models.sync_log import SyncLog
from app.sync.downloader import download_stix
from app.sync.parser import sync_domain

logger = logging.getLogger(__name__)


async def run_sync_all_domains() -> None:
    """Download and parse STIX data for all configured domains."""
    for domain in settings.mitre_domains:
        with SessionLocal() as db:
            log = SyncLog(domain=domain, status="running")
            db.add(log)
            db.commit()
            db.refresh(log)
            log_id = log.id

        try:
            stix_file = await download_stix(domain, settings.stix_data_dir)

            # sync_domain is synchronous (SQLAlchemy bulk inserts).
            # Run in a thread so it doesn't block the async event loop.
            def _import():
                with SessionLocal() as db:
                    result = sync_domain(domain, stix_file, db)
                    db.commit()
                    return result

            stats = await asyncio.to_thread(_import)

            with SessionLocal() as db:
                db.execute(
                    update(SyncLog)
                    .where(SyncLog.id == log_id)
                    .values(
                        status="success",
                        completed_at=datetime.now(timezone.utc),
                        tactics_count=stats["tactics"],
                        techniques_count=stats["techniques"],
                        mitigations_count=stats["mitigations"],
                    )
                )
                db.commit()

            logger.info(
                "Sync complete for %s: %d tactics, %d techniques, %d mitigations",
                domain,
                stats["tactics"],
                stats["techniques"],
                stats["mitigations"],
            )

        except Exception as exc:
            logger.exception("Sync failed for domain %s", domain, exc_info=exc)
            with SessionLocal() as db:
                db.execute(
                    update(SyncLog)
                    .where(SyncLog.id == log_id)
                    .values(
                        status="error",
                        completed_at=datetime.now(timezone.utc),
                        error_message=str(exc),
                    )
                )
                db.commit()


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_sync_all_domains,
        trigger="interval",
        hours=settings.sync_interval_hours,
        misfire_grace_time=3600,
        id="mitre_sync",
        replace_existing=True,
    )
    return scheduler

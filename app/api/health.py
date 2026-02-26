"""Health and sync status endpoints."""
import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repository.mitre_repository import MITRERepository
from app.schemas.sync import SyncStatusResponse
from app.sync.scheduler import run_sync_all_domains

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    with SessionLocal() as db:
        yield db


def get_repo(db: Session = Depends(get_db)) -> MITRERepository:
    return MITRERepository(db)


@router.get("/health", tags=["health"], summary="Application health check")
def health():
    return {"status": "ok", "version": "0.2.0"}


@router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    tags=["sync"],
    summary="Data sync status",
)
def sync_status(repo: MITRERepository = Depends(get_repo)):
    log = repo.get_latest_sync_log()
    if log is None:
        return SyncStatusResponse.no_data()
    return SyncStatusResponse.from_orm(log)


@router.post(
    "/sync/trigger",
    tags=["sync"],
    summary="Manually trigger MITRE data sync",
    status_code=202,
)
async def trigger_sync(background_tasks: BackgroundTasks):
    """Starts sync in the background. Returns immediately with 202 Accepted."""
    background_tasks.add_task(run_sync_all_domains)
    logger.info("Manual sync triggered via API")
    return {"message": "Sync started in background"}

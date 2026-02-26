"""Pydantic schemas for sync status endpoints."""
from datetime import datetime
from pydantic import BaseModel
from app.models.sync_log import SyncLog


class SyncStatusResponse(BaseModel):
    domain: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    tactics_count: int
    techniques_count: int
    mitigations_count: int
    error_message: str | None

    @classmethod
    def from_orm(cls, log: SyncLog) -> "SyncStatusResponse":
        return cls(
            domain=log.domain,
            status=log.status,
            started_at=log.started_at,
            completed_at=log.completed_at,
            tactics_count=log.tactics_count,
            techniques_count=log.techniques_count,
            mitigations_count=log.mitigations_count,
            error_message=log.error_message,
        )

    @classmethod
    def no_data(cls, domain: str = "enterprise-attack") -> "SyncStatusResponse":
        return cls(
            domain=domain,
            status="never_synced",
            started_at=None,
            completed_at=None,
            tactics_count=0,
            techniques_count=0,
            mitigations_count=0,
            error_message=None,
        )

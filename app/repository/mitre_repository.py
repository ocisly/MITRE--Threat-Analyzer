"""Data access layer — pure read queries against the MITRE ATT&CK SQLite/Azure SQL DB."""
import json
from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session

from app.models.tactic import Tactic
from app.models.technique import Technique
from app.models.mitigation import Mitigation
from app.models.sync_log import SyncLog
from app.models.associations import technique_mitigation


class MITRERepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Tactics ──────────────────────────────────────────────────────────────

    def get_all_tactics(self) -> list[Tactic]:
        return list(
            self.db.execute(select(Tactic).order_by(Tactic.attack_id)).scalars().all()
        )

    def get_tactic_by_id(self, tactic_id: int) -> Tactic | None:
        return self.db.get(Tactic, tactic_id)

    # ── Techniques ───────────────────────────────────────────────────────────

    def get_techniques_by_tactic(
        self, tactic_id: int, include_subtechniques: bool = True
    ) -> list[Technique]:
        stmt = (
            select(Technique)
            .join(Technique.tactics)
            .where(Tactic.id == tactic_id)
            .order_by(Technique.attack_id)
        )
        if not include_subtechniques:
            stmt = stmt.where(Technique.is_subtechnique == False)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())

    def get_technique_by_attack_id(self, attack_id: str) -> Technique | None:
        return self.db.execute(
            select(Technique).where(Technique.attack_id == attack_id)
        ).scalar_one_or_none()

    def search_techniques(self, keywords: str, limit: int = 20) -> list[Technique]:
        """Full-text search across technique name and description."""
        terms = [k.strip() for k in keywords.split(",") if k.strip()]
        if not terms:
            return []
        conditions = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.append(
                or_(
                    Technique.name.ilike(pattern),
                    Technique.description.ilike(pattern),
                )
            )
        stmt = (
            select(Technique)
            .where(or_(*conditions))
            .order_by(Technique.attack_id)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ── Mitigations ──────────────────────────────────────────────────────────

    def get_mitigation_by_attack_id(self, attack_id: str) -> Mitigation | None:
        return self.db.execute(
            select(Mitigation).where(Mitigation.attack_id == attack_id)
        ).scalar_one_or_none()

    def get_mitigations_for_technique(self, attack_id: str) -> list[dict]:
        """Returns list of {mitigation, relationship_description} dicts."""
        tech = self.get_technique_by_attack_id(attack_id)
        if not tech:
            return []
        rows = self.db.execute(
            select(Mitigation, technique_mitigation.c.relationship_description)
            .join(
                technique_mitigation,
                Mitigation.id == technique_mitigation.c.mitigation_id,
            )
            .where(technique_mitigation.c.technique_id == tech.id)
            .order_by(Mitigation.attack_id)
        ).all()
        return [
            {
                "mitigation": row[0],
                "relationship_description": row[1],
            }
            for row in rows
        ]

    # ── Sync log ─────────────────────────────────────────────────────────────

    def get_latest_sync_log(self, domain: str = "enterprise-attack") -> SyncLog | None:
        return self.db.execute(
            select(SyncLog)
            .where(SyncLog.domain == domain)
            .order_by(desc(SyncLog.started_at))
            .limit(1)
        ).scalar_one_or_none()

    # ── Agent helper formatters ───────────────────────────────────────────────

    def format_technique_for_agent(self, t: Technique) -> dict:
        """Compact dict for LLM consumption."""
        return {
            "attack_id": t.attack_id,
            "name": t.name,
            "is_subtechnique": t.is_subtechnique,
            "tactics": [tac.name for tac in t.tactics],
            "platforms": json.loads(t.platforms) if t.platforms else [],
            "description": (t.description or "")[:500],
            "detection": (t.detection or "")[:300],
            "url": t.url or "",
        }

    def format_mitigations_for_agent(self, rows: list[dict]) -> list[dict]:
        """Compact list for LLM consumption."""
        result = []
        for row in rows:
            m: Mitigation = row["mitigation"]
            result.append(
                {
                    "attack_id": m.attack_id,
                    "name": m.name,
                    "description": (m.description or "")[:400],
                    "relationship_context": row["relationship_description"] or "",
                    "url": m.url or "",
                }
            )
        return result

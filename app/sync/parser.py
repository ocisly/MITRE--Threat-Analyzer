"""Parse MITRE ATT&CK STIX 2.1 JSON and upsert into SQLite/Azure SQL."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.models.associations import technique_mitigation, technique_tactic
from app.models.mitigation import Mitigation
from app.models.sync_log import SyncLog
from app.models.tactic import Tactic
from app.models.technique import Technique

logger = logging.getLogger(__name__)


def _get_attack_id(stix_obj) -> str:
    """Extract MITRE ATT&CK ID (e.g. T1078, TA0001) from STIX external references."""
    for ref in getattr(stix_obj, "external_references", []):
        if getattr(ref, "source_name", "") == "mitre-attack":
            return getattr(ref, "external_id", "")
    return ""


def _get_url(stix_obj) -> str | None:
    for ref in getattr(stix_obj, "external_references", []):
        if getattr(ref, "source_name", "") == "mitre-attack":
            return getattr(ref, "url", None)
    return None


def _json_list(value) -> str | None:
    if not value:
        return None
    return json.dumps(list(value))


def _upsert_tactic(db: Session, stix_obj, domain: str) -> int | None:
    attack_id = _get_attack_id(stix_obj)
    if not attack_id:
        return None

    data = {
        "stix_id": stix_obj.id,
        "attack_id": attack_id,
        "name": stix_obj.name,
        "shortname": getattr(stix_obj, "x_mitre_shortname", ""),
        "description": getattr(stix_obj, "description", None),
        "url": _get_url(stix_obj),
        "domain": domain,
        "updated_at": datetime.now(timezone.utc),
    }

    existing = db.execute(
        select(Tactic.id).where(Tactic.stix_id == stix_obj.id)
    ).scalar_one_or_none()

    if existing:
        db.execute(update(Tactic).where(Tactic.id == existing).values(**data))
        return existing
    else:
        data["created_at"] = datetime.now(timezone.utc)
        result = db.execute(insert(Tactic).values(**data))
        return result.inserted_primary_key[0]


def _upsert_technique(db: Session, stix_obj, domain: str) -> int | None:
    attack_id = _get_attack_id(stix_obj)
    if not attack_id:
        return None

    is_subtechnique = "." in attack_id

    data = {
        "stix_id": stix_obj.id,
        "attack_id": attack_id,
        "name": stix_obj.name,
        "description": getattr(stix_obj, "description", None),
        "detection": getattr(stix_obj, "x_mitre_detection", None),
        "is_subtechnique": is_subtechnique,
        "platforms": _json_list(getattr(stix_obj, "x_mitre_platforms", None)),
        "data_sources": _json_list(getattr(stix_obj, "x_mitre_data_sources", None)),
        "url": _get_url(stix_obj),
        "domain": domain,
        "updated_at": datetime.now(timezone.utc),
    }

    existing = db.execute(
        select(Technique.id).where(Technique.stix_id == stix_obj.id)
    ).scalar_one_or_none()

    if existing:
        db.execute(update(Technique).where(Technique.id == existing).values(**data))
        return existing
    else:
        data["created_at"] = datetime.now(timezone.utc)
        result = db.execute(insert(Technique).values(**data))
        return result.inserted_primary_key[0]


def _upsert_mitigation(db: Session, stix_obj, domain: str) -> int | None:
    attack_id = _get_attack_id(stix_obj)
    if not attack_id:
        return None

    data = {
        "stix_id": stix_obj.id,
        "attack_id": attack_id,
        "name": stix_obj.name,
        "description": getattr(stix_obj, "description", None),
        "url": _get_url(stix_obj),
        "domain": domain,
        "updated_at": datetime.now(timezone.utc),
    }

    existing = db.execute(
        select(Mitigation.id).where(Mitigation.stix_id == stix_obj.id)
    ).scalar_one_or_none()

    if existing:
        db.execute(update(Mitigation).where(Mitigation.id == existing).values(**data))
        return existing
    else:
        data["created_at"] = datetime.now(timezone.utc)
        result = db.execute(insert(Mitigation).values(**data))
        return result.inserted_primary_key[0]


def sync_domain(domain: str, stix_file: Path, db: Session) -> dict:
    """Parse STIX file and upsert all ATT&CK objects into the database.

    Returns stats dict: {'tactics': N, 'techniques': N, 'mitigations': N}
    """
    from mitreattack.stix20 import MitreAttackData

    logger.info("Parsing STIX file: %s", stix_file)
    attack_data = MitreAttackData(str(stix_file))

    # ── Step 1: Upsert Tactics ─────────────────────────────────────────────
    tactics_map: dict[str, int] = {}  # shortname → DB id
    stix_id_to_tactic_id: dict[str, int] = {}  # STIX id → DB id

    tactics = attack_data.get_tactics(remove_revoked_deprecated=True)
    for tactic in tactics:
        db_id = _upsert_tactic(db, tactic, domain)
        if db_id:
            shortname = getattr(tactic, "x_mitre_shortname", "")
            tactics_map[shortname] = db_id
            stix_id_to_tactic_id[tactic.id] = db_id

    db.flush()
    logger.info("Upserted %d tactics", len(tactics_map))

    # ── Step 2: Upsert Techniques ──────────────────────────────────────────
    techniques_stix_to_id: dict[str, int] = {}  # STIX id → DB id
    attack_id_to_db_id: dict[str, int] = {}  # attack_id → DB id

    techniques = attack_data.get_techniques(
        include_subtechniques=True, remove_revoked_deprecated=True
    )
    for technique in techniques:
        db_id = _upsert_technique(db, technique, domain)
        if db_id:
            techniques_stix_to_id[technique.id] = db_id
            attack_id_to_db_id[_get_attack_id(technique)] = db_id

    db.flush()
    logger.info("Upserted %d techniques", len(techniques_stix_to_id))

    # ── Step 3: Set parent_technique_id for sub-techniques ────────────────
    for technique in techniques:
        attack_id = _get_attack_id(technique)
        if "." in attack_id:
            parent_attack_id = attack_id.rsplit(".", 1)[0]
            parent_db_id = attack_id_to_db_id.get(parent_attack_id)
            child_db_id = techniques_stix_to_id.get(technique.id)
            if parent_db_id and child_db_id:
                db.execute(
                    update(Technique)
                    .where(Technique.id == child_db_id)
                    .values(parent_technique_id=parent_db_id)
                )

    db.flush()

    # ── Step 4: technique ↔ tactic relationships (via kill_chain_phases) ──
    for technique in techniques:
        tech_db_id = techniques_stix_to_id.get(technique.id)
        if not tech_db_id:
            continue
        for phase in getattr(technique, "kill_chain_phases", []) or []:
            tactic_db_id = tactics_map.get(phase.phase_name)
            if tactic_db_id:
                exists = db.execute(
                    select(technique_tactic).where(
                        technique_tactic.c.technique_id == tech_db_id,
                        technique_tactic.c.tactic_id == tactic_db_id,
                    )
                ).first()
                if not exists:
                    db.execute(
                        insert(technique_tactic).values(
                            technique_id=tech_db_id, tactic_id=tactic_db_id
                        )
                    )

    db.flush()

    # ── Step 5: Upsert Mitigations ─────────────────────────────────────────
    mitigations_stix_to_id: dict[str, int] = {}

    mitigations = attack_data.get_mitigations(remove_revoked_deprecated=True)
    for mitigation in mitigations:
        db_id = _upsert_mitigation(db, mitigation, domain)
        if db_id:
            mitigations_stix_to_id[mitigation.id] = db_id

    db.flush()
    logger.info("Upserted %d mitigations", len(mitigations_stix_to_id))

    # ── Step 6: technique ↔ mitigation relationships ───────────────────────
    # get_all_mitigations_mitigating_all_techniques() returns:
    # { technique_stix_id: [{"object": mitigation, "relationships": [rel, ...]}, ...] }
    mit_by_technique = attack_data.get_all_mitigations_mitigating_all_techniques()
    rel_count = 0
    for technique_stix_id, entries in mit_by_technique.items():
        tech_db_id = techniques_stix_to_id.get(technique_stix_id)
        if not tech_db_id:
            continue
        for entry in entries:
            mit_stix_obj = entry["object"]
            mit_db_id = mitigations_stix_to_id.get(mit_stix_obj.id)
            if not mit_db_id:
                continue
            # Use description from first relationship (there is usually exactly one)
            rel_desc = None
            if entry.get("relationships"):
                rel_desc = getattr(entry["relationships"][0], "description", None)
            exists = db.execute(
                select(technique_mitigation).where(
                    technique_mitigation.c.technique_id == tech_db_id,
                    technique_mitigation.c.mitigation_id == mit_db_id,
                )
            ).first()
            if exists:
                db.execute(
                    update(technique_mitigation)
                    .where(
                        technique_mitigation.c.technique_id == tech_db_id,
                        technique_mitigation.c.mitigation_id == mit_db_id,
                    )
                    .values(relationship_description=rel_desc)
                )
            else:
                db.execute(
                    insert(technique_mitigation).values(
                        technique_id=tech_db_id,
                        mitigation_id=mit_db_id,
                        relationship_description=rel_desc,
                    )
                )
            rel_count += 1

    db.flush()
    logger.info("Upserted %d technique-mitigation relationships", rel_count)

    return {
        "tactics": len(tactics_map),
        "techniques": len(techniques_stix_to_id),
        "mitigations": len(mitigations_stix_to_id),
    }

"""MAF @tool functions — MITRE ATT&CK query tools for the AI agent.

Each tool opens its own DB session to keep tools stateless and thread-safe.
"""
import json
import logging

from agent_framework import tool

from app.database import SessionLocal
from app.repository.mitre_repository import MITRERepository

logger = logging.getLogger(__name__)


@tool
def search_techniques(keywords: str) -> str:
    """Search MITRE ATT&CK techniques by comma-separated keywords extracted
    from attack symptoms. Returns techniques ranked by relevance with their
    associated tactics. Use broad keywords for better recall.
    Example: keywords="outbound traffic, admin login, credential"
    """
    with SessionLocal() as db:
        repo = MITRERepository(db)
        techniques = repo.search_techniques(keywords, limit=20)
        if not techniques:
            return json.dumps({"found": 0, "results": []})
        results = [repo.format_technique_for_agent(t) for t in techniques]
        return json.dumps({"found": len(results), "results": results}, ensure_ascii=False)


@tool
def get_technique_detail(attack_id: str) -> str:
    """Get full details of a specific MITRE technique including description,
    detection guidance, platforms, sub-techniques, and all associated mitigations
    with their relationship context.
    attack_id format: T1078 (parent) or T1078.001 (sub-technique)
    """
    with SessionLocal() as db:
        repo = MITRERepository(db)
        tech = repo.get_technique_by_attack_id(attack_id)
        if not tech:
            return json.dumps({"error": f"Technique {attack_id} not found"})
        detail = repo.format_technique_for_agent(tech)
        detail["subtechniques"] = [sub.attack_id for sub in tech.subtechniques]
        mit_rows = repo.get_mitigations_for_technique(attack_id)
        detail["mitigations"] = repo.format_mitigations_for_agent(mit_rows)
        return json.dumps(detail, ensure_ascii=False)


@tool
def get_all_tactics() -> str:
    """List all MITRE ATT&CK tactics in order. Use this to understand the
    full attack lifecycle phases (Reconnaissance → Exfiltration → Impact).
    Helpful when you need to situate a technique within the kill chain.
    """
    with SessionLocal() as db:
        repo = MITRERepository(db)
        tactics = repo.get_all_tactics()
        results = [
            {
                "attack_id": t.attack_id,
                "name": t.name,
                "shortname": t.shortname,
                "description": (t.description or "")[:200],
                "url": t.url or "",
            }
            for t in tactics
        ]
        return json.dumps({"count": len(results), "tactics": results}, ensure_ascii=False)


@tool
def find_mitigations(technique_id: str) -> str:
    """Get all mitigations for a specific MITRE technique including the
    relationship description explaining how each mitigation applies to
    this technique. Use this to generate specific remediation advice.
    technique_id format: T1078 or T1078.001
    """
    with SessionLocal() as db:
        repo = MITRERepository(db)
        rows = repo.get_mitigations_for_technique(technique_id)
        if not rows:
            return json.dumps(
                {"technique_id": technique_id, "found": 0, "mitigations": []}
            )
        formatted = repo.format_mitigations_for_agent(rows)
        return json.dumps(
            {"technique_id": technique_id, "found": len(formatted), "mitigations": formatted},
            ensure_ascii=False,
        )

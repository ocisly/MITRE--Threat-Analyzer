"""Browse REST endpoints — read-only MITRE ATT&CK data."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repository.mitre_repository import MITRERepository
from app.schemas.mitre import (
    TacticSchema,
    TechniqueSchema,
    TechniqueDetailSchema,
    MitigationSchema,
)

router = APIRouter()


def get_db():
    with SessionLocal() as db:
        yield db


def get_repo(db: Session = Depends(get_db)) -> MITRERepository:
    return MITRERepository(db)


@router.get("/tactics", response_model=list[TacticSchema], summary="List all tactics")
def list_tactics(repo: MITRERepository = Depends(get_repo)):
    return [TacticSchema.from_orm(t) for t in repo.get_all_tactics()]


@router.get(
    "/tactics/{tactic_id}/techniques",
    response_model=list[TechniqueSchema],
    summary="List techniques for a tactic",
)
def list_techniques_by_tactic(
    tactic_id: int,
    include_subtechniques: bool = True,
    repo: MITRERepository = Depends(get_repo),
):
    tactic = repo.get_tactic_by_id(tactic_id)
    if not tactic:
        raise HTTPException(status_code=404, detail=f"Tactic {tactic_id} not found")
    techniques = repo.get_techniques_by_tactic(tactic_id, include_subtechniques)
    return [TechniqueSchema.from_orm(t) for t in techniques]


@router.get(
    "/techniques/search",
    response_model=list[TechniqueSchema],
    summary="Search techniques by keyword",
)
def search_techniques(q: str, repo: MITRERepository = Depends(get_repo)):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=422, detail="Query must be at least 2 characters")
    techniques = repo.search_techniques(q)
    return [TechniqueSchema.from_orm(t) for t in techniques]


@router.get(
    "/techniques/{attack_id}",
    response_model=TechniqueDetailSchema,
    summary="Get technique details",
)
def get_technique(attack_id: str, repo: MITRERepository = Depends(get_repo)):
    tech = repo.get_technique_by_attack_id(attack_id.upper())
    if not tech:
        raise HTTPException(status_code=404, detail=f"Technique {attack_id} not found")
    mitigation_rows = repo.get_mitigations_for_technique(attack_id.upper())
    return TechniqueDetailSchema.from_orm(tech, mitigation_rows)


@router.get(
    "/mitigations/{attack_id}",
    response_model=MitigationSchema,
    summary="Get mitigation details",
)
def get_mitigation(attack_id: str, repo: MITRERepository = Depends(get_repo)):
    mit = repo.get_mitigation_by_attack_id(attack_id.upper())
    if not mit:
        raise HTTPException(status_code=404, detail=f"Mitigation {attack_id} not found")
    return MitigationSchema.from_orm(mit)

"""Pydantic response schemas for MITRE ATT&CK data."""
import json
from pydantic import BaseModel, model_validator
from app.models.tactic import Tactic
from app.models.technique import Technique
from app.models.mitigation import Mitigation


class TacticSchema(BaseModel):
    id: int
    attack_id: str
    name: str
    shortname: str
    description: str | None
    url: str | None

    @classmethod
    def from_orm(cls, t: Tactic) -> "TacticSchema":
        return cls(
            id=t.id,
            attack_id=t.attack_id,
            name=t.name,
            shortname=t.shortname,
            description=t.description,
            url=t.url,
        )


class TechniqueSchema(BaseModel):
    id: int
    attack_id: str
    name: str
    is_subtechnique: bool
    parent_attack_id: str | None
    tactic_names: list[str]
    platforms: list[str]
    url: str | None

    @classmethod
    def from_orm(cls, t: Technique) -> "TechniqueSchema":
        parent_id = None
        if t.parent:
            parent_id = t.parent.attack_id
        return cls(
            id=t.id,
            attack_id=t.attack_id,
            name=t.name,
            is_subtechnique=t.is_subtechnique,
            parent_attack_id=parent_id,
            tactic_names=[tac.name for tac in t.tactics],
            platforms=json.loads(t.platforms) if t.platforms else [],
            url=t.url,
        )


class MitigationBriefSchema(BaseModel):
    attack_id: str
    name: str
    relationship_context: str | None


class TechniqueDetailSchema(BaseModel):
    id: int
    attack_id: str
    name: str
    description: str | None
    detection: str | None
    is_subtechnique: bool
    parent_attack_id: str | None
    tactic_names: list[str]
    platforms: list[str]
    data_sources: list[str]
    url: str | None
    subtechnique_ids: list[str]
    mitigations: list[MitigationBriefSchema]

    @classmethod
    def from_orm(
        cls, t: Technique, mitigation_rows: list[dict]
    ) -> "TechniqueDetailSchema":
        parent_id = t.parent.attack_id if t.parent else None
        return cls(
            id=t.id,
            attack_id=t.attack_id,
            name=t.name,
            description=t.description,
            detection=t.detection,
            is_subtechnique=t.is_subtechnique,
            parent_attack_id=parent_id,
            tactic_names=[tac.name for tac in t.tactics],
            platforms=json.loads(t.platforms) if t.platforms else [],
            data_sources=json.loads(t.data_sources) if t.data_sources else [],
            url=t.url,
            subtechnique_ids=[sub.attack_id for sub in t.subtechniques],
            mitigations=[
                MitigationBriefSchema(
                    attack_id=row["mitigation"].attack_id,
                    name=row["mitigation"].name,
                    relationship_context=row["relationship_description"],
                )
                for row in mitigation_rows
            ],
        )


class MitigationSchema(BaseModel):
    id: int
    attack_id: str
    name: str
    description: str | None
    url: str | None

    @classmethod
    def from_orm(cls, m: Mitigation) -> "MitigationSchema":
        return cls(
            id=m.id,
            attack_id=m.attack_id,
            name=m.name,
            description=m.description,
            url=m.url,
        )

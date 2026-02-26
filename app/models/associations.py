from sqlalchemy import Table, Column, ForeignKey, Text
from app.models.base import Base

# Many-to-many: Technique ↔ Tactic
technique_tactic = Table(
    "technique_tactic",
    Base.metadata,
    Column("technique_id", ForeignKey("techniques.id", ondelete="CASCADE"), primary_key=True),
    Column("tactic_id", ForeignKey("tactics.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many: Technique ↔ Mitigation (with relationship context)
technique_mitigation = Table(
    "technique_mitigation",
    Base.metadata,
    Column("technique_id", ForeignKey("techniques.id", ondelete="CASCADE"), primary_key=True),
    Column("mitigation_id", ForeignKey("mitigations.id", ondelete="CASCADE"), primary_key=True),
    # MITRE original relationship description — used by MAF Agent to generate specific advice
    Column("relationship_description", Text, nullable=True),
)

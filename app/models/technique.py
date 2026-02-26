from sqlalchemy import String, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.associations import technique_tactic, technique_mitigation


class Technique(Base, TimestampMixin):
    __tablename__ = "techniques"
    __table_args__ = (
        Index("ix_techniques_attack_id", "attack_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stix_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    attack_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    detection: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_subtechnique: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parent_technique_id: Mapped[int | None] = mapped_column(
        ForeignKey("techniques.id", ondelete="NO ACTION"), nullable=True
    )
    # JSON arrays stored as strings (e.g. '["Windows","Linux"]')
    platforms: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, default="enterprise-attack")

    parent: Mapped["Technique | None"] = relationship(
        "Technique", remote_side="Technique.id", back_populates="subtechniques"
    )
    subtechniques: Mapped[list["Technique"]] = relationship(
        "Technique", back_populates="parent"
    )
    tactics: Mapped[list["Tactic"]] = relationship(  # noqa: F821
        "Tactic",
        secondary=technique_tactic,
        back_populates="techniques",
    )
    mitigations: Mapped[list["Mitigation"]] = relationship(  # noqa: F821
        "Mitigation",
        secondary=technique_mitigation,
        back_populates="techniques",
    )

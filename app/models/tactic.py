from sqlalchemy import String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.associations import technique_tactic


class Tactic(Base, TimestampMixin):
    __tablename__ = "tactics"
    __table_args__ = (
        Index("ix_tactics_attack_id", "attack_id"),
        Index("ix_tactics_shortname", "shortname"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stix_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    attack_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    shortname: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, default="enterprise-attack")

    techniques: Mapped[list["Technique"]] = relationship(  # noqa: F821
        "Technique",
        secondary=technique_tactic,
        back_populates="tactics",
    )

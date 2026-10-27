from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Enumeration(Base):
    __tablename__ = "enumerations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    values: Mapped[list["EnumValue"]] = relationship(
        back_populates="enumeration",
        cascade="all, delete-orphan",
        order_by="EnumValue.position",
    )


class EnumValue(Base):
    __tablename__ = "enum_values"
    __table_args__ = (UniqueConstraint("enumeration_id", "value", name="uq_enum_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    enumeration_id: Mapped[int] = mapped_column(ForeignKey("enumerations.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)

    enumeration: Mapped[Enumeration] = relationship(back_populates="values")

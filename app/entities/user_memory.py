
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.user import User



class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_memory_user_key"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key = True,
        default=uuid.uuid7,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="general",
        index=True
    )
    key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memories",
    )


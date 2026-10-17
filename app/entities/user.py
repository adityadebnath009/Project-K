import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.conversation import Conversation


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid7,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

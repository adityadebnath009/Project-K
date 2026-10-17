import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.conversation_summary import ConversationSummary
    from app.entities.message import Message
    from app.entities.project import Project
    from app.entities.user import User


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid7,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
    Uuid,
    ForeignKey("projects.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
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

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    user: Mapped["User"] = relationship(
    "User",
    back_populates="conversations",
    )

    summaries: Mapped[list["ConversationSummary"]] = relationship(
        "ConversationSummary",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )
    project: Mapped["Project | None"] = relationship(
    "Project",
    back_populates="conversations",
    )



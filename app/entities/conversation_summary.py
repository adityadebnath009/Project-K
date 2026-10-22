import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
    True_,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities import Base

if TYPE_CHECKING:
    from app.entities.conversation import Conversation




class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    __table_args__=(
        UniqueConstraint(
            "conversation_id",
            "version",
            name="uq_conversation_summary_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable = False,
        index=True

    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    summary_content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    last_covered_sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="summaries"
    )
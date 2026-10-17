import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.conversation import Conversation
    from app.entities.project_memory import ProjectMemory
    from app.entities.user import User




class Project(Base):
    __tablename__ = "projects"

    __table_args__= (
        UniqueConstraint("user_id", "name", name = "uq_project_user_name"),


    )
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
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    root_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
        back_populates="projects",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
    )
    memories: Mapped[list["ProjectMemory"]] = relationship(
        "ProjectMemory",
        back_populates="project",
        cascade="all, delete-orphan",
    )

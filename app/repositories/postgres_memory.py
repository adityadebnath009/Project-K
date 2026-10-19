
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db_session
from app.entities.project import Project
from app.entities.project_memory import ProjectMemory
from app.entities.user import User
from app.entities.user_memory import UserMemory
from app.exceptions.user_not_found_error import UserNotFoundError
from app.schemas.memory import (
     ExtractedMemoryPackage,
     MemoryItem,
     ProjectMemoryDTO,
     UserProfileDTO,
)


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
     return uuid.UUID(val) if isinstance(val, str) else val

def _normalize_key(text: str) -> str:
    """Normalizes keys/categories to uniform snake_case."""
    return text.strip().lower().replace(" ", "_").replace("-", "_")

def _deduplicate_items(items: list[MemoryItem]) -> list[MemoryItem]:
    """
    In-memory Python deduplication:
    1. Rejects blank keys or values.
    2. Normalizes keys into snake_case.
    3. If the LLM produces duplicate keys, keeps the one with highest confidence.
    """
    clean_map: dict[str, MemoryItem] = {}
    for item in items:
        norm_key = _normalize_key(item.key)
        val = item.value.strip()
        if not norm_key or not val:
            continue
        item.key = norm_key
        item.category = _normalize_key(item.category)
        existing = clean_map.get(norm_key)
        if existing is None or item.confidence >= existing.confidence:
            clean_map[norm_key] = item
    return list(clean_map.values())


class PostgresMemoryRepository:
    def save_extracted_package(
            self,
            user_id: str,
            project_id: str | None,
            package: ExtractedMemoryPackage,
        ) -> tuple[int, int]:
        u_id = _to_uuid(user_id)
        p_id = _to_uuid(project_id) if project_id else None
        user_count = 0
        project_count = 0
        # 1. In-memory deduplication & normalization
        deduped_user_facts = _deduplicate_items(package.user_facts)
        deduped_project_facts = _deduplicate_items(package.project_facts) if p_id else []
        with get_db_session() as session:
            # Verify user exists
            user = session.get(User, u_id)
            if not user:
                raise UserNotFoundError(f"User '{user_id}' does not exist.")
            now = datetime.now(timezone.utc)
            # 2. Atomic PostgreSQL UPSERT for User Facts
            for item in deduped_user_facts:
                stmt = (
                    pg_insert(UserMemory)
                    .values(
                        id=uuid.uuid7(),
                        user_id=u_id,
                        category=item.category,
                        key=item.key,
                        value=item.value,
                        confidence=item.confidence,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        constraint="uq_user_memory_user_key",
                        set_={
                            "category": item.category,
                            "value": item.value,
                            "confidence": item.confidence,
                            "updated_at": now,
                        },
                    )
                )
                session.execute(stmt)
                user_count += 1
            # 3. Atomic PostgreSQL UPSERT for Project Facts
            if p_id and deduped_project_facts:
                project = session.get(Project, p_id)
                if project:
                    for item in deduped_project_facts:
                        stmt = (
                            pg_insert(ProjectMemory)
                            .values(
                                id=uuid.uuid7(),
                                project_id=p_id,
                                category=item.category,
                                key=item.key,
                                value=item.value,
                                confidence=item.confidence,
                                created_at=now,
                                updated_at=now,
                            )
                            .on_conflict_do_update(
                                constraint="uq_project_memory_project_key",
                                set_={
                                    "category": item.category,
                                    "value": item.value,
                                    "confidence": item.confidence,
                                    "updated_at": now,
                                },
                            )
                        )
                        session.execute(stmt)
                        project_count += 1
            session.flush()
        return user_count, project_count

    
            
            
    def get_user_profile(self, user_id: str) -> UserProfileDTO | None:
        """Retrieves all active memory items for a user."""

        u_id = _to_uuid(user_id)

        with get_db_session() as session:
            stmt  = (
                select(UserMemory). 
                where(UserMemory.user_id == u_id). 
                order_by(UserMemory.confidence.desc(), UserMemory.updated_at.desc())
            )
            records = session.execute(stmt).scalars().all()
            items = [
                MemoryItem(
                        category= r.category,
                        key= r.key,
                        value= r.value,
                        confidence=r.confidence
                )
                for r in records
            ]

            return UserProfileDTO(user_id=str(u_id), memories=items)



        
    def get_project_memory(self, project_id: str) -> ProjectMemoryDTO | None:
        """Retrieves all active architecture memory items for a project."""
        p_id = _to_uuid(project_id)

        with get_db_session() as session:
            project = session.get(Project, p_id)

            if not project:
                return None
            stmt = (
                select(ProjectMemory). 
                where(ProjectMemory.project_id == p_id). 
                order_by(ProjectMemory.confidence.desc(), ProjectMemory.updated_at.desc())
            )
            records = session.execute(stmt).scalars().all()

            items = [ 
                MemoryItem(
                    category= r.category,
                    key= r.key,
                    value= r.value,
                    confidence=r.confidence
                )
                for r in records
            ]
            return ProjectMemoryDTO(
                project_id=str(project.id),
                project_name=project.name,
                root_path=project.root_path,
                memories=items,
            )





        
    def delete_user_memory(self, user_id: str, key: str) -> bool:
        """Deletes a specific user memory fact by key."""
        u_id = _to_uuid(user_id)
        norm_key = _normalize_key(key)

        with get_db_session() as session:
            stmt = (
                delete(UserMemory). 
                where(UserMemory.user_id == u_id, UserMemory.key==norm_key)
            )
            res = session.execute(stmt)

            return (res.rowcount or 0) > 0




    def delete_project_memory(self, project_id: str, key: str) -> bool:
        """Deletes a specific project memory fact by key."""
        p_id = _to_uuid(project_id)
        norm_key = _normalize_key(key)

        with get_db_session() as session:
            stmt = (
                delete(ProjectMemory).
                where(ProjectMemory.project_id == p_id, ProjectMemory.key == norm_key)
            )

            res = session.execute(stmt)
            return (res.rowcount or 0) > 0
    
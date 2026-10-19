import uuid

from sqlalchemy import select

from app.database import get_db_session
from app.entities import Project, User
from app.exceptions.user_not_found_error import UserNotFoundError
from app.schemas import ProjectDTO


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return uuid.UUID(val) if isinstance(val, str) else val



class PostgresProjectRepository:
    def get_or_create_project(
            self, user_id: str, name: str, root_path: str, description: str | None = None
        ) -> ProjectDTO:
            """Retrieves existing project by (user_id, root_path) or creates a new one."""

            u_id = _to_uuid(user_id)

            with get_db_session() as session:
                user = session.get(User, u_id)

                if not user:
                    raise UserNotFoundError(f"User {user_id} does not exists")

                stmt = (
                     select(Project).
                     where(Project.root_path == root_path)
                )
                project = session.execute(stmt).scalars().first()

                if not project:
                    project = Project(
                        id=uuid.uuid7(),
                        user_id=u_id,
                        name=name,
                        root_path=root_path,
                        description=description,
                    )
                    session.add(project)
                    session.flush()
                return ProjectDTO(
                    id=str(project.id),
                    user_id=str(project.user_id),
                    name=project.name,
                    root_path=project.root_path,
                    description=project.description,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                )

            
    def get_project(self, project_id: str) -> ProjectDTO | None:
        """Retrieves a project by its primary key ID."""
        p_id = _to_uuid(project_id)
        with get_db_session() as session:
            project = session.get(Project, p_id)
            if not project:
                return None

            return ProjectDTO(
                id=str(project.id),
                user_id=str(project.user_id),
                name=project.name,
                root_path=project.root_path,
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,
            )

        
    def get_project_by_root_path(self, user_id: str, root_path: str) -> ProjectDTO | None:
        """Retrieves a project matching a user and local directory root path."""
        u_id = _to_uuid(user_id)
        with get_db_session() as session:
            stmt = (
                select(Project).
                where(Project.user_id == u_id, Project.root_path == root_path,)
            )

            project = session.execute(stmt).scalars().first()

            if not project:
                return None


            return ProjectDTO(
                id=str(project.id),
                user_id=str(project.user_id),
                name=project.name,
                root_path=project.root_path,
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,

            )



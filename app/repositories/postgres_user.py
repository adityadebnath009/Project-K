
import uuid
from typing import Any

from app.database import get_db_session
from app.entities.user import User
from app.schemas.user import UserDTO



def to_uuid(val: str | uuid.UUID | None) -> uuid.UUID:
    if val is None:
        return uuid.uuid7()
    if(isinstance(val, uuid.UUID)):
        return val

    try:
        return uuid.UUID(val)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, val)


class PostgresUserRepository:
    def create_user(self, user_id: str | None = None) -> UserDTO:
        u_id = to_uuid(user_id)
        with get_db_session() as session:
            user = session.get(User, u_id)

            if not user:
                user = User(id=u_id)
                session.add(user)
                session.flush()
            return UserDTO(id=str(user.id), created_at=user.created_at)



    def get_user(self, user_id: str) -> UserDTO | None:
        u_id = to_uuid(user_id)
        with get_db_session() as session:
            user = session.get(User, u_id)
            if not user:
                return None
            return UserDTO(id=str(user.id), created_at=user.created_at)

    def user_exists(self, user_id: str) -> bool:
        u_id = to_uuid(user_id)
        with get_db_session() as session:
            return session.get(User, u_id) is not None



        
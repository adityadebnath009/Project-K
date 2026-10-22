
import uuid
from ast import stmt
from datetime import UTC, datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import get_db_session
from app.entities import conversation
from app.entities.conversation import Conversation
from app.entities.conversation_summary import ConversationSummary
from app.entities.message import Message
from app.entities.user import User
from app.exceptions.user_not_found_error import UserNotFoundError
from app.repositories import ConversationRepository, UserRepository
from app.repositories.postgres_user import PostgresUserRepository
from app.schemas import summary


def to_uuid(val: str | uuid.UUID | None) -> uuid.UUID:
        if val is None:
            return uuid.uuid7()

        if(isinstance(val, uuid.UUID)):
            return val
        try:
            return uuid.UUID(val)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_DNS, val)




class PostgresConversationRepository:
    def __init__(self, user_repository: UserRepository | None = None):
         self.user_repository = user_repository or PostgresUserRepository()


        

    

    def get_or_create_conversation(self, conversation_id: str | None, user_id: str) -> str:

        if not self.user_repository.user_exists(user_id=user_id):
            raise UserNotFoundError(f"User '{user_id}' does not exists. Must be Registered ")


        u_id = to_uuid(user_id)

        with get_db_session() as session:

            if conversation_id:
                 
                c_id = to_uuid(conversation_id)
                conv = session.get(Conversation, c_id)
                if conv:
                    if conv.user_id!=u_id:
                        raise PermissionError(f"Conversationn {conversation_id} does not belong to User {user_id}")

                
                    return str(conv.id)

            else:
                c_id= uuid.uuid7()


            conv  = Conversation(id=c_id, user_id= u_id)
            session.add(conv)

            return str(conv.id)


    def get_messages(
            self, conversation_id: str, limit: int | None = None
        ) -> list[dict[str, Any]]:
        c_id = to_uuid(conversation_id)

        with get_db_session() as session:

            if limit is not None:
                stmt = (
                    select(Message).
                    where(Message.conversation_id==c_id).
                    order_by(Message.sequence_number.desc())
                    .limit(limit)
                )
                messages = list(reversed(session.scalars(stmt).all()))

            else:
                stmt = (
                    select(Message).
                    where(Message.conversation_id==c_id).
                    order_by(Message.sequence_number.asc())
                )
                messages = session.scalars(stmt).all()

            return [
                {
                    "role": m.role,
                    "content" : m.content ,
                    "sequence_number": m.sequence_number
                }
                for m in messages
            ]





          

    def append_message(
        self, conversation_id: str, role: str, content: str
    ) -> dict[str, Any]:
        c_id = to_uuid(conversation_id)

        with get_db_session() as session:
            stmt = (

                select(
                    func.coalesce(
                        func.max(Message.sequence_number),0
                    )
                ).where(Message.conversation_id==c_id)
            )

            max_seq = session.execute(stmt).scalar_one()
            next_seq = max_seq +   1

            message = Message(
                conversation_id = c_id,
                role = role,
                content = content,
                sequence_number= next_seq
            )

            session.add(message)
            session.flush()


            return {
                "id": message.id,
                "conversation_id": conversation_id,
                "role" : message.role,
                "content": message.content,
                "sequence_number": message.sequence_number,
                "created_at":message.created_at.isoformat() if message.created_at else  None

            }
        
    def conversation_exists(self, conversation_id: str) -> bool:
        c_id = to_uuid(conversation_id)

        with get_db_session() as session:
            return session.get(Conversation, c_id) is not None

      

    def save_summary(
            self,
            conversation_id: str,
            summary_content: str,
            last_covered_sequence_number: int
    ) -> dict[str, Any]:
        c_id = to_uuid(conversation_id)
        with get_db_session() as session:
            stmt =(
                select(func.coalesce(func.max(ConversationSummary.version),0))
                .where(ConversationSummary.conversation_id==c_id)
            )
            max_version = session.execute(stmt).scalar_one()
            next_version = max_version + 1

            summary = ConversationSummary(
                conversation_id = c_id,
                version = next_version,
                summary_content = summary_content,
                last_covered_sequence_number = last_covered_sequence_number
            )

            session.add(summary)
            session.flush()

            return {
                "id": summary.id,
                "conversation_id" : str(summary.conversation_id),
                "version":summary.version,
                "summary_content" : summary.summary_content,
                "last_covered_sequence_number":summary.last_covered_sequence_number,
                "created_at": summary.created_at.isoformat() if summary.created_at else None

            }
        
      


    def get_latest_summary(
            self,
            conversation_id:str
    ) -> dict[str,Any] | None:
       c_id = to_uuid(conversation_id)

       with get_db_session() as session:
           stmt = (
               select(ConversationSummary).
               where(ConversationSummary.conversation_id == c_id).
               order_by(ConversationSummary.version.desc()).
               limit(1)
           )

           summary = session.scalars(stmt).first()
           if not summary:
               return None

           return {
               "id": summary.id,
                "conversation_id" : str(summary.conversation_id),
                "version":summary.version,
                "summary_content" : summary.summary_content,
                "last_covered_sequence_number":summary.last_covered_sequence_number,
                "created_at": summary.created_at.isoformat() if summary.created_at else None

               
           }
                 
            




    

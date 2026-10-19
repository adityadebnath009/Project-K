import uuid
from datetime import datetime, timezone, UTC
from typing import Any
from app.repositories.interfaces import ConversationRepository





class InMemoryConversationRepository:
    def __init__(self):
        self._conversations: dict[str, dict[str, Any]] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}
        self._global_message_id: int = 0
        self._summaries: dict[str, list[dict[str, Any]]] = {}



    def get_or_create_conversation(self, conversation_id: str | None, user_id: str) -> str:

        if conversation_id and conversation_id in self._conversations:
            return conversation_id


        new_conversation_id = conversation_id or str(uuid.uuid4())

        self._conversations[new_conversation_id] = {
            "user_id": user_id,
            "created_at": datetime.now(UTC)
        }
        self._summaries[new_conversation_id] = []
        self._messages[new_conversation_id] = []
        return new_conversation_id


    def get_messages(self, conversation_id:str, limit: int | None = None) -> list[dict[str, Any]]:
        if conversation_id not in self._messages:
            return []

        messages = self._messages[conversation_id]
        if limit is not None and limit>0:
            return messages[-limit:]

        return list(messages)


    def append_message(self, conversation_id: str, role: str, content: str) -> dict[str, Any]:
        if conversation_id not in self._messages:
            raise ValueError(f"Conversation {conversation_id} does not exists.")


        self._global_message_id+=1
        global_pk = self._global_message_id


        history = self._messages[conversation_id]

        sequence_number = len(history) + 1
        messages_record = {
            "id":global_pk,
            "conversation_id":conversation_id,
            "role":role,
            "content":content,
            "sequence_number":sequence_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        history.append(messages_record)
        return messages_record

    def conversation_exists(self, conversation_id: str) ->bool:
        return conversation_id in self._conversations


    def save_summary(self, 
                    conversation_id,
                    summary_content, 
                    last_covered_sequence_number
                    ) -> dict[str, Any]:



        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} does not exists")

        if conversation_id not in self._summaries:
            self._summaries[conversation_id] = []

        version = len(self._summaries[conversation_id]) + 1
        summary_record = {
            "conversation_id":conversation_id,
            "version":version,
            "summary_content" : summary_content,
            "last_covered_sequence_number": last_covered_sequence_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self._summaries[conversation_id].append(summary_record)
        return summary_record

  
    def get_latest_summary(
    self, conversation_id: str
) -> dict[str, Any] | None:
        summaries = self._summaries.get(conversation_id, [])
        if summaries:
            return summaries[-1]  # Return the latest version
        return None
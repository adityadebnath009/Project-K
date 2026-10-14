from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class ConversationRepository(Protocol):
    """
    Abstract intterface for conversation and memory storage
    """

    def get_or_create_conversation(self, conversation_id: str | None, user_id: str) -> str:
        """
        Get or create a conversation for the given user ID.
        Retrieves an existing conversation or creates a new one.
        Returns the conversation_id.
        """
        ...

    
    def get_messages(
        self, conversation_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Returns messages ordered chronologically by sequence_number.
        Each message dictionary includes:
          - 'role': 'user' | 'assistant' | 'system'
          - 'content': str
          - 'sequence_number': int
        If limit is provided, returns only the last `limit` messages.
        """
        ...
    def append_message(
        self, conversation_id: str, role: str, content: str
    ) -> dict[str, Any]:
        """
        Appends a message to the conversation with an auto-incrementing
        sequence_number to preserve strict ordering.
        Returns the newly created message record.
        """
        ...
    def conversation_exists(self, conversation_id: str) -> bool:
        """
        Checks whether a conversation exists in storage.
        """
        ...

    
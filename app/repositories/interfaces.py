from typing import Any, Protocol, runtime_checkable

from app.schemas.memory import ExtractedMemoryPackage, ProjectMemoryDTO, UserProfileDTO
from app.schemas.project import ProjectDTO
from app.schemas.user import UserDTO


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

    def save_summary(
            self,
            conversation_id: str,
            summary_content: str,
            last_covered_sequence_number: int
    ) -> dict[str, Any]:
        """
        saves a new compaction summary for the conversation.
        Tracks 
        """
        ...


    def get_latest_summary(
            self,
            conversation_id:str
    ) -> dict[str,Any] | None:
        """
        Retrieves the most recent summary for the conversation.
        or None if the conversation has beed compacted.
        """
        ...



@runtime_checkable
class UserRepository(Protocol):
    def create_user(self,user_id: str | None = None) -> UserDTO:
        """
        Registers a new user by ID, or None if not found.
        """
        ...

    def get_user(self, user_id: str) -> UserDTO | None:
        """
        Retrieve the user by id or None if not found
        """
        ...
    def user_exists(self, user_id:str) -> bool:
        """
        Existence Checking
        """
        ...


@runtime_checkable
class ProjectRepository(Protocol):
    """
    Abstract interface for project workspace persistence.
    """
    def get_or_create_project(
        self, user_id: str, name: str, root_path: str, description: str | None = None
    ) -> ProjectDTO:
        """Retrieves existing project by (user_id, root_path) or creates a new one."""
        ...
    def get_project(self, project_id: str) -> ProjectDTO | None:
        """Retrieves a project by its primary key ID."""
        ...
    def get_project_by_root_path(self, user_id: str, root_path: str) -> ProjectDTO | None:
        """Retrieves a project matching a user and local directory root path."""
        ...
@runtime_checkable
class MemoryRepository(Protocol):
    """
    Abstract interface for persisting and retrieving user profile & project memories.
    Handles validation, in-memory deduplication, and atomic PostgreSQL upserts.
    """
    def save_extracted_package(
        self,
        user_id: str,
        project_id: str | None,
        package: ExtractedMemoryPackage,
    ) -> tuple[int, int]:
        """
        Validates, deduplicates, and persists facts from an extraction package.
        Returns (user_facts_upserted_count, project_facts_upserted_count).
        """
        ...
    def get_user_profile(self, user_id: str) -> UserProfileDTO:
        """Retrieves all active memory items for a user."""
        ...
    def get_project_memory(self, project_id: str) -> ProjectMemoryDTO | None:
        """Retrieves all active architecture memory items for a project."""
        ...
    def delete_user_memory(self, user_id: str, key: str) -> bool:
        """Deletes a specific user memory fact by key."""
        ...
    def delete_project_memory(self, project_id: str, key: str) -> bool:
        """Deletes a specific project memory fact by key."""
        ...
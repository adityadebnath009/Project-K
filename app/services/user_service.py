from app.exceptions.user_not_found_error import UserNotFoundError
from app.repositories.interfaces import UserRepository
from app.schemas.user import UserDTO


class UserService:
    """
    Application Service for User registration and identity lookup.
    Acts as the single point of entry for user identity before Clerk / Keycloak integration.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def register_user(self, user_id: str | None = None) -> UserDTO:
        """Registers a new user in the system."""
        return self.user_repository.create_user(user_id)

    def get_user(self, user_id: str) -> UserDTO:
        """Fetches a user by ID or raises UserNotFoundError."""
        user = self.user_repository.get_user(user_id)
        if not user:
            raise UserNotFoundError(f"User '{user_id}' does not exist.")
        return user

    def get_current_user(self, user_id: str | None = None) -> UserDTO:
        """
        Resolves the current authenticated user context.
        If user_id is provided, verifies they exist or seeds default_user for CLI/local testing.
        """
        target_id = user_id or "default_user"
        user = self.user_repository.get_user(target_id)
        if not user:
            user = self.user_repository.create_user(target_id)
        return user
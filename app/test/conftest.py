"""
app/test/conftest.py
Pytest fixtures for Phase 4 and Phase 5 integration testing.
"""
import uuid
import pytest

from app.repositories.postgres_user import PostgresUserRepository
from app.repositories.postgres_conversation import PostgresConversationRepository
from app.services.user_service import UserService


@pytest.fixture
def user_id():
    """Provides a registered user in PostgreSQL."""
    user_repo = PostgresUserRepository()
    user_service = UserService(user_repo)
    user = user_service.register_user()
    return user.id


@pytest.fixture
def conv_id(user_id):
    """Provides an active conversation in PostgreSQL."""
    conv_repo = PostgresConversationRepository()
    return conv_repo.get_or_create_conversation(None, user_id)


@pytest.fixture
def project_id(user_id):
    """Provides a mock project ID."""
    return str(uuid.uuid7())

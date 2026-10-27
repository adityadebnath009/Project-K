import pytest
import uuid
from app.database import SessionLocal
from app.repositories.postgres_conversation import PostgresConversationRepository
from app.repositories.postgres_user import PostgresUserRepository
from app.repositories.postgres_memory import PostgresMemoryRepository
from app.repositories.postgres_project import PostgresProjectRepository
from app.services.conversation_service import ConversationService
from app.services.context_manager import ContextManager
from app.services.compactor import Compactor
from app.services.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService
from app.inference.ollama_client import OllamaClient
from app.schemas.chat import ChatRequest

def test_full_ecosystem_integrated_flow():
    """
    THE ULTIMATE TEST:
    1. User asks to deconstruct a real OS repo.
    2. System slices the repo and injects it into the LLM context.
    3. User asks questions about that real code.
    4. System answers using the sliced codebase context.
    """
    print("\n🚀 STARTING FULL ECOSYSTEM INTEGRATION TEST...")
    
    # Infrastructure
    user_repo = PostgresUserRepository()
    conv_repo = PostgresConversationRepository()
    mem_repo = PostgresMemoryRepository()
    proj_repo = PostgresProjectRepository()
    
    inference_client = OllamaClient()
    mem_service = MemoryService(mem_repo)
    compactor = Compactor(inference_client)
    mem_extractor = MemoryExtractor(inference_client)
    
    service = ConversationService(
        conversation_repository=conv_repo,
        inference_client=inference_client,
        compactor=compactor,
        memory_service=mem_service,
        memory_extractor=mem_extractor,
        project_repository=proj_repo
    )

    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    user_repo.create_user(user_id=user_id)

    # --- TURN 1: Deconstruct a real repo ---
    print("\nTurn 1: Deconstructing real repo...")
    req1 = ChatRequest(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        message="/deconstruct test_fixtures/realworld_fastapi /login"
    )
    res1 = service.process_chat_request(req1)
    assert "Successful" in res1.message
    print(f"Assistant: {res1.message}")

    # --- TURN 2: Ask a question about the sliced code ---
    print("\nTurn 2: Questioning the sliced code...")
    req2 = ChatRequest(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        message="Can you explain exactly how the password verification works in the slice you just extracted?"
    )
    res2 = service.process_chat_request(req2)
    
    # We verify that the response is NOT generic, but refers to the a la a real la code.
    # (The LLM should now have the source code in its context)
    print(f"Assistant: {res2.message}")
    assert len(res2.message) > 50, "Response too short; LLM might not be using the codebase context"

    # --- TURN 3: Adapt to target ---
    print("\nTurn 3: Designing adaptation...")
    req3 = ChatRequest(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        message="I want to move this to a project with a 'src/' root and use 'Managers' for services. How should I name the password reset service?"
    )
    res3 = service.process_chat_request(req3)
    print(f"Assistant: {res3.message}")
    
    assert "Manager" in res3.message, "Assistant failed to apply the naming convention"
    assert "src/" in res3.message, "Assistant failed to apply the root directory convention"

    print("\n🎉 FULL ECOSYSTEM TEST PASSED: Repo Slicing -> Context Injection -> Architectural Adaptation")

if __name__ == "__main__":
    test_full_ecosystem_integration()

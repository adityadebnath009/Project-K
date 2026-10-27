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

def test_real_llm_architectural_flow():
    """
    REAL LLM FLOW TEST:
    Verifies that the LLM actually provides detailed architectural guidance
    and maintains state through a series of design decisions.
    """
    print("\n🚀 STARTING REAL LLM ARCHITECTURAL FLOW TEST...")
    
    # 1. Setup Infrastructure
    user_repo = PostgresUserRepository()
    conv_repo = PostgresConversationRepository()
    mem_repo = PostgresMemoryRepository()
    proj_repo = PostgresProjectRepository()
    
    # REAL LLM Client (No Mocks)
    inference_client = OllamaClient()
    
    # Services
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

    # Setup IDs
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    user_repo.create_user(user_id=user_id)

    # Scenario: Designing a Feature a bit more naturally
    turns = [
        "Hi! I'm building a la a High-Scale Notification System. I want it to be extremely decoupled. Any suggestions on the architecture?",
        "I like the idea of using an Event-Driven approach. How should I structure the domain entities and the event handlers in a Clean Architecture project?",
        "I want my la project root to be 'src/'. Also, I prefer to call my services 'Managers' and my repositories 'Stores'. Can you remember that?",
        "I'm thinking of using Kafka for the event bus. How does that change the repository layer? Should I have a separate 'EventStore'?",
        "Can you summarize the architecture we've designed so far? Be detailed about the folder structure."
    ]

    print("\n--- Starting Real LLM Interaction ---")
    for i, user_msg in enumerate(turns, 1):
        request = ChatRequest(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            message=user_msg
        )
        
        response = service.process_chat_request(request)
        print(f"\n--- TURN {i} ---")
        print(f"USER: {user_msg}")
        print(f"ASSISTANT: {response.message}\n")

    print("\n🎉 REAL LLM FLOW TEST COMPLETE")

if __name__ == "__main__":
    test_real_llm_architectural_flow()

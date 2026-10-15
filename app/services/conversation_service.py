from tiktoken import get_encoding

from app.inference.base import InferenceClient
from app.repositories import ConversationRepository
from app.schemas import ChatRequest, ChatResponse
from app.services.context_manager import ContextManager


class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        inference_client: InferenceClient,
        context_manager: ContextManager | None = None,
    ):
        self.conversation_repository = conversation_repository
        self.inference_client = inference_client
        self.context_manager = context_manager or ContextManager()
    def process_chat_request(self, chat_request: ChatRequest) -> ChatResponse:
        user_id = chat_request.user_id or "default_user"
        conversation_id = self.conversation_repository.get_or_create_conversation(
            chat_request.conversation_id, 
            user_id
        )
        self.conversation_repository.append_message(
            conversation_id=conversation_id,
            role="user",
            content=chat_request.message
        )
        history = self.conversation_repository.get_messages(conversation_id)
        # ─── THE NEW STEP ───
        context_package = self.context_manager.build_context(
            conversation_id=conversation_id,
            user_id=user_id,
            history=history,
        )
        assistant_reply = self.inference_client.generate(messages=context_package.messages)
        self.conversation_repository.append_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_reply,
        )
        prompt_tokens = context_package.estimated_input_tokens
        completion_tokens = self.context_manager.token_counter.count_tokens(assistant_reply)
        
        return ChatResponse(
            conversation_id=conversation_id,
            message=assistant_reply,
            model = getattr(self.inference_client, "model_name", "qwen2.5:7b"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
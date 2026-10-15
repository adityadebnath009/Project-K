from tiktoken import get_encoding

from app.inference.base import InferenceClient
from app.repositories import ConversationRepository
from app.schemas import ChatRequest, ChatResponse
from app.services.context_manager import ContextManager
from app.services.compactor import Compactor

class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        inference_client: InferenceClient,
        context_manager: ContextManager | None = None,
        compactor: Compactor | None = None
    ):
        self.conversation_repository = conversation_repository
        self.inference_client = inference_client
        self.context_manager = context_manager or ContextManager()
        self.compactor = compactor or Compactor()


    def process_chat_request(self, chat_request: ChatRequest) -> ChatResponse:
        user_id = chat_request.user_id or "default_user"
        conversation_id = self.conversation_repository.get_or_create_conversation(
            chat_request.conversation_id, 
            user_id
        )
        # ─── 1. INTERCEPT /compact COMMAND ───
        if chat_request.message.strip().lower() == "/compact":
            return self._handle_compact_command(conversation_id)
        # ─── 2. NORMAL CHAT TURN ───
        self.conversation_repository.append_message(
            conversation_id=conversation_id,
            role="user",
            content=chat_request.message,
        )
        history = self.conversation_repository.get_messages(conversation_id)
        # Retrieve the latest versioned summary (if one exists)
        latest_summary_record = self.conversation_repository.get_latest_summary(conversation_id)
        active_summary = (
            latest_summary_record["summary_content"]
            if latest_summary_record
            else None
        )
        # Build context with token budget enforcement and summary injection
        context_package = self.context_manager.build_context(
            conversation_id=conversation_id,
            user_id=user_id,
            history=history,
            summary=active_summary,
        )
        # Generate response
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
            model=getattr(self.inference_client, "model_name", "qwen2.5:7b"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


    def _handle_compact_command(self, conversation_id: str) -> ChatResponse:
        """
        Executes history compaction for the conversation and saves a new versioned summary.
        """
        history = self.conversation_repository.get_messages(conversation_id)
        if not history:
            return ChatResponse(
                conversation_id=conversation_id,
                message="No conversation history available to compact.",
                model="compactor",
                prompt_tokens=0,
                completion_tokens=0,
            )
        # Check for existing summary to support incremental updates
        latest_summary_record = self.conversation_repository.get_latest_summary(conversation_id)
        existing_summary = (
            latest_summary_record["summary_content"]
            if latest_summary_record
            else None
        )
        # Compact history using structured Pydantic output
        summary_dto = self.compactor.compact_history(
            history=history,
            existing_summary=existing_summary,
        )
        summary_text = summary_dto.to_context_string()
        # Track the last sequence number covered by this compaction
        last_seq = history[-1].get("sequence_number", 0)
        saved_summary = self.conversation_repository.save_summary(
            conversation_id=conversation_id,
            summary_content=summary_text,
            last_covered_sequence_number=last_seq,
        )
        ack_message = (
            f"Conversation compacted successfully (version {saved_summary['version']}).\n\n"
            f"{summary_text}"
        )
        return ChatResponse(
            conversation_id=conversation_id,
            message=ack_message,
            model="compactor",
            prompt_tokens=0,
            completion_tokens=0,
        )
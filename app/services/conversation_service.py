

import logging
from typing import Any

from ollama import chat
from tiktoken import get_encoding

from app.config import settings
from app.inference.base import InferenceClient
from app.repositories import ConversationRepository
from app.repositories.interfaces import ProjectRepository
from app.schemas import ChatRequest, ChatResponse, memory
from app.schemas.summary import CompactionResult
from app.services.compactor import Compactor
from app.services.context_manager import ContextManager
from app.services.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)
class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        inference_client: InferenceClient,
        context_manager: ContextManager | None = None,
        compactor: Compactor | None = None,
        memory_service: MemoryService | None = None,
        memory_extractor: MemoryExtractor | None = None,
        project_repository: ProjectRepository | None = None,
        auto_compact_threshold: float | None = None
    ):
        self.conversation_repository = conversation_repository
        self.inference_client = inference_client
        self.context_manager = context_manager or ContextManager()
        self.compactor = compactor or Compactor()
        self.memory_service = memory_service
        self.memory_extractor = memory_extractor
        self.project_repository  = project_repository
        self.auto_compact_threshold =(auto_compact_threshold 
                                      if auto_compact_threshold is not None else  settings.auto_compact_threshold)



    def process_chat_request(self, chat_request: ChatRequest) -> ChatResponse:
        user_id = chat_request.user_id or "default_user"
        project_id = chat_request.project_id
        conversation_id = self.conversation_repository.get_or_create_conversation(
            chat_request.conversation_id, 
            user_id
        )

        # ─── 1. INTERCEPT MANUAL /compact SLASH COMMAND ───
        if chat_request.message.strip().lower() == "/compact":
            return self._handle_compact_command(
                conversation_id=conversation_id, 
                user_id=user_id, 
                project_id=project_id
            )

        # ─── 2. APPEND THE NEW USER MESSAGE TO DB ───
        user_msg_record = self.conversation_repository.append_message(
            conversation_id=conversation_id,
            role="user",
            content=chat_request.message,
        )
        active_seq = user_msg_record["sequence_number"]
        history = self.conversation_repository.get_messages(conversation_id)

        # ─── 3. GET ACTIVE SUMMARY & WATERMARK ───
        latest_summary_record = self.conversation_repository.get_latest_summary(conversation_id)
        active_summary = (
            latest_summary_record["summary_content"]
            if latest_summary_record
            else None
        )
        last_covered_seq = (
            latest_summary_record["last_covered_sequence_number"]
            if latest_summary_record
            else 0
        )

        # ─── 4. WATERMARK FILTERING (ZERO DUPLICATION) ───
        # Only select messages that are NOT yet covered in the active summary!
        uncovered_history = [
            m for m in history if m.get("sequence_number", 0) > last_covered_seq
        ]

        # ─── 5. RETRIEVE TIER 2 & TIER 3 MEMORIES (~2ms DB LOOKUP) ───
        user_profile_context = None
        if self.memory_service:
            user_profile_context = self.memory_service.get_user_profile_context(user_id=user_id)

        project_context = None
        if self.memory_service and project_id:
            project_context = self.memory_service.get_project_memory_context(project_id=project_id)

        # ─── 6. BUILD INITIAL CONTEXT PACKAGE ───
        context_package = self.context_manager.build_context(
            conversation_id=conversation_id,
            user_id=user_id,
            history=uncovered_history,  # <--- Only fresh, uncovered messages!
            summary=active_summary,
            user_profile=user_profile_context,
            project_context=project_context,
        )

        # ─── 7. AUTO-COMPACTION WATERMARK CHECK (80% CAPACITY) ───
        watermark_limit = context_package.max_input_budget * self.auto_compact_threshold
        is_above_watermark = context_package.estimated_input_tokens >= watermark_limit

        # We need at least 2 uncompacted PRIOR messages (excluding the active request)
        # to justify running compaction (Anti-Thrashing guard):
        prior_uncompacted = [
            m for m in history
            if m.get("sequence_number", 0) > last_covered_seq and m.get("sequence_number") != active_seq
        ]

        if (is_above_watermark or context_package.is_compacted) and len(prior_uncompacted) >= 2:
            logger.info(
                "Context reached watermark (%d/%d tokens). Running auto-compaction in background...",
                context_package.estimated_input_tokens,
                context_package.max_input_budget,
            )
            # Compact historical turns, keeping the active user message untouched
            compaction_result = self._execution_compaction(
                conversation_id=conversation_id,
                user_id=user_id,
                project_id=project_id,
                exclude_sequence_number=active_seq,
            )
            active_summary = compaction_result.summary_content

            # Refresh memories if updated
            if self.memory_service:
                user_profile_context = self.memory_service.get_user_profile_context(user_id=user_id)
                if project_id:
                    project_context = self.memory_service.get_project_memory_context(project_id=project_id)

            # Re-partition history: only messages after the new watermark
            # (Guarantees the active user request is preserved!)
            new_watermark = compaction_result.last_covered_sequence_number
            refreshed_uncovered = [
                m for m in history if m.get("sequence_number", 0) > new_watermark
            ]

            # Re-build the context package with the fresh summary and pruned history
            context_package = self.context_manager.build_context(
                conversation_id=conversation_id,
                user_id=user_id,
                history=refreshed_uncovered,
                summary=active_summary,
                user_profile=user_profile_context,
                project_context=project_context,
            )

        # ─── 8. GENERATE INFERENCE RESPONSE ───
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


    def _handle_compact_command(
    self,
    conversation_id: str,
    user_id: str,
    project_id: str | None = None,
) -> ChatResponse:
        """User-initiated /compact slash command."""
        result = self._execution_compaction(
            conversation_id=conversation_id,
            user_id=user_id,
            project_id=project_id,
            exclude_sequence_number=None,  # Compact everything
        )

        if result.version == 0:
            return ChatResponse(
                conversation_id=conversation_id,
                message="No conversation history available to compact.",
                model="compactor",
                prompt_tokens=0,
                completion_tokens=0,
            )

        ack_message = (
            f"Conversation compacted successfully (version {result.version}).\n"
            f"Memories updated: {result.user_facts_saved} user facts, {result.project_facts_saved} project facts.\n\n"
            f"{result.summary_content}"
        )

        return ChatResponse(
            conversation_id=conversation_id,
            message=ack_message,
            model="compactor",
            prompt_tokens=0,
            completion_tokens=0,
        )

    def _execution_compaction(
        self,
        conversation_id: str,
        user_id: str,
        project_id: str | None = None,
        exclude_sequence_number: int | None = None,
    ) -> CompactionResult:
        """
        Executes incremental history compaction and extracts durable memories.

        Guarantees:
        1. Delta-only: Only summarizes messages > last_covered_sequence_number.
        2. Active turn preservation: Excludes exclude_sequence_number explicitly
           so the active unanswered request remains in working memory.
        3. Contiguous progression: Advances watermark strictly without skipping gaps.
        4. Idempotent: If no new delta messages exist, returns existing summary safely.
        """
        history = self.conversation_repository.get_messages(conversation_id=conversation_id)
        if not history:
            return CompactionResult(
                summary_content="",
                version=0,
                last_covered_sequence_number=0,
            )

        # ─── 1. FETCH LATEST WATERMARK ───
        latest_summary_record = self.conversation_repository.get_latest_summary(
            conversation_id=conversation_id
        )
        existing_summary = (
            latest_summary_record["summary_content"]
            if latest_summary_record
            else None
        )
        last_covered_seq = (
            latest_summary_record["last_covered_sequence_number"]
            if latest_summary_record
            else 0
        )
        current_version = (
            latest_summary_record["version"]
            if latest_summary_record
            else 0
        )

        # ─── 2. SEPARATE COMPACTION CANDIDATES FROM ACTIVE REQUEST ───
        eligible_history = [
            m for m in history
            if exclude_sequence_number is None or m.get("sequence_number") != exclude_sequence_number
        ]

        # ─── 3. EXTRACT ONLY UNCOVERED DELTA MESSAGES ───
        delta_messages = [
            m for m in eligible_history if m.get("sequence_number", 0) > last_covered_seq
        ]

        if not delta_messages:
            return CompactionResult(
                summary_content=existing_summary or "",
                version=current_version,
                last_covered_sequence_number=last_covered_seq,
                user_facts_saved=0,
                project_facts_saved=0,
            )

        # ─── 4. STRICT CONTIGUOUS WATERMARK PROGRESSION (P0 — 3 fix) ───
        sorted_delta = sorted(delta_messages, key=lambda m: m.get("sequence_number", 0))

        contiguous_watermark = last_covered_seq
        contiguous_delta: list[dict[str, Any]] = []

        for msg in sorted_delta:
            seq = msg.get("sequence_number", 0)
            if seq == contiguous_watermark + 1:
                contiguous_watermark = seq
                contiguous_delta.append(msg)
            else:
                # Gap detected! Stop advancing so missing messages are not skipped!
                break

        if not contiguous_delta:
            return CompactionResult(
                summary_content=existing_summary or "",
                version=current_version,
                last_covered_sequence_number=last_covered_seq,
                user_facts_saved=0,
                project_facts_saved=0,
            )

        # ─── 5. INCREMENTAL COMPACTION VIA LLM ───
        summary_dto = self.compactor.compact_history(
            history=contiguous_delta,
            existing_summary=existing_summary,
        )
        summary_text = summary_dto.to_context_string()

        saved_summary = self.conversation_repository.save_summary(
            conversation_id=conversation_id,
            summary_content=summary_text,
            last_covered_sequence_number=contiguous_watermark,
        )

        # ─── 6. INCREMENTAL MEMORY EXTRACTION ───
        user_facts_saved = 0
        project_facts_saved = 0
        if self.memory_extractor and self.memory_service:
            existing_user_profile = self.memory_service.get_user_profile_context(user_id=user_id)
            existing_project_context = (
                self.memory_service.get_project_memory_context(project_id=project_id)
                if project_id
                else None
            )

            extracted_package = self.memory_extractor.extract_memories(
                history=contiguous_delta,  # <--- ONLY CONTIGUOUS DELTA MESSAGES!
                existing_user_profile=existing_user_profile,
                existing_project_context=existing_project_context,
            )
            user_facts_saved, project_facts_saved = self.memory_service.persist_extracted_memories(
                user_id=user_id,
                project_id=project_id,
                package=extracted_package,
            )

        return CompactionResult(
            summary_content=saved_summary["summary_content"],
            version=saved_summary["version"],
            last_covered_sequence_number=contiguous_watermark,
            user_facts_saved=user_facts_saved,
            project_facts_saved=project_facts_saved,
        )
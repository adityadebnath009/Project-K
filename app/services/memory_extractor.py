from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.config import settings
from app.schemas.memory import ExtractedMemoryPackage

EXTRACTION_SYSTEM_PROMPT = """You are an expert architectural memory extraction engine for an AI coding assistant.
Your job is to analyze the conversation history between a developer and an assistant, and extract ONLY durable, long-term facts.
Separate extracted memories strictly into two categories:
1. `user_facts`: Facts about the user's identity, engineering role, habits, preferred frameworks, and instructions on how they want the AI to behave (e.g., explanation style, code generation rules).
2. `project_facts`: Facts about THIS specific codebase's architecture, confirmed tech stack, database choices, patterns, invariants, and directory structures.
### STRICT NEGATIVE CONSTRAINTS (DO NOT EXTRACT):
- DO NOT extract ephemeral conversational chatter ("hello", "thanks", "how are you?").
- DO NOT extract temporary bugs, stack traces, or one-off code fixes ("NullPointerException on line 42").
- DO NOT extract exploratory questions as facts (if user asks "Could we use Redis?", do NOT extract Redis unless they explicitly decided to adopt it).
- DO NOT invent or hallucinate facts that were not stated in the history.
- If no new durable facts exist, return empty lists.
### CANONICAL KEY GUIDELINES (Use uniform snake_case keys):
- Tech stack: 'primary_language', 'backend_framework', 'database', 'orm', 'testing_framework'
- Architecture: 'design_pattern', 'persistence_strategy', 'api_style', 'token_budget_rule'
- Standards & preferences: 'explanation_style', 'guidance_rule', 'code_generation_style'
"""




class MemoryExtractor:
    def __init__(self, 
                model_name : str | None = None,
                base_url: str | None = None):

        self.model_name = model_name or settings.model_name
        raw_url = base_url or settings.ai_base_url
        self.base_url = raw_url.rstrip("/").removesuffix("/v1")

        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.0
        )
        self.structured_extractor  = self.llm.with_structured_output(ExtractedMemoryPackage)


    def extract_memories(
        self,
        history: list[dict[str, Any]],
        existing_user_profile: str | None = None,
        existing_project_context: str | None = None,
    ) -> ExtractedMemoryPackage:
        """
        Extracts new user and project facts from conversation history.
        Passes existing memory context to avoid re-extracting already known facts.
        """
        if not history:
            return ExtractedMemoryPackage(user_facts=[], project_facts=[])
        # Format conversation transcript for the extractor
        transcript_lines: list[str] = []
        for msg in history:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "").strip()
            if content:
                transcript_lines.append(f"{role}: {content}")
        transcript = "\n".join(transcript_lines)
        user_content = f"### CONVERSATION HISTORY TO ANALYZE:\n{transcript}\n"
        if existing_user_profile:
            user_content += f"\n### ALREADY KNOWN USER PROFILE:\n{existing_user_profile}\n"
        if existing_project_context:
            user_content += f"\n### ALREADY KNOWN PROJECT CONTEXT:\n{existing_project_context}\n"
        user_content += (
            "\nExtract any NEW or UPDATED durable facts. "
            "If an existing fact was updated by the user, extract the updated value with the same key."
        )
        messages = [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        try:
            result = self.structured_extractor.invoke(messages)
            if isinstance(result, ExtractedMemoryPackage):
                return result
            return ExtractedMemoryPackage(user_facts=[], project_facts=[])
        except Exception:
            # Resilient fallback so extraction issues never crash the main chat
            return ExtractedMemoryPackage(user_facts=[], project_facts=[])

        
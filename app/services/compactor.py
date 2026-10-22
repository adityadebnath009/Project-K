from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


from app.config import settings
from app.schemas.summary import CompactionSummary
from app.services.token_counter import TokenCounter

COMPACTION_SYSTEM_PROMPT = """You are a technical context compactor for an AI software engineering assistant.
Your task is to analyze the conversation history and extract a dense, factual Operational Ledger.
Do NOT write a narrative or story. Preserve critical architecture decisions, file names, constraints, and progress.
"""


class Compactor:
    """
    Distills raw conversation turns into a structured CompactionSummary
    using LangChain's native with_structured_output.
    """

    def __init__(
        self,
        llm: Any | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        base_url = settings.ai_base_url.rstrip("/").removesuffix("/v1")

        self.llm = llm or ChatOllama(
            base_url=base_url,
            model=settings.model_name,
            temperature=0,
        )
        self.structured_llm = self.llm.with_structured_output(CompactionSummary)
        self.token_counter = token_counter or TokenCounter()

    def compact_history(
        self,
        history: list[dict[str, Any]],
        existing_summary: str | None = None,
        max_input_tokens: int = 4000,
    ) -> CompactionSummary:
        # 1. Measure overhead of system prompt and previous summary
        system_cost = self.token_counter.count_tokens(COMPACTION_SYSTEM_PROMPT)
        summary_header = f"PREVIOUS_SUMMARY:\n{existing_summary}\n\n" if existing_summary else ""
        summary_cost = self.token_counter.count_tokens(summary_header)

        # Usable token budget exclusively for delta messages
        usable_budget = max(500, max_input_tokens - system_cost - summary_cost - 100)

        # 2. Pack delta messages from newest to oldest within usable_budget
        bounded_lines: list[str] = []
        accumulated_tokens = 0

        for msg in reversed(history):
            role = str(msg.get("role", "")).upper()
            content = str(msg.get("content", ""))
            line = f"[{role}] : {content}"
            line_cost = self.token_counter.count_tokens(line) + 4

            if accumulated_tokens + line_cost <= usable_budget:
                bounded_lines.append(line)
                accumulated_tokens += line_cost
            else:
                bounded_lines.append("[... earlier delta messages truncated for compaction budget ...]")
                break

        bounded_lines.reverse()

        # 3. Assemble prompt payload
        formatted_dialogue = []
        if summary_header:
            formatted_dialogue.append(summary_header)

        formatted_dialogue.append("CONVERSATION TO COMPACT:")
        formatted_dialogue.extend(bounded_lines)
        user_content = "\n".join(formatted_dialogue)

        messages = [
            SystemMessage(content=COMPACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]


        result = self.structured_llm.invoke(messages)



        if(isinstance(result, CompactionSummary)):
            return result

        return CompactionSummary.model_validate(result)

        
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


from app.config import settings
from app.schemas.summary import CompactionSummary



COMPACTION_SYSTEM_PROMPT = """You are a technical context compactor for an AI software engineering assistant.
Your task is to analyze the conversation history and extract a dense, factual Operational Ledger.
Do NOT write a narrative or story. Preserve critical architecture decisions, file names, constraints, and progress.
"""


class Compactor:
    """
     Distills raw conversation turns into a structured CompactionSummary
    using LangChain's native with_structured_output.
    """


    def __init__(self,
                llm : Any | None = None) -> None:

        base_url = settings.ai_base_url.rstrip("/").removesuffix("/v1")

        self.llm = llm or ChatOllama(
            base_url=base_url,
            model = settings.model_name,
            temperature=0
        )
        self.structured_llm = self.llm.with_structured_output(CompactionSummary)


    def compact_history(
            self, history:list[dict[str, Any]],
            existing_summary: str | None = None) -> CompactionSummary:

        formatted_dialogue = []
        if existing_summary:
            formatted_dialogue.append(f"PREVIOUS_SUMMARY: \n{existing_summary}\n")

        formatted_dialogue.append("CONVERSATION TO COMPACT:")

        for msg in history:
            role = str(msg.get("role","")).upper()
            content = str(msg.get("content",""))

            formatted_dialogue.append(f"[{role}] : {content}")
        user_content = "\n".join(formatted_dialogue)

        messages = [
            SystemMessage(content=COMPACTION_SYSTEM_PROMPT),
            HumanMessage(content=user_content)
        ]


        result = self.structured_llm.invoke(messages)



        if(isinstance(result, CompactionSummary)):
            return result

        return CompactionSummary.model_validate(result)

        
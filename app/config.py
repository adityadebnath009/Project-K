import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    ai_base_url: str = os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434/v1")
    ai_api_key:str = os.getenv("OLLAMA_API_KEY","DUMMY_KEY")
    model_name:str = os.getenv("MODEL","qwen2.5:7b")
    system_prompt:str = os.getenv("SYSTEM_PROMPT","You are a helpful assistant.")

    effective_context_limit: int = int(os.getenv("EFFECTIVE_CONTEXT_LIMIT", "8192"))
    reserved_output_tokens: int = int(os.getenv("RESERVED_OUTPUT_TOKENS", "1500"))
    safety_margin: int = int(os.getenv("SAFETY_MARGIN", "200"))


    @property
    def max_input_tokens(self) -> int:
        return self.effective_context_limit - self.reserved_output_tokens - self.safety_margin


settings = Settings()
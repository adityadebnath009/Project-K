from openai import OpenAI

from app.config import settings
from app.inference.base import InferenceClient

class OllamaClient(InferenceClient):
    def __init__(self,
                base_url:str | None = None,
                api_key:str | None = None,
                model_name:str | None = None
                 ):
        
        self.base_url: str = base_url or settings.ai_base_url
        self.api_key: str = api_key or settings.ai_api_key
        self.model_name: str = model_name or settings.model_name

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

    def generate(
            self,
            messages: list[dict[str, str]],
            system_prompt: str | None = None,
    ) -> str:
            prompt = system_prompt or settings.system_prompt
            formatted_messages = [{"role": "system", "content": prompt}, *messages]
            response = self.client.chat.completions.create(
            model=self.model_name,
            messages=formatted_messages  # type: ignore
            )
            return response.choices[0].message.content or ""

        
                
import os
import pprint # type : ignore

from dotenv import load_dotenv
from openai import OpenAI

from app.schemas.chat import ChatRequest

load_dotenv()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
MODEL = os.getenv("MODEL")

client = OpenAI(
    base_url=OLLAMA_BASE_URL, 
    api_key=OLLAMA_API_KEY 
)
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
messages = []
while True:
    user_input = input("You: Enter your message (or type 'exit' to quit): ")
   
    if user_input.lower() == 'exit':
        break
    if not user_input.strip():
        print("Please enter a valid message.")
        continue

    messages.append({"role": "user", "content": user_input})
    recent_messages = messages[-5:]  # Get the last 5 messages for context

    try:

        response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *recent_messages
        ]

        )
        answer = response.choices[0].message.content
    
        messages.append({"role": "assistant", "content": answer})
        print(f"AI: {answer}")
    except Exception as e: # type: ignore
        messages.pop()
        print(f"Error: {e}")

   
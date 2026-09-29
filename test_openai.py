import os
from backend.core.config import settings
from openai import OpenAI

client = OpenAI(
  base_url=settings.OPENROUTER_BASE_URL,
  api_key=settings.OPENROUTER_API_KEY,
)

response = client.chat.completions.create(
    model=settings.LLM_MODEL,
    messages=[
        {"role": "user", "content": "hello"}
    ],
    extra_body={"reasoning": {"enabled": True}}
)

print(type(response))
print(response)

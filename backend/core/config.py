import os
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()

class Settings:
    # Only for Jev, the context decision model; it answers faster than a local LLM
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    # Every other LLM call goes to a local OpenAI-compatible server (Ollama)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL1: str = os.getenv("LLM_MODEL1", "qwen3:4b")
    LLM_MODEL2: str = os.getenv("LLM_MODEL2", "")
    LLM_MODEL3: str = os.getenv("LLM_MODEL3", "")
    # Small model for tags, summaries, query profiles and titles
    TAGGING_MODEL: str = os.getenv("TAGGING_MODEL", "qwen3:4b")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    @property
    def chat_models(self) -> list[str]:
        return [m for m in (self.LLM_MODEL1, self.LLM_MODEL2, self.LLM_MODEL3) if m]

settings = Settings()

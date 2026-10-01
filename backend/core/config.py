import os
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()

class Settings:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL1", "")
    LLM_MODEL1: str = os.getenv("LLM_MODEL1", "")
    LLM_MODEL2: str = os.getenv("LLM_MODEL2", "")
    LLM_MODEL3: str = os.getenv("LLM_MODEL3", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

settings = Settings()

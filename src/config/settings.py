import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'cx_agent.db'}")
    DEFAULT_TONE: str = os.getenv("DEFAULT_TONE", "friendly")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PROMPTS_FILE: Path = BASE_DIR / "config" / "system_prompts.yaml"


settings = Settings()

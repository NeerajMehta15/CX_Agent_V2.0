import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Provider presets: base_url, default model, default mini model
PROVIDER_PRESETS = {
    "qwen3": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "model_mini": "qwen-turbo",
    },
    "kimi": {
        "base_url": "https://api.moonshot.ai/v1",
        "model": "kimi-k2.5-preview",
        "model_mini": "kimi-k2.5-preview",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "model_mini": "gpt-4o-mini",
    },
}


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'cx_agent.db'}")
    DEFAULT_TONE: str = os.getenv("DEFAULT_TONE", "friendly")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PROMPTS_FILE: Path = BASE_DIR / "config" / "system_prompts.yaml"

    # LLM provider config
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai") 
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_MODEL_MINI: str = os.getenv("LLM_MODEL_MINI", "")

    @property
    def llm_base_url(self) -> str:
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL
        return PROVIDER_PRESETS.get(self.LLM_PROVIDER, {}).get("base_url", "")

    @property
    def llm_model(self) -> str:
        if self.LLM_MODEL:
            return self.LLM_MODEL
        return PROVIDER_PRESETS.get(self.LLM_PROVIDER, {}).get("model", "")

    @property
    def llm_model_mini(self) -> str:
        if self.LLM_MODEL_MINI:
            return self.LLM_MODEL_MINI
        return PROVIDER_PRESETS.get(self.LLM_PROVIDER, {}).get("model_mini", "")


settings = Settings()

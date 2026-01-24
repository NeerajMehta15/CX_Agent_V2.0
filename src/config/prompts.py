from pathlib import Path

import yaml

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_prompts_cache: dict | None = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is not None:
        return _prompts_cache
    prompts_path: Path = settings.PROMPTS_FILE
    if not prompts_path.exists():
        logger.warning(f"Prompts file not found at {prompts_path}, using defaults.")
        _prompts_cache = {
            "tones": {
                "friendly": {
                    "system_prompt": "You are a warm, friendly customer service agent. Help customers with their queries in a conversational and empathetic manner."
                }
            },
            "default_tone": "friendly",
            "guardrails": [],
        }
        return _prompts_cache
    with open(prompts_path) as f:
        _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


def get_system_prompt(tone: str | None = None) -> str:
    prompts = _load_prompts()
    tone = tone or prompts.get("default_tone", settings.DEFAULT_TONE)
    tone_config = prompts.get("tones", {}).get(tone)
    if not tone_config:
        logger.warning(f"Tone '{tone}' not found, falling back to default.")
        tone = prompts.get("default_tone", "friendly")
        tone_config = prompts["tones"][tone]

    system_prompt = tone_config["system_prompt"]

    # Append guardrails
    guardrails = prompts.get("guardrails", [])
    if guardrails:
        rules = "\n".join(f"- {g}" for g in guardrails)
        system_prompt += f"\n\nIMPORTANT RULES:\n{rules}"

    return system_prompt

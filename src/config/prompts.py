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


def get_system_prompt_with_profile(tone: str | None, profile) -> str:
    """Build the system prompt, appending a CUSTOMER HISTORY block when a profile exists."""
    import json

    base = get_system_prompt(tone)
    if profile is None:
        return base

    # Parse JSON fields safely
    try:
        topics = json.loads(profile.topic_frequency_json) if profile.topic_frequency_json else {}
    except (json.JSONDecodeError, TypeError):
        topics = {}
    top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:3]
    topic_str = ", ".join(f"{t[0]} ({t[1]}x)" for t in top_topics) if top_topics else "none yet"

    sentiment_trend = "improving" if profile.avg_sentiment_drift > 0.05 else (
        "declining" if profile.avg_sentiment_drift < -0.05 else "stable"
    )

    lines = [
        f"\n\nCUSTOMER HISTORY:",
        f"- Loyalty tier: {profile.loyalty_tier}",
        f"- Sessions: {profile.total_sessions} | Escalations: {profile.total_escalations}",
        f"- Resolution rate: {profile.resolution_rate:.0%}",
        f"- Sentiment: {profile.weighted_sentiment:+.2f} (trend: {sentiment_trend})",
        f"- Top topics: {topic_str}",
    ]

    if profile.risk_flag:
        try:
            reasons = json.loads(profile.risk_reasons_json) if profile.risk_reasons_json else []
        except (json.JSONDecodeError, TypeError):
            reasons = []
        lines.append(f"- *** AT-RISK CUSTOMER *** Reasons: {', '.join(reasons)}")

    lines.append("Use this context to personalize responses. Do NOT recite these stats to the customer.")

    return base + "\n".join(lines)

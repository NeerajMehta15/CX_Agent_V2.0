from enum import Enum

from src.agent.memory import ConversationMemory
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HandoffReason(Enum):
    REPEATED_INTENT = "repeated_intent"
    DATA_GAP = "data_gap"
    HALLUCINATION_RISK = "hallucination_risk"


def check_handoff(memory: ConversationMemory, current_message: str) -> HandoffReason | None:
    """Check if the conversation should be handed off to a human agent.

    Rules:
    1. Repeated Intent: If the user asks semantically the same question twice.
    2. Data Gap: If the last tool call returned empty/null results.
    3. Hallucination Risk: Detected post-response (handled in cx_agent.py).
    """
    # Rule 1: Repeated intent detection
    if memory.has_repeated_intent(current_message):
        logger.info(f"Handoff triggered: repeated intent detected.")
        return HandoffReason.REPEATED_INTENT

    # Rule 2: Data gap from previous interaction
    if memory.last_tool_returned_empty():
        logger.info(f"Handoff triggered: data gap detected.")
        return HandoffReason.DATA_GAP

    return None

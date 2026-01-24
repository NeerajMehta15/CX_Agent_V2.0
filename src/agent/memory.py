from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ConversationMemory:
    """Tracks conversation history and user intents for repeat detection."""
    messages: list[dict] = field(default_factory=list)
    intent_history: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def add_intent(self, intent: str):
        self.intent_history.append(intent.lower().strip())

    def add_tool_result(self, tool_name: str, result: dict):
        self.tool_results.append({"tool": tool_name, "result": result})

    def get_messages(self) -> list[dict]:
        return self.messages.copy()

    def has_repeated_intent(self, current_intent: str, threshold: float = 0.85) -> bool:
        """Check if the current intent is semantically similar to a previous one.
        Uses simple word overlap ratio as a lightweight similarity measure.
        """
        current_words = set(current_intent.lower().split())
        for past_intent in self.intent_history:
            past_words = set(past_intent.split())
            if not current_words or not past_words:
                continue
            overlap = len(current_words & past_words)
            total = max(len(current_words), len(past_words))
            similarity = overlap / total if total > 0 else 0
            if similarity >= threshold:
                return True
        return False

    def last_tool_returned_empty(self) -> bool:
        """Check if the most recent tool call returned empty/null results."""
        if not self.tool_results:
            return False
        last = self.tool_results[-1]["result"]
        if isinstance(last, dict):
            result = last.get("result")
            return result is None or result == [] or result == {}
        return False

    def clear(self):
        self.messages.clear()
        self.intent_history.clear()
        self.tool_results.clear()


# Session-based memory store
_sessions: dict[str, ConversationMemory] = defaultdict(ConversationMemory)


def get_memory(session_id: str) -> ConversationMemory:
    return _sessions[session_id]


def clear_memory(session_id: str):
    if session_id in _sessions:
        _sessions[session_id].clear()

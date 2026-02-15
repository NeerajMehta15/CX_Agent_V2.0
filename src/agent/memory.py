import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TOOL_TO_INTENT = {
    "lookup_user": "account_inquiry",
    "get_orders": "order_status",
    "get_tickets": "support_inquiry",
    "update_ticket": "ticket_management",
    "update_user_email": "account_update",
    "flag_refund": "refund",
    "knowledge_search": "general_inquiry",
}


@dataclass
class ConversationMemory:
    """Tracks conversation history and user intents for repeat detection.
    Supports optional DB persistence via the Message model.
    """
    messages: list[dict] = field(default_factory=list)
    intent_history: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)

    _db: Session | None = field(default=None, repr=False)
    _session_id: str | None = field(default=None, repr=False)
    _loaded_from_db: bool = field(default=False, repr=False)
    _handoff_occurred: bool = field(default=False, repr=False)
    _handoff_reason: str | None = field(default=None, repr=False)
    _primary_intent: str | None = field(default=None, repr=False)
    _tone_used: str | None = field(default=None, repr=False)

    def _ensure_loaded(self):
        """Lazy-load messages from DB on first public method call."""
        if self._loaded_from_db or self._db is None:
            return
        self._loaded_from_db = True
        self._load_from_db()

    def _load_from_db(self):
        """Query Message table and populate in-memory state."""
        from src.database.models import Message

        try:
            rows = (
                self._db.query(Message)
                .filter(Message.session_id == self._session_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
                .all()
            )
        except Exception:
            logger.exception("Failed to load messages from DB for session %s", self._session_id)
            return

        for row in rows:
            if row.role in ("user", "assistant"):
                self.messages.append({"role": row.role, "content": row.content})
            elif row.role == "tool":
                meta = row.metadata_dict
                self.tool_results.append({
                    "tool": meta.get("tool_name", ""),
                    "result": meta.get("tool_result", {}),
                })

    def _persist_message(self, role: str, content: str, metadata: dict | None = None):
        """Write a single Message row to DB. No-op when DB is not configured."""
        if self._db is None or self._session_id is None:
            return
        from src.database.models import Message

        try:
            msg = Message(
                session_id=self._session_id,
                role=role,
                content=content,
            )
            if metadata:
                msg.metadata_dict = metadata
            self._db.add(msg)
            self._db.commit()
        except Exception:
            logger.exception("Failed to persist message for session %s", self._session_id)
            try:
                self._db.rollback()
            except Exception:
                pass

    def add_message(self, role: str, content: str):
        self._ensure_loaded()
        self.messages.append({"role": role, "content": content})
        self._persist_message(role, content)

    def add_intent(self, intent: str):
        self._ensure_loaded()
        self.intent_history.append(intent.lower().strip())

    def add_tool_result(self, tool_name: str, result: dict):
        self._ensure_loaded()
        self.tool_results.append({"tool": tool_name, "result": result})
        if self._primary_intent is None and tool_name in TOOL_TO_INTENT:
            self._primary_intent = TOOL_TO_INTENT[tool_name]
        self._persist_message(
            role="tool",
            content=json.dumps(result),
            metadata={"tool_name": tool_name, "tool_result": result},
        )

    def get_messages(self) -> list[dict]:
        self._ensure_loaded()
        return self.messages.copy()

    def has_repeated_intent(self, current_intent: str, threshold: float = 0.85) -> bool:
        """Check if the current intent is semantically similar to a previous one.
        Uses simple word overlap ratio as a lightweight similarity measure.
        """
        self._ensure_loaded()
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
        self._ensure_loaded()
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
_sessions: dict[str, ConversationMemory] = {}


def get_memory(session_id: str, db: Session | None = None) -> ConversationMemory:
    """Get or create a ConversationMemory for the given session.
    When `db` is provided, the instance is wired for DB persistence.
    """
    if session_id not in _sessions:
        _sessions[session_id] = ConversationMemory(
            _db=db,
            _session_id=session_id,
        )
    else:
        # Update DB handle on each request (the Session object may differ)
        mem = _sessions[session_id]
        if db is not None:
            mem._db = db
            mem._session_id = session_id
    return _sessions[session_id]


def clear_memory(session_id: str):
    if session_id in _sessions:
        _sessions[session_id].clear()


def get_conversation_history(
    session_id: str,
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Query persisted messages with pagination. Returns a dict matching PaginatedHistory schema."""
    from src.database.models import Message
    from sqlalchemy import func

    total = (
        db.query(func.count(Message.id))
        .filter(Message.session_id == session_id)
        .scalar()
    )

    rows = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    messages = []
    for row in rows:
        messages.append({
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "metadata": row.metadata_dict,
        })

    return {
        "session_id": session_id,
        "messages": messages,
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < (total or 0),
    }

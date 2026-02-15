"""Persistent customer memory: session close, profile aggregation, and tone inference."""
import json
import math
from datetime import datetime

from sqlalchemy.orm import Session

from src.agent.analysis import analyze_sentiment
from src.agent.memory import _sessions, get_memory
from src.database.models import CustomerProfile, Message, Order, SessionInsights
from src.utils.logger import get_logger

logger = get_logger(__name__)

_CLOSING_PHRASES = [
    "glad i could help",
    "is there anything else",
    "anything else i can help",
    "ticket updated",
    "has been updated",
    "replacement",
    "refund has been",
    "successfully",
    "have a great day",
    "resolved",
]

_NEGATIVE_KEYWORDS = [
    "frustrated",
    "angry",
    "furious",
    "lawsuit",
    "legal",
    "manager",
    "supervisor",
    "unacceptable",
    "ridiculous",
    "terrible",
    "worst",
    "scam",
    "horrible",
    "disgusting",
]


def close_session(session_id: str, db: Session) -> SessionInsights:
    """Compute per-session analytics and persist a SessionInsights row.

    Called on session end (REST close endpoint or WebSocket disconnect).
    """
    memory = get_memory(session_id, db=db)

    # --- gather messages from DB ---
    first_user_msg = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.role == "user")
        .order_by(Message.created_at.asc(), Message.id.asc())
        .first()
    )
    last_user_msg = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.role == "user")
        .order_by(Message.created_at.desc(), Message.id.desc())
        .first()
    )
    last_assistant_msg = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.role == "assistant")
        .order_by(Message.created_at.desc(), Message.id.desc())
        .first()
    )

    total_messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .count()
    )

    # --- sentiment at start and end (2 LLM calls, only at close time) ---
    sentiment_start = _sentiment_score_for_text(first_user_msg.content if first_user_msg else None)
    sentiment_end = _sentiment_score_for_text(last_user_msg.content if last_user_msg else None)
    sentiment_drift = sentiment_end - sentiment_start

    final_sentiment = sentiment_end
    if final_sentiment > 0.2:
        sentiment_label = "positive"
    elif final_sentiment < -0.2:
        sentiment_label = "negative"
    else:
        sentiment_label = "neutral"

    # --- resolution status ---
    handoff_occurred = memory._handoff_occurred
    if handoff_occurred:
        resolution_status = "escalated"
    elif last_assistant_msg and _contains_closing_phrase(last_assistant_msg.content):
        resolution_status = "resolved"
    else:
        resolution_status = "unresolved"

    # --- tool calls list ---
    tool_names = [tr["tool"] for tr in memory.tool_results]

    # --- look up existing ConversationMeta for specialist info ---
    from src.database.models import ConversationMeta
    meta = (
        db.query(ConversationMeta)
        .filter(ConversationMeta.session_id == session_id)
        .first()
    )

    user_id = meta.user_id if meta else None

    now = datetime.utcnow()

    # --- upsert SessionInsights ---
    existing = (
        db.query(SessionInsights)
        .filter(SessionInsights.session_id == session_id)
        .first()
    )
    if existing:
        insight = existing
    else:
        insight = SessionInsights(session_id=session_id)
        db.add(insight)

    insight.user_id = user_id
    insight.sentiment_score = final_sentiment
    insight.sentiment_label = sentiment_label
    insight.assigned_specialist = meta.assigned_specialist if meta else None
    insight.specialist_confidence = meta.specialist_confidence if meta else None
    insight.intent_primary = memory._primary_intent
    insight.intent_confidence = None  # not computed at close time
    insight.sentiment_start = sentiment_start
    insight.sentiment_end = sentiment_end
    insight.sentiment_drift = sentiment_drift
    insight.handoff_occurred = 1 if handoff_occurred else 0
    insight.handoff_reason = memory._handoff_reason
    insight.resolution_status = resolution_status
    insight.message_count = total_messages
    insight.tool_calls_json = json.dumps(tool_names)
    insight.tone_used = memory._tone_used
    insight.closed_at = now
    insight.updated_at = now

    try:
        db.commit()
    except Exception:
        logger.exception("Failed to persist SessionInsights for %s", session_id)
        db.rollback()
        return insight

    # --- update profile if user is known ---
    if user_id:
        try:
            update_profile(user_id, db)
        except Exception:
            logger.exception("Failed to update CustomerProfile for user %d", user_id)

    # --- clean up in-memory session ---
    _sessions.pop(session_id, None)

    return insight


def update_profile(user_id: int, db: Session) -> CustomerProfile:
    """Recompute and persist a CustomerProfile from all SessionInsights for the user."""
    sessions = (
        db.query(SessionInsights)
        .filter(SessionInsights.user_id == user_id)
        .order_by(SessionInsights.closed_at.asc())
        .all()
    )

    total_sessions = len(sessions)
    total_escalations = sum(1 for s in sessions if s.handoff_occurred)
    resolved_count = sum(1 for s in sessions if s.resolution_status == "resolved")
    resolution_rate = resolved_count / total_sessions if total_sessions else 0.0

    # Weighted sentiment: exponential decay (0.7 rate), oldest→newest
    weighted_sentiment = _compute_weighted_sentiment(sessions)

    # Average sentiment drift
    drifts = [s.sentiment_drift for s in sessions if s.sentiment_drift is not None]
    avg_drift = sum(drifts) / len(drifts) if drifts else 0.0

    # Topic frequency
    topic_freq: dict[str, int] = {}
    for s in sessions:
        if s.intent_primary:
            topic_freq[s.intent_primary] = topic_freq.get(s.intent_primary, 0) + 1

    # Loyalty tier from total spend
    total_spend = (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .with_entities(Order.amount)
        .all()
    )
    total_spend_val = sum(row.amount for row in total_spend) if total_spend else 0.0
    loyalty_tier = _loyalty_tier(total_spend_val)

    # Risk flag
    escalation_rate = total_escalations / total_sessions if total_sessions else 0.0
    risk_reasons = []
    if escalation_rate > 0.4:
        risk_reasons.append("high_escalation_rate")
    if weighted_sentiment < -0.3:
        risk_reasons.append("low_sentiment")
    if avg_drift < -0.2:
        risk_reasons.append("negative_sentiment_trend")
    if _consecutive_unresolved(sessions) >= 3:
        risk_reasons.append("consecutive_unresolved")
    risk_flag = 1 if risk_reasons else 0

    # Preferred tone: most-used tone during resolved sessions
    preferred_tone = _preferred_tone(sessions, risk_flag, weighted_sentiment)

    # Timestamps
    first_contact = sessions[0].closed_at if sessions else None
    last_contact = sessions[-1].closed_at if sessions else None
    last_resolution = sessions[-1].resolution_status if sessions else None

    # Upsert
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == user_id).first()
    if not profile:
        profile = CustomerProfile(user_id=user_id)
        db.add(profile)

    profile.total_sessions = total_sessions
    profile.total_escalations = total_escalations
    profile.resolution_rate = round(resolution_rate, 3)
    profile.weighted_sentiment = round(weighted_sentiment, 3)
    profile.avg_sentiment_drift = round(avg_drift, 3)
    profile.topic_frequency_json = json.dumps(topic_freq)
    profile.loyalty_tier = loyalty_tier
    profile.total_spend = round(total_spend_val, 2)
    profile.risk_flag = risk_flag
    profile.risk_reasons_json = json.dumps(risk_reasons)
    profile.preferred_tone = preferred_tone
    profile.first_contact = first_contact
    profile.last_contact = last_contact
    profile.last_resolution_status = last_resolution
    profile.updated_at = datetime.utcnow()

    db.commit()
    return profile


def load_profile(user_id: int, db: Session) -> CustomerProfile | None:
    """Load an existing CustomerProfile for the given user."""
    return db.query(CustomerProfile).filter_by(user_id=user_id).first()


def infer_tone(profile: CustomerProfile | None, current_message: str) -> str:
    """Combine historical preference + real-time signals to pick a tone.

    No LLM call — keyword-based, zero latency added.
    """
    lower_msg = current_message.lower()

    # Acute negative keywords → professional
    if any(kw in lower_msg for kw in _NEGATIVE_KEYWORDS):
        return "professional"

    if profile:
        if profile.risk_flag:
            return "professional"
        if profile.preferred_tone:
            return profile.preferred_tone

    return "friendly"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sentiment_score_for_text(text: str | None) -> float:
    """Get a single sentiment score via the existing analyze_sentiment helper."""
    if not text:
        return 0.0
    result = analyze_sentiment([{"role": "user", "content": text}])
    return result.get("score", 0.0)


def _contains_closing_phrase(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _CLOSING_PHRASES)


def _compute_weighted_sentiment(sessions: list[SessionInsights]) -> float:
    """Exponential decay weighted sentiment (rate=0.7), oldest→newest."""
    if not sessions:
        return 0.0
    decay = 0.7
    total_weight = 0.0
    weighted_sum = 0.0
    n = len(sessions)
    for i, s in enumerate(sessions):
        score = s.sentiment_score if s.sentiment_score is not None else 0.0
        weight = math.pow(decay, n - 1 - i)
        weighted_sum += score * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight else 0.0


def _loyalty_tier(total_spend: float) -> str:
    if total_spend >= 2000:
        return "platinum"
    if total_spend >= 500:
        return "gold"
    if total_spend >= 100:
        return "silver"
    return "standard"


def _consecutive_unresolved(sessions: list[SessionInsights]) -> int:
    """Count trailing consecutive unresolved sessions."""
    count = 0
    for s in reversed(sessions):
        if s.resolution_status == "unresolved":
            count += 1
        else:
            break
    return count


def _preferred_tone(sessions: list[SessionInsights], risk_flag: int, sentiment: float) -> str:
    """Derive preferred tone from resolved sessions, with fallback heuristics."""
    tone_counts: dict[str, int] = {}
    for s in sessions:
        if s.resolution_status == "resolved" and s.tone_used:
            tone_counts[s.tone_used] = tone_counts.get(s.tone_used, 0) + 1
    if tone_counts:
        return max(tone_counts, key=tone_counts.get)
    # Fallback heuristics
    if risk_flag:
        return "professional"
    if sentiment > 0.5:
        return "playful"
    return "friendly"

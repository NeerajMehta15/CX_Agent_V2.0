from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    user_id: int | None = None
    tone: str | None = None


class ChatResponse(BaseModel):
    response: str
    handoff: bool = False
    handoff_reason: str | None = None
    session_id: str
    tool_calls: list[str] = []


class TicketUpdate(BaseModel):
    status: str


class UserProfile(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    created_at: str


class OrderOut(BaseModel):
    id: int
    product: str
    amount: float
    status: str
    created_at: str


class TicketOut(BaseModel):
    id: int
    subject: str
    description: str | None
    status: str
    priority: str
    assigned_to: str | None
    created_at: str


class HandoffEvent(BaseModel):
    session_id: str
    reason: str
    customer_message: str


class HandoffRequest(BaseModel):
    """Pending handoff request info."""
    session_id: str
    reason: str | None
    customer_message: str
    timestamp: str
    accepted_by: str | None = None


class AgentMessage(BaseModel):
    """Message from agent to customer."""
    message: str


class SessionMessage(BaseModel):
    """A message in a conversation session."""
    role: str  # 'customer', 'ai', or 'agent'
    content: str
    timestamp: str


class CopilotSuggestion(BaseModel):
    """AI co-pilot suggestion for agent."""
    suggestion: str


# Canned Responses
class CannedResponseCreate(BaseModel):
    shortcut: str
    title: str
    content: str
    category: str | None = None


class CannedResponseOut(BaseModel):
    id: int
    shortcut: str
    title: str
    content: str
    category: str | None


# Customer Context
class CustomerContext(BaseModel):
    user: UserProfile | None
    orders: list[OrderOut]
    tickets: list[TicketOut]


class LinkUserRequest(BaseModel):
    user_id: int


# Sentiment Analysis
class SentimentAnalysis(BaseModel):
    score: float      # -1.0 to 1.0
    label: str        # "negative", "neutral", "positive"
    confidence: float


# Smart Suggestions
class SmartSuggestion(BaseModel):
    suggestion: str
    confidence: float
    rationale: str


class SmartSuggestionsResponse(BaseModel):
    suggestions: list[SmartSuggestion]
    sentiment: SentimentAnalysis


# Persistent Conversation History
class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    timestamp: str | None = None
    metadata: dict = {}


class PaginatedHistory(BaseModel):
    session_id: str
    messages: list[MessageOut]
    total: int
    limit: int
    offset: int
    has_more: bool


# Knowledge Base
class KnowledgeSearchRequest(BaseModel):
    query: str
    num_results: int = 3


class KnowledgeSearchResult(BaseModel):
    content: str
    source: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchResult]
    query: str


class KnowledgeStatsResponse(BaseModel):
    status: str
    document_count: int
    persist_directory: str
    collection_name: str


class KnowledgeUploadRequest(BaseModel):
    content: str
    doc_name: str


# Persistent Customer Memory
class SessionInsightsOut(BaseModel):
    session_id: str
    user_id: int | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    intent_primary: str | None = None
    sentiment_start: float | None = None
    sentiment_end: float | None = None
    sentiment_drift: float | None = None
    handoff_occurred: bool = False
    resolution_status: str | None = None
    message_count: int = 0
    tone_used: str | None = None
    closed_at: str | None = None


class CustomerProfileOut(BaseModel):
    user_id: int
    total_sessions: int = 0
    total_escalations: int = 0
    resolution_rate: float = 0.0
    weighted_sentiment: float = 0.0
    avg_sentiment_drift: float = 0.0
    topic_frequency: dict = {}
    loyalty_tier: str = "standard"
    total_spend: float = 0.0
    risk_flag: bool = False
    risk_reasons: list[str] = []
    preferred_tone: str = "friendly"
    first_contact: str | None = None
    last_contact: str | None = None
    last_resolution_status: str | None = None


class SessionCloseResponse(BaseModel):
    session_id: str
    resolution_status: str | None = None
    sentiment_drift: float | None = None
    message: str = "Session closed"

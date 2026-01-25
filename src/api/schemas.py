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

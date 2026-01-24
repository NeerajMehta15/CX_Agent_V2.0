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

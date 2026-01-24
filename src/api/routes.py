from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.agent.cx_agent import run_agent
from src.agent.memory import get_memory
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    OrderOut,
    TicketOut,
    TicketUpdate,
    UserProfile,
)
from src.database.connection import get_db
from src.database.models import Order, Ticket, User

router = APIRouter(prefix="/api")


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Send a message to the CX agent and get a response."""
    result = run_agent(
        user_message=request.message,
        session_id=request.session_id,
        db=db,
        tone=request.tone,
    )
    return ChatResponse(
        response=result.message,
        handoff=result.handoff,
        handoff_reason=result.handoff_reason,
        session_id=request.session_id,
        tool_calls=result.tool_calls_made,
    )


@router.get("/sessions/{session_id}/history")
def get_history(session_id: str):
    """Retrieve chat history for a session."""
    memory = get_memory(session_id)
    return {"session_id": session_id, "messages": memory.get_messages()}


@router.get("/users/{user_id}", response_model=UserProfile)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user profile by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        created_at=str(user.created_at),
    )


@router.get("/users/{user_id}/orders", response_model=list[OrderOut])
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    """Get all orders for a user."""
    orders = db.query(Order).filter(Order.user_id == user_id).all()
    return [
        OrderOut(
            id=o.id,
            product=o.product,
            amount=o.amount,
            status=o.status,
            created_at=str(o.created_at),
        )
        for o in orders
    ]


@router.get("/users/{user_id}/tickets", response_model=list[TicketOut])
def get_user_tickets(user_id: int, db: Session = Depends(get_db)):
    """Get all tickets for a user."""
    tickets = db.query(Ticket).filter(Ticket.user_id == user_id).all()
    return [
        TicketOut(
            id=t.id,
            subject=t.subject,
            description=t.description,
            status=t.status,
            priority=t.priority,
            assigned_to=t.assigned_to,
            created_at=str(t.created_at),
        )
        for t in tickets
    ]


@router.put("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, update: TicketUpdate, db: Session = Depends(get_db)):
    """Update ticket status."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    valid_statuses = ["open", "in_progress", "resolved", "escalated"]
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    ticket.status = update.status
    db.commit()
    return {"message": "Ticket updated", "ticket_id": ticket_id, "new_status": update.status}

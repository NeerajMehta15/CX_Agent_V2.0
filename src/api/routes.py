from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.agent.cx_agent import run_agent
from src.agent.memory import get_memory
from src.api.schemas import (
    AgentMessage,
    CannedResponseCreate,
    CannedResponseOut,
    ChatRequest,
    ChatResponse,
    CopilotSuggestion,
    CustomerContext,
    HandoffRequest,
    LinkUserRequest,
    OrderOut,
    SentimentAnalysis,
    SessionMessage,
    SmartSuggestion,
    SmartSuggestionsResponse,
    TicketOut,
    TicketUpdate,
    UserProfile,
)
from src.api.websocket import (
    accepted_handoffs,
    customer_connections,
    handoff_sessions,
    pending_handoffs,
    session_messages,
    session_user_mapping,
)
from src.database.connection import get_db
from src.agent.analysis import analyze_sentiment, generate_smart_suggestions
from src.database.models import CannedResponse, Order, Ticket, User

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

    # Track messages in shared state for agent dashboard
    session_messages[request.session_id].append({
        "role": "customer",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat(),
    })
    session_messages[request.session_id].append({
        "role": "ai",
        "content": result.message,
        "timestamp": datetime.utcnow().isoformat(),
    })

    # If handoff triggered, store in pending handoffs
    if result.handoff:
        handoff_sessions.add(request.session_id)
        pending_handoffs[request.session_id] = {
            "reason": result.handoff_reason,
            "customer_message": request.message,
            "timestamp": datetime.utcnow().isoformat(),
        }

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


# ==================== Agent Dashboard Endpoints ====================


@router.get("/handoffs", response_model=list[HandoffRequest])
def list_handoffs():
    """List all pending handoff requests."""
    handoffs = []
    for session_id, data in pending_handoffs.items():
        handoffs.append(HandoffRequest(
            session_id=session_id,
            reason=data.get("reason"),
            customer_message=data.get("customer_message", ""),
            timestamp=data.get("timestamp", ""),
            accepted_by=accepted_handoffs.get(session_id),
        ))
    # Sort by timestamp (newest first)
    handoffs.sort(key=lambda h: h.timestamp, reverse=True)
    return handoffs


@router.post("/handoffs/{session_id}/accept")
def accept_handoff(session_id: str, agent_name: str = "Agent"):
    """Accept a handoff request."""
    if session_id not in pending_handoffs:
        raise HTTPException(status_code=404, detail="Handoff not found")
    if session_id in accepted_handoffs:
        raise HTTPException(status_code=400, detail=f"Already accepted by {accepted_handoffs[session_id]}")

    accepted_handoffs[session_id] = agent_name
    handoff_sessions.add(session_id)

    return {"message": "Handoff accepted", "session_id": session_id, "agent": agent_name}


@router.get("/handoffs/{session_id}/messages", response_model=list[SessionMessage])
def get_handoff_messages(session_id: str):
    """Get conversation history for a session."""
    # Also include conversation memory from the agent
    memory = get_memory(session_id)
    messages = []

    # First add messages from conversation memory (before handoff)
    for msg in memory.get_messages():
        role = "customer" if msg["role"] == "user" else "ai"
        messages.append(SessionMessage(
            role=role,
            content=msg["content"],
            timestamp="",  # Memory doesn't store timestamps
        ))

    # Then add any messages from the WebSocket session (during handoff)
    for msg in session_messages.get(session_id, []):
        # Avoid duplicates - check if this exact content is already in messages
        if not any(m.content == msg["content"] and m.role == msg["role"] for m in messages):
            messages.append(SessionMessage(
                role=msg["role"],
                content=msg["content"],
                timestamp=msg.get("timestamp", ""),
            ))

    return messages


@router.post("/handoffs/{session_id}/message")
async def send_agent_message(session_id: str, msg: AgentMessage, db: Session = Depends(get_db)):
    """Agent sends a message to the customer."""
    if session_id not in accepted_handoffs:
        raise HTTPException(status_code=400, detail="Session not accepted yet")

    # Store message in shared state
    session_messages[session_id].append({
        "role": "agent",
        "content": msg.message,
        "timestamp": datetime.utcnow().isoformat(),
    })

    # Try to send via WebSocket if customer is connected
    customer_ws = customer_connections.get(session_id)
    if customer_ws:
        try:
            await customer_ws.send_json({
                "type": "agent_message",
                "message": msg.message,
            })
        except Exception:
            pass  # Customer might have disconnected

    return {"message": "Message sent", "session_id": session_id}


@router.get("/handoffs/{session_id}/copilot", response_model=CopilotSuggestion)
def get_copilot_suggestion(session_id: str, db: Session = Depends(get_db)):
    """Get AI co-pilot suggestion based on conversation context."""
    # Get recent messages for context
    messages = session_messages.get(session_id, [])
    memory = get_memory(session_id)

    # Build context from conversation
    context_parts = []
    for msg in memory.get_messages()[-5:]:  # Last 5 messages from memory
        role = "Customer" if msg["role"] == "user" else "AI"
        context_parts.append(f"{role}: {msg['content']}")

    for msg in messages[-3:]:  # Last 3 messages from handoff
        role = msg["role"].capitalize()
        context_parts.append(f"{role}: {msg['content']}")

    context = "\n".join(context_parts) if context_parts else "No conversation context available."

    # Generate co-pilot suggestion
    copilot_prompt = f"""Based on this customer service conversation, suggest a helpful response for the human agent:

{context}

Provide a concise, professional suggestion for how the agent should respond. Focus on being helpful and resolving the customer's issue."""

    result = run_agent(
        user_message=copilot_prompt,
        session_id=f"copilot_{session_id}",
        db=db,
        role="agent_assist",
    )

    return CopilotSuggestion(suggestion=result.message)


# ==================== Canned Responses Endpoints ====================


@router.get("/canned-responses", response_model=list[CannedResponseOut])
def list_canned_responses(category: str | None = None, db: Session = Depends(get_db)):
    """List all canned responses, optionally filtered by category."""
    query = db.query(CannedResponse)
    if category:
        query = query.filter(CannedResponse.category == category)
    responses = query.all()
    return [
        CannedResponseOut(
            id=r.id,
            shortcut=r.shortcut,
            title=r.title,
            content=r.content,
            category=r.category,
        )
        for r in responses
    ]


@router.post("/canned-responses", response_model=CannedResponseOut)
def create_canned_response(response: CannedResponseCreate, db: Session = Depends(get_db)):
    """Create a new canned response."""
    # Check for duplicate shortcut
    existing = db.query(CannedResponse).filter(CannedResponse.shortcut == response.shortcut).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Shortcut '{response.shortcut}' already exists")

    canned = CannedResponse(
        shortcut=response.shortcut,
        title=response.title,
        content=response.content,
        category=response.category,
    )
    db.add(canned)
    db.commit()
    db.refresh(canned)

    return CannedResponseOut(
        id=canned.id,
        shortcut=canned.shortcut,
        title=canned.title,
        content=canned.content,
        category=canned.category,
    )


@router.delete("/canned-responses/{response_id}")
def delete_canned_response(response_id: int, db: Session = Depends(get_db)):
    """Delete a canned response."""
    canned = db.query(CannedResponse).filter(CannedResponse.id == response_id).first()
    if not canned:
        raise HTTPException(status_code=404, detail="Canned response not found")

    db.delete(canned)
    db.commit()
    return {"message": "Canned response deleted", "id": response_id}


# ==================== Customer Context Endpoints ====================


@router.get("/handoffs/{session_id}/context", response_model=CustomerContext)
def get_customer_context(session_id: str, db: Session = Depends(get_db)):
    """Get customer context (profile, orders, tickets) for a session."""
    user_id = session_user_mapping.get(session_id)

    if not user_id:
        return CustomerContext(user=None, orders=[], tickets=[])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return CustomerContext(user=None, orders=[], tickets=[])

    orders = db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).all()
    tickets = db.query(Ticket).filter(Ticket.user_id == user_id).order_by(Ticket.created_at.desc()).all()

    return CustomerContext(
        user=UserProfile(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            created_at=str(user.created_at),
        ),
        orders=[
            OrderOut(
                id=o.id,
                product=o.product,
                amount=o.amount,
                status=o.status,
                created_at=str(o.created_at),
            )
            for o in orders
        ],
        tickets=[
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
        ],
    )


@router.post("/handoffs/{session_id}/link-user")
def link_user_to_session(session_id: str, request: LinkUserRequest, db: Session = Depends(get_db)):
    """Link a user to a session for customer context."""
    # Verify user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session_user_mapping[session_id] = request.user_id
    return {"message": "User linked to session", "session_id": session_id, "user_id": request.user_id}


# ==================== AI Analysis Endpoints ====================


@router.get("/handoffs/{session_id}/sentiment", response_model=SentimentAnalysis)
def get_sentiment_analysis(session_id: str):
    """Get sentiment analysis for a session's conversation."""
    # Get messages from memory and session
    memory = get_memory(session_id)
    messages = []

    # Messages from memory
    for msg in memory.get_messages():
        messages.append({
            "role": "customer" if msg["role"] == "user" else msg["role"],
            "content": msg["content"],
        })

    # Messages from session state
    for msg in session_messages.get(session_id, []):
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    result = analyze_sentiment(messages)
    return SentimentAnalysis(
        score=result["score"],
        label=result["label"],
        confidence=result["confidence"],
    )


@router.get("/handoffs/{session_id}/smart-suggestions", response_model=SmartSuggestionsResponse)
def get_smart_suggestions(session_id: str, db: Session = Depends(get_db)):
    """Get AI-generated smart suggestions with sentiment context."""
    # Get messages
    memory = get_memory(session_id)
    messages = []

    for msg in memory.get_messages():
        messages.append({
            "role": "customer" if msg["role"] == "user" else msg["role"],
            "content": msg["content"],
        })

    for msg in session_messages.get(session_id, []):
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    # Get sentiment
    sentiment = analyze_sentiment(messages)

    # Get customer context if available
    customer_context = None
    user_id = session_user_mapping.get(session_id)
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            orders = db.query(Order).filter(Order.user_id == user_id).all()
            tickets = db.query(Ticket).filter(Ticket.user_id == user_id).all()
            customer_context = {
                "user": {"name": user.name, "email": user.email},
                "orders": [{"product": o.product, "amount": o.amount, "status": o.status} for o in orders],
                "tickets": [{"subject": t.subject, "status": t.status, "priority": t.priority} for t in tickets],
            }

    # Generate suggestions
    suggestions = generate_smart_suggestions(messages, sentiment, customer_context)

    return SmartSuggestionsResponse(
        suggestions=[
            SmartSuggestion(
                suggestion=s["suggestion"],
                confidence=s["confidence"],
                rationale=s["rationale"],
            )
            for s in suggestions
        ],
        sentiment=SentimentAnalysis(
            score=sentiment["score"],
            label=sentiment["label"],
            confidence=sentiment["confidence"],
        ),
    )

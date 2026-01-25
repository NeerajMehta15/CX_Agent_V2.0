import json

from sqlalchemy.orm import Session

from src.api.websocket import session_user_mapping
from src.config.permissions import can_write, can_read
from src.database.middleware import sanitize_input, validate_column_access
from src.database.models import User, Order, Ticket
from src.utils.logger import get_logger

logger = get_logger(__name__)

# OpenAI function definitions for the agent
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_user",
            "description": "Look up a customer by email or user ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Customer email address"},
                    "user_id": {"type": "integer", "description": "Customer user ID"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders",
            "description": "Get orders for a specific customer by user ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "Customer user ID"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tickets",
            "description": "Get support tickets for a specific customer by user ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "Customer user ID"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_ticket",
            "description": "Update the status of a support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "integer", "description": "Ticket ID to update"},
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "resolved", "escalated"],
                        "description": "New status for the ticket",
                    },
                },
                "required": ["ticket_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_email",
            "description": "Update a customer's email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "Customer user ID"},
                    "new_email": {"type": "string", "description": "New email address"},
                },
                "required": ["user_id", "new_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_refund",
            "description": "Flag an order for refund review by updating its status to 'refunded'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "Order ID to flag for refund"},
                },
                "required": ["order_id"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict, db: Session, role: str = "customer_ai", session_id: str | None = None) -> str:
    """Execute a tool call and return the result as a JSON string."""
    try:
        if name == "lookup_user":
            return _lookup_user(db, role, session_id=session_id, **arguments)
        elif name == "get_orders":
            return _get_orders(db, role, **arguments)
        elif name == "get_tickets":
            return _get_tickets(db, role, **arguments)
        elif name == "update_ticket":
            return _update_ticket(db, role, **arguments)
        elif name == "update_user_email":
            return _update_user_email(db, role, **arguments)
        elif name == "flag_refund":
            return _flag_refund(db, role, **arguments)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.error(f"Tool execution error ({name}): {e}")
        return json.dumps({"error": "An internal error occurred."})


def _lookup_user(db: Session, role: str, email: str = None, user_id: int = None, session_id: str | None = None) -> str:
    if not can_read(role, "users"):
        return json.dumps({"error": "Permission denied."})
    user = None
    if email:
        sanitize_input(email)
        user = db.query(User).filter(User.email == email).first()
    elif user_id:
        user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return json.dumps({"result": None, "message": "User not found."})

    # Auto-link user to session for customer context
    if session_id and user:
        session_user_mapping[session_id] = user.id
        logger.info(f"Auto-linked user {user.id} to session {session_id}")

    return json.dumps({
        "result": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "created_at": str(user.created_at),
        }
    })


def _get_orders(db: Session, role: str, user_id: int) -> str:
    if not can_read(role, "orders"):
        return json.dumps({"error": "Permission denied."})
    orders = db.query(Order).filter(Order.user_id == user_id).all()
    if not orders:
        return json.dumps({"result": [], "message": "No orders found for this user."})
    return json.dumps({
        "result": [
            {
                "id": o.id,
                "product": o.product,
                "amount": o.amount,
                "status": o.status,
                "created_at": str(o.created_at),
            }
            for o in orders
        ]
    })


def _get_tickets(db: Session, role: str, user_id: int) -> str:
    if not can_read(role, "tickets"):
        return json.dumps({"error": "Permission denied."})
    tickets = db.query(Ticket).filter(Ticket.user_id == user_id).all()
    if not tickets:
        return json.dumps({"result": [], "message": "No tickets found for this user."})
    return json.dumps({
        "result": [
            {
                "id": t.id,
                "subject": t.subject,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "assigned_to": t.assigned_to,
                "created_at": str(t.created_at),
            }
            for t in tickets
        ]
    })


def _update_ticket(db: Session, role: str, ticket_id: int, status: str) -> str:
    if not can_write(role, "tickets", "status"):
        return json.dumps({"error": "Permission denied: cannot update ticket status."})
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return json.dumps({"error": "Ticket not found."})
    ticket.status = status
    db.commit()
    db.refresh(ticket)
    logger.info(f"Ticket {ticket_id} status updated to '{status}'")
    return json.dumps({"result": "Ticket updated.", "new_status": status})


def _update_user_email(db: Session, role: str, user_id: int, new_email: str) -> str:
    if not can_write(role, "users", "email"):
        return json.dumps({"error": "Permission denied: cannot update user email."})
    sanitize_input(new_email)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return json.dumps({"error": "User not found."})
    user.email = new_email
    db.commit()
    db.refresh(user)
    logger.info(f"User {user_id} email updated to '{new_email}'")
    return json.dumps({"result": "Email updated.", "new_email": new_email})


def _flag_refund(db: Session, role: str, order_id: int) -> str:
    if not can_write(role, "orders", "status"):
        return json.dumps({"error": "Permission denied: cannot flag refund."})
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return json.dumps({"error": "Order not found."})
    order.status = "refunded"
    db.commit()
    db.refresh(order)
    logger.info(f"Order {order_id} flagged for refund")
    return json.dumps({"result": "Order flagged for refund.", "order_id": order_id})

"""LangGraph-based multi-agent routing system for the CX Agent."""
import json
from typing import TypedDict

from langgraph.graph import StateGraph, END
from openai import OpenAI
from sqlalchemy.orm import Session

from src.agent.cx_agent import AgentResponse
from src.agent.memory import get_memory
from src.agent.tools import TOOL_DEFINITIONS, execute_tool
from src.agent.handoff import check_handoff, HandoffReason
from src.config.prompts import get_system_prompt
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.llm_base_url)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ConversationState(TypedDict, total=False):
    messages: list[dict]
    user_message: str
    intent: str                    # general | refund | technical | escalate
    intent_confidence: float       # 0.0 - 1.0
    user_context: dict | None
    session_id: str
    db: object                     # SQLAlchemy Session (not serialisable, runtime only)
    role: str
    tone: str | None
    assigned_specialist: str | None
    specialist_reasoning: str | None
    final_response: str | None
    handoff_triggered: bool
    handoff_reason: str | None
    tool_calls_made: list[str]


# ---------------------------------------------------------------------------
# Node: classify intent
# ---------------------------------------------------------------------------

INTENT_CLASSIFICATION_PROMPT = """\
You are an intent classifier for a customer service system.

Classify the customer message into exactly ONE of these intents:
- "refund": Customer wants a refund, return, money back, or compensation for a purchase.
- "technical": Customer has a technical issue, needs troubleshooting, setup help, or how-to guidance.
- "escalate": Customer explicitly asks for a manager, supervisor, or to escalate their issue.
- "general": Any other customer service inquiry (order status, account changes, general questions).

Consider the overall tone and keywords. Respond in JSON only:
{"intent": "<intent>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}
"""


def classify_intent(state: ConversationState) -> dict:
    """Use a lightweight model to classify the customer's intent."""
    user_message = state["user_message"]

    try:
        response = client.chat.completions.create(
            model=settings.llm_model_mini,
            messages=[
                {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
        )
        raw = response.choices[0].message.content or "{}"
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)

        intent = result.get("intent", "general")
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "")

        # Validate intent value
        if intent not in ("refund", "technical", "escalate", "general"):
            intent = "general"
            confidence = 0.5

        logger.info(
            f"[router] Intent classified: {intent} (confidence={confidence:.2f}) "
            f"for message: {user_message[:80]!r}"
        )

        return {
            "intent": intent,
            "intent_confidence": confidence,
            "specialist_reasoning": reasoning,
        }

    except Exception:
        logger.exception("Intent classification failed, defaulting to general")
        return {
            "intent": "general",
            "intent_confidence": 0.0,
            "specialist_reasoning": "Classification failed, falling back to general.",
        }


# ---------------------------------------------------------------------------
# Router: conditional edge
# ---------------------------------------------------------------------------

def route_to_specialist(state: ConversationState) -> str:
    """Decide which specialist node to route to based on intent + confidence."""
    intent = state.get("intent", "general")
    confidence = state.get("intent_confidence", 0.0)

    if confidence < 0.6:
        logger.info(f"[router] Low confidence ({confidence:.2f}), routing to general_agent")
        return "general_agent"

    if intent == "escalate":
        logger.info("[router] Escalation requested, ending with handoff")
        return "escalate"

    if intent == "refund":
        logger.info(f"[router] Routing to refund_specialist (confidence={confidence:.2f})")
        return "refund_specialist"

    if intent == "technical":
        logger.info(f"[router] Routing to technical_specialist (confidence={confidence:.2f})")
        return "technical_specialist"

    logger.info("[router] Defaulting to general_agent")
    return "general_agent"


# ---------------------------------------------------------------------------
# Specialist nodes
# ---------------------------------------------------------------------------

def general_agent_node(state: ConversationState) -> dict:
    """Run the general-purpose CX agent."""
    db = state["db"]
    session_id = state["session_id"]
    user_message = state["user_message"]
    role = state.get("role", "customer_ai")
    tone = state.get("tone")

    memory = get_memory(session_id, db=db)

    # Check for repeated intent before processing
    handoff_result = check_handoff(memory, user_message)
    if handoff_result:
        memory.add_message("user", user_message)
        msg = _get_handoff_message(handoff_result)
        memory.add_message("assistant", msg)
        return {
            "assigned_specialist": "general",
            "final_response": msg,
            "handoff_triggered": True,
            "handoff_reason": handoff_result.value,
            "tool_calls_made": [],
        }

    system_prompt = get_system_prompt(tone)
    messages = [{"role": "system", "content": system_prompt}]

    if state.get("user_context"):
        messages.append({
            "role": "system",
            "content": f"Customer context: {json.dumps(state['user_context'])}",
        })

    messages.extend(memory.get_messages())
    messages.append({"role": "user", "content": user_message})

    memory.add_intent(user_message)
    memory.add_message("user", user_message)

    tool_calls_made = []
    max_iterations = 5

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        choice = response.choices[0]

        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            assistant_message = choice.message.content or ""
            memory.add_message("assistant", assistant_message)

            if memory.last_tool_returned_empty():
                handoff_result = HandoffReason.DATA_GAP
                msg = _get_handoff_message(handoff_result)
                memory.add_message("assistant", msg)
                return {
                    "assigned_specialist": "general",
                    "final_response": f"{assistant_message}\n\n{msg}",
                    "handoff_triggered": True,
                    "handoff_reason": handoff_result.value,
                    "tool_calls_made": tool_calls_made,
                }

            return {
                "assigned_specialist": "general",
                "final_response": assistant_message,
                "handoff_triggered": False,
                "handoff_reason": None,
                "tool_calls_made": tool_calls_made,
            }

        messages.append(choice.message)
        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            tool_calls_made.append(fn_name)

            logger.info(f"[general_agent] Tool call: {fn_name}({fn_args})")
            result_str = execute_tool(fn_name, fn_args, db, role, session_id=session_id)
            result_data = json.loads(result_str)
            memory.add_tool_result(fn_name, result_data)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

    return {
        "assigned_specialist": "general",
        "final_response": "I'm having trouble processing your request. Let me connect you with a human agent.",
        "handoff_triggered": True,
        "handoff_reason": "max_iterations_exceeded",
        "tool_calls_made": tool_calls_made,
    }


def refund_specialist_node(state: ConversationState) -> dict:
    """Run the refund specialist."""
    from src.agent.specialists.refund_specialist import run_refund_specialist

    db = state["db"]
    role = state.get("role", "customer_ai")

    result = run_refund_specialist(state, db, role)
    return {
        "assigned_specialist": "refund",
        "final_response": result["response"],
        "handoff_triggered": result["handoff"],
        "handoff_reason": result["handoff_reason"],
        "tool_calls_made": result["tool_calls_made"],
    }


def technical_specialist_node(state: ConversationState) -> dict:
    """Run the technical specialist."""
    from src.agent.specialists.technical_specialist import run_technical_specialist

    db = state["db"]
    role = state.get("role", "customer_ai")

    result = run_technical_specialist(state, db, role)
    return {
        "assigned_specialist": "technical",
        "final_response": result["response"],
        "handoff_triggered": result["handoff"],
        "handoff_reason": result["handoff_reason"],
        "tool_calls_made": result["tool_calls_made"],
    }


def escalate_node(state: ConversationState) -> dict:
    """Handle escalation — immediate handoff to human agent."""
    session_id = state["session_id"]
    db = state["db"]
    memory = get_memory(session_id, db=db)

    msg = (
        "I understand you'd like to speak with a supervisor. "
        "I'm connecting you with a human agent right away."
    )
    memory.add_message("user", state["user_message"])
    memory.add_message("assistant", msg)

    return {
        "assigned_specialist": "escalate",
        "final_response": msg,
        "handoff_triggered": True,
        "handoff_reason": "customer_requested_escalation",
        "tool_calls_made": [],
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def create_agent_graph() -> StateGraph:
    """Build and compile the LangGraph agent routing graph."""
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("classify", classify_intent)
    graph.add_node("general_agent", general_agent_node)
    graph.add_node("refund_specialist", refund_specialist_node)
    graph.add_node("technical_specialist", technical_specialist_node)
    graph.add_node("escalate", escalate_node)

    # Entry point
    graph.set_entry_point("classify")

    # Conditional routing from classifier
    graph.add_conditional_edges(
        "classify",
        route_to_specialist,
        {
            "general_agent": "general_agent",
            "refund_specialist": "refund_specialist",
            "technical_specialist": "technical_specialist",
            "escalate": "escalate",
        },
    )

    # All specialist nodes go to END
    graph.add_edge("general_agent", END)
    graph.add_edge("refund_specialist", END)
    graph.add_edge("technical_specialist", END)
    graph.add_edge("escalate", END)

    return graph.compile()


# Module-level compiled graph (reused across requests)
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = create_agent_graph()
    return _compiled_graph


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_agent_with_router(
    user_message: str,
    session_id: str,
    db: Session,
    tone: str | None = None,
    role: str = "customer_ai",
) -> AgentResponse:
    """Entry point for routed conversations. Runs the LangGraph and returns AgentResponse."""
    from src.api.websocket import session_user_mapping
    from src.database.models import User, Order, Ticket, ConversationMeta

    # Fetch user context if available
    user_context = None
    user_id = session_user_mapping.get(session_id)
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            orders = db.query(Order).filter(Order.user_id == user_id).all()
            tickets = db.query(Ticket).filter(Ticket.user_id == user_id).all()
            user_context = {
                "user": {"name": user.name, "email": user.email},
                "orders": [
                    {"id": o.id, "product": o.product, "amount": o.amount, "status": o.status}
                    for o in orders
                ],
                "tickets": [
                    {"id": t.id, "subject": t.subject, "status": t.status, "priority": t.priority}
                    for t in tickets
                ],
            }

    initial_state: ConversationState = {
        "messages": [],
        "user_message": user_message,
        "intent": "",
        "intent_confidence": 0.0,
        "user_context": user_context,
        "session_id": session_id,
        "db": db,
        "role": role,
        "tone": tone,
        "assigned_specialist": None,
        "specialist_reasoning": None,
        "final_response": None,
        "handoff_triggered": False,
        "handoff_reason": None,
        "tool_calls_made": [],
    }

    graph = _get_graph()
    final_state = graph.invoke(initial_state)

    # Persist specialist info to ConversationMeta
    specialist = final_state.get("assigned_specialist")
    confidence = final_state.get("intent_confidence", 0.0)
    if specialist:
        try:
            meta = (
                db.query(ConversationMeta)
                .filter(ConversationMeta.session_id == session_id)
                .first()
            )
            if meta:
                meta.assigned_specialist = specialist
                meta.specialist_confidence = confidence
            else:
                meta = ConversationMeta(
                    session_id=session_id,
                    assigned_specialist=specialist,
                    specialist_confidence=confidence,
                )
                db.add(meta)
            db.commit()
        except Exception:
            logger.exception("Failed to save specialist info to ConversationMeta")
            try:
                db.rollback()
            except Exception:
                pass

    return AgentResponse(
        message=final_state.get("final_response", ""),
        handoff=final_state.get("handoff_triggered", False),
        handoff_reason=final_state.get("handoff_reason"),
        tool_calls_made=final_state.get("tool_calls_made", []),
    )


def _get_handoff_message(reason: HandoffReason) -> str:
    messages = {
        HandoffReason.REPEATED_INTENT: (
            "I notice I haven't been able to fully resolve your concern. "
            "Let me connect you with a human agent who can help further."
        ),
        HandoffReason.DATA_GAP: (
            "I wasn't able to find the information needed to help you. "
            "I'm transferring you to a human agent who can look into this."
        ),
        HandoffReason.HALLUCINATION_RISK: (
            "I want to make sure you get accurate information. "
            "Let me connect you with a human agent for this request."
        ),
    }
    return messages.get(reason, "Connecting you with a human agent.")

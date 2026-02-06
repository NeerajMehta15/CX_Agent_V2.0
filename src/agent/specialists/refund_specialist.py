import json
from typing import TYPE_CHECKING

from openai import OpenAI
from sqlalchemy.orm import Session

from src.agent.memory import get_memory
from src.agent.tools import TOOL_DEFINITIONS, execute_tool
from src.agent.handoff import check_handoff, HandoffReason
from src.config.settings import settings
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.agent.graph_router import ConversationState

logger = get_logger(__name__)

REFUND_SPECIALIST_PROMPT = """You are a refund specialist for our customer service team. \
Your expertise covers:
- Processing refunds within our 30-day return policy
- Handling returns for defective or wrong items
- Evaluating refund eligibility based on order status and purchase date

Priority: Provide quick, empathetic resolution. Always acknowledge the customer's frustration \
before discussing policy. When a customer qualifies for a refund, use the flag_refund tool to \
initiate it. Always offer a replacement as an alternative before processing a refund.

Important guidelines:
- Check order details before making promises
- If the order is outside the 30-day window, explain the policy kindly and offer alternatives
- For defective items, prioritize replacement over refund
- Always confirm the customer's preferred resolution (refund vs replacement)"""

client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.llm_base_url)


def run_refund_specialist(
    state: "ConversationState",
    db: Session,
    role: str = "customer_ai",
) -> dict:
    """Run the refund specialist agent loop. Returns response dict."""
    session_id = state["session_id"]
    user_message = state["user_message"]
    memory = get_memory(session_id, db=db)

    # Check for repeated intent / data gap before processing
    handoff_result = check_handoff(memory, user_message)
    if handoff_result:
        memory.add_message("user", user_message)
        msg = _handoff_message(handoff_result)
        memory.add_message("assistant", msg)
        return {
            "response": msg,
            "handoff": True,
            "handoff_reason": handoff_result.value,
            "tool_calls_made": [],
        }

    # Build messages with specialist prompt
    messages = [{"role": "system", "content": REFUND_SPECIALIST_PROMPT}]

    # Add user context if available
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
                msg = _handoff_message(HandoffReason.DATA_GAP)
                memory.add_message("assistant", msg)
                return {
                    "response": f"{assistant_message}\n\n{msg}",
                    "handoff": True,
                    "handoff_reason": HandoffReason.DATA_GAP.value,
                    "tool_calls_made": tool_calls_made,
                }

            return {
                "response": assistant_message,
                "handoff": False,
                "handoff_reason": None,
                "tool_calls_made": tool_calls_made,
            }

        # Process tool calls
        messages.append(choice.message)
        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            tool_calls_made.append(fn_name)

            logger.info(f"[refund_specialist] Tool call: {fn_name}({fn_args})")
            result_str = execute_tool(fn_name, fn_args, db, role, session_id=session_id)
            result_data = json.loads(result_str)
            memory.add_tool_result(fn_name, result_data)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

    return {
        "response": "I'm having trouble processing your refund request. Let me connect you with a human agent.",
        "handoff": True,
        "handoff_reason": "max_iterations_exceeded",
        "tool_calls_made": tool_calls_made,
    }


def _handoff_message(reason: HandoffReason) -> str:
    messages = {
        HandoffReason.REPEATED_INTENT: (
            "I notice I haven't been able to fully resolve your refund concern. "
            "Let me connect you with a human agent who can help further."
        ),
        HandoffReason.DATA_GAP: (
            "I wasn't able to find the information needed to process your refund. "
            "I'm transferring you to a human agent who can look into this."
        ),
        HandoffReason.HALLUCINATION_RISK: (
            "I want to make sure you get accurate information about your refund. "
            "Let me connect you with a human agent."
        ),
    }
    return messages.get(reason, "Connecting you with a human agent.")

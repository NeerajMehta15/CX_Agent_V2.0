import json
from dataclasses import dataclass, field

from openai import OpenAI
from sqlalchemy.orm import Session

from src.agent.memory import ConversationMemory, get_memory
from src.agent.tools import TOOL_DEFINITIONS, execute_tool
from src.agent.handoff import check_handoff, HandoffReason
from src.config.prompts import get_system_prompt
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.llm_base_url)


@dataclass
class AgentResponse:
    message: str
    handoff: bool = False
    handoff_reason: str | None = None
    tool_calls_made: list[str] = field(default_factory=list)


def run_agent(
    user_message: str,
    session_id: str,
    db: Session,
    tone: str | None = None,
    role: str = "customer_ai",
) -> AgentResponse:
    """Process a user message through the CX agent and return a response."""
    memory = get_memory(session_id, db=db)

    # Check for repeated intent before processing
    handoff_result = check_handoff(memory, user_message)
    if handoff_result:
        memory.add_message("user", user_message)
        transition_msg = _get_handoff_message(handoff_result)
        memory.add_message("assistant", transition_msg)
        return AgentResponse(
            message=transition_msg,
            handoff=True,
            handoff_reason=handoff_result.value,
        )

    # Build conversation messages
    system_prompt = get_system_prompt(tone)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory.get_messages())
    messages.append({"role": "user", "content": user_message})

    # Track intent
    memory.add_intent(user_message)
    memory.add_message("user", user_message)

    tool_calls_made = []

    # Run the agent loop (handle multiple tool calls)
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
            # Final response from the model
            assistant_message = choice.message.content or ""
            memory.add_message("assistant", assistant_message)

            # Post-response handoff check (data gap)
            if memory.last_tool_returned_empty():
                handoff_result = HandoffReason.DATA_GAP
                transition_msg = _get_handoff_message(handoff_result)
                memory.add_message("assistant", transition_msg)
                return AgentResponse(
                    message=f"{assistant_message}\n\n{transition_msg}",
                    handoff=True,
                    handoff_reason=handoff_result.value,
                    tool_calls_made=tool_calls_made,
                )

            return AgentResponse(
                message=assistant_message,
                tool_calls_made=tool_calls_made,
            )

        # Process tool calls
        messages.append(choice.message)
        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            tool_calls_made.append(fn_name)

            logger.info(f"Tool call: {fn_name}({fn_args})")
            result_str = execute_tool(fn_name, fn_args, db, role, session_id=session_id)
            result_data = json.loads(result_str)
            memory.add_tool_result(fn_name, result_data)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

    # If we exhaust iterations, return what we have
    return AgentResponse(
        message="I'm having trouble processing your request. Let me connect you with a human agent.",
        handoff=True,
        handoff_reason="max_iterations_exceeded",
        tool_calls_made=tool_calls_made,
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

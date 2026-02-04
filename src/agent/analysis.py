"""AI-powered conversation analysis for sentiment and smart suggestions."""
import json
from openai import OpenAI
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.llm_base_url)


def analyze_sentiment(messages: list[dict]) -> dict:
    """
    Analyze sentiment of conversation messages.

    Args:
        messages: List of message dicts with 'role' and 'content' keys

    Returns:
        dict with score (-1.0 to 1.0), label, and confidence
    """
    if not messages:
        return {"score": 0.0, "label": "neutral", "confidence": 0.5}

    # Build conversation context (focus on customer messages)
    customer_messages = [
        msg["content"] for msg in messages
        if msg.get("role") in ("customer", "user")
    ]

    if not customer_messages:
        return {"score": 0.0, "label": "neutral", "confidence": 0.5}

    conversation_text = "\n".join(customer_messages[-5:])  # Last 5 customer messages

    try:
        response = client.chat.completions.create(
            model=settings.llm_model_mini,
            messages=[
                {
                    "role": "system",
                    "content": """You are a sentiment analysis expert. Analyze the customer's sentiment in the conversation.

Respond with a JSON object containing:
- score: A number from -1.0 (very negative) to 1.0 (very positive)
- label: One of "negative", "neutral", or "positive"
- confidence: A number from 0.0 to 1.0 indicating your confidence

Consider tone, word choice, punctuation (e.g., caps, exclamation marks), and overall context.

Respond ONLY with the JSON object, no additional text."""
                },
                {
                    "role": "user",
                    "content": f"Analyze the sentiment of these customer messages:\n\n{conversation_text}"
                }
            ],
            temperature=0.3,
            max_tokens=100,
        )

        result_text = response.choices[0].message.content.strip()
        # Parse JSON response
        result = json.loads(result_text)

        return {
            "score": float(result.get("score", 0.0)),
            "label": result.get("label", "neutral"),
            "confidence": float(result.get("confidence", 0.5)),
        }

    except json.JSONDecodeError:
        logger.warning("Failed to parse sentiment JSON response")
        return {"score": 0.0, "label": "neutral", "confidence": 0.5}
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        return {"score": 0.0, "label": "neutral", "confidence": 0.5}


def generate_smart_suggestions(
    messages: list[dict],
    sentiment: dict,
    customer_context: dict | None = None
) -> list[dict]:
    """
    Generate 3 ranked response suggestions for the agent.

    Args:
        messages: Conversation history
        sentiment: Sentiment analysis result
        customer_context: Optional user profile, orders, tickets info

    Returns:
        List of suggestion dicts with suggestion, confidence, and rationale
    """
    if not messages:
        return []

    # Build conversation context
    context_parts = []
    for msg in messages[-10:]:  # Last 10 messages
        role = msg.get("role", "unknown")
        if role in ("customer", "user"):
            role = "Customer"
        elif role == "ai":
            role = "AI"
        elif role == "agent":
            role = "Agent"
        context_parts.append(f"{role}: {msg.get('content', '')}")

    conversation_context = "\n".join(context_parts)

    # Build customer context if available
    customer_info = ""
    if customer_context:
        user = customer_context.get("user")
        orders = customer_context.get("orders", [])
        tickets = customer_context.get("tickets", [])

        if user:
            customer_info += f"\n\nCustomer Profile:\n- Name: {user.get('name', 'Unknown')}\n- Email: {user.get('email', 'Unknown')}"

        if orders:
            customer_info += "\n\nRecent Orders:"
            for order in orders[:3]:
                customer_info += f"\n- {order.get('product', 'Unknown')} (${order.get('amount', 0):.2f}) - Status: {order.get('status', 'Unknown')}"

        if tickets:
            open_tickets = [t for t in tickets if t.get("status") in ("open", "in_progress")]
            if open_tickets:
                customer_info += "\n\nOpen Tickets:"
                for ticket in open_tickets[:3]:
                    customer_info += f"\n- {ticket.get('subject', 'Unknown')} (Priority: {ticket.get('priority', 'Unknown')})"

    # Build sentiment context
    sentiment_info = f"\n\nCustomer Sentiment: {sentiment.get('label', 'neutral').upper()} (score: {sentiment.get('score', 0):.2f})"

    prompt = f"""Based on this customer service conversation, generate 3 different response suggestions for the human agent.

Conversation:
{conversation_context}
{customer_info}
{sentiment_info}

Consider the customer's sentiment when crafting responses. If negative, be more empathetic. If positive, maintain the good rapport.

Respond with a JSON array of 3 objects, each containing:
- suggestion: The suggested response text (2-3 sentences)
- confidence: Your confidence this is the best response (0.0 to 1.0)
- rationale: Brief explanation of why this suggestion fits (1 sentence)

Order by confidence (highest first). Respond ONLY with the JSON array, no additional text."""

    try:
        response = client.chat.completions.create(
            model=settings.llm_model_mini,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert customer service coach helping agents craft helpful, empathetic responses."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=500,
        )

        result_text = response.choices[0].message.content.strip()
        suggestions = json.loads(result_text)

        # Validate and normalize suggestions
        validated = []
        for s in suggestions[:3]:
            validated.append({
                "suggestion": str(s.get("suggestion", "")),
                "confidence": float(s.get("confidence", 0.5)),
                "rationale": str(s.get("rationale", "")),
            })

        return validated

    except json.JSONDecodeError:
        logger.warning("Failed to parse suggestions JSON response")
        return []
    except Exception as e:
        logger.error(f"Smart suggestions error: {e}")
        return []

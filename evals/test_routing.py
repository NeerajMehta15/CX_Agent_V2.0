"""Tests for the LangGraph-based multi-agent routing system."""
import os
import pytest

from src.agent.graph_router import (
    classify_intent,
    route_to_specialist,
    ConversationState,
)

LLM_API_KEY = os.getenv("LLM_API_KEY")
skip_no_api_key = pytest.mark.skipif(
    not LLM_API_KEY,
    reason="LLM_API_KEY not set",
)


def _make_state(**overrides) -> ConversationState:
    """Helper to build a minimal ConversationState for testing."""
    base: ConversationState = {
        "messages": [],
        "user_message": "",
        "intent": "",
        "intent_confidence": 0.0,
        "user_context": None,
        "session_id": "test-session",
        "db": None,
        "role": "customer_ai",
        "tone": None,
        "assigned_specialist": None,
        "specialist_reasoning": None,
        "final_response": None,
        "handoff_triggered": False,
        "handoff_reason": None,
        "tool_calls_made": [],
    }
    base.update(overrides)
    return base


# -------------------------------------------------------------------------
# Routing logic tests (no LLM needed)
# -------------------------------------------------------------------------

class TestRouteToSpecialist:
    """Test the deterministic routing function."""

    def test_low_confidence_routes_to_general(self):
        state = _make_state(intent="refund", intent_confidence=0.3)
        assert route_to_specialist(state) == "general_agent"

    def test_low_confidence_boundary(self):
        state = _make_state(intent="technical", intent_confidence=0.59)
        assert route_to_specialist(state) == "general_agent"

    def test_refund_high_confidence(self):
        state = _make_state(intent="refund", intent_confidence=0.9)
        assert route_to_specialist(state) == "refund_specialist"

    def test_refund_threshold_confidence(self):
        state = _make_state(intent="refund", intent_confidence=0.6)
        assert route_to_specialist(state) == "refund_specialist"

    def test_technical_high_confidence(self):
        state = _make_state(intent="technical", intent_confidence=0.85)
        assert route_to_specialist(state) == "technical_specialist"

    def test_escalate_always_escalates(self):
        state = _make_state(intent="escalate", intent_confidence=0.95)
        assert route_to_specialist(state) == "escalate"

    def test_escalate_even_at_threshold(self):
        state = _make_state(intent="escalate", intent_confidence=0.6)
        assert route_to_specialist(state) == "escalate"

    def test_escalate_low_confidence_goes_general(self):
        """Escalate with very low confidence still goes to general."""
        state = _make_state(intent="escalate", intent_confidence=0.3)
        assert route_to_specialist(state) == "general_agent"

    def test_general_high_confidence(self):
        state = _make_state(intent="general", intent_confidence=0.9)
        assert route_to_specialist(state) == "general_agent"

    def test_unknown_intent_defaults_general(self):
        state = _make_state(intent="unknown", intent_confidence=0.9)
        assert route_to_specialist(state) == "general_agent"

    def test_empty_intent_defaults_general(self):
        state = _make_state(intent="", intent_confidence=0.0)
        assert route_to_specialist(state) == "general_agent"


# -------------------------------------------------------------------------
# Intent classification tests (require LLM)
# -------------------------------------------------------------------------

# Test cases: (message, expected_intent, description)
CLASSIFICATION_TEST_CASES = [
    # Refund intents
    ("I want a refund for my order", "refund", "Direct refund request"),
    ("I'd like my money back please", "refund", "Money back request"),
    ("Can I return this product?", "refund", "Return request"),
    ("This item is defective, I want a replacement or refund", "refund", "Defective item refund"),
    ("I was charged twice, I need a refund", "refund", "Double charge refund"),
    ("I never received my order, I want my money back", "refund", "Missing order refund"),

    # Technical intents
    ("How do I reset my device?", "technical", "Reset how-to"),
    ("My headphones won't connect to bluetooth", "technical", "Bluetooth troubleshooting"),
    ("The product stopped charging", "technical", "Charging issue"),
    ("I can't figure out how to set this up", "technical", "Setup help"),
    ("The screen is flickering on my new monitor", "technical", "Hardware diagnostic"),
    ("How do I update the firmware?", "technical", "Firmware update help"),

    # Escalation intents
    ("I want to speak to a manager", "escalate", "Manager request"),
    ("Let me talk to a supervisor", "escalate", "Supervisor request"),
    ("I need to escalate this issue", "escalate", "Direct escalation"),
    ("This is unacceptable, get me your manager", "escalate", "Angry escalation"),

    # General intents
    ("What's the status of my order?", "general", "Order status check"),
    ("Can you update my email address?", "general", "Account update"),
    ("What are your business hours?", "general", "General inquiry"),
    ("Hi, I need help with my account", "general", "Generic help request"),
    ("Do you have this product in blue?", "general", "Product inquiry"),
    ("When will my package arrive?", "general", "Delivery inquiry"),
]


@skip_no_api_key
class TestIntentClassification:
    """Test intent classification using the LLM."""

    @pytest.mark.parametrize(
        "message,expected_intent,description",
        CLASSIFICATION_TEST_CASES,
        ids=[c[2] for c in CLASSIFICATION_TEST_CASES],
    )
    def test_individual_classification(self, message, expected_intent, description):
        """Test that individual messages are classified correctly."""
        state = _make_state(user_message=message)
        result = classify_intent(state)
        assert result["intent"] == expected_intent, (
            f"Expected '{expected_intent}' for '{message}', "
            f"got '{result['intent']}' (confidence={result['intent_confidence']:.2f}, "
            f"reasoning={result.get('specialist_reasoning', '')})"
        )

    def test_routing_accuracy(self):
        """Test overall routing accuracy across all test cases (>80% required)."""
        correct = 0
        failures = []

        for message, expected, desc in CLASSIFICATION_TEST_CASES:
            state = _make_state(user_message=message)
            result = classify_intent(state)
            if result["intent"] == expected:
                correct += 1
            else:
                failures.append(
                    f"  [{desc}] '{message}' → expected '{expected}', "
                    f"got '{result['intent']}' ({result['intent_confidence']:.2f})"
                )

        total = len(CLASSIFICATION_TEST_CASES)
        accuracy = correct / total
        threshold = 0.80

        fail_report = "\n".join(failures) if failures else "None"
        assert accuracy >= threshold, (
            f"Routing accuracy {accuracy:.0%} ({correct}/{total}) is below "
            f"{threshold:.0%} threshold.\nFailures:\n{fail_report}"
        )

    def test_confidence_is_reasonable(self):
        """Test that classification confidence values are within expected range."""
        clear_messages = [
            "I want a full refund right now",
            "My device won't turn on at all",
            "Get me your manager immediately",
        ]
        for msg in clear_messages:
            state = _make_state(user_message=msg)
            result = classify_intent(state)
            assert 0.0 <= result["intent_confidence"] <= 1.0, (
                f"Confidence {result['intent_confidence']} out of range for '{msg}'"
            )
            # Clear intents should have high confidence
            assert result["intent_confidence"] >= 0.7, (
                f"Expected high confidence for clear intent '{msg}', "
                f"got {result['intent_confidence']:.2f}"
            )

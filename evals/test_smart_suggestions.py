"""Evaluation tests for smart suggestions."""
import os
import pytest

# Skip if no API key (for CI environments)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
skip_no_api_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set"
)


class TestSmartSuggestions:
    """Tests for smart suggestion quality and relevance."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        from src.agent.analysis import generate_smart_suggestions
        self.generate_suggestions = generate_smart_suggestions

    @skip_no_api_key
    def test_returns_three_suggestions(self):
        """Test that exactly 3 suggestions are returned."""
        messages = [{"role": "customer", "content": "I need help with my order."}]
        sentiment = {"score": 0.0, "label": "neutral", "confidence": 0.7}

        suggestions = self.generate_suggestions(messages, sentiment)

        assert len(suggestions) == 3, f"Expected 3 suggestions, got {len(suggestions)}"

    @skip_no_api_key
    def test_suggestion_structure(self):
        """Test that suggestions have required fields."""
        messages = [{"role": "customer", "content": "My product is broken."}]
        sentiment = {"score": -0.5, "label": "negative", "confidence": 0.8}

        suggestions = self.generate_suggestions(messages, sentiment)

        for i, suggestion in enumerate(suggestions):
            assert "suggestion" in suggestion, f"Suggestion {i} missing 'suggestion' field"
            assert "confidence" in suggestion, f"Suggestion {i} missing 'confidence' field"
            assert "rationale" in suggestion, f"Suggestion {i} missing 'rationale' field"
            assert isinstance(suggestion["suggestion"], str), f"Suggestion {i} 'suggestion' not string"
            assert isinstance(suggestion["confidence"], float), f"Suggestion {i} 'confidence' not float"
            assert isinstance(suggestion["rationale"], str), f"Suggestion {i} 'rationale' not string"

    @skip_no_api_key
    def test_confidence_ordering(self):
        """Test that suggestions are ordered by confidence (highest first)."""
        messages = [{"role": "customer", "content": "Where is my refund?"}]
        sentiment = {"score": -0.3, "label": "negative", "confidence": 0.7}

        suggestions = self.generate_suggestions(messages, sentiment)

        confidences = [s["confidence"] for s in suggestions]
        assert confidences == sorted(confidences, reverse=True), \
            f"Suggestions not ordered by confidence: {confidences}"

    @skip_no_api_key
    def test_confidence_range(self):
        """Test that confidence scores are within valid range."""
        messages = [{"role": "customer", "content": "I have a question."}]
        sentiment = {"score": 0.0, "label": "neutral", "confidence": 0.6}

        suggestions = self.generate_suggestions(messages, sentiment)

        for suggestion in suggestions:
            assert 0.0 <= suggestion["confidence"] <= 1.0, \
                f"Confidence out of range: {suggestion['confidence']}"

    @skip_no_api_key
    def test_negative_sentiment_empathetic_response(self):
        """Test that suggestions are empathetic for negative sentiment."""
        messages = [{"role": "customer", "content": "I'm very frustrated with this issue!"}]
        sentiment = {"score": -0.7, "label": "negative", "confidence": 0.9}

        suggestions = self.generate_suggestions(messages, sentiment)

        # Check that at least one suggestion contains empathetic language
        empathy_words = ["understand", "sorry", "apologize", "frustrat", "help", "resolve"]
        all_suggestions_text = " ".join(s["suggestion"].lower() for s in suggestions)

        has_empathy = any(word in all_suggestions_text for word in empathy_words)
        assert has_empathy, f"No empathetic language found in suggestions: {all_suggestions_text}"

    @skip_no_api_key
    def test_context_aware_suggestions(self):
        """Test that suggestions incorporate customer context."""
        messages = [{"role": "customer", "content": "What's happening with my laptop order?"}]
        sentiment = {"score": -0.2, "label": "neutral", "confidence": 0.7}
        context = {
            "user": {"name": "John", "email": "john@example.com"},
            "orders": [{"product": "Laptop Pro 15", "amount": 1299.99, "status": "shipped"}],
            "tickets": [],
        }

        suggestions = self.generate_suggestions(messages, sentiment, context)

        # Check that suggestions reference order/product/shipping
        all_suggestions_text = " ".join(s["suggestion"].lower() for s in suggestions)
        context_words = ["order", "laptop", "ship", "delivery", "track"]

        has_context = any(word in all_suggestions_text for word in context_words)
        assert has_context, f"Suggestions don't reference context: {all_suggestions_text}"

    @skip_no_api_key
    def test_ticket_context_suggestions(self):
        """Test that suggestions consider open tickets."""
        messages = [{"role": "customer", "content": "I submitted a ticket last week about my broken headphones."}]
        sentiment = {"score": -0.3, "label": "negative", "confidence": 0.7}
        context = {
            "user": {"name": "Alice", "email": "alice@example.com"},
            "orders": [{"product": "Wireless Headphones", "amount": 79.99, "status": "delivered"}],
            "tickets": [{"subject": "Headphones not charging", "status": "open", "priority": "high"}],
        }

        suggestions = self.generate_suggestions(messages, sentiment, context)

        # Check that suggestions reference the ticket
        all_suggestions_text = " ".join(s["suggestion"].lower() for s in suggestions)
        ticket_words = ["ticket", "issue", "status", "update", "resolve", "follow"]

        has_ticket_ref = any(word in all_suggestions_text for word in ticket_words)
        assert has_ticket_ref, f"Suggestions don't reference ticket: {all_suggestions_text}"

    @skip_no_api_key
    def test_positive_sentiment_suggestions(self):
        """Test suggestions for positive sentiment conversations."""
        messages = [{"role": "customer", "content": "Thank you! That was really helpful!"}]
        sentiment = {"score": 0.8, "label": "positive", "confidence": 0.9}

        suggestions = self.generate_suggestions(messages, sentiment)

        # Check that suggestions maintain positive tone
        all_suggestions_text = " ".join(s["suggestion"].lower() for s in suggestions)
        positive_words = ["glad", "happy", "welcome", "pleasure", "help", "anything else", "great"]

        has_positive = any(word in all_suggestions_text for word in positive_words)
        assert has_positive, f"Suggestions don't maintain positive tone: {all_suggestions_text}"

    def test_empty_messages(self):
        """Test handling of empty messages."""
        sentiment = {"score": 0.0, "label": "neutral", "confidence": 0.5}

        suggestions = self.generate_suggestions([], sentiment)

        assert suggestions == [], "Expected empty list for empty messages"

    @skip_no_api_key
    def test_suggestion_length(self):
        """Test that suggestions are reasonable length (not too short or long)."""
        messages = [{"role": "customer", "content": "I need to return my order."}]
        sentiment = {"score": 0.0, "label": "neutral", "confidence": 0.7}

        suggestions = self.generate_suggestions(messages, sentiment)

        for i, suggestion in enumerate(suggestions):
            text = suggestion["suggestion"]
            # Should be at least a sentence (20 chars) but not a novel (500 chars)
            assert 20 <= len(text) <= 500, \
                f"Suggestion {i} length {len(text)} not in range [20, 500]: {text[:100]}..."

    @skip_no_api_key
    def test_suggestions_are_unique(self):
        """Test that all three suggestions are different."""
        messages = [{"role": "customer", "content": "Where is my package?"}]
        sentiment = {"score": -0.1, "label": "neutral", "confidence": 0.7}

        suggestions = self.generate_suggestions(messages, sentiment)

        texts = [s["suggestion"] for s in suggestions]
        unique_texts = set(texts)

        assert len(unique_texts) == 3, f"Duplicate suggestions found: {texts}"

    @skip_no_api_key
    def test_refund_scenario(self):
        """Test suggestions for refund request scenario."""
        messages = [
            {"role": "customer", "content": "I want to get a refund for my order."},
        ]
        sentiment = {"score": -0.2, "label": "neutral", "confidence": 0.7}
        context = {
            "user": {"name": "Bob", "email": "bob@example.com"},
            "orders": [{"product": "USB Cable", "amount": 15.99, "status": "delivered"}],
            "tickets": [],
        }

        suggestions = self.generate_suggestions(messages, sentiment, context)

        # Should mention refund process
        all_suggestions_text = " ".join(s["suggestion"].lower() for s in suggestions)
        refund_words = ["refund", "return", "process", "initiate", "policy"]

        has_refund_ref = any(word in all_suggestions_text for word in refund_words)
        assert has_refund_ref, f"Suggestions don't address refund: {all_suggestions_text}"


class TestSmartSuggestionsScenarios:
    """Test smart suggestions against predefined scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self, suggestion_scenarios):
        """Set up test environment."""
        from src.agent.analysis import generate_smart_suggestions
        self.generate_suggestions = generate_smart_suggestions
        self.scenarios = suggestion_scenarios

    @skip_no_api_key
    def test_wrong_item_scenario(self):
        """Test suggestions for wrong item received scenario."""
        scenario = self.scenarios[0]  # Wrong item scenario
        suggestions = self.generate_suggestions(
            scenario["messages"],
            scenario["sentiment"],
            scenario["context"],
        )

        all_text = " ".join(s["suggestion"].lower() for s in suggestions)

        # Should contain at least 2 expected themes
        matches = sum(1 for theme in scenario["expected_themes"] if theme in all_text)
        assert matches >= 2, \
            f"Expected at least 2 themes from {scenario['expected_themes']}, found {matches} in: {all_text}"

    @skip_no_api_key
    def test_shipping_inquiry_scenario(self):
        """Test suggestions for shipping inquiry scenario."""
        scenario = self.scenarios[1]  # Shipping inquiry
        suggestions = self.generate_suggestions(
            scenario["messages"],
            scenario["sentiment"],
            scenario["context"],
        )

        all_text = " ".join(s["suggestion"].lower() for s in suggestions)

        # Should contain at least 2 expected themes
        matches = sum(1 for theme in scenario["expected_themes"] if theme in all_text)
        assert matches >= 2, \
            f"Expected at least 2 themes from {scenario['expected_themes']}, found {matches} in: {all_text}"

    @skip_no_api_key
    def test_positive_feedback_scenario(self):
        """Test suggestions for positive feedback scenario."""
        scenario = self.scenarios[2]  # Positive feedback
        suggestions = self.generate_suggestions(
            scenario["messages"],
            scenario["sentiment"],
            scenario["context"],
        )

        all_text = " ".join(s["suggestion"].lower() for s in suggestions)

        # Should contain at least 2 expected themes
        matches = sum(1 for theme in scenario["expected_themes"] if theme in all_text)
        assert matches >= 2, \
            f"Expected at least 2 themes from {scenario['expected_themes']}, found {matches} in: {all_text}"

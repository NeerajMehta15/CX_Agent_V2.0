"""Integration tests for the full agent productivity and AI enhancement features."""
import os
import pytest

# Skip if no API key (for CI environments)
LLM_API_KEY = os.getenv("LLM_API_KEY")
skip_no_api_key = pytest.mark.skipif(
    not LLM_API_KEY,
    reason="LLM_API_KEY not set"
)


class TestSentimentToSuggestionsIntegration:
    """Test integration between sentiment analysis and smart suggestions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        from src.agent.analysis import analyze_sentiment, generate_smart_suggestions
        self.analyze_sentiment = analyze_sentiment
        self.generate_suggestions = generate_smart_suggestions

    @skip_no_api_key
    def test_negative_sentiment_affects_suggestions(self):
        """Test that negative sentiment results in empathetic suggestions."""
        messages = [
            {"role": "customer", "content": "I'm really frustrated! My order is a week late!"}
        ]

        # First, analyze sentiment
        sentiment = self.analyze_sentiment(messages)
        assert sentiment["label"] == "negative"

        # Then, generate suggestions using that sentiment
        suggestions = self.generate_suggestions(messages, sentiment)

        # Suggestions should be empathetic
        all_text = " ".join(s["suggestion"].lower() for s in suggestions)
        empathy_words = ["understand", "sorry", "apologize", "help", "resolve", "concern"]

        has_empathy = any(word in all_text for word in empathy_words)
        assert has_empathy, f"Suggestions lack empathy for negative sentiment: {all_text}"

    @skip_no_api_key
    def test_positive_sentiment_affects_suggestions(self):
        """Test that positive sentiment results in appropriate suggestions."""
        messages = [
            {"role": "customer", "content": "Thank you so much! You've been incredibly helpful!"}
        ]

        sentiment = self.analyze_sentiment(messages)
        assert sentiment["label"] == "positive"

        suggestions = self.generate_suggestions(messages, sentiment)

        all_text = " ".join(s["suggestion"].lower() for s in suggestions)
        positive_words = ["glad", "happy", "welcome", "pleasure", "great", "anything else"]

        has_positive = any(word in all_text for word in positive_words)
        assert has_positive, f"Suggestions don't match positive sentiment: {all_text}"

    @skip_no_api_key
    def test_context_improves_suggestions(self):
        """Test that customer context improves suggestion relevance."""
        messages = [
            {"role": "customer", "content": "What's the status of my headphones order?"}
        ]
        sentiment = {"score": 0.0, "label": "neutral", "confidence": 0.7}

        # Without context
        suggestions_no_context = self.generate_suggestions(messages, sentiment)

        # With context
        context = {
            "user": {"name": "Alice", "email": "alice@example.com"},
            "orders": [{"product": "Wireless Headphones", "amount": 79.99, "status": "shipped"}],
            "tickets": [],
        }
        suggestions_with_context = self.generate_suggestions(messages, sentiment, context)

        # Context-aware suggestions should mention shipping/tracking more specifically
        with_context_text = " ".join(s["suggestion"].lower() for s in suggestions_with_context)
        context_words = ["shipped", "tracking", "delivery", "headphone"]

        context_matches = sum(1 for word in context_words if word in with_context_text)
        assert context_matches >= 1, f"Context not reflected in suggestions: {with_context_text}"


class TestEndToEndWorkflow:
    """Test end-to-end workflow scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session, sample_user, sample_orders, sample_tickets):
        """Set up test environment with database fixtures."""
        self.db = db_session
        self.user = sample_user
        self.orders = sample_orders
        self.tickets = sample_tickets

    def test_customer_context_retrieval(self):
        """Test retrieving full customer context."""
        from src.database.models import Order, Ticket

        # Get user's orders
        orders = self.db.query(Order).filter(Order.user_id == self.user.id).all()
        assert len(orders) == 3

        # Get user's tickets
        tickets = self.db.query(Ticket).filter(Ticket.user_id == self.user.id).all()
        assert len(tickets) == 2

        # Construct context like the API would
        context = {
            "user": {
                "id": self.user.id,
                "name": self.user.name,
                "email": self.user.email,
                "phone": self.user.phone,
            },
            "orders": [
                {"id": o.id, "product": o.product, "amount": o.amount, "status": o.status}
                for o in orders
            ],
            "tickets": [
                {"id": t.id, "subject": t.subject, "status": t.status, "priority": t.priority}
                for t in tickets
            ],
        }

        assert context["user"]["name"] == "Test User"
        assert len(context["orders"]) == 3
        assert len(context["tickets"]) == 2

    @skip_no_api_key
    def test_full_analysis_pipeline(self):
        """Test the complete analysis pipeline: messages -> sentiment -> suggestions."""
        from src.agent.analysis import analyze_sentiment, generate_smart_suggestions

        # Simulate a conversation
        messages = [
            {"role": "customer", "content": "Hi, I ordered headphones last week."},
            {"role": "ai", "content": "I can help you with that. What's your email?"},
            {"role": "customer", "content": "It's test@example.com. The order hasn't arrived yet and I'm getting worried."},
        ]

        # Analyze sentiment
        sentiment = analyze_sentiment(messages)
        assert sentiment["label"] in ["negative", "neutral"]  # Worried customer

        # Build context from fixtures
        context = {
            "user": {"name": self.user.name, "email": self.user.email},
            "orders": [
                {"product": o.product, "amount": o.amount, "status": o.status}
                for o in self.orders
            ],
            "tickets": [
                {"subject": t.subject, "status": t.status, "priority": t.priority}
                for t in self.tickets
            ],
        }

        # Generate suggestions
        suggestions = generate_smart_suggestions(messages, sentiment, context)

        assert len(suggestions) == 3
        for s in suggestions:
            assert "suggestion" in s
            assert "confidence" in s
            assert "rationale" in s


class TestCannedResponsesIntegration:
    """Test canned responses integration."""

    def test_canned_responses_database_integration(self, db_session, sample_canned_responses):
        """Test canned responses work with the database."""
        from src.database.models import CannedResponse

        # Query all responses
        responses = db_session.query(CannedResponse).all()
        assert len(responses) == 3

        # Query by category
        greetings = db_session.query(CannedResponse).filter(
            CannedResponse.category == "greeting"
        ).all()
        assert len(greetings) == 2

        # Query by shortcut
        greet = db_session.query(CannedResponse).filter(
            CannedResponse.shortcut == "/greet"
        ).first()
        assert greet is not None
        assert "Hello" in greet.content or "help" in greet.content.lower()


class TestSchemaValidation:
    """Test schema validation across the system."""

    def test_sentiment_analysis_schema(self):
        """Test SentimentAnalysis schema validation."""
        from src.api.schemas import SentimentAnalysis

        # Valid sentiment
        sentiment = SentimentAnalysis(
            score=0.5,
            label="positive",
            confidence=0.85,
        )
        assert sentiment.score == 0.5
        assert sentiment.label == "positive"
        assert sentiment.confidence == 0.85

    def test_smart_suggestion_schema(self):
        """Test SmartSuggestion schema validation."""
        from src.api.schemas import SmartSuggestion

        suggestion = SmartSuggestion(
            suggestion="I understand your concern. Let me help.",
            confidence=0.9,
            rationale="Empathetic response for frustrated customer",
        )
        assert suggestion.confidence == 0.9

    def test_smart_suggestions_response_schema(self):
        """Test SmartSuggestionsResponse schema validation."""
        from src.api.schemas import SmartSuggestionsResponse, SmartSuggestion, SentimentAnalysis

        response = SmartSuggestionsResponse(
            suggestions=[
                SmartSuggestion(
                    suggestion="Test suggestion",
                    confidence=0.8,
                    rationale="Test rationale",
                )
            ],
            sentiment=SentimentAnalysis(
                score=-0.3,
                label="negative",
                confidence=0.7,
            ),
        )
        assert len(response.suggestions) == 1
        assert response.sentiment.label == "negative"

    def test_canned_response_schemas(self):
        """Test canned response schemas."""
        from src.api.schemas import CannedResponseCreate, CannedResponseOut

        # Create request
        create = CannedResponseCreate(
            shortcut="/test",
            title="Test",
            content="Test content",
            category="test",
        )
        assert create.shortcut == "/test"

        # Response
        out = CannedResponseOut(
            id=1,
            shortcut="/test",
            title="Test",
            content="Test content",
            category="test",
        )
        assert out.id == 1


class TestRegressionSafety:
    """Regression tests to ensure features don't break."""

    def test_existing_models_unchanged(self, db_session):
        """Test that existing User, Order, Ticket models work."""
        from src.database.models import User, Order, Ticket

        # Create user
        user = User(name="Regression Test", email="regression@test.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create order
        order = Order(user_id=user.id, product="Test", amount=10.0, status="pending")
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Create ticket
        ticket = Ticket(user_id=user.id, subject="Test", status="open", priority="low")
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)

        # Verify relationships
        assert user.orders[0].product == "Test"
        assert user.tickets[0].subject == "Test"

    def test_conversation_meta_doesnt_break_user(self, db_session, sample_user):
        """Test that ConversationMeta doesn't affect User model."""
        from src.database.models import ConversationMeta

        # Create conversation meta linked to user
        meta = ConversationMeta(
            session_id="regression-session",
            user_id=sample_user.id,
        )
        db_session.add(meta)
        db_session.commit()

        # User should still work normally
        db_session.refresh(sample_user)
        assert sample_user.name == "Test User"
        assert sample_user.email == "test@example.com"

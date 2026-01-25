"""Evaluation tests for customer context functionality."""
import pytest

# Check for fastapi availability
try:
    import fastapi
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from src.database.models import ConversationMeta, User


class TestConversationMetaModel:
    """Tests for ConversationMeta database model."""

    def test_create_conversation_meta(self, db_session, sample_user):
        """Test creating conversation metadata."""
        meta = ConversationMeta(
            session_id="test-session-123",
            user_id=sample_user.id,
            sentiment_score=0.5,
            sentiment_label="positive",
        )
        db_session.add(meta)
        db_session.commit()
        db_session.refresh(meta)

        assert meta.id is not None
        assert meta.session_id == "test-session-123"
        assert meta.user_id == sample_user.id
        assert meta.sentiment_score == 0.5
        assert meta.sentiment_label == "positive"
        assert meta.created_at is not None
        assert meta.updated_at is not None

    def test_unique_session_id_constraint(self, db_session, sample_user):
        """Test that session_id must be unique."""
        meta1 = ConversationMeta(
            session_id="unique-session",
            user_id=sample_user.id,
        )
        db_session.add(meta1)
        db_session.commit()

        meta2 = ConversationMeta(
            session_id="unique-session",  # Same session_id
            user_id=sample_user.id,
        )
        db_session.add(meta2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_nullable_user_id(self, db_session):
        """Test that user_id can be null (anonymous sessions)."""
        meta = ConversationMeta(
            session_id="anon-session",
            user_id=None,
        )
        db_session.add(meta)
        db_session.commit()
        db_session.refresh(meta)

        assert meta.user_id is None

    def test_nullable_sentiment(self, db_session):
        """Test that sentiment fields can be null."""
        meta = ConversationMeta(
            session_id="no-sentiment-session",
            sentiment_score=None,
            sentiment_label=None,
        )
        db_session.add(meta)
        db_session.commit()
        db_session.refresh(meta)

        assert meta.sentiment_score is None
        assert meta.sentiment_label is None

    def test_user_relationship(self, db_session, sample_user):
        """Test the relationship to User model."""
        meta = ConversationMeta(
            session_id="rel-test-session",
            user_id=sample_user.id,
        )
        db_session.add(meta)
        db_session.commit()
        db_session.refresh(meta)

        assert meta.user is not None
        assert meta.user.id == sample_user.id
        assert meta.user.name == sample_user.name

    def test_query_by_session_id(self, db_session, sample_user):
        """Test querying by session_id."""
        meta = ConversationMeta(
            session_id="query-test",
            user_id=sample_user.id,
        )
        db_session.add(meta)
        db_session.commit()

        found = db_session.query(ConversationMeta).filter(
            ConversationMeta.session_id == "query-test"
        ).first()

        assert found is not None
        assert found.user_id == sample_user.id


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestSessionUserMapping:
    """Tests for session to user mapping functionality."""

    def test_mapping_initialization(self):
        """Test that session_user_mapping is initialized."""
        from src.api.websocket import session_user_mapping

        assert isinstance(session_user_mapping, dict)

    def test_mapping_add_and_retrieve(self):
        """Test adding and retrieving from mapping."""
        from src.api.websocket import session_user_mapping

        # Add a mapping
        session_user_mapping["test-session-map"] = 42

        # Retrieve it
        assert session_user_mapping.get("test-session-map") == 42

        # Clean up
        del session_user_mapping["test-session-map"]

    def test_mapping_nonexistent_session(self):
        """Test retrieving nonexistent session."""
        from src.api.websocket import session_user_mapping

        result = session_user_mapping.get("nonexistent-session")
        assert result is None


class TestCustomerContextRetrieval:
    """Tests for customer context retrieval logic."""

    def test_get_user_orders(self, db_session, sample_user, sample_orders):
        """Test retrieving user orders."""
        from src.database.models import Order

        orders = db_session.query(Order).filter(
            Order.user_id == sample_user.id
        ).all()

        assert len(orders) == 3
        products = {o.product for o in orders}
        assert "Wireless Headphones" in products
        assert "Phone Case" in products

    def test_get_user_tickets(self, db_session, sample_user, sample_tickets):
        """Test retrieving user tickets."""
        from src.database.models import Ticket

        tickets = db_session.query(Ticket).filter(
            Ticket.user_id == sample_user.id
        ).all()

        assert len(tickets) == 2
        subjects = {t.subject for t in tickets}
        assert "Product not working" in subjects

    def test_get_open_tickets_only(self, db_session, sample_user, sample_tickets):
        """Test filtering for open tickets."""
        from src.database.models import Ticket

        open_tickets = db_session.query(Ticket).filter(
            Ticket.user_id == sample_user.id,
            Ticket.status.in_(["open", "in_progress"])
        ).all()

        assert len(open_tickets) == 2  # Both are open/in_progress

    def test_orders_sorted_by_date(self, db_session, sample_user, sample_orders):
        """Test that orders can be sorted by date."""
        from src.database.models import Order

        orders = db_session.query(Order).filter(
            Order.user_id == sample_user.id
        ).order_by(Order.created_at.desc()).all()

        # Verify ordering (most recent first)
        for i in range(len(orders) - 1):
            assert orders[i].created_at >= orders[i + 1].created_at


class TestCustomerContextSchema:
    """Tests for customer context schema."""

    def test_customer_context_schema(self):
        """Test CustomerContext schema structure."""
        from src.api.schemas import CustomerContext, UserProfile, OrderOut, TicketOut

        # Create sample data
        user = UserProfile(
            id=1,
            name="Test User",
            email="test@example.com",
            phone="+1-555-0100",
            created_at="2024-01-01T00:00:00",
        )
        orders = [
            OrderOut(
                id=1,
                product="Test Product",
                amount=99.99,
                status="shipped",
                created_at="2024-01-01T00:00:00",
            )
        ]
        tickets = [
            TicketOut(
                id=1,
                subject="Test Ticket",
                description="Test description",
                status="open",
                priority="high",
                assigned_to=None,
                created_at="2024-01-01T00:00:00",
            )
        ]

        context = CustomerContext(
            user=user,
            orders=orders,
            tickets=tickets,
        )

        assert context.user.name == "Test User"
        assert len(context.orders) == 1
        assert len(context.tickets) == 1

    def test_customer_context_no_user(self):
        """Test CustomerContext with no user."""
        from src.api.schemas import CustomerContext

        context = CustomerContext(
            user=None,
            orders=[],
            tickets=[],
        )

        assert context.user is None
        assert context.orders == []
        assert context.tickets == []


class TestLinkUserRequest:
    """Tests for link user request schema."""

    def test_link_user_request_schema(self):
        """Test LinkUserRequest schema."""
        from src.api.schemas import LinkUserRequest

        request = LinkUserRequest(user_id=42)
        assert request.user_id == 42

    def test_link_user_request_validation(self):
        """Test LinkUserRequest validation."""
        from src.api.schemas import LinkUserRequest
        from pydantic import ValidationError

        # Valid request
        request = LinkUserRequest(user_id=1)
        assert request.user_id == 1

        # Invalid request (missing user_id)
        with pytest.raises(ValidationError):
            LinkUserRequest()


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestAutoLinkOnLookup:
    """Tests for auto-linking user when lookup_user tool is called."""

    def test_auto_link_import(self):
        """Test that auto-link functionality is properly imported."""
        from src.agent.tools import execute_tool, _lookup_user
        from src.api.websocket import session_user_mapping

        assert callable(execute_tool)
        assert callable(_lookup_user)
        assert isinstance(session_user_mapping, dict)

    def test_lookup_user_signature(self):
        """Test that _lookup_user accepts session_id parameter."""
        import inspect
        from src.agent.tools import _lookup_user

        sig = inspect.signature(_lookup_user)
        params = list(sig.parameters.keys())

        assert "session_id" in params, f"session_id not in parameters: {params}"

    def test_execute_tool_signature(self):
        """Test that execute_tool accepts session_id parameter."""
        import inspect
        from src.agent.tools import execute_tool

        sig = inspect.signature(execute_tool)
        params = list(sig.parameters.keys())

        assert "session_id" in params, f"session_id not in parameters: {params}"

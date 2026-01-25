"""Pytest configuration and fixtures for evals."""
import os
import sys
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models import Base, User, Order, Ticket, CannedResponse


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a fresh database session for each test."""
    Session = sessionmaker(bind=test_engine)
    session = Session()

    # Clear all data before each test
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()

    yield session

    session.rollback()
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        name="Test User",
        email="test@example.com",
        phone="+1-555-0100",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_users(db_session):
    """Create multiple sample users for testing."""
    users = [
        User(name="Alice Johnson", email="alice@example.com", phone="+1-555-0101"),
        User(name="Bob Smith", email="bob@example.com", phone="+1-555-0102"),
        User(name="Carol Williams", email="carol@example.com", phone="+1-555-0103"),
    ]
    db_session.add_all(users)
    db_session.commit()
    for user in users:
        db_session.refresh(user)
    return users


@pytest.fixture
def sample_orders(db_session, sample_user):
    """Create sample orders for testing."""
    orders = [
        Order(user_id=sample_user.id, product="Wireless Headphones", amount=79.99, status="delivered"),
        Order(user_id=sample_user.id, product="Phone Case", amount=19.99, status="shipped"),
        Order(user_id=sample_user.id, product="USB Cable", amount=9.99, status="pending"),
    ]
    db_session.add_all(orders)
    db_session.commit()
    for order in orders:
        db_session.refresh(order)
    return orders


@pytest.fixture
def sample_tickets(db_session, sample_user):
    """Create sample tickets for testing."""
    tickets = [
        Ticket(
            user_id=sample_user.id,
            subject="Product not working",
            description="My headphones stopped working after a week.",
            status="open",
            priority="high",
        ),
        Ticket(
            user_id=sample_user.id,
            subject="Shipping delay",
            description="My order hasn't arrived yet.",
            status="in_progress",
            priority="medium",
        ),
    ]
    db_session.add_all(tickets)
    db_session.commit()
    for ticket in tickets:
        db_session.refresh(ticket)
    return tickets


@pytest.fixture
def sample_canned_responses(db_session):
    """Create sample canned responses for testing."""
    responses = [
        CannedResponse(
            shortcut="/greet",
            title="Greeting",
            content="Hello! How can I help you today?",
            category="greeting",
        ),
        CannedResponse(
            shortcut="/thanks",
            title="Thank You",
            content="Thank you for your patience!",
            category="greeting",
        ),
        CannedResponse(
            shortcut="/refund",
            title="Refund Process",
            content="I'll initiate the refund process for you.",
            category="refund",
        ),
    ]
    db_session.add_all(responses)
    db_session.commit()
    for resp in responses:
        db_session.refresh(resp)
    return responses


# Sentiment test cases
SENTIMENT_TEST_CASES = [
    # (messages, expected_label, description)
    {
        "messages": [{"role": "customer", "content": "This is terrible! I've been waiting for weeks!"}],
        "expected_label": "negative",
        "description": "Angry customer with exclamation marks",
    },
    {
        "messages": [{"role": "customer", "content": "I WANT A REFUND NOW!!!"}],
        "expected_label": "negative",
        "description": "All caps angry customer",
    },
    {
        "messages": [{"role": "customer", "content": "Thanks so much! You've been really helpful!"}],
        "expected_label": "positive",
        "description": "Happy grateful customer",
    },
    {
        "messages": [{"role": "customer", "content": "Great service, I'm very satisfied with the resolution."}],
        "expected_label": "positive",
        "description": "Satisfied customer",
    },
    {
        "messages": [{"role": "customer", "content": "Can you check the status of my order?"}],
        "expected_label": "neutral",
        "description": "Simple inquiry",
    },
    {
        "messages": [{"role": "customer", "content": "I'd like to know about return policies."}],
        "expected_label": "neutral",
        "description": "Information request",
    },
    {
        "messages": [
            {"role": "customer", "content": "This is frustrating."},
            {"role": "ai", "content": "I understand. Let me help."},
            {"role": "customer", "content": "Thank you, that's much better now!"},
        ],
        "expected_label": "positive",
        "description": "Sentiment changed from negative to positive",
    },
    {
        "messages": [
            {"role": "customer", "content": "Hi, I need help with my order."},
            {"role": "ai", "content": "Sure, what's the issue?"},
            {"role": "customer", "content": "It's been 3 weeks and nothing! This is unacceptable!"},
        ],
        "expected_label": "negative",
        "description": "Sentiment degraded during conversation",
    },
]


@pytest.fixture
def sentiment_test_cases():
    """Return sentiment test cases."""
    return SENTIMENT_TEST_CASES


# Smart suggestions test scenarios
SUGGESTION_SCENARIOS = [
    {
        "messages": [
            {"role": "customer", "content": "I ordered a laptop but received a tablet instead."},
        ],
        "sentiment": {"score": -0.6, "label": "negative", "confidence": 0.8},
        "context": {
            "user": {"name": "John Doe", "email": "john@example.com"},
            "orders": [{"product": "Laptop", "amount": 999.99, "status": "delivered"}],
            "tickets": [],
        },
        "expected_themes": ["apologize", "wrong item", "replacement", "return"],
        "description": "Wrong item received - should suggest apology and resolution",
    },
    {
        "messages": [
            {"role": "customer", "content": "When will my order arrive?"},
        ],
        "sentiment": {"score": 0.0, "label": "neutral", "confidence": 0.7},
        "context": {
            "user": {"name": "Jane Doe", "email": "jane@example.com"},
            "orders": [{"product": "Headphones", "amount": 79.99, "status": "shipped"}],
            "tickets": [],
        },
        "expected_themes": ["shipping", "tracking", "delivery", "status"],
        "description": "Shipping inquiry - should provide tracking/status info",
    },
    {
        "messages": [
            {"role": "customer", "content": "Thank you so much for your help!"},
        ],
        "sentiment": {"score": 0.8, "label": "positive", "confidence": 0.9},
        "context": None,
        "expected_themes": ["welcome", "glad", "help", "anything else"],
        "description": "Positive feedback - should acknowledge and offer further help",
    },
]


@pytest.fixture
def suggestion_scenarios():
    """Return smart suggestion test scenarios."""
    return SUGGESTION_SCENARIOS

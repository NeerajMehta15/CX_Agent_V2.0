"""Evaluation tests for canned responses API."""
import pytest
from src.database.models import CannedResponse


class TestCannedResponsesModel:
    """Tests for CannedResponse database model."""

    def test_create_canned_response(self, db_session):
        """Test creating a canned response."""
        response = CannedResponse(
            shortcut="/test",
            title="Test Response",
            content="This is a test response.",
            category="test",
        )
        db_session.add(response)
        db_session.commit()
        db_session.refresh(response)

        assert response.id is not None
        assert response.shortcut == "/test"
        assert response.title == "Test Response"
        assert response.content == "This is a test response."
        assert response.category == "test"
        assert response.created_at is not None

    def test_unique_shortcut_constraint(self, db_session):
        """Test that shortcut must be unique."""
        response1 = CannedResponse(
            shortcut="/unique",
            title="First",
            content="First response",
        )
        db_session.add(response1)
        db_session.commit()

        response2 = CannedResponse(
            shortcut="/unique",  # Same shortcut
            title="Second",
            content="Second response",
        )
        db_session.add(response2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_nullable_category(self, db_session):
        """Test that category can be null."""
        response = CannedResponse(
            shortcut="/nocategory",
            title="No Category",
            content="Response without category",
            category=None,
        )
        db_session.add(response)
        db_session.commit()
        db_session.refresh(response)

        assert response.category is None

    def test_query_by_category(self, db_session, sample_canned_responses):
        """Test querying canned responses by category."""
        greeting_responses = db_session.query(CannedResponse).filter(
            CannedResponse.category == "greeting"
        ).all()

        assert len(greeting_responses) == 2  # /greet and /thanks
        shortcuts = {r.shortcut for r in greeting_responses}
        assert shortcuts == {"/greet", "/thanks"}

    def test_query_all_responses(self, db_session, sample_canned_responses):
        """Test querying all canned responses."""
        all_responses = db_session.query(CannedResponse).all()

        assert len(all_responses) == 3

    def test_delete_canned_response(self, db_session, sample_canned_responses):
        """Test deleting a canned response."""
        response = db_session.query(CannedResponse).filter(
            CannedResponse.shortcut == "/greet"
        ).first()

        db_session.delete(response)
        db_session.commit()

        remaining = db_session.query(CannedResponse).all()
        assert len(remaining) == 2

        # Verify it's deleted
        deleted = db_session.query(CannedResponse).filter(
            CannedResponse.shortcut == "/greet"
        ).first()
        assert deleted is None


class TestCannedResponsesAPI:
    """Tests for canned responses API endpoints (functional tests)."""

    def test_list_responses_empty(self, db_session):
        """Test listing when no responses exist."""
        responses = db_session.query(CannedResponse).all()
        assert responses == []

    def test_list_responses_with_data(self, db_session, sample_canned_responses):
        """Test listing with existing responses."""
        responses = db_session.query(CannedResponse).all()
        assert len(responses) == 3

    def test_filter_by_category(self, db_session, sample_canned_responses):
        """Test filtering by category."""
        refund_responses = db_session.query(CannedResponse).filter(
            CannedResponse.category == "refund"
        ).all()

        assert len(refund_responses) == 1
        assert refund_responses[0].shortcut == "/refund"

    def test_filter_nonexistent_category(self, db_session, sample_canned_responses):
        """Test filtering by nonexistent category."""
        responses = db_session.query(CannedResponse).filter(
            CannedResponse.category == "nonexistent"
        ).all()

        assert responses == []


class TestCannedResponsesContent:
    """Tests for canned response content quality."""

    def test_greeting_content(self, sample_canned_responses):
        """Test that greeting responses have appropriate content."""
        greet = next(r for r in sample_canned_responses if r.shortcut == "/greet")

        # Should contain a greeting
        assert any(word in greet.content.lower() for word in ["hello", "hi", "help"])

    def test_refund_content(self, sample_canned_responses):
        """Test that refund responses have appropriate content."""
        refund = next(r for r in sample_canned_responses if r.shortcut == "/refund")

        # Should mention refund
        assert "refund" in refund.content.lower()

    def test_shortcut_format(self, sample_canned_responses):
        """Test that shortcuts follow expected format."""
        for response in sample_canned_responses:
            assert response.shortcut.startswith("/"), \
                f"Shortcut should start with /: {response.shortcut}"
            assert len(response.shortcut) > 1, \
                f"Shortcut too short: {response.shortcut}"
            assert " " not in response.shortcut, \
                f"Shortcut should not contain spaces: {response.shortcut}"

    def test_content_not_empty(self, sample_canned_responses):
        """Test that content is not empty."""
        for response in sample_canned_responses:
            assert len(response.content.strip()) > 0, \
                f"Content is empty for {response.shortcut}"

    def test_title_not_empty(self, sample_canned_responses):
        """Test that title is not empty."""
        for response in sample_canned_responses:
            assert len(response.title.strip()) > 0, \
                f"Title is empty for {response.shortcut}"


class TestCannedResponsesSeeding:
    """Tests for the seeded canned responses."""

    def test_seed_data_structure(self):
        """Test that seed data imports have correct structure."""
        from src.database.seed import seed_data

        # Just verify the function is importable and callable
        assert callable(seed_data)

    def test_expected_seed_categories(self, db_session, sample_canned_responses):
        """Test expected categories in seed data."""
        categories = {r.category for r in sample_canned_responses if r.category}

        expected = {"greeting", "refund"}
        assert categories == expected, f"Expected categories {expected}, got {categories}"

"""Tests for RAG Knowledge Base functionality."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Skip tests if OpenAI API key is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)


class TestKnowledgeBaseClass:
    """Tests for the KnowledgeBase class."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB persistence."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def knowledge_base(self, temp_persist_dir):
        """Create a KnowledgeBase instance with temporary storage."""
        from src.agent.knowledge_base import KnowledgeBase
        return KnowledgeBase(
            persist_directory=temp_persist_dir,
            collection_name="test_collection"
        )

    def test_initialization(self, knowledge_base):
        """Test KnowledgeBase initializes correctly."""
        assert knowledge_base is not None
        assert knowledge_base.embeddings is not None
        assert knowledge_base.vector_store is not None
        assert knowledge_base.text_splitter is not None

    def test_add_document(self, knowledge_base):
        """Test adding a document to the knowledge base."""
        content = "This is a test document about refund policies. Refunds are processed within 5-7 business days."
        doc_name = "test_doc.md"

        chunks = knowledge_base.add_document(content, doc_name)

        assert chunks >= 1
        stats = knowledge_base.get_stats()
        assert stats["document_count"] >= 1

    def test_search_returns_relevant_results(self, knowledge_base):
        """Test that search returns relevant results."""
        # Add a document about refunds
        refund_content = """
        # Refund Policy
        We offer a 30-day refund policy for defective items.
        Refunds are processed within 5-7 business days.
        Contact support to initiate a refund request.
        """
        knowledge_base.add_document(refund_content, "refund_policy.md")

        # Add a document about shipping
        shipping_content = """
        # Shipping Information
        Standard shipping takes 5-7 business days.
        Express shipping takes 2-3 business days.
        International shipping takes 10-14 days.
        """
        knowledge_base.add_document(shipping_content, "shipping_info.md")

        # Search for refund-related content
        results = knowledge_base.search("How do I get a refund?", k=3)

        assert len(results) >= 1
        assert any("refund" in r["content"].lower() for r in results)
        # First result should be from refund policy
        assert results[0]["source"] == "refund_policy.md"

    def test_get_stats(self, knowledge_base):
        """Test get_stats returns correct structure."""
        stats = knowledge_base.get_stats()

        assert "status" in stats
        assert "document_count" in stats
        assert "persist_directory" in stats
        assert "collection_name" in stats
        assert stats["collection_name"] == "test_collection"

    def test_delete_collection(self, knowledge_base):
        """Test deleting all documents from collection."""
        # Add a document
        knowledge_base.add_document("Test content", "test.md")
        assert knowledge_base.get_stats()["document_count"] >= 1

        # Delete collection
        result = knowledge_base.delete_collection()

        assert result["status"] == "success"
        assert knowledge_base.get_stats()["document_count"] == 0

    def test_search_empty_results(self, knowledge_base):
        """Test search returns empty list when no documents match."""
        results = knowledge_base.search("xyzzy nonexistent query", k=3)
        # Should return empty list or results with low scores
        assert isinstance(results, list)


class TestKnowledgeSearchTool:
    """Tests for the knowledge_search tool integration."""

    def test_tool_exists_in_definitions(self):
        """Test that knowledge_search tool exists in TOOL_DEFINITIONS."""
        from src.agent.tools import TOOL_DEFINITIONS

        tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        assert "knowledge_search" in tool_names

    def test_tool_definition_structure(self):
        """Test that knowledge_search tool has correct structure."""
        from src.agent.tools import TOOL_DEFINITIONS

        kb_tool = None
        for tool in TOOL_DEFINITIONS:
            if tool["function"]["name"] == "knowledge_search":
                kb_tool = tool
                break

        assert kb_tool is not None
        assert kb_tool["type"] == "function"
        assert "description" in kb_tool["function"]
        assert "parameters" in kb_tool["function"]

        params = kb_tool["function"]["parameters"]
        assert "query" in params["properties"]
        assert "num_results" in params["properties"]
        assert "query" in params["required"]


class TestKnowledgeBaseAPI:
    """Tests for knowledge base API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    def test_stats_endpoint(self, client):
        """Test GET /api/knowledge/stats returns correct structure."""
        response = client.get("/api/knowledge/stats")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "document_count" in data
        assert "persist_directory" in data
        assert "collection_name" in data

    def test_search_endpoint(self, client):
        """Test POST /api/knowledge/search endpoint."""
        response = client.post(
            "/api/knowledge/search",
            json={"query": "refund policy", "num_results": 3}
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "refund policy"
        assert isinstance(data["results"], list)

    def test_upload_endpoint(self, client):
        """Test POST /api/knowledge/upload endpoint."""
        response = client.post(
            "/api/knowledge/upload",
            json={
                "content": "This is test content for uploading.",
                "doc_name": "test_upload.md"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["doc_name"] == "test_upload.md"
        assert "chunks_added" in data

    def test_upload_endpoint_empty_content(self, client):
        """Test upload endpoint rejects empty content."""
        response = client.post(
            "/api/knowledge/upload",
            json={"content": "", "doc_name": "empty.md"}
        )

        assert response.status_code == 400

    def test_upload_endpoint_empty_name(self, client):
        """Test upload endpoint rejects empty document name."""
        response = client.post(
            "/api/knowledge/upload",
            json={"content": "Some content", "doc_name": ""}
        )

        assert response.status_code == 400


class TestKnowledgeDocuments:
    """Tests for the knowledge document files."""

    def test_knowledge_docs_exist(self):
        """Test that knowledge document files exist."""
        docs_dir = Path("knowledge_docs")
        assert docs_dir.exists(), "knowledge_docs directory should exist"

        expected_files = [
            "refund_policy.md",
            "shipping_info.md",
            "product_troubleshooting.md",
            "company_policies.md",
        ]

        for filename in expected_files:
            filepath = docs_dir / filename
            assert filepath.exists(), f"{filename} should exist in knowledge_docs"

    def test_refund_policy_content(self):
        """Test refund policy document has required content."""
        content = Path("knowledge_docs/refund_policy.md").read_text()

        assert "30" in content.lower() or "thirty" in content.lower()  # 30-day policy
        assert "14" in content.lower() or "fourteen" in content.lower()  # 14-day buyer's remorse
        assert "warranty" in content.lower()

    def test_shipping_info_content(self):
        """Test shipping info document has required content."""
        content = Path("knowledge_docs/shipping_info.md").read_text()

        assert "5-7" in content or "5 to 7" in content.lower()  # Standard shipping days
        assert "tracking" in content.lower()
        assert "international" in content.lower()

    def test_troubleshooting_content(self):
        """Test troubleshooting document has required content."""
        content = Path("knowledge_docs/product_troubleshooting.md").read_text()

        assert "headphone" in content.lower()
        assert "charging" in content.lower() or "charge" in content.lower()
        assert "reset" in content.lower()
        assert "bluetooth" in content.lower() or "connection" in content.lower()

    def test_company_policies_content(self):
        """Test company policies document has required content."""
        content = Path("knowledge_docs/company_policies.md").read_text()

        assert "9" in content and "5" in content  # Hours 9am-5pm
        assert "monday" in content.lower() or "mon" in content.lower()
        assert "friday" in content.lower() or "fri" in content.lower()
        assert "contact" in content.lower() or "email" in content.lower() or "phone" in content.lower()

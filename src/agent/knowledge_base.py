"""RAG Knowledge Base using ChromaDB for document storage and retrieval."""

import os
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Singleton instance
_knowledge_base_instance = None


class KnowledgeBase:
    """ChromaDB-backed knowledge base for RAG."""

    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "cx_knowledge"):
        """Initialize the knowledge base with ChromaDB.

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings()

        # Initialize or load vector store
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )

        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
        )

        logger.info(f"Knowledge base initialized with persist_directory={persist_directory}")

    def add_document(self, content: str, doc_name: str) -> int:
        """Add a document to the knowledge base.

        Args:
            content: The document content
            doc_name: Name/identifier for the document

        Returns:
            Number of chunks added
        """
        # Split content into chunks
        chunks = self.text_splitter.split_text(content)

        # Create metadata for each chunk
        metadatas = [{"source": doc_name, "chunk": i} for i in range(len(chunks))]

        # Add to vector store
        self.vector_store.add_texts(texts=chunks, metadatas=metadatas)

        logger.info(f"Added document '{doc_name}' with {len(chunks)} chunks")
        return len(chunks)

    def index_documents(self, docs_dir: str) -> dict:
        """Index all markdown files from a directory.

        Args:
            docs_dir: Path to directory containing .md files

        Returns:
            Dict with indexing results
        """
        docs_path = Path(docs_dir)
        if not docs_path.exists():
            logger.warning(f"Documents directory not found: {docs_dir}")
            return {"status": "error", "message": f"Directory not found: {docs_dir}"}

        indexed = []
        total_chunks = 0

        for md_file in docs_path.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                chunks = self.add_document(content, md_file.name)
                indexed.append({"file": md_file.name, "chunks": chunks})
                total_chunks += chunks
                logger.info(f"Indexed {md_file.name}: {chunks} chunks")
            except Exception as e:
                logger.error(f"Error indexing {md_file.name}: {e}")
                indexed.append({"file": md_file.name, "error": str(e)})

        return {
            "status": "success",
            "files_indexed": len([f for f in indexed if "error" not in f]),
            "total_chunks": total_chunks,
            "details": indexed,
        }

    def search(self, query: str, k: int = 3) -> list[dict]:
        """Search the knowledge base.

        Args:
            query: Search query
            k: Number of results to return (max 5)

        Returns:
            List of search results with content, source, and score
        """
        k = min(k, 5)  # Cap at 5 results

        try:
            results = self.vector_store.similarity_search_with_relevance_scores(query, k=k)

            return [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "score": round(score, 4),
                }
                for doc, score in results
            ]
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def get_stats(self) -> dict:
        """Get knowledge base statistics.

        Returns:
            Dict with status, document_count, persist_directory, collection_name
        """
        try:
            # Get collection count
            collection = self.vector_store._collection
            count = collection.count()

            return {
                "status": "healthy",
                "document_count": count,
                "persist_directory": self.persist_directory,
                "collection_name": self.collection_name,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "status": "error",
                "document_count": 0,
                "persist_directory": self.persist_directory,
                "collection_name": self.collection_name,
                "error": str(e),
            }

    def delete_collection(self) -> dict:
        """Delete all documents from the knowledge base.

        Returns:
            Dict with deletion result
        """
        try:
            # Delete and recreate collection
            self.vector_store.delete_collection()

            # Reinitialize vector store
            self.vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory,
            )

            logger.info("Knowledge base cleared")
            return {"status": "success", "message": "All documents deleted"}
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return {"status": "error", "message": str(e)}


def get_knowledge_base() -> KnowledgeBase:
    """Get singleton instance of KnowledgeBase.

    Returns:
        KnowledgeBase instance
    """
    global _knowledge_base_instance

    if _knowledge_base_instance is None:
        _knowledge_base_instance = KnowledgeBase()

    return _knowledge_base_instance

"""Knowledge Base Admin Dashboard for managing RAG documents."""

import requests
import streamlit as st

API_URL = "http://localhost:8000/api"

st.set_page_config(
    page_title="Knowledge Base Admin",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Knowledge Base Admin")

# Session state initialization
if "kb_stats" not in st.session_state:
    st.session_state.kb_stats = None
if "search_results" not in st.session_state:
    st.session_state.search_results = None


def fetch_stats():
    """Fetch knowledge base statistics."""
    try:
        response = requests.get(f"{API_URL}/knowledge/stats", timeout=10)
        if response.status_code == 200:
            st.session_state.kb_stats = response.json()
        else:
            st.error(f"Failed to fetch stats: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure the server is running.")
    except Exception as e:
        st.error(f"Error: {e}")


def search_kb(query: str, num_results: int):
    """Search the knowledge base."""
    try:
        response = requests.post(
            f"{API_URL}/knowledge/search",
            json={"query": query, "num_results": num_results},
            timeout=30,
        )
        if response.status_code == 200:
            st.session_state.search_results = response.json()
        else:
            st.error(f"Search failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure the server is running.")
    except Exception as e:
        st.error(f"Error: {e}")


def upload_document(content: str, doc_name: str):
    """Upload a document to the knowledge base."""
    try:
        response = requests.post(
            f"{API_URL}/knowledge/upload",
            json={"content": content, "doc_name": doc_name},
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Upload failed: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure the server is running.")
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def delete_all_documents():
    """Delete all documents from the knowledge base."""
    try:
        response = requests.delete(f"{API_URL}/knowledge", timeout=10)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Delete failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure the server is running.")
        return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False


# Sidebar - Stats and Controls
with st.sidebar:
    st.header("📊 Statistics")

    if st.button("🔄 Refresh Stats"):
        fetch_stats()

    # Fetch stats on first load
    if st.session_state.kb_stats is None:
        fetch_stats()

    if st.session_state.kb_stats:
        stats = st.session_state.kb_stats
        status_color = "🟢" if stats["status"] == "healthy" else "🔴"
        st.metric("Status", f"{status_color} {stats['status'].title()}")
        st.metric("Document Chunks", stats["document_count"])
        st.caption(f"Collection: {stats['collection_name']}")
        st.caption(f"Storage: {stats['persist_directory']}")

    st.divider()

    # Danger Zone
    st.header("⚠️ Danger Zone")
    if st.button("🗑️ Delete All Documents", type="secondary"):
        st.session_state.confirm_delete = True

    if st.session_state.get("confirm_delete"):
        st.warning("Are you sure? This cannot be undone!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, Delete", type="primary"):
                if delete_all_documents():
                    st.success("All documents deleted!")
                    st.session_state.kb_stats = None
                    st.session_state.confirm_delete = False
                    st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.confirm_delete = False
                st.rerun()

# Main content - Tabs
tab1, tab2, tab3 = st.tabs(["🔍 Search", "📤 Upload", "📄 Documents"])

# Tab 1: Search
with tab1:
    st.subheader("Search Knowledge Base")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Search query", placeholder="e.g., refund policy, shipping times...")
    with col2:
        num_results = st.selectbox("Results", [1, 2, 3, 4, 5], index=2)

    if st.button("🔍 Search", type="primary"):
        if query.strip():
            search_kb(query, num_results)
        else:
            st.warning("Please enter a search query.")

    if st.session_state.search_results:
        results = st.session_state.search_results
        st.markdown(f"**Query:** {results['query']}")
        st.markdown(f"**Found:** {len(results['results'])} results")

        for i, result in enumerate(results["results"], 1):
            with st.expander(f"Result {i} - {result['source']} (Score: {result['score']:.4f})", expanded=i == 1):
                st.markdown(result["content"])
                st.caption(f"Source: {result['source']} | Relevance Score: {result['score']:.4f}")

# Tab 2: Upload
with tab2:
    st.subheader("Upload New Document")

    upload_method = st.radio("Upload method", ["File Upload", "Manual Entry"], horizontal=True)

    if upload_method == "File Upload":
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["md", "txt"],
            help="Upload a Markdown (.md) or Text (.txt) file",
        )

        if uploaded_file:
            content = uploaded_file.read().decode("utf-8")
            doc_name = uploaded_file.name

            st.text_area("Preview", content, height=200, disabled=True)

            if st.button("📤 Upload Document", type="primary"):
                result = upload_document(content, doc_name)
                if result:
                    st.success(f"Successfully uploaded '{doc_name}' with {result['chunks_added']} chunks!")
                    st.session_state.kb_stats = None  # Refresh stats
    else:
        doc_name = st.text_input("Document name", placeholder="e.g., faq.md")
        content = st.text_area(
            "Document content",
            height=300,
            placeholder="Enter your document content here...",
        )

        if st.button("📤 Upload Document", type="primary"):
            if doc_name.strip() and content.strip():
                result = upload_document(content, doc_name)
                if result:
                    st.success(f"Successfully uploaded '{doc_name}' with {result['chunks_added']} chunks!")
                    st.session_state.kb_stats = None  # Refresh stats
            else:
                st.warning("Please provide both document name and content.")

# Tab 3: Documents
with tab3:
    st.subheader("Indexed Documents")

    # Expected documents
    expected_docs = [
        {"name": "refund_policy.md", "description": "30-day defects, 14-day buyer's remorse, warranty info"},
        {"name": "shipping_info.md", "description": "Delivery times, tracking, international shipping"},
        {"name": "product_troubleshooting.md", "description": "Headphones, laptop stand, USB-C hub troubleshooting"},
        {"name": "company_policies.md", "description": "Contact info, hours, account policies"},
    ]

    st.markdown("### Expected Knowledge Documents")
    for doc in expected_docs:
        st.markdown(f"- **{doc['name']}**: {doc['description']}")

    st.divider()

    # Stats summary
    if st.session_state.kb_stats:
        stats = st.session_state.kb_stats
        st.markdown("### Current Status")
        st.info(f"Total document chunks indexed: **{stats['document_count']}**")

        if stats["document_count"] == 0:
            st.warning(
                "No documents indexed yet. Run `python -m src.database.seed` to index the knowledge documents, "
                "or upload documents manually using the Upload tab."
            )
    else:
        st.info("Click 'Refresh Stats' in the sidebar to see current status.")

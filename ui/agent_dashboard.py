import time

import requests
import streamlit as st

API_URL = "http://localhost:8000/api"

st.set_page_config(page_title="Agent Dashboard", page_icon="🎧", layout="wide")

# Session state initialization
if "agent_name" not in st.session_state:
    st.session_state.agent_name = ""
if "active_session" not in st.session_state:
    st.session_state.active_session = None
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
if "message_input" not in st.session_state:
    st.session_state.message_input = ""
if "canned_category_filter" not in st.session_state:
    st.session_state.canned_category_filter = "All"

# Auto-refresh every 2 seconds
REFRESH_INTERVAL = 2
if time.time() - st.session_state.last_refresh > REFRESH_INTERVAL:
    st.session_state.last_refresh = time.time()
    st.rerun()


# ==================== API Functions ====================


def fetch_handoffs():
    """Fetch pending handoff requests from API."""
    try:
        response = requests.get(f"{API_URL}/handoffs", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return []


def accept_handoff(session_id: str, agent_name: str):
    """Accept a handoff request."""
    try:
        response = requests.post(
            f"{API_URL}/handoffs/{session_id}/accept",
            params={"agent_name": agent_name},
            timeout=5,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def fetch_messages(session_id: str):
    """Fetch conversation messages for a session."""
    try:
        response = requests.get(f"{API_URL}/handoffs/{session_id}/messages", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return []


def send_message(session_id: str, message: str):
    """Send a message to the customer."""
    try:
        response = requests.post(
            f"{API_URL}/handoffs/{session_id}/message",
            json={"message": message},
            timeout=5,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def fetch_customer_context(session_id: str):
    """Fetch customer context (profile, orders, tickets)."""
    try:
        response = requests.get(f"{API_URL}/handoffs/{session_id}/context", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return {"user": None, "orders": [], "tickets": []}


def link_user_to_session(session_id: str, user_id: int):
    """Link a user to a session."""
    try:
        response = requests.post(
            f"{API_URL}/handoffs/{session_id}/link-user",
            json={"user_id": user_id},
            timeout=5,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def fetch_sentiment(session_id: str):
    """Fetch sentiment analysis for a session."""
    try:
        response = requests.get(f"{API_URL}/handoffs/{session_id}/sentiment", timeout=30)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return {"score": 0.0, "label": "neutral", "confidence": 0.5}


def fetch_smart_suggestions(session_id: str):
    """Fetch smart suggestions for a session."""
    try:
        response = requests.get(f"{API_URL}/handoffs/{session_id}/smart-suggestions", timeout=30)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return {"suggestions": [], "sentiment": {"score": 0.0, "label": "neutral", "confidence": 0.5}}


def fetch_canned_responses(category: str | None = None):
    """Fetch canned responses, optionally filtered by category."""
    try:
        params = {}
        if category and category != "All":
            params["category"] = category
        response = requests.get(f"{API_URL}/canned-responses", params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return []


def set_message_input(text: str):
    """Set the message input text."""
    st.session_state.message_input = text


# ==================== Sidebar ====================

with st.sidebar:
    st.header("Agent Dashboard")
    st.session_state.agent_name = st.text_input(
        "Your Name",
        value=st.session_state.agent_name,
        placeholder="Enter your name",
    )

    st.divider()

    # Show active session if any
    if st.session_state.active_session:
        st.success(f"Active: {st.session_state.active_session[:8]}...")
        if st.button("End Session"):
            st.session_state.active_session = None
            st.rerun()

    st.divider()

    # Pending handoffs list
    st.subheader("Pending Handoffs")
    handoffs = fetch_handoffs()
    pending = [h for h in handoffs if not h.get("accepted_by")]

    if not pending:
        st.info("No pending handoffs")
    else:
        for handoff in pending:
            session_id = handoff["session_id"]
            reason = handoff.get("reason", "Unknown")
            timestamp = handoff.get("timestamp", "")

            # Parse timestamp for display
            time_display = ""
            if timestamp:
                try:
                    from datetime import datetime
                    ts = datetime.fromisoformat(timestamp)
                    minutes_ago = int((datetime.utcnow() - ts).total_seconds() / 60)
                    time_display = f" ({minutes_ago}m ago)" if minutes_ago > 0 else " (just now)"
                except Exception:
                    pass

            with st.container():
                st.markdown(f"**{session_id[:8]}...**{time_display}")
                st.caption(f"Reason: {reason}")
                if st.button("Accept", key=f"accept_{session_id}"):
                    if not st.session_state.agent_name:
                        st.error("Enter your name first")
                    elif accept_handoff(session_id, st.session_state.agent_name):
                        st.session_state.active_session = session_id
                        st.rerun()
                    else:
                        st.error("Failed to accept")
                st.divider()


# ==================== Main Content ====================

st.title("Agent Dashboard")

if not st.session_state.agent_name:
    st.warning("Please enter your name in the sidebar to get started.")
elif not st.session_state.active_session:
    st.info("Select a pending handoff from the sidebar to start helping a customer.")

    # Show any accepted handoffs by this agent
    my_handoffs = [h for h in handoffs if h.get("accepted_by") == st.session_state.agent_name]
    if my_handoffs:
        st.subheader("Your Active Sessions")
        for h in my_handoffs:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"Session: {h['session_id'][:8]}...")
            with col2:
                if st.button("Resume", key=f"resume_{h['session_id']}"):
                    st.session_state.active_session = h["session_id"]
                    st.rerun()
else:
    # Active chat view - 3-column layout
    session_id = st.session_state.active_session

    # Create 3-column layout: Main Chat (wider) | Context Panel
    main_col, context_col = st.columns([2, 1])

    # ==================== Main Chat Column ====================
    with main_col:
        st.subheader(f"Conversation with {session_id[:8]}...")

        # Sentiment indicator at top
        sentiment = fetch_sentiment(session_id)
        sentiment_label = sentiment.get("label", "neutral")
        sentiment_score = sentiment.get("score", 0.0)
        sentiment_confidence = sentiment.get("confidence", 0.5)

        # Color coding for sentiment
        if sentiment_label == "positive":
            sentiment_color = "green"
            sentiment_emoji = "+"
        elif sentiment_label == "negative":
            sentiment_color = "red"
            sentiment_emoji = "-"
        else:
            sentiment_color = "gray"
            sentiment_emoji = "~"

        st.markdown(
            f"**Sentiment:** :{sentiment_color}[{sentiment_emoji} {sentiment_label.upper()}] "
            f"(score: {sentiment_score:.2f}, confidence: {sentiment_confidence:.0%})"
        )

        # Messages container
        messages = fetch_messages(session_id)

        # Display conversation history
        chat_container = st.container(height=300)
        with chat_container:
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                if role == "customer":
                    with st.chat_message("user"):
                        st.markdown(content)
                elif role == "ai":
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(content)
                elif role == "agent":
                    with st.chat_message("assistant", avatar="🧑"):
                        st.markdown(content)

        st.divider()

        # Smart Suggestions Panel
        st.subheader("Smart Suggestions")
        if st.button("Get Suggestions", key="get_suggestions"):
            with st.spinner("Generating suggestions..."):
                suggestions_data = fetch_smart_suggestions(session_id)
                st.session_state.smart_suggestions = suggestions_data.get("suggestions", [])

        if "smart_suggestions" in st.session_state and st.session_state.smart_suggestions:
            for i, suggestion in enumerate(st.session_state.smart_suggestions):
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        confidence = suggestion.get("confidence", 0)
                        st.markdown(f"**{i+1}.** {suggestion.get('suggestion', '')}")
                        st.caption(f"Confidence: {confidence:.0%} | {suggestion.get('rationale', '')}")
                    with col2:
                        if st.button("Use", key=f"use_suggestion_{i}"):
                            set_message_input(suggestion.get("suggestion", ""))
                            st.rerun()

        st.divider()

        # Canned Responses Picker
        with st.expander("Canned Responses", expanded=False):
            # Category filter
            categories = ["All", "greeting", "refund", "shipping", "support"]
            selected_category = st.selectbox(
                "Filter by category",
                categories,
                index=categories.index(st.session_state.canned_category_filter),
                key="category_select",
            )
            st.session_state.canned_category_filter = selected_category

            canned_responses = fetch_canned_responses(
                None if selected_category == "All" else selected_category
            )

            if canned_responses:
                for response in canned_responses:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{response.get('shortcut', '')}** - {response.get('title', '')}")
                        st.caption(response.get("content", "")[:100] + "..." if len(response.get("content", "")) > 100 else response.get("content", ""))
                    with col2:
                        if st.button("Use", key=f"use_canned_{response.get('id')}"):
                            set_message_input(response.get("content", ""))
                            st.rerun()
            else:
                st.info("No canned responses available")

        st.divider()

        # Message input
        with st.form("message_form", clear_on_submit=True):
            message_input = st.text_area(
                "Your message",
                value=st.session_state.message_input,
                placeholder="Type your message to the customer...",
                key="message_text_area",
            )
            col1, col2 = st.columns([1, 5])
            with col1:
                send_button = st.form_submit_button("Send")

            if send_button and message_input:
                if send_message(session_id, message_input):
                    st.success("Message sent!")
                    st.session_state.message_input = ""
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Failed to send message")

    # ==================== Context Panel Column ====================
    with context_col:
        st.subheader("Customer Context")

        # Fetch customer context
        context = fetch_customer_context(session_id)
        user = context.get("user")
        orders = context.get("orders", [])
        tickets = context.get("tickets", [])

        # User Profile Section
        st.markdown("#### User Profile")
        if user:
            st.markdown(f"**Name:** {user.get('name', 'Unknown')}")
            st.markdown(f"**Email:** {user.get('email', 'Unknown')}")
            if user.get("phone"):
                st.markdown(f"**Phone:** {user.get('phone')}")
        else:
            st.info("No user linked to this session")

            # Manual user linking
            with st.expander("Link User Manually"):
                user_id_input = st.number_input("User ID", min_value=1, step=1, key="link_user_id")
                if st.button("Link User", key="link_user_btn"):
                    if link_user_to_session(session_id, int(user_id_input)):
                        st.success("User linked!")
                        st.rerun()
                    else:
                        st.error("Failed to link user")

        st.divider()

        # Recent Orders Section
        st.markdown("#### Recent Orders")
        if orders:
            for order in orders[:5]:  # Show up to 5 orders
                status = order.get("status", "unknown")
                status_colors = {
                    "pending": "🟡",
                    "shipped": "🔵",
                    "delivered": "🟢",
                    "refunded": "🔴",
                }
                status_icon = status_colors.get(status, "⚪")
                st.markdown(
                    f"{status_icon} **{order.get('product', 'Unknown')}**\n"
                    f"${order.get('amount', 0):.2f} - {status}"
                )
        else:
            st.info("No orders found")

        st.divider()

        # Open Tickets Section
        st.markdown("#### Open Tickets")
        open_tickets = [t for t in tickets if t.get("status") in ("open", "in_progress")]
        if open_tickets:
            for ticket in open_tickets[:5]:  # Show up to 5 tickets
                priority = ticket.get("priority", "medium")
                priority_colors = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴",
                }
                priority_icon = priority_colors.get(priority, "⚪")
                st.markdown(
                    f"{priority_icon} **#{ticket.get('id', '?')}:** {ticket.get('subject', 'Unknown')}\n"
                    f"Status: {ticket.get('status', 'unknown')} | Priority: {priority}"
                )
        else:
            st.info("No open tickets")

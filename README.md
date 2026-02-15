# CX Agent V2.0

An AI-powered Customer Experience Agent with intelligent handoff, real-time sentiment analysis, and comprehensive agent productivity tools. Built with FastAPI, OpenAI GPT-4, and Streamlit.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Agent Dashboard](#agent-dashboard)
- [AI Features](#ai-features)
- [Evaluation Suite](#evaluation-suite)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Core AI Agent
- **GPT-4 Function Calling** — Real-time database lookups with structured tool use
- **Conversation Memory** — Context-aware responses across multi-turn conversations
- **Smart Handoff** — Automatic escalation based on repeated intent, data gaps, or hallucination risk
- **Configurable Tone** — Switch between professional, friendly, and playful personalities
- **RAG Knowledge Base** — ChromaDB-backed retrieval for policies, troubleshooting, and company info

### Persistent Customer Memory
- **Session Insights** — Automated per-session analytics (sentiment drift, resolution status, tool usage) computed at session close
- **Customer Profiles** — Aggregated cross-session profiles with loyalty tier, risk flags, topic frequency, and weighted sentiment
- **Dynamic Tone Selection** — Automatic tone inference from customer history and real-time message signals (no LLM call)
- **Profile-Aware Prompts** — Customer history injected into the system prompt so the agent personalizes from the first message
- **Risk Detection** — Flags at-risk customers based on escalation rate, sentiment trends, and unresolved session streaks

### Agent Productivity Tools
- **Customer Context Panel** — View user profile, order history, and support tickets at a glance
- **Canned Responses** — Pre-built templates with shortcuts (e.g., `/greet`, `/refund`) and category filtering
- **Session-User Linking** — Automatic association when customer identity is discovered

### AI Enhancements
- **Real-time Sentiment Analysis** — Detect customer mood (positive/neutral/negative) with confidence scores
- **Smart Suggestions** — 3 ranked, context-aware response suggestions with rationale
- **Sentiment-Aware Responses** — Suggestions adapt based on customer emotional state

### Infrastructure
- **WebSocket Support** — Real-time bidirectional communication for live chat
- **Role-Based Permissions** — Granular read/write access control per role
- **Query Sanitization** — Input validation to prevent injection attacks
- **Comprehensive Eval Suite** — 90+ tests for quality assurance over time

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CUSTOMER INTERFACE                              │
│                         (Streamlit Chat / WebSocket)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI SERVER                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  REST API   │  │  WebSocket  │  │   Handoff   │  │   AI Analysis       │ │
│  │  /api/*     │  │  /ws/*      │  │   Manager   │  │   (Sentiment/Sugg.) │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                CX AGENT CORE                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Agent     │  │   Tools     │  │   Memory    │  │   Handoff           │ │
│  │   Loop      │  │   Executor  │  │   Manager   │  │   Detection         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │   Profile Engine: session close → insights → profile aggregation       │ │
│  │   Dynamic tone inference · Risk detection · Profile-aware prompts      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                              ▼
┌───────────────────────────────┐    ┌───────────────────────────────────────┐
│         OPENAI API            │    │              DATABASE                  │
│  ┌─────────────────────────┐  │    │  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │  GPT-4 + Function Call  │  │    │  │  Users  │ │ Orders  │ │ Tickets │  │
│  │  GPT-4o-mini (Analysis) │  │    │  └─────────┘ └─────────┘ └─────────┘  │
│  └─────────────────────────┘  │    │  ┌───────────────┐ ┌───────────────┐  │
└───────────────────────────────┘    │  │CannedResponses│ │ConversationMeta│ │
                                     │  └───────────────┘ └───────────────┘  │
                                     │  ┌────────────────┐ ┌────────────────┐│
                                     │  │SessionInsights │ │CustomerProfiles││
                                     │  └────────────────┘ └────────────────┘│
                                     └───────────────────────────────────────┘
```

### Request Flow

1. **Customer Message** → Arrives via REST (`POST /api/chat`) or WebSocket (`/ws/customer/{session_id}`)
2. **Profile Load** → Loads customer profile (single DB query) and infers tone dynamically
3. **Handoff Check** → Evaluates if escalation is needed (repeated intent, data gap)
4. **Agent Loop** → GPT-4 processes message with profile-aware system prompt (up to 5 iterations)
5. **Tool Execution** → Permission-checked database operations; first tool call sets primary intent
6. **Response** → AI response returned; if handoff triggered, broadcasts to agent pool
7. **Session Close** → On disconnect or explicit close, computes sentiment drift, resolution status, and updates customer profile
8. **Agent Dashboard** → Human agents can accept handoffs, view context, use smart suggestions

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **LLM** | OpenAI GPT-4 | Main conversation + function calling |
| **Analysis** | OpenAI GPT-4o-mini | Fast sentiment & suggestion generation |
| **Backend** | FastAPI | REST API + WebSocket server |
| **Database** | SQLite + SQLAlchemy | Data persistence with ORM |
| **Frontend** | Streamlit | Customer chat + Agent dashboard |
| **Testing** | Pytest | Evaluation suite |
| **Config** | YAML + dotenv | System prompts + environment |

---

## Project Structure

```
CX_Agent/
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── agent/
│   │   ├── cx_agent.py         # Main agent loop with GPT-4
│   │   ├── tools.py            # Function calling tool definitions
│   │   ├── memory.py           # Conversation memory management
│   │   ├── handoff.py          # Handoff detection logic
│   │   ├── analysis.py         # Sentiment & smart suggestions
│   │   ├── profile.py          # Session close, profile aggregation, tone inference
│   │   └── knowledge_base.py   # RAG knowledge base with ChromaDB
│   ├── api/
│   │   ├── routes.py           # REST API endpoints
│   │   ├── websocket.py        # WebSocket handlers
│   │   └── schemas.py          # Pydantic request/response models
│   ├── config/
│   │   ├── settings.py         # Environment configuration
│   │   ├── prompts.py          # System prompt loader
│   │   └── permissions.py      # Role-based access control
│   ├── database/
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── connection.py       # Database session management
│   │   ├── seed.py             # Demo data seeding
│   │   └── middleware.py       # Query sanitization
│   └── utils/
│       └── logger.py           # Logging configuration
├── ui/
│   ├── app.py                  # Customer chat interface
│   ├── agent_dashboard.py      # Agent productivity dashboard
│   └── knowledge_admin.py      # Knowledge base admin UI
├── knowledge_docs/             # RAG source documents
│   ├── refund_policy.md
│   ├── shipping_info.md
│   ├── product_troubleshooting.md
│   └── company_policies.md
├── chroma_db/                  # ChromaDB vector store (auto-created)
├── config/
│   └── system_prompts.yaml     # Tone configurations & guardrails
├── evals/                      # Evaluation test suite
│   ├── conftest.py             # Pytest fixtures
│   ├── datasets/               # Test datasets
│   ├── test_sentiment.py       # Sentiment analysis evals
│   ├── test_smart_suggestions.py
│   ├── test_canned_responses.py
│   ├── test_customer_context.py
│   ├── test_integration.py
│   └── run_evals.py            # Eval runner script
├── requirements.txt            # Production dependencies
├── requirements-test.txt       # Test dependencies
├── pytest.ini                  # Pytest configuration
├── .env.example                # Environment template
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10 or higher
- OpenAI API key with GPT-4 access

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NeerajMehta15/CX_Agent_V2.0.git
   cd CX_Agent_V2.0
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt

   # For running tests
   pip install -r requirements-test.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your configuration:
   ```env
   OPENAI_API_KEY=sk-your-api-key-here
   DATABASE_URL=sqlite:///cx_agent.db
   DEFAULT_TONE=friendly
   LOG_LEVEL=INFO
   ```

5. **Initialize database** (automatic on first run, or manually):
   ```bash
   python -m src.database.seed
   ```

---

## Usage

### Start the API Server

```bash
uvicorn src.main:app --reload
```

- API available at: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Database auto-created and seeded on first run

### Start the Customer Chat UI

```bash
streamlit run ui/app.py
```

Opens at `http://localhost:8501`

### Start the Agent Dashboard

```bash
streamlit run ui/agent_dashboard.py --server.port 8502
```

Opens at `http://localhost:8502`

### Start the Knowledge Base Admin

```bash
streamlit run ui/knowledge_admin.py --server.port 8503
```

Opens at `http://localhost:8503`

### Quick Test

```bash
# Send a chat message via API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the status of my order for alice@example.com?", "session_id": "test-123"}'
```

---

## API Reference

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send message to AI agent |
| `GET` | `/api/sessions/{session_id}/history` | Get conversation history |

#### POST /api/chat

**Request:**
```json
{
  "message": "What's my order status?",
  "session_id": "customer-123",
  "user_id": 1,
  "tone": "friendly"
}
```

**Response:**
```json
{
  "response": "I found your order for Wireless Headphones...",
  "handoff": false,
  "handoff_reason": null,
  "session_id": "customer-123",
  "tool_calls": ["lookup_user", "get_orders"]
}
```

### User & Data Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/{user_id}` | Get user profile |
| `GET` | `/api/users/{user_id}/orders` | Get user's orders |
| `GET` | `/api/users/{user_id}/tickets` | Get user's tickets |
| `PUT` | `/api/tickets/{ticket_id}` | Update ticket status |

### Handoff & Agent Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/handoffs` | List pending handoff requests |
| `POST` | `/api/handoffs/{session_id}/accept` | Accept a handoff |
| `GET` | `/api/handoffs/{session_id}/messages` | Get session messages |
| `POST` | `/api/handoffs/{session_id}/message` | Send message as agent |
| `GET` | `/api/handoffs/{session_id}/copilot` | Get AI co-pilot suggestion |

### Customer Context Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/handoffs/{session_id}/context` | Get customer profile, orders, tickets |
| `POST` | `/api/handoffs/{session_id}/link-user` | Link session to user ID |

### Persistent Customer Memory Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions/{session_id}/close` | Close session, compute insights, update profile |
| `GET` | `/api/users/{user_id}/profile` | Get aggregated customer profile |

#### POST /api/sessions/{session_id}/close

Computes per-session analytics (sentiment drift, resolution status, tool usage), persists a `SessionInsights` row, and recomputes the customer's aggregated `CustomerProfile`.

**Response:**
```json
{
  "session_id": "customer-123",
  "resolution_status": "resolved",
  "sentiment_drift": 0.7,
  "message": "Session closed"
}
```

#### GET /api/users/{user_id}/profile

Returns the aggregated customer profile built from all past sessions.

**Response:**
```json
{
  "user_id": 1,
  "total_sessions": 3,
  "total_escalations": 0,
  "resolution_rate": 1.0,
  "weighted_sentiment": 0.3,
  "avg_sentiment_drift": 0.5,
  "topic_frequency": {"support_inquiry": 2, "order_status": 1},
  "loyalty_tier": "silver",
  "total_spend": 199.97,
  "risk_flag": false,
  "risk_reasons": [],
  "preferred_tone": "friendly",
  "first_contact": "2025-01-10 14:30:00",
  "last_contact": "2025-01-15 09:00:00",
  "last_resolution_status": "resolved"
}
```

### AI Analysis Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/handoffs/{session_id}/sentiment` | Get sentiment analysis |
| `GET` | `/api/handoffs/{session_id}/smart-suggestions` | Get 3 ranked suggestions |

#### GET /api/handoffs/{session_id}/sentiment

**Response:**
```json
{
  "score": -0.6,
  "label": "negative",
  "confidence": 0.85
}
```

#### GET /api/handoffs/{session_id}/smart-suggestions

**Response:**
```json
{
  "suggestions": [
    {
      "suggestion": "I sincerely apologize for the delay...",
      "confidence": 0.92,
      "rationale": "Customer is frustrated; empathetic response recommended"
    },
    {
      "suggestion": "Let me check the tracking information...",
      "confidence": 0.85,
      "rationale": "Addresses the shipping concern directly"
    },
    {
      "suggestion": "I understand this is frustrating...",
      "confidence": 0.78,
      "rationale": "Acknowledges emotion before problem-solving"
    }
  ],
  "sentiment": {
    "score": -0.6,
    "label": "negative",
    "confidence": 0.85
  }
}
```

### Canned Responses Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/canned-responses` | List all (filter: `?category=refund`) |
| `POST` | `/api/canned-responses` | Create new canned response |
| `DELETE` | `/api/canned-responses/{id}` | Delete a canned response |

### Knowledge Base Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/knowledge/search` | Search knowledge base |
| `GET` | `/api/knowledge/stats` | Get KB statistics |
| `DELETE` | `/api/knowledge` | Clear all documents |
| `POST` | `/api/knowledge/upload` | Add new document |

#### POST /api/knowledge/search

**Request:**
```json
{
  "query": "What is the refund policy?",
  "num_results": 3
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "We offer a 30-day refund policy for defective items...",
      "source": "refund_policy.md",
      "score": 0.8542
    }
  ],
  "query": "What is the refund policy?"
}
```

#### POST /api/canned-responses

**Request:**
```json
{
  "shortcut": "/apologize",
  "title": "Apology",
  "content": "I sincerely apologize for the inconvenience...",
  "category": "support"
}
```

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/customer/{session_id}` | Customer chat channel |
| `ws://host/ws/agent/{session_id}` | Human agent channel |

---

## Agent Dashboard

The Agent Dashboard provides a comprehensive interface for human agents to handle escalated conversations.

### Layout

```
┌─────────────┬──────────────────────────────┬─────────────────┐
│   SIDEBAR   │         MAIN CHAT            │  CONTEXT PANEL  │
│             │                              │                 │
│ Agent name  │ Sentiment: [+ POSITIVE]      │ USER PROFILE    │
│ Handoffs    │                              │ Name: Alice     │
│             │ Customer: My order...        │ Email: a@ex.com │
│ - Session 1 │ AI: I can help...            │ Phone: 555-0101 │
│ - Session 2 │ Customer: Thanks!            │                 │
│             │                              │ RECENT ORDERS   │
│             ├──────────────────────────────│ 🟢 Headphones   │
│             │ SMART SUGGESTIONS            │ 🔵 Phone Case   │
│             │ 1. "I'll check on that..."   │                 │
│             │ 2. "Let me look into..."     │ OPEN TICKETS    │
│             │ 3. "I understand your..."    │ 🟠 #1: Charging │
│             ├──────────────────────────────│                 │
│             │ CANNED RESPONSES       [▼]   │                 │
│             │ /greet /refund /shipping     │                 │
│             ├──────────────────────────────│                 │
│             │ [Message input...      ] Send│                 │
└─────────────┴──────────────────────────────┴─────────────────┘
```

### Features

1. **Pending Handoffs** — See all escalated sessions, accept to start helping
2. **Sentiment Indicator** — Color-coded mood (🟢 positive, ⚪ neutral, 🔴 negative)
3. **Smart Suggestions** — Click "Get Suggestions" for AI-generated responses
4. **Canned Responses** — Quick-insert templates filtered by category
5. **Customer Context** — Auto-populated when user is identified
6. **Manual User Linking** — Link session to user ID if not auto-detected

---

## AI Features

### Sentiment Analysis

Real-time analysis of customer emotional state using GPT-4o-mini.

- **Score Range:** -1.0 (very negative) to +1.0 (very positive)
- **Labels:** `negative`, `neutral`, `positive`
- **Confidence:** 0.0 to 1.0

Analyzes the last 5 customer messages, considering:
- Word choice and tone
- Punctuation (caps, exclamation marks)
- Overall conversation context

### Smart Suggestions

Context-aware response generation that considers:

1. **Conversation History** — Last 10 messages for context
2. **Sentiment** — Adapts tone based on customer mood
3. **Customer Context** — References specific orders, tickets, user info
4. **Ranking** — 3 suggestions ordered by confidence with rationale

### Persistent Customer Memory

Cross-session customer intelligence that builds over time.

**Session Close Pipeline:**
1. On session end (REST close or WebSocket disconnect), sentiment is computed on the first and last user messages (2 LLM calls, only at close time — zero impact on live chat)
2. Resolution status is inferred: `escalated` if handoff occurred, `resolved` if the last assistant message contains closing phrases, otherwise `unresolved`
3. A `SessionInsights` row is persisted with sentiment drift, intent, tool calls, tone, and handoff details
4. The customer's `CustomerProfile` is recomputed from all their sessions

**Profile Aggregation:**
- **Weighted sentiment** — Exponential decay (0.7 rate) so recent sessions dominate
- **Loyalty tier** — Based on total spend: standard (<$100), silver ($100-499), gold ($500-1999), platinum ($2000+)
- **Risk detection** — Flags customers with escalation rate >40%, weighted sentiment < -0.3, negative drift trend, or 3+ consecutive unresolved sessions
- **Preferred tone** — Most-used tone during resolved sessions, with fallback heuristics

**Dynamic Tone Inference:**
- Acute negative keywords (frustrated, angry, lawsuit, etc.) in the current message → `professional`
- Risk-flagged customer → `professional`
- Historical preferred tone → use it
- Default → `friendly`
- No LLM call — keyword-based, zero added latency

### Auto-Linking

When the AI agent uses `lookup_user` tool and finds a customer, the session is automatically linked to that user ID. This enables:
- Immediate context panel population
- Context-aware smart suggestions
- Profile-aware personalization from the first message

---

## Evaluation Suite

Comprehensive test suite to ensure AI quality over time.

### Running Evals

```bash
# Run all tests (requires OPENAI_API_KEY)
python evals/run_evals.py all

# Run quick tests (no API calls, for CI)
python evals/run_evals.py quick

# Run specific suites
python evals/run_evals.py sentiment
python evals/run_evals.py suggestions
python evals/run_evals.py api
python evals/run_evals.py integration

# Verbose output
python evals/run_evals.py all -v

# View summary
python evals/run_evals.py summary
```

### Test Coverage

| Suite | Tests | Description |
|-------|-------|-------------|
| **Sentiment** | 20+ | Accuracy on negative/positive/neutral, multi-turn, edge cases |
| **Suggestions** | 17+ | Structure, ordering, context-awareness, empathy |
| **Canned Responses** | 17 | CRUD operations, filtering, content quality |
| **Customer Context** | 19 | Session mapping, user linking, data retrieval |
| **Integration** | 14 | End-to-end workflows, regression safety |

### Accuracy Thresholds

- **Sentiment Analysis:** ≥80% label accuracy required
- **Smart Suggestions:** Must contain relevant themes per scenario

### CI Integration

```yaml
# Example GitHub Actions workflow
- name: Run Quick Evals
  run: python evals/run_evals.py quick

- name: Run Full Evals
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: python evals/run_evals.py all
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | (required) | API key for the LLM provider |
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `qwen3`, or `kimi` |
| `DATABASE_URL` | `sqlite:///cx_agent.db` | Database connection string |
| `DEFAULT_TONE` | `friendly` | Default agent personality |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### System Prompts

Edit `config/system_prompts.yaml` to customize agent behavior:

```yaml
tones:
  professional:
    system_prompt: "You are a professional customer service representative..."

  friendly:
    system_prompt: "You are a warm, friendly customer service agent..."

  playful:
    system_prompt: "You are an upbeat, fun customer service agent..."

guardrails:
  - "Never speculate on data you cannot verify from the database."
  - "If uncertain, escalate to a human agent."
  - "Do not share personal information about other customers."
  - "Always verify customer identity before making account changes."
```

### Permissions

Role-based access control in `src/config/permissions.py`:

```python
# customer_ai role: Limited write access
"customer_ai": {
    "read": ["users", "orders", "tickets", "customer_profiles", "session_insights"],
    "write": {"tickets": ["status"], "users": ["email"]}
}

# agent_assist role: Extended access
"agent_assist": {
    "read": ["users", "orders", "tickets", "customer_profiles", "session_insights"],
    "write": {"tickets": ["status", "assigned_to"], "orders": ["status"]}
}
```

---

## Agent Tools

The AI agent has access to these function-calling tools:

| Tool | Description | Permission |
|------|-------------|------------|
| `lookup_user` | Find customer by email or ID | Read: users |
| `get_orders` | Get customer's order history | Read: orders |
| `get_tickets` | Get customer's support tickets | Read: tickets |
| `update_ticket` | Change ticket status | Write: tickets.status |
| `update_user_email` | Update customer email | Write: users.email |
| `flag_refund` | Mark order for refund | Write: orders.status |
| `knowledge_search` | Search RAG knowledge base | None (public) |

---

## Handoff Rules

The agent automatically escalates to a human when:

1. **Repeated Intent** — Customer asks the same question twice (word overlap > 0.85)
2. **Data Gap** — A tool call returns empty/null results
3. **Max Iterations** — Agent loop exceeds 5 tool call rounds

---

## Database Models

### Core Models

```python
User        # id, name, email, phone, created_at, updated_at
Order       # id, user_id, product, amount, status, created_at
Ticket      # id, user_id, subject, description, status, priority, assigned_to
```

### Support Models

```python
CannedResponse    # id, shortcut, title, content, category, created_at
ConversationMeta  # id, session_id, user_id, sentiment_score, sentiment_label
Message           # id, session_id, role, content, metadata_json, created_at
```

### Persistent Memory Models

```python
SessionInsights   # id, session_id, user_id, sentiment_score/label, sentiment_start/end/drift,
                  # intent_primary, handoff_occurred/reason, resolution_status, message_count,
                  # tool_calls_json, tone_used, assigned_specialist, closed_at

CustomerProfile   # id, user_id, total_sessions, total_escalations, resolution_rate,
                  # weighted_sentiment, avg_sentiment_drift, topic_frequency_json,
                  # loyalty_tier, total_spend, risk_flag, risk_reasons_json,
                  # preferred_tone, first_contact, last_contact, last_resolution_status
```

### Demo Data

The seed script creates:
- 3 users (Alice, Bob, Carol)
- 5 orders across users
- 3 support tickets
- 6 canned responses (`/greet`, `/thanks`, `/refund`, `/shipping`, `/escalate`, `/close`)
- 2 session insights (demo-session-alice, demo-session-bob)
- 3 customer profiles (one per demo user)

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`python evals/run_evals.py quick`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### Development Guidelines

- Run `python evals/run_evals.py quick` before committing
- Add tests for new features in `evals/`
- Update README for API changes
- Follow existing code style

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- OpenAI for GPT-4 and function calling capabilities
- FastAPI for the excellent web framework
- Streamlit for rapid UI development

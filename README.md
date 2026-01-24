# CX Agent V2.0

AI-powered Customer Experience Agent built with FastAPI, OpenAI GPT-4, and Streamlit.

## Features

- **AI Chat Agent** — OpenAI GPT-4 with function calling for real-time database lookups
- **Smart Handoff** — Automatic escalation to human agents via repeat detection, data gaps, and hallucination guards
- **WebSocket Support** — Real-time customer ↔ agent communication with co-pilot mode
- **Role-Based Access** — Permission-controlled read/write access to customer data
- **Configurable Tone** — Switch between professional, friendly, and playful personalities
- **Query Sanitization** — Input validation middleware to prevent SQL injection

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | OpenAI GPT-4 (function calling) |
| Backend | FastAPI + WebSocket |
| Database | SQLite + SQLAlchemy ORM |
| Frontend | Streamlit |
| Config | YAML-based system prompts |

## Project Structure

```
CX_Agent/
├── src/
│   ├── main.py              # FastAPI entry point
│   ├── config/              # Settings, prompts, permissions
│   ├── database/            # ORM models, connection, seed data
│   ├── agent/               # AI agent, tools, memory, handoff
│   ├── api/                 # REST routes, WebSocket handlers, schemas
│   └── utils/               # Logging
├── ui/
│   └── app.py               # Streamlit chat interface
├── config/
│   └── system_prompts.yaml  # Tone configurations & guardrails
├── requirements.txt
└── .env.example
```

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/NeerajMehta15/CX_Agent_V2.0.git
   cd CX_Agent_V2.0
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

## Usage

### Start the API server
```bash
uvicorn src.main:app --reload
```
The database is automatically created and seeded on first run. API docs available at `http://localhost:8000/docs`.

### Start the Streamlit UI
```bash
streamlit run ui/app.py
```

## API Endpoints

### REST
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message, get AI response |
| GET | `/api/sessions/{id}/history` | Retrieve chat history |
| GET | `/api/users/{id}` | Get user profile |
| GET | `/api/users/{id}/orders` | Get order history |
| GET | `/api/users/{id}/tickets` | Get support tickets |
| PUT | `/api/tickets/{id}` | Update ticket status |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/customer/{session_id}` | Customer chat channel |
| `ws://host/ws/agent/{session_id}` | Human agent channel |

## Agent Tools

The AI agent has access to the following function-calling tools:

- `lookup_user` — Find customer by email or ID
- `get_orders` — Retrieve order history
- `get_tickets` — Retrieve support tickets
- `update_ticket` — Change ticket status
- `update_user_email` — Update customer email
- `flag_refund` — Flag an order for refund

## Handoff Rules

The agent automatically escalates to a human when:

1. **Repeated Intent** — Customer asks the same question twice (similarity > 0.85)
2. **Data Gap** — A tool call returns empty/null results
3. **Hallucination Risk** — Response cannot be grounded in tool results

## Configuration

Edit `config/system_prompts.yaml` to customize agent tones and guardrails:

```yaml
tones:
  friendly:
    system_prompt: "You are a warm, friendly customer service agent..."

guardrails:
  - "Never speculate on data you cannot verify from the database."
  - "If uncertain, escalate to a human agent."
```

## License

MIT

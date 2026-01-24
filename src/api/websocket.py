import json
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.agent.cx_agent import run_agent
from src.database.connection import SessionLocal
from src.utils.logger import get_logger

logger = get_logger(__name__)

ws_router = APIRouter()

# Connection pools
customer_connections: dict[str, WebSocket] = {}
agent_connections: dict[str, WebSocket] = {}
# Track which sessions are in handoff mode
handoff_sessions: set[str] = set()


@ws_router.websocket("/ws/customer/{session_id}")
async def customer_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for customer chat."""
    await websocket.accept()
    customer_connections[session_id] = websocket
    logger.info(f"Customer connected: {session_id}")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            user_msg = message.get("message", "")

            if session_id in handoff_sessions:
                # Session is in handoff mode - forward to human agent
                await _forward_to_agent(session_id, user_msg)
            else:
                # Process through AI agent
                db = SessionLocal()
                try:
                    result = run_agent(
                        user_message=user_msg,
                        session_id=session_id,
                        db=db,
                        tone=message.get("tone"),
                    )

                    # Send AI response to customer
                    await websocket.send_json({
                        "type": "ai_response",
                        "message": result.message,
                        "handoff": result.handoff,
                    })

                    # If handoff triggered, notify agent pool
                    if result.handoff:
                        handoff_sessions.add(session_id)
                        await _broadcast_handoff_request(
                            session_id, user_msg, result.handoff_reason
                        )
                finally:
                    db.close()
    except WebSocketDisconnect:
        customer_connections.pop(session_id, None)
        logger.info(f"Customer disconnected: {session_id}")


@ws_router.websocket("/ws/agent/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for human agent. Receives handoff requests and co-pilot suggestions."""
    await websocket.accept()
    agent_connections[session_id] = websocket
    logger.info(f"Agent connected: {session_id}")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type", "")

            if msg_type == "accept_handoff":
                # Agent accepts the handoff
                target_session = message.get("session_id")
                if target_session:
                    handoff_sessions.add(target_session)
                    # Notify customer
                    customer_ws = customer_connections.get(target_session)
                    if customer_ws:
                        await customer_ws.send_json({
                            "type": "agent_joined",
                            "message": "A human agent has joined the conversation.",
                        })

            elif msg_type == "agent_message":
                # Agent sends message to customer
                target_session = message.get("session_id")
                agent_msg = message.get("message", "")
                customer_ws = customer_connections.get(target_session)
                if customer_ws:
                    await customer_ws.send_json({
                        "type": "agent_message",
                        "message": agent_msg,
                    })

                # Generate co-pilot suggestion for agent
                db = SessionLocal()
                try:
                    copilot_result = run_agent(
                        user_message=f"[Customer context] The customer said: {agent_msg}. Suggest a helpful response.",
                        session_id=f"copilot_{target_session}",
                        db=db,
                        role="agent_assist",
                    )
                    await websocket.send_json({
                        "type": "copilot_suggestion",
                        "suggestion": copilot_result.message,
                    })
                finally:
                    db.close()

    except WebSocketDisconnect:
        agent_connections.pop(session_id, None)
        logger.info(f"Agent disconnected: {session_id}")


async def _forward_to_agent(session_id: str, message: str):
    """Forward a customer message to the connected agent."""
    for agent_ws in agent_connections.values():
        try:
            await agent_ws.send_json({
                "type": "customer_message",
                "session_id": session_id,
                "message": message,
            })
        except Exception:
            pass


async def _broadcast_handoff_request(session_id: str, customer_message: str, reason: str | None):
    """Broadcast a handoff request to all connected agents."""
    event = {
        "type": "handoff_request",
        "session_id": session_id,
        "reason": reason,
        "customer_message": customer_message,
    }
    for agent_ws in agent_connections.values():
        try:
            await agent_ws.send_json(event)
        except Exception:
            pass

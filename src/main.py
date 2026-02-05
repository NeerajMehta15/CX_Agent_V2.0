from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.api.websocket import ws_router
from src.database.connection import init_db
from src.database.seed import seed_data

app = FastAPI(title="CX Agent", version="1.0.0", description="AI-powered Customer Experience Agent")

# Include routers
app.include_router(router)
app.include_router(ws_router)

# Serve frontend files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    init_db()
    seed_data()


@app.get("/")
def root():
    return {"message": "CX Agent API is running", "docs": "/docs"}


@app.get("/chat")
def customer_chat():
    return FileResponse(str(FRONTEND_DIR / "customer.html"))


@app.get("/dashboard")
def agent_dashboard():
    return FileResponse(str(FRONTEND_DIR / "agent.html"))

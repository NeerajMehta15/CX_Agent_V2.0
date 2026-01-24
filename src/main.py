from fastapi import FastAPI

from src.api.routes import router
from src.api.websocket import ws_router
from src.database.connection import init_db
from src.database.seed import seed_data

app = FastAPI(title="CX Agent", version="1.0.0", description="AI-powered Customer Experience Agent")

# Include routers
app.include_router(router)
app.include_router(ws_router)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_data()


@app.get("/")
def root():
    return {"message": "CX Agent API is running", "docs": "/docs"}

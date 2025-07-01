from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

try:
    from .database import db_manager, session_service
    from .routes.openai import router as openai_router
except ImportError:
    from database import db_manager, session_service
    from routes.openai import router as openai_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_manager.init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down")

app = FastAPI(
    title="Claude Code API",
    description="HTTP server with OpenAI API compatibility",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(openai_router)

@app.get("/")
async def root():
    return {"message": "Claude Code API Server"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
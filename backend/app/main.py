"""
Support Brain — FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import init_db

# Routes
from app.routes.auth import router as auth_router
from app.routes.knowledge import router as knowledge_router
from app.routes.chat import router as chat_router
from app.routes.email_routes import router as email_router
from app.routes.pending import router as pending_router
from app.routes.lessons import router as lessons_router
from app.routes.analytics import router as analytics_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("support_brain")

settings = get_settings()

# Rate limiter for public chat
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.CHAT_RATE_LIMIT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Support Brain starting up…")
    settings.validate_all()
    await init_db()
    logger.info("✅ Database ready. App is live.")
    yield
    logger.info("👋 Support Brain shutting down.")


app = FastAPI(
    title="Support Brain API",
    description="AI-powered customer support platform with Knowledge Brain, RAG, and Gmail integration.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/api/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


# Apply rate limit to public chat
from app.routes.chat import public_chat
limiter.limit(settings.CHAT_RATE_LIMIT)(public_chat)

# Include all routers
app.include_router(auth_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(email_router)
app.include_router(pending_router)
app.include_router(lessons_router)
app.include_router(analytics_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

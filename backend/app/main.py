"""
Support Brain — FastAPI Application Entry Point
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
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


@app.get("/widget.js", tags=["widget"])
async def get_widget_script():
    """
    Serve the embeddable customer chat widget JavaScript file.
    Usable on external websites with:
      <script src="https://YOUR_BACKEND_URL/widget.js" data-business-token="PUBLIC_WIDGET_TOKEN"></script>
    """
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "widget", "src", "widget.js")
    )
    if not os.path.exists(script_path):
        return JSONResponse(status_code=404, content={"detail": "widget.js not found"})
    return FileResponse(
        script_path,
        media_type="application/javascript",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.get("/api/widget/iframe", tags=["widget"])
async def widget_iframe(token: Optional[str] = None, slug: Optional[str] = None):
    """
    Redirect helper for external iframe embedding.
    Directs to the public chat interface for the requested business token or slug.
    """
    frontend_base = (settings.FRONTEND_URL or "http://localhost:5173").rstrip("/")
    if token:
        return RedirectResponse(f"{frontend_base}/chat?token={token}")
    elif slug:
        return RedirectResponse(f"{frontend_base}/chat/{slug}")
    return RedirectResponse(f"{frontend_base}/chat")


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

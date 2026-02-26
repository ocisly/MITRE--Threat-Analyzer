"""FastAPI application factory — Phase 2.

Adds:
  - MAF AG-UI endpoint at POST /agent (streaming SSE)
  - REST Browse API at /api/v1/*
  - CORS middleware
  - opentelemetry-semconv-ai compatibility patch (LLM_SYSTEM)
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, init_db
from app.models.sync_log import SyncLog
from app.sync.scheduler import create_scheduler, run_sync_all_domains
from app.api import api_router

# ── opentelemetry-semconv-ai compatibility patch ──────────────────────────────
# agent-framework-core uses SpanAttributes attributes that were removed in
# opentelemetry-semantic-conventions-ai >= 0.4.2. Patch them back from their
# canonical OpenTelemetry GenAI semantic convention string values.
_MISSING_SPAN_ATTRS = {
    "LLM_SYSTEM": "gen_ai.system",
    "LLM_REQUEST_MAX_TOKENS": "gen_ai.request.max_tokens",
    "LLM_REQUEST_MODEL": "gen_ai.request.model",
    "LLM_REQUEST_TEMPERATURE": "gen_ai.request.temperature",
    "LLM_REQUEST_TOP_P": "gen_ai.request.top_p",
    "LLM_RESPONSE_MODEL": "gen_ai.response.model",
    "LLM_TOKEN_TYPE": "gen_ai.token.type",
}
try:
    from opentelemetry.semconv_ai import SpanAttributes as _SA
    for _attr, _val in _MISSING_SPAN_ATTRS.items():
        if not hasattr(_SA, _attr):
            setattr(_SA, _attr, _val)  # type: ignore[attr-defined]
except ImportError:
    pass
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _create_ag_ui_agent():
    """Create the MAF agent only when Azure OpenAI is configured."""
    if not settings.azure_openai_endpoint or not settings.azure_openai_deployment:
        logger.warning(
            "AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_DEPLOYMENT not set — "
            "AG-UI /agent endpoint will NOT be registered. "
            "Set these env vars to enable AI threat analysis."
        )
        return None
    try:
        from app.agent.agent_factory import create_agent
        return create_agent(settings)
    except Exception as exc:
        logger.error("Failed to create MAF agent: %s", exc)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    settings.stix_data_dir.mkdir(parents=True, exist_ok=True)

    init_db()
    logger.info("Database ready")

    with SessionLocal() as db:
        last_success = db.execute(
            select(SyncLog)
            .where(SyncLog.status == "success")
            .order_by(SyncLog.completed_at.desc())
        ).scalars().first()

    if last_success is None:
        logger.info("No successful sync on record — scheduling initial MITRE sync in background")
        asyncio.create_task(run_sync_all_domains())

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started (interval: %dh)", settings.sync_interval_hours)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MITRE ATT&CK Threat Analyzer",
        description="AI-powered threat analysis using MITRE ATT&CK framework",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS — allow frontend dev server and configured frontend URL
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # REST Browse + Health API
    app.include_router(api_router)

    # AG-UI endpoint (only when Azure OpenAI is configured)
    agent = _create_ag_ui_agent()
    if agent is not None:
        from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
        add_agent_framework_fastapi_endpoint(app, agent, "/agent")
        logger.info("AG-UI endpoint registered at POST /agent")
    else:
        @app.post("/agent", tags=["agent"], status_code=503)
        def agent_not_configured():
            return {
                "error": "AI agent not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT env vars."
            }

    # Serve the React frontend from /dist (production Docker image only).
    # Mounted LAST so all API routes take priority.
    # html=True returns index.html for unmatched paths (SPA client-side routing).
    _dist = Path(__file__).parent.parent / "dist"
    if _dist.exists():
        app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
        logger.info("Serving frontend from %s", _dist)
    else:
        logger.info("No dist/ found — API-only mode (local dev)")

    return app


app = create_app()

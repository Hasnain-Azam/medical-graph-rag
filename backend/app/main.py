"""
Medical Graph RAG — FastAPI Application Entrypoint

Startup: connects to Neo4j, creates vector index
Shutdown: gracefully closes Neo4j driver
All routes are prefixed with /api
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import upload, query
from app.services.graph_manager import graph_manager

# ── Logging ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (replaces deprecated on_event) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to Neo4j on startup; disconnect on shutdown."""
    logger.info("🚀 Starting Medical Graph RAG API...")
    try:
        graph_manager.connect()
        logger.info("✅ Neo4j connection established.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Neo4j: {e}")
        logger.warning("API will start, but graph endpoints will return 503.")

    yield  # Application runs here

    logger.info("🛑 Shutting down — closing Neo4j connection...")
    graph_manager.close()


# ── App Factory ───────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Medical Graph RAG API",
        description=(
            "A GraphRAG-powered medical research assistant. "
            "Upload medical documents, build a knowledge graph, and query it with AI."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS — allow the React frontend (Vite dev server) ─────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(upload.router, prefix="/api", tags=["Ingestion"])
    app.include_router(query.router, prefix="/api", tags=["Query"])

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "service": "Medical Graph RAG API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()

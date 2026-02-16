"""
FastAPI application for QMD MCP Server.

Provides HTTP endpoints for embedding generation, vector search,
and hybrid search with a single model instance.
"""

from fastapi import FastAPI, HTTPException
import asyncio
from typing import List, Optional
import logging

from qmd.server.models import (
    EmbedRequest, EmbedResponse,
    VSearchRequest, VSearchResponse,
    QueryRequest, QueryResponse,
    HealthResponse
)
from qmd.models.config import AppConfig

logger = logging.getLogger(__name__)

# Global singletons
_model = None
_processing_lock: Optional[asyncio.Lock] = None
_config: Optional[AppConfig] = None
_vector_search = None
_hybrid_search = None

# Model configuration
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="QMD MCP Server",
        description="Embedding and search service for QMD",
        version="1.0.0",
    )

    @app.on_event("startup")
    async def startup_event():
        """Initialize model and search engines on startup."""
        global _model, _processing_lock, _config, _vector_search, _hybrid_search

        try:
            # Load configuration
            _config = AppConfig.load()

            # Initialize embed model
            from fastembed import TextEmbedding
            logger.info(f"Loading model: {DEFAULT_MODEL}")
            _model = TextEmbedding(model_name=DEFAULT_MODEL)
            _processing_lock = asyncio.Lock()
            logger.info("Model loaded successfully")

            # Initialize search engines (lazy, will be created on first use)
            logger.info("Search engines will be initialized on first request")

        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down server")

    def _get_vector_search():
        """Lazy initialization of VectorSearch."""
        global _vector_search
        if _vector_search is None:
            from qmd.search.vector import VectorSearch

            _vector_search = VectorSearch(
                db_dir=".qmd_vector_db",
                mode="auto",
                server_url="http://localhost:8000"  # Default, will use auto-detect
            )
            logger.info("VectorSearch initialized")
        return _vector_search

    def _get_hybrid_search():
        """Lazy initialization of HybridSearcher."""
        global _hybrid_search
        if _hybrid_search is None:
            from qmd.search.hybrid import HybridSearcher
            from qmd.database.manager import DatabaseManager

            db = DatabaseManager(_config.db_path)
            _hybrid_search = HybridSearcher(
                db=db,
                vector_db_dir=".qmd_vector_db",
                mode="auto",
                server_url="http://localhost:8000"
            )
            logger.info("HybridSearcher initialized")
        return _hybrid_search

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy" if _model is not None else "unhealthy",
            model_loaded=_model is not None,
            queue_size=0,
        )

    @app.post("/embed", response_model=EmbedResponse)
    async def embed(request: EmbedRequest):
        """Generate embeddings for a list of texts."""
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        if not request.texts:
            raise HTTPException(status_code=400, detail="Empty texts list")

        if len(request.texts) > 1000:
            raise HTTPException(
                status_code=413, detail=f"Too many texts ({len(request.texts)} > 1000)"
            )

        try:
            async with _processing_lock:
                embeddings_list = await process_embeddings(request.texts)
            return EmbedResponse(embeddings=embeddings_list)

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/vsearch", response_model=VSearchResponse)
    async def vsearch(request: VSearchRequest):
        """Vector semantic search."""
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        try:
            searcher = _get_vector_search()
            results = searcher.search(
                request.query,
                collection_name=request.collection or "todo",
                limit=request.limit
            )
            # Convert SearchResult objects to dicts
            results_dicts = [r.dict() for r in results]
            return VSearchResponse(results=results_dicts)

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest):
        """Hybrid search (BM25 + vector + optional LLM expansion)."""
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        try:
            searcher = _get_hybrid_search()
            results = searcher.search(
                request.query,
                collection=request.collection or "todo",
                limit=request.limit
            )
            return QueryResponse(results=results)

        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app


async def process_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Process embeddings using the singleton model.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each as list of floats)
    """
    global _model

    # fastembed returns an iterator of numpy arrays
    embeddings = list(_model.embed(texts))

    # Convert numpy arrays to lists for JSON serialization
    return [emb.tolist() for emb in embeddings]


# Create the app instance
app = create_app()

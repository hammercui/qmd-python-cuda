"""
FastAPI application for QMD MCP Server.

Provides HTTP endpoints for embedding generation, vector search,
hybrid search, query expansion and LLM reranking — all as
shared singleton services so every CLI client just makes HTTP requests.
"""

from fastapi import FastAPI, HTTPException, Request
import asyncio
import time
from typing import List, Optional
import logging

from qmd.server.models import (
    EmbedRequest, EmbedResponse,
    VSearchRequest, VSearchResponse,
    QueryRequest, QueryResponse,
    ExpandRequest, ExpandResponse,
    RerankRequest, RerankResponse,
    HealthResponse
)
from qmd.models.config import AppConfig

logger = logging.getLogger(__name__)

# Global singletons
_model = None
_reranker = None
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
        description="Embedding, search, expand and rerank service for QMD",
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # 请求日志中间件：记录每条 HTTP 请求的方法、路径、状态码、耗时
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path}"
            f" → {response.status_code}"
            f" ({elapsed_ms:.1f} ms)"
            f" client={request.client.host if request.client else '-'}"
        )
        return response

    @app.on_event("startup")
    async def startup_event():
        """Initialize model and search engines on startup."""
        global _model, _processing_lock, _config, _vector_search, _hybrid_search

        try:
            # Load configuration
            _config = AppConfig.load()

            # Initialize embed model
            from fastembed import TextEmbedding

            # Detect GPU providers
            providers = None
            try:
                import torch
                if torch.cuda.is_available():
                    providers = ["CUDAExecutionProvider"]
                    logger.info("Using CUDAExecutionProvider for fastembed")
            except ImportError:
                pass

            logger.info(f"Loading embed model: {DEFAULT_MODEL}")
            logger.info(f"Providers: {providers or 'CPU'}")

            _model = TextEmbedding(
                model_name=DEFAULT_MODEL,
                providers=providers
            )
            _processing_lock = asyncio.Lock()
            logger.info("Embed model loaded successfully")
            logger.info("Search engines will be initialized on first request")
            logger.info("Reranker / query-expansion will be initialized on first /expand or /rerank request")

        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down server")

    # ------------------------------------------------------------------
    # Lazy initializers
    # ------------------------------------------------------------------
    def _make_embed_fn():
        """Return a callable that embeds a single string using the server's singleton model."""
        def _fn(text: str) -> List[float]:
            return list(_model.embed([text]))[0].tolist()
        return _fn

    def _get_vector_search():
        global _vector_search
        if _vector_search is None:
            from qmd.search.vector import VectorSearch
            # Inject the server's already-loaded _model so VectorSearch
            # doesn't create a second fastembed instance or HTTP-call itself.
            _vector_search = VectorSearch(
                db_dir=None,
                embed_fn=_make_embed_fn(),
            )
            logger.info("VectorSearch initialized at %s", _vector_search.db_dir)
        return _vector_search

    def _get_hybrid_search():
        global _hybrid_search
        if _hybrid_search is None:
            from qmd.search.hybrid import HybridSearcher
            from qmd.database.manager import DatabaseManager
            db = DatabaseManager(_config.db_path)
            # vector_db_dir=None lets VectorSearch auto-resolve to ~/.qmd/vector_db
            _hybrid_search = HybridSearcher(
                db=db,
                vector_db_dir=None,
                embed_fn=_make_embed_fn(),
            )
            logger.info("HybridSearcher initialized")
        return _hybrid_search

    def _get_reranker():
        """Lazy-load LLMReranker（reranker + query-expansion 两个模型）。"""
        global _reranker
        if _reranker is None:
            from qmd.search.rerank import LLMReranker
            logger.info("Loading LLMReranker (query-expansion + cross-encoder)...")
            _reranker = LLMReranker()
            # 触发两个子模型的懒加载，首次较慢
            _ = _reranker.expansion_model
            _ = _reranker.model
            logger.info("LLMReranker loaded successfully")
        return _reranker

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy" if _model is not None else "unhealthy",
            model_loaded=_model is not None,
            reranker_loaded=_reranker is not None,
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
            raise HTTPException(status_code=413, detail=f"Too many texts ({len(request.texts)} > 1000)")
        try:
            async with _processing_lock:
                embeddings_list = await process_embeddings(request.texts)
            return EmbedResponse(embeddings=embeddings_list)
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/vsearch", response_model=VSearchResponse)
    async def vsearch(request: VSearchRequest):
        """Vector semantic search. Searches all collections when collection is not specified."""
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        try:
            searcher = _get_vector_search()
            # collection=None → searches across ALL embedded collections
            results = searcher.search(
                request.query,
                collection_name=request.collection or None,
                limit=request.limit
            )
            return VSearchResponse(results=[r.dict() for r in results])
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest):
        """Hybrid search (BM25 + vector)."""
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        try:
            searcher = _get_hybrid_search()
            results = searcher.search(
                request.query,
                collection=request.collection or None,
                limit=request.limit
            )
            return QueryResponse(results=results)
        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/expand", response_model=ExpandResponse)
    async def expand(request: ExpandRequest):
        """Query expansion using local LLM (Qwen2.5-0.5B-Instruct)."""
        try:
            reranker = _get_reranker()
            queries = reranker.expand_query(request.query)
            return ExpandResponse(queries=queries)
        except Exception as e:
            logger.error(f"Query expansion error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rerank", response_model=RerankResponse)
    async def rerank(request: RerankRequest):
        """LLM reranking using cross-encoder (Qwen3-Reranker-0.6B)."""
        if not request.documents:
            return RerankResponse(results=[])
        try:
            reranker = _get_reranker()
            results = reranker.rerank(request.query, request.documents, top_k=request.top_k)
            return RerankResponse(results=results)
        except Exception as e:
            logger.error(f"Reranking error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app


async def process_embeddings(texts: List[str]) -> List[List[float]]:
    """Process embeddings using the singleton model."""
    global _model
    embeddings = list(_model.embed(texts))
    return [emb.tolist() for emb in embeddings]


# Create the app instance
app = create_app()

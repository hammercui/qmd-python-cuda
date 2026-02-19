"""
FastAPI application for QMD MCP Server.

Provides HTTP endpoints for embedding generation, vector search,
hybrid search, query expansion and LLM reranking — all as
shared singleton services so every CLI client just makes HTTP requests.
"""

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp
import asyncio
import math
import time
from typing import List, Optional
import logging
from pathlib import Path


# ----------------------------------------------------------------------
# Request Size Limit Middleware
# ----------------------------------------------------------------------
# Fix HTTP 413 error by increasing max request body size
# Default Starlette has no explicit limit, but some configurations may restrict it
# This middleware explicitly allows larger requests for batch embedding
# ----------------------------------------------------------------------


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check request body size before processing.

    Allows up to max_size bytes for POST requests.
    Returns 413 if exceeded.
    """

    def __init__(self, app: ASGIApp, max_size: int = 100 * 1024 * 1024):
        super().__init__(app)
        self.max_size = max_size  # Default: 100MB

    async def dispatch(self, request: Request, call_next):
        t_start = time.time()
        ts_in = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t_start))
        logger.info(f"[{ts_in}] --> {request.method} {request.url.path}")

        # Check Content-Length for POST/PUT requests
        if request.method in ("POST", "PUT"):
            content_length = request.headers.get("content-length")
            if content_length:
                size = int(content_length)
                if size > self.max_size:
                    elapsed = (time.time() - t_start) * 1000
                    ts_out = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    logger.info(f"[{ts_out}] <-- {request.method} {request.url.path} 413 ({elapsed:.1f}ms)")
                    return Response(
                        content=f"Request body too large: {size} > {self.max_size} bytes. "
                        f"Use batch endpoint or increase limit.",
                        status_code=413,
                        media_type="text/plain",
                    )

        response = await call_next(request)
        elapsed = (time.time() - t_start) * 1000
        ts_out = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info(f"[{ts_out}] <-- {request.method} {request.url.path} {response.status_code} ({elapsed:.1f}ms)")
        return response


from qmd.server.models import (
    EmbedRequest,
    EmbedResponse,
    VSearchRequest,
    VSearchResponse,
    QueryRequest,
    QueryResponse,
    ExpandRequest,
    ExpandResponse,
    RerankRequest,
    RerankResponse,
    HealthResponse,
)
from qmd.models.config import AppConfig
from qmd.llm.engine import (
    EMBEDDING_MODEL_NAME,
    JINA_ZH_PROVIDERS,
    _register_jina_zh,
)

logger = logging.getLogger(__name__)

# Global singletons
_model = None
_reranker = None
_processing_lock: Optional[asyncio.Lock] = None
_config: Optional[AppConfig] = None
_vector_search = None
_hybrid_search = None

# Model configuration
DEFAULT_MODEL = "jinaai/jina-embeddings-v2-base-zh-q4f16"  # Jina v2 ZH INT8 ONNX (Xenova), 768d


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="QMD MCP Server",
        description="Embedding, search, expand and rerank service for QMD",
        version="1.0.0",
    )

    # ------------------------------------------------------------------
    # Request Size Limit: 允许最大 100MB 请求体
    # 解决批量嵌入时的 HTTP 413 错误
    # ------------------------------------------------------------------
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_size=100 * 1024 * 1024,  # 100MB
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
            _config = AppConfig.load()

            if DEFAULT_MODEL == EMBEDDING_MODEL_NAME:
                _register_jina_zh()
                providers = JINA_ZH_PROVIDERS
            else:
                providers = None

            from fastembed import TextEmbedding as _TextEmbedding

            logger.info(f"Loading embed model: {DEFAULT_MODEL} (providers: {providers})")
            load_kwargs = dict(model_name=DEFAULT_MODEL)
            if providers:
                load_kwargs["providers"] = providers

            _model = _TextEmbedding(**load_kwargs)
            _processing_lock = asyncio.Lock()
            logger.info("Embed model loaded successfully")

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
        """Return a callable that embeds a single query string using the server's singleton model."""

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
        """Generate embeddings for a list of texts.

        Note: For large batches (>32 texts), consider using /embed/batch endpoint
        or splitting into smaller requests to avoid memory issues.
        """
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        if not request.texts:
            raise HTTPException(status_code=400, detail="Empty texts list")
        try:
            texts = request.texts
            async with _processing_lock:
                embeddings_list = await process_embeddings(texts)
            return EmbedResponse(embeddings=embeddings_list)
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/embed/batch", response_model=EmbedResponse)
    async def embed_batch(request: EmbedRequest):
        """Generate embeddings for a large batch of texts with internal chunking.

        This endpoint automatically splits large batches into smaller chunks
        for efficient GPU processing. Recommended for embedding many documents.

        Args:
            request: EmbedRequest with texts list (can be large, up to 1000 texts)

        Returns:
            EmbedResponse with embeddings for all texts
        """
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        if not request.texts:
            raise HTTPException(status_code=400, detail="Empty texts list")

        try:
            texts = request.texts

            # process_embeddings already batches internally (GPU_EMBED_BATCH_SIZE)
            async with _processing_lock:
                all_embeddings = await process_embeddings(texts)

            return EmbedResponse(embeddings=all_embeddings)
        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
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
                limit=request.limit,
            )
            return VSearchResponse(results=[r.dict() for r in results])
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest):
        """Full query pipeline (TS-equivalent):
        LLM expansion → multi-query BM25+vector → weighted RRF → cross-encoder rerank → position-aware blend.
        Falls back gracefully to plain RRF if any step fails.
        """
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        try:
            import math
            from collections import defaultdict

            hybrid = _get_hybrid_search()
            vsearcher = _get_vector_search()
            col = request.collection or None
            limit = request.limit

            # ── Step 1: Query expansion via LLM ──────────────────────────────
            fts_queries = [request.query]
            vec_queries = [request.query]
            reranker = None
            try:
                reranker = _get_reranker()
                expanded = reranker.expand_query(request.query)
                # expanded[0] is always the original query; [1:] are LLM-generated variants
                for v in expanded[1:]:
                    if v and v.strip() and v != request.query:
                        fts_queries.append(v)
                        vec_queries.append(v)
                logger.info(
                    "Query expansion: %d BM25 queries, %d vector queries",
                    len(fts_queries),
                    len(vec_queries),
                )
            except Exception as exp_err:
                logger.warning(
                    "Query expansion failed (%s), using original query only", exp_err
                )

            # ── Steps 2 + 3: Multi-query BM25 + vector → ranked id lists ─────
            k = 60
            ranked_lists: list = []  # each element: [doc_id, ...] in rank order
            weights_list: list = []
            doc_info: dict = {}

            # BM25 searches (original query → weight 2.0; expanded → weight 1.0)
            for i, q in enumerate(fts_queries):
                results = hybrid.fts.search(q, limit=limit * 3)
                if col:
                    results = [r for r in results if r.get("collection") == col]
                if results:
                    ids = [f"{r['collection']}:{r['path']}" for r in results]
                    ranked_lists.append(ids)
                    weights_list.append(2.0 if i == 0 else 1.0)
                    for r in results:
                        did = f"{r['collection']}:{r['path']}"
                        if did not in doc_info:
                            doc_info[did] = {
                                "title": r.get("title", ""),
                                "collection": r["collection"],
                                "path": r["path"],
                                "content": r.get("content", ""),
                                "type": "fts",
                            }

            # Vector searches (original query → weight 2.0; expanded → weight 1.0)
            for i, q in enumerate(vec_queries):
                v_results = vsearcher.search(q, collection_name=col, limit=limit * 3)
                if v_results:
                    ids = [f"{r.collection}:{r.path}" for r in v_results]
                    ranked_lists.append(ids)
                    weights_list.append(2.0 if i == 0 else 1.0)
                    for r in v_results:
                        did = f"{r.collection}:{r.path}"
                        if did not in doc_info:
                            doc_info[did] = {
                                "title": r.metadata.get("title", ""),
                                "collection": r.collection,
                                "path": r.path,
                                "content": r.content,
                                "type": "vector",
                            }
                        else:
                            doc_info[did]["type"] = "hybrid"

            if not doc_info:
                return QueryResponse(results=[])

            # ── Step 4: Weighted Reciprocal Rank Fusion ──────────────────────
            rrf_scores: dict = defaultdict(float)
            for ids, w in zip(ranked_lists, weights_list):
                for rank, did in enumerate(ids, 1):
                    rrf_scores[did] += w / (k + rank)

            sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            rrf_ordered = []
            for rrf_rank, (did, rrf_score) in enumerate(sorted_docs[:40], 1):
                rrf_ordered.append(
                    {
                        "id": did,
                        "score": rrf_score,
                        "_rrf_rank": rrf_rank,
                        **doc_info[did],
                    }
                )

            # ── Step 5: LLM cross-encoder reranking ─────────────────────────
            if reranker is not None and rrf_ordered:
                try:
                    reranked = reranker.rerank(
                        request.query, rrf_ordered, top_k=len(rrf_ordered)
                    )

                    # ── Step 6: Position-aware score blending ─────────────────
                    rrf_rank_map = {c["id"]: c["_rrf_rank"] for c in rrf_ordered}
                    final = []
                    for doc in reranked:
                        rrf_rank = rrf_rank_map.get(doc.get("id", ""), 30)
                        rrf_s = float(rrf_scores.get(doc.get("id", ""), 0.0))
                        raw_rerank = float(doc.get("rerank_score", 0.0))
                        # Sigmoid-normalize the cross-encoder logit to [0, 1]
                        norm_rerank = 1.0 / (1.0 + math.exp(-raw_rerank))
                        # Weight towards RRF for top positions (trust retrieval rank more)
                        if rrf_rank <= 3:
                            w_rrf = 0.75
                        elif rrf_rank <= 10:
                            w_rrf = 0.60
                        else:
                            w_rrf = 0.40
                        blended = w_rrf * rrf_s + (1.0 - w_rrf) * norm_rerank
                        clean = {
                            key: val
                            for key, val in doc.items()
                            if not key.startswith("_")
                        }
                        final.append({**clean, "score": blended})

                    final.sort(key=lambda x: x["score"], reverse=True)
                    logger.info(
                        "Query pipeline complete: %d results (expanded+reranked)",
                        len(final[:limit]),
                    )
                    return QueryResponse(results=final[:limit])
                except Exception as rr_err:
                    logger.warning(
                        "Reranking failed (%s), returning plain RRF results", rr_err
                    )

            # Fallback: return weighted-RRF results without reranking
            fallback = [
                {key: val for key, val in c.items() if not key.startswith("_")}
                for c in rrf_ordered[:limit]
            ]
            logger.info("Query pipeline complete: %d results (RRF only)", len(fallback))
            return QueryResponse(results=fallback)

        except Exception as e:
            logger.error("Query pipeline error: %s", e, exc_info=True)
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
            results = reranker.rerank(
                request.query, request.documents, top_k=request.top_k
            )
            return RerankResponse(results=results)
        except Exception as e:
            logger.error(f"Reranking error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app


# GPU batch size for embedding inference.
# Jina v2 ZH quantized (768d): a batch of 16 x 3200-char chunks uses ~200 MB VRAM.
# Much lighter than BGE-M3; can be increased on higher-VRAM GPUs.
GPU_EMBED_BATCH_SIZE = 16


async def process_embeddings(texts: List[str]) -> List[List[float]]:
    """Process embeddings using the singleton model, batched to avoid OOM.

    Regardless of how many texts are passed, the actual model.embed() call
    is split into GPU_EMBED_BATCH_SIZE chunks so VRAM usage stays bounded.
    Non-finite values (nan/inf) are replaced with 0.0 for JSON safety.
    """
    global _model
    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), GPU_EMBED_BATCH_SIZE):
        batch = texts[i : i + GPU_EMBED_BATCH_SIZE]
        embeddings = list(_model.embed(batch))
        for emb in embeddings:
            vec = emb.tolist()
            if not all(math.isfinite(v) for v in vec):
                logger.warning(f"Non-finite values in embedding, replacing with 0.0 (text snippet: {batch[0][:50]!r})")
                vec = [v if math.isfinite(v) else 0.0 for v in vec]
            all_embeddings.append(vec)
    return all_embeddings


# Create the app instance
app = create_app()

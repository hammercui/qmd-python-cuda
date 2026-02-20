"""API endpoints for QMD server."""

import asyncio
import json as json_lib
import logging
import math
import time
from collections import defaultdict
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException

import qmd.server._state as _state
from qmd.server._state import DEFAULT_MODEL, srv_console
from qmd.server._worker import embed_worker
from qmd.server.models import (
    EmbedRequest,
    EmbedResponse,
    EmbedIndexRequest,
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

logger = logging.getLogger(__name__)

# Lazy-loaded singletons managed within this module
reranker = None
vector_search = None
hybrid_search = None

# Create router
router = APIRouter()

# GPU batch size (imported from state)
GPU_EMBED_BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Lazy initializers
# ---------------------------------------------------------------------------


def make_embed_fn():
    """Return a callable that embeds a single query string using the server's singleton model."""

    def _fn(text: str) -> List[float]:
        return list(_state.model.embed([text]))[0].tolist()

    return _fn


def get_vector_search():
    """Lazy-load VectorSearch."""
    global vector_search
    if vector_search is None:
        from qmd.search.vector import VectorSearch

        # Inject the server's already-loaded model so VectorSearch
        # doesn't create a second fastembed instance or HTTP-call itself.
        vector_search = VectorSearch(
            db_path=None,
            embed_fn=make_embed_fn(),
        )
        logger.info("VectorSearch initialized at %s", vector_search.db_path)
    return vector_search


def get_hybrid_search():
    """Lazy-load HybridSearcher."""
    global hybrid_search
    if hybrid_search is None:
        from qmd.search.hybrid import HybridSearcher
        from qmd.database.manager import DatabaseManager

        db = DatabaseManager(_state.config.db_path)
        # vector_db_dir=None lets VectorSearch auto-resolve to ~/.qmd/vector_db
        hybrid_search = HybridSearcher(
            db=db,
            vector_db_dir=None,
            embed_fn=make_embed_fn(),
        )
        logger.info("HybridSearcher initialized")
    return hybrid_search


def get_reranker():
    """Lazy-load LLMReranker (reranker + query-expansion two models)."""
    global reranker
    if reranker is None:
        from qmd.search.rerank import LLMReranker

        logger.info("Loading LLMReranker (query-expansion + cross-encoder)...")
        reranker = LLMReranker()
        # Trigger lazy loading of both sub-models; first call is slow
        _ = reranker.expansion_model
        _ = reranker.model
        logger.info("LLMReranker loaded successfully")
    return reranker


async def process_embeddings(texts: List[str]) -> List[List[float]]:
    """Process embeddings using the singleton model, batched to avoid OOM.

    Regardless of how many texts are passed, the actual model.embed() call
    is split into GPU_EMBED_BATCH_SIZE chunks so VRAM usage stays bounded.
    Non-finite values (nan/inf) are replaced with 0.0 for JSON safety.
    """
    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), GPU_EMBED_BATCH_SIZE):
        batch = texts[i : i + GPU_EMBED_BATCH_SIZE]
        embeddings = list(_state.model.embed(batch))
        for emb in embeddings:
            vec = emb.tolist()
            if not all(math.isfinite(v) for v in vec):
                logger.warning(
                    f"Non-finite values in embedding, replacing with 0.0 (text snippet: {batch[0][:50]!r})"
                )
                vec = [v if math.isfinite(v) else 0.0 for v in vec]
            all_embeddings.append(vec)
    return all_embeddings


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if _state.model is not None else "unhealthy",
        model_loaded=_state.model is not None,
        reranker_loaded=reranker is not None,
        queue_size=0,
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    """Generate embeddings for a list of texts.

    Note: For large batches (>32 texts), consider using /embed/batch endpoint
    or splitting into smaller requests to avoid memory issues.
    """
    if _state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if _state.embed_job.running:
        raise HTTPException(
            status_code=503,
            detail="Index embedding job in progress. Use /embed/index to attach.",
        )
    if not request.texts:
        raise HTTPException(status_code=400, detail="Empty texts list")
    try:
        texts = request.texts
        async with _state.processing_lock:
            embeddings_list = await process_embeddings(texts)
        return EmbedResponse(embeddings=embeddings_list)
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/batch", response_model=EmbedResponse)
async def embed_batch(request: EmbedRequest):
    """Generate embeddings for a large batch of texts with internal chunking.

    This endpoint automatically splits large batches into smaller chunks
    for efficient GPU processing. Recommended for embedding many documents.

    Args:
        request: EmbedRequest with texts list (can be large, up to 1000 texts)

    Returns:
        EmbedResponse with embeddings for all texts
    """
    if _state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if _state.embed_job.running:
        raise HTTPException(
            status_code=503,
            detail="Index embedding job in progress. Use /embed/index to attach.",
        )
    if not request.texts:
        raise HTTPException(status_code=400, detail="Empty texts list")

    try:
        texts = request.texts

        # process_embeddings already batches internally (GPU_EMBED_BATCH_SIZE)
        async with _state.processing_lock:
            all_embeddings = await process_embeddings(texts)

        return EmbedResponse(embeddings=all_embeddings)
    except Exception as e:
        logger.error(f"Batch embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/index")
async def embed_index(request: EmbedIndexRequest):
    """Server-side embedding: read DB → chunk → GPU embed → write DB, streamed as SSE.

    Only one job runs at a time.  A second caller automatically attaches to
    the running job and receives the current + future progress events.
    """
    if _state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    q: asyncio.Queue = asyncio.Queue()

    async with _state.embed_job_lock:
        if _state.embed_job.running:
            # Attach to the running job — send current state immediately
            _state.embed_job._queues.append(q)
            await q.put(
                json_lib.dumps(
                    {
                        "status": "running",
                        "done_chunks": _state.embed_job.done_chunks,
                        "total_chunks": _state.embed_job.total_chunks,
                        "done_docs": _state.embed_job.done_docs,
                        "total_docs": _state.embed_job.total_docs,
                        "_attached": True,
                    }
                )
            )
            logger.info("New client attached to running embed job")
        else:
            # Start a new job
            _state.embed_job.running = True
            _state.embed_job.finished = False
            _state.embed_job.collection = request.collection
            _state.embed_job.force = request.force
            _state.embed_job.total_chunks = 0
            _state.embed_job.done_chunks = 0
            _state.embed_job.total_docs = 0
            _state.embed_job.done_docs = 0
            _state.embed_job.error = None
            _state.embed_job._queues = [q]
            asyncio.create_task(embed_worker())
            logger.info(
                "Started embed job: collection=%s force=%s",
                request.collection,
                request.force,
            )

    from fastapi.responses import StreamingResponse

    async def event_stream():
        try:
            while True:
                item = await q.get()
                if item is None:  # sentinel: job finished
                    break
                yield f"data: {item}\n\n"
        except asyncio.CancelledError:
            pass  # client disconnected

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/vsearch", response_model=VSearchResponse)
async def vsearch(request: VSearchRequest):
    """
    Vector semantic search with optional query expansion.

    TS implementation:
    - Uses expandQueryStructured with includeLexical=false (no lex variants)
    - Only vec/hyde variants for vector search
    - Takes best score across multiple queries for same doc
    - Default min_score = 0.3
    """
    if _state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        searcher = get_vector_search()

        # Get all queries to search: original + expanded (vec/hyde only, no lex)
        queries = [request.query]
        min_score = request.min_score if request.min_score is not None else 0.3

        # Try query expansion (without lex variants for vsearch)
        try:
            reranker = get_reranker()
            loop = asyncio.get_event_loop()
            expanded = await loop.run_in_executor(
                None,
                reranker.expand_query,
                request.query,
                False,  # include_lexical=False
            )
            # Only use vec and hyde variants for vector search
            for v in expanded.get("vec", []) + expanded.get("hyde", []):
                if v and v.strip():
                    queries.append(v)
            if len(queries) > 1:
                logger.info(f"VSearch expansion: {len(queries)} queries")
        except Exception as exp_err:
            logger.warning(f"Query expansion failed in vsearch: {exp_err}")

        # Search with all queries, collect best score per document
        doc_best_score: Dict[str, float] = {}
        doc_info: Dict[str, Dict] = {}

        for q in queries:
            results = searcher.search(
                q,
                collection_name=request.collection or None,
                limit=request.limit * 2,  # Get more for dedup
            )

            for r in results:
                doc_key = f"{r.collection}:{r.path}"
                score = r.score

                # Keep best score across all queries
                if doc_key not in doc_best_score or score > doc_best_score[doc_key]:
                    doc_best_score[doc_key] = score
                    doc_info[doc_key] = {
                        "filepath": r.filepath,
                        "display_path": r.display_path,
                        "title": r.title,
                        "body": r.body,
                        "score": score,
                        "hash": r.hash,
                        "collection": r.collection,
                        "path": r.path,
                    }

        # Filter by min_score and convert to list
        filtered_results = [
            doc_info[k] for k, v in doc_best_score.items() if v >= min_score
        ]

        # Sort by score (best first) and limit
        filtered_results.sort(key=lambda x: x["score"], reverse=True)
        final_results = filtered_results[: request.limit]

        logger.info(
            f"VSearch: {len(queries)} queries, {len(doc_best_score)} candidates, "
            f"{len(final_results)} results (min_score={min_score})"
        )

        return VSearchResponse(results=final_results)
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Full query pipeline (TS-equivalent):
    Strong signal detection → (optional LLM expansion) → multi-query BM25+vector →
    weighted RRF with top-rank bonus → cross-encoder rerank → position-aware blend → dedup.
    Falls back gracefully to plain RRF if any step fails.
    """
    if _state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        hybrid = get_hybrid_search()
        vsearcher = get_vector_search()
        col = request.collection or None
        limit = request.limit

        # ── Step 0: Strong signal detection ─────────────────────────────
        # Check if top BM25 result is strong enough to skip LLM expansion
        # TS: topScore >= 0.85 AND (topScore - secondScore) >= 0.15
        t0 = time.perf_counter()
        initial_results = hybrid.fts.search(request.query, limit=20, collection=col)
        strong_signal = False

        if len(initial_results) >= 2:
            top_score = initial_results[0].get("score", 0.0)
            second_score = initial_results[1].get("score", 0.0)
            if top_score >= 0.85 and (top_score - second_score) >= 0.15:
                strong_signal = True
                logger.info(
                    "Strong signal detected: top=%.3f, second=%.3f -> skipping LLM expansion",
                    top_score,
                    second_score,
                )

        # ── Step 1: Query expansion via LLM (skip if strong signal) ───────
        fts_queries = [request.query]
        vec_queries = [request.query]
        reranker = None

        if not strong_signal:
            try:
                reranker = get_reranker()
                loop = asyncio.get_event_loop()
                expanded = await loop.run_in_executor(
                    None,
                    reranker.expand_query,
                    request.query,
                    True,  # include_lexical=True for query
                )
                # expanded is now {"lex": [...], "vec": [...], "hyde": [...]}
                # Lex variants go to FTS only
                for v in expanded.get("lex", []):
                    if v and v.strip():
                        fts_queries.append(v)
                # Vec and hyde variants go to both FTS and Vector
                for v in expanded.get("vec", []) + expanded.get("hyde", []):
                    if v and v.strip():
                        fts_queries.append(v)
                        vec_queries.append(v)
                logger.info(
                    "Query expansion: %d BM25 queries, %d vector queries (%.1fs)",
                    len(fts_queries),
                    len(vec_queries),
                    time.perf_counter() - t0,
                )
            except Exception as exp_err:
                logger.warning(
                    "Query expansion failed (%s), using original query only", exp_err
                )
        else:
            logger.info("Skipping LLM expansion due to strong signal")

        # ── Steps 2 + 3: Multi-query BM25 + vector → ranked id lists ─────
        t1 = time.perf_counter()
        k = 60
        ranked_lists: List[List[str]] = []  # each element: [doc_id, ...] in rank order
        weights_list: List[float] = []
        doc_info: Dict[str, Dict[str, Any]] = {}

        # Track: doc_id -> {rrf_score, top_rank} for top-rank bonus
        doc_rank_tracking: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"score": 0.0, "top_rank": math.inf}
        )

        # BM25 searches (original query → weight 2.0; expanded → weight 1.0)
        for i, q in enumerate(fts_queries):
            results = hybrid.fts.search(q, limit=limit * 3, collection=col)
            if results:
                ids = [f"{r['collection']}:{r['path']}" for r in results]
                ranked_lists.append(ids)
                weights_list.append(2.0 if i == 0 else 1.0)
                for rank, r in enumerate(results):  # 0-indexed rank
                    did = f"{r['collection']}:{r['path']}"
                    if did not in doc_info:
                        doc_info[did] = {
                            "title": r.get("title", ""),
                            "collection": r["collection"],
                            "path": r["path"],
                            "content": r.get("content", ""),
                            "type": "fts",
                            "fts_score": r.get("score", 0.0),
                        }
                    # Track top rank
                    if rank < doc_rank_tracking[did]["top_rank"]:
                        doc_rank_tracking[did]["top_rank"] = rank

        # Vector searches (original query → weight 2.0; expanded → weight 1.0)
        for i, q in enumerate(vec_queries):
            v_results = vsearcher.search(q, collection_name=col, limit=limit * 3)
            if v_results:
                ids = [f"{r.collection}:{r.path}" for r in v_results]
                ranked_lists.append(ids)
                weights_list.append(2.0 if i == 0 else 1.0)
                for rank, r in enumerate(v_results):  # 0-indexed rank
                    did = f"{r.collection}:{r.path}"
                    if did not in doc_info:
                        doc_info[did] = {
                            "title": r.title,
                            "collection": r.collection,
                            "path": r.path,
                            "content": r.body,
                            "type": "vector",
                            "vec_score": r.score,
                        }
                    else:
                        doc_info[did]["type"] = "hybrid"
                        doc_info[did]["vec_score"] = r.score
                    # Track top rank
                    if rank < doc_rank_tracking[did]["top_rank"]:
                        doc_rank_tracking[did]["top_rank"] = rank

        logger.info("BM25+vector search: %.1fs", time.perf_counter() - t1)

        if not doc_info:
            return QueryResponse(results=[])

        # ── Step 4: Weighted Reciprocal Rank Fusion with top-rank bonus ────
        t2 = time.perf_counter()
        for ids, w in zip(ranked_lists, weights_list):
            for rank, did in enumerate(ids):  # 0-indexed rank
                # RRF formula: w / (k + rank + 1)
                doc_rank_tracking[did]["score"] += w / (k + rank + 1)

        # Apply top-rank bonus (TS implementation)
        for did, entry in doc_rank_tracking.items():
            top_rank = entry["top_rank"]
            if top_rank == 0:
                entry["score"] += 0.05  # Rank 0 gets +0.05
            elif top_rank <= 2:
                entry["score"] += 0.02  # Ranks 1-2 get +0.02

        # Sort by RRF score and get top 40
        sorted_docs = sorted(
            doc_rank_tracking.items(), key=lambda x: x[1]["score"], reverse=True
        )[:40]

        rrf_ordered = []
        for rrf_rank, (did, entry) in enumerate(sorted_docs):
            rrf_ordered.append(
                {
                    "id": did,
                    "score": entry["score"],  # RRF cumulative score
                    "_rrf_rank": rrf_rank + 1,  # 1-indexed for display
                    "_top_rank": entry["top_rank"],  # Track best rank
                    **doc_info[did],
                }
            )
        logger.info(
            "RRF fusion: %.1fs, %d candidates",
            time.perf_counter() - t2,
            len(rrf_ordered),
        )

        # ── Step 5: LLM cross-encoder reranking ─────────────────────────
        # Only rerank top-10 by RRF to limit latency; tail docs keep RRF order.
        RERANK_TOP_N = 10
        if reranker is not None and rrf_ordered:
            try:
                t3 = time.perf_counter()
                rerank_candidates = rrf_ordered[:RERANK_TOP_N]
                loop = asyncio.get_event_loop()
                reranked = await loop.run_in_executor(
                    None,
                    reranker.rerank,
                    request.query,
                    rerank_candidates,
                    len(rerank_candidates),
                )
                # Append tail docs (beyond RERANK_TOP_N) in original RRF order
                reranked_ids = {d["id"] for d in reranked}
                for doc in rrf_ordered[RERANK_TOP_N:]:
                    if doc["id"] not in reranked_ids:
                        reranked.append(doc)
                logger.info(
                    "Reranking %d docs: %.1fs",
                    len(rerank_candidates),
                    time.perf_counter() - t3,
                )

                # ── Step 6: Position-aware score blending (TS-style) ────────
                # TS uses 1/rrfRank (position-based), not cumulative RRF score
                rrf_rank_map = {c["id"]: c["_rrf_rank"] for c in rrf_ordered}
                final = []
                for doc in reranked:
                    rrf_rank = rrf_rank_map.get(doc.get("id", ""), 30)
                    # Use 1/rrfRank instead of cumulative score
                    rrf_position_score = 1.0 / rrf_rank if rrf_rank > 0 else 1.0
                    # rerank_score is P(yes) in [0,1]
                    norm_rerank = float(doc.get("rerank_score", 0.5))
                    # Weight towards RRF for top positions (trust retrieval rank more)
                    if rrf_rank <= 3:
                        w_rrf = 0.75
                    elif rrf_rank <= 10:
                        w_rrf = 0.60
                    else:
                        w_rrf = 0.40
                    blended = w_rrf * rrf_position_score + (1.0 - w_rrf) * norm_rerank
                    clean = {
                        key: val for key, val in doc.items() if not key.startswith("_")
                    }
                    final.append({**clean, "score": blended})

                # ── Step 7: Deduplication by file path ─────────────────────
                seen_files: set = set()
                deduped = []
                for doc in final:
                    file_key = (doc.get("collection", ""), doc.get("path", ""))
                    if file_key not in seen_files:
                        seen_files.add(file_key)
                        deduped.append(doc)
                    else:
                        logger.debug(f"Duplicate removed: {file_key}")

                deduped.sort(key=lambda x: x["score"], reverse=True)
                logger.info(
                    "Query pipeline complete: %d results (expanded+reranked+deduped %d->%d)",
                    len(deduped[:limit]),
                    len(final),
                    len(deduped),
                )
                return QueryResponse(results=deduped[:limit])
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


@router.post("/expand", response_model=ExpandResponse)
async def expand(request: ExpandRequest):
    """Query expansion using local LLM (Qwen2.5-0.5B-Instruct).

    Returns typed expansion: {"lex": [...], "vec": [...], "hyde": [...]}
    - lex: lexical variants (synonyms, spelling variations) - for BM25 only
    - vec: semantic variants (paraphrases) - for both BM25 and Vector
    - hyde: hypothetical document - for both BM25 and Vector
    """
    try:
        reranker = get_reranker()
        expanded = reranker.expand_query(request.query, include_lexical=True)
        # For backward compatibility with API, flatten all variants into a list
        all_queries = []
        for variants in expanded.values():
            all_queries.extend(variants)
        return ExpandResponse(queries=all_queries)
    except Exception as e:
        logger.error(f"Query expansion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """LLM reranking using cross-encoder (Qwen3-Reranker-0.6B)."""
    if not request.documents:
        return RerankResponse(results=[])
    try:
        reranker = get_reranker()
        results = reranker.rerank(request.query, request.documents, top_k=request.top_k)
        return RerankResponse(results=results)
    except Exception as e:
        logger.error(f"Reranking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""
FastAPI application for QMD MCP Server.

Provides HTTP endpoints for embedding generation, vector search,
hybrid search, query expansion and LLM reranking — all as
shared singleton services so every CLI client just makes HTTP requests.
"""

import asyncio
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

from qmd.server._middleware import RequestSizeLimitMiddleware
from qmd.server._state import (
    model,
    reranker,
    processing_lock,
    config,
    embed_job_lock,
    DEFAULT_MODEL,
)
from qmd.server._endpoints import router
from qmd.llm.engine import (
    EMBEDDING_MODEL_NAME,
    JINA_ZH_PROVIDERS,
    _register_jina_zh,
)

if TYPE_CHECKING:
    from qmd.models.config import AppConfig

import logging

logger = logging.getLogger(__name__)


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
        import qmd.server._state as _state_mod

        # Register torch/lib DLL directory on Windows BEFORE any onnxruntime CUDA
        # session is created. fastembed-gpu triggers onnxruntime CUDA init, which
        # needs cufftw64_11.dll from torch/lib. Must happen before fastembed import.
        try:
            import os, torch
            if os.name == "nt":
                import pathlib
                torch_lib = pathlib.Path(torch.__file__).parent / "lib"
                if torch_lib.exists():
                    os.add_dll_directory(str(torch_lib))
                    logger.info(f"Registered DLL directory: {torch_lib}")
        except ImportError:
            pass  # torch not installed, skip

        try:
            from qmd.models.config import AppConfig

            _state_mod.config = AppConfig.load()
            _state_mod.embed_job_lock = asyncio.Lock()

            if DEFAULT_MODEL == EMBEDDING_MODEL_NAME:
                _register_jina_zh()
                providers = JINA_ZH_PROVIDERS
            else:
                providers = None

            from fastembed import TextEmbedding as TextEmbedding

            logger.info(
                f"Loading embed model: {DEFAULT_MODEL} (providers: {providers})"
            )
            load_kwargs = dict(model_name=DEFAULT_MODEL)
            if providers:
                load_kwargs["providers"] = providers

            _state_mod.model = TextEmbedding(**load_kwargs)
            _state_mod.processing_lock = asyncio.Lock()
            logger.info("Embed model loaded successfully")

            # Warm up reranker (cross-encoder) + query expansion model
            logger.info("Warming up reranker and query expansion models...")
            from qmd.server._endpoints import get_reranker
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, get_reranker)
            logger.info("All models warmed up, server ready")

        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down server")

    # Include all API endpoints
    app.include_router(router)

    return app


# Create the app instance
app = create_app()

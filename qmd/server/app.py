"""
FastAPI application for QMD MCP Server.

Provides HTTP endpoints for embedding generation with a single
model instance shared across all requests via queue-based processing.

设计目标:
- 单例模型：只有一个模型实例在显存中 (2-4GB)
- 队列模式：所有 embed 请求串行处理，避免并发显存爆炸
- 适合 4GB/6GB VRAM 用户
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from typing import List, Optional
import logging

from qmd.server.models import EmbedRequest, EmbedResponse, HealthResponse

logger = logging.getLogger(__name__)

# Global singleton model and processing lock
_model = None
_processing_lock: Optional[asyncio.Lock] = None

# Model configuration
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="QMD MCP Server",
        description="Embedding service for QMD with shared model instance (queue-based)",
        version="1.0.0",
    )

    @app.on_event("startup")
    async def startup_event():
        """Initialize model and lock on startup."""
        global _model, _processing_lock
        try:
            from fastembed import TextEmbedding

            logger.info(f"Loading model: {DEFAULT_MODEL}")
            _model = TextEmbedding(model_name=DEFAULT_MODEL)
            _processing_lock = asyncio.Lock()
            logger.info("Model loaded successfully (single instance)")
            logger.info("Queue-based processing: requests will be serialized")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down server")

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy" if _model is not None else "unhealthy",
            model_loaded=_model is not None,
        )

    @app.post("/embed", response_model=EmbedResponse)
    async def embed(request: EmbedRequest):
        """
        Generate embeddings for a list of texts.

        使用 asyncio.Lock 实现真正的串行处理:
        - 多个请求同时到来时，会排队等待
        - 同一时刻只有一个请求在处理模型
        - 避免并发导致显存爆炸
        """
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        # Validate input
        if not request.texts:
            raise HTTPException(status_code=400, detail="Empty texts list")

        if len(request.texts) > 1000:
            raise HTTPException(
                status_code=413, detail=f"Too many texts ({len(request.texts)} > 1000)"
            )

        try:
            # 使用 Lock 实现真正的串行处理
            async with _processing_lock:
                logger.debug(
                    f"Processing {len(request.texts)} texts (queue position: serialized)"
                )
                embeddings_list = await process_embeddings(request.texts)

            return EmbedResponse(embeddings=embeddings_list)

        except ValueError as e:
            logger.error(f"Invalid input: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            logger.error(f"Model processing error: {e}")
            raise HTTPException(status_code=500, detail="Embedding processing failed")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

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
    # 注意: _model.embed 是同步调用，但我们已经在 Lock 保护下
    embeddings = list(_model.embed(texts))

    # Convert numpy arrays to lists for JSON serialization
    return [emb.tolist() for emb in embeddings]


# Create the app instance
app = create_app()

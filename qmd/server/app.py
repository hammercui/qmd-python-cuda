"""
FastAPI application for QMD MCP Server.

Provides HTTP endpoints for embedding generation with a single
model instance shared across all requests.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from typing import List, Optional
import logging

from qmd.server.models import EmbedRequest, EmbedResponse, HealthResponse

logger = logging.getLogger(__name__)

# Global singleton model and queue
_model = None
_queue: Optional[asyncio.Queue] = None

# Model configuration
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
MAX_QUEUE_SIZE = 100  # Prevent memory overflow


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="QMD MCP Server",
        description="Embedding service for QMD with shared model instance",
        version="1.0.0"
    )
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize model and queue on startup."""
        global _model, _queue
        try:
            from fastembed import TextEmbedding
            
            logger.info(f"Loading model: {DEFAULT_MODEL}")
            _model = TextEmbedding(model_name=DEFAULT_MODEL)
            _queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
            logger.info("Model loaded successfully")
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
            model_loaded=_model is not None
        )
    
    @app.post("/embed", response_model=EmbedResponse)
    async def embed(request: EmbedRequest):
        """
        Generate embeddings for a list of texts.
        
        Processes requests through a queue to avoid concurrency issues.
        """
        if _model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        # Validate input
        if not request.texts:
            raise HTTPException(status_code=400, detail="Empty texts list")
        
        if len(request.texts) > 1000:
            raise HTTPException(
                status_code=413, 
                detail=f"Too many texts ({len(request.texts)} > 1000)"
            )
        
        try:
            # Queue the request to avoid concurrent access
            await _queue.put(request.texts)
            
            # Process embeddings
            embeddings_list = await process_embeddings(request.texts)
            
            # Mark as complete
            await _queue.get()
            
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
    embeddings = list(_model.embed(texts))
    
    # Convert numpy arrays to lists for JSON serialization
    return [emb.tolist() for emb in embeddings]


# Create the app instance
app = create_app()

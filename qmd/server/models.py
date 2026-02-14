"""Request/Response models for MCP Server API."""

from pydantic import BaseModel
from typing import List


class EmbedRequest(BaseModel):
    """Request model for embedding generation."""
    texts: List[str]


class EmbedResponse(BaseModel):
    """Response model for embedding generation."""
    embeddings: List[List[float]]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool

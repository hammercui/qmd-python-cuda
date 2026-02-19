"""Request/Response models for MCP Server API."""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class EmbedRequest(BaseModel):
    """Request model for embedding generation."""
    texts: List[str]


class EmbedResponse(BaseModel):
    """Response model for embedding generation."""
    embeddings: List[List[float]]


class VSearchRequest(BaseModel):
    """Request model for vector semantic search."""
    query: str
    limit: int = 10
    min_score: float = 0.3
    collection: Optional[str] = None


class VSearchResponse(BaseModel):
    """Response model for vector search."""
    results: List[Dict[str, Any]]


class QueryRequest(BaseModel):
    """Request model for hybrid search with LLM query expansion."""
    query: str
    limit: int = 10
    min_score: float = 0.0
    collection: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for hybrid search."""
    results: List[Dict[str, Any]]


class ExpandRequest(BaseModel):
    """Request model for query expansion."""
    query: str


class ExpandResponse(BaseModel):
    """Response model for query expansion."""
    queries: List[str]


class RerankRequest(BaseModel):
    """Request model for LLM reranking."""
    query: str
    documents: List[Dict[str, Any]]
    top_k: int = 5


class RerankResponse(BaseModel):
    """Response model for LLM reranking."""
    results: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    reranker_loaded: bool = False
    queue_size: int = 0

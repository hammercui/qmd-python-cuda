"""
LLM Engine for generating embeddings.

Supports two modes:
1. Standalone: Load model locally (default for high VRAM)
2. Server: Use MCP Server for low VRAM systems
"""

from typing import List, Optional, Union
from pathlib import Path
import logging

from qmd.models.downloader import ModelDownloader

logger = logging.getLogger(__name__)


class LLMEngine:
    """
    LLM Engine for generating embeddings.
    Supports both local model loading and MCP server client modes.
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: Optional[str] = None,
        threads: Optional[int] = None,
        local_model_path: Optional[Path] = None,
        mode: str = "auto",
        server_url: str = "http://localhost:8000"
    ):
        """
        Args:
            model_name: HuggingFace model ID or path
            cache_dir: FastEmbed cache directory
            threads: Number of threads for embedding
            local_model_path: Local path to model (overrides download)
            mode: Operation mode - "auto", "standalone", or "server"
            server_url: URL of MCP server (used in server mode)
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.threads = threads
        self.local_model_path = local_model_path
        self.server_url = server_url
        
        # Detect and set mode
        self.mode = self._detect_mode(mode)
        logger.info(f"LLMEngine mode: {self.mode}")
        
        # Initialize based on mode
        from fastembed import TextEmbedding
        from qmd.server.client import EmbedServerClient
        
        self._model: Optional[TextEmbedding] = None
        self._downloader: Optional[ModelDownloader] = None
        self._client: Optional[EmbedServerClient] = None
        
        if self.mode == "server":
            self._init_client()
        else:
            # Lazy load model in standalone mode
            pass
    
    def _detect_mode(self, mode: str) -> str:
        """
        Auto-detect best mode based on system VRAM.
        
        Returns:
            "standalone" or "server"
        """
        if mode != "auto":
            return mode
        
        # Auto-detect based on VRAM
        try:
            import torch
            if torch.cuda.is_available():
                total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
                logger.info(f"Detected {total_gb:.1f}GB VRAM")
                
                # Use server mode if VRAM < 8GB
                if total_gb < 8:
                    logger.info("Low VRAM detected, using server mode")
                    return "server"
                else:
                    logger.info("Sufficient VRAM, using standalone mode")
                    return "standalone"
            else:
                logger.info("No CUDA detected, using standalone mode")
                return "standalone"
        except Exception as e:
            logger.warning(f"VRAM detection failed: {e}, using standalone")
            return "standalone"
    
    def _init_client(self) -> None:
        """Initialize MCP server client."""
        from qmd.server.client import EmbedServerClient
        self._client = EmbedServerClient(base_url=self.server_url)
        
        # Health check
        if self._client.health_check():
            logger.info(f"Connected to MCP server at {self.server_url}")
        else:
            logger.warning(f"MCP server not available at {self.server_url}")
            self._client = None
    
    def _ensure_model(self) -> None:
        """Load model if not already loaded (standalone mode)."""
        if self._model is not None:
            return

        # Determine model path (local > cached > download)
        model_path = self.model_name

        if self.local_model_path and self.local_model_path.exists():
            # Use local path
            model_path = str(self.local_model_path)
        else:
            # Try to use downloader to get cached path
            if self._downloader is None:
                self._downloader = ModelDownloader()

            cached_path = self._downloader.get_model_path("embedding")
            if cached_path:
                model_path = str(cached_path)

        # Load model
        from fastembed import TextEmbedding
        self._model = TextEmbedding(
            model_name=model_path,
            cache_dir=self.cache_dir,
            threads=self.threads
        )
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of embedding vectors
        """
        if self.mode == "server" and self._client is not None:
            # Try server mode
            result = self._client.embed_texts(texts)
            if result is not None:
                return result
            else:
                # Server unavailable, fallback to standalone
                logger.warning("MCP server unavailable, falling back to standalone")
                self.mode = "standalone"
                self._client = None
        
        # Standalone mode (local model)
        self._ensure_model()
        assert self._model is not None
        
        # fastembed returns an iterator of numpy arrays
        embeddings = list(self._model.embed(texts))
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            text: Query string
            
        Returns:
            Embedding vector
        """
        return self.embed_texts([text])[0]
    
    def close(self) -> None:
        """Cleanup resources."""
        if self._client is not None:
            self._client.close()

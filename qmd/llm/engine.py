"""
LLM Engine for generating embeddings.

Supports three modes:
1. Standalone: Load model locally (default, best performance)
2. Server: Use MCP Server (for multi-process shared model)
3. Auto: Automatically detect (default: standalone)

When to use each mode:
- standalone: Best performance, each process loads its own model
- server: When running multiple concurrent qmd commands,
          start 'qmd server' first to share one model instance
- auto: Uses standalone by default, unless explicitly configured
"""

from typing import List, Optional, Union
from pathlib import Path
import logging
import os

from qmd.models.downloader import ModelDownloader

logger = logging.getLogger(__name__)

# Environment variable to force server mode in auto
FORCE_SERVER_MODE_ENV = "QMD_FORCE_SERVER"


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
        server_url: str = "http://localhost:8000",
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

        Mode selection logic:
        - "standalone": Always use local model (best performance, needs 8GB+ VRAM)
        - "server": Always use MCP Server (for 4GB/6GB VRAM, shared model + queue)
        - "auto": Auto-detect based on VRAM:
            - VRAM < 8GB → server (避免显存爆炸)
            - VRAM >= 8GB → standalone (最佳性能)
            - No CUDA → standalone (CPU mode)

        设计目标:
        - 4GB/6GB VRAM 用户 → 默认 server 模式，共享模型
        - 8GB+ VRAM 用户 → 默认 standalone，最佳性能
        - 用户可手动 override: --mode standalone 或 --mode server
        """
        if mode != "auto":
            return mode

        # Check environment variable for forced server mode
        if os.environ.get(FORCE_SERVER_MODE_ENV, "").lower() in ("1", "true", "yes"):
            logger.info("QMD_FORCE_SERVER env detected, using server mode")
            return "server"

        # Auto-detect based on VRAM
        try:
            import torch

            if torch.cuda.is_available():
                total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
                free_gb = (
                    torch.cuda.get_device_properties(0).total_memory
                    - torch.cuda.memory_allocated(0)
                ) / 1e9

                logger.info(f"Detected {total_gb:.1f}GB VRAM (~{free_gb:.1f}GB free)")

                # VRAM < 8GB: Use server mode (avoid OOM)
                if total_gb < 8:
                    logger.info("Low VRAM (<8GB), using server mode (shared model)")
                    return "server"
                else:
                    logger.info("Sufficient VRAM (>=8GB), using standalone mode")
                    return "standalone"
            else:
                logger.info("No CUDA detected, using standalone mode")
                return "standalone"
        except Exception as e:
            logger.warning(f"VRAM detection failed: {e}, defaulting to server (safer)")
            return "server"

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
            model_name=model_path, cache_dir=self.cache_dir, threads=self.threads
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

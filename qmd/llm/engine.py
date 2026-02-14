from typing import List, Optional
from pathlib import Path
import numpy as np

from fastembed import TextEmbedding
from qmd.models.downloader import ModelDownloader

class LLMEngine:
    """
    LLM Engine for generating embeddings.
    Uses fastembed as a high-performance backend.
    """
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: Optional[str] = None,
        threads: Optional[int] = None,
        local_model_path: Optional[Path] = None
    ):
        """
        Args:
            model_name: HuggingFace model ID or path
            cache_dir: FastEmbed cache directory
            threads: Number of threads for embedding
            local_model_path: Local path to model (overrides download)
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.threads = threads
        self.local_model_path = local_model_path
        self._model: Optional[TextEmbedding] = None
        self._downloader: Optional[ModelDownloader] = None

    def _ensure_model(self):
        """Load the model if not already loaded."""
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
        self._model = TextEmbedding(
            model_name=model_path,
            cache_dir=self.cache_dir,
            threads=self.threads
        )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        self._ensure_model()
        assert self._model is not None
        
        # fastembed returns an iterator of numpy arrays
        embeddings = list(self._model.embed(texts))
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single query."""
        return self.embed_texts([text])[0]

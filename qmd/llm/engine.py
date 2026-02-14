from typing import List, Optional
import numpy as np
from fastembed import TextEmbedding

class LLMEngine:
    """
    LLM Engine for generating embeddings.
    Uses fastembed as a high-performance backend.
    """
    def __init__(
        self, 
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: Optional[str] = None,
        threads: Optional[int] = None
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.threads = threads
        self._model: Optional[TextEmbedding] = None

    def _ensure_model(self):
        """Load the model if not already loaded."""
        if self._model is not None:
            return

        self._model = TextEmbedding(
            model_name=self.model_name,
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

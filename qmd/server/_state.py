"""Global state and configuration for QMD server."""

import asyncio
import dataclasses
import logging
from typing import Optional, TYPE_CHECKING

from rich.console import Console as RichConsole

if TYPE_CHECKING:
    from qmd.models.config import AppConfig

logger = logging.getLogger(__name__)

# Server-side console for progress output
srv_console = RichConsole(stderr=False)

# Global singletons
model = None
reranker = None
processing_lock: Optional[asyncio.Lock] = None
config: Optional["AppConfig"] = None
vector_search = None
hybrid_search = None
embed_job_lock: Optional[asyncio.Lock] = None

# Model configuration
DEFAULT_MODEL = (
    "jinaai/jina-embeddings-v2-base-zh-q4f16"  # Jina v2 ZH INT8 ONNX (Xenova), 768d
)

# GPU batch size for embedding inference.
# Jina v2 ZH quantized (768d): a batch of 16 x 3200-char chunks uses ~200 MB VRAM.
# Much lighter than BGE-M3; can be increased on higher-VRAM GPUs.
GPU_EMBED_BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Server-side embedding job state
# Only one embed job runs at a time; multiple CLI clients can attach via SSE.
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class EmbedJobState:
    """State for the server-side embedding job."""

    running: bool = False
    collection: Optional[str] = None
    force: bool = False
    total_chunks: int = 0
    done_chunks: int = 0
    total_docs: int = 0
    done_docs: int = 0
    error: Optional[str] = None
    finished: bool = False
    _queues: list = dataclasses.field(default_factory=list)


# Global embed job instance
embed_job: EmbedJobState = EmbedJobState()


def reset_embed_job() -> None:
    """Reset embed job state for a new job."""
    global embed_job
    embed_job = EmbedJobState()

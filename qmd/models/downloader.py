"""
Smart model downloader with geographic source detection.

Features:
- Auto-detect China/Overseas location
- Use ModelScope (default, China) or HuggingFace (overseas)
- Configurable source in config file
- Rich progress bars
- Local caching at ~/.cache/qmd/models/
"""

import os
from pathlib import Path
from typing import Optional, Dict, List
import shutil

try:
    from rich.console import Console
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from qmd.models.config import AppConfig


def _detect_location() -> str:
    """
    Detect if running in China or Overseas.

    Returns: 'cn' for China, 'global' for overseas
    """
    try:
        import requests

        # Try to detect via timezone first (faster)
        import time
        import datetime

        # Get timezone
        if hasattr(time, "tz"):
            tz = time.tzname
            if tz and "Asia/Shanghai" in tz:
                return "cn"
            if tz and (
                "Asia/Beijing" in tz or "Asia/Chongqing" in tz or "Asia/Harbin" in tz
            ):
                return "cn"

        # Fallback: Check via IP (slower)
        try:
            response = requests.get("http://ip-api.com/json/", timeout=3)
            if response.status_code == 200:
                data = response.json()
                country = data.get("country_code", "").upper()
                if country == "CN":
                    return "cn"
        except:
            pass

    except Exception:
        pass

    # Default: Assume China for faster downloads for Chinese users
    return "cn"


class ModelDownloader:
    """Parallel downloader supporting both HF and ModelScope."""

    # Model definitions
    MODELS = {
        "embedding": {
            "hf": "Xenova/jina-embeddings-v2-base-zh",
            "ms": "Xenova/jina-embeddings-v2-base-zh",
            "size_mb": 161,                                    # model_int8.onnx ~161 MB
            "type": "onnx-int8",
            "model_file": "onnx/model_int8.onnx",
            "additional_files": [],
            "dim": 768,                                        # 向量维度 Jina v2 ZH
        },
        "reranker": {
            "hf": "thomasht86/Qwen3-Reranker-0.6B-int8-ONNX",
            "ms": "thomasht86/Qwen3-Reranker-0.6B-int8-ONNX",
            "size_mb": 600,
            "type": "onnx-reranker",
            "model_file": "model.onnx",                       # 根目录，无 onnx/ 子目录
        },
        "expansion": {
            "hf": "onnx-community/Qwen3-0.6B-ONNX",
            "ms": "onnx-community/Qwen3-0.6B-ONNX",
            "size_mb": 544,
            "type": "onnx-causal-lm",
            "model_file": "onnx/model_q4f16.onnx",  # INT4 weights + FP16 activations, GPU-native
        },
    }

    def __init__(
        self, cache_dir: Optional[Path] = None, model_source: Optional[str] = None
    ):
        """
        Args:
            cache_dir: Custom cache directory (default: ~/.cache/qmd/models/)
            model_source: 'auto' (detect), 'huggingface', 'modelscope'
        """
        if cache_dir is None:
            home = Path.home()
            cache_dir = home / ".qmd" / "models"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.console = Console() if RICH_AVAILABLE else None

        # Determine download source
        if model_source is None:
            # Load from config
            try:
                config = AppConfig.load()
                model_source = config.model_source
            except:
                model_source = "auto"

        self.model_source = model_source

    def _download_from_hf(
        self, model_name: str, local_path: Path, progress=None, task=None
    ) -> bool:
        """Download from HuggingFace."""
        try:
            from huggingface_hub import snapshot_download

            if self.console and progress and task:
                progress.update(
                    task, description=f"[cyan][HF] Downloading {model_name}..."
                )

            # Download model files
            snapshot_download(
                repo_id=model_name, local_dir=local_path, local_dir_use_symlinks=False
            )

            if self.console and progress and task:
                progress.update(task, completed=100)
                self.console.print(f"[green][HF] OK Downloaded to {local_path}[/green]")
            return True
        except Exception as e:
            if self.console and progress and task:
                self.console.print(f"[red][HF] X Failed: {e}[/red]")
            return False

    def _download_from_ms(
        self, model_name: str, local_path: Path, progress=None, task=None
    ) -> bool:
        """Download from ModelScope."""
        try:
            from modelscope.hub.api import HubApi

            if self.console and progress and task:
                progress.update(
                    task, description=f"[cyan][MoT] Downloading {model_name}..."
                )

            api = HubApi()
            # Download model to local path
            api.snapshot_download(model_name, cache_dir=str(local_path.parent))

            # Move to exact path if needed
            downloaded_path = local_path.parent / model_name.replace("/", "--")
            if downloaded_path != local_path and downloaded_path.exists():
                shutil.move(str(downloaded_path), str(local_path))

            if self.console and progress and task:
                progress.update(task, completed=100)
                self.console.print(
                    f"[green][MoT] OK Downloaded to {local_path}[/green]"
                )
            return True
        except Exception as e:
            if self.console and progress and task:
                self.console.print(f"[red][MoT] X Failed: {e}[/red]")
            return False

    def _select_source(self, model_key: str) -> str:
        """Select download source based on location and config."""
        model_info = self.MODELS[model_key]

        # Explicit source specified (accept both short and long names)
        if self.model_source in ["huggingface", "hf"]:
            return model_info["hf"]
        if self.model_source in ["modelscope", "ms"]:
            return model_info["ms"]

        # Auto-detect location
        location = _detect_location()

        if location == "cn":
            # China: Use ModelScope
            if self.console:
                self.console.print(
                    f"[dim]Detected location: China - Using ModelScope[/dim]"
                )
            return model_info["ms"]
        else:
            # Overseas: Use HuggingFace
            if self.console:
                self.console.print(
                    f"[dim]Detected location: Overseas - Using HuggingFace[/dim]"
                )
            return model_info["hf"]

    def _parallel_download(self, model_key: str, force: bool = False) -> Optional[Path]:
        """Download model from selected source (HF or ModelScope)."""
        if model_key not in self.MODELS:
            raise ValueError(f"Unknown model: {model_key}")

        model_info = self.MODELS[model_key]
        model_name = model_info["type"] + "_" + model_key  # e.g., "embedding_reranker"
        local_path = self.cache_dir / model_name

        # Check if already exists
        if local_path.exists() and not force:
            if self.console:
                self.console.print(
                    f"[green]OK Model already cached: {local_path}[/green]"
                )
            return local_path

        # Select source based on location
        source = self._select_source(model_key)

        if self.console:
            source_name = (
                "ModelScope" if "modelscope" in source.lower() else "HuggingFace"
            )
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console,
            ) as progress:
                task = progress.add_task(
                    f"[cyan][{source_name}] Downloading {model_key}...", total=100
                )

                # Try to download from selected source
                if "modelscope" in source.lower():
                    success = self._download_from_ms(source, local_path, progress, task)
                else:
                    success = self._download_from_hf(source, local_path, progress, task)

                if success:
                    return local_path

        # Fallback without rich
        else:
            if "modelscope" in source.lower():
                if self._download_from_ms(source, local_path, None, None):
                    return local_path
            else:
                if self._download_from_hf(source, local_path, None, None):
                    return local_path

        self.console.print(
            f"[red]X Download failed for {model_key}[/red]"
            if self.console
            else f"Failed to download {model_key}"
        )
        return None

    def download_all(self, force: bool = False) -> Dict[str, Optional[Path]]:
        """Download all required models.

        Args:
            force: Re-download even if cached

        Returns:
            Dict mapping model_key -> local_path or None if failed
        """
        results = {}

        if self.console:
            self.console.print(f"[bold yellow]Starting model download...[/bold yellow]")
            self.console.print(f"[dim]Cache directory: {self.cache_dir}[/dim]")

        for model_key in ["embedding", "reranker", "expansion"]:
            results[model_key] = self._parallel_download(model_key, force)

            if results[model_key] is None:
                if self.console:
                    self.console.print(f"[red]X Failed to download {model_key}[/red]")

        if self.console:
            self.console.print(f"[bold green]Download complete![/bold green]")
            successful = sum(1 for p in results.values() if p is not None)
            self.console.print(
                f"[dim]Successfully downloaded: {successful}/3 models[/dim]"
            )

        return results

    def get_model_path(self, model_key: str) -> Optional[Path]:
        """Get cached model path without downloading.

        Returns directory path only if the expected ONNX model file exists.
        """
        model_info = self.MODELS[model_key]
        model_dir_name = model_info["type"] + "_" + model_key
        local_path = self.cache_dir / model_dir_name
        if not local_path.exists() or not local_path.is_dir():
            return None

        # Verify the expected ONNX file actually exists
        expected_file = model_info.get("model_file")
        if expected_file and not (local_path / expected_file).exists():
            return None

        return local_path

    def check_availability(self) -> Dict[str, bool]:
        """Check which models are already cached."""
        return {
            model_key: self.get_model_path(model_key) is not None
            for model_key in self.MODELS.keys()
        }


def download_models_command():
    """CLI command for downloading models."""
    downloader = ModelDownloader()
    downloader.download_all()


if __name__ == "__main__":
    download_models_command()

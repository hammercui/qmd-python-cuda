"""
Download GGUF embedding models from HuggingFace or ModelScope.

Supports:
- lm-sys/FastEmbed-gemma-2b (gemma-2b-quantized.gguf)
- Other GGUF embedding models
"""

import os
import sys
from pathlib import Path
import hashlib
from typing import Optional
import requests


# Model configurations
MODELS = {
    "gemma-300m-q8": {
        "repo_id": "unsloth/embeddinggemma-300m-GGUF",
        "filename": "embeddinggemma-300M-Q8_0.gguf",
        "size_mb": 340,  # Expected size
        "description": "Gemma 300M Q8 quantized embedding model",
    },
    "bge-small-en": {
        "repo_id": "ChristianAzinn/bge-small-en-v1.5-gguf",
        "filename": "bge-small-en-v1.5-Q8_0.gguf",
        "size_mb": 130,
        "description": "BGE Small English v1.5 Q8 quantized",
    },
    "qwen-embedding-0.6b": {
        "repo_id": "Qwen/Qwen3-Embedding-0.6B-GGUF",
        "filename": "qwen3-embedding-0.6b-q8_0.gguf",
        "size_mb": 600,
        "description": "Qwen3 Embedding 0.6B Q8 quantized",
    },
}


def get_download_urls(repo_id: str, filename: str) -> dict:
    """
    Get download URLs from different sources.

    Returns:
        Dict with 'huggingface' and 'modelscope' URLs
    """
    urls = {}

    # HuggingFace URL
    urls["huggingface"] = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"

    # ModelScope URL (conversion pattern)
    # HuggingFace: org/model -> ModelScope: org/model
    urls["modelscope"] = (
        f"https://www.modelscope.cn/api/v1/models/{repo_id}/repo?path={filename}"
    )

    return urls


def download_file(
    url: str,
    destination: Path,
    expected_size_mb: Optional[int] = None,
    show_progress: bool = True,
) -> bool:
    """
    Download file with progress bar.

    Args:
        url: Download URL
        destination: Destination path
        expected_size_mb: Expected file size in MB (for validation)
        show_progress: Show progress bar

    Returns:
        True if successful
    """
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192
        downloaded = 0

        print(f"Downloading to: {destination}")
        print(f"File size: {total_size / (1024**2):.1f} MB")

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if show_progress and total_size > 0:
                        percent = downloaded / total_size * 100
                        mb_downloaded = downloaded / (1024**2)
                        bar_length = 40
                        filled = int(bar_length * downloaded / total_size)
                        bar = "█" * filled + "░" * (bar_length - filled)
                        print(
                            f"\r  [{bar}] {percent:.1f}% ({mb_downloaded:.1f} MB)",
                            end="",
                            flush=True,
                        )

        print()  # New line after progress bar

        # Validate size
        actual_size = destination.stat().st_size / (1024**2)
        if (
            expected_size_mb
            and abs(actual_size - expected_size_mb) > expected_size_mb * 0.5
        ):
            print(
                f"  WARNING: File size ({actual_size:.1f} MB) differs from expected ({expected_size_mb} MB)"
            )
            print(f"  This might indicate an incomplete download.")
            return False

        print(f"[OK] Downloaded successfully!")
        return True

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Download failed: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False


def compute_file_hash(filepath: Path, algorithm: str = "sha256") -> str:
    """Compute file hash."""
    hash_func = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def download_model(
    model_name: str,
    output_dir: Optional[Path] = None,
    source: str = "auto",
) -> Optional[Path]:
    """
    Download a GGUF model.

    Args:
        model_name: Model name (key in MODELS dict)
        output_dir: Output directory (default: ~/.qmd/models/)
        source: Download source - "auto", "huggingface", or "modelscope"

    Returns:
        Path to downloaded file, or None if failed
    """
    if model_name not in MODELS:
        print(f"[ERROR] Unknown model: {model_name}")
        print(f"Available models: {', '.join(MODELS.keys())}")
        return None

    model_info = MODELS[model_name]
    filename = model_info["filename"]

    # Set output directory
    if output_dir is None:
        output_dir = Path.home() / ".qmd" / "models"
    output_dir.mkdir(parents=True, exist_ok=True)

    destination = output_dir / filename

    # Check if already exists
    if destination.exists():
        print(f"[OK] Model already exists: {destination}")
        print(f"  Size: {destination.stat().st_size / (1024**2):.1f} MB")
        return destination

    print(f"\n{'=' * 60}")
    print(f"Model: {model_info['description']}")
    print(f"File: {filename}")
    print(f"Expected size: {model_info['size_mb']:.0f} MB")
    print(f"{'=' * 60}\n")

    # Get download URLs
    urls = get_download_urls(model_info["repo_id"], filename)

    # Determine download order
    if source == "auto":
        # Try HuggingFace first (more reliable), then ModelScope
        sources = ["huggingface", "modelscope"]
    else:
        sources = [source]

    # Try each source
    for src in sources:
        print(f"Attempting download from {src.upper()}...")
        url = urls[src]

        success = download_file(
            url,
            destination,
            expected_size_mb=model_info["size_mb"],
        )

        if success:
            # Verify file exists and is not empty
            if destination.exists() and destination.stat().st_size > 0:
                print(f"\n[SUCCESS] Model downloaded successfully!")
                print(f"  Location: {destination}")
                print(f"  Size: {destination.stat().st_size / (1024**2):.1f} MB")

                # Compute hash
                file_hash = compute_file_hash(destination)[:16]
                print(f"  SHA256: {file_hash}...")

                return destination
            else:
                print(f"\n[ERROR] Downloaded file is invalid or empty")
                destination.unlink(missing_ok=True)

        print(f"[ERROR] Failed to download from {src.upper()}")
        if src != sources[-1]:
            print(f"Trying next source...\n")

    print(f"\n[ERROR] All download sources failed")
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Download GGUF embedding models")
    parser.add_argument(
        "--model",
        type=str,
        default="gemma-300m-q8",
        choices=list(MODELS.keys()),
        help="Model to download",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: ~/.qmd/models/)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="auto",
        choices=["auto", "huggingface", "modelscope"],
        help="Download source (default: auto)",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None

    print("\n" + "=" * 60)
    print("GGUF Model Downloader")
    print("=" * 60 + "\n")

    result = download_model(
        model_name=args.model,
        output_dir=output_dir,
        source=args.source,
    )

    if result:
        print(f"\nYou can now run the benchmark with:")
        print(f'  python test_llama_embedding.py --model "{result}"')
        sys.exit(0)
    else:
        print(f"\n[ERROR] Failed to download model")
        sys.exit(1)


if __name__ == "__main__":
    main()

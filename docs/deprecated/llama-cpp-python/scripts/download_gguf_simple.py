"""
Simple GGUF model downloader without Unicode characters.
"""

import os
import sys
from pathlib import Path
import requests


MODELS = {
    "gemma-300m": {
        "url": "https://huggingface.co/unsloth/embeddinggemma-300m-GGUF/resolve/main/embeddinggemma-300M-Q8_0.gguf",
        "filename": "embeddinggemma-300M-Q8_0.gguf",
        "size_mb": 313,
    },
    "bge-small-en": {
        "url": "https://huggingface.co/ChristianAzinn/bge-small-en-v1.5-gguf/resolve/main/bge-small-en-v1.5.Q8_0.gguf",
        "filename": "bge-small-en-v1.5.Q8_0.gguf",
        "size_mb": 37,
    },
    "gte-small": {
        "url": "https://huggingface.co/ChristianAzinn/gte-small-gguf/resolve/main/gte-small.Q8_0.gguf",
        "filename": "gte-small.Q8_0.gguf",
        "size_mb": 37,
    },
    "qwen3-reranker": {
        "url": "https://huggingface.co/ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf",
        "filename": "qwen3-reranker-0.6b-q8_0.gguf",
        "size_mb": 640,
    },
}


def download_file(url: str, destination: Path) -> bool:
    """Download file with simple progress."""
    try:
        print(f"Downloading: {destination.name}")
        print(f"From: {url}")

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        block_size = 8192

        print(f"Size: {total_size / (1024**2):.1f} MB\n")

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Simple progress display
                    if total_size > 0:
                        percent = downloaded / total_size * 100
                        mb_downloaded = downloaded / (1024**2)
                        print(
                            f"\rProgress: {percent:.1f}% ({mb_downloaded:.1f} MB)",
                            end="",
                        )

        print("\n[OK] Download complete!")
        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Download GGUF models")
    parser.add_argument(
        "--model", type=str, default="gemma-300m", choices=list(MODELS.keys())
    )
    parser.add_argument("--output-dir", type=str, default=None)

    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path.home() / ".qmd" / "models"

    output_dir.mkdir(parents=True, exist_ok=True)

    model = MODELS[args.model]
    destination = output_dir / model["filename"]

    if destination.exists():
        print(f"[OK] Model already exists: {destination}")
        print(f"Size: {destination.stat().st_size / (1024**2):.1f} MB\n")
        print(f"Run benchmark:")
        print(f'  python test_llama_embedding.py --model "{destination}"')
        return

    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"File: {model['filename']}")
    print("=" * 60)
    print()

    success = download_file(model["url"], destination)

    if success and destination.exists():
        actual_size = destination.stat().st_size / (1024**2)
        print(f"\n[OK] Model saved: {destination}")
        print(f"Size: {actual_size:.1f} MB\n")

        print("Run benchmark:")
        print(f'  python test_llama_embedding.py --model "{destination}"')
    else:
        print(f"\n[ERROR] Download failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

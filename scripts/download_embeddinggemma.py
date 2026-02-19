#!/usr/bin/env python
"""
Jina Embeddings v2 Base ZH INT8 ONNX 模型下载脚本

从 Xenova/jina-embeddings-v2-base-zh 下载 INT8 变体（~161 MB）。
支持中英文混合输入，8192 token 上下文，768 维输出。

用法：
    python scripts/download_embeddinggemma.py           # 下载到默认路径
    python scripts/download_embeddinggemma.py --force   # 强制重新下载
    python scripts/download_embeddinggemma.py --check   # 仅检测，不下载
    python scripts/download_embeddinggemma.py --model-dir D:/models/jina-zh

国内加速（HF 镜像）：
    set HF_ENDPOINT=https://hf-mirror.com
    python scripts/download_embeddinggemma.py
"""

import sys
import shutil
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────────────────

REPO_ID    = "Xenova/jina-embeddings-v2-base-zh"
MODEL_NAME = "jinaai/jina-embeddings-v2-base-zh-q4f16"   # 自定义逻辑名，避免与 fastembed 内置冲突

# INT8 ONNX：~161 MB，数值稳定，支持 CUDA / CPU
REQUIRED_FILES = [
    "onnx/model_int8.onnx",
    "tokenizer.json",
    "tokenizer_config.json",
    "config.json",
    "special_tokens_map.json",
]

DEFAULT_MODEL_DIR = Path.home() / ".cache" / "qmd" / "models" / "jina-embeddings-v2-base-zh"


# ──────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────────────────────

def _file_info(path: Path) -> str:
    size = path.stat().st_size
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    elif size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def check_model(model_dir: Path) -> dict:
    """检测 INT8 模型文件完整性。"""
    results = {"complete": True, "files": {}}
    for rel_path in REQUIRED_FILES:
        full_path = model_dir / rel_path
        if full_path.exists():
            results["files"][rel_path] = {"exists": True, "size": _file_info(full_path)}
        else:
            results["files"][rel_path] = {"exists": False, "size": "-"}
            results["complete"] = False
    return results


def print_check_result(model_dir: Path, result: dict) -> None:
    print(f"模型目录 : {model_dir}")
    print(f"来源仓库 : {REPO_ID}")
    print(f"变体     : INT8 ONNX (~161 MB, 768d, 中英文)")
    print()
    print(f"{'文件':<45} {'状态':<8} {'大小'}")
    print("-" * 70)
    for rel_path, info in result["files"].items():
        status = "✅ 存在" if info["exists"] else "❌ 缺失"
        print(f"  {rel_path:<43} {status:<8} {info['size']}")
    print()
    if result["complete"]:
        print("✅ 模型完整，可以直接使用。")
    else:
        print("❌ 模型不完整，请运行下载脚本。")


# ──────────────────────────────────────────────────────────────────────────────
# 下载函数
# ──────────────────────────────────────────────────────────────────────────────

def download_model(model_dir: Path = None, force: bool = False) -> bool:
    if model_dir is None:
        model_dir = DEFAULT_MODEL_DIR
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Jina Embeddings v2 Base ZH INT8 ONNX 下载器")
    print("=" * 60)
    print(f"来源仓库 : {REPO_ID}")
    print(f"目标目录 : {model_dir}")
    print()

    result = check_model(model_dir)
    if result["complete"] and not force:
        print("✅ 模型已存在且完整，无需重新下载。")
        print()
        print_check_result(model_dir, result)
        print()
        print("提示：使用 --force 强制重新下载。")
        return True

    if force and result["complete"]:
        print("⚠️  --force 模式：清除旧 ONNX 文件后重新下载...")
        onnx_dir = model_dir / "onnx"
        if onnx_dir.exists():
            shutil.rmtree(onnx_dir)
        print()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("❌ 缺少 huggingface_hub：pip install huggingface_hub")
        return False

    print("正在下载以下文件：")
    for f in REQUIRED_FILES:
        print(f"  - {f}")
    print()
    print("⏳ 开始下载（model_int8.onnx 约 161 MB，请耐心等待）...")
    print()

    try:
        snapshot_download(
            repo_id=REPO_ID,
            allow_patterns=REQUIRED_FILES,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
        )
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        print()
        print("解决方案：")
        print("  国内镜像：set HF_ENDPOINT=https://hf-mirror.com")
        print("  代    理：set HTTPS_PROXY=http://127.0.0.1:7890")
        import traceback
        traceback.print_exc()
        return False

    print()
    print("正在验证下载的文件...")
    result = check_model(model_dir)
    print()
    print_check_result(model_dir, result)

    if not result["complete"]:
        print()
        print("❌ 部分文件缺失，请尝试 --force 重新下载。")
        return False

    # 快速推理验证
    print()
    print("正在进行推理验证（通过 fastembed 加载模型）...")
    try:
        from fastembed.text.text_embedding import TextEmbedding
        from fastembed.common.model_description import PoolingType, ModelSource

        try:
            TextEmbedding.add_custom_model(
                model=MODEL_NAME,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=REPO_ID),
                dim=768,
                model_file="onnx/model_int8.onnx",
                description="Jina Embeddings v2 Base ZH, INT8 ONNX, 768d, Chinese+English",
                size_in_gb=0.16,
            )
        except ValueError as ve:
            if "already registered" not in str(ve):
                raise

        model = TextEmbedding(
            model_name=MODEL_NAME,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        embedding = list(model.embed(["Hello! 你好世界。"]))[0]
        assert len(embedding) == 768, f"维度错误：{len(embedding)}"
        print(f"✅ 推理验证通过！维度：{len(embedding)}d")
    except ImportError:
        print("⚠️  fastembed 未安装，跳过验证。")
    except Exception as e:
        print(f"⚠️  推理验证失败（文件已下载）：{e}")

    print()
    print("=" * 60)
    print("  🎉 下载完成！")
    print("=" * 60)
    print()
    print("后续步骤：")
    print("  qmd server   # 启动嵌入服务")
    print("  qmd embed    # 为文档生成嵌入（768d）")
    print()
    return True


# ──────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="下载 Jina Embeddings v2 Base ZH INT8 ONNX 模型（中英文，768d）",
    )
    parser.add_argument("--check",     action="store_true", help="只检测，不下载")
    parser.add_argument("--force",     action="store_true", help="强制重新下载")
    parser.add_argument("--model-dir", type=str, default=None,
                        help=f"自定义保存目录（默认：{DEFAULT_MODEL_DIR}）")

    args = parser.parse_args()
    target_dir = Path(args.model_dir) if args.model_dir else DEFAULT_MODEL_DIR

    if args.check:
        result = check_model(target_dir)
        print_check_result(target_dir, result)
        sys.exit(0 if result["complete"] else 1)

    success = download_model(model_dir=target_dir, force=args.force)
    sys.exit(0 if success else 1)



import os, time

# 把 cuDNN 目录加入 PATH（必须在 import onnxruntime 之前）
os.environ["PATH"] = (
    r"C:\Program Files\NVIDIA\CUDNN\v9.19\bin\12.9\x64" + os.pathsep + os.environ["PATH"]
)

import onnxruntime as ort

print("ort version :", ort.__version__)
print("providers   :", ort.get_available_providers())

from fastembed.text.text_embedding import TextEmbedding
from fastembed.common.model_description import PoolingType, ModelSource

# BAAI/bge-m3 需要手动注册（Xenova/bge-m3 int8 ONNX，1024d，CLS pooling）
TextEmbedding.add_custom_model(
    model="BAAI/bge-m3",
    pooling=PoolingType.CLS,
    normalization=True,
    sources=ModelSource(hf="Xenova/bge-m3"),
    dim=1024,
    model_file="onnx/model_int8.onnx",
    size_in_gb=0.55,
)

print("\n加载 BAAI/bge-m3 int8（CUDA+CPU）...")
t0 = time.perf_counter()
m = TextEmbedding(
    "BAAI/bge-m3",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
)
print(f"加载耗时: {time.perf_counter() - t0:.2f}s")

texts = ["hello world", "今天天气真好，适合出去走走"] * 8
for bs in [1, 4, 16]:
    print(f"\n推理 {len(texts)} 条，batch_size={bs}...")
    t1 = time.perf_counter()
    try:
        vecs = list(m.embed(texts, batch_size=bs))
        elapsed = time.perf_counter() - t1
        print(f"  OK  耗时={elapsed:.3f}s  ({len(texts)/elapsed:.1f} texts/s)  dim={len(vecs[0])}")
    except Exception as e:
        print(f"  FAIL: {e}")


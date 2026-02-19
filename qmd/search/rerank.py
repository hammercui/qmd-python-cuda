import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from qmd.models.downloader import ModelDownloader


def _get_device() -> str:
    """Auto-detect best available device (cuda > mps > cpu)."""
    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            return "cuda"
        elif "CoreMLExecutionProvider" in providers:
            return "mps"  # Apple Silicon
        else:
            return "cpu"
    except ImportError:
        return "cpu"


class LLMReranker:
    """
    Reranker using ONNX models (optimum + onnxruntime).
    Query Expansion + Cross-Encoder for Reranking.
    """

    def __init__(
        self,
        model_name: str = "thomasht86/Qwen3-Reranker-0.6B-int8-ONNX",
        local_reranker_path: Optional[Path] = None,
        local_expansion_path: Optional[Path] = None,
    ):
        """
        Args:
            model_name: HuggingFace model ID or local path
            local_reranker_path: Local path for reranker model
            local_expansion_path: Local path for expansion model
        """
        self.model_name = model_name
        self.local_reranker_path = local_reranker_path
        self.local_expansion_path = local_expansion_path
        self._tokenizer = None
        self._model = None
        self._expansion_model = None
        self._expansion_tokenizer = None
        self._device = _get_device()
        self._torch_device = "cuda" if self._device == "cuda" else "cpu"
        self._downloader: Optional[ModelDownloader] = None

    @property
    def model(self):
        if self._model is None:
            try:
                import onnxruntime as ort
                from transformers import AutoTokenizer
                import torch  # 二次保险：确保 torch/lib DLL 目录已注册

                # Determine model path (local > download)
                model_path = self.model_name
                if self.local_reranker_path and self.local_reranker_path.exists():
                    if any(self.local_reranker_path.iterdir()):
                        model_path = str(self.local_reranker_path)
                else:
                    if self._downloader is None:
                        self._downloader = ModelDownloader()
                    cached = self._downloader.get_model_path("reranker")
                    if cached and any(cached.iterdir()):
                        model_path = str(cached)

                provider = (
                    "CUDAExecutionProvider"
                    if self._device == "cuda"
                    else "CPUExecutionProvider"
                )
                onnx_path = str(Path(model_path) / "model.onnx")
                print(f"[Reranker] Loading from: {onnx_path} (provider: {provider})")
                self._tokenizer = AutoTokenizer.from_pretrained(model_path)
                # int8-quantized ONNX models run on CPU SIMD (VNNI/AVX512).
                # CUDA EP fallbacks for quantized ops cause extreme CPU<->GPU copy overhead,
                # making it far slower than pure CPUExecutionProvider.
                # Force CPUExecutionProvider regardless of device.
                try:
                    self._model = ort.InferenceSession(
                        onnx_path,
                        providers=["CPUExecutionProvider"],
                    )
                    print(f"[Reranker] ORT session OK, providers: {self._model.get_providers()}")
                except Exception as cuda_err:
                    raise
            except Exception as e:
                print(f"Warning: Failed to load reranker model: {type(e).__name__}: {e}")
        return self._model

    @property
    def expansion_model(self):
        if self._expansion_model is None:
            try:
                from transformers import AutoTokenizer
                import torch  # 二次保险：确保 torch/lib DLL 目录已注册

                # Determine model path (local > download)
                model_name = "onnx-community/Qwen3-0.6B-ONNX"
                model_path = model_name

                if self.local_expansion_path and self.local_expansion_path.exists():
                    # Check if directory is not empty
                    if any(self.local_expansion_path.iterdir()):
                        model_path = str(self.local_expansion_path)
                else:
                    # Try downloader cache
                    if self._downloader is None:
                        self._downloader = ModelDownloader()
                    cached = self._downloader.get_model_path("expansion")
                    if cached and any(cached.iterdir()):
                        model_path = str(cached)

                provider = (
                    "CUDAExecutionProvider"
                    if self._device == "cuda"
                    else "CPUExecutionProvider"
                )
                import onnxruntime as ort
                # Use model_q4f16.onnx: INT4 weights + FP16 activations.
                # MatMulNBits (INT4) IS natively supported by CUDAExecutionProvider
                # in onnxruntime >= 1.17, so no CPU fallback overhead.
                onnx_path = str(Path(model_path) / "onnx" / "model_q4f16.onnx")
                print(f"[Expansion] Loading from: {onnx_path} (provider: {provider})")
                self._expansion_tokenizer = AutoTokenizer.from_pretrained(model_path)
                try:
                    self._expansion_model = ort.InferenceSession(
                        onnx_path,
                        providers=[provider, "CPUExecutionProvider"],
                    )
                    print(f"[Expansion] ORT session OK, providers: {self._expansion_model.get_providers()}")
                except Exception as cuda_err:
                    if provider == "CUDAExecutionProvider":
                        print(f"[Expansion] CUDA load failed ({cuda_err}), retrying with CPU...")
                        self._torch_device = "cpu"
                        self._expansion_model = ort.InferenceSession(
                            onnx_path,
                            providers=["CPUExecutionProvider"],
                        )
                        print("[Expansion] Loaded on CPU")
                    else:
                        raise
            except ImportError as e:
                print(
                    f"Warning: optimum[onnxruntime] not installed. Query expansion will be disabled. ({e})"
                )
            except Exception as e:
                print(f"Warning: Failed to load expansion model: {type(e).__name__}: {e}")
        return self._expansion_model

    def expand_query(self, query: str) -> List[str]:
        """Expand query into 2-3 variants using Qwen3-0.6B-Instruct ONNX."""
        if not self.expansion_model:
            return [query]

        try:
            # Use ChatML format for Qwen3 (apply_chat_template)
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Given the following search query, generate 2 alternative "
                        f"search queries that capture the same intent but use different "
                        f"wording or synonyms. Return only the variants, one per line.\n\n"
                        f"Query: {query}"
                    ),
                }
            ]
            try:
                prompt = self._expansion_tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                prompt = (
                    f"Given the following search query, generate 2 alternative search "
                    f"queries that capture the same intent but use different wording or "
                    f"synonyms. Return only the variants, one per line.\n\nQuery: {query}\n"
                )

            import numpy as np
            enc = self._expansion_tokenizer(prompt, return_tensors="np", truncation=True, max_length=512)
            input_ids = enc["input_ids"]          # (1, seq)
            attention_mask = enc["attention_mask"]  # (1, seq)

            # ORT session: 28 layers, 8 kv_heads, head_dim=128
            ort_session = self._expansion_model  # raw InferenceSession stored here
            print(f"[Expansion] providers active: {ort_session.get_providers()}")
            NUM_LAYERS = 28
            KV_HEADS = 8
            HEAD_DIM = 128

            generated = input_ids.copy()  # (1, seq)

            # Initialize empty KV cache.
            # q4f16 model expects float16 KV tensors; int8 model expects float32.
            # Detect by checking if any input has float16 type.
            _input_types = {inp.name: inp.type for inp in ort_session.get_inputs()}
            _kv_dtype = np.float16 if any("float16" in t for t in _input_types.values()) else np.float32
            past_seq = 0
            pkv = {
                f"past_key_values.{i}.{kv}": np.zeros(
                    (1, KV_HEADS, past_seq, HEAD_DIM), dtype=_kv_dtype
                )
                for i in range(NUM_LAYERS)
                for kv in ("key", "value")
            }

            eos_id = self._expansion_tokenizer.eos_token_id
            _t0 = time.perf_counter()

            for step in range(25):  # max_new_tokens=25 (2 short variants fit in ~20 tokens)
                seq_len = generated.shape[1]
                pos_ids = np.arange(past_seq, past_seq + 1, dtype=np.int64).reshape(1, 1)
                attn_mask = np.ones((1, past_seq + seq_len if past_seq == 0 else past_seq + 1), dtype=np.int64)

                if past_seq == 0:
                    # Prefill: process entire prompt
                    cur_input = generated
                    pos_ids = np.arange(seq_len, dtype=np.int64).reshape(1, seq_len)
                    attn_mask = attention_mask
                else:
                    # Decode: process one token at a time
                    cur_input = generated[:, -1:]

                feeds = {
                    "input_ids": cur_input,
                    "attention_mask": attn_mask,
                    "position_ids": pos_ids,
                    **pkv,
                }

                outs = ort_session.run(None, feeds)
                logits = outs[0]  # (1, step_seq, vocab)

                # Update KV cache from outputs
                out_names = [o.name for o in ort_session.get_outputs()]
                new_pkv = {}
                for i, name in enumerate(out_names):
                    if "present" in name or "past" in name:
                        new_pkv[name.replace("present", "past_key_values")] = outs[i]
                if new_pkv:
                    pkv = new_pkv
                    past_seq = list(pkv.values())[0].shape[2]
                else:
                    past_seq += cur_input.shape[1]

                # Greedy: argmax on last token logits
                next_token = int(logits[0, -1].argmax())
                if next_token == eos_id:
                    break
                generated = np.concatenate(
                    [generated, np.array([[next_token]], dtype=np.int64)], axis=1
                )

            print(f"[Expansion] decode {step+1} steps, {time.perf_counter() - _t0:.2f}s")
            input_len = input_ids.shape[1]
            response = self._expansion_tokenizer.decode(
                generated[0][input_len:], skip_special_tokens=True
            ).strip()

            variants = [v.strip() for v in response.split("\n") if v.strip()]
            return [query] + variants[:2]
        except Exception as e:
            print(f"Query expansion error: {e}")
            return [query]

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Rerank documents using cross-encoder."""
        if not documents:
            return []

        if not self.model:
            return documents[:top_k]

        # Prepare pairs for cross-encoder
        # Use content if available, otherwise title
        try:
            import numpy as np
            import math
            # Qwen3-Reranker: causal LM, score = P(yes) via softmax over yes/no logits
            YES_TOKEN_ID = 9693
            NO_TOKEN_ID = 2152

            SYSTEM_PROMPT = (
                'Judge whether the Document meets the requirements based on the Query '
                'and the Candidate Document, output "yes" or "no" to indicate '
                'the relevance of the document.'
            )

            def _make_input(query: str, doc: str) -> str:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"<Query>{query}</Query>\n<Document>{doc}</Document>"},
                ]
                return self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                ) + "<think>\n\n</think>\n\n"

            ort_session = self._model
            print(f"[Reranker] providers active: {ort_session.get_providers()}, docs={len(documents)}")
            batch_scores = []
            _t0 = time.perf_counter()
            for query_text, doc_text in [[query, doc.get("content", doc.get("title", ""))] for doc in documents]:
                # Truncate doc content: shorter seq → much smaller logits output
                doc_text = doc_text[:300]
                prompt = _make_input(query_text, doc_text)
                enc = self._tokenizer(
                    prompt, return_tensors="np", truncation=True, max_length=128
                )
                seq = enc["input_ids"].shape[1]
                pos_ids = np.arange(seq, dtype=np.int64).reshape(1, seq)
                outs = ort_session.run(
                    None,
                    {
                        "input_ids": enc["input_ids"],
                        "attention_mask": enc["attention_mask"],
                        "position_ids": pos_ids,
                    },
                )
                last_logits = outs[0][0, -1, :]  # (vocab,)
                yes_logit = float(last_logits[YES_TOKEN_ID])
                no_logit = float(last_logits[NO_TOKEN_ID])
                # Softmax over yes/no: P(yes)
                exp_yes = math.exp(yes_logit - max(yes_logit, no_logit))
                exp_no  = math.exp(no_logit  - max(yes_logit, no_logit))
                score = exp_yes / (exp_yes + exp_no)
                batch_scores.append(score)

            print(f"[Reranker] {len(documents)} docs scored in {time.perf_counter()-_t0:.2f}s")
            for i, doc in enumerate(documents):
                doc["rerank_score"] = batch_scores[i]

            # Sort by rerank_score
            reranked = sorted(
                documents, key=lambda x: x.get("rerank_score", 0), reverse=True
            )
            return reranked[:top_k]
        except Exception as e:
            print(f"Reranking error: {e}")
            return documents[:top_k]

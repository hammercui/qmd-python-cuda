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
                # seq-cls FP32: all ops natively supported by CUDAExecutionProvider,
                # no int8 fallback overhead. Use CUDA directly.
                try:
                    self._model = ort.InferenceSession(
                        onnx_path,
                        providers=[provider, "CPUExecutionProvider"],
                    )
                    inp_names = [i.name for i in self._model.get_inputs()]
                    out_shapes = [(o.name, o.shape) for o in self._model.get_outputs()]
                    print(
                        f"[Reranker] ORT session OK, providers: {self._model.get_providers()}"
                    )
                    print(f"[Reranker] inputs: {inp_names}")
                    print(f"[Reranker] outputs: {out_shapes}")
                except Exception as cuda_err:
                    if provider == "CUDAExecutionProvider":
                        print(
                            f"[Reranker] CUDA load failed ({cuda_err}), retrying CPU..."
                        )
                        self._model = ort.InferenceSession(
                            onnx_path, providers=["CPUExecutionProvider"]
                        )
                    else:
                        raise
            except Exception as e:
                print(
                    f"Warning: Failed to load reranker model: {type(e).__name__}: {e}"
                )
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
                    print(
                        f"[Expansion] ORT session OK, providers: {self._expansion_model.get_providers()}"
                    )
                except Exception as cuda_err:
                    if provider == "CUDAExecutionProvider":
                        print(
                            f"[Expansion] CUDA load failed ({cuda_err}), retrying with CPU..."
                        )
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
                print(
                    f"Warning: Failed to load expansion model: {type(e).__name__}: {e}"
                )
        return self._expansion_model

    def expand_query(
        self, query: str, include_lexical: bool = True
    ) -> Dict[str, List[str]]:
        """
        Expand query into lex/vec/hyde variants using Qwen3-0.6B-Instruct ONNX.

        TS implementation:
        - Uses GBNF grammar to enforce output format: "type: content\\n"
        - Types: lex (lexical variants), vec (semantic variants), hyde (hypothetical doc)
        - Validity filter: must contain at least one term from original query

        Args:
            query: Original search query
            include_lexical: If False, don't generate lex variants (used in vsearch)

        Returns:
            Dict with keys: {"lex": [...], "vec": [...], "hyde": [...]}
            Each list contains query variants of that type
        """
        if not self.expansion_model:
            return {"lex": [], "vec": [], "hyde": []}

        try:
            # Build prompt with type prefixes
            # TS uses GBNF grammar; we'll use explicit instructions
            types_desc = ""
            if include_lexical:
                types_desc = "- lex: (lexical) word-level variants with synonyms, spelling variations\n"

            prompt_content = f"""Generate alternative search queries for: "{query}"

Output format (one query per line, prefixed with type):
{types_desc}- vec: (semantic) paraphrased queries with same meaning
- hyde: (hypothetical) pretend you're writing a document that answers this query

Examples:
lex: {query} tutorial
vec: how to {query}
hyde: This guide explains {query} in detail with step-by-step instructions...

Generate 2-3 variants total:"""

            # Use ChatML format for Qwen3 (apply_chat_template)
            messages = [
                {
                    "role": "user",
                    "content": prompt_content,
                }
            ]
            try:
                prompt = self._expansion_tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                prompt = prompt_content + "\n\n"

            import numpy as np

            enc = self._expansion_tokenizer(
                prompt, return_tensors="np", truncation=True, max_length=512
            )
            input_ids = enc["input_ids"]  # (1, seq)
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
            _kv_dtype = (
                np.float16
                if any("float16" in t for t in _input_types.values())
                else np.float32
            )
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

            for step in range(40):  # max_new_tokens=40 (need more for hyde)
                seq_len = generated.shape[1]
                pos_ids = np.arange(past_seq, past_seq + 1, dtype=np.int64).reshape(
                    1, 1
                )
                attn_mask = np.ones(
                    (1, past_seq + seq_len if past_seq == 0 else past_seq + 1),
                    dtype=np.int64,
                )

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

            print(
                f"[Expansion] decode {step + 1} steps, {time.perf_counter() - _t0:.2f}s"
            )
            input_len = input_ids.shape[1]
            response = self._expansion_tokenizer.decode(
                generated[0][input_len:], skip_special_tokens=True
            ).strip()

            # Parse response by type prefixes
            result = {"lex": [], "vec": [], "hyde": []}
            query_terms = set(query.lower().split())

            for line in response.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Check for type prefix
                q_type = None
                content = line

                for t in ["lex", "vec", "hyde"]:
                    if line.startswith(f"{t}:"):
                        q_type = t
                        content = line[len(f"{t}:") :].strip()
                        break

                if q_type is None:
                    # No type prefix, skip or default to vec
                    continue

                # Validity filter: must contain at least one original term
                content_terms = set(content.lower().split())
                if not query_terms.intersection(content_terms):
                    print(f"[Expansion] Filtered (no original terms): {content}")
                    continue

                # Skip if lex but include_lexical is False
                if q_type == "lex" and not include_lexical:
                    continue

                if q_type in result and content:
                    result[q_type].append(content)

            # Fallback: if no valid variants, return empty
            if not any(result.values()):
                print("[Expansion] No valid variants generated, using original query")
                return {"lex": [], "vec": [], "hyde": []}

            print(
                f"[Expansion] Generated: lex={len(result['lex'])}, vec={len(result['vec'])}, hyde={len(result['hyde'])}"
            )
            return result

        except Exception as e:
            print(f"Query expansion error: {e}")
            return {"lex": [], "vec": [], "hyde": []}

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

            enc = self._expansion_tokenizer(
                prompt, return_tensors="np", truncation=True, max_length=512
            )
            input_ids = enc["input_ids"]  # (1, seq)
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
            _kv_dtype = (
                np.float16
                if any("float16" in t for t in _input_types.values())
                else np.float32
            )
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

            for step in range(
                25
            ):  # max_new_tokens=25 (2 short variants fit in ~20 tokens)
                seq_len = generated.shape[1]
                pos_ids = np.arange(past_seq, past_seq + 1, dtype=np.int64).reshape(
                    1, 1
                )
                attn_mask = np.ones(
                    (1, past_seq + seq_len if past_seq == 0 else past_seq + 1),
                    dtype=np.int64,
                )

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

            print(
                f"[Expansion] decode {step + 1} steps, {time.perf_counter() - _t0:.2f}s"
            )
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

            SYSTEM_PROMPT = (
                "Judge whether the Document meets the requirements based on the Query "
                'and the Candidate Document, output "yes" or "no" to indicate '
                "the relevance of the document."
            )

            def _make_input(query: str, doc: str) -> str:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"<Query>{query}</Query>\n<Document>{doc}</Document>",
                    },
                ]
                return (
                    self._tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
                    + "<think>\n\n</think>\n\n"
                )

            ort_session = self._model
            input_names = {inp.name for inp in ort_session.get_inputs()}
            print(
                f"[Reranker] providers active: {ort_session.get_providers()}, docs={len(documents)}"
            )
            _t0 = time.perf_counter()

            # Build prompts for all docs at once
            doc_texts = [
                doc.get("content", doc.get("title", ""))[:300] for doc in documents
            ]
            prompts = [_make_input(query, t) for t in doc_texts]

            # Tokenize as a batch with padding
            enc = self._tokenizer(
                prompts,
                padding=True,
                truncation=True,
                return_tensors="np",
                max_length=512,
            )

            # Build ORT inputs - auto-detect which inputs the model requires
            ort_inputs = {
                "input_ids": enc["input_ids"],
                "attention_mask": enc["attention_mask"],
            }
            if "position_ids" in input_names:
                batch, seq = enc["input_ids"].shape
                ort_inputs["position_ids"] = np.broadcast_to(
                    np.arange(seq, dtype=np.int64), (batch, seq)
                ).copy()

            # Single batch forward → (batch, 1) or (batch, num_labels)
            outs = ort_session.run(None, ort_inputs)
            scores = outs[0].squeeze(-1).flatten()  # (batch,)

            print(
                f"[Reranker] {len(documents)} docs scored in {time.perf_counter() - _t0:.2f}s"
            )
            for i, doc in enumerate(documents):
                doc["rerank_score"] = float(scores[i])

            reranked = sorted(
                documents, key=lambda x: x.get("rerank_score", 0), reverse=True
            )
            return reranked[:top_k]
        except Exception as e:
            print(f"Reranking error: {e}")
            return documents[:top_k]

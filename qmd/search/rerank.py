import os
from typing import List, Dict, Any
 
class LLMReranker:
    """
    Reranker using local models (transformers).
    Query Expansion + Cross-Encoder for Reranking.
    """
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._expansion_model = None
        self._expansion_tokenizer = None
 
    @property
    def model(self):
        if self._model is None:
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import torch

                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
                self._model.eval()
                self._torch = torch
            except ImportError:
                print("Warning: transformers or torch not installed. Reranking will be disabled.")
        return self._model

    @property
    def expansion_model(self):
        if self._expansion_model is None:
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM
                import torch

                # Use Qwen3 for query expansion (local)
                model_name = "Qwen/Qwen3-0.5B-Instruct"
                self._expansion_tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._expansion_model = AutoModelForCausalLM.from_pretrained(model_name)
                self._expansion_model.eval()
            except ImportError:
                print("Warning: transformers or torch not installed. Query expansion will be disabled.")
        return self._expansion_model
 
    def expand_query(self, query: str) -> List[str]:
        """Expand query into 2-3 variants using local Qwen3."""
        if not self.expansion_model:
            return [query]

        try:
            prompt = f"""Given the following search query, generate 2 alternative search queries that capture the same intent but use different wording or synonyms. Return only the variants, one per line.

Query: {query}
"""

            inputs = self._expansion_tokenizer(prompt, return_tensors="pt")

            with self._expansion_model._torch.no_grad():
                outputs = self._expansion_model.generate(
                    **inputs,
                    max_new_tokens=50,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self._expansion_tokenizer.eos_token_id
                )

            response = self._expansion_tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Parse variants (after "Query:" line)
            if "Query:" in response:
                response = response.split("Query:")[-1].strip()

            variants = [v.strip() for v in response.split("\n") if v.strip()]
            return [query] + variants[:2]
        except Exception as e:
            print(f"Query expansion error: {e}")
            return [query]
 
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """Rerank documents using cross-encoder."""
        if not documents:
            return []
             
        if not self.model:
            return documents[:top_k]
             
        # Prepare pairs for cross-encoder
        # Use content if available, otherwise title
        pairs = [[query, doc.get("content", doc.get("title", ""))] for doc in documents]
         
        try:
            with self._torch.no_grad():
                inputs = self._tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=512
                )
                outputs = self._model(**inputs)
                scores = outputs.logits.squeeze(-1)
                 
                # If scores is 1D (for multiple documents) or 0D (for single)
                if scores.dim() == 0:
                    scores = scores.unsqueeze(0)
                 
            # Add scores to documents
            for i, doc in enumerate(documents):
                doc["rerank_score"] = float(scores[i])
                 
            # Sort by rerank_score
            reranked = sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)
            return reranked[:top_k]
        except Exception as e:
            print(f"Reranking error: {e}")
            return documents[:top_k]

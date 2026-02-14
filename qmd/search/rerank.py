import os
from typing import List, Dict, Any

class LLMReranker:
    """
    Reranker using Gemini for Query Expansion and Cross-Encoders for Reranking.
    """
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self._client = None
        self._tokenizer = None
        self._model = None

    @property
    def client(self):
        if self._client is None and self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                pass
        return self._client

    def _load_model(self):
        if self._tokenizer is None:
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import torch
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
                self._model.eval()
                self._torch = torch
            except ImportError:
                print("Warning: transformers or torch not installed. Reranking will be disabled.")
                return False
        return True

    def expand_query(self, query: str) -> List[str]:
        """Expand query into 2-3 variants using Gemini."""
        client = self.client
        if not client:
            return [query]
        
        prompt = f"""
        Given the following search query, generate 2-3 alternative versions that 
        capture the same intent but use different wording or synonyms.
        Return only the variants, one per line.
        
        Query: {query}
        """
        
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            variants = [v.strip() for v in response.text.split("\n") if v.strip()]
            return [query] + variants[:2]
        except Exception as e:
            print(f"Query expansion error: {e}")
            return [query]

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """Rerank documents using a cross-encoder."""
        if not documents:
            return []
            
        if not self._load_model():
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

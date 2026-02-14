import pytest
from unittest.mock import MagicMock, patch
from qmd.search.rerank import LLMReranker

@pytest.fixture
def mock_reranker():
    with patch('transformers.AutoTokenizer.from_pretrained'), \
         patch('transformers.AutoModelForSequenceClassification.from_pretrained'), \
         patch('google.genai.Client'):
        reranker = LLMReranker()
        yield reranker

def test_expand_query(mock_reranker):
    mock_reranker.client.models.generate_content.return_value.text = "variant 1\nvariant 2"
    variants = mock_reranker.expand_query("original query")
    assert len(variants) == 3
    assert "original query" in variants
    assert "variant 1" in variants

def test_rerank(mock_reranker):
    docs = [
        {"id": "1", "content": "doc1", "title": "t1"},
        {"id": "2", "content": "doc2", "title": "t2"}
    ]
    # Trigger model loading and mock it
    mock_reranker._load_model()
    import torch
    mock_output = MagicMock()
    mock_output.logits = torch.tensor([0.1, 0.9])
    mock_reranker._model.return_value = mock_output
    
    results = mock_reranker.rerank("query", docs)
    assert len(results) == 2
    assert results[0]["id"] == "2" # Score 0.9 > 0.1
    assert "rerank_score" in results[0]

"""Basic tests for MCP Server functionality."""

import pytest
from qmd.server.app import create_app
from qmd.server.client import EmbedServerClient
from fastapi.testclient import TestClient


@pytest.fixture
def test_app():
    """Create test FastAPI app."""
    return create_app()


@pytest.fixture
def test_client(test_app):
    """Create HTTP test client."""
    return TestClient(test_app)


def test_health_endpoint(test_client):
    """Test health check endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "unhealthy"]
    assert isinstance(data["model_loaded"], bool)


def test_embed_endpoint_empty_texts(test_client):
    """Test embed endpoint with empty texts list."""
    response = test_client.post("/embed", json={"texts": []})
    assert response.status_code == 400  # Bad Request


def test_embed_endpoint_too_many_texts(test_client):
    """Test embed endpoint with too many texts."""
    # Create list with 1001 texts
    texts = ["test"] * 1001
    response = test_client.post("/embed", json={"texts": texts})
    assert response.status_code == 413  # Payload Too Large


def test_client_health_check(monkeypatch):
    """Test EmbedServerClient health check."""

    # Mock successful response
    class MockResponse:
        status_code = 200

    class MockClient:
        def get(self, url):
            return MockResponse()

    def mock_get_client(self):
        return MockClient()

    def mock_discover_server(self):
        return "http://localhost:18765"

    # Mock both _discover_server and _get_client
    monkeypatch.setattr(EmbedServerClient, "_get_client", mock_get_client)
    monkeypatch.setattr(EmbedServerClient, "_discover_server", mock_discover_server)

    client = EmbedServerClient()
    assert client.health_check() is True


def test_client_embed_texts(monkeypatch):
    """Test EmbedServerClient embed_texts method."""

    class MockResponse:
        status_code = 200

        def json(self):
            return {"embeddings": [[0.1] * 384, [0.2] * 384]}

        def raise_for_status(self):
            pass

    class MockClient:
        def post(self, url, json=None, **kwargs):
            return MockResponse()

    def mock_get_client(self):
        return MockClient()

    def mock_discover_server(self):
        return "http://localhost:18765"

    # Mock both _discover_server and _get_client
    monkeypatch.setattr(EmbedServerClient, "_get_client", mock_get_client)
    monkeypatch.setattr(EmbedServerClient, "_discover_server", mock_discover_server)

    client = EmbedServerClient()
    result = client.embed_texts(["text1", "text2"])

    assert result is not None
    assert len(result) == 2
    assert len(result[0]) == 384

"""
HTTP client for QMD MCP Server.

Provides a fallback-enabled client for communicating with
the embedding server.
"""

import httpx
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class EmbedServerClient:
    """
    Client for communicating with the QMD MCP Server.
    
    Automatically falls back to None if server is unavailable,
    allowing the caller to switch to local embedding mode.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 5.0
    ):
        """
        Initialize client.
        
        Args:
            base_url: Base URL of the MCP server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
    
    def _get_client(self) -> httpx.Client:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client
    
    def health_check(self) -> bool:
        """
        Check if the server is healthy.
        
        Returns:
            True if server is responding, False otherwise
        """
        try:
            client = self._get_client()
            response = client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
    
    def embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Send embedding request to server.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors if successful, None if server unavailable
        """
        try:
            client = self._get_client()
            response = client.post(
                f"{self.base_url}/embed",
                json={"texts": texts}
            )
            response.raise_for_status()
            
            data = response.json()
            return data["embeddings"]
            
        except httpx.ConnectError:
            logger.warning(f"Cannot connect to MCP server at {self.base_url}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"MCP server timeout")
            return None
        except Exception as e:
            logger.error(f"MCP server error: {e}")
            return None
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

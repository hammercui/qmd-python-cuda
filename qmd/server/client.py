"""
HTTP client for QMD MCP Server.

Provides a fallback-enabled client for communicating with
the embedding server with automatic service discovery.
"""

import httpx
import json as _json
import subprocess
import platform
import time
from typing import Callable, List, Optional
import logging

from .port_manager import find_available_port, get_saved_port, DEFAULT_PORT
from .process import find_server_processes

logger = logging.getLogger(__name__)


class EmbedServerClient:
    """
    Client for communicating with the QMD MCP Server.

    Features:
    - Automatic service discovery
    - Auto-start server if not running
    - Fallback to None if unavailable
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0):
        """
        Initialize client with automatic service discovery.

        Args:
            base_url: Base URL of the MCP server (None = auto-discover)
            timeout: Read timeout in seconds for search/embed requests (default 120s).
                     Connect timeout is always 5 s.
        """
        self.timeout = timeout
        # Fine-grained timeout: quick connect probe, generous read for search/rerank
        self._request_timeout = httpx.Timeout(
            connect=5.0,
            read=timeout,
            write=30.0,
            pool=5.0,
        )
        self._client: Optional[httpx.Client] = None
        self.base_url = base_url or self._discover_server()

    def _discover_server(self) -> str:
        """
        Discover or auto-start QMD MCP Server.

        Returns:
            Server base URL

        Discovery logic:
        1. Try to connect to localhost:18765
        2. Read saved port from ~/.qmd/server_port.txt
        3. Check if server process is running
        4. If not running, auto-start server
        """
        # Step 1: Try default port
        if self._try_connect("http://localhost:18765"):
            logger.info("Connected to server on default port 18765")
            return "http://localhost:18765"

        # Step 2: Try saved port
        saved_port = get_saved_port()
        if saved_port and self._try_connect(f"http://localhost:{saved_port}"):
            logger.info(f"Connected to server on saved port {saved_port}")
            return f"http://localhost:{saved_port}"

        # Step 3: Check if server process is running
        if self._is_server_running():
            logger.warning("Server process found but not accessible, starting new one")

        # Step 4: Auto-start server
        logger.info("No server found, auto-starting...")
        return self._auto_start_server()

    def _try_connect(self, url: str, timeout: float = 1.0) -> bool:
        """
        Try to connect to server URL.

        Args:
            url: Server URL to test
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{url}/health")
                return response.status_code == 200
        except Exception:
            return False

    def _is_server_running(self) -> bool:
        """
        Check if QMD server process is running.

        Returns:
            True if server process found, False otherwise
        """
        procs = find_server_processes()
        return len(procs) > 0

    def _auto_start_server(self) -> str:
        """
        Auto-start QMD MCP Server.

        Returns:
            Server base URL

        Raises:
            RuntimeError: If server fails to start
        """
        # Find available port
        port = find_available_port(DEFAULT_PORT)

        # Start server in background
        try:
            if platform.system() == "Windows":
                # Windows: use CREATE_NEW_PROCESS_GROUP
                subprocess.Popen(
                    ["qmd", "server", "--port", str(port)],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # Linux/macOS: use nohup
                subprocess.Popen(
                    ["qmd", "server", "--port", str(port)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # Wait for server to start (max 10 seconds)
            url = f"http://localhost:{port}"
            for i in range(20):
                time.sleep(0.5)
                if self._try_connect(url):
                    logger.info(f"Server started successfully on port {port}")
                    return url

            raise RuntimeError("Server failed to start within 10 seconds")

        except Exception as e:
            raise RuntimeError(f"Failed to start server: {e}")

    def _get_client(self) -> httpx.Client:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self._request_timeout)
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

    def embed_index(
        self,
        collection: Optional[str] = None,
        force: bool = False,
        on_progress: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """Trigger server-side embedding job and stream progress via SSE.

        If the server is already running an embed job, attaches to it so only
        one job runs at a time.

        Args:
            collection: Collection name to embed (None = all collections).
            force: If True, clear existing embeddings and re-embed everything.
            on_progress: Called with each progress event dict from the server.
                         Event keys: status, done_chunks, total_chunks,
                         done_docs, total_docs, error (on error), _attached (bool).

        Raises:
            httpx.ConnectError: If the server is not running.
            httpx.HTTPStatusError: If the server returns an HTTP error.
        """
        body: dict = {"force": force}
        if collection:
            body["collection"] = collection

        # Infinite read timeout: embedding may take a long time
        timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=5.0)

        with httpx.stream(
            "POST",
            f"{self.base_url}/embed/index",
            json=body,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = _json.loads(line[5:].strip())
                except Exception:
                    continue
                if on_progress:
                    on_progress(event)
                if event.get("status") in ("complete", "error"):
                    break

    def embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Send embedding request to server.

        Sends texts in client-side chunks of CLIENT_CHUNK_SIZE to avoid
        large HTTP request bodies, then concatenates the results.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors if successful, None if server unavailable
        """
        CLIENT_CHUNK_SIZE = 64  # safety cap; CLI already sends ≤32 per call
        try:
            client = self._get_client()
            all_embeddings: List[List[float]] = []

            for i in range(0, len(texts), CLIENT_CHUNK_SIZE):
                chunk = texts[i : i + CLIENT_CHUNK_SIZE]
                response = client.post(
                    f"{self.base_url}/embed/batch",
                    json={"texts": chunk},
                )
                response.raise_for_status()
                all_embeddings.extend(response.json()["embeddings"])

            return all_embeddings

        except httpx.ConnectError:
            logger.warning(f"Cannot connect to MCP server at {self.base_url}")
            return None
        except httpx.TimeoutException:
            logger.warning("MCP server timeout")
            return None
        except Exception as e:
            logger.error(f"MCP server error: {e}")
            return None

    def vsearch(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.3,
        collection: Optional[str] = None,
    ) -> Optional[list]:
        """
        Vector semantic search.

        Args:
            query: Search query string
            limit: Max number of results
            min_score: Minimum similarity score (0-1)
            collection: Collection name to filter (None = search all collections)

        Returns:
            List of search results if successful, None otherwise
        """
        try:
            client = self._get_client()
            body: dict = {"query": query, "limit": limit, "min_score": min_score}
            if collection:
                body["collection"] = collection
            response = client.post(f"{self.base_url}/vsearch", json=body)
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return None

    def query(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
        collection: Optional[str] = None,
    ) -> Optional[list]:
        """
        Hybrid search (BM25 + vector).

        Args:
            query: Search query string
            limit: Max number of results
            min_score: Minimum relevance score
            collection: Collection name to filter (None = search all collections)

        Returns:
            List of search results if successful, None otherwise
        """
        try:
            client = self._get_client()
            body: dict = {"query": query, "limit": limit, "min_score": min_score}
            if collection:
                body["collection"] = collection
            response = client.post(f"{self.base_url}/query", json=body)
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            return None

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

"""HTTP middleware for QMD server."""

import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check request body size before processing.

    Allows up to max_size bytes for POST requests.
    Returns 413 if exceeded.
    """

    def __init__(self, app: ASGIApp, max_size: int = 100 * 1024 * 1024):
        super().__init__(app)
        self.max_size = max_size  # Default: 100MB

    async def dispatch(self, request: Request, call_next):
        import logging

        logger = logging.getLogger(__name__)
        t_start = time.time()
        ts_in = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t_start))
        logger.info(f"[{ts_in}] --> {request.method} {request.url.path}")

        # Check Content-Length for POST/PUT requests
        if request.method in ("POST", "PUT"):
            content_length = request.headers.get("content-length")
            if content_length:
                size = int(content_length)
                if size > self.max_size:
                    elapsed = (time.time() - t_start) * 1000
                    ts_out = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    logger.info(
                        f"[{ts_out}] <-- {request.method} {request.url.path} 413 ({elapsed:.1f}ms)"
                    )
                    return Response(
                        content=f"Request body too large: {size} > {self.max_size} bytes. "
                        f"Use batch endpoint or increase limit.",
                        status_code=413,
                        media_type="text/plain",
                    )

        response = await call_next(request)
        elapsed = (time.time() - t_start) * 1000
        ts_out = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.info(
            f"[{ts_out}] <-- {request.method} {request.url.path} {response.status_code} ({elapsed:.1f}ms)"
        )
        return response

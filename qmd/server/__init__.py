"""
QMD MCP Server Module

Provides a server-based embedding service to reduce VRAM usage
when multiple CLI processes run concurrently.
"""

from qmd.server.app import app

__all__ = ["app"]

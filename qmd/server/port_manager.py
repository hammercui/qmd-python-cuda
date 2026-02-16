"""
Port Manager for QMD MCP Server

功能：
1. 检测可用端口，冲突时自动递增
2. 保存实际端口到文件
3. 读取保存的端口
"""

import socket
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Default port
DEFAULT_PORT = 18765
PORT_FILE = ".qmd/server_port.txt"


def find_available_port(start_port=DEFAULT_PORT, max_attempts=100) -> int:
    """
    Find an available port starting from start_port.

    Args:
        start_port: Starting port number (default: 18765)
        max_attempts: Maximum ports to try (default: 100)

    Returns:
        First available port in range

    Raises:
        RuntimeError: If no available port found
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                logger.info(f"Found available port: {port}")
                return port
            except OSError:
                logger.debug(f"Port {port} occupied, trying next...")
                continue

    raise RuntimeError(
        f"No available ports in range {start_port}-{start_port + max_attempts}"
    )


def save_server_port(port: int):
    """
    Save actual server port to ~/.qmd/server_port.txt.

    Args:
        port: The actual port server is listening on
    """
    qmd_dir = Path.home() / ".qmd"
    qmd_dir.mkdir(parents=True, exist_ok=True)

    port_file = qmd_dir / PORT_FILE
    port_file.write_text(str(port))
    logger.info(f"Saved server port {port} to {port_file}")


def get_saved_port() -> int | None:
    """
    Get saved server port if exists.

    Returns:
        Port number if file exists, None otherwise
    """
    port_file = Path.home() / ".qmd" / PORT_FILE

    if port_file.exists():
        try:
            return int(port_file.read_text().strip())
        except (ValueError, FileNotFoundError):
            logger.warning(f"Invalid port file at {port_file}, ignoring")
            return None

    return None

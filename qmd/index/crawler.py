import os
import hashlib
from pathlib import Path
from typing import Iterator, Tuple, Optional
from ..models.document import Document

class Crawler:
    def __init__(self, root_path: str, glob_pattern: str = "**/*.md"):
        self.root_path = Path(root_path)
        self.glob_pattern = glob_pattern

    def scan(self) -> Iterator[Tuple[str, str, str, str]]:
        """
        Scans the directory for files matching the glob pattern.
        Returns an iterator of (relative_path, content, hash, title).
        """
        if not self.root_path.exists():
            return

        for file_path in self.root_path.glob(self.glob_pattern):
            if not file_path.is_file():
                continue
            
            data = self._read_file(file_path)
            if data:
                yield data

    def _read_file(self, file_path: Path) -> Optional[Tuple[str, str, str, str]]:
        try:
            content = file_path.read_text(encoding="utf-8")
            doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            title = self._extract_title(content) or file_path.name
            rel_path = str(file_path.relative_to(self.root_path))
            return rel_path, content, doc_hash, title
        except (IOError, UnicodeDecodeError):
            return None

    def _extract_title(self, content: str) -> Optional[str]:
        # Simple title extraction: first line starting with #
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return None

from dataclasses import dataclass
from typing import Optional

@dataclass
class Document:
    collection: str
    path: str
    content: str
    hash: str
    title: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None

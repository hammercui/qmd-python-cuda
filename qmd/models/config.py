from pydantic import BaseModel, Field
from typing import List, Optional
import os
import yaml
from pathlib import Path

def get_default_config_dir() -> Path:
    return Path.home() / ".qmd"

def get_default_config_path() -> Path:
    return get_default_config_dir() / "index.yml"

class CollectionConfig(BaseModel):
    name: str
    path: str
    glob_pattern: str = "**/*.md"

class AppConfig(BaseModel):
    db_path: str = Field(default_factory=lambda: str(get_default_config_dir() / "qmd.db"))
    collections: List[CollectionConfig] = []

    # Model download source: "auto" (detect location), "huggingface", "modelscope"
    model_source: str = "auto"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        config_path = path or get_default_config_path()
        if not config_path.exists():
            return cls()
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data is None:
                return cls()
            return cls.model_validate(data)

    def save(self, path: Optional[Path] = None):
        config_path = path or get_default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, allow_unicode=True)

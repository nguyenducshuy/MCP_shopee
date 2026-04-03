import json
from pathlib import Path

from app.core.logger import get_logger

logger = get_logger(__name__)


class EndpointRepository:
    def __init__(self, path: str = "data/endpoint_catalog.json"):
        self.path = Path(path)
        self._cache: list[dict] | None = None

    def get_all(self) -> list[dict]:
        if self._cache is None:
            if not self.path.exists():
                self._cache = []
            else:
                try:
                    self._cache = json.loads(self.path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    logger.error("endpoint_repo_read_error | %s | %s", self.path, exc)
                    self._cache = []
        return self._cache

    def get_by_key(self, key: str) -> dict:
        for item in self.get_all():
            if item.get("key") == key:
                return item
        return {}

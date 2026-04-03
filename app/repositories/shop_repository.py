import json
import tempfile
import os
import threading
from pathlib import Path

from app.core.logger import get_logger

logger = get_logger(__name__)


class ShopRepository:
    def __init__(self, path: str = "data/shops.json"):
        self.path = Path(path)
        self._lock = threading.Lock()

    def get_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("shop_repo_read_error | %s | %s", self.path, exc)
            return []

    def get_by_code(self, shop_code: str) -> dict:
        for item in self.get_all():
            if item.get("code") == shop_code:
                return item
        return {}

    def _atomic_write(self, shops: list[dict]) -> None:
        """Write to temp file then rename — atomic, no corruption on crash."""
        data = json.dumps(shops, indent=2, ensure_ascii=False)
        dir_path = self.path.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
        closed = False
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            closed = True
            os.replace(tmp_path, str(self.path))
        except OSError:
            if not closed:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def update_shop(self, shop_code: str, updates: dict) -> dict:
        """Update fields for a shop identified by code, then persist."""
        with self._lock:
            shops = self.get_all()
            for shop in shops:
                if shop.get("code") == shop_code:
                    shop.update(updates)
                    self._atomic_write(shops)
                    logger.info("shop_updated | %s | fields=%s", shop_code, list(updates.keys()))
                    return shop
            return {}

    def add_shop(self, shop: dict) -> dict:
        """Add a new shop entry."""
        with self._lock:
            shops = self.get_all()
            # Check duplicate
            for s in shops:
                if s.get("code") == shop.get("code"):
                    logger.warning("shop_duplicate | %s", shop.get("code"))
                    return s
            shops.append(shop)
            self._atomic_write(shops)
            logger.info("shop_added | %s", shop.get("code"))
            return shop

    def remove_shop(self, shop_code: str) -> bool:
        """Remove a shop by code. Returns True if found and removed."""
        with self._lock:
            shops = self.get_all()
            new_shops = [s for s in shops if s.get("code") != shop_code]
            if len(new_shops) == len(shops):
                return False
            self._atomic_write(new_shops)
            logger.info("shop_removed | %s", shop_code)
            return True

"""
File-based cache layer.

Data dir:  data/cache/
Structure: data/cache/{namespace}/{key}.json

Mỗi cache entry là 1 file JSON:
{
    "created_at": 1711440000,
    "ttl": 300,
    "expires_at": 1711440300,
    "namespace": "order_list",
    "key": "shop_abc123",
    "data": { ... actual cached data ... }
}

AI Agent đọc được qua MCP tools (cache_list, cache_get, cache_clear).
Sau này chuyển sang Redis chỉ cần thay class này.
"""

import json
import os
import time
import hashlib
import threading
from pathlib import Path
from app.core.logger import get_logger

logger = get_logger(__name__)

# Default TTLs per data type (seconds)
DEFAULT_TTLS = {
    "category":         86400,   # 24h  — danh mục ít thay đổi
    "attribute_tree":   86400,   # 24h
    "channel_list":     3600,    # 1h   — kênh vận chuyển
    "shop_info":        1800,    # 30m
    "item_list":        300,     # 5m   — danh sách sản phẩm
    "item_base_info":   300,     # 5m
    "order_list":       60,      # 1m   — đơn hàng thay đổi nhanh
    "voucher_list":     300,     # 5m
    "discount_list":    300,     # 5m
    "ads_performance":  900,     # 15m
    "ams_performance":  900,     # 15m
    "comment":          300,     # 5m
    "model_list":       300,     # 5m
    "default":          120,     # 2m   — fallback
}

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


class CacheService:
    """File-based cache with TTL, namespace, and JSON storage."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "writes": 0, "evictions": 0}

    def _make_path(self, namespace: str, key: str) -> Path:
        """Generate file path for a cache entry."""
        safe_key = hashlib.md5(key.encode()).hexdigest()[:16]
        ns_dir = self._dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / f"{safe_key}.json"

    def get(self, namespace: str, key: str) -> dict | None:
        """Get cached data. Returns None if miss or expired."""
        path = self._make_path(namespace, key)
        if not path.exists():
            self._stats["misses"] += 1
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._stats["misses"] += 1
            path.unlink(missing_ok=True)
            return None

        if time.time() > entry.get("expires_at", 0):
            self._stats["evictions"] += 1
            path.unlink(missing_ok=True)
            return None

        self._stats["hits"] += 1
        return entry["data"]

    def set(self, namespace: str, key: str, data: dict, ttl: int | None = None) -> None:
        """Write data to cache with TTL."""
        if ttl is None:
            ttl = DEFAULT_TTLS.get(namespace, DEFAULT_TTLS["default"])

        now = time.time()
        entry = {
            "created_at": int(now),
            "ttl": ttl,
            "expires_at": int(now + ttl),
            "namespace": namespace,
            "key": key,
            "data": data,
        }

        path = self._make_path(namespace, key)
        with self._lock:
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            os.replace(tmp, path)

        self._stats["writes"] += 1

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a specific cache entry."""
        path = self._make_path(namespace, key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace. Returns count deleted."""
        ns_dir = self._dir / namespace
        if not ns_dir.exists():
            return 0
        count = 0
        for f in ns_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count

    def clear_all(self) -> int:
        """Clear entire cache. Returns count deleted."""
        count = 0
        for ns_dir in self._dir.iterdir():
            if ns_dir.is_dir():
                for f in ns_dir.glob("*.json"):
                    f.unlink()
                    count += 1
        return count

    def list_namespaces(self) -> list[dict]:
        """List all cache namespaces with entry counts and sizes."""
        result = []
        for ns_dir in sorted(self._dir.iterdir()):
            if not ns_dir.is_dir():
                continue
            entries = list(ns_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in entries)
            # Count expired
            now = time.time()
            expired = 0
            for f in entries:
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        e = json.load(fh)
                    if now > e.get("expires_at", 0):
                        expired += 1
                except Exception:
                    expired += 1

            result.append({
                "namespace": ns_dir.name,
                "entries": len(entries),
                "expired": expired,
                "active": len(entries) - expired,
                "size_kb": round(total_size / 1024, 1),
            })
        return result

    def list_entries(self, namespace: str) -> list[dict]:
        """List all entries in a namespace (metadata only, no data)."""
        ns_dir = self._dir / namespace
        if not ns_dir.exists():
            return []

        now = time.time()
        result = []
        for f in sorted(ns_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    entry = json.load(fh)
                remaining = max(0, int(entry["expires_at"] - now))
                result.append({
                    "key": entry.get("key", ""),
                    "namespace": namespace,
                    "created_at": entry.get("created_at"),
                    "ttl": entry.get("ttl"),
                    "expires_at": entry.get("expires_at"),
                    "remaining_seconds": remaining,
                    "expired": remaining == 0,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
            except Exception:
                pass
        return result

    def get_entry_full(self, namespace: str, key: str) -> dict | None:
        """Get full cache entry including metadata (for AI Agent inspection)."""
        path = self._make_path(namespace, key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            now = time.time()
            entry["remaining_seconds"] = max(0, int(entry["expires_at"] - now))
            entry["expired"] = entry["remaining_seconds"] == 0
            return entry
        except Exception:
            return None

    def get_stats(self) -> dict:
        """Get cache hit/miss statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": round(self._stats["hits"] / total * 100, 1) if total > 0 else 0,
        }

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.time()
        removed = 0
        for ns_dir in self._dir.iterdir():
            if not ns_dir.is_dir():
                continue
            for f in ns_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        entry = json.load(fh)
                    if now > entry.get("expires_at", 0):
                        f.unlink()
                        removed += 1
                except Exception:
                    f.unlink()
                    removed += 1
        self._stats["evictions"] += removed
        return removed

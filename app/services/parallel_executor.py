"""
Parallel executor for N-shop operations.

Features:
- Semaphore-controlled concurrency (prevent Shopee rate limit)
- Per-shop timeout
- Error isolation (1 shop fail ≠ whole batch fail)
- Cache integration (skip API call if cached)
- Progress tracking
"""

import asyncio
import time
from typing import Any, Callable, Coroutine
from app.core.logger import get_logger

logger = get_logger(__name__)

# Shopee partner rate limit is ~1000 req/min
# Safe default: 10 concurrent shops × 3 calls each = 30 concurrent API calls
DEFAULT_MAX_CONCURRENT = 10
DEFAULT_TIMEOUT_PER_SHOP = 30  # seconds


class ShopResult:
    """Result from processing one shop."""

    __slots__ = ("shop_code", "shop_name", "ok", "data", "error", "duration_ms")

    def __init__(self, shop_code: str, shop_name: str = ""):
        self.shop_code = shop_code
        self.shop_name = shop_name
        self.ok = False
        self.data: Any = None
        self.error: str | None = None
        self.duration_ms = 0

    def to_dict(self) -> dict:
        d = {
            "shop_code": self.shop_code,
            "shop_name": self.shop_name,
            "ok": self.ok,
            "duration_ms": self.duration_ms,
        }
        if self.ok:
            d["data"] = self.data
        else:
            d["error"] = self.error
        return d


class BatchResult:
    """Aggregated result from processing N shops."""

    def __init__(self):
        self.results: list[ShopResult] = []
        self.start_time = time.time()
        self.end_time = 0.0

    def add(self, result: ShopResult):
        self.results.append(result)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    @property
    def success_results(self) -> list[ShopResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed_results(self) -> list[ShopResult]:
        return [r for r in self.results if not r.ok]

    def to_dict(self, include_details: bool = True) -> dict:
        self.end_time = time.time()
        d: dict = {
            "meta": {
                "total_shops": self.total,
                "success": self.success_count,
                "failed": self.failed_count,
                "duration_ms": int((self.end_time - self.start_time) * 1000),
            },
        }
        if include_details:
            d["by_shop"] = [r.to_dict() for r in self.results]
        if self.failed_results:
            d["errors"] = [
                {"shop_code": r.shop_code, "error": r.error}
                for r in self.failed_results
            ]
        return d


async def execute_parallel(
    shops: list[dict],
    task_fn: Callable[[dict], Coroutine[Any, Any, Any]],
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    timeout_per_shop: int = DEFAULT_TIMEOUT_PER_SHOP,
    skip_errors: bool = True,
) -> BatchResult:
    """
    Execute an async task for N shops in parallel with concurrency control.

    Args:
        shops: List of shop dicts [{"code": "xxx", "shop_name": "yyy", ...}]
        task_fn: Async function that takes a shop dict and returns data
        max_concurrent: Max shops processed simultaneously
        timeout_per_shop: Timeout per shop in seconds
        skip_errors: If True, continue on error; if False, abort on first error

    Returns:
        BatchResult with all shop results
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    batch = BatchResult()

    async def _process_one(shop: dict) -> ShopResult:
        result = ShopResult(
            shop_code=shop.get("code", ""),
            shop_name=shop.get("shop_name", ""),
        )
        t0 = time.time()

        async with semaphore:
            try:
                data = await asyncio.wait_for(
                    task_fn(shop),
                    timeout=timeout_per_shop,
                )
                result.ok = True
                result.data = data
            except asyncio.TimeoutError:
                result.error = f"Timeout after {timeout_per_shop}s"
                logger.warning("parallel_timeout | shop=%s", shop.get("code"))
            except Exception as e:
                result.error = str(e)
                logger.warning("parallel_error | shop=%s | %s", shop.get("code"), e)
                if not skip_errors:
                    raise

        result.duration_ms = int((time.time() - t0) * 1000)
        return result

    tasks = [_process_one(shop) for shop in shops]
    completed = await asyncio.gather(*tasks, return_exceptions=skip_errors)

    for item in completed:
        if isinstance(item, ShopResult):
            batch.add(item)
        elif isinstance(item, Exception):
            # Should not happen with skip_errors=True, but safety
            r = ShopResult(shop_code="unknown")
            r.error = str(item)
            batch.add(r)

    return batch

import asyncio

import httpx

from app.config import settings
from app.core.logger import get_logger
from app.core.exceptions import ShopeeAPIError

logger = get_logger(__name__)

_RETRIABLE_ERRORS = {"error_auth", "error_server", "error_push_too_fast"}
_MAX_RETRIES = 2
_BACKOFF_BASE = 0.5  # seconds: 0.5, 1.0, 2.0 ...


class ShopeeHttpAdapter:
    """Async HTTP adapter for Shopee Open API with connection pooling and exponential backoff."""

    def __init__(self):
        self.timeout = settings.DEFAULT_TIMEOUT
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init a persistent client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Graceful shutdown — close the connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        base_url: str,
        path: str,
        query: dict,
        body: dict | None = None,
    ) -> dict:
        url = f"{base_url}{path}"
        attempt = 0
        last_err: ShopeeAPIError | None = None
        client = await self._get_client()

        while attempt <= _MAX_RETRIES:
            attempt += 1
            try:
                if method.upper() == "GET":
                    resp = await client.get(url, params=query)
                else:
                    resp = await client.post(url, params=query, json=body or {})

                resp.raise_for_status()

                try:
                    data = resp.json()
                except ValueError as exc:
                    raise ShopeeAPIError(
                        error_code="INVALID_JSON",
                        error_msg=f"Response is not valid JSON: {resp.text[:200]}",
                    ) from exc

                error_code = data.get("error", "")
                if error_code:
                    if error_code in _RETRIABLE_ERRORS and attempt <= _MAX_RETRIES:
                        delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "retriable | %s | attempt %d | %s | backoff %.1fs",
                            path, attempt, error_code, delay,
                        )
                        last_err = ShopeeAPIError(
                            error_code=error_code,
                            error_msg=data.get("message", ""),
                            request_id=data.get("request_id", ""),
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise ShopeeAPIError(
                        error_code=error_code,
                        error_msg=data.get("message", ""),
                        request_id=data.get("request_id", ""),
                    )

                return data

            except httpx.HTTPStatusError as exc:
                logger.error("http_error | %s | %d", path, exc.response.status_code)
                raise ShopeeAPIError(
                    error_code=f"HTTP_{exc.response.status_code}",
                    error_msg=str(exc),
                ) from exc
            except httpx.RequestError as exc:
                logger.error("network_error | %s | %s", path, str(exc))
                if attempt <= _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning("network_retry | %s | backoff %.1fs", path, delay)
                    last_err = ShopeeAPIError(error_code="NETWORK_ERROR", error_msg=str(exc))
                    await asyncio.sleep(delay)
                    continue
                raise ShopeeAPIError(error_code="NETWORK_ERROR", error_msg=str(exc)) from exc

        if last_err is not None:
            raise last_err
        raise ShopeeAPIError(error_code="UNKNOWN_ERROR", error_msg="Request failed with no error details")

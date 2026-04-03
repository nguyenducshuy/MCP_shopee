"""Bearer token authentication middleware — pure ASGI, SSE-compatible."""
import hmac
import json

from app.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class BearerAuthMiddleware:
    """Pure ASGI middleware (not BaseHTTPMiddleware) so SSE streaming works.

    - Skipped when MCP_API_KEY is empty (dev mode).
    - Uses constant-time comparison to prevent timing attacks.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not settings.MCP_API_KEY:
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()

        if not auth.startswith("Bearer "):
            client = scope.get("client", ("?",))[0]
            logger.warning("auth_rejected | missing Bearer token | %s", client)
            return await self._reject(send, 401, "Missing Bearer token")

        token = auth[7:]
        if not hmac.compare_digest(token, settings.MCP_API_KEY):
            client = scope.get("client", ("?",))[0]
            logger.warning("auth_rejected | invalid token | %s", client)
            return await self._reject(send, 403, "Invalid API key")

        return await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send, status: int, message: str):
        body = json.dumps({"error": message}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({"type": "http.response.body", "body": body})

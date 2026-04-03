import asyncio

from app.core.constants import ACCESS_TOKEN_LIFETIME, REFRESH_TOKEN_LIFETIME
from app.core.exceptions import (
    TokenNotFoundError,
    TokenExpiredError,
    RefreshTokenExpiredError,
    ShopeeAPIError,
)
from app.core.logger import get_logger
from app.core.utils import now_ts
from app.config import settings
from app.repositories.token_repository import TokenRepository

logger = get_logger(__name__)


class TokenService:
    def __init__(self, token_repo: TokenRepository | None = None):
        self.repo = token_repo or TokenRepository()
        self._auth_service = None  # lazy inject to avoid circular import
        self._refresh_lock = asyncio.Lock()  # global fallback
        self._shop_locks: dict[str, asyncio.Lock] = {}  # per-shop locks

    def _get_shop_lock(self, shop_code: str) -> asyncio.Lock:
        """Get or create per-shop refresh lock."""
        if shop_code not in self._shop_locks:
            self._shop_locks[shop_code] = asyncio.Lock()
        return self._shop_locks[shop_code]

    def set_auth_service(self, auth_service):
        """Inject AuthService after construction (avoids circular dependency)."""
        self._auth_service = auth_service

    # ── Read helpers ───────────────────────────────────────────────

    def get_access_token(self, shop_code: str) -> str:
        """Return a valid access_token or raise."""
        token = self.repo.get_by_shop_code(shop_code)
        if not token or not token.get("access_token"):
            raise TokenNotFoundError(f"No token for shop {shop_code}.")

        expire_at = token.get("token_expire_at", 0)
        # T9 fix: expire_at=0 means token never properly saved → treat as missing
        if not expire_at:
            raise TokenNotFoundError(f"Token for shop {shop_code} has no expiry — re-exchange required.")

        remaining = expire_at - now_ts()
        if remaining < 0:
            logger.warning("token_expired | %s | expired %ds ago", shop_code, abs(remaining))
            raise TokenExpiredError(f"Token expired for shop {shop_code}.")

        logger.info(
            "token_loaded | %s | token=...%s | expires_in=%ds",
            shop_code,
            token["access_token"][-8:] if len(token["access_token"]) > 8 else "***",
            remaining,
        )
        return token["access_token"]

    def get_refresh_token(self, shop_code: str) -> str:
        token = self.repo.get_by_shop_code(shop_code)
        if not token or not token.get("refresh_token"):
            raise TokenNotFoundError(f"No refresh token for shop {shop_code}.")

        # T12 fix: check refresh_expire_at before using
        refresh_expire_at = token.get("refresh_expire_at", 0)
        if refresh_expire_at and refresh_expire_at < now_ts():
            raise RefreshTokenExpiredError(
                f"Refresh token for shop {shop_code} expired. "
                f"Please re-authorize the shop using get_auth_url → exchange_token."
            )

        return token["refresh_token"]

    def has_valid_token(self, shop_code: str) -> bool:
        token = self.repo.get_by_shop_code(shop_code)
        if not token or not token.get("access_token"):
            return False
        expire_at = token.get("token_expire_at", 0)
        # T9 fix: expire_at=0 → not valid
        if not expire_at:
            return False
        if expire_at - now_ts() < 0:
            return False
        return True

    def needs_refresh(self, shop_code: str) -> bool:
        """Token exists but is within the refresh window."""
        token = self.repo.get_by_shop_code(shop_code)
        if not token or not token.get("access_token"):
            return False
        expire_at = token.get("token_expire_at", 0)
        if not expire_at:
            return True
        return expire_at - now_ts() < settings.TOKEN_REFRESH_BEFORE_SECONDS

    def get_token_status(self, shop_code: str) -> dict:
        """Return detailed token status for admin tools."""
        token = self.repo.get_by_shop_code(shop_code)
        ts = now_ts()
        if not token or not token.get("access_token"):
            return {"status": "MISSING", "message": "No token found. Use exchange_token to obtain one."}

        expire_at = token.get("token_expire_at", 0)
        refresh_expire_at = token.get("refresh_expire_at", 0)

        access_remaining = (expire_at - ts) if expire_at else 0
        refresh_remaining = (refresh_expire_at - ts) if refresh_expire_at else 0

        if refresh_expire_at and refresh_remaining < 0:
            status = "REFRESH_EXPIRED"
            message = f"Refresh token expired {abs(refresh_remaining)}s ago. Re-authorize required."
        elif not expire_at or access_remaining < 0:
            status = "ACCESS_EXPIRED"
            message = f"Access token expired. Will auto-refresh on next API call."
        elif access_remaining < settings.TOKEN_REFRESH_BEFORE_SECONDS:
            status = "EXPIRING_SOON"
            message = f"Access token expires in {access_remaining}s. Will refresh on next call."
        else:
            status = "VALID"
            message = f"Access token valid for {access_remaining}s."

        return {
            "status": status,
            "message": message,
            "access_token_tail": "..." + token["access_token"][-8:] if token["access_token"] else "",
            "access_expires_in_seconds": max(access_remaining, 0),
            "access_expires_in_human": _format_duration(access_remaining),
            "refresh_expires_in_seconds": max(refresh_remaining, 0),
            "refresh_expires_in_human": _format_duration(refresh_remaining),
        }

    # ── Write helpers ──────────────────────────────────────────────

    def save_token(self, shop_code: str, api_response: dict) -> dict:
        """Persist token data from Shopee API response."""
        ts = now_ts()
        expire_in = api_response.get("expire_in", ACCESS_TOKEN_LIFETIME)
        token_data = {
            "access_token": api_response["access_token"],
            "refresh_token": api_response["refresh_token"],
            "token_expire_at": ts + expire_in,
            "refresh_expire_at": ts + REFRESH_TOKEN_LIFETIME,
        }
        self.repo.save_token(shop_code, token_data)
        logger.info("token_saved | %s | expires_in=%ds", shop_code, expire_in)
        return token_data

    def clear_token(self, shop_code: str) -> None:
        """Clear all token data for a shop (admin/debug)."""
        self.repo.save_token(shop_code, {
            "access_token": "",
            "refresh_token": "",
            "token_expire_at": 0,
            "refresh_expire_at": 0,
        })
        logger.info("token_cleared | %s", shop_code)

    def invalidate_access_token(self, shop_code: str) -> None:
        """Drop only the access token so the next call can refresh using the saved refresh token."""
        token = self.repo.get_by_shop_code(shop_code)
        if not token:
            return
        self.repo.save_token(shop_code, {
            "access_token": "",
            "refresh_token": token.get("refresh_token", ""),
            "token_expire_at": 0,
            "refresh_expire_at": token.get("refresh_expire_at", 0),
        })
        logger.info("access_token_invalidated | %s", shop_code)

    # ── Main auto-resolve ──────────────────────────────────────────

    async def ensure_token(self, shop_code: str, shop: dict) -> str:
        """Auto-resolve token: exchange code if empty, refresh if expired, return access_token."""
        if not self._auth_service:
            raise RuntimeError("AuthService not injected into TokenService.")

        shop_id = shop["shop_id"]
        environment = shop.get("environment", "sandbox")

        # Case 1: no valid token → exchange code or refresh
        if not self.has_valid_token(shop_code):
            shop_lock = self._get_shop_lock(shop_code)
            async with shop_lock:
                # Double-check after acquiring lock (another call may have refreshed)
                if self.has_valid_token(shop_code):
                    return self.get_access_token(shop_code)

                token = self.repo.get_by_shop_code(shop_code)
                has_refresh = token and token.get("refresh_token")

                try:
                    if has_refresh:
                        # T12: check refresh_expire_at before attempting
                        refresh_expire_at = token.get("refresh_expire_at", 0)
                        if refresh_expire_at and refresh_expire_at < now_ts():
                            raise RefreshTokenExpiredError(
                                f"Refresh token expired for shop {shop_code}. "
                                f"Re-authorize using get_auth_url → exchange_token."
                            )
                        logger.info("ensure_token | %s | refreshing expired token", shop_code)
                        resp = await self._auth_service.refresh_token(
                            token["refresh_token"], shop_id, environment
                        )
                    else:
                        code = shop.get("code_oauth", "")
                        if not code:
                            raise TokenNotFoundError(
                                f"No code and no token for shop {shop_code}. "
                                f"Use get_auth_url to get an authorization link, "
                                f"then exchange_token with the code."
                            )
                        logger.info("ensure_token | %s | exchanging code for token", shop_code)
                        resp = await self._auth_service.get_token_by_code(code, shop_id, environment)
                except ShopeeAPIError as exc:
                    # T4: detect auth errors specifically
                    if exc.error_code in ("error_auth", "invalid_refresh_token"):
                        # Clear stale tokens
                        self.clear_token(shop_code)
                        raise RefreshTokenExpiredError(
                            f"Token revoked/invalid for shop {shop_code}. "
                            f"Cleared stale token. Re-authorize using get_auth_url → exchange_token."
                        ) from exc
                    logger.error("ensure_token | %s | failed: %s", shop_code, exc)
                    raise TokenNotFoundError(
                        f"Failed to obtain token for shop {shop_code}: {exc}"
                    ) from exc

                if "access_token" not in resp or not resp["access_token"]:
                    raise TokenNotFoundError(f"Shopee returned empty token for shop {shop_code}.")

                self.save_token(shop_code, resp)

                # T5: clear code after successful exchange (code is single-use)
                if not has_refresh:
                    self.repo.shop_repo.update_shop(shop_code, {"code_oauth": ""})
                    logger.info("ensure_token | %s | cleared used OAuth code", shop_code)

                return resp["access_token"]

        # Case 2: token exists but needs refresh soon
        if self.needs_refresh(shop_code):
            shop_lock = self._get_shop_lock(shop_code)
            async with shop_lock:
                # Double-check
                if not self.needs_refresh(shop_code):
                    return self.get_access_token(shop_code)

                try:
                    refresh_tok = self.get_refresh_token(shop_code)
                    logger.info("ensure_token | %s | proactive refresh (expiring soon)", shop_code)
                    resp = await self._auth_service.refresh_token(refresh_tok, shop_id, environment)
                    self.save_token(shop_code, resp)
                    return resp["access_token"]
                except RefreshTokenExpiredError:
                    raise  # T3: propagate clearly
                except (ShopeeAPIError, TokenNotFoundError) as exc:
                    logger.warning(
                        "ensure_token | %s | proactive refresh failed, using current token: %s",
                        shop_code, exc,
                    )
                    return self.get_access_token(shop_code)

        # Case 3: token is valid
        return self.get_access_token(shop_code)


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "expired"
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)

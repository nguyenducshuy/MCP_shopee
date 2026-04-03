from app.config import settings
from app.core.constants import TOKEN_GET_PATH, TOKEN_REFRESH_PATH
from app.core.logger import get_logger
from app.services.sign_service import SignService
from app.adapters.shopee_http_adapter import ShopeeHttpAdapter

logger = get_logger(__name__)


class AuthService:
    def __init__(self, sign_service: SignService, http_adapter: ShopeeHttpAdapter):
        self.sign = sign_service
        self.http = http_adapter

    async def get_token_by_code(self, code: str, shop_id: int, environment: str = "sandbox") -> dict:
        """Exchange auth code for access_token + refresh_token."""
        base_url = settings.get_base_url(environment)
        partner_id, _ = settings.get_partner_credentials(environment)
        query = self.sign.common_query(TOKEN_GET_PATH, environment=environment)
        body = {
            "code": code,
            "shop_id": shop_id,
            "partner_id": partner_id,
        }
        logger.info("get_token_by_code | shop_id=%d | env=%s", shop_id, environment)
        resp = await self.http.request("POST", base_url, TOKEN_GET_PATH, query=query, body=body)
        logger.info(
            "get_token_by_code | access_token=%s | refresh_token=%s | expire_in=%s",
            resp.get("access_token", "N/A")[-8:] if resp.get("access_token") else "EMPTY",
            resp.get("refresh_token", "N/A")[-8:] if resp.get("refresh_token") else "EMPTY",
            resp.get("expire_in", "N/A"),
        )
        return resp

    async def refresh_token(self, refresh_token: str, shop_id: int, environment: str = "sandbox") -> dict:
        """Refresh an expiring access_token."""
        base_url = settings.get_base_url(environment)
        partner_id, _ = settings.get_partner_credentials(environment)
        query = self.sign.common_query(TOKEN_REFRESH_PATH, environment=environment)
        body = {
            "refresh_token": refresh_token,
            "shop_id": shop_id,
            "partner_id": partner_id,
        }
        logger.info("refresh_token | shop_id=%d | env=%s", shop_id, environment)
        resp = await self.http.request("POST", base_url, TOKEN_REFRESH_PATH, query=query, body=body)
        logger.info(
            "refresh_token | new_access_token=%s | new_refresh_token=%s | expire_in=%s",
            resp.get("access_token", "N/A")[-8:] if resp.get("access_token") else "EMPTY",
            resp.get("refresh_token", "N/A")[-8:] if resp.get("refresh_token") else "EMPTY",
            resp.get("expire_in", "N/A"),
        )
        return resp

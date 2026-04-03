from app.config import settings
from app.core.logger import get_logger
from app.core.exceptions import ShopNotFoundError, ShopeeAPIError
from app.services.shop_registry_service import ShopRegistryService
from app.services.token_service import TokenService
from app.services.sign_service import SignService
from app.services.endpoint_registry_service import EndpointRegistryService
from app.adapters.shopee_http_adapter import ShopeeHttpAdapter

logger = get_logger(__name__)

_AUTH_RETRY_ERRORS = {"error_auth"}


class ShopeeClient:
    """Central client that orchestrates sign → token → HTTP for any Shopee API call."""

    def __init__(
        self,
        shop_registry_service: ShopRegistryService,
        token_service: TokenService,
        sign_service: SignService,
        endpoint_registry_service: EndpointRegistryService,
        http_adapter: ShopeeHttpAdapter,
    ):
        self.shops = shop_registry_service
        self.tokens = token_service
        self.sign = sign_service
        self.endpoints = endpoint_registry_service
        self.http = http_adapter

    def _resolve_shop(self, shop_code: str) -> dict:
        shop = self.shops.get_shop(shop_code)
        if not shop:
            raise ShopNotFoundError(f"Shop '{shop_code}' not found in registry.")
        return shop

    async def call(
        self,
        shop_code: str,
        endpoint_key: str,
        body: dict | None = None,
        extra_params: dict | None = None,
    ) -> dict:
        shop = self._resolve_shop(shop_code)
        shop_id = shop["shop_id"]
        environment = shop.get("environment", "sandbox")
        base_url = settings.get_base_url(environment)

        endpoint = self.endpoints.get_endpoint(endpoint_key)
        if not endpoint:
            raise ValueError(f"Unknown endpoint key: {endpoint_key}")

        path = endpoint["path"]
        method = endpoint["method"]

        # T7: retry once with fresh token on error_auth
        for attempt in range(2):
            access_token = await self.tokens.ensure_token(shop_code, shop)
            query = self.sign.common_query(path, access_token=access_token, shop_id=shop_id, environment=environment)
            if extra_params:
                query.update(extra_params)

            logger.info(
                "api_call | %s %s | shop=%s | shop_id=%d | token=...%s | sign=%s",
                method, path, shop_code, shop_id,
                access_token[-8:] if (access_token and len(access_token) > 8) else "***",
                query.get("sign", "")[:12] + "...",
            )

            try:
                data = await self.http.request(method, base_url, path, query=query, body=body)
            except ShopeeAPIError as exc:
                # T7: if error_auth on first attempt, invalidate token and retry
                if exc.error_code in _AUTH_RETRY_ERRORS and attempt == 0:
                    logger.warning(
                        "api_auth_retry | %s | token rejected, forcing refresh",
                        endpoint_key,
                    )
                    self.tokens.invalidate_access_token(shop_code)
                    continue
                raise

            # Also check Shopee-level error_auth in response (non-HTTP error cases)
            error_code = data.get("error", "")
            if error_code in _AUTH_RETRY_ERRORS and attempt == 0:
                logger.warning(
                    "api_auth_retry | %s | response error_auth, forcing refresh",
                    endpoint_key,
                )
                self.tokens.invalidate_access_token(shop_code)
                continue

            raw_resp = data.get("response", data)
            logger.info(
                "api_resp | %s | error=%s | request_id=%s | resp_type=%s | resp_preview=%.100s",
                endpoint_key, data.get("error", ""), data.get("request_id", ""),
                type(raw_resp).__name__, str(raw_resp)[:100],
            )

            # Trích xuất response — Shopee v2 wrap: {"error":"","response":{...}}
            if isinstance(data, dict):
                resp = raw_resp
                # Nếu response rỗng/null → trả {"_empty": true} để caller biết
                if resp is None:
                    logger.warning("api_resp_empty | %s | response is None", endpoint_key)
                    return {"_empty": True}
                if isinstance(resp, str) and resp == "":
                    logger.warning("api_resp_empty | %s | response is empty string", endpoint_key)
                    return {"_empty": True}
                return resp
            return data if data is not None else {"_empty": True}

        # Should not reach here, but safety net
        raise ShopeeAPIError(error_code="AUTH_RETRY_EXHAUSTED", error_msg="Token refresh retry exhausted")

import hashlib
import hmac

from app.config import settings
from app.core.utils import now_ts


class SignService:
    def __init__(self):
        pass

    def _get_credentials(self, environment: str = "sandbox") -> tuple[int, str]:
        return settings.get_partner_credentials(environment)

    def make_sign(self, partner_key: str, base_string: str) -> str:
        """HMAC-SHA256 sign a pre-built base_string."""
        return hmac.new(
            partner_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def sign_api(self, path: str, timestamp: int, access_token: str = "", shop_id: int = 0, environment: str = "sandbox") -> str:
        """Sign a normal API call: partner_id + path + timestamp + access_token + shop_id"""
        partner_id, partner_key = self._get_credentials(environment)
        base = f"{partner_id}{path}{timestamp}{access_token}{shop_id}"
        return self.make_sign(partner_key, base)

    def sign_auth(self, path: str, timestamp: int, environment: str = "sandbox") -> str:
        """Sign an auth-level call (no access_token / shop_id): partner_id + path + timestamp"""
        partner_id, partner_key = self._get_credentials(environment)
        base = f"{partner_id}{path}{timestamp}"
        return self.make_sign(partner_key, base)

    def common_query(self, path: str, access_token: str = "", shop_id: int = 0, environment: str = "sandbox") -> dict:
        """Build the common query params required by every Shopee API call."""
        partner_id, _ = self._get_credentials(environment)
        ts = now_ts()
        if access_token:
            sign = self.sign_api(path, ts, access_token, shop_id, environment)
        else:
            sign = self.sign_auth(path, ts, environment)
        params: dict = {
            "partner_id": partner_id,
            "timestamp": ts,
            "sign": sign,
        }
        if access_token:
            params["access_token"] = access_token
            params["shop_id"] = shop_id
        return params

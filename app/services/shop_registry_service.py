import secrets

from app.core.logger import get_logger
from app.repositories.shop_repository import ShopRepository

logger = get_logger(__name__)


class ShopRegistryService:
    def __init__(self, repo: ShopRepository | None = None):
        self.repo = repo or ShopRepository()

    def get_shop(self, shop_code: str) -> dict:
        return self.repo.get_by_code(shop_code)

    def list_shops(self) -> list[dict]:
        return self.repo.get_all()

    def add_shop(
        self,
        shop_id: int,
        shop_name: str,
        region: str = "VN",
        environment: str = "sandbox",
        code: str = "",
    ) -> dict:
        """Add a new shop. Auto-generates a shop_code."""
        shop_code = secrets.token_hex(16)
        shop = {
            "code": shop_code,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "region": region,
            "environment": environment,
            "is_active": True,
            "code_oauth": code,
            "access_token": "",
            "refresh_token": "",
            "token_expire_at": 0,
            "refresh_expire_at": 0,
        }
        return self.repo.add_shop(shop)

    def update_shop(self, shop_code: str, updates: dict) -> dict:
        return self.repo.update_shop(shop_code, updates)

    def remove_shop(self, shop_code: str) -> bool:
        return self.repo.remove_shop(shop_code)

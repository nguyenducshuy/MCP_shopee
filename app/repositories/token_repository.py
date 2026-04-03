from app.repositories.shop_repository import ShopRepository


class TokenRepository:
    def __init__(self, shop_repo: ShopRepository | None = None):
        self.shop_repo = shop_repo or ShopRepository()

    def get_by_shop_code(self, shop_code: str) -> dict:
        shop = self.shop_repo.get_by_code(shop_code)
        if not shop:
            return {}
        return {
            "access_token": shop.get("access_token", ""),
            "refresh_token": shop.get("refresh_token", ""),
            "token_expire_at": shop.get("token_expire_at", 0),
            "refresh_expire_at": shop.get("refresh_expire_at", 0),
        }

    def save_token(self, shop_code: str, token_data: dict) -> dict:
        return self.shop_repo.update_shop(shop_code, {
            "access_token": token_data.get("access_token", ""),
            "refresh_token": token_data.get("refresh_token", ""),
            "token_expire_at": token_data.get("token_expire_at", 0),
            "refresh_expire_at": token_data.get("refresh_expire_at", 0),
        })

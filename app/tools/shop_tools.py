"""Shop tools — chỉ giữ tools cần cho Flash Sale."""
from app.dependencies import shopee_client, shop_registry_service


def register_shop_tools(mcp):
    @mcp.tool()
    def list_shops() -> dict:
        """Liệt kê tất cả shop đã đăng ký."""
        shops = shop_registry_service.list_shops()
        return {
            "ok": True,
            "shops": [
                {"shop_code": s["code"], "shop_id": s.get("shop_id"), "shop_name": s["shop_name"], "region": s["region"], "environment": s.get("environment", "")}
                for s in shops
            ],
        }

    @mcp.tool()
    async def get_shop_info(shop_code: str) -> dict:
        """Lấy thông tin cơ bản của 1 shop từ Shopee API."""
        return await shopee_client.call(shop_code, "shop.get_shop_info")

    @mcp.tool()
    async def get_shop_holiday_mode(shop_code: str) -> dict:
        """Kiểm tra trạng thái chế độ nghỉ lễ của shop.
        Flash Sale không chạy được khi shop ở holiday mode."""
        return await shopee_client.call(shop_code, "shop.get_shop_holiday_mode")

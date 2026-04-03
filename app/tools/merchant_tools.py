"""Merchant tools — quản lý merchant (đa shop)."""
from app.dependencies import shopee_client


def register_merchant_tools(mcp):

    @mcp.tool()
    async def get_merchant_info(shop_code: str) -> dict:
        """Lấy thông tin merchant."""
        return await shopee_client.call(shop_code, "merchant.get_merchant_info")

    @mcp.tool()
    async def get_shop_list_by_merchant(shop_code: str, page_no: int = 1, page_size: int = 100) -> dict:
        """Lấy danh sách shop thuộc merchant."""
        return await shopee_client.call(
            shop_code, "merchant.get_shop_list_by_merchant",
            extra_params={"page_no": page_no, "page_size": page_size},
        )

    @mcp.tool()
    async def get_merchant_warehouse_location_list(shop_code: str) -> dict:
        """Lấy danh sách vị trí kho của merchant."""
        return await shopee_client.call(shop_code, "merchant.get_merchant_warehouse_location_list")

    @mcp.tool()
    async def get_merchant_warehouse_list(shop_code: str) -> dict:
        """Lấy danh sách kho của merchant."""
        return await shopee_client.call(shop_code, "merchant.get_merchant_warehouse_list")

    @mcp.tool()
    async def get_warehouse_eligible_shop_list(shop_code: str, warehouse_id: int) -> dict:
        """Lấy danh sách shop có thể dùng kho."""
        return await shopee_client.call(
            shop_code, "merchant.get_warehouse_eligible_shop_list",
            extra_params={"warehouse_id": warehouse_id},
        )

    @mcp.tool()
    async def get_merchant_prepaid_account_list(shop_code: str) -> dict:
        """Lấy danh sách tài khoản trả trước của merchant."""
        return await shopee_client.call(shop_code, "merchant.get_merchant_prepaid_account_list")

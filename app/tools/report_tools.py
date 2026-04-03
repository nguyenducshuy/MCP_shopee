from app.dependencies import shopee_client


def register_report_tools(mcp):
    @mcp.tool()
    async def get_shop_health_report(shop_code: str) -> dict:
        """Lấy báo cáo sức khỏe shop (Account Health)."""
        return await shopee_client.call(
            shop_code,
            "account_health.shop_performance",
        )

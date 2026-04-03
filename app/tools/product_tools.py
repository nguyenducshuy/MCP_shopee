"""Product tools — chỉ giữ tools cần cho Flash Sale (lấy thông tin SP, giá, tồn kho, model)."""
from app.dependencies import shopee_client


def register_product_tools(mcp):

    @mcp.tool()
    async def get_item_list(shop_code: str, offset: int = 0, page_size: int = 50, item_status: str = "NORMAL") -> dict:
        """Lấy danh sách sản phẩm của shop. item_status: NORMAL, BANNED, DELETED, UNLIST."""
        return await shopee_client.call(
            shop_code, "product.get_item_list",
            extra_params={"offset": offset, "page_size": page_size, "item_status": item_status},
        )

    @mcp.tool()
    async def get_item_base_info(shop_code: str, item_id_list: str) -> dict:
        """Lấy thông tin cơ bản SP: tên, giá, tồn kho, model (biến thể).
        item_id_list: danh sách ID cách nhau bởi dấu phẩy (VD: '123,456')."""
        return await shopee_client.call(
            shop_code, "product.get_item_base_info",
            extra_params={"item_id_list": item_id_list},
        )

    @mcp.tool()
    async def get_model_list(shop_code: str, item_id: int) -> dict:
        """Lấy danh sách model (biến thể) của SP: model_id, giá, tồn kho, SKU."""
        return await shopee_client.call(
            shop_code, "product.get_model_list",
            extra_params={"item_id": item_id},
        )

    @mcp.tool()
    async def get_item_extra_info(shop_code: str, item_id_list: str) -> dict:
        """Lấy thông tin mở rộng SP: lượt thích, xem, bán. item_id_list: '123,456'."""
        return await shopee_client.call(
            shop_code, "product.get_item_extra_info",
            extra_params={"item_id_list": item_id_list},
        )

    @mcp.tool()
    async def get_item_promotion(shop_code: str, item_id_list: str) -> dict:
        """Lấy thông tin khuyến mãi đang áp dụng cho SP. Dùng để check SP có đang trong promotion khác không.
        item_id_list: '123,456'."""
        return await shopee_client.call(
            shop_code, "product.get_item_promotion",
            extra_params={"item_id_list": item_id_list},
        )

    @mcp.tool()
    async def search_item(shop_code: str, item_name: str = "", offset: int = 0, page_size: int = 50) -> dict:
        """Tìm kiếm sản phẩm trong shop theo tên."""
        params: dict = {"offset": offset, "page_size": page_size}
        if item_name:
            params["item_name"] = item_name
        return await shopee_client.call(
            shop_code, "product.search_item",
            extra_params=params,
        )

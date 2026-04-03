from app.dependencies import shopee_client


def register_global_product_tools(mcp):
    # ── Danh mục & thuộc tính (Global) ───────────────────────────────

    @mcp.tool()
    async def gp_get_category(shop_code: str, language: str = "vi") -> dict:
        """Lấy danh sách danh mục sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_category",
            extra_params={"language": language},
        )

    @mcp.tool()
    async def gp_get_attribute_tree(shop_code: str, category_id: int, language: str = "vi") -> dict:
        """Lấy cây thuộc tính của 1 danh mục toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_attribute_tree",
            extra_params={"category_id": category_id, "language": language},
        )

    @mcp.tool()
    async def gp_get_brand_list(shop_code: str, category_id: int, offset: int = 0, page_size: int = 100, status: int = 1) -> dict:
        """Lấy danh sách thương hiệu theo danh mục toàn cầu. status: 1=active, 2=pending."""
        return await shopee_client.call(
            shop_code, "global_product.get_brand_list",
            extra_params={"category_id": category_id, "offset": offset, "page_size": page_size, "status": status},
        )

    @mcp.tool()
    async def gp_get_global_item_limit(shop_code: str) -> dict:
        """Lấy giới hạn số lượng sản phẩm toàn cầu của shop."""
        return await shopee_client.call(shop_code, "global_product.get_global_item_limit")

    @mcp.tool()
    async def gp_get_global_item_list(shop_code: str, offset: int = 0, page_size: int = 50) -> dict:
        """Lấy danh sách sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_global_item_list",
            extra_params={"offset": offset, "page_size": page_size},
        )

    @mcp.tool()
    async def gp_get_global_item_info(shop_code: str, global_item_id_list: str) -> dict:
        """Lấy thông tin sản phẩm toàn cầu. global_item_id_list: danh sách ID cách nhau bởi dấu phẩy (VD: '123,456')."""
        return await shopee_client.call(
            shop_code, "global_product.get_global_item_info",
            extra_params={"global_item_id_list": global_item_id_list},
        )

    @mcp.tool()
    async def gp_get_global_model_list(shop_code: str, global_item_id: int) -> dict:
        """Lấy danh sách model của sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_global_model_list",
            extra_params={"global_item_id": global_item_id},
        )

    @mcp.tool()
    async def gp_support_size_chart(shop_code: str, category_id: int) -> dict:
        """Kiểm tra danh mục có hỗ trợ bảng size hay không."""
        return await shopee_client.call(
            shop_code, "global_product.support_size_chart",
            extra_params={"category_id": category_id},
        )

    @mcp.tool()
    async def gp_get_publishable_shop(shop_code: str, global_item_id: int) -> dict:
        """Lấy danh sách shop có thể publish sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_publishable_shop",
            extra_params={"global_item_id": global_item_id},
        )

    @mcp.tool()
    async def gp_get_publish_task_result(shop_code: str, publish_task_id: int) -> dict:
        """Lấy kết quả của task publish sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_publish_task_result",
            extra_params={"publish_task_id": publish_task_id},
        )

    @mcp.tool()
    async def gp_get_published_list(shop_code: str, global_item_id: int, offset: int = 0, page_size: int = 50) -> dict:
        """Lấy danh sách sản phẩm đã publish từ sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_published_list",
            extra_params={"global_item_id": global_item_id, "offset": offset, "page_size": page_size},
        )

    @mcp.tool()
    async def gp_get_global_item_id(shop_code: str, item_id: int) -> dict:
        """Lấy global_item_id từ item_id của shop."""
        return await shopee_client.call(
            shop_code, "global_product.get_global_item_id",
            extra_params={"item_id": item_id},
        )

    @mcp.tool()
    async def gp_category_recommend(shop_code: str, item_name: str) -> dict:
        """Gợi ý danh mục toàn cầu phù hợp dựa trên tên sản phẩm."""
        return await shopee_client.call(
            shop_code, "global_product.category_recommend",
            extra_params={"item_name": item_name},
        )

    @mcp.tool()
    async def gp_get_recommend_attribute(shop_code: str, category_id: int, item_name: str = "") -> dict:
        """Gợi ý giá trị thuộc tính cho sản phẩm toàn cầu."""
        params = {"category_id": category_id}
        if item_name:
            params["item_name"] = item_name
        return await shopee_client.call(
            shop_code, "global_product.get_recommend_attribute",
            extra_params=params,
        )

    @mcp.tool()
    async def gp_get_shop_publishable_status(shop_code: str) -> dict:
        """Lấy trạng thái publish được của các shop."""
        return await shopee_client.call(shop_code, "global_product.get_shop_publishable_status")

    @mcp.tool()
    async def gp_get_variations(shop_code: str, global_item_id: int) -> dict:
        """Lấy danh sách biến thể của sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_variations",
            extra_params={"global_item_id": global_item_id},
        )

    @mcp.tool()
    async def gp_get_size_chart_detail(shop_code: str, size_chart_id: int) -> dict:
        """Lấy chi tiết bảng size."""
        return await shopee_client.call(
            shop_code, "global_product.get_size_chart_detail",
            extra_params={"size_chart_id": size_chart_id},
        )

    @mcp.tool()
    async def gp_get_size_chart_list(shop_code: str, category_id: int, page_size: int = 50) -> dict:
        """Lấy danh sách bảng size theo danh mục."""
        return await shopee_client.call(
            shop_code, "global_product.get_size_chart_list",
            extra_params={"category_id": category_id, "page_size": page_size},
        )

    @mcp.tool()
    async def gp_search_global_attribute_value_list(shop_code: str, attribute_id: int, keyword: str, language: str = "vi") -> dict:
        """Tìm kiếm giá trị thuộc tính toàn cầu theo keyword."""
        return await shopee_client.call(
            shop_code, "global_product.search_global_attribute_value_list",
            extra_params={"attribute_id": attribute_id, "keyword": keyword, "language": language},
        )

    @mcp.tool()
    async def gp_get_local_adjustment_rate(shop_code: str, global_item_id: int) -> dict:
        """Lấy tỷ lệ điều chỉnh giá local của sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.get_local_adjustment_rate",
            extra_params={"global_item_id": global_item_id},
        )

    # ── POST endpoints ───────────────────────────────────────────────

    @mcp.tool()
    async def gp_add_global_item(shop_code: str, data: dict) -> dict:
        """Tạo sản phẩm toàn cầu mới."""
        return await shopee_client.call(
            shop_code, "global_product.add_global_item", body=data,
        )

    @mcp.tool()
    async def gp_update_global_item(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Cập nhật thông tin sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.update_global_item", body=data,
        )

    @mcp.tool()
    async def gp_delete_global_item(shop_code: str, global_item_id: int) -> dict:
        """Xoá sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.delete_global_item",
            body={"global_item_id": global_item_id},
        )

    @mcp.tool()
    async def gp_init_tier_variation(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Khởi tạo biến thể tier cho sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.init_tier_variation", body=data,
        )

    @mcp.tool()
    async def gp_update_tier_variation(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Cập nhật biến thể tier của sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.update_tier_variation", body=data,
        )

    @mcp.tool()
    async def gp_add_global_model(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Thêm model cho sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.add_global_model", body=data,
        )

    @mcp.tool()
    async def gp_update_global_model(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Cập nhật model của sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.update_global_model", body=data,
        )

    @mcp.tool()
    async def gp_delete_global_model(shop_code: str, global_item_id: int, model_id: int) -> dict:
        """Xoá model của sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.delete_global_model",
            body={"global_item_id": global_item_id, "model_id": model_id},
        )

    @mcp.tool()
    async def gp_update_size_chart(shop_code: str, data: dict) -> dict:
        """Cập nhật bảng size."""
        return await shopee_client.call(
            shop_code, "global_product.update_size_chart", body=data,
        )

    @mcp.tool()
    async def gp_create_publish_task(shop_code: str, data: dict) -> dict:
        """Tạo task publish sản phẩm toàn cầu ra các shop."""
        return await shopee_client.call(
            shop_code, "global_product.create_publish_task", body=data,
        )

    @mcp.tool()
    async def gp_update_price(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Cập nhật giá sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.update_price", body=data,
        )

    @mcp.tool()
    async def gp_update_stock(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Cập nhật tồn kho sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.update_stock", body=data,
        )

    @mcp.tool()
    async def gp_set_sync_field(shop_code: str, data: dict) -> dict:
        """Cài đặt các trường đồng bộ cho sản phẩm toàn cầu."""
        return await shopee_client.call(
            shop_code, "global_product.set_sync_field", body=data,
        )

    @mcp.tool()
    async def gp_update_local_adjustment_rate(shop_code: str, global_item_id: int, data: dict) -> dict:
        """Cập nhật tỷ lệ điều chỉnh giá local của sản phẩm toàn cầu."""
        data["global_item_id"] = global_item_id
        return await shopee_client.call(
            shop_code, "global_product.update_local_adjustment_rate", body=data,
        )

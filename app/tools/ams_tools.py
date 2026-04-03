from app.dependencies import shopee_client


def register_ams_tools(mcp):
    # ── Open Campaign - Product Management ────────────────────────

    @mcp.tool()
    async def ams_get_open_campaign_added_product(
        shop_code: str, page_size: int, cursor: str = "", sort_by: str = "", search_type: str = "", search_content: str = ""
    ) -> dict:
        """Lấy danh sách sản phẩm đã thêm vào chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.get_open_campaign_added_product",
            extra_params={"page_size": page_size, "cursor": cursor, "sort_by": sort_by, "search_type": search_type, "search_content": search_content},
        )

    @mcp.tool()
    async def ams_get_open_campaign_not_added_product(
        shop_code: str, page_size: int, cursor: str = ""
    ) -> dict:
        """Lấy danh sách sản phẩm chưa thêm vào chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.get_open_campaign_not_added_product",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_get_auto_add_new_product_toggle_status(shop_code: str) -> dict:
        """Lấy trạng thái bật/tắt tự động thêm sản phẩm mới."""
        return await shopee_client.call(
            shop_code, "ams.get_auto_add_new_product_toggle_status",
        )

    @mcp.tool()
    async def ams_get_open_campaign_batch_task_result(shop_code: str, task_id: int) -> dict:
        """Lấy kết quả tác vụ hàng loạt của chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.get_open_campaign_batch_task_result",
            extra_params={"task_id": task_id},
        )

    @mcp.tool()
    async def ams_get_optimization_suggestion_product(
        shop_code: str, page_size: int, cursor: str = ""
    ) -> dict:
        """Lấy danh sách sản phẩm có gợi ý tối ưu hóa."""
        return await shopee_client.call(
            shop_code, "ams.get_optimization_suggestion_product",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_batch_get_products_suggested_rate(shop_code: str, item_id_list: str) -> dict:
        """Lấy tỷ lệ hoa hồng gợi ý cho nhiều sản phẩm. item_id_list: chuỗi id cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code, "ams.batch_get_products_suggested_rate",
            extra_params={"item_id_list": item_id_list},
        )

    @mcp.tool()
    async def ams_get_shop_suggested_rate(shop_code: str) -> dict:
        """Lấy tỷ lệ hoa hồng gợi ý cho shop."""
        return await shopee_client.call(
            shop_code, "ams.get_shop_suggested_rate",
        )

    # ── Open Campaign - Batch Operations (POST) ──────────────────

    @mcp.tool()
    async def ams_batch_add_products_to_open_campaign(shop_code: str, data: dict) -> dict:
        """Thêm hàng loạt sản phẩm vào chiến dịch mở. data chứa item_list."""
        return await shopee_client.call(
            shop_code, "ams.batch_add_products_to_open_campaign", body=data,
        )

    @mcp.tool()
    async def ams_add_all_products_to_open_campaign(shop_code: str, data: dict) -> dict:
        """Thêm tất cả sản phẩm vào chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.add_all_products_to_open_campaign", body=data,
        )

    @mcp.tool()
    async def ams_update_auto_add_new_product_setting(shop_code: str, data: dict) -> dict:
        """Cập nhật cài đặt tự động thêm sản phẩm mới."""
        return await shopee_client.call(
            shop_code, "ams.update_auto_add_new_product_setting", body=data,
        )

    @mcp.tool()
    async def ams_batch_edit_products_open_campaign_setting(shop_code: str, data: dict) -> dict:
        """Chỉnh sửa hàng loạt cài đặt sản phẩm trong chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.batch_edit_products_open_campaign_setting", body=data,
        )

    @mcp.tool()
    async def ams_edit_all_products_open_campaign_setting(shop_code: str, data: dict) -> dict:
        """Chỉnh sửa cài đặt tất cả sản phẩm trong chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.edit_all_products_open_campaign_setting", body=data,
        )

    @mcp.tool()
    async def ams_batch_remove_products_open_campaign_setting(shop_code: str, data: dict) -> dict:
        """Xóa hàng loạt sản phẩm khỏi chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.batch_remove_products_open_campaign_setting", body=data,
        )

    @mcp.tool()
    async def ams_remove_all_products_open_campaign_setting(shop_code: str, data: dict) -> dict:
        """Xóa tất cả sản phẩm khỏi chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.remove_all_products_open_campaign_setting", body=data,
        )

    # ── Targeted Campaign ─────────────────────────────────────────

    @mcp.tool()
    async def ams_get_targeted_campaign_addable_product_list(
        shop_code: str, campaign_id: int, page_size: int = 20, cursor: str = ""
    ) -> dict:
        """Lấy danh sách sản phẩm có thể thêm vào chiến dịch nhắm mục tiêu."""
        return await shopee_client.call(
            shop_code, "ams.get_targeted_campaign_addable_product_list",
            extra_params={"campaign_id": campaign_id, "page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_get_targeted_campaign_list(
        shop_code: str, page_size: int = 20, cursor: str = ""
    ) -> dict:
        """Lấy danh sách chiến dịch nhắm mục tiêu."""
        return await shopee_client.call(
            shop_code, "ams.get_targeted_campaign_list",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_get_targeted_campaign_settings(shop_code: str, campaign_id: int) -> dict:
        """Lấy cài đặt của chiến dịch nhắm mục tiêu."""
        return await shopee_client.call(
            shop_code, "ams.get_targeted_campaign_settings",
            extra_params={"campaign_id": campaign_id},
        )

    @mcp.tool()
    async def ams_create_new_targeted_campaign(shop_code: str, data: dict) -> dict:
        """Tạo chiến dịch nhắm mục tiêu mới."""
        return await shopee_client.call(
            shop_code, "ams.create_new_targeted_campaign", body=data,
        )

    @mcp.tool()
    async def ams_update_basic_info_of_targeted_campaign(shop_code: str, campaign_id: int, data: dict) -> dict:
        """Cập nhật thông tin cơ bản của chiến dịch nhắm mục tiêu."""
        data["campaign_id"] = campaign_id
        return await shopee_client.call(
            shop_code, "ams.update_basic_info_of_targeted_campaign", body=data,
        )

    @mcp.tool()
    async def ams_edit_product_list_of_targeted_campaign(shop_code: str, campaign_id: int, data: dict) -> dict:
        """Chỉnh sửa danh sách sản phẩm của chiến dịch nhắm mục tiêu."""
        data["campaign_id"] = campaign_id
        return await shopee_client.call(
            shop_code, "ams.edit_product_list_of_targeted_campaign", body=data,
        )

    @mcp.tool()
    async def ams_edit_affiliate_list_of_targeted_campaign(shop_code: str, campaign_id: int, data: dict) -> dict:
        """Chỉnh sửa danh sách affiliate của chiến dịch nhắm mục tiêu."""
        data["campaign_id"] = campaign_id
        return await shopee_client.call(
            shop_code, "ams.edit_affiliate_list_of_targeted_campaign", body=data,
        )

    @mcp.tool()
    async def ams_terminate_targeted_campaign(shop_code: str, campaign_id: int) -> dict:
        """Kết thúc chiến dịch nhắm mục tiêu."""
        return await shopee_client.call(
            shop_code, "ams.terminate_targeted_campaign", body={"campaign_id": campaign_id},
        )

    # ── Affiliate Management ──────────────────────────────────────

    @mcp.tool()
    async def ams_get_recommended_affiliate_list(
        shop_code: str, page_size: int = 20, cursor: str = ""
    ) -> dict:
        """Lấy danh sách affiliate được đề xuất."""
        return await shopee_client.call(
            shop_code, "ams.get_recommended_affiliate_list",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_get_managed_affiliate_list(
        shop_code: str, page_size: int = 20, cursor: str = ""
    ) -> dict:
        """Lấy danh sách affiliate đang quản lý."""
        return await shopee_client.call(
            shop_code, "ams.get_managed_affiliate_list",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_query_affiliate_list(
        shop_code: str, page_size: int = 20, cursor: str = ""
    ) -> dict:
        """Truy vấn danh sách affiliate."""
        return await shopee_client.call(
            shop_code, "ams.query_affiliate_list",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    # ── Performance & Reporting ───────────────────────────────────

    @mcp.tool()
    async def ams_get_performance_data_update_time(shop_code: str) -> dict:
        """Lấy thời gian cập nhật dữ liệu hiệu suất."""
        return await shopee_client.call(
            shop_code, "ams.get_performance_data_update_time",
        )

    @mcp.tool()
    async def ams_get_shop_performance(shop_code: str, start_date: str, end_date: str) -> dict:
        """Lấy dữ liệu hiệu suất của shop. start_date, end_date: định dạng ngày."""
        return await shopee_client.call(
            shop_code, "ams.get_shop_performance",
            extra_params={"start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_product_performance(
        shop_code: str, page_size: int = 20, cursor: str = "", start_date: str = "", end_date: str = ""
    ) -> dict:
        """Lấy dữ liệu hiệu suất theo sản phẩm."""
        return await shopee_client.call(
            shop_code, "ams.get_product_performance",
            extra_params={"page_size": page_size, "cursor": cursor, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_affiliate_performance(
        shop_code: str, page_size: int = 20, cursor: str = "", start_date: str = "", end_date: str = ""
    ) -> dict:
        """Lấy dữ liệu hiệu suất theo affiliate."""
        return await shopee_client.call(
            shop_code, "ams.get_affiliate_performance",
            extra_params={"page_size": page_size, "cursor": cursor, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_content_performance(
        shop_code: str, page_size: int = 20, cursor: str = "", start_date: str = "", end_date: str = ""
    ) -> dict:
        """Lấy dữ liệu hiệu suất theo nội dung."""
        return await shopee_client.call(
            shop_code, "ams.get_content_performance",
            extra_params={"page_size": page_size, "cursor": cursor, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_campaign_key_metrics_performance(
        shop_code: str, start_date: str, end_date: str
    ) -> dict:
        """Lấy chỉ số hiệu suất chính của chiến dịch."""
        return await shopee_client.call(
            shop_code, "ams.get_campaign_key_metrics_performance",
            extra_params={"start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_open_campaign_performance(
        shop_code: str, start_date: str, end_date: str
    ) -> dict:
        """Lấy dữ liệu hiệu suất chiến dịch mở."""
        return await shopee_client.call(
            shop_code, "ams.get_open_campaign_performance",
            extra_params={"start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_targeted_campaign_performance(
        shop_code: str, campaign_id: int, start_date: str, end_date: str
    ) -> dict:
        """Lấy dữ liệu hiệu suất chiến dịch nhắm mục tiêu."""
        return await shopee_client.call(
            shop_code, "ams.get_targeted_campaign_performance",
            extra_params={"campaign_id": campaign_id, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ams_get_conversion_report(
        shop_code: str, page_size: int = 20, cursor: str = "", start_date: str = "", end_date: str = ""
    ) -> dict:
        """Lấy báo cáo chuyển đổi."""
        return await shopee_client.call(
            shop_code, "ams.get_conversion_report",
            extra_params={"page_size": page_size, "cursor": cursor, "start_date": start_date, "end_date": end_date},
        )

    # ── Validation ────────────────────────────────────────────────

    @mcp.tool()
    async def ams_get_validation_list(
        shop_code: str, page_size: int = 20, cursor: str = ""
    ) -> dict:
        """Lấy danh sách xác thực."""
        return await shopee_client.call(
            shop_code, "ams.get_validation_list",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def ams_get_validation_report(shop_code: str, validation_id: int) -> dict:
        """Lấy báo cáo xác thực chi tiết."""
        return await shopee_client.call(
            shop_code, "ams.get_validation_report",
            extra_params={"validation_id": validation_id},
        )

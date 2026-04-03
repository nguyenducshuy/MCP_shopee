from app.dependencies import shopee_client


def register_video_tools(mcp):
    # ── GET endpoints ────────────────────────────────────────────

    @mcp.tool()
    async def video_get_cover_list(shop_code: str, video_id_list: str) -> dict:
        """Lấy danh sách ảnh bìa video. video_id_list: chuỗi id cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code, "video.get_cover_list",
            extra_params={"video_id_list": video_id_list},
        )

    @mcp.tool()
    async def video_get_video_list(shop_code: str, page_size: int = 20, cursor: str = "") -> dict:
        """Lấy danh sách video của shop."""
        return await shopee_client.call(
            shop_code, "video.get_video_list",
            extra_params={"page_size": page_size, "cursor": cursor},
        )

    @mcp.tool()
    async def video_get_video_detail(shop_code: str, video_id: int) -> dict:
        """Lấy chi tiết một video."""
        return await shopee_client.call(
            shop_code, "video.get_video_detail",
            extra_params={"video_id": video_id},
        )

    @mcp.tool()
    async def video_get_overview_performance(shop_code: str, start_date: str, end_date: str) -> dict:
        """Lấy tổng quan hiệu suất video trong khoảng thời gian."""
        return await shopee_client.call(
            shop_code, "video.get_overview_performance",
            extra_params={"start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_metric_trend(shop_code: str, start_date: str, end_date: str, metric_type: str = "") -> dict:
        """Lấy xu hướng chỉ số video theo khoảng thời gian."""
        return await shopee_client.call(
            shop_code, "video.get_metric_trend",
            extra_params={"start_date": start_date, "end_date": end_date, "metric_type": metric_type},
        )

    @mcp.tool()
    async def video_get_user_demographics(shop_code: str, start_date: str, end_date: str) -> dict:
        """Lấy thông tin nhân khẩu học người xem video."""
        return await shopee_client.call(
            shop_code, "video.get_user_demographics",
            extra_params={"start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_video_performance_list(
        shop_code: str, page_size: int = 20, cursor: str = "", start_date: str = "", end_date: str = ""
    ) -> dict:
        """Lấy danh sách hiệu suất các video."""
        return await shopee_client.call(
            shop_code, "video.get_video_performance_list",
            extra_params={"page_size": page_size, "cursor": cursor, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_prodcut_performance_list(
        shop_code: str, page_size: int = 20, cursor: str = "", start_date: str = "", end_date: str = ""
    ) -> dict:
        """Lấy danh sách hiệu suất sản phẩm từ video."""
        return await shopee_client.call(
            shop_code, "video.get_prodcut_performance_list",
            extra_params={"page_size": page_size, "cursor": cursor, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_video_detail_performance(shop_code: str, video_id: int, start_date: str, end_date: str) -> dict:
        """Lấy hiệu suất chi tiết của một video."""
        return await shopee_client.call(
            shop_code, "video.get_video_detail_performance",
            extra_params={"video_id": video_id, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_video_detail_metric_trend(shop_code: str, video_id: int, start_date: str, end_date: str) -> dict:
        """Lấy xu hướng chỉ số chi tiết của một video."""
        return await shopee_client.call(
            shop_code, "video.get_video_detail_metric_trend",
            extra_params={"video_id": video_id, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_video_detail_audience_distribution(shop_code: str, video_id: int, start_date: str, end_date: str) -> dict:
        """Lấy phân bố khán giả chi tiết của một video."""
        return await shopee_client.call(
            shop_code, "video.get_video_detail_audience_distribution",
            extra_params={"video_id": video_id, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def video_get_video_detail_product_performance(shop_code: str, video_id: int, start_date: str, end_date: str) -> dict:
        """Lấy hiệu suất sản phẩm chi tiết của một video."""
        return await shopee_client.call(
            shop_code, "video.get_video_detail_product_performance",
            extra_params={"video_id": video_id, "start_date": start_date, "end_date": end_date},
        )

    # ── POST endpoints ───────────────────────────────────────────

    @mcp.tool()
    async def video_edit_video_info(shop_code: str, data: dict) -> dict:
        """Chỉnh sửa thông tin video (video_id, title, v.v.)."""
        return await shopee_client.call(shop_code, "video.edit_video_info", body=data)

    @mcp.tool()
    async def video_post_video(shop_code: str, data: dict) -> dict:
        """Đăng video mới lên shop."""
        return await shopee_client.call(shop_code, "video.post_video", body=data)

    @mcp.tool()
    async def video_delete_video(shop_code: str, video_id: int) -> dict:
        """Xóa một video khỏi shop."""
        return await shopee_client.call(shop_code, "video.delete_video", body={"video_id": video_id})

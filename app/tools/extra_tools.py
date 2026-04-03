"""Flash Sale tools — 11 endpoints từ module ShopFlashSale."""
from app.dependencies import shopee_client


def register_extra_tools(mcp):

    # ── Flash Sale ──────────────────────────────────────────────────────
    # Catalog chuẩn: docs/SHOP_FLASH_SALE_API.md | 11 endpoints
    # Flow: get_item_criteria → get_time_slot_id → create → add_items → update(status=1)
    # Sửa giá/stock đang enabled: update_items(status=0) → update_items(giá mới + status=1)
    # Session status: 0=deleted, 1=enabled, 2=disabled, 3=system_rejected
    # Item status: 0=disabled, 1=enabled, 2=deleted, 4=system_rejected, 5=manual_rejected

    @mcp.tool()
    async def get_time_slot_id(shop_code: str, start_time: int, end_time: int) -> dict:
        """Lấy danh sách slot giờ Flash Sale hợp lệ. Slot do Shopee định nghĩa sẵn, phải ở tương lai.
        - start_time: timestamp bắt đầu tìm (>= now, max=2145887999)
        - end_time: timestamp kết thúc tìm (> start_time)
        Trả về: [{timeslot_id, start_time, end_time}]. Gọi API này TRƯỚC khi tạo Flash Sale."""
        import time
        now = int(time.time())
        # Shopee yêu cầu start_time >= now — tự động clamp để tránh lỗi param_error
        if start_time < now:
            start_time = now + 60
        if end_time <= start_time:
            end_time = start_time + 7 * 86400
        result = await shopee_client.call(
            shop_code, "shop_flash_sale.get_time_slot_id",
            extra_params={"start_time": start_time, "end_time": end_time},
        )
        # Normalize: luôn trả về {"time_slot_list": [...], "total": N}
        if isinstance(result, list):
            return {"time_slot_list": result, "total": len(result)}
        if isinstance(result, dict):
            slots = result.get("time_slot_list") or result.get("time_slot") or []
            if not isinstance(slots, list):
                slots = []
            return {"time_slot_list": slots, "total": len(slots)}
        return {"time_slot_list": [], "total": 0}

    @mcp.tool()
    async def create_shop_flash_sale(shop_code: str, timeslot_id: int) -> dict:
        """Tạo phiên Flash Sale rỗng (chưa có SP). Sau bước này phải add_items.
        - timeslot_id: từ get_time_slot_id, slot phải ở tương lai.
        Phiên mới tạo có status=2 (disabled). Trả về: {flash_sale_id, status}."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.create_shop_flash_sale",
            body={"timeslot_id": timeslot_id},
        )

    @mcp.tool()
    async def get_item_criteria(shop_code: str) -> dict:
        """Lấy bộ tiêu chí để item đủ điều kiện vào Flash Sale. Không cần tham số.
        Trả về: criteria[] {criteria_id, min_product_rating (-1=không giới hạn), min_likes,
        must_not_pre_order, min_order_total, max_days_to_ship, min_repetition_day,
        min_promo_stock, max_promo_stock, min_discount, max_discount,
        min_discount_price (giá thực = giá trị/100000), max_discount_price, need_lowest_price},
        pair_ids[] {criteria_id → category_list (0=tất cả)}, overlap_block_category_ids[].
        Gọi API này TRƯỚC khi chọn SP, không nên hard-code tiêu chí."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.get_item_criteria",
        )

    @mcp.tool()
    async def add_shop_flash_sale_items(shop_code: str, flash_sale_id: int, items: list[dict]) -> dict:
        """Thêm sản phẩm vào Flash Sale. Phiên phải enabled hoặc upcoming. Max 50 item enabled/phiên.
        items[]:
          - item_id (int): ID sản phẩm
          - purchase_limit (int): giới hạn mua/khách, 0=không giới hạn
          SP CÓ biến thể → models[]:
            [{model_id (int), input_promo_price (float, giá không thuế), stock (int, min=1)}]
          SP KHÔNG biến thể:
            item_input_promo_price (float, giá không thuế), item_stock (int, min=1)
        VD có biến thể: {"item_id":123,"purchase_limit":5,"models":[{"model_id":456,"input_promo_price":69.3,"stock":100}]}
        VD không biến thể: {"item_id":789,"purchase_limit":3,"item_input_promo_price":15.99,"item_stock":200}
        Trả về failed_items kèm mã lỗi nếu SP không đạt criteria."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.add_shop_flash_sale_items",
            body={"flash_sale_id": flash_sale_id, "items": items},
        )

    @mcp.tool()
    async def get_shop_flash_sale_list(
        shop_code: str, type: int = 0, offset: int = 0, limit: int = 20,
        start_time: int | None = None, end_time: int | None = None,
    ) -> dict:
        """Lấy danh sách phiên Flash Sale của shop.
        - type: 0=all, 1=upcoming, 2=ongoing, 3=expired
        - offset: 0-1000, limit: 1-100
        - start_time/end_time: lọc thêm theo khoảng thời gian (tùy chọn)
        Trả về: total_count, flash_sale_list[] {flash_sale_id, timeslot_id, status,
        start_time, end_time, enabled_item_count, item_count, type, remindme_count, click_count}."""
        params: dict = {"type": type, "offset": offset, "limit": limit}
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        result = await shopee_client.call(
            shop_code, "shop_flash_sale.get_shop_flash_sale_list",
            extra_params=params,
        )
        # Normalize: luôn trả về {"flash_sale_list": [...], "total_count": N}
        if isinstance(result, list):
            return {"flash_sale_list": result, "total_count": len(result)}
        if isinstance(result, dict):
            fsl = result.get("flash_sale_list") or []
            tc = result.get("total_count", len(fsl))
            return {"flash_sale_list": fsl, "total_count": tc}
        return {"flash_sale_list": [], "total_count": 0}

    @mcp.tool()
    async def get_shop_flash_sale(shop_code: str, flash_sale_id: int) -> dict:
        """Đọc chi tiết 1 phiên Flash Sale. Trả về: flash_sale_id, status (0-3),
        type (1=upcoming, 2=ongoing, 3=expired), start_time, end_time, enabled_item_count, item_count.
        Dùng để kiểm tra trước khi update/delete/enable."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.get_shop_flash_sale",
            extra_params={"flash_sale_id": flash_sale_id},
        )

    @mcp.tool()
    async def get_shop_flash_sale_items(shop_code: str, flash_sale_id: int, offset: int = 0, limit: int = 50) -> dict:
        """Lấy danh sách item trong Flash Sale.
        Trả về: total_count, items[], models[].
        item_status: 0=disabled, 1=enabled, 2=deleted, 4=system_rejected, 5=manual_rejected.
        Dùng để audit, kiểm tra trước giờ chạy, xem reject_reason."""
        result = await shopee_client.call(
            shop_code, "shop_flash_sale.get_shop_flash_sale_items",
            extra_params={"flash_sale_id": flash_sale_id, "offset": offset, "limit": limit},
        )
        # Normalize: Shopee trả item_info hoặc items — thống nhất thành "items"
        if isinstance(result, dict):
            items = result.get("items") or result.get("item_info") or result.get("item") or []
            result["items"] = items
            # Xóa field trùng để tránh nhầm lẫn
            for key in ("item_info", "item"):
                result.pop(key, None)
        return result

    @mcp.tool()
    async def update_shop_flash_sale(shop_code: str, flash_sale_id: int, status: int) -> dict:
        """Bật/tắt phiên Flash Sale (công tắc tổng).
        - status: 1=enable, 2=disable
        Disable → tắt toàn bộ item bên trong. Không sửa phiên status=3 (system_rejected).
        Chỉ enable sau khi đã add items đầy đủ. Nếu có sự cố → disable cả phiên là chặn nhanh nhất."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.update_shop_flash_sale",
            body={"flash_sale_id": flash_sale_id, "status": status},
        )

    @mcp.tool()
    async def update_shop_flash_sale_items(shop_code: str, flash_sale_id: int, items: list[dict]) -> dict:
        """Sửa item/model trong Flash Sale. Phiên phải enabled hoặc upcoming.
        QUAN TRỌNG: không sửa trực tiếp giá/stock item đang enabled.
        Muốn đổi giá → gọi 2 lần: (1) status=0 disable, (2) giá mới + status=1 enable.
        items[]:
          - item_id (int), purchase_limit (int, không sửa nếu đang enabled)
          SP có biến thể → models[]:
            - model_id (int), status (0=disable, 1=enable)
            - input_promo_price (float): chỉ sửa khi status=0, hoặc gửi kèm status=1 để đổi giá và bật
            - stock (int): chỉ sửa khi status=0
          SP không biến thể:
            - item_status (0=disable, 1=enable)
            - item_input_promo_price: không sửa nếu item_status=1
        Trả về failed_items."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.update_shop_flash_sale_items",
            body={"flash_sale_id": flash_sale_id, "items": items},
        )

    @mcp.tool()
    async def delete_shop_flash_sale(shop_code: str, flash_sale_id: int) -> dict:
        """Xóa phiên Flash Sale. Chỉ xóa được phiên upcoming. KHÔNG xóa ongoing/expired. Sau xóa status=0."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.delete_shop_flash_sale",
            body={"flash_sale_id": flash_sale_id},
        )

    @mcp.tool()
    async def delete_shop_flash_sale_items(shop_code: str, flash_sale_id: int, item_ids: list[int]) -> dict:
        """Xóa item khỏi Flash Sale. Xóa item → xóa luôn toàn bộ model/variation.
        Phiên phải enabled hoặc upcoming. KHÔNG xóa từ phiên ongoing/expired."""
        return await shopee_client.call(
            shop_code, "shop_flash_sale.delete_shop_flash_sale_items",
            body={"flash_sale_id": flash_sale_id, "item_ids": item_ids},
        )

from app.dependencies import shopee_client


def register_marketing_tools(mcp):
    # Voucher
    @mcp.tool()
    async def get_voucher_list(
        shop_code: str,
        page_no: int = 1,
        page_size: int = 20,
        status: str = "all",
    ) -> dict:
        """Lấy danh sách voucher của shop. `status`: all, upcoming, ongoing, expired."""
        return await shopee_client.call(
            shop_code,
            "voucher.get_voucher_list",
            extra_params={"page_no": page_no, "page_size": page_size, "status": status},
        )

    @mcp.tool()
    async def get_voucher(shop_code: str, voucher_id: int) -> dict:
        """Lấy chi tiết một voucher theo `voucher_id`."""
        return await shopee_client.call(
            shop_code,
            "voucher.get_voucher",
            extra_params={"voucher_id": voucher_id},
        )

    @mcp.tool()
    async def add_voucher(shop_code: str, voucher_data: dict) -> dict:
        """Tạo voucher mới.

        Theo tài liệu Shopee, payload thường gồm `voucher_name`, `voucher_code`,
        `start_time`, `end_time`, `voucher_type`, `reward_type`, `usage_quantity`
        và các field reward tương ứng như `discount_amount`, `percentage`,
        `max_price`, `min_basket_price`, `item_id_list`.
        """
        return await shopee_client.call(shop_code, "voucher.add_voucher", body=voucher_data)

    @mcp.tool()
    async def update_voucher(shop_code: str, voucher_id: int, voucher_data: dict) -> dict:
        """Cập nhật voucher hiện có. Shopee chỉ cho sửa một số field tùy trạng thái voucher."""
        payload = dict(voucher_data)
        payload["voucher_id"] = voucher_id
        return await shopee_client.call(shop_code, "voucher.update_voucher", body=payload)

    @mcp.tool()
    async def delete_voucher(shop_code: str, voucher_id: int) -> dict:
        """Xóa voucher. Thường chỉ xóa được voucher upcoming và chưa phát sinh usage."""
        return await shopee_client.call(
            shop_code,
            "voucher.delete_voucher",
            body={"voucher_id": voucher_id},
        )

    @mcp.tool()
    async def end_voucher(shop_code: str, voucher_id: int) -> dict:
        """Kết thúc voucher sớm trước `end_time`."""
        return await shopee_client.call(
            shop_code,
            "voucher.end_voucher",
            body={"voucher_id": voucher_id},
        )

    # Discount
    @mcp.tool()
    async def get_discount_list(
        shop_code: str,
        page_no: int = 1,
        page_size: int = 100,
        status: str = "all",
    ) -> dict:
        """Lấy danh sách discount activity. `status`: all, upcoming, ongoing, expired."""
        return await shopee_client.call(
            shop_code,
            "discount.get_discount_list",
            extra_params={"discount_status": status, "page_no": page_no, "page_size": page_size},
        )

    @mcp.tool()
    async def get_discount(
        shop_code: str,
        discount_id: int,
        page_no: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Lấy chi tiết một discount và danh sách item phân trang bên trong discount đó."""
        return await shopee_client.call(
            shop_code,
            "discount.get_discount",
            extra_params={
                "discount_id": discount_id,
                "page_no": page_no,
                "page_size": page_size,
            },
        )

    @mcp.tool()
    async def add_discount(shop_code: str, discount_data: dict) -> dict:
        """Tạo discount activity mới.

        Theo docs, discount được tạo trước rồi mới thêm item bằng `add_discount_item`.
        Payload thường có `discount_name`, `start_time`, `end_time`.
        """
        return await shopee_client.call(shop_code, "discount.add_discount", body=discount_data)

    @mcp.tool()
    async def update_discount(shop_code: str, discount_id: int, discount_data: dict) -> dict:
        """Cập nhật discount activity. Quyền sửa field phụ thuộc trạng thái upcoming/ongoing/expired."""
        payload = dict(discount_data)
        payload["discount_id"] = discount_id
        return await shopee_client.call(shop_code, "discount.update_discount", body=payload)

    @mcp.tool()
    async def delete_discount(shop_code: str, discount_id: int) -> dict:
        """Xóa discount activity. Theo docs, thường chỉ xóa được discount upcoming."""
        return await shopee_client.call(
            shop_code,
            "discount.delete_discount",
            body={"discount_id": discount_id},
        )

    @mcp.tool()
    async def end_discount(shop_code: str, discount_id: int) -> dict:
        """Kết thúc sớm discount đang ongoing."""
        return await shopee_client.call(
            shop_code,
            "discount.end_discount",
            body={"discount_id": discount_id},
        )

    @mcp.tool()
    async def add_discount_item(
        shop_code: str,
        discount_id: int,
        item_list: list[dict],
    ) -> dict:
        """Thêm item/model vào discount.

        Mỗi phần tử trong `item_list` thường chứa `item_id`, `purchase_limit` và
        một trong hai:
        - `item_promotion_price` cho item không có variation
        - `model_list` cho item có variation
        """
        return await shopee_client.call(
            shop_code,
            "discount.add_discount_item",
            body={"discount_id": discount_id, "item_list": item_list},
        )

    @mcp.tool()
    async def update_discount_item(
        shop_code: str,
        discount_id: int,
        item_list: list[dict],
    ) -> dict:
        """Cập nhật giá khuyến mãi hoặc purchase limit của item/model trong discount."""
        return await shopee_client.call(
            shop_code,
            "discount.update_discount_item",
            body={"discount_id": discount_id, "item_list": item_list},
        )

    @mcp.tool()
    async def delete_discount_item(
        shop_code: str,
        discount_id: int,
        item_id: int,
        model_id: int = 0,
    ) -> dict:
        """Gỡ một item/model khỏi discount.

        Với item không có variation, truyền `model_id=0`.
        """
        return await shopee_client.call(
            shop_code,
            "discount.delete_discount_item",
            body={"discount_id": discount_id, "item_id": item_id, "model_id": model_id},
        )

    @mcp.tool()
    async def get_sip_discounts(shop_code: str, region: str = "") -> dict:
        """Lấy SIP discounts. Bỏ trống `region` để lấy tất cả region đang có upcoming/ongoing."""
        params = {"region": region} if region else {}
        return await shopee_client.call(
            shop_code,
            "discount.get_sip_discounts",
            extra_params=params,
        )

    @mcp.tool()
    async def set_sip_discount(shop_code: str, region: str, sip_discount_rate: int) -> dict:
        """Tạo hoặc cập nhật SIP discount cho một region.

        Theo docs:
        - dùng Primary shop để gọi
        - VN thường không vượt quá 50%
        - không thể sửa liên tiếp trong vòng 15 phút
        """
        return await shopee_client.call(
            shop_code,
            "discount.set_sip_discount",
            body={"region": region, "sip_discount_rate": sip_discount_rate},
        )

    @mcp.tool()
    async def delete_sip_discount(shop_code: str, region: str) -> dict:
        """Xóa SIP discount khỏi một region affiliate shop."""
        return await shopee_client.call(
            shop_code,
            "discount.delete_sip_discount",
            body={"region": region},
        )

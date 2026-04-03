from app.dependencies import shopee_client


def register_order_tools(mcp):
    @mcp.tool()
    async def get_order_list(
        shop_code: str, time_from: int, time_to: int, page_size: int = 50
    ) -> dict:
        """Lấy danh sách đơn hàng theo khoảng thời gian (unix timestamp)."""
        return await shopee_client.call(
            shop_code,
            "order.get_order_list",
            extra_params={
                "time_range_field": "create_time",
                "time_from": time_from,
                "time_to": time_to,
                "page_size": page_size,
            },
        )

    @mcp.tool()
    async def get_order_detail(shop_code: str, order_sn_list: str) -> dict:
        """Lấy chi tiết đơn hàng. order_sn_list: danh sách order_sn cách nhau bởi dấu phẩy (VD: 'SN001,SN002')."""
        return await shopee_client.call(
            shop_code,
            "order.get_order_detail",
            extra_params={
                "order_sn_list": order_sn_list,
                "response_optional_fields": "item_list,buyer_user_id,shipping_carrier",
            },
        )

    @mcp.tool()
    async def get_shipment_list(shop_code: str, cursor: str = "", page_size: int = 50) -> dict:
        """Lấy danh sách lô hàng (shipment) cần xử lý."""
        params = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        return await shopee_client.call(
            shop_code, "order.get_shipment_list", extra_params=params
        )

    @mcp.tool()
    async def cancel_order(shop_code: str, order_sn: str, cancel_reason: str = "OUT_OF_STOCK") -> dict:
        """Hủy đơn hàng. cancel_reason: OUT_OF_STOCK, CUSTOMER_REQUEST, UNDELIVERABLE_AREA, COD_NOT_SUPPORTED, ..."""
        return await shopee_client.call(
            shop_code,
            "order.cancel_order",
            body={"order_sn": order_sn, "cancel_reason": cancel_reason},
        )

    @mcp.tool()
    async def handle_buyer_cancellation(shop_code: str, order_sn: str, accept: bool = True) -> dict:
        """Xử lý yêu cầu hủy đơn từ người mua. accept=True: chấp nhận, False: từ chối."""
        operation = "ACCEPT" if accept else "REJECT"
        return await shopee_client.call(
            shop_code,
            "order.handle_buyer_cancellation",
            body={"order_sn": order_sn, "operation": operation},
        )

    @mcp.tool()
    async def search_package_list(
        shop_code: str, order_sn: str = "", package_number: str = "", page_size: int = 50, cursor: str = ""
    ) -> dict:
        """Tìm kiếm danh sách kiện hàng theo order_sn hoặc package_number."""
        params: dict = {"page_size": page_size}
        if order_sn:
            params["order_sn"] = order_sn
        if package_number:
            params["package_number"] = package_number
        if cursor:
            params["cursor"] = cursor
        return await shopee_client.call(
            shop_code, "order.search_package_list", extra_params=params
        )

    @mcp.tool()
    async def get_package_detail(shop_code: str, package_number_list: str) -> dict:
        """Lấy chi tiết kiện hàng. package_number_list: danh sách package_number cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "order.get_package_detail",
            extra_params={"package_number_list": package_number_list},
        )

    @mcp.tool()
    async def split_order(shop_code: str, order_sn: str, package_list: list) -> dict:
        """Tách đơn hàng thành nhiều kiện. package_list: danh sách dict mô tả từng kiện."""
        return await shopee_client.call(
            shop_code,
            "order.split_order",
            body={"order_sn": order_sn, "package_list": package_list},
        )

    @mcp.tool()
    async def unsplit_order(shop_code: str, order_sn: str) -> dict:
        """Hủy tách đơn hàng, gộp lại thành một kiện duy nhất."""
        return await shopee_client.call(
            shop_code,
            "order.unsplit_order",
            body={"order_sn": order_sn},
        )

    @mcp.tool()
    async def set_note(shop_code: str, order_sn: str, note: str) -> dict:
        """Đặt ghi chú cho đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "order.set_note",
            body={"order_sn": order_sn, "note": note},
        )

    @mcp.tool()
    async def get_pending_buyer_invoice_order_list(
        shop_code: str, page_size: int = 50, cursor: str = ""
    ) -> dict:
        """Lấy danh sách đơn hàng đang chờ hóa đơn từ người mua."""
        params: dict = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        return await shopee_client.call(
            shop_code, "order.get_pending_buyer_invoice_order_list", extra_params=params
        )

    @mcp.tool()
    async def get_buyer_invoice_info(shop_code: str, order_sn: str) -> dict:
        """Lấy thông tin hóa đơn người mua của đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "order.get_buyer_invoice_info",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def upload_invoice_doc(shop_code: str, data: dict) -> dict:
        """Tải lên tài liệu hóa đơn cho đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "order.upload_invoice_doc",
            body=data,
        )

    @mcp.tool()
    async def download_invoice_doc(shop_code: str, order_sn: str) -> dict:
        """Tải xuống tài liệu hóa đơn của đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "order.download_invoice_doc",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def handle_prescription_check(shop_code: str, data: dict) -> dict:
        """Xử lý kiểm tra đơn thuốc cho đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "order.handle_prescription_check",
            body=data,
        )

    @mcp.tool()
    async def get_warehouse_filter_config(shop_code: str) -> dict:
        """Lấy cấu hình bộ lọc kho hàng."""
        return await shopee_client.call(
            shop_code, "order.get_warehouse_filter_config"
        )

    @mcp.tool()
    async def get_booking_list(shop_code: str, page_size: int = 50, cursor: str = "") -> dict:
        """Lấy danh sách đặt lịch giao hàng."""
        params: dict = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        return await shopee_client.call(
            shop_code, "order.get_booking_list", extra_params=params
        )

    @mcp.tool()
    async def get_booking_detail(shop_code: str, booking_sn: str) -> dict:
        """Lấy chi tiết đặt lịch giao hàng."""
        return await shopee_client.call(
            shop_code,
            "order.get_booking_detail",
            extra_params={"booking_sn": booking_sn},
        )

    @mcp.tool()
    async def generate_fbs_invoices(shop_code: str, data: dict) -> dict:
        """Tạo hóa đơn FBS (Fulfilled by Shopee)."""
        return await shopee_client.call(
            shop_code,
            "order.generate_fbs_invoices",
            body=data,
        )

    @mcp.tool()
    async def get_fbs_invoices_result(shop_code: str, task_id: str) -> dict:
        """Lấy kết quả tạo hóa đơn FBS theo task_id."""
        return await shopee_client.call(
            shop_code,
            "order.get_fbs_invoices_result",
            extra_params={"task_id": task_id},
        )

    @mcp.tool()
    async def download_fbs_invoices(shop_code: str, task_id: str) -> dict:
        """Tải xuống hóa đơn FBS theo task_id."""
        return await shopee_client.call(
            shop_code,
            "order.download_fbs_invoices",
            extra_params={"task_id": task_id},
        )

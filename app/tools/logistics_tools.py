from app.dependencies import shopee_client


def register_logistics_tools(mcp):
    @mcp.tool()
    async def ship_order(
        shop_code: str, order_sn: str, shipping_type: str = "dropoff", package_number: str = ""
    ) -> dict:
        """Xác nhận giao hàng cho đơn hàng.
        shipping_type: 'pickup' (lấy tại nhà), 'dropoff' (gửi tại bưu cục), 'non_integrated' (tự vận chuyển).
        Gọi get_shipping_parameter trước để biết shipping_type nào khả dụng."""
        body: dict = {"order_sn": order_sn}
        if shipping_type == "pickup":
            body["pickup"] = {}
        elif shipping_type == "dropoff":
            body["dropoff"] = {}
        else:
            body["non_integrated"] = {}
        if package_number:
            body["package_number"] = package_number
        return await shopee_client.call(shop_code, "logistics.ship_order", body=body)

    @mcp.tool()
    async def get_shipping_parameter(shop_code: str, order_sn: str) -> dict:
        """Lấy thông số vận chuyển cần thiết trước khi ship (địa chỉ, kênh vận chuyển, ...)."""
        return await shopee_client.call(
            shop_code, "logistics.get_shipping_parameter",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def get_tracking_number(shop_code: str, order_sn: str) -> dict:
        """Lấy mã vận đơn (tracking number) của đơn hàng."""
        return await shopee_client.call(
            shop_code, "logistics.get_tracking_number",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def get_channel_list(shop_code: str) -> dict:
        """Lấy danh sách kênh vận chuyển khả dụng của shop."""
        return await shopee_client.call(shop_code, "logistics.get_channel_list")

    # --- GET tools ---

    @mcp.tool()
    async def get_mass_shipping_parameter(shop_code: str, order_sn_list: str) -> dict:
        """Lấy thông số vận chuyển hàng loạt. order_sn_list: danh sách order_sn cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_mass_shipping_parameter",
            extra_params={"order_sn_list": order_sn_list},
        )

    @mcp.tool()
    async def get_mass_tracking_number(shop_code: str, order_sn_list: str) -> dict:
        """Lấy mã vận đơn hàng loạt. order_sn_list: danh sách order_sn cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_mass_tracking_number",
            extra_params={"order_sn_list": order_sn_list},
        )

    @mcp.tool()
    async def get_shipping_document_parameter(shop_code: str, order_list: str) -> dict:
        """Lấy thông số tài liệu vận chuyển. order_list: danh sách order cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_shipping_document_parameter",
            extra_params={"order_list": order_list},
        )

    @mcp.tool()
    async def get_shipping_document_result(shop_code: str, order_list: str) -> dict:
        """Lấy kết quả tạo tài liệu vận chuyển. order_list: danh sách order cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_shipping_document_result",
            extra_params={"order_list": order_list},
        )

    @mcp.tool()
    async def download_shipping_document(shop_code: str, order_list: str) -> dict:
        """Tải xuống tài liệu vận chuyển. order_list: danh sách order cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.download_shipping_document",
            extra_params={"order_list": order_list},
        )

    @mcp.tool()
    async def get_shipping_document_data_info(shop_code: str, order_list: str) -> dict:
        """Lấy thông tin dữ liệu tài liệu vận chuyển. order_list: danh sách order cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_shipping_document_data_info",
            extra_params={"order_list": order_list},
        )

    @mcp.tool()
    async def get_tracking_info(shop_code: str, order_sn: str) -> dict:
        """Lấy thông tin theo dõi vận chuyển chi tiết của đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_tracking_info",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def get_address_list(shop_code: str) -> dict:
        """Lấy danh sách địa chỉ của shop."""
        return await shopee_client.call(shop_code, "logistics.get_address_list")

    @mcp.tool()
    async def get_operating_hours(shop_code: str) -> dict:
        """Lấy giờ hoạt động của shop."""
        return await shopee_client.call(shop_code, "logistics.get_operating_hours")

    @mcp.tool()
    async def get_operating_hour_restrictions(shop_code: str) -> dict:
        """Lấy các hạn chế về giờ hoạt động."""
        return await shopee_client.call(shop_code, "logistics.get_operating_hour_restrictions")

    @mcp.tool()
    async def get_booking_shipping_parameter(shop_code: str, booking_sn: str) -> dict:
        """Lấy thông số vận chuyển cho đặt lịch giao hàng."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_booking_shipping_parameter",
            extra_params={"booking_sn": booking_sn},
        )

    @mcp.tool()
    async def get_booking_tracking_number(shop_code: str, booking_sn: str) -> dict:
        """Lấy mã vận đơn của đặt lịch giao hàng."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_booking_tracking_number",
            extra_params={"booking_sn": booking_sn},
        )

    @mcp.tool()
    async def get_booking_shipping_document_parameter(shop_code: str, booking_sn_list: str) -> dict:
        """Lấy thông số tài liệu vận chuyển cho đặt lịch. booking_sn_list: cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_booking_shipping_document_parameter",
            extra_params={"booking_sn_list": booking_sn_list},
        )

    @mcp.tool()
    async def get_booking_shipping_document_result(shop_code: str, booking_sn_list: str) -> dict:
        """Lấy kết quả tạo tài liệu vận chuyển cho đặt lịch. booking_sn_list: cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_booking_shipping_document_result",
            extra_params={"booking_sn_list": booking_sn_list},
        )

    @mcp.tool()
    async def download_booking_shipping_document(shop_code: str, booking_sn_list: str) -> dict:
        """Tải xuống tài liệu vận chuyển cho đặt lịch. booking_sn_list: cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.download_booking_shipping_document",
            extra_params={"booking_sn_list": booking_sn_list},
        )

    @mcp.tool()
    async def get_booking_shipping_document_data_info(shop_code: str, booking_sn_list: str) -> dict:
        """Lấy thông tin dữ liệu tài liệu vận chuyển cho đặt lịch. booking_sn_list: cách nhau bởi dấu phẩy."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_booking_shipping_document_data_info",
            extra_params={"booking_sn_list": booking_sn_list},
        )

    @mcp.tool()
    async def get_booking_tracking_info(shop_code: str, booking_sn: str) -> dict:
        """Lấy thông tin theo dõi vận chuyển cho đặt lịch giao hàng."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_booking_tracking_info",
            extra_params={"booking_sn": booking_sn},
        )

    @mcp.tool()
    async def download_to_label(shop_code: str, order_sn: str) -> dict:
        """Tải xuống nhãn vận chuyển TO (Transfer Order) của đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "logistics.download_to_label",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def get_shipping_document_job_status(shop_code: str, job_id: str) -> dict:
        """Lấy trạng thái công việc tạo tài liệu vận chuyển."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_shipping_document_job_status",
            extra_params={"job_id": job_id},
        )

    @mcp.tool()
    async def download_shipping_document_job(shop_code: str, job_id: str) -> dict:
        """Tải xuống tài liệu vận chuyển theo job_id."""
        return await shopee_client.call(
            shop_code,
            "logistics.download_shipping_document_job",
            extra_params={"job_id": job_id},
        )

    @mcp.tool()
    async def get_mart_packaging_info(shop_code: str, order_sn: str) -> dict:
        """Lấy thông tin đóng gói Mart cho đơn hàng."""
        return await shopee_client.call(
            shop_code,
            "logistics.get_mart_packaging_info",
            extra_params={"order_sn": order_sn},
        )

    @mcp.tool()
    async def check_polygon_update_status(shop_code: str, task_id: str) -> dict:
        """Kiểm tra trạng thái cập nhật vùng phục vụ (polygon)."""
        return await shopee_client.call(
            shop_code,
            "logistics.check_polygon_update_status",
            extra_params={"task_id": task_id},
        )

    # --- POST tools ---

    @mcp.tool()
    async def mass_ship_order(shop_code: str, data: dict) -> dict:
        """Xác nhận giao hàng hàng loạt. data chứa order_list."""
        return await shopee_client.call(
            shop_code, "logistics.mass_ship_order", body=data
        )

    @mcp.tool()
    async def update_shipping_order(shop_code: str, order_sn: str, data: dict) -> dict:
        """Cập nhật thông tin vận chuyển cho đơn hàng."""
        body = {"order_sn": order_sn, **data}
        return await shopee_client.call(
            shop_code, "logistics.update_shipping_order", body=body
        )

    @mcp.tool()
    async def create_shipping_document(shop_code: str, data: dict) -> dict:
        """Tạo tài liệu vận chuyển. data chứa order_list."""
        return await shopee_client.call(
            shop_code, "logistics.create_shipping_document", body=data
        )

    @mcp.tool()
    async def set_address_config(shop_code: str, data: dict) -> dict:
        """Thiết lập cấu hình địa chỉ cho shop."""
        return await shopee_client.call(
            shop_code, "logistics.set_address_config", body=data
        )

    @mcp.tool()
    async def update_address(shop_code: str, data: dict) -> dict:
        """Cập nhật địa chỉ của shop."""
        return await shopee_client.call(
            shop_code, "logistics.update_address", body=data
        )

    @mcp.tool()
    async def delete_address(shop_code: str, address_id: int) -> dict:
        """Xóa địa chỉ của shop theo address_id."""
        return await shopee_client.call(
            shop_code, "logistics.delete_address", body={"address_id": address_id}
        )

    @mcp.tool()
    async def update_channel(shop_code: str, data: dict) -> dict:
        """Cập nhật cấu hình kênh vận chuyển."""
        return await shopee_client.call(
            shop_code, "logistics.update_channel", body=data
        )

    @mcp.tool()
    async def update_operating_hours(shop_code: str, data: dict) -> dict:
        """Cập nhật giờ hoạt động của shop."""
        return await shopee_client.call(
            shop_code, "logistics.update_operating_hours", body=data
        )

    @mcp.tool()
    async def delete_special_operating_hour(shop_code: str, data: dict) -> dict:
        """Xóa giờ hoạt động đặc biệt."""
        return await shopee_client.call(
            shop_code, "logistics.delete_special_operating_hour", body=data
        )

    @mcp.tool()
    async def batch_update_tpf_warehouse_tracking_status(shop_code: str, data: dict) -> dict:
        """Cập nhật hàng loạt trạng thái theo dõi kho TPF (Third-Party Fulfillment)."""
        return await shopee_client.call(
            shop_code, "logistics.batch_update_tpf_warehouse_tracking_status", body=data
        )

    @mcp.tool()
    async def batch_ship_order(shop_code: str, data: dict) -> dict:
        """Xác nhận giao hàng theo lô."""
        return await shopee_client.call(
            shop_code, "logistics.batch_ship_order", body=data
        )

    @mcp.tool()
    async def update_tracking_status(shop_code: str, data: dict) -> dict:
        """Cập nhật trạng thái theo dõi vận chuyển."""
        return await shopee_client.call(
            shop_code, "logistics.update_tracking_status", body=data
        )

    @mcp.tool()
    async def ship_booking(shop_code: str, data: dict) -> dict:
        """Xác nhận giao hàng cho đặt lịch."""
        return await shopee_client.call(
            shop_code, "logistics.ship_booking", body=data
        )

    @mcp.tool()
    async def create_booking_shipping_document(shop_code: str, data: dict) -> dict:
        """Tạo tài liệu vận chuyển cho đặt lịch giao hàng."""
        return await shopee_client.call(
            shop_code, "logistics.create_booking_shipping_document", body=data
        )

    @mcp.tool()
    async def create_shipping_document_job(shop_code: str, data: dict) -> dict:
        """Tạo công việc tạo tài liệu vận chuyển (xử lý bất đồng bộ)."""
        return await shopee_client.call(
            shop_code, "logistics.create_shipping_document_job", body=data
        )

    @mcp.tool()
    async def update_self_collection_order_logistics(shop_code: str, data: dict) -> dict:
        """Cập nhật thông tin logistics cho đơn hàng tự nhận."""
        return await shopee_client.call(
            shop_code, "logistics.update_self_collection_order_logistics", body=data
        )

    @mcp.tool()
    async def set_mart_packaging_info(shop_code: str, data: dict) -> dict:
        """Thiết lập thông tin đóng gói Mart cho đơn hàng."""
        return await shopee_client.call(
            shop_code, "logistics.set_mart_packaging_info", body=data
        )

    @mcp.tool()
    async def upload_serviceable_polygon(shop_code: str, data: dict) -> dict:
        """Tải lên vùng phục vụ (polygon) cho khu vực giao hàng."""
        return await shopee_client.call(
            shop_code, "logistics.upload_serviceable_polygon", body=data
        )

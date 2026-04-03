"""Ads tools — Quản lý quảng cáo Shopee (CPC, GMS, Product Ads)."""
from app.dependencies import shopee_client


def register_ads_tools(mcp):

    # ── Tổng quan & Cài đặt ──────────────────────────────────────────

    @mcp.tool()
    async def ads_get_total_balance(shop_code: str) -> dict:
        """Lấy số dư quảng cáo tổng của shop."""
        return await shopee_client.call(shop_code, "ads.get_total_balance")

    @mcp.tool()
    async def ads_get_shop_toggle_info(shop_code: str) -> dict:
        """Lấy thông tin bật/tắt quảng cáo của shop."""
        return await shopee_client.call(shop_code, "ads.get_shop_toggle_info")

    # ── Gợi ý từ khóa & sản phẩm ────────────────────────────────────

    @mcp.tool()
    async def ads_get_recommended_keyword_list(shop_code: str, item_id: int, page_size: int = 20) -> dict:
        """Lấy danh sách từ khóa gợi ý cho sản phẩm quảng cáo."""
        return await shopee_client.call(
            shop_code, "ads.get_recommended_keyword_list",
            extra_params={"item_id": item_id, "page_size": page_size},
        )

    @mcp.tool()
    async def ads_get_recommended_item_list(shop_code: str, page_size: int = 20) -> dict:
        """Lấy danh sách sản phẩm gợi ý để chạy quảng cáo."""
        return await shopee_client.call(
            shop_code, "ads.get_recommended_item_list",
            extra_params={"page_size": page_size},
        )

    # ── Hiệu suất CPC ───────────────────────────────────────────────

    @mcp.tool()
    async def ads_get_all_cpc_ads_hourly_performance(shop_code: str, performance_date: str) -> dict:
        """Lấy hiệu suất quảng cáo CPC theo giờ. performance_date: DD-MM-YYYY."""
        return await shopee_client.call(
            shop_code, "ads.get_all_cpc_ads_hourly_performance",
            extra_params={"performance_date": performance_date},
        )

    @mcp.tool()
    async def ads_get_all_cpc_ads_daily_performance(shop_code: str, start_date: str, end_date: str) -> dict:
        """Lấy hiệu suất quảng cáo CPC theo ngày. start_date, end_date: DD-MM-YYYY."""
        return await shopee_client.call(
            shop_code, "ads.get_all_cpc_ads_daily_performance",
            extra_params={"start_date": start_date, "end_date": end_date},
        )

    # ── Hiệu suất chiến dịch sản phẩm ───────────────────────────────

    @mcp.tool()
    async def ads_get_product_campaign_daily_performance(
        shop_code: str, campaign_id_list: str, start_date: str, end_date: str
    ) -> dict:
        """Lấy hiệu suất chiến dịch sản phẩm theo ngày. campaign_id_list: danh sách ID cách nhau bởi dấu phẩy. Dates: DD-MM-YYYY."""
        return await shopee_client.call(
            shop_code, "ads.get_product_campaign_daily_performance",
            extra_params={"campaign_id_list": campaign_id_list, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ads_get_product_campaign_hourly_performance(
        shop_code: str, campaign_id_list: str, performance_date: str
    ) -> dict:
        """Lấy hiệu suất chiến dịch sản phẩm theo giờ. campaign_id_list: danh sách ID cách nhau bởi dấu phẩy. performance_date: DD-MM-YYYY."""
        return await shopee_client.call(
            shop_code, "ads.get_product_campaign_hourly_performance",
            extra_params={"campaign_id_list": campaign_id_list, "performance_date": performance_date},
        )

    @mcp.tool()
    async def ads_get_product_level_campaign_id_list(shop_code: str, page_size: int = 50, offset: int = 0) -> dict:
        """Lấy danh sách campaign_id quảng cáo sản phẩm."""
        return await shopee_client.call(
            shop_code, "ads.get_product_level_campaign_id_list",
            extra_params={"page_size": page_size, "offset": offset},
        )

    @mcp.tool()
    async def ads_get_product_level_campaign_setting_info(
        shop_code: str, campaign_id_list: str, info_type_list: str = "1,2,3"
    ) -> dict:
        """Lấy thông tin cài đặt chiến dịch quảng cáo sản phẩm.
        campaign_id_list: danh sách campaign ID cách nhau bởi dấu phẩy.
        info_type_list: 1=campaign_info, 2=targeting_info, 3=keyword_info, 4=enhanced_cpc_info. VD: '1,2,3'."""
        return await shopee_client.call(
            shop_code, "ads.get_product_level_campaign_setting_info",
            extra_params={"campaign_id_list": campaign_id_list, "info_type_list": info_type_list},
        )

    # ── Tạo & Sửa quảng cáo sản phẩm ────────────────────────────────

    @mcp.tool()
    async def ads_create_manual_product_ads(shop_code: str, ads_data: dict) -> dict:
        """Tạo quảng cáo sản phẩm thủ công. ads_data chứa: item_id, daily_budget, keywords, bid_price, ..."""
        return await shopee_client.call(shop_code, "ads.create_manual_product_ads", body=ads_data)

    @mcp.tool()
    async def ads_edit_manual_product_ad_keywords(shop_code: str, campaign_id: int, keywords_data: dict) -> dict:
        """Sửa từ khóa quảng cáo sản phẩm thủ công."""
        keywords_data["campaign_id"] = campaign_id
        return await shopee_client.call(shop_code, "ads.edit_manual_product_ad_keywords", body=keywords_data)

    @mcp.tool()
    async def ads_edit_manual_product_ads(shop_code: str, campaign_id: int, ads_data: dict) -> dict:
        """Sửa quảng cáo sản phẩm thủ công (budget, status, ...)."""
        ads_data["campaign_id"] = campaign_id
        return await shopee_client.call(shop_code, "ads.edit_manual_product_ads", body=ads_data)

    # ── Gợi ý ngân sách & ROI ────────────────────────────────────────

    @mcp.tool()
    async def ads_get_create_product_ad_budget_suggestion(
        shop_code: str, item_id: int, bidding_method: str = "manual",
        campaign_placement: str = "search", product_selection: str = "manual",
        reference_id: int = 0
    ) -> dict:
        """Lấy gợi ý ngân sách khi tạo quảng cáo sản phẩm.
        bidding_method: 'manual' hoặc 'auto'.
        campaign_placement: 'search', 'recommendation', hoặc 'all'.
        product_selection: 'manual' hoặc 'auto'.
        reference_id: campaign_id nếu đã có chiến dịch, 0 nếu tạo mới."""
        return await shopee_client.call(
            shop_code, "ads.get_create_product_ad_budget_suggestion",
            extra_params={
                "item_id": item_id, "bidding_method": bidding_method,
                "campaign_placement": campaign_placement, "product_selection": product_selection,
                "reference_id": reference_id,
            },
        )

    @mcp.tool()
    async def ads_get_product_recommended_roi_target(shop_code: str, item_id: int, reference_id: int = 0) -> dict:
        """Lấy mục tiêu ROI gợi ý cho sản phẩm quảng cáo. reference_id: campaign_id nếu đã có chiến dịch, 0 nếu tạo mới."""
        return await shopee_client.call(
            shop_code, "ads.get_product_recommended_roi_target",
            extra_params={"item_id": item_id, "reference_id": reference_id},
        )

    @mcp.tool()
    async def ads_get_ads_facil_shop_rate(shop_code: str) -> dict:
        """Lấy tỷ lệ Ads Fácil của shop (Brazil market)."""
        return await shopee_client.call(shop_code, "ads.get_ads_facil_shop_rate")

    # ── GMS (Gross Merchandise Sales) Campaigns ──────────────────────

    @mcp.tool()
    async def ads_check_create_gms_product_campaign_eligibility(shop_code: str, item_id: int) -> dict:
        """Kiểm tra sản phẩm có đủ điều kiện tạo chiến dịch GMS không."""
        return await shopee_client.call(
            shop_code, "ads.check_create_gms_product_campaign_eligibility",
            extra_params={"item_id": item_id},
        )

    @mcp.tool()
    async def ads_create_gms_product_campaign(shop_code: str, campaign_data: dict) -> dict:
        """Tạo chiến dịch quảng cáo GMS cho sản phẩm."""
        return await shopee_client.call(shop_code, "ads.create_gms_product_campaign", body=campaign_data)

    @mcp.tool()
    async def ads_edit_gms_product_campaign(shop_code: str, campaign_id: int, campaign_data: dict) -> dict:
        """Sửa chiến dịch quảng cáo GMS."""
        campaign_data["campaign_id"] = campaign_id
        return await shopee_client.call(shop_code, "ads.edit_gms_product_campaign", body=campaign_data)

    @mcp.tool()
    async def ads_list_gms_user_deleted_item(shop_code: str, page_size: int = 50, offset: int = 0) -> dict:
        """Lấy danh sách sản phẩm đã xóa khỏi GMS."""
        return await shopee_client.call(
            shop_code, "ads.list_gms_user_deleted_item",
            extra_params={"page_size": page_size, "offset": offset},
        )

    @mcp.tool()
    async def ads_edit_gms_item_product_campaign(shop_code: str, campaign_id: int, item_data: dict) -> dict:
        """Sửa sản phẩm trong chiến dịch GMS."""
        item_data["campaign_id"] = campaign_id
        return await shopee_client.call(shop_code, "ads.edit_gms_item_product_campaign", body=item_data)

    @mcp.tool()
    async def ads_get_gms_campaign_performance(
        shop_code: str, campaign_id: int, start_date: str, end_date: str
    ) -> dict:
        """Lấy hiệu suất chiến dịch GMS."""
        return await shopee_client.call(
            shop_code, "ads.get_gms_campaign_performance",
            extra_params={"campaign_id": campaign_id, "start_date": start_date, "end_date": end_date},
        )

    @mcp.tool()
    async def ads_get_gms_item_performance(
        shop_code: str, campaign_id: int, start_date: str, end_date: str
    ) -> dict:
        """Lấy hiệu suất từng sản phẩm trong chiến dịch GMS."""
        return await shopee_client.call(
            shop_code, "ads.get_gms_item_performance",
            extra_params={"campaign_id": campaign_id, "start_date": start_date, "end_date": end_date},
        )

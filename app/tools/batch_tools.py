"""Batch tools — lấy data & cập nhật hàng loạt across multiple shops."""
import asyncio

from app.dependencies import shopee_client, shop_registry_service, token_service
from app.core.logger import get_logger
from app.core.utils import resolve_shops

logger = get_logger(__name__)


async def _fetch_all_order_pages(
    shop_code: str,
    *,
    time_range_field: str,
    time_from: int,
    time_to: int,
    page_size: int,
    order_status: str = "ALL",
) -> list[dict]:
    """Fetch all pages for order.get_order_list to avoid silent undercounting."""
    all_orders: list[dict] = []
    cursor = ""

    for _ in range(100):
        params = {
            "time_range_field": time_range_field,
            "time_from": time_from,
            "time_to": time_to,
            "page_size": page_size,
            "order_status": order_status,
        }
        if cursor:
            params["cursor"] = cursor

        resp = await shopee_client.call(
            shop_code,
            "order.get_order_list",
            extra_params=params,
        )
        page_orders = resp.get("order_list", [])
        all_orders.extend(page_orders)

        next_cursor = resp.get("next_cursor", "")
        has_more = bool(resp.get("more")) or bool(resp.get("has_next_page"))
        if not next_cursor and not has_more:
            break
        if not next_cursor:
            break
        cursor = next_cursor

    return all_orders


def register_batch_tools(mcp):

    # ── OVERVIEW: 1 call lấy tổng quan toàn bộ ────────────────────────

    @mcp.tool()
    async def get_all_shops_overview() -> dict:
        """Lấy tổng quan TẤT CẢ shop: danh sách shop, trạng thái token, số sản phẩm.
        Dùng tool này ĐẦU TIÊN để nắm toàn cảnh trước khi thao tác."""
        shops = shop_registry_service.list_shops()
        results = []

        async def fetch_shop(shop):
            shop_code = shop.get("code", "")
            entry = {
                "shop_code": shop_code,
                "shop_id": shop.get("shop_id"),
                "shop_name": shop.get("shop_name", ""),
                "environment": shop.get("environment", ""),
                "token_status": "unknown",
                "item_count": 0,
                "items": [],
            }
            # Token status
            try:
                status = token_service.get_token_status(shop_code)
                entry["token_status"] = status.get("status", "unknown")
                entry["token_expires_in"] = status.get("access_expires_in_human", "")
            except Exception:
                entry["token_status"] = "error"

            # Item count (chỉ lấy nếu token valid)
            if entry["token_status"] == "VALID":
                try:
                    resp = await shopee_client.call(
                        shop_code, "product.get_item_list",
                        extra_params={"offset": 0, "page_size": 50, "item_status": "NORMAL"},
                    )
                    items = resp.get("item", [])
                    entry["item_count"] = resp.get("total_count", len(items))
                    entry["items"] = [
                        {"item_id": it.get("item_id"), "item_status": it.get("item_status", "")}
                        for it in items
                    ]
                except Exception as e:
                    entry["item_count_error"] = str(e)

            return entry

        results = await asyncio.gather(*[fetch_shop(s) for s in shops], return_exceptions=True)
        # Handle exceptions in gather
        clean_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                clean_results.append({
                    "shop_code": shops[i].get("code", ""),
                    "shop_name": shops[i].get("shop_name", ""),
                    "error": str(r),
                })
            else:
                clean_results.append(r)

        return {
            "ok": True,
            "total_shops": len(clean_results),
            "total_items": sum(r.get("item_count", 0) for r in clean_results if isinstance(r, dict)),
            "shops": clean_results,
        }

    # ── CHI TIẾT SẢN PHẨM TOÀN BỘ SHOP ───────────────────────────────

    @mcp.tool()
    async def get_all_items_detail(shop_codes: str = "") -> dict:
        """Lấy thông tin CHI TIẾT tất cả sản phẩm (tên, giá, tồn kho, trạng thái) của 1 hoặc nhiều shop.
        - shop_codes: danh sách shop_code cách nhau bởi dấu phẩy. Bỏ trống = tất cả shop.
        VD: 'abc123,def456' hoặc bỏ trống."""
        shops = resolve_shops(shop_registry_service, shop_codes or "all")

        all_items = []

        async def fetch_detail(shop):
            shop_code = shop.get("code", "")
            shop_name = shop.get("shop_name", "")
            try:
                # Step 1: get item list
                resp = await shopee_client.call(
                    shop_code, "product.get_item_list",
                    extra_params={"offset": 0, "page_size": 50, "item_status": "NORMAL"},
                )
                items = resp.get("item", [])
                if not items:
                    return []

                # Step 2: get base info for all items
                item_ids = ",".join(str(it["item_id"]) for it in items)
                base_info = await shopee_client.call(
                    shop_code, "product.get_item_base_info",
                    extra_params={"item_id_list": item_ids},
                )
                item_list = base_info.get("item_list", [])

                result = []
                for item in item_list:
                    models = item.get("model", [])
                    price_info = item.get("price_info", [{}])
                    stock_info = item.get("stock_info", [{}])

                    entry = {
                        "shop_code": shop_code,
                        "shop_name": shop_name,
                        "item_id": item.get("item_id"),
                        "item_name": item.get("item_name", ""),
                        "item_status": item.get("item_status", ""),
                        "category_id": item.get("category_id"),
                        "has_model": len(models) > 0,
                    }

                    if models:
                        entry["models"] = []
                        for m in models:
                            m_price = m.get("price_info", [{}])
                            m_stock = m.get("stock_info", [{}])
                            entry["models"].append({
                                "model_id": m.get("model_id"),
                                "model_name": ", ".join(
                                    ti.get("option", "") for ti in m.get("tier_index_name", m.get("extinfo", {}).get("tier_index_name", []))
                                ) if "tier_index_name" in m else str(m.get("model_sku", "")),
                                "price": m_price[0].get("current_price") if isinstance(m_price, list) and m_price else m.get("price_info", {}).get("current_price"),
                                "original_price": m_price[0].get("original_price") if isinstance(m_price, list) and m_price else m.get("price_info", {}).get("original_price"),
                                "stock": m_stock[0].get("current_stock") if isinstance(m_stock, list) and m_stock else m.get("stock_info_v2", {}).get("seller_stock", [{}])[0].get("stock") if m.get("stock_info_v2") else 0,
                            })
                    else:
                        entry["price"] = price_info[0].get("current_price") if isinstance(price_info, list) and price_info else item.get("price_info", {}).get("current_price")
                        entry["original_price"] = price_info[0].get("original_price") if isinstance(price_info, list) and price_info else item.get("price_info", {}).get("original_price")
                        entry["stock"] = stock_info[0].get("current_stock") if isinstance(stock_info, list) and stock_info else item.get("stock_info_v2", {}).get("seller_stock", [{}])[0].get("stock") if item.get("stock_info_v2") else 0

                    result.append(entry)
                return result

            except Exception as e:
                return [{"shop_code": shop_code, "shop_name": shop_name, "error": str(e)}]

        gather_results = await asyncio.gather(*[fetch_detail(s) for s in shops], return_exceptions=True)
        for r in gather_results:
            if isinstance(r, Exception):
                all_items.append({"error": str(r)})
            elif isinstance(r, list):
                all_items.extend(r)

        return {
            "ok": True,
            "total_items": len([i for i in all_items if "error" not in i]),
            "items": all_items,
        }

    # ── CHIẾN DỊCH MARKETING TOÀN BỘ SHOP ─────────────────────────────

    @mcp.tool()
    async def get_all_campaigns(shop_codes: str = "") -> dict:
        """Lấy TẤT CẢ voucher + discount của 1 hoặc nhiều shop.
        - shop_codes: cách nhau bởi dấu phẩy. Bỏ trống = tất cả shop."""
        shops = resolve_shops(shop_registry_service, shop_codes or "all")

        all_campaigns = []

        async def fetch_campaigns(shop):
            shop_code = shop.get("code", "")
            shop_name = shop.get("shop_name", "")
            result = {"shop_code": shop_code, "shop_name": shop_name, "vouchers": [], "discounts": []}

            try:
                vouchers = await shopee_client.call(
                    shop_code, "voucher.get_voucher_list",
                    extra_params={"page_no": 1, "page_size": 100, "status": "all"},
                )
                result["vouchers"] = vouchers.get("voucher_list", vouchers.get("voucher", []))
            except Exception as e:
                result["voucher_error"] = str(e)

            try:
                discounts = await shopee_client.call(
                    shop_code, "discount.get_discount_list",
                    extra_params={"discount_status": "all", "page_no": 1, "page_size": 100},
                )
                result["discounts"] = discounts.get("discount_list", discounts.get("discount", []))
            except Exception as e:
                result["discount_error"] = str(e)

            return result

        gather_results = await asyncio.gather(*[fetch_campaigns(s) for s in shops], return_exceptions=True)
        for r in gather_results:
            if isinstance(r, Exception):
                all_campaigns.append({"error": str(r)})
            else:
                all_campaigns.append(r)

        total_vouchers = sum(len(c.get("vouchers", [])) for c in all_campaigns if isinstance(c, dict))
        total_discounts = sum(len(c.get("discounts", [])) for c in all_campaigns if isinstance(c, dict))

        return {
            "ok": True,
            "total_vouchers": total_vouchers,
            "total_discounts": total_discounts,
            "shops": all_campaigns,
        }

    # ── BATCH UPDATE GIÁ ────────────────────────────────────────────────

    @mcp.tool()
    async def batch_update_prices(updates: list[dict]) -> dict:
        """Cập nhật giá HÀNG LOẠT nhiều sản phẩm, nhiều shop cùng lúc.
        updates: danh sách các object, mỗi object gồm:
          - shop_code: mã shop (bắt buộc)
          - item_id: ID sản phẩm (bắt buộc)
          - price: giá mới (bắt buộc)
          - model_id: ID model nếu sản phẩm có biến thể (tùy chọn)
        VD: [
          {"shop_code": "abc", "item_id": 123, "price": 150000},
          {"shop_code": "abc", "item_id": 456, "price": 200000, "model_id": 789}
        ]"""
        results = []

        async def do_update(u):
            shop_code = u["shop_code"]
            item_id = u["item_id"]
            price = u["price"]
            model_id = u.get("model_id")

            price_entry = {"original_price": price}
            if model_id is not None:
                price_entry["model_id"] = model_id

            try:
                resp = await shopee_client.call(
                    shop_code, "product.update_price",
                    body={"item_id": item_id, "price_list": [price_entry]},
                )
                return {"shop_code": shop_code, "item_id": item_id, "status": "ok", "response": resp}
            except Exception as e:
                return {"shop_code": shop_code, "item_id": item_id, "status": "error", "error": str(e)}

        results = await asyncio.gather(*[do_update(u) for u in updates], return_exceptions=True)
        clean = []
        for r in results:
            if isinstance(r, Exception):
                clean.append({"status": "error", "error": str(r)})
            else:
                clean.append(r)

        ok_count = sum(1 for r in clean if r.get("status") == "ok")
        return {
            "ok": True,
            "total": len(clean),
            "success": ok_count,
            "failed": len(clean) - ok_count,
            "results": clean,
        }

    # ── BATCH UPDATE TỒN KHO ────────────────────────────────────────────

    @mcp.tool()
    async def batch_update_stocks(updates: list[dict]) -> dict:
        """Cập nhật tồn kho HÀNG LOẠT nhiều sản phẩm, nhiều shop cùng lúc.
        updates: danh sách các object, mỗi object gồm:
          - shop_code: mã shop (bắt buộc)
          - item_id: ID sản phẩm (bắt buộc)
          - stock: số lượng tồn kho mới (bắt buộc)
          - model_id: ID model nếu sản phẩm có biến thể (tùy chọn)
        VD: [
          {"shop_code": "abc", "item_id": 123, "stock": 100},
          {"shop_code": "abc", "item_id": 456, "stock": 50, "model_id": 789}
        ]"""
        results = []

        async def do_update(u):
            shop_code = u["shop_code"]
            item_id = u["item_id"]
            stock = u["stock"]
            model_id = u.get("model_id")

            stock_entry = {"seller_stock": [{"stock": stock}]}
            if model_id is not None:
                stock_entry["model_id"] = model_id

            try:
                resp = await shopee_client.call(
                    shop_code, "product.update_stock",
                    body={"item_id": item_id, "stock_list": [stock_entry]},
                )
                return {"shop_code": shop_code, "item_id": item_id, "status": "ok", "response": resp}
            except Exception as e:
                return {"shop_code": shop_code, "item_id": item_id, "status": "error", "error": str(e)}

        results = await asyncio.gather(*[do_update(u) for u in updates], return_exceptions=True)
        clean = []
        for r in results:
            if isinstance(r, Exception):
                clean.append({"status": "error", "error": str(r)})
            else:
                clean.append(r)

        ok_count = sum(1 for r in clean if r.get("status") == "ok")
        return {
            "ok": True,
            "total": len(clean),
            "success": ok_count,
            "failed": len(clean) - ok_count,
            "results": clean,
        }

    # ── BATCH UNLIST/LIST SẢN PHẨM ──────────────────────────────────────

    @mcp.tool()
    async def batch_unlist_items(actions: list[dict]) -> dict:
        """Ẩn/hiện sản phẩm HÀNG LOẠT nhiều shop cùng lúc.
        actions: danh sách các object, mỗi object gồm:
          - shop_code: mã shop (bắt buộc)
          - item_id: ID sản phẩm (bắt buộc)
          - unlist: true=ẩn, false=hiện (bắt buộc)
        VD: [
          {"shop_code": "abc", "item_id": 123, "unlist": true},
          {"shop_code": "def", "item_id": 456, "unlist": false}
        ]"""
        # Group by shop_code (Shopee API accepts batch per shop)
        by_shop: dict[str, list] = {}
        for a in actions:
            code = a["shop_code"]
            by_shop.setdefault(code, []).append({"item_id": a["item_id"], "unlist": a["unlist"]})

        results = []

        async def do_unlist(shop_code, item_list):
            try:
                resp = await shopee_client.call(
                    shop_code, "product.unlist_item",
                    body={"item_list": item_list},
                )
                return {"shop_code": shop_code, "status": "ok", "count": len(item_list), "response": resp}
            except Exception as e:
                return {"shop_code": shop_code, "status": "error", "count": len(item_list), "error": str(e)}

        gather = await asyncio.gather(*[do_unlist(code, items) for code, items in by_shop.items()], return_exceptions=True)
        for r in gather:
            if isinstance(r, Exception):
                results.append({"status": "error", "error": str(r)})
            else:
                results.append(r)

        return {"ok": True, "results": results}

    # ── ĐƠN HÀNG TOÀN BỘ SHOP ──────────────────────────────────────────

    @mcp.tool()
    async def get_all_orders(shop_codes: str = "", time_range_field: str = "create_time",
                              days_back: int = 7, page_size: int = 50) -> dict:
        """Lấy đơn hàng từ TẤT CẢ shop trong N ngày gần nhất.
        - shop_codes: cách nhau bởi dấu phẩy. Bỏ trống = tất cả shop.
        - time_range_field: create_time hoặc update_time
        - days_back: lấy đơn trong N ngày gần nhất (mặc định 7)"""
        import time
        shops = resolve_shops(shop_registry_service, shop_codes or "all")

        now = int(time.time())
        time_from = now - (days_back * 86400)

        all_orders = []

        async def fetch_orders(shop):
            shop_code = shop.get("code", "")
            shop_name = shop.get("shop_name", "")
            try:
                orders = await _fetch_all_order_pages(
                    shop_code,
                    time_range_field=time_range_field,
                    time_from=time_from,
                    time_to=now,
                    page_size=page_size,
                    order_status="ALL",
                )
                return {
                    "shop_code": shop_code,
                    "shop_name": shop_name,
                    "order_count": len(orders),
                    "orders": orders,
                }
            except Exception as e:
                return {"shop_code": shop_code, "shop_name": shop_name, "error": str(e)}

        gather = await asyncio.gather(*[fetch_orders(s) for s in shops], return_exceptions=True)
        for r in gather:
            if isinstance(r, Exception):
                all_orders.append({"error": str(r)})
            else:
                all_orders.append(r)

        total = sum(o.get("order_count", 0) for o in all_orders if isinstance(o, dict))
        return {"ok": True, "total_orders": total, "shops": all_orders}

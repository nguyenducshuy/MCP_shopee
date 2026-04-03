"""
Workflow tools — Luồng tổng hợp nghiệp vụ cho N shop.

Mỗi tool gọi N shop song song, cache kết quả, trả về 1 response duy nhất.
AI Agent chỉ cần 1 call thay vì N×M calls.
"""

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from app.dependencies import shopee_client, shop_registry_service, cache_service
from app.services.parallel_executor import execute_parallel
from app.core.utils import resolve_shops as _resolve_shops_util


def _resolve_shops(shop_codes: str) -> list[dict]:
    return _resolve_shops_util(shop_registry_service, shop_codes)


def _cache_key(shop_code: str, extra: str = "") -> str:
    return f"{shop_code}:{extra}" if extra else shop_code


VN_TZ = timezone(timedelta(hours=7))


def _vn_day_start(now_ts: int) -> int:
    """Return VN-local midnight for the provided unix timestamp."""
    dt = datetime.fromtimestamp(now_ts, VN_TZ)
    return int(datetime(dt.year, dt.month, dt.day, tzinfo=VN_TZ).timestamp())


async def _fetch_all_orders(
    shop_code: str,
    *,
    time_from: int,
    time_to: int,
    time_range_field: str = "create_time",
    page_size: int = 100,
    order_status: str | None = None,
) -> dict:
    """Fetch all pages for order.get_order_list using cursor pagination when available."""
    all_orders: list[dict] = []
    cursor = ""
    total_count = 0

    for _ in range(100):
        params = {
            "time_range_field": time_range_field,
            "time_from": time_from,
            "time_to": time_to,
            "page_size": page_size,
        }
        if order_status is not None:
            params["order_status"] = order_status
        if cursor:
            params["cursor"] = cursor

        data = await shopee_client.call(shop_code, "order.get_order_list", extra_params=params)
        page_orders = data.get("order_list", [])
        all_orders.extend(page_orders)
        total_count = max(total_count, data.get("total_count", 0), len(all_orders))

        next_cursor = data.get("next_cursor", "")
        has_more = bool(data.get("more")) or bool(data.get("has_next_page"))
        if not next_cursor and not has_more:
            break
        if not next_cursor:
            break
        cursor = next_cursor

    return {"orders": all_orders, "total_count": max(total_count, len(all_orders))}


def register_workflow_tools(mcp):

    # ══════════════════════════════════════════════════════════════════
    # D1: DASHBOARD TỔNG QUAN TẤT CẢ SHOP
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def dashboard_all_shops(shop_codes: str = "all", max_concurrent: int = 10) -> dict:
        """Tổng quan toàn bộ shop: tên, trạng thái, token, số sản phẩm.
        shop_codes: 'all' hoặc 'shop1,shop2,...'"""
        shops = _resolve_shops(shop_codes)
        if not shops:
            return {"ok": False, "error": "No active shops found"}

        async def _fetch(shop):
            code = shop["code"]
            result = {"shop_code": code, "shop_name": shop.get("shop_name", "")}

            # Token status
            token_exp = shop.get("token_expire_at", 0)
            now = int(time.time())
            if not shop.get("access_token"):
                result["token_status"] = "MISSING"
            elif token_exp < now:
                result["token_status"] = "EXPIRED"
            elif token_exp - now < 600:
                result["token_status"] = "EXPIRING"
            else:
                result["token_status"] = "VALID"
                result["token_remaining_h"] = round((token_exp - now) / 3600, 1)

            # Item count (cached)
            cached = cache_service.get("item_list", _cache_key(code))
            if cached:
                result["item_count"] = cached.get("total_count", len(cached.get("item", [])))
                result["cache_hit"] = True
            else:
                try:
                    data = await shopee_client.call(code, "product.get_item_list",
                        extra_params={"offset": 0, "page_size": 1, "item_status": "NORMAL"})
                    result["item_count"] = data.get("total_count", 0)
                    cache_service.set("item_list", _cache_key(code), data)
                    result["cache_hit"] = False
                except Exception as e:
                    result["item_count"] = "error"
                    result["item_error"] = str(e)

            return result

        batch = await execute_parallel(shops, _fetch, max_concurrent=max_concurrent)
        summary = {
            "total_shops": batch.total,
            "token_valid": sum(1 for r in batch.success_results if r.data.get("token_status") == "VALID"),
            "token_expiring": sum(1 for r in batch.success_results if r.data.get("token_status") == "EXPIRING"),
            "token_expired": sum(1 for r in batch.success_results if r.data.get("token_status") in ("EXPIRED", "MISSING")),
            "total_items": sum(r.data.get("item_count", 0) for r in batch.success_results if isinstance(r.data.get("item_count"), int)),
        }
        return {"summary": summary, **batch.to_dict()}

    # ══════════════════════════════════════════════════════════════════
    # D2: DASHBOARD ĐƠN HÀNG HÔM NAY
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def dashboard_orders_today(shop_codes: str = "all", max_concurrent: int = 10) -> dict:
        """Tổng hợp đơn hàng hôm nay từ tất cả shop: chờ xử lý, đang giao, hoàn thành."""
        shops = _resolve_shops(shop_codes)
        if not shops:
            return {"ok": False, "error": "No active shops found"}

        now = int(time.time())
        today_start = _vn_day_start(now)

        async def _fetch(shop):
            code = shop["code"]

            cached = cache_service.get("order_list", _cache_key(code, "today"))
            if cached:
                return cached

            try:
                data = await _fetch_all_orders(
                    code,
                    time_range_field="create_time",
                    time_from=today_start,
                    time_to=now,
                    page_size=100,
                )
                result = {
                    "shop_code": code,
                    "shop_name": shop.get("shop_name", ""),
                    "total_orders": data.get("total_count", len(data.get("orders", []))),
                    "orders": data.get("orders", []),
                }
                cache_service.set("order_list", _cache_key(code, "today"), result, ttl=60)
                return result
            except Exception as e:
                return {"shop_code": code, "error": str(e), "total_orders": 0, "orders": []}

        batch = await execute_parallel(shops, _fetch, max_concurrent=max_concurrent)

        total_orders = 0
        all_orders = []
        for r in batch.success_results:
            total_orders += r.data.get("total_orders", 0)
            for o in r.data.get("orders", []):
                o["_shop_code"] = r.data.get("shop_code", r.shop_code)
                all_orders.append(o)

        return {
            "summary": {
                "total_shops": batch.total,
                "total_orders_today": total_orders,
            },
            **batch.to_dict(),
        }

    # ══════════════════════════════════════════════════════════════════
    # P1: QUÉT TOÀN BỘ SẢN PHẨM
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def scan_all_products(shop_codes: str = "all", max_concurrent: int = 10) -> dict:
        """Quét toàn bộ sản phẩm từ N shop. Trả về danh sách item_id, tên, giá, tồn kho, trạng thái."""
        shops = _resolve_shops(shop_codes)
        if not shops:
            return {"ok": False, "error": "No active shops found"}

        async def _fetch(shop):
            code = shop["code"]

            # Step 1: Get item list
            cached_list = cache_service.get("item_list", _cache_key(code, "full"))
            if cached_list:
                return cached_list

            all_items = []
            offset = 0
            while True:
                data = await shopee_client.call(code, "product.get_item_list",
                    extra_params={"offset": offset, "page_size": 50, "item_status": "NORMAL"})
                items = data.get("item", [])
                all_items.extend(items)
                if not data.get("has_next_page", False) or not items:
                    break
                offset += len(items)

            if not all_items:
                result = {"shop_code": code, "shop_name": shop.get("shop_name", ""), "items": [], "total": 0}
                cache_service.set("item_list", _cache_key(code, "full"), result)
                return result

            # Step 2: Get base info (batch by 50)
            item_ids = [str(i["item_id"]) for i in all_items]
            detailed_items = []
            for i in range(0, len(item_ids), 50):
                chunk = item_ids[i:i+50]
                info = await shopee_client.call(code, "product.get_item_base_info",
                    extra_params={"item_id_list": ",".join(chunk)})
                for item in info.get("item_list", []):
                    detailed_items.append({
                        "shop_code": code,
                        "item_id": item.get("item_id"),
                        "item_name": item.get("item_name", ""),
                        "item_status": item.get("item_status", ""),
                        "price": item.get("price_info", [{}])[0].get("original_price") if item.get("price_info") else None,
                        "stock": item.get("stock_info_v2", {}).get("summary_info", {}).get("total_available_stock", 0),
                        "sales": item.get("sales", 0),
                    })

            result = {
                "shop_code": code,
                "shop_name": shop.get("shop_name", ""),
                "items": detailed_items,
                "total": len(detailed_items),
            }
            cache_service.set("item_list", _cache_key(code, "full"), result)
            return result

        batch = await execute_parallel(shops, _fetch, max_concurrent=max_concurrent, timeout_per_shop=60)

        all_items = []
        for r in batch.success_results:
            all_items.extend(r.data.get("items", []))

        return {
            "summary": {
                "total_shops": batch.total,
                "total_products": len(all_items),
                "shops_success": batch.success_count,
                "shops_failed": batch.failed_count,
            },
            "products": all_items,
            **batch.to_dict(include_details=False),
        }

    # ══════════════════════════════════════════════════════════════════
    # P2: TÌM SẢN PHẨM SẮP HẾT HÀNG
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def find_low_stock_products(
        shop_codes: str = "all", threshold: int = 10, max_concurrent: int = 10
    ) -> dict:
        """Tìm sản phẩm có tồn kho thấp hơn ngưỡng (mặc định < 10) trên tất cả shop."""
        result = await scan_all_products(shop_codes=shop_codes, max_concurrent=max_concurrent)
        if "products" not in result:
            return result

        low_stock = [p for p in result["products"] if isinstance(p.get("stock"), int) and p["stock"] < threshold]
        low_stock.sort(key=lambda x: x.get("stock", 0))

        return {
            "summary": {
                "total_products_scanned": len(result["products"]),
                "low_stock_count": len(low_stock),
                "threshold": threshold,
            },
            "low_stock_products": low_stock,
        }

    # ══════════════════════════════════════════════════════════════════
    # O1: ĐƠN HÀNG CHỜ XỬ LÝ TẤT CẢ SHOP
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def pending_orders_all_shops(shop_codes: str = "all", max_concurrent: int = 10) -> dict:
        """Lấy tất cả đơn chờ xử lý (READY_TO_SHIP) từ N shop, sắp theo thời gian."""
        shops = _resolve_shops(shop_codes)
        if not shops:
            return {"ok": False, "error": "No active shops found"}

        now = int(time.time())

        async def _fetch(shop):
            code = shop["code"]
            data = await shopee_client.call(code, "order.get_order_list",
                extra_params={
                    "time_range_field": "create_time",
                    "time_from": now - 7 * 86400,  # last 7 days
                    "time_to": now,
                    "page_size": 100,
                    "order_status": "READY_TO_SHIP",
                })
            orders = data.get("order_list", [])
            for o in orders:
                o["_shop_code"] = code
                o["_shop_name"] = shop.get("shop_name", "")
            return {
                "shop_code": code,
                "count": len(orders),
                "orders": orders,
            }

        batch = await execute_parallel(shops, _fetch, max_concurrent=max_concurrent)

        all_pending = []
        for r in batch.success_results:
            all_pending.extend(r.data.get("orders", []))

        # Sort by create_time (oldest first = most urgent)
        all_pending.sort(key=lambda x: x.get("create_time", 0))

        return {
            "summary": {
                "total_shops": batch.total,
                "total_pending_orders": len(all_pending),
                "by_shop": [
                    {"shop_code": r.data["shop_code"], "count": r.data["count"]}
                    for r in batch.success_results if r.data.get("count", 0) > 0
                ],
            },
            "pending_orders": all_pending,
            "errors": [r.to_dict() for r in batch.failed_results] if batch.failed_results else [],
        }

    # ══════════════════════════════════════════════════════════════════
    # P4: CẬP NHẬT GIÁ HÀNG LOẠT
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def bulk_update_prices(updates: list[dict], max_concurrent: int = 10) -> dict:
        """Cập nhật giá hàng loạt. updates: [{"shop_code": "x", "item_id": 123, "price": 100000, "model_id": 0}]
        model_id=0 nếu không có variation."""

        # Group by shop
        by_shop: dict[str, list[dict]] = {}
        for u in updates:
            code = u["shop_code"]
            by_shop.setdefault(code, []).append(u)

        results = []
        for code, items in by_shop.items():
            for item in items:
                price_entry: dict = {"original_price": item["price"]}
                if item.get("model_id"):
                    price_entry["model_id"] = item["model_id"]
                try:
                    data = await shopee_client.call(code, "product.update_price",
                        body={"item_id": item["item_id"], "price_list": [price_entry]})
                    results.append({"shop_code": code, "item_id": item["item_id"], "ok": True, "data": data})
                    cache_service.delete("item_list", _cache_key(code, "full"))
                except Exception as e:
                    results.append({"shop_code": code, "item_id": item["item_id"], "ok": False, "error": str(e)})

        success = sum(1 for r in results if r["ok"])
        return {
            "summary": {"total_updates": len(updates), "shops_success": success, "shops_failed": len(results) - success},
            "results": results,
        }

    # ══════════════════════════════════════════════════════════════════
    # P5: CẬP NHẬT TỒN KHO HÀNG LOẠT
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def bulk_update_stocks(updates: list[dict], max_concurrent: int = 10) -> dict:
        """Cập nhật tồn kho hàng loạt. updates: [{"shop_code": "x", "item_id": 123, "stock": 50, "model_id": 0}]"""

        by_shop: dict[str, list[dict]] = {}
        for u in updates:
            code = u["shop_code"]
            by_shop.setdefault(code, []).append(u)

        results = []
        for code, items in by_shop.items():
            for item in items:
                stock_entry: dict = {"seller_stock": [{"stock": item["stock"]}]}
                if item.get("model_id"):
                    stock_entry["model_id"] = item["model_id"]
                try:
                    data = await shopee_client.call(code, "product.update_stock",
                        body={"item_id": item["item_id"], "stock_list": [stock_entry]})
                    results.append({"shop_code": code, "item_id": item["item_id"], "ok": True, "data": data})
                    cache_service.delete("item_list", _cache_key(code, "full"))
                except Exception as e:
                    results.append({"shop_code": code, "item_id": item["item_id"], "ok": False, "error": str(e)})

        success = sum(1 for r in results if r["ok"])
        return {
            "summary": {"total_updates": len(updates), "shops_success": success, "shops_failed": len(results) - success},
            "results": results,
        }

    # ══════════════════════════════════════════════════════════════════
    # C1: COMMENT CHƯA TRẢ LỜI
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def unreplied_comments_all_shops(shop_codes: str = "all", max_concurrent: int = 10) -> dict:
        """Lấy tất cả comment chưa trả lời trên N shop."""
        shops = _resolve_shops(shop_codes)
        if not shops:
            return {"ok": False, "error": "No active shops found"}

        async def _fetch(shop):
            code = shop["code"]
            data = await shopee_client.call(code, "product.get_comment",
                extra_params={"cursor": "", "page_size": 50})
            comments = data.get("item_comment_list", [])
            unreplied = []
            for c in comments:
                for cmt in c.get("comment_list", []):
                    if not cmt.get("reply", {}).get("reply"):
                        unreplied.append({
                            "shop_code": code,
                            "item_id": c.get("item_id"),
                            "comment_id": cmt.get("comment_id"),
                            "buyer_username": cmt.get("buyer_username", ""),
                            "comment": cmt.get("comment", ""),
                            "rating_star": cmt.get("rating_star", 0),
                            "create_time": cmt.get("create_time", 0),
                        })
            return {"shop_code": code, "unreplied": unreplied, "count": len(unreplied)}

        batch = await execute_parallel(shops, _fetch, max_concurrent=max_concurrent)

        all_unreplied = []
        for r in batch.success_results:
            all_unreplied.extend(r.data.get("unreplied", []))

        # Sort: negative reviews first
        all_unreplied.sort(key=lambda x: (x.get("rating_star", 5), x.get("create_time", 0)))

        return {
            "summary": {
                "total_shops": batch.total,
                "total_unreplied": len(all_unreplied),
                "negative_reviews": sum(1 for c in all_unreplied if c.get("rating_star", 5) <= 2),
            },
            "unreplied_comments": all_unreplied,
        }

    # ══════════════════════════════════════════════════════════════════
    # R5: ACTION ITEMS HÔM NAY (QUAN TRỌNG NHẤT)
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def action_items_today(shop_codes: str = "all", max_concurrent: int = 10) -> dict:
        """Danh sách VIỆC CẦN LÀM hôm nay trên tất cả shop:
        - Đơn chờ ship
        - Comment chưa reply
        - Sản phẩm sắp hết hàng
        - Token sắp hết hạn
        1 tool thay 10+ tools. Gọi đầu ngày."""
        shops = _resolve_shops(shop_codes)
        if not shops:
            return {"ok": False, "error": "No active shops found"}

        now = int(time.time())
        actions = {"urgent": [], "needs_attention": [], "info": []}

        # 1. Token health
        for shop in shops:
            code = shop["code"]
            token_exp = shop.get("token_expire_at", 0)
            refresh_exp = shop.get("refresh_expire_at", 0)

            if not shop.get("access_token"):
                actions["urgent"].append({
                    "type": "TOKEN_MISSING",
                    "shop_code": code,
                    "shop_name": shop.get("shop_name", ""),
                    "message": "Chưa có token. Cần authorize lại.",
                })
            elif refresh_exp > 0 and refresh_exp < now:
                actions["urgent"].append({
                    "type": "REFRESH_TOKEN_EXPIRED",
                    "shop_code": code,
                    "shop_name": shop.get("shop_name", ""),
                    "message": "Refresh token hết hạn. Cần lấy OAuth code mới.",
                })
            elif token_exp > 0 and token_exp < now + 600:
                actions["needs_attention"].append({
                    "type": "TOKEN_EXPIRING",
                    "shop_code": code,
                    "shop_name": shop.get("shop_name", ""),
                    "message": f"Token hết hạn trong {max(0, (token_exp - now) // 60)} phút.",
                })

        # 2. Pending orders (parallel across all shops)
        async def _get_pending(shop):
            code = shop["code"]
            if not shop.get("access_token"):
                return {"count": 0, "orders": []}
            try:
                data = await shopee_client.call(code, "order.get_order_list",
                    extra_params={
                        "time_range_field": "create_time",
                        "time_from": now - 7 * 86400,
                        "time_to": now,
                        "page_size": 50,
                        "order_status": "READY_TO_SHIP",
                    })
                orders = data.get("order_list", [])
                return {"count": len(orders), "shop_code": code, "shop_name": shop.get("shop_name", "")}
            except Exception:
                return {"count": 0}

        async def _get_comments(shop):
            code = shop["code"]
            if not shop.get("access_token"):
                return {"count": 0}
            try:
                data = await shopee_client.call(code, "product.get_comment",
                    extra_params={"cursor": "", "page_size": 20})
                unreplied = 0
                negative = 0
                for c in data.get("item_comment_list", []):
                    for cmt in c.get("comment_list", []):
                        if not cmt.get("reply", {}).get("reply"):
                            unreplied += 1
                            if cmt.get("rating_star", 5) <= 2:
                                negative += 1
                return {"count": unreplied, "negative": negative, "shop_code": code}
            except Exception:
                return {"count": 0, "negative": 0}

        import asyncio
        # Run orders and comments in parallel
        order_tasks = [_get_pending(s) for s in shops]
        comment_tasks = [_get_comments(s) for s in shops]

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _with_sem(coro):
            async with semaphore:
                return await coro

        all_results = await asyncio.gather(
            *[_with_sem(t) for t in order_tasks],
            *[_with_sem(t) for t in comment_tasks],
            return_exceptions=True,
        )

        order_results = all_results[:len(shops)]
        comment_results = all_results[len(shops):]

        # Process orders
        total_pending = 0
        for r in order_results:
            if isinstance(r, dict) and r.get("count", 0) > 0:
                total_pending += r["count"]
                actions["needs_attention"].append({
                    "type": "PENDING_ORDERS",
                    "shop_code": r.get("shop_code", ""),
                    "shop_name": r.get("shop_name", ""),
                    "count": r["count"],
                    "message": f"{r['count']} đơn chờ ship.",
                })

        # Process comments
        total_unreplied = 0
        total_negative = 0
        for r in comment_results:
            if isinstance(r, dict):
                if r.get("negative", 0) > 0:
                    total_negative += r["negative"]
                    actions["urgent"].append({
                        "type": "NEGATIVE_REVIEW",
                        "shop_code": r.get("shop_code", ""),
                        "count": r["negative"],
                        "message": f"{r['negative']} đánh giá tiêu cực (1-2 sao) chưa phản hồi.",
                    })
                if r.get("count", 0) > 0:
                    total_unreplied += r["count"]

        if total_unreplied > 0:
            actions["info"].append({
                "type": "UNREPLIED_COMMENTS",
                "total": total_unreplied,
                "message": f"Tổng {total_unreplied} comment chưa trả lời trên tất cả shop.",
            })

        return {
            "summary": {
                "total_shops": len(shops),
                "urgent_items": len(actions["urgent"]),
                "attention_items": len(actions["needs_attention"]),
                "info_items": len(actions["info"]),
                "total_pending_orders": total_pending,
                "total_unreplied_comments": total_unreplied,
                "total_negative_reviews": total_negative,
            },
            "actions": actions,
        }

    # ══════════════════════════════════════════════════════════════════
    # ADS1: GỢI Ý BẬT CAMPAIGN CHO SẢN PHẨM BÁN TỐT NHƯNG CHƯA CÓ ADS
    # ══════════════════════════════════════════════════════════════════
    @mcp.tool()
    async def suggest_campaigns_for_top_sellers(
        shop_code: str,
        days: int = 7,
        min_revenue: int = 0,
        min_orders: int = 1,
        top_n: int = 20,
    ) -> dict:
        """Phân tích đơn hàng N ngày qua, tìm sản phẩm bán tốt nhưng CHƯA có campaign quảng cáo đang chạy.
        Trả về gợi ý bật campaign kèm budget + keyword suggestions từ Shopee.
        - shop_code: mã shop
        - days: số ngày phân tích (mặc định 7)
        - min_revenue: doanh thu tối thiểu (VND) để được gợi ý (0 = tất cả)
        - min_orders: số đơn tối thiểu để được gợi ý (mặc định 1)
        - top_n: số sản phẩm gợi ý tối đa (mặc định 20)
        """

        now = int(time.time())
        time_from = now - days * 86400

        # ── Step 1: Lấy đơn hàng N ngày, chia chunk 15 ngày (giới hạn Shopee) ─
        all_order_sns = []
        chunk_start = time_from
        while chunk_start < now:
            chunk_end = min(chunk_start + 15 * 86400, now)
            cursor = ""
            for _ in range(20):  # max 20 pages per chunk
                params = {
                    "time_range_field": "create_time",
                    "time_from": chunk_start,
                    "time_to": chunk_end,
                    "page_size": 100,
                }
                if cursor:
                    params["cursor"] = cursor
                data = await shopee_client.call(shop_code, "order.get_order_list", extra_params=params)
                orders = data.get("order_list", [])
                all_order_sns.extend([o["order_sn"] for o in orders if o.get("order_sn")])
                if not data.get("more", False) and not data.get("next_cursor"):
                    break
                cursor = data.get("next_cursor", "")
                if not cursor:
                    break
            chunk_start = chunk_end

        if not all_order_sns:
            return {
                "ok": True,
                "message": f"Không có đơn hàng nào trong {days} ngày qua.",
                "suggestions": [],
            }

        # ── Step 2: Lấy chi tiết đơn → tổng hợp doanh thu theo item_id ─
        item_stats = defaultdict(lambda: {"revenue": 0, "quantity": 0, "orders": 0, "item_name": ""})

        for i in range(0, len(all_order_sns), 50):
            chunk = all_order_sns[i:i + 50]
            try:
                detail = await shopee_client.call(shop_code, "order.get_order_detail", extra_params={
                    "order_sn_list": ",".join(chunk),
                    "response_optional_fields": "item_list",
                })
                for order in detail.get("order_list", []):
                    # Chỉ tính đơn thành công
                    status = order.get("order_status", "")
                    if status in ("CANCELLED", "INVOICE_PENDING"):
                        continue
                    for item in order.get("item_list", []):
                        iid = item.get("item_id", 0)
                        if not iid:
                            continue
                        qty = item.get("model_quantity_purchased", 0) or item.get("quantity", 0) or 1
                        price = item.get("model_discounted_price", 0) or item.get("model_original_price", 0) or 0
                        revenue = price * qty
                        item_stats[iid]["revenue"] += revenue
                        item_stats[iid]["quantity"] += qty
                        item_stats[iid]["orders"] += 1
                        if not item_stats[iid]["item_name"]:
                            item_stats[iid]["item_name"] = item.get("item_name", "")
            except Exception:
                continue

        if not item_stats:
            return {
                "ok": True,
                "message": f"Có {len(all_order_sns)} đơn nhưng không lấy được chi tiết item.",
                "suggestions": [],
            }

        # ── Step 3: Lấy tất cả campaign ongoing → set item_id đã có ads ─
        ads_item_ids = set()
        campaign_by_item = {}  # item_id → campaign info

        # Get all campaign IDs
        all_campaign_ids = []
        offset = 0
        for _ in range(30):
            cdata = await shopee_client.call(shop_code, "ads.get_product_level_campaign_id_list",
                extra_params={"page_size": 50, "offset": offset})
            clist = cdata.get("campaign_list", [])
            all_campaign_ids.extend([str(c["campaign_id"]) for c in clist])
            if not cdata.get("has_next_page", False) or not clist:
                break
            offset += len(clist)

        # Get settings in batches to find ongoing ones
        for i in range(0, len(all_campaign_ids), 20):
            batch = all_campaign_ids[i:i + 20]
            try:
                info = await shopee_client.call(shop_code, "ads.get_product_level_campaign_setting_info",
                    extra_params={"campaign_id_list": ",".join(batch), "info_type_list": "1"})
                for c in info.get("campaign_list", []):
                    cstatus = c.get("common_info", {}).get("campaign_status", "")
                    if cstatus == "ongoing":
                        for iid in c.get("common_info", {}).get("item_id_list", []):
                            ads_item_ids.add(iid)
                            campaign_by_item[iid] = {
                                "campaign_id": c["campaign_id"],
                                "ad_name": c["common_info"].get("ad_name", ""),
                                "budget": c["common_info"].get("campaign_budget", 0),
                            }
            except Exception:
                continue

        # ── Step 4: So sánh → sản phẩm bán tốt nhưng chưa có ads ───
        suggestions = []
        already_has_ads = []

        for iid, stats in item_stats.items():
            if stats["orders"] < min_orders:
                continue
            if min_revenue > 0 and stats["revenue"] < min_revenue:
                continue

            entry = {
                "item_id": iid,
                "item_name": stats["item_name"],
                "revenue_7d": stats["revenue"],
                "quantity_sold_7d": stats["quantity"],
                "orders_7d": stats["orders"],
            }

            if iid in ads_item_ids:
                entry["has_active_campaign"] = True
                entry["current_campaign"] = campaign_by_item.get(iid, {})
                already_has_ads.append(entry)
            else:
                entry["has_active_campaign"] = False
                suggestions.append(entry)

        # Sort by revenue descending
        suggestions.sort(key=lambda x: x["revenue_7d"], reverse=True)
        already_has_ads.sort(key=lambda x: x["revenue_7d"], reverse=True)
        suggestions = suggestions[:top_n]

        # ── Step 5: Gợi ý budget + keyword cho top suggestions ──────
        async def _enrich(item):
            iid = item["item_id"]
            # Budget suggestion
            try:
                budget = await shopee_client.call(shop_code, "ads.get_create_product_ad_budget_suggestion",
                    extra_params={
                        "item_id": iid, "bidding_method": "auto",
                        "campaign_placement": "all", "product_selection": "manual",
                        "reference_id": 0,
                    })
                item["budget_suggestion"] = budget.get("budget", {})
            except Exception:
                item["budget_suggestion"] = None

            # Keyword suggestions
            try:
                kw = await shopee_client.call(shop_code, "ads.get_recommended_keyword_list",
                    extra_params={"item_id": iid, "page_size": 10})
                item["keyword_suggestions"] = kw.get("keyword_list", [])[:5]
            except Exception:
                item["keyword_suggestions"] = []

            # ROI target
            try:
                roi = await shopee_client.call(shop_code, "ads.get_product_recommended_roi_target",
                    extra_params={"item_id": iid, "reference_id": 0})
                item["recommended_roi_target"] = roi
            except Exception:
                item["recommended_roi_target"] = None

            return item

        # Enrich top 10 (limit API calls)
        enriched = []
        sem = asyncio.Semaphore(5)
        async def _safe_enrich(item):
            async with sem:
                return await _enrich(item)

        enriched = await asyncio.gather(*[_safe_enrich(s) for s in suggestions[:10]])
        # Replace first 10 with enriched, keep rest as-is
        suggestions = list(enriched) + suggestions[10:]

        return {
            "ok": True,
            "summary": {
                "period_days": days,
                "total_orders_analyzed": len(all_order_sns),
                "unique_items_sold": len(item_stats),
                "items_with_active_ads": len(ads_item_ids),
                "items_selling_without_ads": len([s for s in suggestions]),
                "items_selling_with_ads": len(already_has_ads),
                "total_campaigns_ongoing": len(ads_item_ids),
            },
            "suggestions": suggestions,
            "already_has_ads": already_has_ads[:10],
            "action_plan": (
                f"Có {len(suggestions)} sản phẩm bán được hàng trong {days} ngày qua "
                f"nhưng CHƯA có campaign quảng cáo. "
                f"Gợi ý tạo campaign cho các sản phẩm này để tăng doanh thu. "
                f"Top {min(len(suggestions), 10)} sản phẩm đã có gợi ý budget và keyword từ Shopee."
            ),
        }

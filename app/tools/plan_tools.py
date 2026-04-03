"""Flash Sale planning tools — orchestration tập trung trên MCP server.

Hai tool:
  plan_flash_sale          — nhận rows từ sheet, phân bổ slot, tạo/tìm phiên, add items, enable.
  delete_flash_sale_by_date — tìm tất cả phiên trong ngày, disable + delete.

Thiết kế:
  - Xử lý nhiều shop song song bằng asyncio.gather.
  - Mỗi shop: lấy timeslots → sort SP theo sales_velocity → nhóm ITEMS_PER_SESSION/slot
    → create/reuse session → add items → enable.
  - Trả về cấu trúc chuẩn để Apps Script đọc và ghi thẳng vào sheet.
"""
import asyncio
import time as _time
from datetime import datetime, timezone, timedelta

from app.dependencies import shopee_client
from app.core.logger import get_logger

logger = get_logger(__name__)

VN_TZ = timezone(timedelta(hours=7))
ITEMS_PER_SESSION = 10  # SP tối đa mỗi phiên FS


# ────────────────────────────────────────────────────────────────
# PARSE / FORMAT
# ────────────────────────────────────────────────────────────────

def _parse_target_date(date_str: str) -> tuple[int, int]:
    """Parse 'DD-MM-YYYY' → (ts_start_of_day, ts_end_of_day) theo VN TZ."""
    dt = datetime.strptime(date_str.strip(), "%d-%m-%Y")
    start = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=VN_TZ)
    end   = datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=VN_TZ)
    return int(start.timestamp()), int(end.timestamp())


def _ts_to_date_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, VN_TZ).strftime("%d-%m-%Y")


def _ts_to_time_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, VN_TZ).strftime("%H:%M")


# ────────────────────────────────────────────────────────────────
# EXTRACT FROM API RESPONSES
# ────────────────────────────────────────────────────────────────

def _extract_time_slots(r) -> list:
    if isinstance(r, list):
        return r
    if not isinstance(r, dict):
        return []
    slots = r.get("time_slot_list") or r.get("time_slot") or []
    return slots if isinstance(slots, list) else []


def _extract_flash_sale_list(r: dict) -> list:
    if not isinstance(r, dict):
        return []
    lst = r.get("flash_sale_list") or []
    return lst if isinstance(lst, list) else []


def _build_failed_map(failed_items: list) -> dict:
    """Xây {item_id|model_id: failed_info} từ failed_items response."""
    m: dict[str, dict] = {}
    for f in (failed_items or []):
        if not isinstance(f, dict):
            continue
        item_id  = f.get("item_id")
        model_id = f.get("model_id") or 0
        if item_id is None:
            continue
        key = f"{item_id}|{model_id}"
        m[key] = f
        # Alias không có model
        if not model_id:
            m[f"{item_id}|0"] = f
    return m


# ────────────────────────────────────────────────────────────────
# BUILD API PAYLOAD
# ────────────────────────────────────────────────────────────────

def _build_items_payload(rows: list) -> list:
    """Gom rows → danh sách items cho add_shop_flash_sale_items.
    SP cùng item_id nhưng khác model_id được gom vào mảng models[].
    """
    item_map: dict[int, dict] = {}
    items: list[dict] = []

    for r in rows:
        item_id  = r["item_id"]
        model_id = r.get("model_id") or 0
        fs_price = r.get("fs_price") or 0
        stock    = 1  # luôn lấy 1 đơn vị từ kho cho mỗi SP trong phiên FS
        limit    = r.get("limit") or 0

        if model_id:
            # SP có biến thể
            if item_id not in item_map:
                obj: dict = {"item_id": item_id, "purchase_limit": limit, "models": []}
                item_map[item_id] = obj
                items.append(obj)
            item_map[item_id]["models"].append({
                "model_id":          model_id,
                "input_promo_price": fs_price,
                "stock":             stock,
            })
        else:
            # SP không biến thể
            if item_id not in item_map:
                obj = {
                    "item_id":              item_id,
                    "purchase_limit":       limit,
                    "item_input_promo_price": fs_price,
                    "item_stock":           stock,
                }
                item_map[item_id] = obj
                items.append(obj)

    return items


# ────────────────────────────────────────────────────────────────
# SKIP HELPER
# ────────────────────────────────────────────────────────────────

_TRANSIENT_PATTERNS = [
    "server error",
    "please wait",
    "service unavailable",
    "internal error",
    "timeout",
    "too many requests",
    "rate limit",
]

def _is_transient(msg: str) -> bool:
    m = msg.lower()
    return any(p in m for p in _TRANSIENT_PATTERNS)


def _make_skip(row_index: int, shop: str, item_id: int, model_id: int, reason: str) -> dict:
    return {
        "row_index": row_index,
        "shop":      shop,
        "item_id":   item_id,
        "model_id":  model_id or 0,
        "status":    "SKIP",
        "reason":    reason,
    }


# ────────────────────────────────────────────────────────────────
# SESSION MANAGEMENT
# ────────────────────────────────────────────────────────────────

async def _find_existing_session(shop_code: str, timeslot_id: int) -> int | None:
    """Tìm phiên FS (status 1=enabled hoặc 2=disabled) cho timeslot đã cho.
    Quét toàn bộ trang (pagination) để không bỏ sót khi shop có nhiều session.
    """
    target = int(timeslot_id)
    for fs_type in [1, 2]:
        offset = 0
        while True:
            list_resp = await shopee_client.call(
                shop_code,
                "shop_flash_sale.get_shop_flash_sale_list",
                extra_params={"type": fs_type, "offset": offset, "limit": 100},
            )
            page = _extract_flash_sale_list(list_resp)
            logger.info(
                "_find_existing_session | shop=%s | type=%s | offset=%s | page_len=%s | timeslot_ids=%s",
                shop_code, fs_type, offset, len(page),
                [fs.get("timeslot_id") for fs in page if isinstance(fs, dict)][:10],
            )
            for fs in page:
                if not isinstance(fs, dict):
                    continue
                if int(fs.get("timeslot_id", -1)) == target:
                    return int(fs["flash_sale_id"])
            if len(page) < 100:
                break
            offset += 100
            if offset > 1000:
                break
    return None


async def _get_or_create_session(shop_code: str, shop_name: str, timeslot_id: int, logs: list) -> int | None:
    """Tìm phiên hiện có hoặc tạo mới cho timeslot_id.
    Retry 1 lần nếu lỗi tạm thời. Trả về flash_sale_id hoặc None nếu thất bại."""
    fs_id = await _find_existing_session(shop_code, timeslot_id)
    if fs_id:
        logs.append({"shop": shop_name, "action": "reuse_session", "status": "OK",
                     "message": f"FS#{fs_id} (timeslot={timeslot_id})"})
        return fs_id

    last_err = "no response"
    for attempt in range(2):
        cr = await shopee_client.call(
            shop_code,
            "shop_flash_sale.create_shop_flash_sale",
            body={"timeslot_id": timeslot_id},
        )
        if isinstance(cr, dict):
            new_id = cr.get("flash_sale_id")
            if new_id:
                logs.append({"shop": shop_name, "action": "create_session", "status": "OK",
                             "message": f"FS#{new_id} (timeslot={timeslot_id})"})
                return int(new_id)
            last_err = cr.get("message") or cr.get("error") or str(cr)
        if attempt == 0 and _is_transient(last_err):
            continue  # retry 1 lần
        break

    logs.append({"shop": shop_name, "action": "create_session", "status": "FAIL",
                 "message": f"timeslot={timeslot_id} | {last_err}"})
    return None


# ────────────────────────────────────────────────────────────────
# PER-SHOP PLAN
# ────────────────────────────────────────────────────────────────

async def _process_shop_plan(
    shop_code: str,
    shop_name: str,
    ts_start: int,
    ts_end:   int,
    rows: list,
    logs: list,
) -> tuple[list, list, list]:
    """Xử lý 1 shop: lấy slots → phân bổ rows → tạo sessions → add items → enable.
    Trả về (selected_rows, skipped_rows, sessions_created).
    """
    selected:          list[dict] = []
    skipped:           list[dict] = []
    sessions_created:  list[dict] = []

    now = int(_time.time())

    # Lấy timeslots cho ngày target
    slots_resp = await shopee_client.call(
        shop_code,
        "shop_flash_sale.get_time_slot_id",
        extra_params={
            "start_time": max(now + 60, ts_start),
            "end_time":   ts_end,
        },
    )
    all_slots = _extract_time_slots(slots_resp)
    slots_on_date = [
        s for s in all_slots
        if isinstance(s, dict) and ts_start <= s.get("start_time", 0) <= ts_end
    ]

    if not slots_on_date:
        reason = "khong co khung gio Flash Sale trong ngay " + _ts_to_date_str(ts_start)
        for r in rows:
            skipped.append(_make_skip(r["row_index"], shop_name, r["item_id"], r.get("model_id", 0), reason))
            logs.append({"shop": shop_name, "item_id": r["item_id"], "model_id": r.get("model_id", 0),
                         "action": "get_time_slot_id", "status": "SKIP", "message": reason})
        return selected, skipped, sessions_created

    # Group rows theo item_id — mỗi item mang theo tất cả biến thể (models).
    # Sort theo sales_velocity cao nhất của item (lấy max giữa các biến thể).
    item_groups: dict[int, list] = {}
    item_velocity: dict[int, int] = {}
    for r in rows:
        iid = r["item_id"]
        if iid not in item_groups:
            item_groups[iid] = []
            item_velocity[iid] = 0
        item_groups[iid].append(r)
        item_velocity[iid] = max(item_velocity[iid], r.get("sales_velocity", 0))

    sorted_item_ids = sorted(item_groups.keys(), key=lambda iid: item_velocity[iid], reverse=True)

    # Phân bổ ITEMS_PER_SESSION sản phẩm (item_id) mỗi slot — không phải rows/biến thể
    pending_ids = list(sorted_item_ids)
    for slot in slots_on_date:
        if not pending_ids:
            break

        batch_ids   = pending_ids[:ITEMS_PER_SESSION]
        pending_ids = pending_ids[ITEMS_PER_SESSION:]

        # Gom tất cả rows (biến thể) của các item trong batch
        batch_rows = []
        for iid in batch_ids:
            batch_rows.extend(item_groups[iid])

        timeslot_id = slot["timeslot_id"]
        slot_date   = _ts_to_date_str(slot["start_time"])
        slot_time   = _ts_to_time_str(slot["start_time"])

        fs_id = await _get_or_create_session(shop_code, shop_name, timeslot_id, logs)
        if not fs_id:
            for r in batch_rows:
                logs.append({"shop": shop_name, "item_id": r["item_id"], "model_id": r.get("model_id", 0),
                             "action": "create_session", "status": "FAIL",
                             "message": f"khung {slot_time} {slot_date} | tao phien that bai"})
                skipped.append(_make_skip(r["row_index"], shop_name, r["item_id"], r.get("model_id", 0),
                                          f"tao phien {slot_date} {slot_time} that bai"))
            continue

        sessions_created.append({
            "shop":          shop_name,
            "flash_sale_id": fs_id,
            "timeslot_id":   timeslot_id,
            "slot_date":     slot_date,
            "slot_time":     slot_time,
        })

        # Thêm SP vào phiên
        items_payload = _build_items_payload(batch_rows)
        # Gọi add_items, retry 1 lần nếu exception tạm thời
        add_resp = None
        add_exc: Exception | None = None
        for attempt in range(2):
            try:
                add_resp = await shopee_client.call(
                    shop_code,
                    "shop_flash_sale.add_shop_flash_sale_items",
                    body={"flash_sale_id": fs_id, "items": items_payload},
                )
                add_exc = None
                break
            except Exception as exc:
                add_exc = exc
                if attempt == 0 and _is_transient(str(exc)):
                    continue  # retry 1 lần
                break

        if add_exc is not None:
            err = str(add_exc)
            for r in batch_rows:
                logs.append({"shop": shop_name, "item_id": r["item_id"], "model_id": r.get("model_id", 0),
                             "action": "add_item", "status": "FAIL", "message": f"FS#{fs_id} | {err}"})
                skipped.append(_make_skip(r["row_index"], shop_name, r["item_id"], r.get("model_id", 0), err))
            continue

        failed_items: list = []
        if isinstance(add_resp, dict):
            failed_items = add_resp.get("failed_items") or []

        # Retry 1 lần cho các item bị lỗi tạm thời
        transient_rows = []
        for f in failed_items:
            err = f.get("err_msg") or f.get("unqualified_reason") or f"err_code:{f.get('err_code', '?')}"
            if _is_transient(err):
                key = f"{f['item_id']}|{f.get('model_id') or 0}"
                for r in batch_rows:
                    if f"{r['item_id']}|{r.get('model_id', 0) or 0}" == key:
                        transient_rows.append(r)

        if transient_rows:
            retry_payload = _build_items_payload(transient_rows)
            retry_resp = await shopee_client.call(
                shop_code,
                "shop_flash_sale.add_shop_flash_sale_items",
                body={"flash_sale_id": fs_id, "items": retry_payload},
            )
            if isinstance(retry_resp, dict):
                transient_keys = {f"{r['item_id']}|{r.get('model_id', 0) or 0}" for r in transient_rows}
                failed_items = [f for f in failed_items
                                if f"{f['item_id']}|{f.get('model_id') or 0}" not in transient_keys]
                failed_items.extend(retry_resp.get("failed_items") or [])

        failed_map = _build_failed_map(failed_items)

        # Enable phiên (status=1)
        await shopee_client.call(
            shop_code,
            "shop_flash_sale.update_shop_flash_sale",
            body={"flash_sale_id": fs_id, "status": 1},
        )

        # Đếm tổng models thực tế trong payload
        total_models = sum(len(it.get("models", [])) or 1 for it in items_payload)
        failed_model_count = len(failed_items)

        # Tóm tắt lý do thất bại từ Shopee để dễ chẩn đoán
        fail_summary = ""
        if failed_items:
            reasons: dict[str, int] = {}
            for fi in failed_items:
                r_msg = (fi.get("err_msg") or fi.get("unqualified_reason")
                         or f"err_code:{fi.get('err_code', '?')}")
                reasons[r_msg] = reasons.get(r_msg, 0) + 1
            fail_summary = " | " + "; ".join(f"{cnt}x '{msg}'" for msg, cnt in reasons.items())
        logs.append({
            "shop":    shop_name,
            "action":  "add_items",
            "status":  "OK" if not failed_items else "PARTIAL",
            "message": (
                f"FS#{fs_id} {slot_date} {slot_time} | "
                f"items={len(batch_ids)} models={total_models} "
                f"ok={total_models - failed_model_count} failed={failed_model_count}{fail_summary}"
            ),
        })

        # Phân loại kết quả từng row.
        # Item bị Shopee reject → chỉ log, KHÔNG ghi vào skipped_rows
        # (cell sheet giữ trống → tự retry lần sau).
        for r in batch_rows:
            item_id  = r["item_id"]
            model_id = r.get("model_id", 0)
            key      = f"{item_id}|{model_id or 0}"
            if key in failed_map:
                f   = failed_map[key]
                err = (f.get("err_msg") or f.get("unqualified_reason")
                       or f"err_code:{f.get('err_code', '?')}")
                # Đã retry rồi → mọi failed đều ghi FAIL vào sheet
                logs.append({
                    "shop":     shop_name,
                    "item_id":  item_id,
                    "model_id": model_id or 0,
                    "action":   "add_item",
                    "status":   "FAIL",
                    "message":  f"FS#{fs_id} | {err}",
                })
                skipped.append({
                    "row_index": r["row_index"], "shop": shop_name,
                    "item_id":   item_id,        "model_id": model_id or 0,
                    "status":    "SKIP",         "reason":   err,
                })
            else:
                selected.append({
                    "row_index":     r["row_index"], "shop":      shop_name,
                    "item_id":       item_id,        "model_id":  model_id or 0,
                    "flash_sale_id": fs_id,          "slot_date": slot_date,
                    "slot_time":     slot_time,      "status":    "OK",
                    "message":       f"FS#{fs_id}",
                })

    # Items còn thừa (hết slot)
    cap    = len(slots_on_date) * ITEMS_PER_SESSION
    reason = f"het phien trong ngay (toi da {cap} SP cho {len(slots_on_date)} khung gio)"
    for iid in pending_ids:
        for r in item_groups[iid]:
            skipped.append(_make_skip(r["row_index"], shop_name, r["item_id"], r.get("model_id", 0), reason))
            logs.append({"shop": shop_name, "item_id": r["item_id"], "model_id": r.get("model_id", 0),
                         "action": "het_slot", "status": "SKIP", "message": reason})

    return selected, skipped, sessions_created


# ────────────────────────────────────────────────────────────────
# PER-SHOP DELETE
# ────────────────────────────────────────────────────────────────

async def _delete_shop_sessions(
    shop_code: str,
    shop_name: str,
    ts_start:  int,
    ts_end:    int,
    logs: list,
) -> tuple[list, list]:
    """Xoá tất cả phiên FS của shop trong [ts_start, ts_end].
    Trả về (deleted_sessions, failed_sessions).
    """
    deleted: list[dict] = []
    failed:  list[dict] = []

    # Lấy danh sách phiên (type 1=upcoming, 2=ongoing, 0=tất cả)
    all_sessions: list[dict] = []
    for fs_type in [1, 2]:
        offset = 0
        while True:
            list_resp = await shopee_client.call(
                shop_code,
                "shop_flash_sale.get_shop_flash_sale_list",
                extra_params={"type": fs_type, "offset": offset, "limit": 100},
            )
            page = _extract_flash_sale_list(list_resp)
            if not page:
                break
            all_sessions.extend([s for s in page if isinstance(s, dict)])
            if len(page) < 100:
                break
            offset += 100
            if offset > 1000:
                break

    # Lọc trong ngày target
    target_sessions = [
        fs for fs in all_sessions
        if ts_start <= fs.get("start_time", 0) <= ts_end
    ]

    if not target_sessions:
        logs.append({"shop": shop_name, "action": "delete_sessions", "status": "OK",
                     "message": f"khong co phien Flash Sale trong ngay {_ts_to_date_str(ts_start)}"})
        return deleted, failed

    for fs in target_sessions:
        fs_id      = fs.get("flash_sale_id")
        start_time = fs.get("start_time", 0)
        if not fs_id:
            continue

        slot_date = _ts_to_date_str(start_time)
        slot_time = _ts_to_time_str(start_time)

        # Disable trước
        await shopee_client.call(
            shop_code,
            "shop_flash_sale.update_shop_flash_sale",
            body={"flash_sale_id": fs_id, "status": 2},
        )

        # Delete
        del_resp = await shopee_client.call(
            shop_code,
            "shop_flash_sale.delete_shop_flash_sale",
            body={"flash_sale_id": fs_id},
        )

        # Kiểm tra lỗi
        is_err = False
        if isinstance(del_resp, dict):
            # Shopee trả error_code != 0 khi lỗi
            err_code = del_resp.get("error_code") or del_resp.get("error")
            if err_code and err_code not in [0, None, ""]:
                is_err = True
                err_msg = del_resp.get("message") or del_resp.get("msg") or str(err_code)
                failed.append({"shop": shop_name, "flash_sale_id": fs_id,
                               "slot_date": slot_date, "slot_time": slot_time, "error": str(err_msg)})
                logs.append({"shop": shop_name, "action": "delete_session", "status": "FAIL",
                             "message": f"FS#{fs_id} {slot_date} {slot_time} | {err_msg}"})

        if not is_err:
            deleted.append({"shop": shop_name, "flash_sale_id": fs_id,
                            "slot_date": slot_date, "slot_time": slot_time})
            logs.append({"shop": shop_name, "action": "delete_session", "status": "OK",
                         "message": f"FS#{fs_id} {slot_date} {slot_time}"})

    return deleted, failed


# ────────────────────────────────────────────────────────────────
# REGISTER TOOLS
# ────────────────────────────────────────────────────────────────

def register_plan_tools(mcp):

    @mcp.tool()
    async def plan_flash_sale(target_date: str, shops: list[dict], rows: list[dict]) -> dict:
        """Lên kế hoạch và thực thi Flash Sale nhiều shop cho một ngày.

        Args:
          target_date: Ngày cần tạo Flash Sale, định dạng 'DD-MM-YYYY' (vd: '05-04-2026').
          shops: Danh sách shop cần xử lý.
                 [{shop_code: str, shop_name: str}]
          rows: Danh sách SP từ sheet. Mỗi row là một model/variant riêng.
                [{row_index: int,        # số dòng sheet (1-based)
                  shop: str,             # tên shop khớp với shops[].shop_name
                  item_id: int,
                  model_id: int,         # 0 nếu SP không có biến thể
                  item_name: str,
                  model_name: str,
                  stock: int,
                  sales_velocity: int,   # dùng để sort ưu tiên
                  fs_price: float,       # giá Flash Sale (không thuế)
                  limit: int}]           # giới hạn mua/khách, 0=không giới hạn

        Logic:
          - Xử lý tất cả shops song song (asyncio.gather).
          - Mỗi shop: lấy timeslots → sort SP theo sales_velocity giảm dần
            → dedupe (item_id, model_id) → nhóm ITEMS_PER_SESSION SP/slot
            → tạo/tìm phiên → add items → enable.

        Returns:
          {selected_rows: [...], skipped_rows: [...], sessions_created: [...], logs: [...]}
          selected_rows[]: {row_index, shop, item_id, model_id, flash_sale_id, slot_date, slot_time, status="OK", message}
          skipped_rows[]:  {row_index, shop, item_id, model_id, status="SKIP", reason}
        """
        try:
            ts_start, ts_end = _parse_target_date(target_date)
        except Exception as exc:
            return {"error": f"target_date sai dinh dang (can DD-MM-YYYY): {exc}"}

        # Gom rows theo shop
        rows_by_shop: dict[str, list] = {}
        for r in rows:
            shop = r.get("shop", "")
            rows_by_shop.setdefault(shop, []).append(r)

        all_selected:  list[dict] = []
        all_skipped:   list[dict] = []
        all_sessions:  list[dict] = []
        logs:          list[dict] = []

        # Xây task list chỉ với shop có rows
        tasks = [
            (s.get("shop_code", ""), s.get("shop_name", ""), rows_by_shop.get(s.get("shop_name", ""), []))
            for s in shops
            if s.get("shop_code") and rows_by_shop.get(s.get("shop_name", ""))
        ]

        if not tasks:
            return {"selected_rows": [], "skipped_rows": [], "sessions_created": [], "logs": logs}

        results = await asyncio.gather(
            *[_process_shop_plan(sc, sn, ts_start, ts_end, sr, logs) for sc, sn, sr in tasks],
            return_exceptions=True,
        )

        for i, res in enumerate(results):
            sc, sn, shop_rows = tasks[i]
            if isinstance(res, Exception):
                logger.error("plan_flash_sale | shop=%s | shop_code=%s | %s", sn, sc, res)
                # Lỗi exception (server error...) → chỉ log, không ghi FAIL vào sheet → retry lần sau
                logs.append({"shop": sn, "action": "plan_flash_sale", "status": "ERROR",
                             "message": f"shop_code={sc!r} | {res}"})
            else:
                sel, skip, sess = res
                all_selected.extend(sel)
                all_skipped.extend(skip)
                all_sessions.extend(sess)

        return {
            "selected_rows":    all_selected,
            "skipped_rows":     all_skipped,
            "sessions_created": all_sessions,
            "logs":             logs,
        }

    @mcp.tool()
    async def delete_flash_sale_by_date(target_date: str, shops: list[dict]) -> dict:
        """Xoá tất cả phiên Flash Sale của các shop trong ngày target_date.

        Args:
          target_date: Ngày cần xoá, định dạng 'DD-MM-YYYY' (vd: '05-04-2026').
          shops: [{shop_code: str, shop_name: str}]

        Logic:
          - Lấy danh sách phiên của từng shop (type 1+2) trong ngày target.
          - Với mỗi phiên: update_shop_flash_sale(status=2) → delete_shop_flash_sale.
          - Xử lý song song tất cả shops.

        Returns:
          {deleted_sessions: [...], failed_sessions: [...], logs: [...]}
          deleted_sessions[]: {shop, flash_sale_id, slot_date, slot_time}
          failed_sessions[]:  {shop, flash_sale_id, slot_date, slot_time, error}
        """
        try:
            ts_start, ts_end = _parse_target_date(target_date)
        except Exception as exc:
            return {"error": f"target_date sai dinh dang (can DD-MM-YYYY): {exc}"}

        logs: list[dict] = []

        tasks = [
            (s.get("shop_code", ""), s.get("shop_name", ""))
            for s in shops
            if s.get("shop_code")
        ]

        if not tasks:
            return {"deleted_sessions": [], "failed_sessions": [], "logs": logs}

        results = await asyncio.gather(
            *[_delete_shop_sessions(sc, sn, ts_start, ts_end, logs) for sc, sn in tasks],
            return_exceptions=True,
        )

        all_deleted: list[dict] = []
        all_failed:  list[dict] = []

        for i, res in enumerate(results):
            sc, sn = tasks[i]
            if isinstance(res, Exception):
                logger.error("delete_flash_sale_by_date | shop=%s | shop_code=%s | %s", sn, sc, res)
                logs.append({"shop": sn, "action": "delete_flash_sale_by_date",
                             "status": "ERROR", "message": f"shop_code={sc!r} | {res}"})
                all_failed.append({"shop": sn, "flash_sale_id": None, "error": f"shop_code={sc!r} | {res}"})
            else:
                deleted, failed = res
                all_deleted.extend(deleted)
                all_failed.extend(failed)

        return {
            "deleted_sessions": all_deleted,
            "failed_sessions":  all_failed,
            "logs":             logs,
        }

"""Test plan_flash_sale + delete_flash_sale_by_date flow.

Usage:
    # Terminal 1: start MCP server
    python -m app.main

    # Terminal 2: run test
    python scripts/test_plan_flow.py "C:\\path\\to\\exported_sheet.xlsx"
    python scripts/test_plan_flow.py "C:\\path\\to\\exported_sheet.xlsx" --date 05-04-2026
"""
import sys, io, os, json, re, math, time, httpx
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Config ──────────────────────────────────────────────────────
MCP_BASE = "http://localhost:8000/mcp"
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
TZ = timezone(timedelta(hours=7))
DEFAULT_DATE = "03-04-2026"

# Column indices — giống Apps Script COL
COL_SHOP = 0            # A
COL_ITEM_NAME = 2       # C
COL_MODEL_NAME = 5      # F
COL_LIMIT = 9           # J
COL_STOCK = 11          # L
COL_SALES_VELOCITY = 12 # M
COL_ITEM_ID = 13        # N
COL_MODEL_ID = 14       # O
COL_FS_PRICE = 15       # P

SHOPS_JSON = Path(__file__).resolve().parent.parent / "data" / "shops.json"

# ── Helpers ─────────────────────────────────────────────────────

def to_int(v):
    """Giống Apps Script toInt_: trả int hoặc None."""
    if v is None or v == "":
        return None
    v = str(v).strip().strip('"')
    # Xử lý scientific notation kiểu "2,33019E+11" (dấu phẩy thập phân)
    v = v.replace(",", ".")
    try:
        n = float(v)
        if math.isnan(n):
            return None
        return int(n)
    except (ValueError, OverflowError):
        return None


def to_price(v):
    if v is None or v == "":
        return None
    v = str(v).strip().strip('"').replace(",", ".")
    try:
        n = float(v)
        return None if math.isnan(n) else n
    except (ValueError, OverflowError):
        return None


def is_dc_shop(name):
    return str(name or "").strip().upper().startswith("ĐC")


def min_stock_required(name):
    return 2 if is_dc_shop(name) else 3


def normalize_shop_name(name):
    """Giống Apps Script normalizeShopName_."""
    import unicodedata
    s = re.sub(r"\s*[-–]?\s*\d{6,}\s*$", "", str(name or "")).strip()
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u0300-\u036f]", "", s)
    s = s.replace("đ", "d")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def extract_shop_id(name):
    parts = re.split(r"[-–\s]+", str(name))
    for p in reversed(parts):
        p = p.strip()
        if re.match(r"^\d{6,}$", p):
            return p
    return None


# ── Parse sheet data ────────────────────────────────────────────

def read_tsv_file(path):
    """Đọc file tab-separated (có thể .xlsx nhưng thực tế là text)."""
    raw = Path(path).read_bytes()
    # Detect encoding
    for enc in ["utf-8-sig", "utf-8", "cp1258", "latin-1"]:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")

    lines = text.splitlines()
    if not lines:
        return [], []
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        rows.append(line.split("\t"))
    return header, rows


def parse_sheet_data(file_path):
    """Parse file → eligible rows + shop set, giống runCreateFS logic."""
    header, raw_rows = read_tsv_file(file_path)
    print(f"  File: {file_path}")
    print(f"  Header cols: {len(header)}, Data rows: {len(raw_rows)}")

    seen_keys = set()
    eligible = []

    for i, cols in enumerate(raw_rows):
        # Pad cols nếu thiếu
        while len(cols) <= COL_FS_PRICE:
            cols.append("")

        shop_name = str(cols[COL_SHOP] or "").strip()
        if not shop_name:
            continue

        item_id = to_int(cols[COL_ITEM_ID])
        if item_id is None:
            continue

        fs_price = to_price(cols[COL_FS_PRICE])
        if fs_price is None or fs_price <= 0:
            continue

        stock = to_int(cols[COL_STOCK])
        min_stk = min_stock_required(shop_name)
        if stock is None or stock < min_stk:
            continue

        model_id = to_int(cols[COL_MODEL_ID]) or 0

        # Dedupe
        key = f"{shop_name}|{item_id}|{model_id}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        sales_velocity = to_int(cols[COL_SALES_VELOCITY]) or 0
        limit_val = to_int(cols[COL_LIMIT]) or 0

        eligible.append({
            "row_index": i + 2,  # 1-based, header = row 1
            "shop": shop_name,
            "item_id": item_id,
            "model_id": model_id,
            "item_name": str(cols[COL_ITEM_NAME] or ""),
            "model_name": str(cols[COL_MODEL_NAME] or ""),
            "stock": stock,
            "sales_velocity": sales_velocity,
            "fs_price": fs_price,
            "limit": limit_val,
        })

    # Sort by sales_velocity desc
    eligible.sort(key=lambda e: e["sales_velocity"], reverse=True)
    return eligible


# ── Resolve shops ───────────────────────────────────────────────

def load_shop_registry():
    """Đọc data/shops.json → build lookup giống Apps Script."""
    with open(SHOPS_JSON, encoding="utf-8") as f:
        shops = json.load(f)
    by_name = {}
    by_lower = {}
    by_id = {}
    by_norm = {}
    for s in shops:
        if not s.get("code") or not s.get("is_active"):
            continue
        info = {"shop_code": s["code"], "shop_name": s["shop_name"], "shop_id": s.get("shop_id")}
        name = str(s.get("shop_name", "")).strip()
        if name:
            by_name[name] = info
            by_lower[name.lower()] = info
            norm = normalize_shop_name(name)
            if norm:
                by_norm[norm] = info
        sid = s.get("shop_id")
        if sid is not None and sid != "":
            by_id[str(sid)] = info
    return {"by_name": by_name, "by_lower": by_lower, "by_id": by_id, "by_norm": by_norm}


def resolve_shop(shop_name, registry):
    """Giống Apps Script resolveShopInfo_."""
    raw = str(shop_name or "").strip()
    if not raw:
        return None
    if raw in registry["by_name"]:
        return registry["by_name"][raw]
    lower = raw.lower()
    if lower in registry["by_lower"]:
        return registry["by_lower"][lower]
    sid = extract_shop_id(raw)
    if sid and sid in registry["by_id"]:
        return registry["by_id"][sid]
    norm = normalize_shop_name(raw)
    if norm and norm in registry["by_norm"]:
        return registry["by_norm"][norm]
    # Strip shop id suffix and retry
    no_id = re.sub(r"\s*[-–]?\s*\d{6,}\s*$", "", raw).strip()
    norm_no_id = normalize_shop_name(no_id)
    if norm_no_id and norm_no_id in registry["by_norm"]:
        return registry["by_norm"][norm_no_id]
    return None


# ── MCP client ──────────────────────────────────────────────────

class MCPClient:
    def __init__(self, base_url=MCP_BASE):
        self.base = base_url
        self.sid = None

    def _call(self, method, params=None):
        h = dict(MCP_HEADERS)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
        with httpx.stream("POST", self.base, json=body, headers=h, timeout=120) as resp:
            self.sid = resp.headers.get("mcp-session-id", self.sid)
            results = []
            for line in resp.iter_lines():
                if line.strip().startswith("data: "):
                    try:
                        results.append(json.loads(line.strip()[6:]))
                    except json.JSONDecodeError:
                        pass
            return results

    def init(self):
        self._call("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test_plan_flow", "version": "1"},
        })
        h = dict(MCP_HEADERS)
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        httpx.post(self.base, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=h)

    def tool(self, name, args):
        results = self._call("tools/call", {"name": name, "arguments": args})
        for item in results:
            if "result" in item:
                for c in item["result"].get("content", []):
                    if c.get("type") == "text":
                        try:
                            return json.loads(c["text"])
                        except json.JSONDecodeError:
                            return c["text"]
            if "error" in item:
                return {"__mcp_error__": item["error"]}
        return None


# ── Validation ──────────────────────────────────────────────────

def validate_create_result(result, eligible_rows):
    """Validate plan_flash_sale response."""
    errors = []

    if not isinstance(result, dict):
        errors.append(f"Response is not dict: {str(result)[:200]}")
        return errors

    if "error" in result:
        errors.append(f"Tool error: {result['error']}")
        return errors

    selected = result.get("selected_rows", [])
    skipped = result.get("skipped_rows", [])
    sessions = result.get("sessions_created", [])
    logs = result.get("logs", [])

    total_input = len(eligible_rows)
    total_output = len(selected) + len(skipped)

    print(f"\n  --- CREATE RESULTS ---")
    print(f"  Input rows:      {total_input}")
    print(f"  Selected (OK):   {len(selected)}")
    print(f"  Skipped (FAIL):  {len(skipped)}")
    print(f"  Sessions:        {len(sessions)}")

    # Kiểm tra tổng output = input
    if total_output != total_input:
        errors.append(f"Output mismatch: input={total_input} but selected+skipped={total_output}")

    # Kiểm tra "already exist"
    already_exist = [s for s in skipped if "already exist" in str(s.get("reason", "")).lower()]
    if already_exist:
        errors.append(f"{len(already_exist)} models bi 'already exist':")
        for ae in already_exist:
            errors.append(f"  item={ae.get('item_id')} model={ae.get('model_id')} | {ae.get('reason')}")

    # Kiểm tra logs — verify items vs models count
    for log in logs:
        msg = log.get("message", "")
        if log.get("action") == "add_items" and "models=" in msg:
            # Parse: "FS#xxx date time | items=N models=M ok=X failed=Y"
            m_items = re.search(r"items=(\d+)", msg)
            m_models = re.search(r"models=(\d+)", msg)
            if m_items and m_models:
                items_n = int(m_items.group(1))
                models_n = int(m_models.group(1))
                if models_n < items_n:
                    errors.append(f"Log error: models({models_n}) < items({items_n}) — {msg}")

    # Kiểm tra FAIL logs
    fail_logs = [l for l in logs if l.get("status") == "FAIL"]
    if fail_logs:
        print(f"  FAIL logs:       {len(fail_logs)}")
        for fl in fail_logs:
            print(f"    [{fl.get('action')}] {fl.get('shop', '')} | {fl.get('message', '')}")

    # Print sessions
    for s in sessions:
        print(f"  Session: FS#{s.get('flash_sale_id')} | {s.get('slot_date')} {s.get('slot_time')} | {s.get('shop')}")

    # Print logs summary
    print(f"\n  --- LOGS ({len(logs)}) ---")
    for log in logs:
        status_icon = {"OK": "+", "PARTIAL": "~", "FAIL": "!", "SKIP": "-", "ERROR": "X"}.get(log.get("status"), "?")
        print(f"  [{status_icon}] {log.get('shop', ''):20s} | {log.get('action', ''):20s} | {log.get('message', '')}")

    return errors


def validate_delete_result(result, sessions_created):
    """Validate delete_flash_sale_by_date response."""
    errors = []

    if not isinstance(result, dict):
        errors.append(f"Delete response is not dict: {str(result)[:200]}")
        return errors

    if "error" in result:
        errors.append(f"Delete tool error: {result['error']}")
        return errors

    deleted = result.get("deleted_sessions", [])
    failed = result.get("failed_sessions", [])
    logs = result.get("logs", [])

    print(f"\n  --- DELETE RESULTS ---")
    print(f"  Deleted:  {len(deleted)}")
    print(f"  Failed:   {len(failed)}")

    if failed:
        errors.append(f"{len(failed)} sessions xoa that bai:")
        for f in failed:
            errors.append(f"  FS#{f.get('flash_sale_id')} | {f.get('error')}")

    # Kiểm tra mỗi session đã tạo đều được xoá
    created_ids = {s.get("flash_sale_id") for s in sessions_created}
    deleted_ids = {d.get("flash_sale_id") for d in deleted}
    missing = created_ids - deleted_ids
    if missing:
        errors.append(f"Sessions chua duoc xoa: {missing}")

    for log in logs:
        status_icon = {"OK": "+", "FAIL": "!", "ERROR": "X"}.get(log.get("status"), "?")
        print(f"  [{status_icon}] {log.get('shop', ''):20s} | {log.get('action', ''):20s} | {log.get('message', '')}")

    return errors


# ── Main ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_plan_flow.py <file_path> [--date DD-MM-YYYY]")
        sys.exit(1)

    file_path = sys.argv[1]
    target_date = DEFAULT_DATE
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            target_date = sys.argv[idx + 1]

    print("=" * 70)
    print(f"TEST PLAN FLOW | Date: {target_date} | {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')}")
    print("=" * 70)

    # 1. Parse file
    print(f"\n[1] PARSE FILE")
    eligible = parse_sheet_data(file_path)
    if not eligible:
        print("  KHONG CO ROW NAO DU DIEU KIEN")
        sys.exit(1)

    # Collect unique shops
    shop_names = list(dict.fromkeys(e["shop"] for e in eligible))
    print(f"  Eligible rows:  {len(eligible)}")
    print(f"  Unique shops:   {len(shop_names)}")
    for sn in shop_names:
        cnt = sum(1 for e in eligible if e["shop"] == sn)
        print(f"    {sn}: {cnt} rows")

    # 2. Resolve shops
    print(f"\n[2] RESOLVE SHOPS")
    registry = load_shop_registry()
    shops_arr = []
    resolved = {}  # shop_name → info
    for sn in shop_names:
        info = resolve_shop(sn, registry)
        if info:
            resolved[sn] = info
            shops_arr.append(info)
            print(f"  {sn:40s} -> {info['shop_name']} (code={info['shop_code'][:12]}...)")
        else:
            print(f"  {sn:40s} -> !! KHONG TIM THAY")

    # Filter eligible to only resolved shops, remap shop name to registry name
    rows_for_mcp = []
    for e in eligible:
        if e["shop"] not in resolved:
            continue
        row = dict(e)
        row["shop"] = resolved[e["shop"]]["shop_name"]
        rows_for_mcp.append(row)

    if not rows_for_mcp:
        print("  KHONG CO SHOP NAO RESOLVE DUOC")
        sys.exit(1)

    print(f"  Rows after resolve: {len(rows_for_mcp)}")

    # 3. Connect MCP
    print(f"\n[3] CONNECT MCP")
    mcp = MCPClient()
    try:
        mcp.init()
        print(f"  Connected (session={mcp.sid})")
    except Exception as ex:
        print(f"  !! KHONG KET NOI DUOC MCP: {ex}")
        print(f"  Dam bao server dang chay: python -m app.main")
        sys.exit(1)

    all_errors = []

    # 4. Test plan_flash_sale (CREATE)
    print(f"\n[4] CALL plan_flash_sale (date={target_date}, {len(shops_arr)} shops, {len(rows_for_mcp)} rows)")
    t0 = time.time()
    create_result = mcp.tool("plan_flash_sale", {
        "target_date": target_date,
        "shops": shops_arr,
        "rows": rows_for_mcp,
    })
    elapsed = time.time() - t0
    print(f"  Thoi gian: {elapsed:.1f}s")

    create_errors = validate_create_result(create_result, rows_for_mcp)
    all_errors.extend(create_errors)

    sessions_created = create_result.get("sessions_created", []) if isinstance(create_result, dict) else []

    # 5. Test delete_flash_sale_by_date (DELETE)
    print(f"\n[5] CALL delete_flash_sale_by_date (date={target_date})")
    t0 = time.time()
    delete_result = mcp.tool("delete_flash_sale_by_date", {
        "target_date": target_date,
        "shops": shops_arr,
    })
    elapsed = time.time() - t0
    print(f"  Thoi gian: {elapsed:.1f}s")

    delete_errors = validate_delete_result(delete_result, sessions_created)
    all_errors.extend(delete_errors)

    # 6. Report
    print(f"\n{'=' * 70}")
    if all_errors:
        print(f"FAIL — {len(all_errors)} loi:")
        for err in all_errors:
            print(f"  !! {err}")
    else:
        print("PASS — Tao + Xoa thanh cong, khong co loi")
    print("=" * 70)

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()

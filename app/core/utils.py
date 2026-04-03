import re
import time


def now_ts() -> int:
    return int(time.time())


def to_float(v) -> float:
    """Chuyển giá trị bất kỳ sang float. Xử lý dấu phẩy, %, khoảng trắng."""
    try:
        return float(str(v).replace(",", "").replace("%", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def to_int_safe(v) -> int | None:
    """Chuyển sang int, trả None nếu không hợp lệ."""
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def resolve_shops(shop_registry_service, shop_codes: str = "all") -> list[dict]:
    """Resolve 'all' hoặc 'shop1,shop2' thành danh sách shop dicts.
    Dùng chung cho batch_tools, workflow_tools, flash_sale_tools."""
    all_shops = shop_registry_service.list_shops()
    if not shop_codes or shop_codes.strip().lower() == "all":
        return [s for s in all_shops if s.get("is_active", True)]
    codes = [c.strip() for c in shop_codes.split(",") if c.strip()]
    return [s for s in all_shops if s.get("code") in codes]


def extract_shop_id(shop_name: str) -> str | None:
    """Trích xuất shop_id từ tên shop dạng 'TB - Shopee - TenShop - 847753176'."""
    parts = shop_name.strip().rsplit("-", 1)
    if len(parts) == 2:
        candidate = parts[1].strip()
        if candidate.isdigit():
            return candidate
    m = re.search(r"(\d{6,})", shop_name)
    return m.group(1) if m else None


def find_shop_code(shop_id: str, shops: list[dict]) -> str | None:
    """Tìm shop_code từ shop_id trong danh sách shops."""
    for s in shops:
        if str(s.get("shop_id")) == str(shop_id):
            return s.get("code")
    return None

"""Chuẩn hóa response format cho tất cả MCP tools."""
from typing import Any


def ok(data: dict | None = None, **kwargs) -> dict:
    """Response thành công. Dùng: return ok(items=items, total=10)"""
    result = {"ok": True}
    if data:
        result.update(data)
    result.update(kwargs)
    return result


def err(error: str, **kwargs) -> dict:
    """Response lỗi. Dùng: return err("Shop không tồn tại", shop_code=code)"""
    result = {"ok": False, "error": error}
    result.update(kwargs)
    return result

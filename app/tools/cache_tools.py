"""Cache tools — AI Agent quản lý cache qua MCP."""
from app.dependencies import cache_service


def register_cache_tools(mcp):

    @mcp.tool()
    def cache_status() -> dict:
        """Xem tổng quan cache: namespaces, số entry, hit rate, dung lượng."""
        return {
            "namespaces": cache_service.list_namespaces(),
            "stats": cache_service.get_stats(),
        }

    @mcp.tool()
    def cache_list_entries(namespace: str) -> dict:
        """Liệt kê các entry trong 1 namespace (VD: 'item_list', 'order_list', 'shop_info')."""
        entries = cache_service.list_entries(namespace)
        return {
            "namespace": namespace,
            "entries": entries,
            "count": len(entries),
        }

    @mcp.tool()
    def cache_get_entry(namespace: str, key: str) -> dict:
        """Đọc chi tiết 1 cache entry (bao gồm data + metadata). key thường là shop_code."""
        entry = cache_service.get_entry_full(namespace, key)
        if entry is None:
            return {"ok": False, "error": f"Cache miss: {namespace}/{key}"}
        return {"ok": True, "entry": entry}

    @mcp.tool()
    def cache_clear_namespace(namespace: str) -> dict:
        """Xóa toàn bộ cache trong 1 namespace."""
        count = cache_service.clear_namespace(namespace)
        return {"ok": True, "deleted": count, "namespace": namespace}

    @mcp.tool()
    def cache_clear_all() -> dict:
        """Xóa toàn bộ cache. Dùng khi cần refresh data hoàn toàn."""
        count = cache_service.clear_all()
        return {"ok": True, "deleted": count}

    @mcp.tool()
    def cache_cleanup_expired() -> dict:
        """Dọn dẹp các entry đã hết hạn. Giải phóng dung lượng."""
        removed = cache_service.cleanup_expired()
        return {"ok": True, "removed": removed}

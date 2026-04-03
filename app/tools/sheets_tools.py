"""
Google Sheets MCP Tools — đọc/ghi Google Sheets.

Chỉ chứa tools thao tác trực tiếp với Google Sheets API.
Logic xử lý/phân tích data thuộc về Apps Script hoặc client.
"""

from app.dependencies import sheets_service
from app.core.logger import get_logger

logger = get_logger(__name__)


def register_sheets_tools(mcp):

    # ── Meta / Discovery ──────────────────────────────────────────────

    @mcp.tool()
    async def sheets_info(spreadsheet_id: str) -> dict:
        """Lấy thông tin spreadsheet: danh sách tabs, phân loại summary vs raw data.
        Gọi tool này ĐẦU TIÊN để biết nên đọc tab nào, tránh đọc raw data khổng lồ.

        Trả về:
        - summary_tabs: tabs ít dòng → nên đọc (dashboard, tổng hợp)
        - raw_tabs:     tabs nhiều dòng → KHÔNG nên đọc toàn bộ, dùng sheets_search thay thế
        """
        if not sheets_service.is_configured():
            return {
                "ok": False,
                "error": "Google Sheets chưa cấu hình. Set GOOGLE_SERVICE_ACCOUNT_FILE hoặc GOOGLE_SERVICE_ACCOUNT_JSON trong .env",
            }
        try:
            return {"ok": True, **await sheets_service.get_spreadsheet_info(spreadsheet_id)}
        except Exception as e:
            logger.error("sheets_info | %s | %s", spreadsheet_id, e)
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def sheets_named_ranges(spreadsheet_id: str) -> dict:
        """Lấy danh sách named ranges đã đặt tên trong spreadsheet."""
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            return {"ok": True, **await sheets_service.list_named_ranges(spreadsheet_id)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Read ──────────────────────────────────────────────────────────

    @mcp.tool()
    async def sheets_read_range(spreadsheet_id: str, range_notation: str) -> dict:
        """Đọc 1 range cụ thể — cách HIỆU QUẢ NHẤT.

        range_notation:
        - 'Dashboard!A1:H30'   → tọa độ cell
        - 'CAMPAIGN_SUMMARY'   → named range
        - 'Summary'            → toàn bộ tab (cẩn thận nếu tab lớn)
        """
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            return {"ok": True, **await sheets_service.read_range(spreadsheet_id, range_notation)}
        except Exception as e:
            logger.error("sheets_read_range | %s | %s | %s", spreadsheet_id, range_notation, e)
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def sheets_read_tab(
        spreadsheet_id: str, tab_name: str, max_rows: int = 300,
    ) -> dict:
        """Đọc toàn bộ 1 tab (bảo vệ bằng max_rows).
        Nên dùng cho summary/dashboard tabs. Với raw data tabs, dùng sheets_search().
        """
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            result = await sheets_service.read_tab(spreadsheet_id, tab_name, max_rows)
            if result.get("is_likely_raw_data") and result.get("total_rows_in_sheet", 0) > max_rows:
                result["warning"] = (
                    f"Tab '{tab_name}' có {result['total_rows_in_sheet']} dòng — đây có thể là raw data. "
                    f"Chỉ đọc {max_rows} dòng đầu. Dùng sheets_search() để filter."
                )
            return {"ok": True, **result}
        except Exception as e:
            logger.error("sheets_read_tab | %s | %s | %s", spreadsheet_id, tab_name, e)
            return {"ok": False, "error": str(e)}

    # ── Search / Filter ───────────────────────────────────────────────

    @mcp.tool()
    async def sheets_search(
        spreadsheet_id: str, tab_name: str, keyword: str, column: str = "",
    ) -> dict:
        """Tìm kiếm rows trong tab chứa keyword. Trả về chỉ matching rows.

        - keyword: từ khóa (không phân biệt hoa thường)
        - column: giới hạn tìm trong cột cụ thể. Bỏ trống = tìm toàn bộ.
        """
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            return {"ok": True, **await sheets_service.search_tab(
                spreadsheet_id, tab_name, keyword, column
            )}
        except Exception as e:
            logger.error("sheets_search | %s | %s | %s", spreadsheet_id, tab_name, e)
            return {"ok": False, "error": str(e)}

    # ── Write ─────────────────────────────────────────────────────────

    @mcp.tool()
    async def sheets_update_range(
        spreadsheet_id: str, range_notation: str, values: list[list]
    ) -> dict:
        """Cập nhật một vùng dữ liệu trên Google Sheet.

        range_notation: VD 'FS!S2:S100', 'Sheet1!A1:C5'
        values: [["OK"], ["Lỗi"], ["OK"]]  → 3 ô trong 1 cột
        """
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            result = await sheets_service.update_range(spreadsheet_id, range_notation, values)
            return {"ok": True, **result}
        except Exception as e:
            logger.error("sheets_update_range | %s | %s | %s", spreadsheet_id, range_notation, e)
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def sheets_update_cells(
        spreadsheet_id: str, tab_name: str, updates: list[dict]
    ) -> dict:
        """Cập nhật từng ô riêng lẻ. updates: [{"cell": "S2", "value": "OK"}, ...]"""
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            if len(updates) > 10:
                result = await sheets_service.batch_update_cells(spreadsheet_id, tab_name, updates)
            else:
                result = await sheets_service.update_cells(spreadsheet_id, tab_name, updates)
            return {"ok": True, **result}
        except Exception as e:
            logger.error("sheets_update_cells | %s | %s | %s", spreadsheet_id, tab_name, e)
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def sheets_append_rows(
        spreadsheet_id: str, tab_name: str, rows: list[list]
    ) -> dict:
        """Thêm dòng mới vào cuối tab. rows: [["Shop A", "SP001", "OK"], ...]"""
        if not sheets_service.is_configured():
            return {"ok": False, "error": "Google Sheets chưa cấu hình."}
        try:
            result = await sheets_service.append_rows(spreadsheet_id, tab_name, rows)
            return {"ok": True, **result}
        except Exception as e:
            logger.error("sheets_append_rows | %s | %s | %s", spreadsheet_id, tab_name, e)
            return {"ok": False, "error": str(e)}

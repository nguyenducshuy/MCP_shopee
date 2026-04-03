"""
Google Sheets Service — đọc Google Sheets dùng Service Account.

Authentication:
  - GOOGLE_SERVICE_ACCOUNT_FILE: path tới file JSON service account key
  - GOOGLE_SERVICE_ACCOUNT_JSON: nội dung JSON (dùng cho Docker / env var)

Sau khi setup, share spreadsheet với email service account
(dạng: xxx@project.iam.gserviceaccount.com) quyền Viewer.
"""

import asyncio
import json
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Sentinel để phân biệt "chưa khởi tạo" với None (credentials không hợp lệ)
_UNSET = object()


class SheetsService:
    """Async-friendly wrapper around gspread (sync I/O → asyncio.to_thread)."""

    def __init__(self):
        self._client: gspread.Client | None = None
        self._init_error: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────

    def _build_client(self) -> gspread.Client:
        """Build gspread client từ settings. Raise rõ ràng nếu thiếu config."""
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
            logger.info("sheets_auth | using JSON env var")
        elif settings.GOOGLE_SERVICE_ACCOUNT_FILE:
            creds = Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_SCOPES
            )
            logger.info("sheets_auth | using file: %s", settings.GOOGLE_SERVICE_ACCOUNT_FILE)
        else:
            raise RuntimeError(
                "Google Sheets chưa được cấu hình. "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE hoặc GOOGLE_SERVICE_ACCOUNT_JSON trong .env"
            )
        return gspread.authorize(creds)

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def is_configured(self) -> bool:
        return bool(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE or settings.GOOGLE_SERVICE_ACCOUNT_JSON
        )

    # ── Core operations (sync, wrapped below) ────────────────────────

    def _sync_get_spreadsheet_info(self, spreadsheet_id: str) -> dict:
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        tabs = []
        for ws in sh.worksheets():
            tabs.append({
                "title": ws.title,
                "row_count": ws.row_count,
                "col_count": ws.col_count,
                "is_likely_raw": ws.row_count > settings.SHEETS_RAW_TAB_THRESHOLD,
            })
        return {
            "spreadsheet_id": spreadsheet_id,
            "title": sh.title,
            "url": sh.url,
            "tabs": tabs,
            "total_tabs": len(tabs),
            "summary_tabs": [t["title"] for t in tabs if not t["is_likely_raw"]],
            "raw_tabs": [t["title"] for t in tabs if t["is_likely_raw"]],
        }

    def _sync_read_tab(
        self, spreadsheet_id: str, tab_name: str, max_rows: int
    ) -> dict:
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(tab_name)

        total_rows = ws.row_count
        is_likely_raw = total_rows > settings.SHEETS_RAW_TAB_THRESHOLD

        # get_all_records() dùng row 1 làm header tự động
        records: list[dict] = ws.get_all_records(numericise_ignore=["all"])

        truncated = len(records) > max_rows
        if truncated:
            records = records[:max_rows]

        columns = list(records[0].keys()) if records else []

        return {
            "spreadsheet_id": spreadsheet_id,
            "tab": tab_name,
            "columns": columns,
            "row_count": len(records),
            "total_rows_in_sheet": total_rows,
            "truncated": truncated,
            "truncated_at": max_rows if truncated else None,
            "is_likely_raw_data": is_likely_raw,
            "data": records,
        }

    def _sync_read_range(self, spreadsheet_id: str, range_notation: str) -> dict:
        """Đọc range dạng 'TabName!A1:H50' hoặc named range."""
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        values: list[list] = sh.values_get(range_notation).get("values", [])

        if not values:
            return {"range": range_notation, "row_count": 0, "columns": [], "data": []}

        headers = [str(h).strip() for h in values[0]]
        data = []
        for row in values[1:]:
            # Pad row nếu thiếu cột
            padded = row + [""] * (len(headers) - len(row))
            data.append(dict(zip(headers, padded[:len(headers)])))

        return {
            "range": range_notation,
            "columns": headers,
            "row_count": len(data),
            "data": data,
        }

    def _sync_list_named_ranges(self, spreadsheet_id: str) -> dict:
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        # Lấy metadata qua batch_update fetch
        spreadsheet = sh.fetch_sheet_metadata()
        named_ranges = spreadsheet.get("namedRanges", [])
        result = []
        for nr in named_ranges:
            result.append({
                "name": nr.get("name"),
                "range": nr.get("range", {}),
            })
        return {
            "spreadsheet_id": spreadsheet_id,
            "named_ranges": result,
            "count": len(result),
        }

    def _sync_search_tab(
        self, spreadsheet_id: str, tab_name: str, keyword: str, column: str = ""
    ) -> dict:
        """Tìm rows chứa keyword trong tab. Nếu column="", tìm toàn bộ."""
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(tab_name)
        records: list[dict] = ws.get_all_records(numericise_ignore=["all"])

        keyword_lower = keyword.lower()
        matches = []
        for i, row in enumerate(records, start=2):  # start=2 vì row 1 là header
            if column:
                cell_val = str(row.get(column, "")).lower()
                if keyword_lower in cell_val:
                    matches.append({"_row": i, **row})
            else:
                row_str = " ".join(str(v) for v in row.values()).lower()
                if keyword_lower in row_str:
                    matches.append({"_row": i, **row})

        return {
            "tab": tab_name,
            "keyword": keyword,
            "column_filter": column or "all",
            "matches": matches,
            "match_count": len(matches),
        }

    # ── Write operations (sync) ────────────────────────────────────────

    def _sync_update_range(
        self, spreadsheet_id: str, range_notation: str, values: list[list]
    ) -> dict:
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        sh.values_update(
            range_notation,
            params={"valueInputOption": "USER_ENTERED"},
            body={"values": values},
        )
        return {"range": range_notation, "updated_rows": len(values)}

    def _sync_append_rows(
        self, spreadsheet_id: str, tab_name: str, rows: list[list]
    ) -> dict:
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(tab_name)
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        return {"tab": tab_name, "appended_rows": len(rows)}

    def _sync_update_cells(
        self, spreadsheet_id: str, tab_name: str, updates: list[dict]
    ) -> dict:
        """updates: [{"cell": "A2", "value": "OK"}, {"cell": "B5", "value": 123}]"""
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(tab_name)
        for u in updates:
            ws.update_acell(u["cell"], u["value"])
        return {"tab": tab_name, "updated_cells": len(updates)}

    def _sync_batch_update_cells(
        self, spreadsheet_id: str, tab_name: str, updates: list[dict]
    ) -> dict:
        """Batch update — hiệu quả hơn update_cells cho nhiều ô.
        updates: [{"cell": "S2", "value": "OK"}, ...]"""
        gc = self._get_client()
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(tab_name)
        batch = [{"range": u["cell"], "values": [[u["value"]]]} for u in updates]
        ws.batch_update(batch, value_input_option="USER_ENTERED")
        return {"tab": tab_name, "updated_cells": len(updates)}

    # ── Async public API ──────────────────────────────────────────────

    async def get_spreadsheet_info(self, spreadsheet_id: str) -> dict:
        """Lấy metadata spreadsheet: danh sách tabs, phân loại summary/raw."""
        return await asyncio.to_thread(
            self._sync_get_spreadsheet_info, spreadsheet_id
        )

    async def read_tab(
        self, spreadsheet_id: str, tab_name: str, max_rows: int | None = None
    ) -> dict:
        """Đọc 1 tab, trả về list of dicts. Tự cắt tại max_rows."""
        limit = max_rows or settings.SHEETS_MAX_ROWS
        return await asyncio.to_thread(
            self._sync_read_tab, spreadsheet_id, tab_name, limit
        )

    async def read_range(self, spreadsheet_id: str, range_notation: str) -> dict:
        """Đọc range cụ thể, VD: 'Dashboard!A1:H20' hoặc named range."""
        return await asyncio.to_thread(
            self._sync_read_range, spreadsheet_id, range_notation
        )

    async def list_named_ranges(self, spreadsheet_id: str) -> dict:
        """Lấy danh sách named ranges đã định nghĩa trong spreadsheet."""
        return await asyncio.to_thread(self._sync_list_named_ranges, spreadsheet_id)

    async def search_tab(
        self, spreadsheet_id: str, tab_name: str, keyword: str, column: str = ""
    ) -> dict:
        """Tìm kiếm keyword trong tab, trả về matching rows."""
        return await asyncio.to_thread(
            self._sync_search_tab, spreadsheet_id, tab_name, keyword, column
        )

    async def update_range(
        self, spreadsheet_id: str, range_notation: str, values: list[list]
    ) -> dict:
        """Cập nhật vùng dữ liệu trên Sheet."""
        return await asyncio.to_thread(
            self._sync_update_range, spreadsheet_id, range_notation, values
        )

    async def append_rows(
        self, spreadsheet_id: str, tab_name: str, rows: list[list]
    ) -> dict:
        """Thêm dòng mới cuối tab."""
        return await asyncio.to_thread(
            self._sync_append_rows, spreadsheet_id, tab_name, rows
        )

    async def update_cells(
        self, spreadsheet_id: str, tab_name: str, updates: list[dict]
    ) -> dict:
        """Cập nhật từng ô riêng lẻ. updates: [{"cell": "A2", "value": "OK"}]"""
        return await asyncio.to_thread(
            self._sync_update_cells, spreadsheet_id, tab_name, updates
        )

    async def batch_update_cells(
        self, spreadsheet_id: str, tab_name: str, updates: list[dict]
    ) -> dict:
        """Batch update nhiều ô cùng lúc (hiệu quả hơn update_cells)."""
        return await asyncio.to_thread(
            self._sync_batch_update_cells, spreadsheet_id, tab_name, updates
        )

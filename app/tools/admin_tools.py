from app.config import settings
from app.core.constants import AUTH_PARTNER_PATH
from app.core.logger import get_logger
from app.core.utils import now_ts
from app.dependencies import (
    shop_registry_service,
    token_service,
    auth_service,
    sign_service,
)

logger = get_logger(__name__)


def register_admin_tools(mcp):

    # ── Shop management ────────────────────────────────────────────

    @mcp.tool()
    def add_shop(
        shop_id: int,
        shop_name: str,
        region: str = "VN",
        environment: str = "sandbox",
        oauth_code: str = "",
    ) -> dict:
        """Thêm shop mới vào hệ thống. Trả về shop_code để dùng cho các tool khác.
        - shop_id: ID shop trên Shopee (bắt buộc)
        - shop_name: tên shop (bắt buộc)
        - region: VN, SG, MY, TH, PH, ... (mặc định VN)
        - environment: sandbox hoặc production (mặc định sandbox)
        - oauth_code: OAuth code từ Shopee (nếu có). Có thể thêm sau bằng set_oauth_code.
        """
        shop = shop_registry_service.add_shop(
            shop_id=shop_id,
            shop_name=shop_name,
            region=region,
            environment=environment,
            code=oauth_code,
        )
        return {
            "ok": True,
            "message": f"Shop '{shop_name}' added successfully.",
            "shop_code": shop["code"],
            "next_step": (
                "Use exchange_token(shop_code, code) to obtain access token."
                if oauth_code
                else "Use get_auth_url() to get authorization link, then exchange_token()."
            ),
        }

    @mcp.tool()
    def update_shop(shop_code: str, shop_name: str = "", region: str = "", environment: str = "") -> dict:
        """Cập nhật thông tin shop (tên, region, environment). Chỉ gửi field muốn sửa."""
        updates = {}
        if shop_name:
            updates["shop_name"] = shop_name
        if region:
            updates["region"] = region
        if environment:
            updates["environment"] = environment
        if not updates:
            return {"ok": False, "message": "No fields to update."}
        result = shop_registry_service.update_shop(shop_code, updates)
        if not result:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}
        return {"ok": True, "message": "Shop updated.", "updated_fields": list(updates.keys())}

    @mcp.tool()
    def remove_shop(shop_code: str) -> dict:
        """Xóa shop khỏi hệ thống. CẢNH BÁO: sẽ xóa luôn token."""
        removed = shop_registry_service.remove_shop(shop_code)
        if not removed:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}
        return {"ok": True, "message": f"Shop '{shop_code}' removed."}

    # ── OAuth & Token ──────────────────────────────────────────────

    @mcp.tool()
    def get_auth_url(redirect_url: str = "", environment: str = "sandbox") -> dict:
        """Tạo URL authorize shop trên Shopee. User cần mở link này trên browser, đăng nhập, rồi copy code từ redirect URL.
        - redirect_url: URL nhận callback (mặc định dùng config SHOPEE_REDIRECT_URL hoặc webhook.site)
        - environment: sandbox hoặc production (mặc định sandbox)
        """
        redirect = redirect_url or settings.SHOPEE_REDIRECT_URL or "https://webhook.site/"
        partner_id, _ = settings.get_partner_credentials(environment)
        ts = now_ts()
        sign = sign_service.sign_auth(AUTH_PARTNER_PATH, ts, environment=environment)
        base_url = settings.get_base_url(environment)
        url = (
            f"{base_url}{AUTH_PARTNER_PATH}"
            f"?partner_id={partner_id}"
            f"&timestamp={ts}"
            f"&sign={sign}"
            f"&redirect={redirect}"
        )
        return {
            "ok": True,
            "auth_url": url,
            "instructions": (
                "1. Open this URL in a browser\n"
                "2. Login with Shopee seller account\n"
                "3. Authorize the app\n"
                "4. Copy the 'code' parameter from the redirect URL\n"
                "5. Use exchange_token(shop_code, code) to get access token"
            ),
            "note": "This link expires in 5 minutes.",
        }

    @mcp.tool()
    def set_oauth_code(shop_code: str, code: str) -> dict:
        """Lưu OAuth code vào shop (chưa exchange). Dùng khi muốn lưu code trước, exchange sau."""
        result = shop_registry_service.update_shop(shop_code, {"code_oauth": code})
        if not result:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}
        return {"ok": True, "message": "OAuth code saved. Use exchange_token to get access token."}

    @mcp.tool()
    async def exchange_token(shop_code: str, code: str = "") -> dict:
        """Exchange OAuth code lấy access_token + refresh_token.
        - code: OAuth code từ Shopee redirect. Nếu bỏ trống, dùng code đã lưu trong shop.
        """
        shop = shop_registry_service.get_shop(shop_code)
        if not shop:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}

        oauth_code = code or shop.get("code_oauth", "")
        if not oauth_code:
            return {
                "ok": False,
                "message": "No OAuth code provided and no code stored for this shop.",
                "hint": "Use get_auth_url() to get authorization link first.",
            }

        shop_id = shop["shop_id"]
        environment = shop.get("environment", "sandbox")

        try:
            resp = await auth_service.get_token_by_code(oauth_code, shop_id, environment)
        except Exception as exc:
            logger.error("exchange_token | %s | %s: %s", shop_code, type(exc).__name__, exc)
            return {"ok": False, "message": f"Exchange failed: {exc}", "error_type": type(exc).__name__}

        if not resp.get("access_token"):
            return {"ok": False, "message": "Shopee returned empty access token.", "raw": resp}

        token_data = token_service.save_token(shop_code, resp)
        # Clear used code
        shop_registry_service.update_shop(shop_code, {"code_oauth": ""})

        return {
            "ok": True,
            "message": "Token obtained successfully!",
            "access_token_tail": "..." + resp["access_token"][-8:],
            "expires_in_seconds": resp.get("expire_in", 0),
            "expires_in_human": f"{resp.get('expire_in', 0) // 3600}h",
        }

    @mcp.tool()
    async def force_refresh_token(shop_code: str) -> dict:
        """Ép refresh token ngay lập tức (dù chưa hết hạn)."""
        shop = shop_registry_service.get_shop(shop_code)
        if not shop:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}

        try:
            refresh_tok = token_service.get_refresh_token(shop_code)
        except Exception as exc:
            return {"ok": False, "message": f"No refresh token: {exc}"}

        shop_id = shop["shop_id"]
        environment = shop.get("environment", "sandbox")

        try:
            resp = await auth_service.refresh_token(refresh_tok, shop_id, environment)
        except Exception as exc:
            logger.error("force_refresh | %s | %s: %s", shop_code, type(exc).__name__, exc)
            return {"ok": False, "message": f"Refresh failed: {exc}", "error_type": type(exc).__name__}

        if not resp.get("access_token"):
            return {"ok": False, "message": "Shopee returned empty access token.", "raw": resp}

        token_service.save_token(shop_code, resp)
        return {
            "ok": True,
            "message": "Token refreshed successfully!",
            "access_token_tail": "..." + resp["access_token"][-8:],
            "expires_in_seconds": resp.get("expire_in", 0),
        }

    @mcp.tool()
    def check_token_status(shop_code: str) -> dict:
        """Kiểm tra trạng thái token của shop: còn hạn bao lâu, cần refresh không, ..."""
        shop = shop_registry_service.get_shop(shop_code)
        if not shop:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}

        status = token_service.get_token_status(shop_code)
        status["ok"] = True
        status["shop_name"] = shop.get("shop_name", "")
        return status

    @mcp.tool()
    def check_all_tokens() -> dict:
        """Kiểm tra trạng thái token của TẤT CẢ shop. Hữu ích để phát hiện shop nào sắp hết hạn."""
        shops = shop_registry_service.list_shops()
        results = []
        for shop in shops:
            shop_code = shop.get("code", "")
            status = token_service.get_token_status(shop_code)
            results.append({
                "shop_code": shop_code,
                "shop_name": shop.get("shop_name", ""),
                "status": status["status"],
                "message": status["message"],
                "access_expires_in": status.get("access_expires_in_human", ""),
                "refresh_expires_in": status.get("refresh_expires_in_human", ""),
            })
        return {"ok": True, "shops": results, "total": len(results)}

    @mcp.tool()
    def clear_token(shop_code: str) -> dict:
        """Xóa token của shop (reset, debug). Shop sẽ cần exchange_token lại."""
        shop = shop_registry_service.get_shop(shop_code)
        if not shop:
            return {"ok": False, "message": f"Shop '{shop_code}' not found."}
        token_service.clear_token(shop_code)
        return {"ok": True, "message": f"Token cleared for shop '{shop_code}'. Use exchange_token to re-authenticate."}

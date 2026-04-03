"""Flash Sale batch tools — tổng hợp API tạo flash sale hàng loạt."""
import asyncio

from app.dependencies import shopee_client
from app.core.logger import get_logger

logger = get_logger(__name__)


def register_flash_sale_tools(mcp):

    @mcp.tool()
    async def batch_create_flash_sale(flash_sale_items: list[dict]) -> dict:
        """Tạo flash sale HÀNG LOẠT cho nhiều shop cùng lúc.

        flash_sale_items: danh sách, mỗi item gồm:
          - shop_code: mã shop (bắt buộc)
          - timeslot_id: ID khung giờ từ get_time_slot_id (bắt buộc)
          - item_list: danh sách sản phẩm, mỗi sp gồm:
              SP CÓ biến thể:
                - item_id: ID sản phẩm
                - purchase_limit: giới hạn mua (0=không giới hạn)
                - models: [{model_id, input_promo_price, stock}]
              SP KHÔNG biến thể:
                - item_id: ID sản phẩm
                - purchase_limit: giới hạn mua (0=không giới hạn)
                - item_input_promo_price: giá FS
                - item_stock: số lượng

        VD: [
          {
            "shop_code": "abc123",
            "timeslot_id": 123456,
            "item_list": [
              {"item_id": 12345, "purchase_limit": 5, "models": [{"model_id": 67890, "input_promo_price": 99000, "stock": 10}]}
            ]
          }
        ]

        Flow: create_shop_flash_sale → add_items → enable(status=1)
        """
        async def do_create(item):
            shop_code = item["shop_code"]
            timeslot_id = item.get("timeslot_id")
            items = item.get("item_list", [])

            if not timeslot_id:
                return {
                    "shop_code": shop_code,
                    "status": "error",
                    "error": "Thieu timeslot_id. Goi get_time_slot_id truoc.",
                    "item_count": len(items),
                }

            try:
                # Step 1: Tạo phiên FS rỗng
                create_resp = await shopee_client.call(
                    shop_code, "shop_flash_sale.create_shop_flash_sale",
                    body={"timeslot_id": timeslot_id},
                )
                if not isinstance(create_resp, dict) or not create_resp.get("flash_sale_id"):
                    return {
                        "shop_code": shop_code,
                        "status": "error",
                        "error": "Tao phien FS that bai: " + str(create_resp),
                        "item_count": len(items),
                    }
                flash_sale_id = create_resp["flash_sale_id"]

                # Step 2: Thêm sản phẩm
                failed_items = []
                add_error = None
                if items:
                    add_result = await shopee_client.call(
                        shop_code, "shop_flash_sale.add_shop_flash_sale_items",
                        body={"flash_sale_id": flash_sale_id, "items": items},
                    )
                    if not isinstance(add_result, dict):
                        add_error = "add_items response invalid: " + str(type(add_result))
                    else:
                        # Hỗ trợ cả failed_items và items[].err_code
                        if isinstance(add_result.get("failed_items"), list):
                            failed_items = add_result["failed_items"]
                        elif isinstance(add_result.get("items"), list):
                            failed_items = [it for it in add_result["items"] if it.get("err_code")]

                # Step 3: Enable phiên nếu có ít nhất 1 SP thành công
                added_ok = len(items) - len(failed_items)
                enable_result = None
                enable_error = None
                if added_ok > 0:
                    try:
                        enable_result = await shopee_client.call(
                            shop_code, "shop_flash_sale.update_shop_flash_sale",
                            body={"flash_sale_id": flash_sale_id, "status": 1},
                        )
                    except Exception as enable_exc:
                        enable_error = str(enable_exc)

                return {
                    "shop_code": shop_code,
                    "status": "ok" if added_ok > 0 else "error",
                    "flash_sale_id": flash_sale_id,
                    "item_count": len(items),
                    "added_ok": added_ok,
                    "failed_items": failed_items,
                    "add_error": add_error,
                    "enable_response": enable_result,
                    "enable_error": enable_error,
                }
            except Exception as e:
                return {
                    "shop_code": shop_code,
                    "status": "error",
                    "error": str(e),
                    "item_count": len(items),
                }

        results = await asyncio.gather(
            *[do_create(it) for it in flash_sale_items], return_exceptions=True
        )
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

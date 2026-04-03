from fastmcp import FastMCP

from app.config import settings
from app.tools.shop_tools import register_shop_tools
from app.tools.product_tools import register_product_tools
from app.tools.order_tools import register_order_tools
from app.tools.logistics_tools import register_logistics_tools
from app.tools.marketing_tools import register_marketing_tools
from app.tools.report_tools import register_report_tools
from app.tools.admin_tools import register_admin_tools
from app.tools.batch_tools import register_batch_tools
from app.tools.ams_tools import register_ams_tools
from app.tools.video_tools import register_video_tools
from app.tools.global_product_tools import register_global_product_tools
from app.tools.media_tools import register_media_tools
from app.tools.merchant_tools import register_merchant_tools
from app.tools.extra_tools import register_extra_tools
from app.tools.ads_tools import register_ads_tools
from app.tools.cache_tools import register_cache_tools
from app.tools.workflow_tools import register_workflow_tools
from app.tools.sheets_tools import register_sheets_tools
from app.tools.flash_sale_tools import register_flash_sale_tools
from app.tools.plan_tools import register_plan_tools

mcp = FastMCP(name=settings.APP_NAME)

register_shop_tools(mcp)
register_product_tools(mcp)
register_order_tools(mcp)
register_logistics_tools(mcp)
register_marketing_tools(mcp)
register_report_tools(mcp)
register_admin_tools(mcp)
register_batch_tools(mcp)
register_ams_tools(mcp)
register_video_tools(mcp)
register_global_product_tools(mcp)
register_media_tools(mcp)
register_merchant_tools(mcp)
register_extra_tools(mcp)
register_ads_tools(mcp)
register_cache_tools(mcp)
register_workflow_tools(mcp)
register_sheets_tools(mcp)
register_flash_sale_tools(mcp)
register_plan_tools(mcp)


def create_server() -> FastMCP:
    return mcp


if __name__ == "__main__":
    import sys

    transport = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        from app.middleware.auth import BearerAuthMiddleware
        from starlette.middleware.cors import CORSMiddleware

        app = mcp.http_app(path="/mcp", transport="streamable-http")

        sse_app = mcp.http_app(path="/sse", transport="sse")
        for route in sse_app.routes:
            app.routes.append(route)

        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
        app.add_middleware(BearerAuthMiddleware)

        import uvicorn
        uvicorn.run(app, host=settings.APP_HOST, port=settings.APP_PORT)

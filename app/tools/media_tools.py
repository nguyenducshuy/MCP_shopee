"""MediaSpace tools — upload ảnh/video lên Shopee."""
from app.dependencies import shopee_client


def register_media_tools(mcp):

    @mcp.tool()
    async def media_upload_image(shop_code: str, image_data: dict) -> dict:
        """Upload ảnh lên Shopee MediaSpace. image_data chứa image (base64 hoặc url)."""
        return await shopee_client.call(shop_code, "media_space.upload_image", body=image_data)

    @mcp.tool()
    async def media_init_video_upload(shop_code: str, file_md5: str, file_size: int) -> dict:
        """Khởi tạo upload video. Trả về video_upload_id."""
        return await shopee_client.call(
            shop_code, "media_space.init_video_upload",
            body={"file_md5": file_md5, "file_size": file_size},
        )

    @mcp.tool()
    async def media_upload_video_part(shop_code: str, upload_data: dict) -> dict:
        """Upload từng phần video. upload_data chứa video_upload_id, part_seq, content_md5."""
        return await shopee_client.call(shop_code, "media_space.upload_video_part", body=upload_data)

    @mcp.tool()
    async def media_complete_video_upload(shop_code: str, video_upload_id: str, part_seq_list: list[int]) -> dict:
        """Hoàn tất upload video."""
        return await shopee_client.call(
            shop_code, "media_space.complete_video_upload",
            body={"video_upload_id": video_upload_id, "part_seq_list": part_seq_list},
        )

    @mcp.tool()
    async def media_get_video_upload_result(shop_code: str, video_upload_id: str) -> dict:
        """Kiểm tra kết quả upload video."""
        return await shopee_client.call(
            shop_code, "media_space.get_video_upload_result",
            extra_params={"video_upload_id": video_upload_id},
        )

    @mcp.tool()
    async def media_cancel_video_upload(shop_code: str, video_upload_id: str) -> dict:
        """Hủy upload video."""
        return await shopee_client.call(
            shop_code, "media_space.cancel_video_upload",
            body={"video_upload_id": video_upload_id},
        )

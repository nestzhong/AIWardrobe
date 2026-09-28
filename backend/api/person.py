"""
本人照片 API：设置页上传 / 移除，供 AI 试穿使用。
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

from services.gateway_utils import guess_image_mime
from services.person_image import (
    clear_person_image,
    person_image_url,
    save_person_image,
)
from storage.config_store import update_config

router = APIRouter()

_ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}


@router.post("/person-image")
async def upload_person_image(file: UploadFile = File(...)):
    """上传或替换本人照片。"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="图片内容为空")

    mime = file.content_type or guess_image_mime(raw_bytes)
    if mime not in _ALLOWED_MIME:
        mime = guess_image_mime(raw_bytes)

    filename = save_person_image(raw_bytes, mime)
    update_config(person_image_filename=filename)

    return {
        "success": True,
        "person_image_url": person_image_url(filename),
        "has_person_image": True,
    }


@router.delete("/person-image")
async def remove_person_image():
    """移除已保存的本人照片。"""
    clear_person_image()
    update_config(person_image_filename="")
    return {
        "success": True,
        "person_image_url": "",
        "has_person_image": False,
    }
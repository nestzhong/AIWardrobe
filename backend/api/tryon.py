"""
AI 试穿 API（以图生图，统一入口）。

POST /api/tryon  body: {"garment_ids": [int, ...]}
- 参考图 = 设置中的本人照片 + 各服饰商品图
- 详情页传单个 id；穿搭页传上衣 / 下装 / 鞋履 id
"""
from pathlib import Path
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.person_image import load_person_image_bytes
from services.tryon import run_tryon
from storage.config_store import load_config
from storage.db import get_clothes_by_id

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
TRYON_DIR = UPLOAD_DIR / "tryon"
TRYON_DIR.mkdir(parents=True, exist_ok=True)


class TryOnRequest(BaseModel):
    """试穿请求：1~4 件服饰。"""

    garment_ids: list[int] = Field(default_factory=list, min_length=1, max_length=4)


@router.post("/tryon")
async def tryon(request: TryOnRequest):
    config = load_config()

    person_bytes = load_person_image_bytes(config.person_image_filename)
    if not person_bytes:
        raise HTTPException(
            status_code=400,
            detail="PERSON_IMAGE_MISSING",
        )

    garments = []
    for garment_id in request.garment_ids:
        garment = await get_clothes_by_id(garment_id)
        if not garment:
            raise HTTPException(status_code=404, detail=f"衣物不存在: {garment_id}")

        garment_path = UPLOAD_DIR / Path(garment.image_url).name
        if not garment_path.is_file():
            raise HTTPException(status_code=404, detail=f"衣物图片文件不存在: {garment_id}")

        garments.append(
            {
                "id": garment.id,
                "category": garment.category,
                "item": garment.item,
                "description": garment.description,
                "image_bytes": garment_path.read_bytes(),
            }
        )

    try:
        result = await run_tryon(person_image_bytes=person_bytes, garments=garments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"试穿失败: {e}")

    if result.result_image_url:
        return {
            "success": True,
            "result_image_url": result.result_image_url,
            "source": "remote_url",
        }

    ext = result.image_ext or "png"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = TRYON_DIR / filename
    with open(filepath, "wb") as f:
        f.write(result.image_bytes or b"")

    return {
        "success": True,
        "result_image_url": f"/uploads/tryon/{filename}",
        "source": "local_file",
    }
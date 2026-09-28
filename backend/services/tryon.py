"""
AI 试穿服务（以图生图）。

与服饰商品图（canonical）共用同一生图模型与网关协议：
参考图 = 本人照片 + 单品服饰商品图，输出本人穿着这些服饰的照片。
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from domain.prompts_tryon import TRYON_NEGATIVE_PROMPT, build_tryon_prompt
from services.image_generation import generate_image
from storage.config_store import load_config


class TryOnResult:
    def __init__(
        self,
        result_image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_ext: str = "png",
    ):
        self.result_image_url = result_image_url
        self.image_bytes = image_bytes
        self.image_ext = image_ext


async def run_tryon(
    person_image_bytes: bytes,
    garments: Sequence[dict[str, Any]],
) -> TryOnResult:
    """
    以图生图生成试穿图。

    Args:
        person_image_bytes: 本人照片字节
        garments: 服饰列表，元素含 category / item / description / image_bytes
    """
    config = load_config()

    if not config.image_model:
        raise ValueError("未配置生图模型（image_model），请先在设置中完成生图配置。")
    if not person_image_bytes:
        raise ValueError("缺少本人照片，请先在设置中上传。")

    references = [person_image_bytes]
    for garment in garments:
        image_bytes = garment.get("image_bytes")
        if image_bytes:
            references.append(image_bytes)

    if len(references) < 2:
        raise ValueError("缺少服饰图片，请至少选择一件有图片的服饰。")

    prompt = build_tryon_prompt(garments)

    generated_bytes = await generate_image(
        prompt=prompt,
        model=config.image_model,
        category="tryon",
        reference_images=references,
        negative_prompt=TRYON_NEGATIVE_PROMPT,
        watermark=False,
    )

    return TryOnResult(image_bytes=generated_bytes, image_ext="png")
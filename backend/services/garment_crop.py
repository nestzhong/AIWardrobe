"""
服装裁剪服务：按 bbox 从原图裁出服饰参考图（双图参考的图 2）。

优先用多模态分析返回的归一化 bbox；缺失或无效时用 rembg mask 的 bbox 兜底。
"""
import io
from typing import List, Optional

from PIL import Image


def _load_rgb(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _save_png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def crop_by_bbox(
    image_bytes: bytes,
    bbox: List[float],
    padding: float = 0.03,
    min_side: int = 16,
) -> Optional[bytes]:
    """
    按归一化 bbox 裁剪原图。

    Args:
        bbox: [x1, y1, x2, y2]，取值 0-1
        padding: 相对裁剪框宽高的额外留白比例
    """
    if not bbox or len(bbox) != 4:
        return None

    try:
        img = _load_rgb(image_bytes)
    except Exception:
        return None

    width, height = img.size
    x1, y1, x2, y2 = bbox

    pad_x = (x2 - x1) * padding
    pad_y = (y2 - y1) * padding

    left = int(max(0.0, x1 - pad_x) * width)
    top = int(max(0.0, y1 - pad_y) * height)
    right = int(min(1.0, x2 + pad_x) * width)
    bottom = int(min(1.0, y2 + pad_y) * height)

    if right - left < min_side or bottom - top < min_side:
        return None

    crop = img.crop((left, top, right, bottom))
    return _save_png(crop)


def crop_by_mask(image_bytes: bytes) -> Optional[bytes]:
    """用 rembg 前景 mask 的 bbox 兜底裁剪。"""
    try:
        from services.segment import remove_background

        masked_png = remove_background(image_bytes)
    except Exception:
        return None

    try:
        masked = Image.open(io.BytesIO(masked_png)).convert("RGBA")
        alpha_bbox = masked.getchannel("A").getbbox()
        if not alpha_bbox:
            return None

        original = _load_rgb(image_bytes)
        # mask 与原图尺寸通常一致；若不同则按比例缩放 bbox
        if masked.size != original.size:
            scale_x = original.width / masked.width
            scale_y = original.height / masked.height
            alpha_bbox = (
                int(alpha_bbox[0] * scale_x),
                int(alpha_bbox[1] * scale_y),
                int(alpha_bbox[2] * scale_x),
                int(alpha_bbox[3] * scale_y),
            )

        crop = original.crop(alpha_bbox)
        if crop.width < 16 or crop.height < 16:
            return None
        return _save_png(crop)
    except Exception:
        return None


def crop_garment_reference(
    image_bytes: bytes,
    bbox: Optional[List[float]] = None,
    allow_mask_fallback: bool = True,
) -> Optional[bytes]:
    """
    获取服饰参考图：优先 bbox，其次 mask 兜底。

    返回 PNG 字节；都失败时返回 None（调用方决定退回全图）。
    """
    if bbox:
        cropped = crop_by_bbox(image_bytes, bbox)
        if cropped:
            return cropped

    if allow_mask_fallback:
        return crop_by_mask(image_bytes)

    return None


def flatten_on_white(image_bytes: bytes) -> bytes:
    """
    把图片（含透明 PNG）合成到白底再做 RGB 编码。

    透明背景直接喂给视觉模型效果差，语义识别前先铺白底。
    失败时原样返回。
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return image_bytes

    try:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            flattened = background
        else:
            flattened = img.convert("RGB")
        return _save_png(flattened)
    except Exception:
        return image_bytes
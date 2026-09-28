"""
网关通用工具：API Base 归一化、图片 data URL 构造。
"""
import base64
from typing import Optional


def normalize_api_base(api_base: str) -> str:
    """确保 API Base 以 /v1 结尾（与现有 openai_compatible 行为一致）。"""
    base = (api_base or "").strip().rstrip("/")
    if not base:
        return base
    if not base.endswith("/v1"):
        base = base + "/v1"
    return base


def guess_image_mime(image_bytes: bytes) -> str:
    """根据文件头猜测图片 MIME 类型。"""
    if not image_bytes:
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def to_data_url(image_bytes: bytes, mime: Optional[str] = None) -> str:
    """将图片字节转换为 data URL（base64）。"""
    resolved_mime = mime or guess_image_mime(image_bytes)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{resolved_mime};base64,{encoded}"
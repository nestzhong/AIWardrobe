"""
服装分析服务：把真人照片拆解为结构化服饰列表（含规格与 bbox）。

使用网关的 OpenAI 兼容 /chat/completions，模型由 config.vision_model 指定。
"""
from typing import Any, List, Optional

import httpx

from domain.clothes import resolve_category_value
from domain.garments import GarmentCandidate, GarmentSpec
from domain.prompts_garment import ANALYZE_PERSON_PROMPT
from services.gateway_utils import normalize_api_base, to_data_url
from services.openai_compatible import extract_json_from_response
from storage.config_store import load_config

_ALLOWED_CATEGORIES = {"top", "bottom", "shoes", "accessory"}


async def analyze_person_image(image_bytes: bytes, mime: Optional[str] = None) -> List[GarmentCandidate]:
    """
    调用多模态模型拆解人物照中的服饰。

    Returns:
        List[GarmentCandidate]（可能为空列表）
    """
    config = load_config()

    if not config.api_key:
        raise ValueError("请先配置 API Key")

    api_base = normalize_api_base(config.api_base)
    if not api_base:
        raise ValueError("请先配置 API Base")

    model = (config.vision_model or config.model or "").strip()
    if not model:
        raise ValueError("请先配置识别模型（vision_model）")

    url = f"{api_base}/chat/completions"
    image_url = to_data_url(image_bytes, mime)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYZE_PERSON_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "max_tokens": 2048,
        # 关闭思考模式以提速（部分网关/模型可能忽略）
        "enable_thinking": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        raise ValueError(f"识别请求失败: {response.status_code} - {response.text[:300]}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"识别响应格式异常: {str(data)[:300]}") from exc

    parsed = extract_json_from_response(content)
    return normalize_garments(parsed)


def normalize_garments(parsed: Any) -> List[GarmentCandidate]:
    """把模型返回的 JSON 归一化为 GarmentCandidate 列表。"""
    raw_items: List[dict] = []

    if isinstance(parsed, dict):
        candidates = parsed.get("garments")
        if isinstance(candidates, list):
            raw_items = [item for item in candidates if isinstance(item, dict)]
        elif parsed.get("category"):
            raw_items = [parsed]
    elif isinstance(parsed, list):
        raw_items = [item for item in parsed if isinstance(item, dict)]

    garments: List[GarmentCandidate] = []
    seen_keys: set[str] = set()

    for index, raw in enumerate(raw_items, start=1):
        garment_key = str(raw.get("id") or raw.get("garment_key") or f"garment_{index:02d}")
        if garment_key in seen_keys:
            garment_key = f"garment_{index:02d}_{len(seen_keys)}"
        seen_keys.add(garment_key)

        category = resolve_category_value(
            str(raw.get("category") or ""),
            str(raw.get("item") or ""),
            str(raw.get("description") or ""),
        )
        if category not in _ALLOWED_CATEGORIES:
            category = "accessory"

        spec = _normalize_spec(raw.get("spec"))
        bbox = _normalize_bbox(raw.get("bbox"))

        garments.append(
            GarmentCandidate(
                garment_key=garment_key,
                category=category,
                item=str(raw.get("item") or "").strip() or "未知服饰",
                description=str(raw.get("description") or "").strip(),
                visible_area=str(raw.get("visible_area") or "").strip(),
                pattern=str(raw.get("pattern") or "").strip(),
                graphics=str(raw.get("graphics") or "").strip(),
                spec=spec,
                bbox=bbox,
            )
        )

    return garments


def _normalize_spec(raw: Any) -> GarmentSpec:
    if not isinstance(raw, dict):
        return GarmentSpec()

    details = raw.get("details")
    if isinstance(details, list):
        details = [str(item) for item in details if str(item).strip()]
    else:
        details = []

    def _text(key: str) -> str:
        value = raw.get(key)
        text = str(value).strip() if value is not None else ""
        return text or "unknown"

    return GarmentSpec(
        color=_text("color"),
        neckline=_text("neckline"),
        sleeve=_text("sleeve"),
        fit=_text("fit"),
        fabric=_text("fabric"),
        length=_text("length"),
        details=details,
    )


def _normalize_bbox(raw: Any) -> Optional[List[float]]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        values = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None

    # 兼容 0-1000 归一化：若超出 1，则按 1000 缩放
    if any(value > 1.5 for value in values):
        values = [value / 1000.0 for value in values]

    clamped = [min(1.0, max(0.0, value)) for value in values]
    x1, y1, x2, y2 = clamped
    if x2 <= x1 or y2 <= y1:
        return None
    return clamped
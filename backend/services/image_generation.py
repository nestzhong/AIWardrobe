"""
生图服务：按网关（TokenHub OpenAI 兼容）协议调用 canonical 商品图生成。

请求体按模型名分支：
- qwen-image* + 参考图 -> input.messages[].content[] + parameters（size 用 `*`）
- doubao-seedream* + 参考图 -> 顶层 prompt + image[] + response_format（size 用 `x`）
- 其它 / 无参考图 -> 扁平文生图

响应按多形态解析：metadata.output.choices -> data[].url -> data[].b64_json。
"""
import base64
from typing import Any, List, Optional, Sequence, Tuple

import httpx

from domain.prompts_garment import resolve_canonical_size
from domain.prompts_tryon import resolve_tryon_size
from services.gateway_utils import normalize_api_base, to_data_url
from storage.config_store import load_config


def detect_provider(model: str) -> str:
    """按模型名判断生图分支：qwen / doubao / flat。"""
    name = (model or "").lower()
    if "qwen-image" in name:
        return "qwen"
    if "doubao-seedream" in name:
        return "doubao"
    return "flat"


def _size_for(category: str, provider: str) -> str:
    if (category or "").strip().lower() == "tryon":
        return resolve_tryon_size(provider)
    if provider == "qwen":
        return resolve_canonical_size(category, "qwen")
    return resolve_canonical_size(category, "doubao")


def build_payload(
    model: str,
    prompt: str,
    category: str,
    references: Optional[Sequence[str]] = None,
    negative_prompt: Optional[str] = None,
    watermark: bool = False,
    n: int = 1,
) -> Tuple[dict, str]:
    """
    构造生图请求体。

    Args:
        references: 参考图列表，元素已是 URL 或 data URL 字符串
    Returns:
        (payload, provider)
    """
    provider = detect_provider(model)
    refs = list(references or [])
    size = _size_for(category, provider)

    if provider == "qwen" and refs:
        content: List[dict] = [{"image": ref} for ref in refs]
        content.append({"text": prompt})
        payload: dict[str, Any] = {
            "model": model,
            "watermark": watermark,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": {
                "n": n,
                "size": size,
                "negative_prompt": negative_prompt or "",
                "prompt_extend": False,
            },
        }
        return payload, provider

    if provider == "doubao" and refs:
        payload = {
            "model": model,
            "prompt": prompt,
            "watermark": watermark,
            "image": refs,
            "response_format": "url",
            "n": n,
            "size": size,
            "negative_prompt": negative_prompt or "",
        }
        return payload, provider

    # 扁平文生图（无参考图或未知模型）；size 统一用 x 格式
    flat_size = size.replace("*", "x")
    payload = {
        "model": model,
        "prompt": prompt,
        "watermark": watermark,
        "n": n,
        "size": flat_size,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    return payload, provider


def extract_image_result(data: dict) -> Optional[Tuple[str, str]]:
    """
    从响应中提取第一张图片。

    Returns:
        ("url", url) 或 ("b64", base64_str)，找不到返回 None
    """
    if not isinstance(data, dict):
        return None

    # 1) qwen 多图：metadata.output.choices[].message.content[].image
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        output = metadata.get("output")
        if isinstance(output, dict):
            choices = output.get("choices")
            if isinstance(choices, list):
                for choice in choices:
                    message = choice.get("message") if isinstance(choice, dict) else None
                    if not isinstance(message, dict):
                        continue
                    content = message.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("image"):
                                return ("url", str(block["image"]))

    # 2) OpenAI 标准 data[]
    items = data.get("data")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("url"):
                return ("url", str(item["url"]))
            if item.get("b64_json"):
                return ("b64", str(item["b64_json"]))

    # 3) 顶层/嵌套兜底
    fallback = _find_url_like(data)
    if fallback:
        return fallback

    return None


def _find_url_like(node: Any, depth: int = 0) -> Optional[Tuple[str, str]]:
    """在响应结构里递归查找 url / image / b64_json（有限深度）。"""
    if depth > 4:
        return None
    if isinstance(node, dict):
        for key in ("url", "image"):
            value = node.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://", "data:image")):
                return ("url", value)
        if isinstance(node.get("b64_json"), str):
            return ("b64", node["b64_json"])
        for value in node.values():
            found = _find_url_like(value, depth + 1)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_url_like(value, depth + 1)
            if found:
                return found
    return None


def _raise_api_error(data: Any, status_code: int, raw_text: str) -> None:
    """把网关的多种错误形态映射为 ValueError。"""
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            raise ValueError(f"生图失败: {error['message']}")

        code = data.get("code")
        if code and str(code).lower() not in {"ok", "success", "0", "200", "none"}:
            message = data.get("message") or code
            raise ValueError(f"生图失败 ({code}): {message}")

    raise ValueError(f"生图请求失败: HTTP {status_code} - {raw_text[:300]}")


async def _download_image(client: httpx.AsyncClient, ref: str) -> bytes:
    if ref.startswith("data:"):
        _, _, encoded = ref.partition(",")
        return base64.b64decode(encoded)
    response = await client.get(ref)
    if response.status_code != 200:
        raise ValueError(f"下载生成图失败: HTTP {response.status_code}")
    return response.content


async def generate_image(
    prompt: str,
    model: str,
    category: str = "top",
    reference_images: Optional[Sequence[bytes]] = None,
    reference_urls: Optional[Sequence[str]] = None,
    negative_prompt: Optional[str] = None,
    watermark: bool = False,
) -> bytes:
    """
    调用网生图并返回图片字节（n=1）。

    Args:
        reference_images: 参考图片字节；默认以 base64 data URL 传入
        reference_urls: 当配置 image_reference_transport="url" 时使用的公网 URL
    """
    config = load_config()

    api_base = normalize_api_base(config.image_api_base or config.api_base)
    api_key = config.image_api_key or config.api_key

    if not api_base:
        raise ValueError("请先配置生图 API Base")
    if not api_key:
        raise ValueError("请先配置生图 API Key")

    model = (model or "").strip()
    if not model:
        raise ValueError("请先配置生图模型（image_model）")

    # 组装参考图
    references: List[str] = []
    if config.image_reference_transport == "url" and reference_urls:
        references = [str(url) for url in reference_urls]
    elif reference_images:
        references = [to_data_url(image_bytes) for image_bytes in reference_images]

    payload, _provider = build_payload(
        model=model,
        prompt=prompt,
        category=category,
        references=references,
        negative_prompt=negative_prompt,
        watermark=watermark,
        n=1,
    )

    url = f"{api_base}/images/generations"

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        try:
            data = response.json()
        except Exception:
            data = None

        if response.status_code != 200:
            _raise_api_error(data, response.status_code, response.text)

        if isinstance(data, dict) and not extract_image_result(data):
            # 200 但业务错误或无图片
            _raise_api_error(data, response.status_code, response.text)

        result = extract_image_result(data)
        if not result:
            raise ValueError(f"生图响应中未找到图片: {str(data)[:300]}")

        kind, value = result
        if kind == "b64":
            return base64.b64decode(value)
        return await _download_image(client, value)
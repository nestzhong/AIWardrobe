"""
OpenAI 兼容 API 服务
支持任何 OpenAI 风格的 API 接口
"""
import httpx
import base64
import json
import re
from typing import List, Optional
from storage.config_store import load_config
from domain.prompts import CLOTHES_SEMANTIC_PROMPT
from domain.clothes import ClothesSemantics


async def fetch_available_models() -> List[dict]:
    """
    获取可用模型列表
    """
    config = load_config()
    
    if not config.api_key:
        return []
    
    # 确保 api_base 格式正确
    api_base = config.api_base.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = api_base + "/v1"
    
    url = f"{api_base}/models"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                # 过滤出支持视觉的模型（通常包含 vision, gpt-4o, claude 等关键词）
                return [
                    {"id": m["id"], "name": m.get("name", m["id"])}
                    for m in models
                ]
            else:
                error_msg = f"API请求失败 ({response.status_code}): {response.text[:200]}"
                print(error_msg)
                raise Exception(error_msg)
    except Exception as e:
        print(f"获取模型列表异常: {e}")
        raise Exception(f"连接异常: {str(e)}")


def extract_json_from_response(text: str) -> dict:
    """
    从响应中提取 JSON
    处理可能的 markdown 代码块包装
    """
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 markdown 代码块中的 JSON
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试找到 { } 包围的内容
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"无法从响应中提取 JSON: {text}")


def normalize_semantics_payload(result: dict) -> dict:
    """把模型返回的语义 JSON 归一化，容忍字符串/unknown/缺失字段。"""
    if not isinstance(result, dict):
        result = {}

    def as_list(value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            items = [str(entry).strip() for entry in value]
        else:
            text = str(value).strip()
            if not text:
                return []
            for sep in ("/", "、", "，", ","):
                text = text.replace(sep, ",")
            items = [part.strip() for part in text.split(",")]
        return [entry for entry in items if entry and entry.lower() != "unknown"]

    def as_text(value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return "" if text.lower() == "unknown" else text

    return {
        "category": as_text(result.get("category")) or "accessory",
        "item": as_text(result.get("item")) or "未知服饰",
        "style_semantics": as_list(result.get("style_semantics")),
        "season_semantics": as_list(result.get("season_semantics")),
        "usage_semantics": as_list(result.get("usage_semantics")),
        "color_semantics": as_text(result.get("color_semantics")),
        "description": as_text(result.get("description")),
    }


async def analyze_clothes_openai(image_bytes: bytes, model: Optional[str] = None) -> ClothesSemantics:
    """
    使用 OpenAI 兼容 API 分析衣物图片
    
    Args:
        image_bytes: 图片的字节数据
        model: 可选的模型名覆盖（默认使用 config.model；服装录入链路传 vision_model）
        
    Returns:
        ClothesSemantics: 衣物语义信息
    """
    config = load_config()
    
    if not config.api_key:
        raise ValueError("请先配置 API Key")

    use_model = (model or config.model or "").strip()
    if not use_model:
        raise ValueError("请先配置模型")
    
    # 确保 api_base 格式正确
    api_base = config.api_base.rstrip("/")
    if not api_base.endswith("/v1"):
        api_base = api_base + "/v1"
    
    url = f"{api_base}/chat/completions"
    
    # 将图片转换为 base64
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # 构建请求体
    payload = {
        "model": use_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": CLOTHES_SEMANTIC_PROMPT
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        if response.status_code != 200:
            raise ValueError(f"API 请求失败: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # 提取响应内容
        content = data["choices"][0]["message"]["content"]
        
        # 解析 JSON
        result = extract_json_from_response(content)
        
        return ClothesSemantics(**normalize_semantics_payload(result))

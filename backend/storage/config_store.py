"""
配置存储 - 使用 JSON 文件持久化配置
"""
import json
from pathlib import Path
from typing import Optional
from domain.config import LLMConfig, RecommendationModeWeights
from services.weather import validate_location_input, DEFAULT_LOCATION_QUERY

CONFIG_FILE = Path(__file__).parent / "llm_config.json"
_CONFIG_CACHE: Optional[LLMConfig] = None
_CONFIG_MTIME: Optional[float] = None


def load_config() -> LLMConfig:
    """加载 LLM 配置"""
    global _CONFIG_CACHE, _CONFIG_MTIME

    if not CONFIG_FILE.exists():
        _CONFIG_CACHE = LLMConfig()
        _CONFIG_MTIME = None
        return _CONFIG_CACHE

    try:
        mtime = CONFIG_FILE.stat().st_mtime
    except Exception:
        mtime = None

    if _CONFIG_CACHE is not None and _CONFIG_MTIME == mtime:
        return _CONFIG_CACHE

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _CONFIG_CACHE = LLMConfig(**data)
        _CONFIG_MTIME = mtime
        return _CONFIG_CACHE
    except Exception:
        _CONFIG_CACHE = LLMConfig()
        _CONFIG_MTIME = mtime
        return _CONFIG_CACHE


def save_config(config: LLMConfig) -> None:
    """保存 LLM 配置"""
    global _CONFIG_CACHE, _CONFIG_MTIME

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)

    _CONFIG_CACHE = config
    try:
        _CONFIG_MTIME = CONFIG_FILE.stat().st_mtime
    except Exception:
        _CONFIG_MTIME = None


def update_config(
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    removebg_api_key: Optional[str] = None,
    bg_removal_method: Optional[str] = None,
    tryon_provider: Optional[str] = None,
    tryon_api_url: Optional[str] = None,
    tryon_api_key: Optional[str] = None,
    tryon_model: Optional[str] = None,
    weather_location: Optional[str] = None,
    zodiac_sign: Optional[str] = None,
    recommendation_mode_weights: Optional[RecommendationModeWeights] = None,
    experimental_garment_pipeline: Optional[bool] = None,
    vision_model: Optional[str] = None,
    image_model: Optional[str] = None,
    image_api_base: Optional[str] = None,
    image_api_key: Optional[str] = None,
    image_reference_transport: Optional[str] = None,
    person_image_filename: Optional[str] = None,
) -> LLMConfig:
    """更新配置"""
    config = load_config()

    if api_base is not None:
        config.api_base = api_base.strip()
    if api_key is not None:
        config.api_key = api_key.strip()
    if model is not None:
        config.model = model.strip()
    if removebg_api_key is not None:
        config.removebg_api_key = removebg_api_key.strip()
    if bg_removal_method is not None:
        config.bg_removal_method = bg_removal_method
    if tryon_provider is not None:
        config.tryon_provider = tryon_provider
    if tryon_api_url is not None:
        config.tryon_api_url = tryon_api_url.strip()
    if tryon_api_key is not None:
        config.tryon_api_key = tryon_api_key.strip()
    if tryon_model is not None:
        config.tryon_model = tryon_model.strip()
    if weather_location is not None:
        normalized_location = weather_location.strip() or DEFAULT_LOCATION_QUERY
        validation_error = validate_location_input(normalized_location)
        if validation_error:
            raise ValueError(validation_error)
        config.weather_location = normalized_location
    if zodiac_sign is not None:
        config.zodiac_sign = zodiac_sign.strip().lower()
    if recommendation_mode_weights is not None:
        config.recommendation_mode_weights = recommendation_mode_weights
    if experimental_garment_pipeline is not None:
        config.experimental_garment_pipeline = experimental_garment_pipeline
    if vision_model is not None:
        config.vision_model = vision_model.strip()
    if image_model is not None:
        config.image_model = image_model.strip()
    if image_api_base is not None:
        config.image_api_base = image_api_base.strip()
    if image_api_key is not None:
        config.image_api_key = image_api_key.strip()
    if image_reference_transport is not None:
        config.image_reference_transport = image_reference_transport
    if person_image_filename is not None:
        config.person_image_filename = person_image_filename.strip()

    save_config(config)
    return config


def _mask_key(key: str) -> str:
    """对 API Key 进行脱敏处理"""
    if not key:
        return ""
    if len(key) > 8:
        return key[:4] + "*" * (len(key) - 8) + key[-4:]
    return "*" * len(key)


def get_masked_config() -> dict:
    """获取脱敏后的配置（隐藏 API Key）"""
    config = load_config()
    weather_location = (config.weather_location or "").strip() or DEFAULT_LOCATION_QUERY
    if validate_location_input(weather_location):
        weather_location = DEFAULT_LOCATION_QUERY
    
    return {
        "api_base": config.api_base,
        "api_key_masked": _mask_key(config.api_key),
        "has_api_key": bool(config.api_key),
        "model": config.model,
        "removebg_api_key_masked": _mask_key(config.removebg_api_key),
        "has_removebg_key": bool(config.removebg_api_key),
        "bg_removal_method": config.bg_removal_method,
        "tryon_provider": config.tryon_provider,
        "tryon_api_url": config.tryon_api_url,
        "tryon_api_key_masked": _mask_key(config.tryon_api_key),
        "has_tryon_api_key": bool(config.tryon_api_key),
        "tryon_model": config.tryon_model,
        "weather_location": weather_location,
        "zodiac_sign": config.zodiac_sign,
        "recommendation_mode_weights": config.recommendation_mode_weights.model_dump(),
        "experimental_garment_pipeline": config.experimental_garment_pipeline,
        "vision_model": config.vision_model,
        "image_model": config.image_model,
        "image_api_base": config.image_api_base,
        "image_api_key_masked": _mask_key(config.image_api_key),
        "has_image_api_key": bool(config.image_api_key),
        "image_reference_transport": config.image_reference_transport,
        "person_image_url": f"/uploads/person/{config.person_image_filename}" if config.person_image_filename else "",
        "has_person_image": bool(config.person_image_filename),
    }

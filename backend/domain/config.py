"""
API 配置模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class ModeBonusWeights(BaseModel):
    goal_bonus: int = 4
    color_bonus: int = 4
    style_bonus: int = 3


class RecommendationModeWeights(BaseModel):
    balanced: ModeBonusWeights = Field(default_factory=ModeBonusWeights)
    goal_first: ModeBonusWeights = Field(
        default_factory=lambda: ModeBonusWeights(goal_bonus=7, color_bonus=3, style_bonus=2)
    )
    wardrobe_first: ModeBonusWeights = Field(
        default_factory=lambda: ModeBonusWeights(goal_bonus=2, color_bonus=5, style_bonus=4)
    )


class LLMConfig(BaseModel):
    """LLM API 配置"""
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    # remove.bg 配置
    removebg_api_key: str = ""
    bg_removal_method: Literal["local", "removebg"] = "local"  # 本地 rembg 或 remove.bg API
    # Try-on 配置
    tryon_provider: Literal["disabled", "custom"] = "disabled"
    tryon_api_url: str = ""
    tryon_api_key: str = ""
    tryon_model: str = ""
    # 默认天气城市（用于首页与推荐页）
    weather_location: str = "上海, 上海市, 中国"
    # 用户星座配置（用于首页运势）
    zodiac_sign: str = ""
    # 推荐模式权重
    recommendation_mode_weights: RecommendationModeWeights = Field(default_factory=RecommendationModeWeights)
    # 服装录入（实验特性）：Person -> Canonical Garment
    experimental_garment_pipeline: bool = False  # 多件拆分 + canonical 生成总开关
    vision_model: str = "qwen3.8-flash"  # 多模态识别模型
    image_model: str = "qwen-image-3.0-pro"  # canonical 生图模型
    image_api_base: str = ""  # 留空复用 api_base
    image_api_key: str = ""  # 留空复用 api_key
    image_reference_transport: Literal["base64", "url"] = "base64"  # 参考图传输方式
    # 本人照片（设置页上传，用于 AI 试穿）
    person_image_filename: str = ""


class LLMConfigUpdate(BaseModel):
    """更新 LLM 配置的请求体"""
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    removebg_api_key: Optional[str] = None
    bg_removal_method: Optional[Literal["local", "removebg"]] = None
    tryon_provider: Optional[Literal["disabled", "custom"]] = None
    tryon_api_url: Optional[str] = None
    tryon_api_key: Optional[str] = None
    tryon_model: Optional[str] = None
    weather_location: Optional[str] = None
    zodiac_sign: Optional[str] = None
    recommendation_mode_weights: Optional[RecommendationModeWeights] = None
    experimental_garment_pipeline: Optional[bool] = None
    vision_model: Optional[str] = None
    image_model: Optional[str] = None
    image_api_base: Optional[str] = None
    image_api_key: Optional[str] = None
    image_reference_transport: Optional[Literal["base64", "url"]] = None


class AvailableModel(BaseModel):
    """可用模型"""
    id: str
    name: str


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[AvailableModel]

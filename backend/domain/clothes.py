"""
服装语义数据结构定义
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

CATEGORY_ALIASES = {
    "top": {"top", "tops", "上衣", "上装", "外套"},
    "bottom": {"bottom", "bottoms", "裤子", "下装", "裙子"},
    "shoes": {"shoes", "shoe", "鞋", "鞋子", "鞋履"},
    "accessory": {"accessory", "accessories", "饰品", "配饰", "首饰", "珠宝"},
}

CATEGORY_KEYWORDS = {
    "top": {
        "卫衣", "连帽", "hoodie", "jacket", "coat", "shirt", "t-shirt", "tee", "sweater", "cardigan", "blazer", "夹克", "衬衫", "毛衣", "t恤", "短袖", "长袖", "外套"
    },
    "bottom": {
        "裤", "裤子", "牛仔裤", "半身裙", "短裙", "裙", "jeans", "pants", "trousers", "shorts", "skirt"
    },
    "shoes": {
        "鞋", "鞋子", "球鞋", "运动鞋", "皮鞋", "靴", "sneaker", "shoe", "boots", "loafer", "heel", "sandals"
    },
    "accessory": {
        "配饰", "饰品", "项链", "手链", "耳环", "手表", "帽", "围巾", "眼镜", "腰带", "包", "necklace", "bracelet", "earring", "watch", "hat", "scarf", "belt", "bag", "sunglasses"
    },
}

CANONICAL_CATEGORIES = {"top", "bottom", "shoes", "accessory"}


def normalize_category_value(category: str) -> str:
    """将类别归一化为 top/bottom/shoes/accessory。"""
    value = (category or "").strip().lower()

    for canonical, aliases in CATEGORY_ALIASES.items():
        if value in aliases:
            return canonical

    for canonical, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in value for keyword in keywords):
            return canonical

    return value


def resolve_category_value(category: str, item: str = "", description: str = "") -> str:
    """结合 category/item/description 归一化类别。"""
    normalized = normalize_category_value(category)
    if normalized in CANONICAL_CATEGORIES:
        return normalized

    text = f"{category} {item} {description}".strip().lower()
    if text:
        for candidate in ("top", "bottom", "shoes", "accessory"):
            keywords = CATEGORY_KEYWORDS[candidate]
            if any(keyword in text for keyword in keywords):
                return candidate

    return normalized


class ClothesSemantics(BaseModel):
    """Gemini Vision 返回的语义数据结构"""
    category: str  # top | bottom | shoes | accessory
    item: str  # 具体衣物名称
    style_semantics: List[str]  # 风格标签
    season_semantics: List[str]  # 季节
    usage_semantics: List[str]  # 使用场景
    color_semantics: str  # 颜色语义
    description: str  # 一句话总结


class ClothesItem(BaseModel):
    """衣柜中的单个衣物"""
    id: int
    category: str
    item: str
    style_semantics: List[str]
    season_semantics: List[str]
    usage_semantics: List[str]
    color_semantics: str
    description: str
    image_url: str
    created_at: datetime


class ClothesCreate(BaseModel):
    """创建衣物的请求体"""
    category: str
    item: str
    style_semantics: List[str]
    season_semantics: List[str]
    usage_semantics: List[str]
    color_semantics: str
    description: str
    image_filename: str
    # 溯源（可选）：原始人物照 / 服装参考 crop / 生图原图
    source_image_filename: Optional[str] = None
    reference_image_filename: Optional[str] = None
    generated_image_filename: Optional[str] = None


class WardrobeResponse(BaseModel):
    """衣柜分类响应"""
    tops: List[ClothesItem]
    bottoms: List[ClothesItem]
    shoes: List[ClothesItem]
    accessories: List[ClothesItem]

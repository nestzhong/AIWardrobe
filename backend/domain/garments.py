"""
服装录入（Person -> Canonical Garment）数据结构定义
"""
from pydantic import BaseModel, Field
from typing import List, Optional

from domain.clothes import ClothesItem


class GarmentSpec(BaseModel):
    """单件服饰的规格描述（用于生图条件）。"""
    color: str = "unknown"
    neckline: str = "unknown"
    sleeve: str = "unknown"
    fit: str = "unknown"
    fabric: str = "unknown"
    length: str = "unknown"
    details: List[str] = Field(default_factory=list)


class GarmentCandidate(BaseModel):
    """多模态分析返回的单件服饰候选。"""
    garment_key: str
    category: str  # top | bottom | shoes | accessory
    item: str
    description: str = ""
    visible_area: str = ""
    pattern: str = ""
    graphics: str = ""
    spec: GarmentSpec = Field(default_factory=GarmentSpec)
    bbox: Optional[List[float]] = None  # 归一化 [x1, y1, x2, y2]


class GarmentDraftOut(BaseModel):
    """返回给前端的草稿视图。"""
    garment_key: str
    category: str
    item: str
    description: str = ""
    spec: GarmentSpec = Field(default_factory=GarmentSpec)
    bbox: Optional[List[float]] = None
    crop_url: str = ""
    generated_url: str = ""
    alpha_url: str = ""
    status: str = "pending"
    error: str = ""


class AnalyzeResponse(BaseModel):
    """POST /api/capture/analyze 响应。"""
    session_id: str
    source_image: str
    garments: List[GarmentDraftOut]


class GenerateRequest(BaseModel):
    """POST /api/capture/generate 请求。"""
    session_id: str
    garment_key: str


class GenerateResponse(BaseModel):
    """POST /api/capture/generate 响应。"""
    garment_key: str
    generated_url: str = ""
    alpha_url: str = ""
    spec: GarmentSpec = Field(default_factory=GarmentSpec)
    status: str = "pending"  # done | fallback | failed
    error: str = ""


class CommitItem(BaseModel):
    """待入库的单件服饰。"""
    garment_key: str
    category: str
    item: str
    description: str = ""
    style_semantics: List[str] = Field(default_factory=list)
    season_semantics: List[str] = Field(default_factory=list)
    usage_semantics: List[str] = Field(default_factory=list)
    color_semantics: str = ""
    selected: bool = True


class CommitRequest(BaseModel):
    """POST /api/capture/commit 请求。"""
    session_id: str
    items: List[CommitItem]


class CommitResponse(BaseModel):
    """POST /api/capture/commit 响应。"""
    created: List[ClothesItem]
    failed: List[dict]
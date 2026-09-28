"""
服装录入（Person -> Canonical Garment）Prompt 定义

设计目标：
1. 分析：让多模态模型把真人照片拆解成结构化服饰列表（含规格与 bbox）。
2. 生成：让生图模型把真人身上的每件衣服恢复为完整、规范的 canonical 商品图。
"""

# ---------------------------------------------------------------------------
# 1. 分析 Prompt
# ---------------------------------------------------------------------------

ANALYZE_PERSON_PROMPT = """
你是一个【服装分析 AI】。输入是一张真人照片（可能是全身照、半身照或单件服饰照）。

你的任务：识别照片中人物真实穿着的每一件服饰，并输出结构化信息，用于后续逐件生成规范的商品图。

只返回 JSON，不要任何解释、不要 markdown 代码块。

JSON Schema：
{
  "garments": [
    {
      "id": "garment_01",
      "category": "top | bottom | shoes | accessory",
      "item": "具体衣物名称，如 短袖T恤、牛仔裤、运动鞋、单肩包",
      "description": "一句话英文描述，如 black oversized short sleeve T-shirt",
      "visible_area": "front | back | side | partial",
      "pattern": "图案/纹理，如 solid black / horizontal stripes / floral print",
      "graphics": "印花或 logo，如 small white graphic on chest；没有则填 none",
      "spec": {
        "color": "主色，如 black",
        "neckline": "领型，如 crew neck / hooded / v-neck；不适用填 unknown",
        "sleeve": "袖长，如 short / long / sleeveless；不适用填 unknown",
        "fit": "版型，如 oversized / slim / regular",
        "fabric": "面料观感，如 cotton jersey / denim / leather",
        "length": "长度，如 hip-length / ankle-length",
        "details": ["其他可辨识细节，如 buttons、drawstring、pockets、logo"]
      },
      "bbox": [x1, y1, x2, y2]
    }
  ]
}

硬性约束：
- bbox 使用【归一化坐标】，取值 0 到 1，相对整张图片；x1,y1 为左上角，x2,y2 为右下角。尽量紧贴该件服饰。
- 只列出【真实穿着的服饰】，忽略人脸、皮肤、头发、背景。
- 同一物理服饰只出现一次；不要拆分同一件衣服。
- category 必须是 top / bottom / shoes / accessory 之一。
- 如果照片里只有一件单独的衣服（没有真人），也按同样格式输出，bbox 覆盖该衣物。
- 如果某个字段无法判断，填 "unknown"，不要编造。
- 无法识别任何服饰时返回 {"garments": []}。
""".strip()


# ---------------------------------------------------------------------------
# 2. Canonical 生成 Prompt
# ---------------------------------------------------------------------------

CANONICAL_PROMPT_TEMPLATE = """
Image 1 provides the full-body context. Image 2 is a close-up visual reference
of the garment. Use them as the ONLY visual reference.

Identify the {description} worn by the person.

Generate a complete standalone product image of THIS EXACT GARMENT.
Remove the person completely. Reconstruct the entire garment, including portions
that are occluded by the person's arms or body.

Preserve the original exactly:
- color
- fabric appearance
- graphic print
- logo
- collar
- neckline
- sleeve length
- sleeve shape
- hem shape
- seams
- pockets
- buttons
- proportions

Do NOT redesign the garment. The output must depict the SAME physical garment
shown in the reference photo, not a similar garment.
Do not invent or redesign any garment details.

Present the garment as {canonical_view}.
The entire garment must be visible.
No person. No mannequin. No hanger. No accessories. No additional garments.
Neutral studio background. Centered composition. Commercial fashion catalog photography.
""".strip()

CANONICAL_NEGATIVE_PROMPT = (
    "new garment, similar garment, changed color, changed pattern, invented logo, "
    "invented print, added pockets, removed pockets, changed sleeve length, "
    "changed collar shape, changed neckline, accessories, person, human, face, "
    "mannequin, hanger, multiple garments, duplicate garment, cut-off, cropped, "
    "text, letters, watermark, blurry, low quality"
)

# 按 category 的 canonical 视角
CANONICAL_VIEW_BY_CATEGORY = {
    "top": "a clean front-facing flat-lay product photograph with sleeves spread naturally",
    "bottom": "a clean front-facing flat-lay product photograph with both legs straightened",
    "shoes": "a standard product photograph shot from a three-quarter angle, the pair side by side",
    "accessory": "a clean front-facing product photograph",
}

# 外套类（归在 top 下）单独用「正面展开」视角
OUTERWEAR_KEYWORDS = {
    "jacket", "coat", "blazer", "parka", "windbreaker", "trench", "夹克", "外套", "大衣", "风衣", "西装", "羽绒"
}
OUTERWEAR_VIEW = "a clean front-facing flat-lay product photograph, laid open with the front fully visible"

# 尺寸：qwen 用 `*`，doubao 用 `x`
CANONICAL_SIZE_BY_CATEGORY = {
    "top": {"qwen": "1728*2368", "doubao": "1728x2304"},
    "bottom": {"qwen": "1728*2368", "doubao": "1728x2304"},
    "shoes": {"qwen": "2048*2048", "doubao": "2048x2048"},
    "accessory": {"qwen": "2048*2048", "doubao": "2048x2048"},
}

DEFAULT_QWEN_SIZE = "1728*2368"
DEFAULT_DOUBAO_SIZE = "1728x2304"


def resolve_canonical_view(category: str, item: str = "") -> str:
    """根据类别（和外套关键词）选择 canonical 视角描述。"""
    text = f"{category or ''} {item or ''}".lower()
    if any(keyword.lower() in text for keyword in OUTERWEAR_KEYWORDS):
        return OUTERWEAR_VIEW
    return CANONICAL_VIEW_BY_CATEGORY.get(
        (category or "").strip().lower(),
        CANONICAL_VIEW_BY_CATEGORY["top"],
    )


def resolve_canonical_size(category: str, provider: str) -> str:
    """根据类别与生图厂商返回尺寸字符串。"""
    normalized = (category or "").strip().lower()
    sizes = CANONICAL_SIZE_BY_CATEGORY.get(normalized)
    if not sizes:
        sizes = {"qwen": DEFAULT_QWEN_SIZE, "doubao": DEFAULT_DOUBAO_SIZE}
    if provider == "doubao":
        return sizes["doubao"]
    return sizes["qwen"]
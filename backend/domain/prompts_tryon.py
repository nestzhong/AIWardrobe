"""
AI 试穿（以图生图）Prompt 定义。

参考图顺序：Image 1 = 本人照片；Image 2..N = 单品服饰商品图。
要求：保留本人身份 / 面部 / 身形 / 姿态 / 背景，只把服饰替换为参考图中的单品。
"""

# 尺寸：qwen 用 `*`，doubao 用 `x`
TRYON_SIZE_BY_PROVIDER = {
    "qwen": "1728*2368",
    "doubao": "1728x2304",
}

# category -> 提示词中的英文槽位描述
TRYON_CATEGORY_LABEL = {
    "top": "upper body garment",
    "bottom": "lower body garment",
    "shoes": "pair of shoes",
    "accessory": "accessory",
}

TRYON_PROMPT_TEMPLATE = """
Image 1 is a photo of a person. The remaining images are product photos of garments.

Generate a photorealistic full-body photograph of the SAME person shown in Image 1, wearing exactly the garments from the reference images.

Garments to wear:
{garment_lines}

Preserve the person exactly:
- facial identity, facial features, hairstyle and hair color
- skin tone and body shape
- pose and camera angle
- original lighting and background

Preserve every garment exactly:
- color, pattern and print
- logo and graphics
- fabric appearance
- cut, length, sleeve and neckline
- proportions

Do NOT redesign or replace any garment. Do NOT change the person's face, body or pose.
The output must look like a real photograph of this person wearing these clothes.
No text, no letters, no watermark. No extra garments. No collage or split screen.
""".strip()

TRYON_NEGATIVE_PROMPT = (
    "different person, changed face, different face, changed hairstyle, altered body shape, "
    "extra clothing, additional garments, missing garment, wrong color, changed pattern, "
    "invented logo, extra limbs, distorted hands, distorted body, collage, split image, "
    "multiple people, mannequin, text, letters, watermark, blurry, low quality"
)


def build_tryon_prompt(garments) -> str:
    """按参考图顺序（Image 2 起）拼装服饰描述行。"""
    lines = []
    for index, garment in enumerate(garments, start=2):
        category = (garment.get("category") or "").strip().lower()
        label = TRYON_CATEGORY_LABEL.get(category, "garment")
        description = (garment.get("description") or garment.get("item") or "garment").strip()
        lines.append(f"- {label}: {description} (reference image {index})")

    if not lines:
        lines.append("- as shown in the reference images")

    return TRYON_PROMPT_TEMPLATE.format(garment_lines="\n".join(lines))


def resolve_tryon_size(provider: str) -> str:
    """按生图厂商返回竖构图尺寸字符串。"""
    if provider == "qwen":
        return TRYON_SIZE_BY_PROVIDER["qwen"]
    return TRYON_SIZE_BY_PROVIDER["doubao"]
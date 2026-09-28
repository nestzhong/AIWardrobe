"""
Canonical 生成编排：把真人身上的单件服饰恢复为完整商品图。

流程：双图参考(全身照 + 服装 crop) -> 生图 -> 下载 -> rembg 抠图 -> 存盘。
生图失败时降级为「对参考图抠图」，保证始终有可用图片。
"""
import uuid
from pathlib import Path
from typing import Any, Optional

from domain.garments import GarmentSpec
from domain.prompts_garment import (
    CANONICAL_NEGATIVE_PROMPT,
    CANONICAL_PROMPT_TEMPLATE,
    resolve_canonical_view,
)
from services.image_generation import generate_image
from storage.config_store import load_config

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
SOURCE_DIR = UPLOAD_DIR / "source"
REFERENCE_DIR = UPLOAD_DIR / "reference"
GENERATED_DIR = UPLOAD_DIR / "generated"


def ensure_capture_dirs() -> None:
    """确保录入相关目录存在。"""
    for directory in (SOURCE_DIR, REFERENCE_DIR, GENERATED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _save_bytes(directory: Path, image_bytes: bytes, suffix: str = "png") -> str:
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.{suffix}"
    with open(directory / filename, "wb") as f:
        f.write(image_bytes)
    return filename


def build_canonical_prompt(description: str, category: str, item: str) -> str:
    """根据服饰描述与类别构造 canonical 生成提示词。"""
    view = resolve_canonical_view(category, item)
    return CANONICAL_PROMPT_TEMPLATE.format(
        description=description or item or "garment",
        canonical_view=view,
    )


def build_description(spec: GarmentSpec, item: str, description: str = "") -> str:
    """当分析未给 description 时，用 spec 兜底拼一句英文描述。"""
    if description.strip():
        return description.strip()

    parts = []
    if spec.color and spec.color != "unknown":
        parts.append(spec.color)
    if spec.fit and spec.fit != "unknown":
        parts.append(spec.fit)
    parts.append(item or "garment")
    return " ".join(parts).strip()


def alpha_or_original(image_bytes: Optional[bytes]) -> Optional[bytes]:
    """对参考图做抠图；rembg 不可用时返回原图。"""
    if not image_bytes:
        return None
    try:
        from services.segment import remove_background

        return remove_background(image_bytes)
    except Exception:
        return image_bytes


async def generate_canonical_garment(
    source_image_bytes: bytes,
    reference_image_bytes: Optional[bytes],
    spec: GarmentSpec,
    category: str,
    item: str,
    description: str = "",
) -> dict[str, Any]:
    """
    生成单件 canonical 商品图。

    Returns:
        {
          "generated_filename": str | None,  # 生图原始输出（含背景）
          "alpha_filename": str | None,      # 最终透明 PNG
          "status": "done" | "fallback" | "failed",
          "error": str,
        }
    """
    ensure_capture_dirs()
    config = load_config()

    prompt = build_canonical_prompt(
        build_description(spec, item, description), category, item
    )

    # 双图参考：图1 = 全身照（上下文），图2 = 服装 crop（细节）
    references = [source_image_bytes]
    if reference_image_bytes:
        references.append(reference_image_bytes)

    generated_filename: Optional[str] = None

    if config.image_model:
        try:
            generated_bytes = await generate_image(
                prompt=prompt,
                model=config.image_model,
                category=category,
                reference_images=references,
                negative_prompt=CANONICAL_NEGATIVE_PROMPT,
                watermark=False,
            )
            generated_filename = _save_bytes(GENERATED_DIR, generated_bytes)

            alpha = alpha_or_original(generated_bytes)
            if alpha:
                alpha_filename = _save_bytes(UPLOAD_DIR, alpha)
                return {
                    "generated_filename": generated_filename,
                    "alpha_filename": alpha_filename,
                    "status": "done",
                    "error": "",
                }
        except Exception as exc:  # noqa: BLE001 - 需要降级而非中断
            error_message = str(exc)
        else:
            error_message = ""
    else:
        error_message = "未配置生图模型（image_model），已降级为抠图"

    # 降级：对服装参考图（无则全图）抠图
    fallback_source = reference_image_bytes or source_image_bytes
    alpha = alpha_or_original(fallback_source)
    if alpha:
        alpha_filename = _save_bytes(UPLOAD_DIR, alpha)
        return {
            "generated_filename": generated_filename,
            "alpha_filename": alpha_filename,
            "status": "fallback",
            "error": error_message,
        }

    return {
        "generated_filename": generated_filename,
        "alpha_filename": None,
        "status": "failed",
        "error": error_message or "抠图失败",
    }
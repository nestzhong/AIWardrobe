"""
服装录入 API（实验特性）：Person -> Canonical Garment

- POST /api/capture/analyze   人物照 -> 服饰列表 + crop
- POST /api/capture/generate  单件 -> canonical 商品图
- POST /api/capture/commit    批量入库
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from domain.clothes import ClothesCreate, resolve_category_value
from domain.garments import (
    AnalyzeResponse,
    CommitRequest,
    CommitResponse,
    GarmentDraftOut,
    GarmentSpec,
    GenerateRequest,
    GenerateResponse,
)
from services.garment_analysis import analyze_person_image
from services.garment_canonical import (
    GENERATED_DIR,
    REFERENCE_DIR,
    SOURCE_DIR,
    alpha_or_original,
    generate_canonical_garment,
)
from services.garment_crop import crop_garment_reference, flatten_on_white
from services.gateway_utils import guess_image_mime
from services.openai_compatible import analyze_clothes_openai
from storage.config_store import load_config
from storage.db import (
    add_clothes,
    create_garment_draft,
    create_garment_session,
    get_clothes_by_id,
    get_garment_draft,
    get_garment_session,
    update_garment_draft,
)

router = APIRouter()

ALLOWED_CATEGORIES = {"top", "bottom", "shoes", "accessory"}
_EXT_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _safe_name(filename: str) -> str:
    """只取文件名，避免路径穿越。"""
    return Path(filename).name


def _ensure_dirs() -> None:
    """确保本模块使用的源图/参考图目录存在。"""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)


def _upload_url(directory_name: str, filename: str) -> str:
    if not filename:
        return ""
    if directory_name:
        return f"/uploads/{directory_name}/{filename}"
    return f"/uploads/{filename}"


def _read_first_existing(candidates) -> bytes:
    """按顺序返回第一个存在的文件内容。"""
    for path in candidates:
        try:
            if path and path.is_file():
                return path.read_bytes()
        except OSError:
            continue
    return None


async def _analyze_semantics(draft: dict, image_filename: str):
    """
    用识别模型对最终商品图产出中文语义（风格/季节/场景/颜色/描述）。

    优先用生图原图（带背景），其次透明成品图（铺白底），再次服装 crop。
    失败时返回 None（不阻塞入库）。
    """
    config = load_config()

    semantic_bytes = _read_first_existing(
        [
            GENERATED_DIR / _safe_name(draft["generated_filename"] or "")
            if draft.get("generated_filename")
            else None,
            (SOURCE_DIR.parent / _safe_name(image_filename)) if image_filename else None,
            REFERENCE_DIR / _safe_name(draft["crop_filename"] or "")
            if draft.get("crop_filename")
            else None,
        ]
    )

    if not semantic_bytes:
        return None

    try:
        return await analyze_clothes_openai(
            flatten_on_white(semantic_bytes),
            model=config.vision_model,
        )
    except Exception as exc:  # noqa: BLE001 - 语义失败不应阻塞入库
        print(f"⚠️ 服装语义分析失败，使用空语义: {exc}")
        return None


@router.post("/capture/analyze", response_model=AnalyzeResponse)
async def analyze_capture(file: UploadFile = File(...)):
    """上传人物照，拆解出服饰列表并生成参考 crop。"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="图片内容为空")

    _ensure_dirs()

    mime = file.content_type or guess_image_mime(raw_bytes)
    ext = _EXT_BY_MIME.get(mime, "jpg")
    source_filename = f"{uuid.uuid4()}.{ext}"
    with open(SOURCE_DIR / source_filename, "wb") as f:
        f.write(raw_bytes)

    try:
        candidates = await analyze_person_image(raw_bytes, mime=mime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"服饰识别失败: {exc}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"服饰识别异常: {exc}")

    session_id = str(uuid.uuid4())
    garments_out = []
    analysis_payload = {"garments": []}

    for candidate in candidates:
        crop_bytes = crop_garment_reference(raw_bytes, candidate.bbox)
        crop_filename = ""
        if crop_bytes:
            crop_filename = f"{session_id}_{candidate.garment_key}.png"
            with open(REFERENCE_DIR / crop_filename, "wb") as f:
                f.write(crop_bytes)

        await create_garment_draft(
            session_id=session_id,
            garment_key=candidate.garment_key,
            category=candidate.category,
            item=candidate.item,
            description=candidate.description,
            spec=candidate.spec.model_dump(),
            bbox=candidate.bbox,
            crop_filename=crop_filename or None,
        )

        analysis_payload["garments"].append(candidate.model_dump())
        garments_out.append(
            GarmentDraftOut(
                garment_key=candidate.garment_key,
                category=candidate.category,
                item=candidate.item,
                description=candidate.description,
                spec=candidate.spec,
                bbox=candidate.bbox,
                crop_url=_upload_url("reference", crop_filename),
                status="pending",
            )
        )

    await create_garment_session(session_id, source_filename, analysis_payload)

    return AnalyzeResponse(
        session_id=session_id,
        source_image=_upload_url("source", source_filename),
        garments=garments_out,
    )


@router.post("/capture/generate", response_model=GenerateResponse)
async def generate_capture(request: GenerateRequest):
    """对单件服饰执行 canonical 生成。"""
    session = await get_garment_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="录入会话不存在")

    draft = await get_garment_draft(request.session_id, request.garment_key)
    if not draft:
        raise HTTPException(status_code=404, detail="服饰草稿不存在")

    source_path = SOURCE_DIR / _safe_name(session["source_filename"])
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="原始照片不存在")

    reference_bytes = None
    if draft["crop_filename"]:
        reference_path = REFERENCE_DIR / _safe_name(draft["crop_filename"])
        if reference_path.is_file():
            reference_bytes = reference_path.read_bytes()

    spec = GarmentSpec(**(draft["spec"] or {}))

    await update_garment_draft(request.session_id, request.garment_key, status="generating")

    result = await generate_canonical_garment(
        source_image_bytes=source_path.read_bytes(),
        reference_image_bytes=reference_bytes,
        spec=spec,
        category=draft["category"],
        item=draft["item"],
        description=draft["description"],
    )

    await update_garment_draft(
        request.session_id,
        request.garment_key,
        status=result["status"],
        generated_filename=result["generated_filename"],
        alpha_filename=result["alpha_filename"],
        error=result["error"],
    )

    return GenerateResponse(
        garment_key=request.garment_key,
        generated_url=_upload_url("generated", result["generated_filename"] or ""),
        alpha_url=_upload_url("", result["alpha_filename"] or ""),
        spec=spec,
        status=result["status"],
        error=result["error"],
    )


@router.post("/capture/commit", response_model=CommitResponse)
async def commit_capture(request: CommitRequest):
    """把选中的草稿批量写入衣柜。"""
    session = await get_garment_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="录入会话不存在")

    created = []
    failed = []

    for item in request.items:
        if not item.selected:
            continue

        draft = await get_garment_draft(request.session_id, item.garment_key)
        if not draft:
            failed.append({"garment_key": item.garment_key, "error": "草稿不存在"})
            continue

        image_filename = draft["alpha_filename"]
        if not image_filename and draft["crop_filename"]:
            # 兜底：对 crop 抠图
            crop_path = REFERENCE_DIR / _safe_name(draft["crop_filename"])
            if crop_path.is_file():
                alpha = alpha_or_original(crop_path.read_bytes())
                if alpha:
                    image_filename = f"{uuid.uuid4()}.png"
                    with open(SOURCE_DIR.parent / image_filename, "wb") as f:
                        f.write(alpha)

        if not image_filename:
            failed.append({"garment_key": item.garment_key, "error": "缺少可用图片，请先生成"})
            continue

        category = resolve_category_value(item.category, item.item, item.description)
        if category not in ALLOWED_CATEGORIES:
            category = "accessory"

        # 用识别模型补齐中文语义（风格/季节/场景/颜色/描述）；失败不阻塞入库
        semantics = await _analyze_semantics(draft, image_filename)

        style_semantics = item.style_semantics or (semantics.style_semantics if semantics else [])
        season_semantics = item.season_semantics or (semantics.season_semantics if semantics else [])
        usage_semantics = item.usage_semantics or (semantics.usage_semantics if semantics else [])
        color_semantics = item.color_semantics or (semantics.color_semantics if semantics else "")
        description = (
            semantics.description
            if semantics and semantics.description
            else item.description
        )

        try:
            clothes_id = await add_clothes(
                ClothesCreate(
                    category=category,
                    item=item.item,
                    style_semantics=style_semantics,
                    season_semantics=season_semantics,
                    usage_semantics=usage_semantics,
                    color_semantics=color_semantics,
                    description=description,
                    image_filename=image_filename,
                    source_image_filename=_safe_name(session["source_filename"]),
                    reference_image_filename=_safe_name(draft["crop_filename"] or "") or None,
                    generated_image_filename=_safe_name(draft["generated_filename"] or "") or None,
                )
            )
            clothes = await get_clothes_by_id(clothes_id)
            if clothes:
                created.append(clothes)
            else:
                failed.append({"garment_key": item.garment_key, "error": "保存后读取失败"})
        except Exception as exc:  # noqa: BLE001
            failed.append({"garment_key": item.garment_key, "error": str(exc)})

    return CommitResponse(created=created, failed=failed)
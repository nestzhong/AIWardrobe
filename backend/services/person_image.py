"""
本人照片存储：设置页上传，供 AI 试穿使用。

文件统一存放在 uploads/person/ 下（单文件覆盖），文件名记录在配置的
person_image_filename 中，静态资源经 /uploads/person/ 暴露。
"""
from pathlib import Path
from typing import Optional

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
PERSON_DIR = UPLOAD_DIR / "person"

_EXT_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _ensure_dir() -> None:
    PERSON_DIR.mkdir(parents=True, exist_ok=True)


def _clear_existing() -> None:
    """删除已存在的本人照片，保证只保留一份。"""
    _ensure_dir()
    for path in PERSON_DIR.glob("person.*"):
        try:
            path.unlink()
        except OSError:
            continue


def save_person_image(image_bytes: bytes, mime: str = "") -> str:
    """保存本人照片（覆盖旧文件），返回文件名。"""
    _ensure_dir()
    _clear_existing()
    ext = _EXT_BY_MIME.get((mime or "").lower(), "png")
    filename = f"person.{ext}"
    with open(PERSON_DIR / filename, "wb") as f:
        f.write(image_bytes)
    return filename


def clear_person_image() -> None:
    """删除本人照片文件。"""
    _clear_existing()


def person_image_url(filename: str) -> str:
    """返回可访问的静态资源路径。"""
    if not filename:
        return ""
    return f"/uploads/person/{filename}"


def load_person_image_bytes(filename: str) -> Optional[bytes]:
    """读取本人照片字节；不存在返回 None。"""
    name = Path(filename or "").name
    if not name:
        return None
    path = PERSON_DIR / name
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None
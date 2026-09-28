"""
数据库连接和 CRUD 操作
"""
import aiosqlite
import json
from pathlib import Path
from typing import Any, List, Optional
from datetime import datetime
from domain.clothes import ClothesItem, ClothesCreate
from storage.models import (
    CLOTHES_TABLE_SQL,
    CLOTHES_INDEX_SQL,
    HOROSCOPE_RECORDS_TABLE_SQL,
    HOROSCOPE_RECORDS_INDEX_SQL,
    WEATHER_CACHE_TABLE_SQL,
    WEATHER_CACHE_INDEX_SQL,
    WEATHER_CACHE_UPDATED_AT_INDEX_SQL,
    LOCATION_CACHE_TABLE_SQL,
    LOCATION_CACHE_INDEX_SQL,
    GARMENT_SESSIONS_TABLE_SQL,
    GARMENT_DRAFTS_TABLE_SQL,
    GARMENT_DRAFTS_INDEX_SQL,
    CLOTHES_TRACEABILITY_COLUMNS,
)

# 数据库文件路径
# 优先使用环境变量，方便 Docker 挂载 volume
import os
_default_path = Path(__file__).parent.parent / "wardrobe.db"
DB_PATH = Path(os.getenv("DB_FILE_PATH", _default_path))


async def init_db():
    """初始化数据库，创建表和索引"""
    # 确保数据库文件的父目录存在
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CLOTHES_TABLE_SQL)
        await db.execute(CLOTHES_INDEX_SQL)
        await db.execute(HOROSCOPE_RECORDS_TABLE_SQL)
        await db.execute(HOROSCOPE_RECORDS_INDEX_SQL)
        await db.execute(WEATHER_CACHE_TABLE_SQL)
        await db.execute(WEATHER_CACHE_INDEX_SQL)
        await db.execute(WEATHER_CACHE_UPDATED_AT_INDEX_SQL)
        await db.execute(LOCATION_CACHE_TABLE_SQL)
        await db.execute(LOCATION_CACHE_INDEX_SQL)
        await db.execute(GARMENT_SESSIONS_TABLE_SQL)
        await db.execute(GARMENT_DRAFTS_TABLE_SQL)
        await db.execute(GARMENT_DRAFTS_INDEX_SQL)

        # 老库平滑升级：补齐 clothes 表的溯源列
        cursor = await db.execute("PRAGMA table_info(clothes)")
        existing_columns = {row[1] for row in await cursor.fetchall()}
        for column_name, column_type in CLOTHES_TRACEABILITY_COLUMNS:
            if column_name not in existing_columns:
                await db.execute(
                    f"ALTER TABLE clothes ADD COLUMN {column_name} {column_type}"
                )

        await db.commit()


async def add_clothes(clothes: ClothesCreate) -> int:
    """
    添加衣物到数据库
    
    Returns:
        新创建的衣物 ID
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO clothes (
                category, item, style_semantics, season_semantics,
                usage_semantics, color_semantics, description, image_filename,
                source_image_filename, reference_image_filename, generated_image_filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clothes.category,
                clothes.item,
                json.dumps(clothes.style_semantics),
                json.dumps(clothes.season_semantics),
                json.dumps(clothes.usage_semantics),
                clothes.color_semantics,
                clothes.description,
                clothes.image_filename,
                clothes.source_image_filename,
                clothes.reference_image_filename,
                clothes.generated_image_filename,
            )
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_clothes() -> List[ClothesItem]:
    """获取所有衣物"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM clothes ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        
        return [_row_to_clothes_item(row) for row in rows]


async def get_clothes_by_category(category: str) -> List[ClothesItem]:
    """按类别获取衣物"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM clothes WHERE category = ? ORDER BY created_at DESC",
            (category,)
        )
        rows = await cursor.fetchall()
        
        return [_row_to_clothes_item(row) for row in rows]


async def get_clothes_by_id(clothes_id: int) -> Optional[ClothesItem]:
    """按 ID 获取衣物"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM clothes WHERE id = ?",
            (clothes_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            return _row_to_clothes_item(row)
        return None


async def delete_clothes(clothes_id: int) -> bool:
    """删除衣物"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM clothes WHERE id = ?",
            (clothes_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_clothes(clothes_id: int, clothes: ClothesCreate) -> bool:
    """更新衣物信息"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE clothes 
            SET category = ?, item = ?, style_semantics = ?, 
                season_semantics = ?, usage_semantics = ?, 
                color_semantics = ?, description = ?
            WHERE id = ?
            """,
            (
                clothes.category,
                clothes.item,
                json.dumps(clothes.style_semantics),
                json.dumps(clothes.season_semantics),
                json.dumps(clothes.usage_semantics),
                clothes.color_semantics,
                clothes.description,
                clothes_id
            )
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_horoscope_record(record_date: str, zodiac_sign: str) -> Optional[dict[str, Any]]:
    """按日期和星座获取缓存的运势记录。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM horoscope_records
            WHERE record_date = ? AND zodiac_sign = ?
            LIMIT 1
            """,
            (record_date, zodiac_sign),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_horoscope_record(row)


async def upsert_horoscope_source(
    record_date: str,
    zodiac_sign: str,
    zodiac_name: str,
    source_provider: str,
    source_payload: dict[str, Any],
) -> int:
    """
    写入或更新星座原始数据（aztro/fallback）。
    已存在记录时，保留现有推理状态与推理内容。
    """
    payload_json = json.dumps(source_payload, ensure_ascii=False)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id FROM horoscope_records
            WHERE record_date = ? AND zodiac_sign = ?
            LIMIT 1
            """,
            (record_date, zodiac_sign),
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """
                UPDATE horoscope_records
                SET zodiac_name = ?,
                    source_provider = ?,
                    source_payload = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (zodiac_name, source_provider, payload_json, existing["id"]),
            )
            await db.commit()
            return int(existing["id"])

        cursor = await db.execute(
            """
            INSERT INTO horoscope_records (
                record_date, zodiac_sign, zodiac_name, source_provider, source_payload, llm_status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (record_date, zodiac_sign, zodiac_name, source_provider, payload_json),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def update_horoscope_inference(
    record_id: int,
    llm_status: str,
    llm_reasoning: Optional[str] = None,
    llm_error: Optional[str] = None,
) -> None:
    """更新运势推理状态与结果。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE horoscope_records
            SET llm_status = ?,
                llm_reasoning = ?,
                llm_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (llm_status, llm_reasoning, llm_error, record_id),
        )
        await db.commit()


async def get_weather_cache(location_key: str, bucket_start: str) -> Optional[dict[str, Any]]:
    """按地点+时间桶获取天气缓存。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM weather_cache
            WHERE location_key = ? AND bucket_start = ?
            LIMIT 1
            """,
            (location_key, bucket_start),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_weather_cache(row)


async def get_latest_weather_cache(location_key: str) -> Optional[dict[str, Any]]:
    """按地点获取最新一条天气缓存。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM weather_cache
            WHERE location_key = ?
            ORDER BY bucket_start DESC, updated_at DESC, id DESC
            LIMIT 1
            """,
            (location_key,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_weather_cache(row)


async def upsert_weather_cache(
    location_key: str,
    bucket_start: str,
    payload: dict[str, Any],
) -> int:
    """写入或更新天气缓存。"""
    payload_json = json.dumps(payload, ensure_ascii=False)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id FROM weather_cache
            WHERE location_key = ? AND bucket_start = ?
            LIMIT 1
            """,
            (location_key, bucket_start),
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """
                UPDATE weather_cache
                SET payload = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (payload_json, existing["id"]),
            )
            await db.commit()
            return int(existing["id"])

        cursor = await db.execute(
            """
            INSERT INTO weather_cache (location_key, bucket_start, payload)
            VALUES (?, ?, ?)
            """,
            (location_key, bucket_start, payload_json),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def cleanup_weather_cache(max_rows: int = 1000) -> None:
    """限制天气缓存表大小，保留最新记录。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM weather_cache
            WHERE id NOT IN (
                SELECT id FROM weather_cache
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
            )
            """,
            (max_rows,),
        )
        await db.commit()


async def get_location_cache(query_key: str) -> Optional[dict[str, Any]]:
    """按归一化地点文本获取解析缓存。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM location_cache
            WHERE query_key = ?
            LIMIT 1
            """,
            (query_key,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "query_key": row["query_key"],
            "resolved_location": row["resolved_location"],
            "display_location": row["display_location"],
        }


async def upsert_location_cache(
    query_key: str,
    resolved_location: str,
    display_location: str,
) -> int:
    """写入或更新地点解析缓存。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id FROM location_cache
            WHERE query_key = ?
            LIMIT 1
            """,
            (query_key,),
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                """
                UPDATE location_cache
                SET resolved_location = ?,
                    display_location = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (resolved_location, display_location, existing["id"]),
            )
            await db.commit()
            return int(existing["id"])

        cursor = await db.execute(
            """
            INSERT INTO location_cache (query_key, resolved_location, display_location)
            VALUES (?, ?, ?)
            """,
            (query_key, resolved_location, display_location),
        )
        await db.commit()
        return int(cursor.lastrowid)


# ---------------------------------------------------------------------------
# 服装录入（实验特性）：Person -> Canonical Garment
# ---------------------------------------------------------------------------

async def create_garment_session(
    session_id: str,
    source_filename: str,
    analysis: dict[str, Any],
) -> None:
    """创建一次服装录入会话。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO garment_sessions (id, source_filename, analysis_json)
            VALUES (?, ?, ?)
            """,
            (session_id, source_filename, json.dumps(analysis, ensure_ascii=False)),
        )
        await db.commit()


async def get_garment_session(session_id: str) -> Optional[dict[str, Any]]:
    """获取服装录入会话。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM garment_sessions WHERE id = ? LIMIT 1",
            (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "source_filename": row["source_filename"],
            "analysis": json.loads(row["analysis_json"] or "{}"),
            "created_at": row["created_at"],
        }


async def create_garment_draft(
    session_id: str,
    garment_key: str,
    category: str,
    item: str,
    description: str,
    spec: dict[str, Any],
    bbox: Optional[list[float]],
    crop_filename: Optional[str],
) -> int:
    """创建单件服饰草稿。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO garment_drafts (
                session_id, garment_key, category, item, description,
                spec_json, bbox_json, crop_filename, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                session_id,
                garment_key,
                category,
                item,
                description,
                json.dumps(spec or {}, ensure_ascii=False),
                json.dumps(bbox) if bbox is not None else None,
                crop_filename,
            ),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_garment_draft(
    session_id: str, garment_key: str
) -> Optional[dict[str, Any]]:
    """按会话 + garment_key 获取草稿。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM garment_drafts
            WHERE session_id = ? AND garment_key = ?
            LIMIT 1
            """,
            (session_id, garment_key),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_garment_draft(row)


async def list_garment_drafts(session_id: str) -> List[dict[str, Any]]:
    """列出某会话下的全部草稿。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM garment_drafts
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_garment_draft(row) for row in rows]


async def update_garment_draft(
    session_id: str,
    garment_key: str,
    *,
    status: Optional[str] = None,
    generated_filename: Optional[str] = None,
    alpha_filename: Optional[str] = None,
    crop_filename: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """更新草稿状态与产物文件名。"""
    fields: list[str] = []
    values: list[Any] = []

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if generated_filename is not None:
        fields.append("generated_filename = ?")
        values.append(generated_filename)
    if alpha_filename is not None:
        fields.append("alpha_filename = ?")
        values.append(alpha_filename)
    if crop_filename is not None:
        fields.append("crop_filename = ?")
        values.append(crop_filename)
    if error is not None:
        fields.append("error = ?")
        values.append(error)

    if not fields:
        return False

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.extend([session_id, garment_key])

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"UPDATE garment_drafts SET {', '.join(fields)} "
            "WHERE session_id = ? AND garment_key = ?",
            tuple(values),
        )
        await db.commit()
        return cursor.rowcount > 0


def _row_to_garment_draft(row: aiosqlite.Row) -> dict[str, Any]:
    """将数据库行转换为服饰草稿字典。"""
    bbox = None
    if row["bbox_json"]:
        try:
            bbox = json.loads(row["bbox_json"])
        except (json.JSONDecodeError, TypeError):
            bbox = None
    return {
        "id": int(row["id"]),
        "session_id": row["session_id"],
        "garment_key": row["garment_key"],
        "category": row["category"] or "",
        "item": row["item"] or "",
        "description": row["description"] or "",
        "spec": json.loads(row["spec_json"] or "{}"),
        "bbox": bbox,
        "crop_filename": row["crop_filename"],
        "generated_filename": row["generated_filename"],
        "alpha_filename": row["alpha_filename"],
        "status": row["status"] or "pending",
        "error": row["error"] or "",
    }


def _row_to_clothes_item(row: aiosqlite.Row) -> ClothesItem:
    """将数据库行转换为 ClothesItem"""
    return ClothesItem(
        id=row["id"],
        category=row["category"],
        item=row["item"],
        style_semantics=json.loads(row["style_semantics"] or "[]"),
        season_semantics=json.loads(row["season_semantics"] or "[]"),
        usage_semantics=json.loads(row["usage_semantics"] or "[]"),
        color_semantics=row["color_semantics"] or "",
        description=row["description"] or "",
        image_url=f"/uploads/{row['image_filename']}",
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
    )


def _row_to_horoscope_record(row: aiosqlite.Row) -> dict[str, Any]:
    """将数据库行转换为星座记录字典。"""
    return {
        "id": int(row["id"]),
        "record_date": row["record_date"],
        "zodiac_sign": row["zodiac_sign"],
        "zodiac_name": row["zodiac_name"],
        "source_provider": row["source_provider"] or "unknown",
        "source_payload": json.loads(row["source_payload"] or "{}"),
        "llm_status": row["llm_status"] or "pending",
        "llm_reasoning": row["llm_reasoning"] or "",
        "llm_error": row["llm_error"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_weather_cache(row: aiosqlite.Row) -> dict[str, Any]:
    """将数据库行转换为天气缓存字典。"""
    return {
        "id": int(row["id"]),
        "location_key": row["location_key"],
        "bucket_start": row["bucket_start"],
        "payload": json.loads(row["payload"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

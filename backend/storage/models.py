"""
SQLite 数据库模型定义
使用 aiosqlite 进行异步操作
"""

# 数据库表结构
CLOTHES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS clothes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,  -- top, bottom, shoes, accessory
    item TEXT NOT NULL,
    style_semantics TEXT,  -- JSON array
    season_semantics TEXT,  -- JSON array
    usage_semantics TEXT,  -- JSON array
    color_semantics TEXT,
    description TEXT,
    image_filename TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# 创建索引用于快速查询
CLOTHES_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_clothes_category ON clothes(category);
"""

# 星座运势缓存表
HOROSCOPE_RECORDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS horoscope_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT NOT NULL,  -- YYYY-MM-DD
    zodiac_sign TEXT NOT NULL,
    zodiac_name TEXT NOT NULL,
    source_provider TEXT NOT NULL,  -- aztro / fallback
    source_payload TEXT NOT NULL,  -- JSON
    llm_status TEXT NOT NULL DEFAULT 'pending',  -- pending / done / failed / skipped
    llm_reasoning TEXT,
    llm_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(record_date, zodiac_sign)
);
"""

HOROSCOPE_RECORDS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_horoscope_records_date_sign
ON horoscope_records(record_date, zodiac_sign);
"""

# 天气缓存表（按地点+时间桶）
WEATHER_CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key TEXT NOT NULL,
    bucket_start TEXT NOT NULL,  -- YYYY-MM-DDTHH
    payload TEXT NOT NULL,  -- JSON WeatherInfo
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(location_key, bucket_start)
);
"""

WEATHER_CACHE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_weather_cache_key_bucket ON weather_cache(location_key, bucket_start);
"""

WEATHER_CACHE_UPDATED_AT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_weather_cache_updated_at ON weather_cache(updated_at);
"""

# 地点解析缓存：文本地点 -> 坐标 + 展示名
LOCATION_CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS location_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_key TEXT NOT NULL UNIQUE,
    resolved_location TEXT NOT NULL,
    display_location TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

LOCATION_CACHE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_location_cache_query_key ON location_cache(query_key);
"""


# ---------------------------------------------------------------------------
# 服装录入（实验特性）：Person -> Canonical Garment
# ---------------------------------------------------------------------------

# 录入会话：一张人物照一次分析
GARMENT_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS garment_sessions (
    id TEXT PRIMARY KEY,
    source_filename TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# 会话下的单件服饰草稿
GARMENT_DRAFTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS garment_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    garment_key TEXT NOT NULL,
    category TEXT,
    item TEXT,
    description TEXT,
    spec_json TEXT,
    bbox_json TEXT,
    crop_filename TEXT,
    generated_filename TEXT,
    alpha_filename TEXT,
    status TEXT DEFAULT 'pending',
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, garment_key)
);
"""

GARMENT_DRAFTS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_garment_drafts_session ON garment_drafts(session_id);
"""

# clothes 表溯源列（老库需 ALTER TABLE 补齐）
CLOTHES_TRACEABILITY_COLUMNS = (
    ("source_image_filename", "TEXT"),
    ("reference_image_filename", "TEXT"),
    ("generated_image_filename", "TEXT"),
)

"""
数据库配置辅助（从 .env 读取），供其它模块导入DATABASE_URL
（已从原位置移动到 postgres_data 包中）
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 默认使用 asyncpg 适配异步 SQLAlchemy；运行时请通过环境变量覆盖（.env 或进程环境）
# 示例：postgresql+asyncpg://welegal_user:password@localhost:5432/welegal_db
DEFAULT_DB = 'postgresql+asyncpg://welegal_user:REPLACE_ME@localhost:5432/welegal_db'

def _normalize_url(url: str) -> str:
    """确保返回的 URL 明确使用 asyncpg 驱动（`+asyncpg`）。

    规则：
    - 如果 URL 已包含 `+asyncpg`，保持不变。
    - 如果 URL 包含 `+psycopg` 或 `psycopg`，优先保留（不自动修改），但会记录提示。
    - 如果 URL 看起来是 `postgresql://...`（未指定驱动），则改为 `postgresql+asyncpg://...`。
    """
    if not url:
        return DEFAULT_DB
    lower = url.lower()
    if '+asyncpg' in lower:
        return url
    if '+psycopg' in lower or 'psycopg' in lower and '+asyncpg' not in lower:
        # 保持用户显式指定的 psycopg 驱动，但记录以便运维注意
        try:
            import logging
            logging.getLogger(__name__).warning("数据库 URL 使用 psycopg 驱动：%s", url.split('@')[0] + '@...')
        except Exception:
            pass
        return url
    # 若未指定驱动，则插入 +asyncpg
    if lower.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    return url


def get_database_url() -> str:
    """读取环境变量并返回规范化的 DATABASE_URL（优先使用 asyncpg）。"""
    env_url = os.getenv('DATABASE_URL')
    if env_url:
        return _normalize_url(env_url)
    return DEFAULT_DB

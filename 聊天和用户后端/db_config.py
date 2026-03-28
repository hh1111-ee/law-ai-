"""兼容 shim：从 `postgres_data.db_config` 导出数据库配置。

原文件已移动到 `postgres_data/db_config.py`，此处保留导出以保持向后兼容。
"""

from postgres_data.db_config import DATABASE_URL, get_database_url  # noqa: F401

__all__ = ["DATABASE_URL", "get_database_url"]

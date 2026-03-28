"""兼容 shim：从 `postgres_data.db_session` 导出 SQLAlchemy 变量与 `get_db`。

原实现已移动到 `postgres_data/db_session.py`，此处保留导出以保持向后兼容。
"""

from postgres_data.db_session import engine, SessionLocal, Base, get_db  # noqa: F401

__all__ = ["engine", "SessionLocal", "Base", "get_db"]

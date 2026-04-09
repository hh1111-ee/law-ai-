"""兼容 shim：从 `postgres_data.models` 导出模型定义。

原文件已移动到 `postgres_data/models.py`，此处保留导出以保持向后兼容。
"""

from postgres_data.models import *  # noqa: F401,F403

__all__ = [
    "User",
    "Post",
    "Case",
]

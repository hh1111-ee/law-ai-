import os
from dotenv import load_dotenv

# 使用异步 SQLAlchemy（asyncpg 驱动）
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

load_dotenv()

# 统一从 db_config 获取 URL
from .db_config import get_database_url

DATABASE_URL = os.getenv("DATABASE_URL", get_database_url())

# 异步引擎配置。生产环境可根据需要调整 pool/timeout 等参数。
def _create_engine_with_fallback(url: str):
    """为确保在 Windows/Proactor 环境下优先使用 asyncpg：
    - 强制将普通的 `postgresql://` 或 `+psycopg` URL 规范为 `+asyncpg`。
    - 记录所用 URL（脱敏后）以便调试。
    该实现避免自动回退到 psycopg，从而避免 ProactorEventLoop 兼容性问题。
    """
    import logging
    logger = logging.getLogger(__name__)
    final_url = url or ''
    lower = final_url.lower()
    # 如果明确使用 psycopg，则替换为 asyncpg（优先 asyncpg）
    if '+psycopg' in lower:
        final_url = final_url.replace('+psycopg', '+asyncpg')
    # 未指定驱动的 postgres:// -> 使用 asyncpg
    if lower.startswith('postgresql://') and '+asyncpg' not in lower:
        final_url = final_url.replace('postgresql://', 'postgresql+asyncpg://', 1)

    try:
        logger.info("Creating async engine using DB URL: %s", (final_url.split('@')[0] + '@...') if '@' in final_url else final_url)
        return create_async_engine(final_url, future=True)
    except Exception:
        # 若出现任何创建错误，让上层看到原始异常以便诊断
        logger.exception("create_async_engine failed for URL: %s", final_url)
        raise

engine = _create_engine_with_fallback(DATABASE_URL)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

# 仍然为模型定义保留 Base
Base = declarative_base()

async def get_db():
    """异步依赖：在 FastAPI 中使用 `Depends(get_db)` 获取 `AsyncSession`。"""
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_db():
    """在应用关闭时优雅释放 SQLAlchemy async engine 的连接池。"""
    try:
        await engine.dispose()
    except Exception:
        # 不要让关闭函数抛出异常干扰主流程，记录即可
        import logging
        logging.getLogger(__name__).exception("dispose_db: 释放 engine 失败")


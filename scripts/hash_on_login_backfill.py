import logging
import os
import sys

# Ensure project root is on sys.path so we can import `postgres_data` when running from scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hash_backfill")


def backfill_sync():
    """同步实现：使用 SQLAlchemy 同步引擎避免 async/loop 问题。"""
    try:
        from postgres_data.db_config import get_database_url
        from postgres_data.models import User
        from passlib.hash import argon2
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except Exception as exc:
        logger.exception("导入模块失败：%s", exc)
        return 1

    url = get_database_url()
    # 若 URL 指定了 async 驱动，替换为 sync 可用的 psycopg
    if '+asyncpg' in url:
        url = url.replace('+asyncpg', '+psycopg')

    try:
        engine = create_engine(url, future=True)
        Session = sessionmaker(bind=engine)
    except Exception as exc:
        logger.exception("创建同步 engine 失败：%s", exc)
        return 1

    done = 0
    skipped = 0
    session = Session()
    try:
        users = session.query(User).filter(User.password_hash == None, User.password != None).all()
    except Exception as exc:
        logger.exception("查询需要回填的用户失败：%s", exc)
        session.close()
        return 1

    logger.info("找到 %d 个待回填用户（有明文 password 且 password_hash 为空）", len(users))
    for u in users:
        try:
            pw = getattr(u, 'password', None)
            ph = getattr(u, 'password_hash', None)
            if not pw or ph:
                skipped += 1
                continue

            try:
                hashed = argon2.hash(pw)
            except Exception as e:
                logger.exception("为用户 %s 生成 hash 失败：%s", getattr(u, 'id', '<id>'), e)
                continue

            setattr(u, 'password_hash', hashed)
            # 注：默认不清除明文 password，改动可在确认后启用
            done += 1
        except Exception:
            logger.exception("处理用户 %s 时失败", getattr(u, 'id', '<id>'))

    try:
        session.commit()
        logger.info("回填完成：%d 已回填，%d 跳过", done, skipped)
        session.close()
        return 0
    except Exception as exc:
        logger.exception("提交回填更改失败：%s", exc)
        session.rollback()
        session.close()
        return 1


def main():
    # 优先使用同步实现避免 asyncio/事件循环兼容性问题
    try:
        code = backfill_sync()
        sys.exit(code)
    except Exception as exc:
        logger.exception("回填运行失败：%s", exc)
        sys.exit(1)


if __name__ == '__main__':
    main()

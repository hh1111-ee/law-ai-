"""
测试迁移脚本（异步）
用法：在已激活 venv 且正确设置 `DATABASE_URL` 的同一终端运行：

powershell:
$env:DATABASE_URL = "postgresql+asyncpg://welegal_user:REPLACE_ME@localhost:5432/welegal_db"
python scripts/test_migration.py

或测试后清理：
python scripts/test_migration.py --cleanup

脚本会：
- 使用 `postgres_data` 的 `engine` 与 `Base` 创建表（如果尚未存在）
- 插入少量测试行到 `users`、`posts`、`cases`、`comments`、`groups`
- 查询并打印插入结果
- 可选地删除插入的数据并可在 `--cleanup` 下 drop 表（谨慎）

注意：该脚本仅用于测试迁移流程；不要在生产数据库上直接运行 drop 操作。
"""

import asyncio
import selectors

# Windows 的 ProactorEventLoop 与 psycopg 不兼容，避免使用已弃用的全局策略。
# 优先使用 asyncio.Runner 并传入 selector-based loop factory；若不可用回退到 asyncio.run。
try:
    from asyncio import Runner

    def run_async(coro):
        runner = Runner(loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
        return runner.run(coro)
except Exception:
    def run_async(coro):
        # 回退：在旧 Python 版本上直接使用 asyncio.run
        return asyncio.run(coro)

# Ensure project root is on sys.path so `postgres_data` package is importable
import sys
import pathlib
project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
import argparse
import uuid
from typing import List
from sqlalchemy import text

from postgres_data.db_session import engine, AsyncSessionLocal, Base
from postgres_data import models

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def seed_and_verify() -> List[str]:
    msgs = []
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 添加用户（若已存在则跳过唯一冲突）
            u = models.User(username=f"test_user_{uuid.uuid4().hex[:6]}", password="testpass", location="测试区", identity="业主")
            session.add(u)
        # 提交后再查询
        async with session.begin():
            res = await session.execute(
                text("SELECT id, username FROM users WHERE username LIKE 'test_user_%' ORDER BY id DESC LIMIT 1")
            )
            row = res.first()
            if row:
                msgs.append(f"Inserted user id={row[0]}, username={row[1]}")

        # 插入帖子
        async with session.begin():
            # 取刚创建的用户 id
            res = await session.execute(text("SELECT id FROM users WHERE username LIKE 'test_user_%' ORDER BY id DESC LIMIT 1"))
            r = res.first()
            user_id = r[0] if r else None
            p = models.Post(title="测试帖", content="这是测试帖子", author_id=user_id, section="公告")
            session.add(p)

        # 插入案例（case）
        async with session.begin():
            c = models.Case(case_number=f"TEST-{uuid.uuid4().hex[:6]}", summary="测试案例摘要", keywords="测试,示例")
            session.add(c)

        # 查询计数
        async with session.begin():
            r1 = await session.execute(text("SELECT COUNT(*) FROM users WHERE username LIKE 'test_user_%'"))
            r2 = await session.execute(text("SELECT COUNT(*) FROM posts WHERE title = '测试帖'"))
            r3 = await session.execute(text("SELECT COUNT(*) FROM cases WHERE summary LIKE '%测试案例摘要%'") )
            cnt_users = r1.scalar_one()
            cnt_posts = r2.scalar_one()
            cnt_cases = r3.scalar_one()
            msgs.append(f"counts => users: {cnt_users}, posts: {cnt_posts}, cases: {cnt_cases}")

    return msgs

async def cleanup_inserted():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM posts WHERE title = '测试帖'"))
            await session.execute(text("DELETE FROM users WHERE username LIKE 'test_user_%'"))
            await session.execute(text("DELETE FROM cases WHERE summary LIKE '%测试案例摘要%'") )


async def main(cleanup: bool):
    print("=> 创建表（若不存在）...")
    await create_tables()
    print("=> 表已创建。开始插入测试数据...")
    msgs = await seed_and_verify()
    for m in msgs:
        print(m)

    if cleanup:
        print("=> 清理测试数据...")
        await cleanup_inserted()
        print("=> 删除测试数据完成。可选：如需删除表请谨慎运行 drop。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cleanup', action='store_true', help='插入后删除测试数据，但不 drop 表')
    args = parser.parse_args()
    run_async(main(args.cleanup))

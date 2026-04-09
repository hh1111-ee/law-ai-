#!/usr/bin/env python3
"""
迁移脚本模板：把旧的 pickle 数据迁移到 PostgreSQL（模板，不在此执行实际迁移）。

用法示例：
  python scripts/migrate_pickles.py --pickle-dir data/pickles --commit

默认是 dry-run（只打印统计与示例），加 `--commit` 才会写入数据库。
本脚本使用psycopg[binary]，请确保环境中已安装并正确配置 DATABASE_URL 环境变量指向目标数据库。
"""
import argparse
import asyncio
import logging
import os
import pickle
from typing import Any, Dict, List
from pathlib import Path
 
import sys
import asyncio
import selectors

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Note: don't set global event loop policy here (in Python 3.14
# SelectorEventLoopPolicy may be unavailable). We'll pass a selector-based
# loop factory to `asyncio.run()` in `main()` when needed.
from postgres_data import models
from postgres_data.db_session import AsyncSessionLocal
def discover_pickles(pickle_dir: str) -> List[str]:
    if not os.path.isdir(pickle_dir):
        raise FileNotFoundError(pickle_dir)
    return [os.path.join(pickle_dir, f) for f in os.listdir(pickle_dir) if f.endswith('.pkl') or f.endswith('.pickle')]


def load_pickle(path: str) -> Any:
    class SafeUnpickler(pickle.Unpickler):
        # 把无法导入的自定义类替换为 SimpleNamespace，保留属性访问
        def find_class(self, module, name):
            try:
                return super().find_class(module, name)
            except Exception:
                import types
                return types.SimpleNamespace

    with open(path, 'rb') as fh:
        try:
            return SafeUnpickler(fh).load()
        except Exception:
            # 如果失败，回退并抛出异常让上层记录
            fh.seek(0)
            return SafeUnpickler(fh).load()


def is_user_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        return 'username' in obj or ('id' in obj and 'identity' in obj)
    # 支持 SimpleNamespace/对象形式 或 旧类 `user`
    return any(hasattr(obj, a) for a in ('username', 'identity', 'password'))


def is_post_like(obj: Any) -> bool:
    if isinstance(obj, dict):
        return 'content' in obj or 'title' in obj or 'author' in obj
    return any(hasattr(obj, a) for a in ('content', 'title', 'author'))


def map_user(old: Dict) -> models.User:
    # 兼容 dict 与 对象（如旧的 `user` 实例或 SimpleNamespace）
    if not isinstance(old, dict):
        try:
            old = vars(old)
        except Exception:
            old = {k: getattr(old, k) for k in dir(old) if not k.startswith('_')}

    kwargs = {}
    # 旧 user 有 id, username, identity, password, location, role, friends, state
    kwargs['id'] = old.get('id')
    kwargs['username'] = old.get('username') or old.get('name') or old.get('user')
    # 旧项目可能只存明文 password
    if 'password_hash' in old:
        kwargs['password_hash'] = old.get('password_hash')
    elif 'password' in old:
        kwargs['password'] = old.get('password')
    kwargs['identity'] = old.get('identity')
    kwargs['location'] = old.get('location')
    kwargs['friends'] = old.get('friends')
    kwargs['role'] = old.get('role')
    kwargs['state'] = old.get('state')
    kwargs['created_at'] = old.get('created_at')
    return models.User(**{k: v for k, v in kwargs.items() if v is not None})


def map_post(old: Dict) -> models.Post:
    # 兼容 dict 与 Post/Comment 对象
    if not isinstance(old, dict):
        try:
            old = vars(old)
        except Exception:
            old = {k: getattr(old, k) for k in dir(old) if not k.startswith('_')}

    kwargs = {}
    kwargs['id'] = old.get('id')
    # 旧 Post 的 author 字段可能是 username 或 user id
    kwargs['author_id'] = old.get('author') or old.get('author_id') or old.get('user')
    kwargs['title'] = old.get('title')
    kwargs['content'] = old.get('content') or old.get('body')
    kwargs['section'] = old.get('section')
    kwargs['created_at'] = old.get('time') or old.get('created_at')
    return models.Post(**{k: v for k, v in kwargs.items() if v is not None})


async def migrate(pickle_dir: str, commit: bool = False):
    files = discover_pickles(pickle_dir)
    logging.info('发现 %d 个 pickle 文件', len(files))

    raw_users = []
    raw_posts = []

    for p in files:
        try:
            data = load_pickle(p)
        except Exception:
            logging.exception('读取 pickle 失败：%s', p)
            continue

        # 支持多种格式：单个 dict / list
        if is_user_like(data):
            raw_users.append(data)
        elif is_post_like(data):
            raw_posts.append(data)
        elif isinstance(data, list):
            for item in data:
                if is_user_like(item):
                    raw_users.append(item)
                elif is_post_like(item):
                    raw_posts.append(item)
        else:
            logging.warning('无法识别 pickle 内容类型，跳过：%s', p)

    logging.info('解析得到 %d 用户条目，%d 帖子条目', len(raw_users), len(raw_posts))

    mapped_users = [map_user(u) for u in raw_users]
    mapped_posts = [map_post(p) for p in raw_posts]

    # dry-run: 打印样例和统计
    logging.info('Mapped users: %d, posts: %d', len(mapped_users), len(mapped_posts))
    if mapped_users:
        logging.info('用户样例：%s', repr(mapped_users[0])[:400])
    if mapped_posts:
        logging.info('帖子样例：%s', repr(mapped_posts[0])[:400])
        print(mapped_posts[0].author_id)
        print(mapped_posts[0].title)
        print(mapped_posts[0].content)

    if not commit:
        logging.info('未启用 --commit，退出（dry-run）')
        return

    # 写入数据库（异步 session）——幂等处理：跳过已存在的 PK 或同名用户
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        try:
            inserted_u = 0
            inserted_p = 0
            # Users:按 id 优先、否则按 username 检查
            for u in mapped_users:
                exists = None
                if getattr(u, 'id', None) is not None:
                    exists = await session.get(models.User, u.id)
                if exists is None and getattr(u, 'username', None):
                    q = await session.execute(select(models.User).filter_by(username=u.username))
                    exists = q.scalars().first()
                if exists:
                    logging.info('跳过已存在用户：%s', getattr(u, 'username', None) or getattr(u, 'id', None))
                else:
                    session.add(u)
                    inserted_u += 1

            # Posts: 在写入前解析 author 字段（若为 username 则替换为 user id），并按 id 检查
            for p in mapped_posts:
                # resolve author if author_id is a username
                try:
                    aid = getattr(p, 'author_id', None)
                except Exception:
                    aid = None
                if aid is not None and isinstance(aid, str):
                    q = await session.execute(select(models.User).filter_by(username=aid))
                    user_obj = q.scalars().first()
                    if user_obj:
                        setattr(p, 'author_id', user_obj.id)
                        logging.info('解析 author username %s -> user_id=%s', aid, getattr(p, 'author_id', None))
                    else:
                        logging.warning('未找到 username=%s 对应的用户，帖子将以匿名/无作者插入', aid)
                        # 将 author 设置为 None（匿名），使用 setattr 以避免静态类型检查警告
                        setattr(p, 'author_id', None)

                # 基本字段校验：title/content 非空，否则跳过
                title = getattr(p, 'title', None)
                content = getattr(p, 'content', None)
                if not title or not content:
                    logging.warning('跳过帖子（缺少 title 或 content）：%s', getattr(p, 'id', None))
                    continue

                exists = None
                if getattr(p, 'id', None) is not None:
                    exists = await session.get(models.Post, p.id)
                if exists:
                    logging.info('跳过已存在帖子 id=%s', getattr(p, 'id', None))
                else:
                    session.add(p)
                    inserted_p += 1

            await session.commit()
            logging.info('已提交 %d 用户和 %d 帖子到数据库', inserted_u, inserted_p)
        except Exception:
            logging.exception('写入数据库失败，回滚')
            await session.rollback()


def parse_args():
    p = argparse.ArgumentParser(description='迁移 pickle 到 PostgreSQL（模板）')
    p.add_argument('--pickle-dir', '-d', required=True, help='pickle 文件目录')
    p.add_argument('--commit', action='store_true', help='写入数据库（否则为 dry-run）')
    return p.parse_args()


def main():
    args = parse_args()
    # 提醒：请先设置环境变量 DATABASE_URL 指向目标数据库
    if not args.commit:
        logging.info('运行 dry-run，请确认输出后再用 --commit 执行实际迁移')
    # Use a selector-based event loop on Windows to be compatible with psycopg async
    if sys.platform.startswith('win'):
        loop_factory = lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.run(migrate(args.pickle_dir, commit=args.commit), loop_factory=loop_factory)
    else:
        asyncio.run(migrate(args.pickle_dir, commit=args.commit))


if __name__ == '__main__':
    main()

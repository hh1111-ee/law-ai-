import logging
from typing import List, Dict, Optional, Any, cast, Union
from sqlalchemy import select, text

from .db_session import AsyncSessionLocal
from .models import ExampleRelation

logger = logging.getLogger(__name__)

# 自定义异常：供上层区分“无数据”与“查询失败/事件循环不兼容”
class AdapterError(Exception):
    pass


class DatabaseError(AdapterError):
    """表示数据库查询或写入失败（非空结果的情况）"""
    pass


class LoopIncompatError(AdapterError):
    """表示在当前事件循环下 psycopg 无法以 async 模式工作（Windows Proactor）"""
    pass


# 业务异常，接口层可据此返回 404/400 等更语义化的 HTTP 状态
class UserNotFoundError(AdapterError):
    pass


class PostNotFoundError(AdapterError):
    pass

# 模块级同步 engine/session 单例，避免每次调用都创建连接池
_SYNC_ENGINE = None
_SYNC_SessionFactory = None

def _init_sync_engine():
    global _SYNC_ENGINE, _SYNC_SessionFactory
    if _SYNC_ENGINE is not None and _SYNC_SessionFactory is not None:
        return
    try:
        from .db_config import get_database_url
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except Exception as exc:
        logger.exception("初始化同步 engine 时导入失败: %s", exc)
        raise

    url = get_database_url()
    if '+asyncpg' in url:
        url = url.replace('+asyncpg', '+psycopg')

    _SYNC_ENGINE = create_engine(url, future=True)
    _SYNC_SessionFactory = sessionmaker(bind=_SYNC_ENGINE)

def _get_sync_session():
    global _SYNC_ENGINE, _SYNC_SessionFactory
    if _SYNC_SessionFactory is None:
        _init_sync_engine()
    if _SYNC_SessionFactory is None:
        raise RuntimeError("同步 SessionFactory 未能初始化")
    return _SYNC_SessionFactory()


def _is_loop_incompat_error(exc: Exception) -> bool:
    """判断异常是否由 Windows ProactorEventLoop 与 psycopg 不兼容导致。"""
    try:
        import psycopg
        if isinstance(exc, getattr(psycopg, 'InterfaceError', type(None))):
            return True
    except Exception:
        pass
    msg = str(exc)
    if 'ProactorEventLoop' in msg or 'cannot use the' in msg:
        return True
    return False


async def fetch_relations_rows() -> List[Dict[str, str]]:
    """从数据库中读取 example_relation 表，返回与旧 Excel 相同的字典列表格式。

    返回每行字典，包含中文字段以便与现有代码兼容：
    - '案号', '链接', '摘要', '关键词1', '关键词2', '关键词3'
    若发生错误或 DB 不可用，返回空列表并记录异常。
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ExampleRelation))
            rows = result.scalars().all()
            out: List[Dict[str, str]] = []
            for r in rows:
                out.append({
                    '案号': str(getattr(r, 'case_number', '') or ''),
                    '链接': str(getattr(r, 'url', '') or ''),
                    '摘要': str(getattr(r, 'summary', '') or ''),
                    '关键词1': str(getattr(r, 'keyword1', '') or ''),
                    '关键词2': str(getattr(r, 'keyword2', '') or ''),
                    '关键词3': str(getattr(r, 'keyword3', '') or ''),
                })
            return out
    except Exception as exc:
        logger.exception("从数据库读取 example_relation 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def fetch_example_legal_rows() -> List[Dict[str, str]]:
    """读取 example_legal 表，返回与 `_load_excel_rows` 相同结构的字典列表：
    每项包含 'region','url','name'。
    """
    try:
        from .models import ExampleLegal

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ExampleLegal))
            rows = result.scalars().all()
            out: List[Dict[str, str]] = []
            for r in rows:
                out.append({
                    'region': str(getattr(r, 'region', '') or ''),
                    'url': str(getattr(r, 'url', '') or ''),
                    'name': str(getattr(r, 'title', '') or ''),
                })
            return out
    except Exception as exc:
        logger.exception("从数据库读取 example_legal 失败: %s", exc)
        raise DatabaseError(exc) from exc


def _format_dt(dt) -> str:
    try:
        if dt is None:
            return ''
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(dt)


async def fetch_posts_rows(section: Optional[str] = None) -> List[Dict]:
    """读取 posts 及其评论，返回与 `Post.to_dict()` 类似的字典列表。"""
    try:
        from .models import Post, Comment, User

        async with AsyncSessionLocal() as session:
            if section is not None:
                result = await session.execute(select(Post).where(Post.section == section))
            else:
                result = await session.execute(select(Post))
            posts = result.scalars().all()
            out: List[Dict] = []
            for p in posts:
                # 获取评论
                comments_q = await session.execute(select(Comment).where(Comment.post_id == p.id))
                comments = comments_q.scalars().all()
                comments_list = []
                for c in comments:
                    comments_list.append({
                        'id': c.id,
                        'post_id': c.post_id,
                        'author': c.author_name,
                        'content': c.content,
                        'time': _format_dt(c.created_at),
                    })

                # 作者用户名（若可关联）
                author_name = None
                try:
                    if getattr(p, 'author_id', None) is not None:
                        user_q = await session.execute(select(User).where(User.id == getattr(p, 'author_id')))
                        u = user_q.scalars().first()
                        if u:
                            author_name = getattr(u, 'username', None)
                except Exception:
                    author_name = None

                out.append({
                    'id': getattr(p, 'id', None),
                    'author': author_name,
                    'title': str(getattr(p, 'title', '') or ''),
                    'content': str(getattr(p, 'content', '') or ''),
                    'section': str(getattr(p, 'section', '') or ''),
                    'time': _format_dt(getattr(p, 'created_at', None)),
                    'comments': comments_list,
                })
            return out
    except Exception as exc:
        logger.exception("从数据库读取 posts 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def fetch_users_rows() -> List[Dict]:
    """读取 users 表，返回与 `user.to_dict()` 兼容的列表字典。"""
    try:
        from .models import User

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            out: List[Dict] = []
            for u in users:
                friends = u.friends or []
                out.append({
                    'id': u.id,
                    'username': u.username,
                    'identity': u.identity,
                    'role': u.role,
                    'location': u.location,
                    'state': u.state,
                    'friends': friends,
                })
            return out
    except Exception as exc:
        logger.exception("从数据库读取 users 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def get_user_by_username(username: str) -> Dict:
    try:
        from .models import User
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.username == str(username)))
            u = result.scalars().first()
            print(f"查询 username={username}，结果 user id={getattr(u, 'id', None) if u else 'None'}")
        if not u:
            return {}
        return {
            'id': u.id,
            'username': u.username,
            'identity': u.identity,
            'role': u.role,
            'location': u.location,
            'state': u.state,
            'friends': u.friends or [],
        }
    except Exception as exc:
        logger.exception("查询 user 失败: %s", exc)
        raise DatabaseError(exc) from exc
async def get_users_by_name(username: str) -> List[Dict]:
    """模糊查询，寻找用户名包含指定字符串的用户列表。"""
    try:
        from .models import User
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.username.contains(username)).limit(50))
            users = result.scalars().all()  # 限制最多返回 50 条结果以避免过载
        out = []
        for u in users:
            out.append({
                'id': u.id,
                'username': u.username,
                'identity': u.identity,
                'role': u.role,
                'location': u.location,
                'state': u.state,
                'friends': u.friends or [],
            })
        return out
    except Exception as exc:
        logger.exception("模糊查询 users 失败: %s", exc)
        raise DatabaseError(exc) from exc

async def get_user_by_id(user_id: int) -> Dict:
    try:
        from .models import User
         
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            u = result.scalars().first()
        if not u:
            return {}
        return {
            'id': u.id,
            'username': getattr(u, 'username', None),
            'identity': getattr(u, 'identity', None),
            'role': getattr(u, 'role', None),
            'location': getattr(u, 'location', None),
            'state': getattr(u, 'state', None),
            'friends': getattr(u, 'friends', []) or [],
        }
    except Exception as exc:
        logger.exception("按 id 查询 user 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def set_user_state(username: Optional[str] = None, user_id: Optional[int] = None, state: str = "online") -> bool:
    """设置用户状态（online/offline）。返回 True 表示已更新，False 表示未找到用户。"""
    try:
        from .models import User

        async with AsyncSessionLocal() as session:
            async with session.begin():
                if username:
                    result = await session.execute(select(User).where(User.username == username))
                    u = result.scalars().first()
                elif user_id is not None:
                    result = await session.execute(select(User).where(User.id == user_id))
                    u = result.scalars().first()
                else:
                    return False

                if not u:
                    return False

                # 更新并提交（session.begin() 会在退出时提交）
                try:
                    setattr(u, 'state', state)
                except Exception:
                    # 尝试通过属性访问失败时，直接使用 SQL 更新
                    sql = "UPDATE users SET state = :state WHERE username = :username" if username else "UPDATE users SET state = :state WHERE id = :id"
                    await session.execute(text(sql), {'state': state, 'username': username, 'id': user_id})
        return True
    except Exception as exc:
        logger.exception("设置 user state 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def set_user_state_if_offline(username: Optional[str] = None, user_id: Optional[int] = None, new_state: str = "online") -> bool:
    """原子性地将用户状态从非 `online` 更新为 `new_state`。

    返回 True 表示更新成功（即之前不是 online 并已设置为 new_state），
    返回 False 表示未找到用户或当前已为 online（未做更新）。
    """
    try:
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            async with session.begin():
                if user_id is not None:
                    sql = text("UPDATE users SET state = :state WHERE id = :id AND state != 'online' RETURNING id")
                    res = await session.execute(sql, {"state": new_state, "id": user_id})
                elif username:
                    sql = text("UPDATE users SET state = :state WHERE username = :username AND state != 'online' RETURNING id")
                    res = await session.execute(sql, {"state": new_state, "username": username})
                else:
                    return False
                row = res.first()
        return row is not None
    except Exception as exc:
        logger.exception("原子设置 user state 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def create_user(user_id: int, username: Optional[str], password: Optional[str], identity: Optional[str], location: Optional[str], role: Optional[str], friends: Optional[list] = None, password_hash: Optional[str] = None) -> Dict:
    """在数据库中创建用户。返回用户基本信息字典或空字典表示失败。"""
    try:
        from .models import User

        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 检查冲突（在同一事务内执行查询与写入以避免重复 begin）
                if username:
                    q = await session.execute(select(User).where(User.username == username))
                    if q.scalars().first():
                        return {}
                if user_id is not None:
                    q2 = await session.execute(select(User).where(User.id == user_id))
                    if q2.scalars().first():
                        return {}

                new_user = User(id=user_id if user_id is not None else None,
                                username=username,
                                password=password,
                                password_hash=password_hash,
                                identity=identity,
                                location=location,
                                role=role,
                                friends=friends or [])
                session.add(new_user)

            return {
                'id': new_user.id,
                'username': getattr(new_user, 'username', None),
                'identity': getattr(new_user, 'identity', None),
                'role': getattr(new_user, 'role', None),
                'location': getattr(new_user, 'location', None),
                'state': getattr(new_user, 'state', None),
            }
    except Exception as exc:
        logger.exception("创建 user 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def get_user_credentials(user_id: int) -> Dict:
    """返回指定用户的凭据信息：{'password': str|None, 'password_hash': str|None} 或空字典。"""
    try:
        from .models import User

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            u = result.scalars().first()
        if not u:
            return {}
        return {
            'password': getattr(u, 'password', None),
            'password_hash': getattr(u, 'password_hash', None),
            'state': getattr(u, 'state', None),
        }
    except Exception as exc:
        logger.exception("获取 user 凭据失败: %s", exc)
        raise DatabaseError(exc) from exc


async def get_post_by_id(post_id: int) -> Dict:
    try:
        from .models import Post, Comment, User
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Post).where(Post.id == post_id))
            p = result.scalars().first()
            if not p:
                return {}
            comments_q = await session.execute(select(Comment).where(Comment.post_id == p.id))
            comments = comments_q.scalars().all()
            comments_list = []
            for c in comments:
                comments_list.append({
                    'id': c.id,
                    'post_id': c.post_id,
                    'author': c.author_name,
                    'content': c.content,
                    'time': _format_dt(c.created_at),
                })

            author_name = None
            if getattr(p, 'author_id', None) is not None:
                user_q = await session.execute(select(User).where(User.id == getattr(p, 'author_id')))
                u = user_q.scalars().first()
                if u:
                    author_name = getattr(u, 'username', None)

            return {
                'id': p.id,
                'author': author_name,
                'title': p.title or '',
                'content': p.content or '',
                'section': p.section or '',
                'time': _format_dt(p.created_at),
                'comments': comments_list,
            }
    except Exception as exc:
        logger.exception("查询 post 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def create_post(author: Union[str, int, None], title: Optional[str], content: Optional[str], section: Optional[str]) -> Dict:
    """在数据库中创建一个帖子。

    `author` 可以是用户名（str）或用户 ID（int 或可解析为 int 的字符串）。
    返回与 `Post.to_dict()` 兼容的字典结构或空字典表示失败。
    """
    try:
        from .models import Post, User

        async with AsyncSessionLocal() as session:
            async with session.begin():
                author_id = None
                if author is not None:
                    if isinstance(author, int):
                        author_id = author
                    else:
                        s = str(author).strip()
                        if s.isdigit():
                            try:
                                author_id = int(s)
                            except Exception:
                                author_id = None
                        else:
                            user_q = await session.execute(select(User).where(User.username == str(s)))
                            u = user_q.scalars().first()
                            if u:
                                author_id = u.id

                new_post = Post(title=title or '', content=content or '', author_id=author_id, section=section)
                session.add(new_post)
                await session.flush()  # 确保 new_post.id 可用
                return {
                    'id': new_post.id,
                    'author': str(author) if author is not None else None,
                    'title': new_post.title or '',
                    'content': new_post.content or '',
                    'section': new_post.section or '',
                    'time': _format_dt(new_post.created_at),
                    'comments': [],
                }
    except Exception as exc:
        logger.exception("创建 post 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def add_comment(post_id: int, author: Optional[object], content: Optional[str]) -> Dict:
    """在数据库中为帖子添加评论，返回与 `Comment.to_dict()` 兼容的字典。

    `author` 可以是用户名或用户 id；如果是 id，会尝试解析为用户名并写入 `author_name` 字段。
    """
    try:
        from .models import Comment, Post, User

        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 确认帖子存在
                post_q = await session.execute(select(Post).where(Post.id == post_id))
                p = post_q.scalars().first()
                if not p:
                    return {}

                author_name = None
                if author is not None:
                    if isinstance(author, int):
                        user_q = await session.execute(select(User).where(User.id == author))
                        u = user_q.scalars().first()
                        if u:
                            author_name = getattr(u, 'username', None)
                    else:
                        s = str(author).strip()
                        if s:
                                user_q = await session.execute(select(User).where(User.username == s))
                                u = user_q.scalars().first()
                                if u:
                                    author_name = getattr(u, 'username', None)
                        elif s.isdigit():
                            try:
                                uid = int(s)
                                user_q = await session.execute(select(User).where(User.id == uid))
                                u = user_q.scalars().first()
                                if u:
                                    author_name =str(u.username)
                                    print(f"解析 comment author={author} 为用户 id={uid}，用户名={author_name}")
                            except Exception:
                                author_name = s
                        else:
                            author_name = s

                new_comment = Comment(post_id=post_id, author_name=author_name, content=content)
                session.add(new_comment)

            return {
                'id': new_comment.id,
                'post_id': new_comment.post_id,
                'author': new_comment.author_name,
                'content': new_comment.content,
                'time': _format_dt(new_comment.created_at),
            }
    except Exception as exc:
        logger.exception("添加 comment 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def ensure_seed_data() -> Dict[str, int]:
    """确保数据库中存在最小的种子数据（用于开发/测试）。

    返回字典：{'users': int, 'posts': int} 表示当前计数（插入后为插入前计数）。
    """
    try:
        from .models import User, Post
        from sqlalchemy import func

        async with AsyncSessionLocal() as session:
            async with session.begin():
                res = await session.execute(select(func.count()).select_from(User))
                user_cnt = int(res.scalar_one())
                res2 = await session.execute(select(func.count()).select_from(Post))
                post_cnt = int(res2.scalar_one())
                if user_cnt == 0:
                    session.add(User(username='test1', identity='tester', role='user'))
                    session.add(User(username='test2', identity='tester', role='user'))
            return {'users': user_cnt, 'posts': post_cnt}
    except Exception as exc:
        logger.exception("ensure_seed_data 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def create_personal_message(sender: Union[int, str], receiver: Union[int, str], content: str, timestamp: Optional[str] = None) -> Dict:
    """在数据库中创建私信记录，接受用户 id 或 username 作为 `sender`/`receiver`，
    内部解析为 id 再写入表。返回已创建行的字典；若无法解析为用户 id 则返回空字典。
    """
     
    try:
        from .models import PersonalMessage, User

        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 解析 sender -> id
                sender_id = None
                if isinstance(sender, int):
                    sender_id = sender
                else:
                    s = str(sender).strip() if sender is not None else ''
                    if s.isdigit():
                        try:
                            sender_id = int(s)
                        except Exception:
                            sender_id = None
                    elif s:
                        res = await session.execute(select(User).where(User.username == s))
                        u = res.scalars().first()
                        if u:
                            sender_id = u.id

                # 解析 receiver -> id
                receiver_id = None
                if isinstance(receiver, int):
                    receiver_id = receiver
                else:
                    r = str(receiver).strip() if receiver is not None else ''
                    if r.isdigit():
                        try:
                            receiver_id = int(r)
                        except Exception:
                            receiver_id = None
                    elif r:
                        res2 = await session.execute(select(User).where(User.username == r))
                        u2 = res2.scalars().first()
                        if u2:
                            receiver_id = u2.id

                if sender_id is None or receiver_id is None:
                    logger.warning("create_personal_message: 无法解析 sender/receiver 为用户 id: %s %s", sender, receiver)
                    return {}

                pm = PersonalMessage(sender=sender_id, receiver=receiver_id, content=content)
                session.add(pm)

            return {
                'id': pm.id,
                'sender': pm.sender,
                'receiver': pm.receiver,
                'content': pm.content,
                'time': _format_dt(pm.created_at),
            }
    except Exception as exc:
        logger.exception("创建 personal message 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def fetch_personal_messages(user_a: int, user_b: int) -> List[Dict]:
    """获取两位用户之间的私信历史（按时间升序）。

    返回列表，格式与前端现有 `get_personal_messages` 输出兼容：
    每项包含 'sender','receiver','content','time'
    """
    try:
        from .models import PersonalMessage

        async with AsyncSessionLocal() as session:
            # 查询两方向的消息
            q = await session.execute(
                select(PersonalMessage).where(
                    ((PersonalMessage.sender == user_a) & (PersonalMessage.receiver == user_b))
                    | ((PersonalMessage.sender == user_b) & (PersonalMessage.receiver == user_a))
                ).order_by(PersonalMessage.created_at)
            )
            msgs = q.scalars().all()
            out: List[Dict] = []
            for m in msgs:
                out.append({
                    'sender': getattr(m, 'sender', ''),
                    'receiver': getattr(m, 'receiver', ''),
                    'content': getattr(m, 'content', ''),
                    'time': _format_dt(getattr(m, 'created_at', None)),
                })
            return out
    except Exception as exc:
        logger.exception("从数据库读取 personal messages 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def create_group_message(group_name: str, sender: str, content: str, timestamp: Optional[str] = None) -> Dict:
    """在数据库中创建群消息记录，返回已创建行的字典。"""
    try:
        from .models import GroupMessage

        async with AsyncSessionLocal() as session:
            async with session.begin():
                gm = GroupMessage(group_name=group_name, sender=sender, content=content)
                session.add(gm)

            return {
                'id': gm.id,
                'group': gm.group_name,
                'sender': gm.sender,
                'content': gm.content,
                'time': _format_dt(gm.created_at),
            }
    except Exception as exc:
        logger.exception("创建 group message 失败: %s", exc)
        raise DatabaseError(exc) from exc


async def add_friend_db(userid: int, friend_id: int) -> bool:
    """在 DB 中为两位用户互相添加好友（friends 存为 JSON 列）。返回 True 表示成功。"""
    try:
        from .models import User

        async with AsyncSessionLocal() as session:
            async with session.begin():
                res_a = await session.execute(select(User).where(User.id == userid))
                a = res_a.scalars().first()
                res_b = await session.execute(select(User).where(User.id == friend_id))
                b = res_b.scalars().first()
                if not a or not b:
                    return False

                # friends 在 models 中声明为 Column[...]，静态类型检查器可能会把它当作 Column[Any]
                # 运行时它通常是列表或 None；用 cast 告知类型检查器并使用 setattr 避免 Column 与 list 的直接赋值警告
                fa = list(cast(List[int], a.friends) or [])
                fb = list(cast(List[int], b.friends) or [])
                if friend_id not in fa:
                    fa.append(friend_id)
                if userid not in fb:
                    fb.append(userid)
                try:
                    setattr(a, "friends", fa)
                    setattr(b, "friends", fb)
                except Exception:
                    # fallback to raw SQL update
                    await session.execute(text("UPDATE users SET friends = :fa WHERE id = :uid"), {'fa': fa, 'uid': userid})
                    await session.execute(text("UPDATE users SET friends = :fb WHERE id = :uid"), {'fb': fb, 'uid': friend_id})
        return True
    except Exception as exc:
        logger.exception("add_friend_db 失败: %s", exc)
        raise DatabaseError(exc) from exc


# ===== 同步辅助函数（供脚本/短命进程安全调用） =====
# 下面的函数使用同步 SQLAlchemy 引擎，以避免在脚本或在 Windows 的
# ProactorEventLoop 下直接调用 async adapter 时出现 psycopg 的事件循环兼容性错误。
# 函数命名以 `_sync` 结尾，放在文件末尾以便明显区分。

def get_user_by_id_sync(user_id: int) -> Dict:
    try:
        from .models import User
    except Exception as exc:
        logger.exception("同步导入模块失败: %s", exc)
        return {}

    try:
        session = _get_sync_session()
    except Exception as exc:
        logger.exception("初始化同步 session 失败: %s", exc)
        return {}

    try:
        u = session.query(User).filter(User.id == user_id).first()
        if not u:
            return {}
        return {
            'id': u.id,
            'username': getattr(u, 'username', None),
            'identity': getattr(u, 'identity', None),
            'role': getattr(u, 'role', None),
            'location': getattr(u, 'location', None),
            'state': getattr(u, 'state', None),
            'friends': getattr(u, 'friends', []) or [],
            'password_hash': getattr(u, 'password_hash', None),
        }
    except Exception as exc:
        logger.exception("同步按 id 查询 user 失败: %s", exc)
        return {}
    finally:
        try:
            session.close()
        except Exception:
            pass


def get_user_credentials_sync(user_id: int) -> Dict:
    try:
        from .models import User
    except Exception as exc:
        logger.exception("同步导入模块失败: %s", exc)
        return {}

    try:
        session = _get_sync_session()
    except Exception as exc:
        logger.exception("初始化同步 session 失败: %s", exc)
        return {}

    try:
        u = session.query(User).filter(User.id == user_id).first()
        if not u:
            return {}
        return {
            'password': getattr(u, 'password', None),
            'password_hash': getattr(u, 'password_hash', None),
        }
    except Exception as exc:
        logger.exception("同步获取 user 凭据失败: %s", exc)
        return {}
    finally:
        try:
            session.close()
        except Exception:
            pass


def get_user_by_username_sync(username: str) -> Dict:
    try:
        from .models import User
    except Exception as exc:
        logger.exception("同步导入模块失败: %s", exc)
        return {}

    try:
        session = _get_sync_session()
    except Exception as exc:
        logger.exception("初始化同步 session 失败: %s", exc)
        return {}

    try:
        u = session.query(User).filter(User.username == username).first()
        if not u:
            return {}
        return {
            'id': u.id,
            'username': getattr(u, 'username', None),
            'identity': getattr(u, 'identity', None),
            'role': getattr(u, 'role', None),
            'location': getattr(u, 'location', None),
            'state': getattr(u, 'state', None),
            'friends': getattr(u, 'friends', []) or [],
            'password_hash': getattr(u, 'password_hash', None),
        }
    except Exception as exc:
        logger.exception("同步按 username 查询 user 失败: %s", exc)
        return {}
    finally:
        try:
            session.close()
        except Exception:
            pass

# adminstrater.py
# ------------------- 管理员后台 -------------------
# 依赖模块（请确保相应文件在同目录或已加入 PYTHONPATH）
from user import user, userManage
from post import PostManage
from ChatMessage import MessageManage
from group import groupManage                      # 群管理模块
import easygui as eg
import os

# 管理脚本改为直接使用 Postgres 的同步 session（移除对 pickle 的依赖）
try:
    from postgres_data.adapter import _get_sync_session
    PG_SYNC_AVAILABLE = True
except Exception:
    _get_sync_session = None
    PG_SYNC_AVAILABLE = False
# 不再使用本地 pkl 文件；所有数据读写通过 Postgres 完成


# ------------------- 管理对象（单例） -------------------
# 管理对象（本地缓存/UI 展示使用同步 DB 查询获得数据）
user_manager = userManage()
post_manager = PostManage()
message_manager = MessageManage()
group_manager = groupManage()


# ------------------- 同步 DB 辅助（用于管理界面） -------------------
def _fetch_all_users_sync() -> list:
    if not PG_SYNC_AVAILABLE or _get_sync_session is None:
        return []
    session = None
    try:
        session = _get_sync_session()
        from postgres_data.models import User
        rows = session.query(User).all()
        out = []
        for u in rows:
            out.append({
                'id': getattr(u, 'id', None),
                'username': getattr(u, 'username', None),
                'identity': getattr(u, 'identity', None),
                'role': getattr(u, 'role', None),
                'location': getattr(u, 'location', None),
                'state': getattr(u, 'state', None),
                'friends': getattr(u, 'friends', []) or [],
                'password': getattr(u, 'password', None),
            })
        return out
    except Exception as e:
        print(f"fetch_all_users_sync failed: {e}")
        return []
    finally:
        try:
            if session:
                session.close()
        except Exception:
            pass


def _fetch_all_posts_sync() -> list:
    if not PG_SYNC_AVAILABLE or _get_sync_session is None:
        return []
    session = None
    try:
        session = _get_sync_session()
        from postgres_data.models import Post, Comment, User
        posts = session.query(Post).all()
        out = []
        for p in posts:
            comments_q = session.query(Comment).filter(Comment.post_id == p.id).all()
            comments_list = []
            for c in comments_q:
                comments_list.append({
                    'id': c.id,
                    'post_id': c.post_id,
                    'author': c.author_name,
                    'content': c.content,
                    'time': str(c.created_at),
                })
            author_name = None
            if getattr(p, 'author_id', None) is not None:
                u = session.query(User).filter(User.id == p.author_id).first()
                if u:
                    author_name = getattr(u, 'username', None)
            out.append({
                'id': p.id,
                'author': author_name,
                'title': getattr(p, 'title', ''),
                'content': getattr(p, 'content', ''),
                'section': getattr(p, 'section', ''),
                'time': str(getattr(p, 'created_at', None)),
                'comments': comments_list,
            })
        return out
    except Exception as e:
        print(f"fetch_all_posts_sync failed: {e}")
        return []
    finally:
        try:
            if session:
                session.close()
        except Exception:
            pass


def _fetch_personal_messages_sync() -> list:
    if not PG_SYNC_AVAILABLE or _get_sync_session is None:
        return []
    session = None
    try:
        session = _get_sync_session()
        from postgres_data.models import PersonalMessage
        msgs = session.query(PersonalMessage).all()
        out = []
        for m in msgs:
            out.append({
                'sender': getattr(m, 'sender', ''),
                'receiver': getattr(m, 'receiver', ''),
                'content': getattr(m, 'content', ''),
                'time': str(getattr(m, 'created_at', None)),
            })
        return out
    except Exception as e:
        print(f"fetch_personal_messages_sync failed: {e}")
        return []
    finally:
        try:
            if session:
                session.close()
        except Exception:
            pass


def _fetch_group_messages_sync() -> list:
    if not PG_SYNC_AVAILABLE or _get_sync_session is None:
        return []
    session = None
    try:
        session = _get_sync_session()
        from postgres_data.models import GroupMessage
        msgs = session.query(GroupMessage).all()
        out = []
        for m in msgs:
            out.append({
                'sender': getattr(m, 'sender', ''),
                'group': getattr(m, 'group_name', ''),
                'content': getattr(m, 'content', ''),
                'time': str(getattr(m, 'created_at', None)),
            })
        return out
    except Exception as e:
        print(f"fetch_group_messages_sync failed: {e}")
        return []
    finally:
        try:
            if session:
                session.close()
        except Exception:
            pass


# ------------------- 功能实现 -------------------
def addUser() -> None:
    """在管理员后台添加新用户（直接写入 Postgres）。"""
    if not PG_SYNC_AVAILABLE or _get_sync_session is None:
        eg.msgbox("数据库不可用，无法添加用户。")
        return

    id_text = eg.enterbox("请输入用户 ID（数字，可留空）")
    try:
        user_id = int(id_text) if id_text else None
    except Exception:
        eg.msgbox("用户 ID 格式错误")
        return

    identity = eg.choicebox("请选择身份类型", choices=["业主方", "物业方", "律师"])
    name = eg.enterbox("请输入用户名")
    password = eg.enterbox("请输入密码")
    # 位置获取
    location = eg.enterbox("请输入详细地址")

    if not all([identity, name, password, location]):
        eg.msgbox("所有字段都必须填写！")
        return

    session = None
    try:
        session = _get_sync_session()
        from postgres_data.models import User
        new_user = User(id=user_id if user_id is not None else None,
                        username=name,
                        password=password,
                        identity=identity,
                        location=location,
                        role=identity,
                        friends=[])
        session.add(new_user)
        session.commit()
        eg.msgbox(f"用户 {name} 添加成功！")
    except Exception as e:
        try:
            if session:
                session.rollback()
        except Exception:
            pass
        eg.msgbox(f"添加用户失败: {e}")
    finally:
        try:
            if session:
                session.close()
        except Exception:
            pass

def addPost() -> None:
    """在管理员后台添加新帖子（直接写入 Postgres）。"""
    if not PG_SYNC_AVAILABLE or _get_sync_session is None:
        eg.msgbox("数据库不可用，无法添加帖子。")
        return

    author = eg.enterbox("请输入作者用户名（可留空）")
    title = eg.enterbox("请输入帖子标题")
    content = eg.enterbox("请输入帖子内容")
    section = eg.enterbox("请输入板块名称")

    if not (title and content and section):
        eg.msgbox("标题、内容与板块不能为空！")
        return

    session = None
    try:
        session = _get_sync_session()
        from postgres_data.models import Post, User
        author_id = None
        if author:
            u = session.query(User).filter(User.username == author).first()
            if u:
                author_id = u.id

        new_post = Post(title=title, content=content, section=section, author_id=author_id)
        session.add(new_post)
        session.commit()
        eg.msgbox("帖子添加成功！")
    except Exception as e:
        try:
            if session:
                session.rollback()
        except Exception:
            pass
        eg.msgbox(f"添加帖子失败: {e}")
    finally:
        try:
            if session:
                session.close()
        except Exception:
            pass


# ------------------- 查看数据 -------------------
def showUsers() -> None:
    """展示所有用户的简要信息（使用 easygui.textbox）。"""
    rows = _fetch_all_users_sync()
    if not rows:
        eg.msgbox("暂无用户数据或数据库不可用！")
        return

    lines = []
    for idx, u in enumerate(rows, 1):
        lines.append(
            f"===== 用户 {idx} =====\n"
            f"ID：{u.get('id')}\n"
            f"用户名：{u.get('username')}\n"
            f"身份类型：{u.get('identity')}\n"
            f"好友数量：{len(u.get('friends', []))}\n"
            f"密码：{u.get('password')}\n"
            f"位置：{u.get('location')}\n"
            f"状态：{u.get('state')}\n"
        )
        print(f"用户 {idx}：{u.get('username')}，身份：{u.get('identity')}")
    eg.textbox("数据表", "用户数据列表（共{}条）".format(len(rows)), "\n".join(lines))


def showPosts() -> None:
    """展示所有帖子的详细信息（从 Postgres 同步读取）。"""
    posts = _fetch_all_posts_sync()
    if not posts:
        eg.msgbox("暂无帖子数据或数据库不可用！")
        return

    lines = []
    for idx, p in enumerate(posts, 1):
        comment_lines = [
            f"  - 评论{c.get('id')}：{c.get('author')} | {c.get('content')}（{c.get('time')}）"
            for c in p.get('comments', [])
        ]
        comments = "\n".join(comment_lines) if comment_lines else "  无评论"

        lines.append(
            f"===== 帖子 {idx}（ID：{p.get('id')}） =====\n"
            f"作者：{p.get('author')}\n"
            f"标题：{p.get('title')}\n"
            f"板块：{p.get('section')}\n"
            f"发布时间：{p.get('time')}\n"
            f"内容：{p.get('content')}\n"
            f"评论：\n{comments}\n"
        )
    eg.textbox("帖子数据列表", "\n".join(lines))


def showPersonalMessages() -> None:
    """展示所有私信（个人消息）。"""
    msgs = _fetch_personal_messages_sync()
    if not msgs:
        eg.msgbox("暂无私信数据或数据库不可用！")
        return

    lines = []
    for idx, m in enumerate(msgs, 1):
        lines.append(
            f"===== 私信 {idx} =====\n"
            f"发送者：{m.get('sender')}\n"
            f"接收者：{m.get('receiver')}\n"
            f"内容：{m.get('content')}\n"
            f"发送时间：{m.get('time')}\n"
        )
    eg.textbox("私信数据列表", "\n".join(lines))


def showGroupMessages() -> None:
    """展示所有群消息。"""
    msgs = _fetch_group_messages_sync()
    if not msgs:
        eg.msgbox("暂无群消息数据或数据库不可用！")
        return

    lines = []
    for idx, m in enumerate(msgs, 1):
        lines.append(
            f"===== 群消息 {idx} =====\n"
            f"发送者：{m.get('sender')}\n"
            f"所属群组：{m.get('group')}\n"
            f"内容：{m.get('content')}\n"
            f"发送时间：{m.get('time')}\n"
        )
    eg.textbox("群消息数据列表", "\n".join(lines))


def showData() -> None:
    """数据查看总入口，选择查看哪类数据。"""
    choice = eg.choicebox(
        "请选择要查看的数据类型",
        title="数据查看",
        choices=["用户数据", "帖子数据", "私信数据", "群消息数据"]
    )
    if not choice:
        return

    if choice == "用户数据":
        showUsers()
    elif choice == "帖子数据":
        showPosts()
    elif choice == "私信数据":
        showPersonalMessages()
    elif choice == "群消息数据":
        showGroupMessages()


# ------------------- 主界面 -------------------
def adminInterface() -> None:
    """管理员后台主循环。"""
    while True:
        choice = eg.buttonbox(
            "请选择操作",
            title="管理员后台",
            choices=["添加用户", "添加帖子", "查看数据", "退出"]
        )
        if choice == "添加用户":
            addUser()
        elif choice == "添加帖子":
            addPost()
        elif choice == "查看数据":
            showData()
        elif choice == "退出":
            # 退出时无需写回本地 pkl；所有更改已直接写入 Postgres
            eg.msgbox("退出：数据已持久化到 Postgres（若可用）。")
            break


if __name__ == "__main__":
    adminInterface()

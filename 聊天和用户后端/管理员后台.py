# adminstrater.py
# ------------------- 管理员后台 -------------------
# 依赖模块（请确保相应文件在同目录或已加入 PYTHONPATH）
from user import user, userManage
from post import PostManage
from ChatMessage import MessageManage
from group import groupManage                      # 群管理模块
import easygui as eg
import os
import pickle
# ------------------- 数据文件路径 -------------------
# 与交流服务器保持一致的绝对路径
USER_FILE = r'D:\项目：ai法律平台\users.pkl'
GROUP_FILE = r'D:\项目：ai法律平台\groups.pkl'
POST_FILE = r'D:\项目：ai法律平台\posts.pkl'
PERSONAL_MSG_FILE = r'D:\项目：ai法律平台\personal_messages.pkl'
GROUP_MSG_FILE = r'D:\项目：ai法律平台\group_messages.pkl'


# ------------------- 文件准备工具 -------------------
def ensure_file_exists(filename: str) -> None:
    """若文件不存在则创建空二进制文件，防止 pickle.load 报错。"""
    if not os.path.exists(filename):
        with open(filename, 'wb') as f:
            pass


# ------------------- 管理对象（单例） -------------------
user_manager = userManage()
post_manager = PostManage()
message_manager = MessageManage()
group_manager = groupManage()


# ------------------- 数据加载 -------------------
def load_all_data() -> None:
    """启动时加载所有持久化数据。"""
    ensure_file_exists(USER_FILE)
    ensure_file_exists(GROUP_FILE)
    ensure_file_exists(POST_FILE)
    ensure_file_exists(PERSONAL_MSG_FILE)
    ensure_file_exists(GROUP_MSG_FILE)

    user_manager.load_users(USER_FILE)
    group_manager.load_groups(GROUP_FILE)
    post_manager.load_posts(POST_FILE)
    message_manager.load_personal_messages(PERSONAL_MSG_FILE)
    message_manager.load_group_messages(GROUP_MSG_FILE)


# 初始化加载
load_all_data()


# ------------------- 功能实现 -------------------
def addUser() -> None:
    """在管理员后台添加新用户（兼容 `user` 类的 role 参数）。"""
    identity = eg.choicebox("请选择身份类型", choices=["业主方", "物业方", "律师"])
    name = eg.enterbox("请输入用户名")
    password = eg.enterbox("请输入密码")
    # 位置获取
    location = eg.enterbox("请输入详细地址")

    # 基础校验
    if not all([identity, name, password, location]):
        eg.msgbox("所有字段都必须填写！")
        return

    # 创建并写入
    new_user = user(name, identity, password, location, role=identity)
    user_manager.add_user(new_user)
    user_manager.save_users(USER_FILE)
    eg.msgbox(f"用户 {name} 添加成功！")

def addPost() -> None:
    """在管理员后台添加新帖子。"""
    author = eg.enterbox("请输入作者用户名")
    title = eg.enterbox("请输入帖子标题")
    content = eg.enterbox("请输入帖子内容")
    section = eg.enterbox("请输入板块名称")

    if author and title and content and section:
        post_manager.add_post(author, title, content, section)
        post_manager.save_posts(POST_FILE)
        eg.msgbox("帖子添加成功！")
    else:
        eg.msgbox("所有字段不能为空！")


# ------------------- 查看数据 -------------------
def showUsers() -> None:
    """展示所有用户的简要信息（使用 easygui.textbox）。"""
    if not user_manager.user_list:
        eg.msgbox("暂无用户数据！")
        return

    lines = []
    for idx, u in enumerate(user_manager.user_list, 1):
        lines.append(
            f"===== 用户 {idx} =====\n"
            f"用户名：{u.username}\n"
            f"身份类型：{u.identity}\n"
            f"好友数量：{len(u.friends)}\n"
            f"密码：{u.password}\n"
            f"位置：{u.location}\n"
            f"状态：{u.state}\n"
        )
        print(f'用户 {idx}：{u.username}，身份：{u.identity}')
    eg.textbox("数据表","用户数据列表","\n".join(lines))


def showPosts() -> None:
    """展示所有帖子的详细信息。"""
    posts = post_manager.get_posts()
    if not posts:
        eg.msgbox("暂无帖子数据！")
        return

    lines = []
    for idx, p in enumerate(posts, 1):
        # 组织评论
        comment_lines = [
            f"  - 评论{c.id}：{c.author} | {c.content}（{c.time}）"
            for c in getattr(p, "comments", [])
        ]
        comments = "\n".join(comment_lines) if comment_lines else "  无评论"

        lines.append(
            f"===== 帖子 {idx}（ID：{p.id}） =====\n"
            f"作者：{p.author}\n"
            f"标题：{p.title}\n"
            f"板块：{p.section}\n"
            f"发布时间：{p.time}\n"
            f"内容：{p.content}\n"
            f"评论：\n{comments}\n"
        )
    eg.textbox("帖子数据列表", "\n".join(lines))


def showPersonalMessages() -> None:
    """展示所有私信（个人消息）。"""
    if not message_manager.personal_messages:
        eg.msgbox("暂无私信数据！")
        return

    lines = []
    for idx, msg in enumerate(message_manager.personal_messages, 1):
        sender = msg.sender.username if hasattr(msg.sender, "username") else str(msg.sender)
        receiver = msg.receiver.username if hasattr(msg.receiver, "username") else str(msg.receiver)

        lines.append(
            f"===== 私信 {idx} =====\n"
            f"发送者：{sender}\n"
            f"接收者：{receiver}\n"
            f"内容：{msg.content}\n"
            f"发送时间：{msg.timestamp}\n"
        )
    eg.textbox("私信数据列表", "\n".join(lines))


def showGroupMessages() -> None:
    """展示所有群消息。"""
    if not message_manager.group_messages:
        eg.msgbox("暂无群消息数据！")
        return

    lines = []
    for idx, msg in enumerate(message_manager.group_messages, 1):
        sender = msg.sender.username if hasattr(msg.sender, "username") else str(msg.sender)
        group = msg.group.name if hasattr(msg.group, "name") else str(msg.group)

        lines.append(
            f"===== 群消息 {idx} =====\n"
            f"发送者：{sender}\n"
            f"所属群组：{group}\n"
            f"内容：{msg.content}\n"
            f"发送时间：{msg.timestamp}\n"
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
            # 退出前统一保存所有持久化数据
            user_manager.save_users(USER_FILE)
            post_manager.save_posts(POST_FILE)
            message_manager.save_personal_messages(PERSONAL_MSG_FILE)
            message_manager.save_group_messages(GROUP_MSG_FILE)
            group_manager.save_groups(GROUP_FILE)
            eg.msgbox("数据已保存，退出成功！")
            break


if __name__ == "__main__":
    adminInterface()

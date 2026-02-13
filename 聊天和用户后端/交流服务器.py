from ChatMessage import MessageManage as MsgMgr
from user import userManage as UserMgr, user as UserClass  # 重命名避免变量冲突
from group import groupManage as GroupMgr
from post import PostManage
from flask import Flask, request, jsonify
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
from ChatMessage import personalChatMessage

app = Flask(__name__)
msg_manager = MsgMgr()
user_manager = UserMgr()
group_manager = GroupMgr()
post_manager = PostManage()

# ===================== 日志配置（记录详细错误） =====================
# 确保logs目录存在
os.makedirs('logs', exist_ok=True)
# 配置日志格式：包含时间、级别、模块、函数、行号、错误信息、堆栈
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
# 文件日志：5MB轮转，保留5个备份
file_handler = RotatingFileHandler(
    'logs/flask_api.log',
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
# 控制台日志
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
# 配置日志级别
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# 数据文件名同步
USER_FILE = r'D:\项目：ai法律平台\users.pkl'
GROUP_FILE = r'D:\项目：ai法律平台\groups.pkl'
POST_FILE = r'D:\项目：ai法律平台\posts.pkl'
PERSONAL_MSG_FILE = r'D:\项目：ai法律平台\personal_messages.pkl'
GROUP_MSG_FILE = r'D:\项目：ai法律平台\group_messages.pkl'

# ===================== 通用工具函数 =====================
def ensure_file_exists(filename):
    """确保文件存在，不存在则创建空文件"""
    if not os.path.exists(filename):
        with open(filename, 'wb') as f:
            pass  # 创建空文件
        logger.info(f"创建空数据文件：{filename}")

def return_error(message, code=400, request_data=None):
    """统一错误返回格式（中文）"""
    error_info = {
        "code": code,
        "error": message,
        "request_data": request_data or request.get_json(silent=True) or request.args.to_dict()
    }
    # 记录错误日志
    logger.error(f"接口错误：{message}，请求参数：{error_info['request_data']}")
    return jsonify(error_info), code

def return_success(data=None, message="操作成功"):
    """统一成功返回格式（中文）"""
    success_info = {
        "code": 200,
        "message": message,
        "data": data or {}
    }
    logger.info(f"接口成功：{message}，返回数据：{data}")
    return jsonify(success_info)

# ===================== 数据加载/保存 =====================
# 启动时自动加载数据
def load_all_data_on_start():
    try:
        ensure_file_exists(PERSONAL_MSG_FILE)
        ensure_file_exists(GROUP_MSG_FILE)
        ensure_file_exists(USER_FILE)
        ensure_file_exists(GROUP_FILE)
        ensure_file_exists(POST_FILE)
        
        msg_manager.load_personal_messages(PERSONAL_MSG_FILE)
        msg_manager.load_group_messages(GROUP_MSG_FILE)
        user_manager.load_users(USER_FILE)
        group_manager.load_groups(GROUP_FILE)
        post_manager.load_posts(POST_FILE)
        for user in user_manager.user_list:
            logger.info(f"加载用户：{user.username}，状态：{user.state}，好友数：{len(user.get_friends())}")
        logger.info("所有数据加载成功")
    except Exception as e:
        logger.error(f"数据加载失败：{str(e)}", exc_info=True)
        raise e

# 退出时自动保存数据，防止多次保存
_save_exit_called = False
def save_all_data_on_exit():
    global _save_exit_called
    if _save_exit_called:
        logger.warning("save_all_data_on_exit 已被调用，跳过重复保存")
        return
    _save_exit_called = True
    try:
        logger.info("开始保存所有数据（退出钩子）")
        msg_manager.save_personal_messages(PERSONAL_MSG_FILE)
        logger.info("个人消息保存完成")
        msg_manager.save_group_messages(GROUP_MSG_FILE)
        logger.info("群消息保存完成")
        user_manager.save_users(USER_FILE)
        logger.info("用户数据保存完成")
        group_manager.save_groups(GROUP_FILE)
        logger.info("群组数据保存完成")
        post_manager.save_posts(POST_FILE)
        logger.info("帖子数据保存完成")
        logger.info("所有数据保存成功")
    except Exception as e:
        logger.error(f"数据保存失败：{str(e)}", exc_info=True)
        raise e

import atexit
import signal
load_all_data_on_start()

# 捕获 Ctrl+C (SIGINT) 信号，保存数据后优雅退出
def handle_sigint(signum, frame):
    logger.info('收到 Ctrl+C (SIGINT) 信号，开始保存数据并退出...')
    try:
        save_all_data_on_exit()
    except Exception as e:
        logger.error(f'Ctrl+C 保存数据失败: {e}', exc_info=True)
    import sys
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

# ===================== 跨域配置 =====================
@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = app.make_response(('', 200))
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
        return response

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    return response

# ===================== 全局异常处理 =====================
@app.errorhandler(Exception)
def handle_global_exception(e):
    """捕获所有未处理的异常，返回中文错误信息"""
    error_msg = f"服务器内部错误：{str(e)}"
    logger.error(error_msg, exc_info=True)  # 记录完整堆栈
    return jsonify({
        "code": 500,
        "error": error_msg,
        "request_data": request.get_json(silent=True) or request.args.to_dict()
    }), 500

# ===================== 接口定义（带详细中文错误） =====================
@app.route('/load_all_data', methods=['POST'])
def load_all_data():
    try:
        load_all_data_on_start()
        return return_success(message="所有数据加载成功")
    except Exception as e:
        return return_error(f"数据加载失败：{str(e)}", 500)

@app.route('/save_all_data', methods=['POST'])
def save_all_data():
    try:
        save_all_data_on_exit()
        return return_success(message="所有数据保存成功")
    except Exception as e:
        return return_error(f"数据保存失败：{str(e)}", 500)

@app.route('/user_register', methods=['POST'])
def user_register():
    # 获取并校验参数
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    username = data.get('username')
    identity = data.get('identity')
    password = data.get('password')
    location = data.get('location')
    role = data.get('role') or identity

    # 校验必填参数
    missing_fields = []
    if not username:
        missing_fields.append('用户名(username)')
    if not identity:
        missing_fields.append('身份标识(identity)')
    if not password:
        missing_fields.append('密码(password)')
    if not location:
        missing_fields.append('位置(location)')
    
    if missing_fields:
        return return_error(f"注册失败：缺少必填参数 - {', '.join(missing_fields)}")
    
    # 校验用户名是否已存在
    if user_manager.find_user(username):
        return return_error(f"注册失败：用户名「{username}」已存在", 400)
    
    # 创建用户
    try:
        new_user = UserClass(username, identity, password, location, role)
        user_manager.add_user(new_user)
        logger.info(f"用户注册成功：{username}，身份：{identity}，位置：{location}")
        # 注册后立即保存用户数据
        try:
            user_manager.save_users(USER_FILE)
            logger.info(f"注册后用户数据已保存：{USER_FILE}")
        except Exception as e:
            logger.error(f"注册后保存用户数据失败：{e}", exc_info=True)
        return return_success(data={"user": new_user.get_profile()}, message=f"用户「{username}」注册成功")
    except Exception as e:
        return return_error(f"用户「{username}」注册失败：{str(e)}", 500)

@app.route('/user_login', methods=['POST'])
def user_login():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    username = data.get('username')
    password = data.get('password')

    # 校验参数
    if not username:
        return return_error("登录失败：缺少用户名(username)参数")
    if not password:
        return return_error("登录失败：缺少密码(password)参数")
    
    # 校验用户
    user_obj = user_manager.find_user(username)  # 重命名避免和类名冲突
    if not user_obj:
        return return_error(f"登录失败：用户名「{username}」不存在", 401)
    
    if user_obj.password != password:
        return return_error(f"登录失败：用户名「{username}」的密码错误", 401)
    
    # 更新状态并返回
    user_obj.set_state("online")
    profile = user_obj.get_profile()
    profile.pop("password", None)
    return return_success(data={"user": profile}, message=f"用户「{username}」登录成功")

@app.route('/user_friends', methods=['POST'])
def user_friends():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    username = data.get('username')
    if not username:
        return return_error("查询失败：缺少用户名(username)参数")
    
    user_obj = user_manager.find_user(username)
    if not user_obj:
        return return_error(f"查询失败：用户名「{username}」不存在", 404)
    
    friends = [friend.get_profile() for friend in user_obj.get_friends()]
    return return_success(data={"friends": friends}, message=f"查询到用户「{username}」的好友列表")

@app.route('/user_state_search', methods=['POST'])
def user_state_search():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    username = data.get('username')
    if not username:
        return return_error("查询失败：缺少用户名(username)参数")
    
    user_in_state = [u.get_profile() for u in user_manager.user_list if u.username == username]
    if not user_in_state:
        return return_error(f"查询失败：未找到用户名「{username}」的用户信息", 404)
    
    return return_success(data={"users": user_in_state}, message=f"查询到用户「{username}」的状态信息")

@app.route('/send_personal_message', methods=['POST'])
def send_personal_message():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    sender_name = data.get('sender')
    receiver_name = data.get('receiver')
    content = data.get('content')
    timestamp = data.get('timestamp')

    # 校验必填参数
    missing_fields = []
    if not sender_name:
        missing_fields.append('发送方(sender)')
    if not receiver_name:
        missing_fields.append('接收方(receiver)')
    if not content:
        missing_fields.append('消息内容(content)')
    if not timestamp:
        missing_fields.append('时间戳(timestamp)')
    
    if missing_fields:
        return return_error(f"发送私信失败：缺少必填参数 - {', '.join(missing_fields)}")
    
    # 校验用户是否存在
    sender = user_manager.find_user(sender_name)
    receiver = user_manager.find_user(receiver_name)
    
    error_msg = []
    if not sender:
        error_msg.append(f"发送方「{sender_name}」不存在")
    if not receiver:
        error_msg.append(f"接收方「{receiver_name}」不存在")
    
    if error_msg:
        return return_error(f"发送私信失败：{'; '.join(error_msg)}", 404)
    
    # 发送消息
    try:
        message = personalChatMessage(sender, receiver, content, timestamp)
        msg_manager.add_personal_message(message)
        # 发送私信后立即保存个人消息
        try:
            msg_manager.save_personal_messages(PERSONAL_MSG_FILE)
            logger.info(f"发送私信后个人消息已保存：{PERSONAL_MSG_FILE}")
        except Exception as e:
            logger.error(f"发送私信后保存个人消息失败：{e}", exc_info=True)
        return return_success(message=f"私信发送成功：从「{sender_name}」到「{receiver_name}」，内容：{content}")
    except Exception as e:
        return return_error(f"发送私信失败：{str(e)}", 500)

@app.route('/send_group_message', methods=['POST'])
def send_group_message():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    sender_name = data.get('sender')
    group_name = data.get('group')
    content = data.get('content')
    timestamp = data.get('timestamp')

    # 校验必填参数
    missing_fields = []
    if not sender_name:
        missing_fields.append('发送方(sender)')
    if not group_name:
        missing_fields.append('群组名(group)')
    if not content:
        missing_fields.append('消息内容(content)')
    if not timestamp:
        missing_fields.append('时间戳(timestamp)')
    
    if missing_fields:
        return return_error(f"发送群消息失败：缺少必填参数 - {', '.join(missing_fields)}")
    
    # 校验用户和群组是否存在
    sender = user_manager.find_user(sender_name)
    group = group_manager.find_group(group_name)
    
    error_msg = []
    if not sender:
        error_msg.append(f"发送方「{sender_name}」不存在")
    if not group:
        error_msg.append(f"群组「{group_name}」不存在")
    
    if error_msg:
        return return_error(f"发送群消息失败：{'; '.join(error_msg)}", 404)
    
    # 发送消息
    try:
        from ChatMessage import groupChatMessage
        message = groupChatMessage(sender, group, content, timestamp)
        msg_manager.add_group_message(message)
        return return_success(message=f"群消息发送成功：「{sender_name}」发送到群组「{group_name}」")
    except Exception as e:
        return return_error(f"发送群消息失败：{str(e)}", 500)
    
@app.route('/get_personal_messages', methods=['POST'])
def get_personal_messages():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    user1 = data.get('user1')
    user2 = data.get('user2')
    if not user1 or not user2:
        return return_error("查询失败：缺少 user1 或 user2 参数")
    # 校验用户是否存在
    u1 = user_manager.find_user(user1)
    u2 = user_manager.find_user(user2)
    if not u1 or not u2:
        return return_error(f"查询失败：用户不存在（{user1 if not u1 else ''} {user2 if not u2 else ''})", 404)
    # 查询消息
    try:
        # msg_manager.get_personal_messages(user1, user2) 应返回两人之间的消息列表
        # 每条消息应包含 sender, receiver, content, timestamp
        messages = msg_manager.get_personal_messages(user1, user2)
        # 转为前端友好格式，sender/receiver 一定转为字符串
        def to_str(val):
            # 如果是 user/personalChatMessage 等对象，优先取 username 属性，否则直接转字符串
            return getattr(val, 'username', str(val))

        msg_list = []
        for msg in messages:
            msg_list.append({
                'sender': to_str(getattr(msg, 'sender', getattr(msg, 'from_user', ''))),
                'receiver': to_str(getattr(msg, 'receiver', getattr(msg, 'to_user', ''))),
                'content': getattr(msg, 'content', getattr(msg, 'text', '')),
                'timestamp': getattr(msg, 'timestamp', getattr(msg, 'time', ''))
            })
        return return_success(data={"messages": msg_list}, message=f"查询到{user1}与{user2}的历史私聊消息，共{len(msg_list)}条")
    except Exception as e:
        logger.error(f"查询历史私聊消息失败：{e}", exc_info=True)
        return return_error(f"查询历史私聊消息失败：{str(e)}", 500)
    
@app.route('/get_posts', methods=['GET'])
def get_posts():
    section = request.args.get('section')
    if not section:
        return return_error("查询帖子失败：缺少板块名称(section)参数")
    
    try:
        posts = post_manager.get_posts(section)
        posts_dict = [p.to_dict() for p in posts]
        return return_success(
            data={"posts": posts_dict},
            message=f"查询到「{section}」板块下共{len(posts_dict)}条帖子"
        )
    except Exception as e:
        return return_error(f"查询「{section}」板块帖子失败：{str(e)}", 500)

@app.route('/create_post', methods=['POST'])
def create_post():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    author = data.get('author')
    title = data.get('title')
    content = data.get('content')
    section = data.get('section')

    # 校验必填参数
    missing_fields = []
    if not author:
        missing_fields.append('作者(author)')
    if not title:
        missing_fields.append('标题(title)')
    if not content:
        missing_fields.append('内容(content)')
    if not section:
        missing_fields.append('板块(section)')
    
    if missing_fields:
        return return_error(f"创建帖子失败：缺少必填参数 - {', '.join(missing_fields)}")
    
    # 校验作者是否存在
    if not user_manager.find_user(author):
        return return_error(f"创建帖子失败：作者「{author}」不存在", 404)
    
    try:
        post = post_manager.add_post(author, title, content, section)
        # 创建帖子后立即保存帖子数据
        try:
            post_manager.save_posts(POST_FILE)
            logger.info(f"创建帖子后帖子数据已保存：{POST_FILE}")
        except Exception as e:
            logger.error(f"创建帖子后保存帖子数据失败：{e}", exc_info=True)
        return return_success(
            data={"post": post.to_dict()},
            message=f"帖子「{title}」创建成功（ID：{post.post_id}）"
        )
    except Exception as e:
        return return_error(f"创建帖子「{title}」失败：{str(e)}", 500)

@app.route('/get_post_detail', methods=['GET'])
def get_post_detail():
    post_id_str = request.args.get('post_id')
    if not post_id_str:
        return return_error("查询帖子详情失败：缺少帖子ID(post_id)参数")
    
    # 校验ID格式
    try:
        post_id = int(post_id_str)
    except ValueError:
        return return_error(f"查询帖子详情失败：帖子ID「{post_id_str}」不是有效的数字")
    
    post = post_manager.get_post(post_id)
    if not post:
        return return_error(f"查询帖子详情失败：未找到ID为{post_id}的帖子", 404)
    
    return return_success(
        data={"post": post.to_dict()},
        message=f"查询到ID为{post_id}的帖子详情"
    )

@app.route('/add_comment', methods=['POST'])
def add_comment():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    post_id_str = data.get('post_id')
    author = data.get('author')
    content = data.get('content')

    # 校验必填参数
    missing_fields = []
    if not post_id_str:
        missing_fields.append('帖子ID(post_id)')
    if not author:
        missing_fields.append('评论作者(author)')
    if not content:
        missing_fields.append('评论内容(content)')
    
    if missing_fields:
        return return_error(f"添加评论失败：缺少必填参数 - {', '.join(missing_fields)}")
    
    # 校验帖子ID格式
    try:
        post_id = int(post_id_str)
    except ValueError:
        return return_error(f"添加评论失败：帖子ID「{post_id_str}」不是有效的数字")
    
    # 校验作者是否存在
    if not user_manager.find_user(author):
        return return_error(f"添加评论失败：作者「{author}」不存在", 404)
    
    # 添加评论
    comment = post_manager.add_comment(post_id, author, content)
    if not comment:
        return return_error(f"添加评论失败：未找到ID为{post_id}的帖子", 404)
    
    return return_success(
        data={"comment": comment.to_dict()},
        message=f"成功为ID{post_id}的帖子添加评论（评论作者：{author}）"
    )

@app.route('/user_logout', methods=['POST'])
def user_logout():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    username = data.get('username')
    if not username:
        return return_error("登出失败：缺少用户名(username)参数")
    
    user_obj = user_manager.find_user(username)
    if not user_obj:
        return return_error(f"登出失败：用户名「{username}」不存在", 404)
    
    user_obj.set_state("offline")
    return return_success(message=f"用户「{username}」已成功登出，状态更新为离线")

@app.route("/add_friend", methods=['POST'])
def add_friend():
    data = request.get_json()
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    
    username = data.get('username')
    friend_name = data.get('friend')

    # 校验参数
    if not username:
        return return_error("添加好友失败：缺少用户名(username)参数")
    if not friend_name:
        return return_error("添加好友失败：缺少好友用户名(friend)参数")
    
    if username == friend_name:
        return return_error(f"添加好友失败：不能添加自己（用户名：{username}）", 400)
    
    # 校验用户是否存在
    user_obj = user_manager.find_user(username)
    friend_obj = user_manager.find_user(friend_name)
    
    error_msg = []
    if not user_obj:
        error_msg.append(f"当前用户「{username}」不存在")
    if not friend_obj:
        error_msg.append(f"好友「{friend_name}」不存在")
    
    if error_msg:
        return return_error(f"添加好友失败：{'; '.join(error_msg)}", 404)
    
    # 校验是否已添加
    if friend_obj in user_obj.get_friends():
        return return_error(f"添加好友失败：「{username}」已添加「{friend_name}」为好友", 400)
    
    # 添加好友（双向）
    try:
        user_obj.add_friend(friend_obj)
        friend_obj.add_friend(user_obj)
        return return_success(message=f"添加好友成功：「{username}」和「{friend_name}」已互加为好友")
    except Exception as e:
        return return_error(f"添加好友失败：{str(e)}", 500)

if __name__ == '__main__':
    app.run(debug=False, port=3000)
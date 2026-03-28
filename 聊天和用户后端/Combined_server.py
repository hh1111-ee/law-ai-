from contextlib import asynccontextmanager
import threading
import asyncio
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple

import requests
import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from openpyxl import load_workbook
import pandas as pd

# ======================================================
# Combined_server.py
# 主服务：处理聊天、用户、群组和帖子管理的 FastAPI 应用。
# - 持久化采用本地 pickle 文件（演示/开发级别）。
# - 将阻塞的模型调用移到线程池以避免阻塞事件循环。
# - 所有磁盘写操作在全局线程锁下进行以避免并发写入冲突。
# 本文件侧重于可读性与可维护性，注释均为中文以方便本地开发阅读。
# ======================================================


# 让BASE_DIR指向上一级目录（主目录）
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CHAT_BACKEND_DIR = os.path.dirname(__file__)

if CHAT_BACKEND_DIR not in sys.path:
    sys.path.append(CHAT_BACKEND_DIR)

from ChatMessage import MessageManage as MsgMgr  # noqa: E402
from ChatMessage import personalChatMessage, groupChatMessage  # noqa: E402
from group import groupManage as GroupMgr  # noqa: E402
from post import PostManage  # noqa: E402
from user import user as UserClass  # noqa: E402
from user import userManage as UserMgr  # noqa: E402

# ===================== 日志配置 =====================
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "combined_server.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

# ===================== 数据路径 =====================
# 数据文件全部指向主目录
BASE_FLODER="数据库"
USER_FILE = os.path.join(BASE_DIR, BASE_FLODER, "users.pkl")
GROUP_FILE = os.path.join(BASE_DIR, BASE_FLODER, "groups.pkl")
POST_FILE = os.path.join(BASE_DIR, BASE_FLODER, "posts.pkl")
PERSONAL_MSG_FILE = os.path.join(BASE_DIR, BASE_FLODER, "personal_messages.pkl")
GROUP_MSG_FILE = os.path.join(BASE_DIR, BASE_FLODER, "group_messages.pkl")

DATA_PATH = os.path.join(BASE_DIR, "数据", "地区.xlsx")
CASES_FILE = os.path.join(BASE_DIR, "数据", "案号.xlsx")

# 日志目录也指向主目录
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
# ===================== 业务对象 =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    使用 FastAPI 的 lifespan 协调应用的启动与关闭。

    - 启动时在后台线程加载所有数据（避免阻塞事件循环）。
    - 关闭时记录 PID 并在后台线程执行一次性保存（调用 save_all_data_on_exit）。
    这样可以更集中地管理进程生命周期与日志，便于在多进程/热重载场景中排查哪个进程执行了保存操作。
    """
    try:
        await asyncio.to_thread(load_all_data_on_start)
        logger.info("Startup: 数据加载完成（PID=%s）", os.getpid())
    except Exception:
        logger.exception("Startup: 加载数据失败")
    try:
        yield
    finally:
        try:
            pid = os.getpid()
            logger.info("Shutdown: PID=%s 开始保存数据", pid)
            await asyncio.to_thread(save_all_data_on_exit)
            logger.info("Shutdown: PID=%s 保存数据完成", pid)
        except Exception:
            logger.exception("Shutdown: 保存数据失败")


app = FastAPI(lifespan=lifespan)

msg_manager = MsgMgr()
user_manager = UserMgr()
group_manager = GroupMgr()
post_manager = PostManage()
cases_df = pd.DataFrame() # 全局存储案例数据

# 全局写入锁，防止并发写文件
write_lock = threading.Lock()

# 控制本地模型并发调用数：根据机器能力设置为2或3
MODEL_CONCURRENCY = 2
model_semaphore = asyncio.Semaphore(MODEL_CONCURRENCY)


# Helpers: run blocking save operations in threadpool while holding write_lock
def _locked_exec(func, *args, **kwargs):
    """
    在持有模块级 `write_lock`（threading.Lock）的情况下，同步执行
    `func(*args, **kwargs)`。

    该函数设计为在后台线程中运行（例如通过 `asyncio.to_thread`），
    将锁的获取集中在这里可以统一控制对磁盘写入的互斥访问。
    """
    with write_lock:
        return func(*args, **kwargs)

async def run_in_thread_with_lock(func, *args, **kwargs):
    """
    将同步可调用对象下放到后台线程执行，同时保证执行期间持有
    全局的 `write_lock`。

    用法示例：`await run_in_thread_with_lock(some_manager.save, filename)`
    """
    return await asyncio.to_thread(_locked_exec, func, *args, **kwargs)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 处理 CORS 预检请求（OPTIONS），捕获所有路径的预检请求并返回 200
@app.options("/{path:path}")
async def preflight_handler(path: str, request: Request):
    """
    统一响应浏览器的 CORS 预检请求。CORS 中间件会自动添加必要响应头。
    """
    return JSONResponse(content={}, status_code=200)

# ===================== 工具函数 =====================

_DATA_CACHE: List[Dict[str, str]] = []
_DATA_MTIME: float = -1.0
_save_exit_called = False
# 用于保护数据缓存的异步锁
_data_cache_lock = asyncio.Lock()

4
def ensure_file_exists(filename: str) -> None:
    """
    确保指定路径的文件存在；如果不存在则创建一个空文件。

    说明：提前创建空文件可以简化后续的加载逻辑，使其无需在每处
    都先判断文件是否存在。
    """
    if not os.path.exists(filename):
        # Create parent dir if necessary
        parent = os.path.dirname(filename)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(filename, "wb"):
            pass
        logger.info("创建空数据文件：%s", filename)


def return_error(message: str, code: int = 400, request_data: Optional[Dict] = None) -> JSONResponse:
        """
        统一的错误 JSON 响应构造器，供各 API 接口使用。

        - `message`：可读的错误描述。
        - `code`：HTTP 状态码，同时写入返回体的 `code` 字段。
        - `request_data`：可选的请求数据，便于日志和调试。
        """
        error_info = {
            "code": code,
            "error": message,
            "request_data": request_data or {},
        }
        logger.error("接口错误：%s，请求参数：%s", message, error_info["request_data"])
        return JSONResponse(status_code=code, content=error_info)


def return_success(data: Optional[Dict] = None, message: str = "操作成功") -> JSONResponse:
    """
    统一的成功 JSON 响应构造器。
    """
    success_info = {
        "code": 200,
        "message": message,
        "data": data or {},
    }
    logger.info("接口成功：%s，返回数据：%s", message, data)
    return JSONResponse(content=success_info)


def load_all_data_on_start() -> None:
    """
    在应用启动时将所有持久化数据加载到内存中。

    函数会确保每个预期的持久化文件存在，然后调用各自的管理器
    进行反序列化加载。遇到错误仅记录日志，不会抛出，以便服务器
    在数据不完整时仍能启动用于开发/调试。
    """
    ensure_file_exists(PERSONAL_MSG_FILE)
    ensure_file_exists(GROUP_MSG_FILE)
    ensure_file_exists(USER_FILE)
    ensure_file_exists(GROUP_FILE)
    ensure_file_exists(POST_FILE)

    # 加载已持久化的消息与数据，各管理器负责自己的反序列化与完整性校验。
    msg_manager.load_personal_messages(PERSONAL_MSG_FILE)

    # 将 Excel 案例数据加载为 pandas DataFrame，用于检索与展示
    global cases_df
    try:
        if os.path.exists(CASES_FILE):
            cases_df = pd.read_excel(CASES_FILE, dtype=str).fillna("")
            logger.info("✅ 成功加载 %s 条案例", len(cases_df))
        else:
            logger.warning("❌ 案号文件不存在: %s", CASES_FILE)
            cases_df = pd.DataFrame()
    except Exception as e:
        logger.error("❌ 加载 Excel 失败: %s", e, exc_info=True)
        cases_df = pd.DataFrame()

    # 继续加载其余持久化结构
    msg_manager.load_group_messages(GROUP_MSG_FILE)
    user_manager.load_users(USER_FILE)
    group_manager.load_groups(GROUP_FILE)
    post_manager.load_posts(POST_FILE)

    # 输出已加载用户的简要信息，便于运维查看
    for user in user_manager.user_list:
        logger.info(
            "加载用户：%s，状态：%s，好友数：%s",
            user.username,
            user.state,
            len(user.get_friends()),
        )
    logger.info("所有数据加载成功")


def save_all_data_on_exit() -> None:
    """
    将内存中的所有数据保存到磁盘。该函数可被多次调用，但仅第一次
    会执行保存操作（通过 `_save_exit_called` 进行保护）。

    保存操作在 `write_lock` 下执行，以在关闭时提供单一的磁盘写入序列化点。
    """
    global _save_exit_called
    if _save_exit_called:
        logger.warning("save_all_data_on_exit 已被调用，跳过重复保存")
        return
    _save_exit_called = True
    logger.info("开始保存所有数据（退出钩子）")
    with write_lock:
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


def _safe_text(value) -> str:
    """将任意值规范为去除首尾空白的字符串；None 返回空字符串。"""
    if value is None:
        return ""
    return str(value).strip()


def _load_excel_rows() -> List[Dict[str, str]]:
    """
    从 `DATA_PATH` 指定的 Excel 文件加载行，并转换为字典列表，
    每项包含 'region'、'url'、'name' 三个字段，空行将被忽略。
    """
    if not os.path.exists(DATA_PATH):
        logger.warning("数据文件不存在: %s", DATA_PATH)
        return []

    workbook = load_workbook(DATA_PATH, read_only=True, data_only=True)
    sheet = workbook.active
    if sheet is None:
        logger.warning("Excel 表格未找到活动工作表: %s", DATA_PATH)
        return []
    rows: List[Dict[str, str]] = []

    for row in sheet.iter_rows(min_row=2, max_col=3, values_only=True):
        region = _safe_text(row[0])
        url = _safe_text(row[1])
        law_name = _safe_text(row[2])
        if not (region or url or law_name):
            continue
        rows.append({"region": region, "url": url, "name": law_name})

    return rows


async def get_data_rows() -> List[Dict[str, str]]:
    global _DATA_CACHE, _DATA_MTIME
    async with _data_cache_lock:
        try:
            mtime = os.path.getmtime(DATA_PATH)
        except OSError:
            mtime = -1.0

        if mtime != _DATA_MTIME:
            _DATA_CACHE = _load_excel_rows()
            _DATA_MTIME = mtime
            logger.info("已加载数据: %s 条", len(_DATA_CACHE))
        return _DATA_CACHE


def resolve_location(payload: Dict) -> Dict[str, str]:
    """
    从请求 payload 中解析用户位置信息，支持多种输入形式（顶层字段
    或嵌套的 `location` 字典）。返回包含 `province` 和 `city` 的字典；
    若省份缺失，默认返回 "全国"，城市会回退为省份。
    """
    location = payload.get("location") or {}
    province = _safe_text(payload.get("province") or location.get("province"))
    city = _safe_text(payload.get("city") or location.get("city"))
    region = _safe_text(payload.get("region"))

    if region and not province:
        province = region

    if not province:
        province = "全国"

    return {"province": province, "city": city or province}


def build_results(rows: List[Dict[str, str]], keyword: str) -> List[Dict[str, str]]:
    """
    按关键字过滤 `rows`，关键字可匹配 'name' 或 'region' 字段（不区分大小写），
    返回供 API 使用的标准化结果列表。
    """
    keyword_lower = keyword.lower()
    results: List[Dict[str, str]] = []

    for row in rows:
        name = row.get("name", "")
        region = row.get("region", "")
        if keyword_lower not in name.lower() and keyword_lower not in region.lower():
            continue
        results.append({
            "name": name or "未命名法律",
            "desc": f"地区: {region or '未知'}",
            "url": row.get("url", ""),
        })

    return results


def paginate_results(results: List[Dict[str, str]], page: int, page_size: int) -> Dict[str, object]:
    """简易分页辅助：约束 `page` 和 `page_size` 的合理范围并返回切片结果。"""
    page = max(page, 1)
    page_size = max(min(page_size, 50), 1)
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "results": results[start:end],
    }


def build_recommended(rows: List[Dict[str, str]], location: Dict[str, str]) -> List[Dict[str, str]]: 
    """
    根据 `location` 构建简短的推荐列表。

    通过 (name, url) 去重，最多返回 6 条结果。
    """
    province = location.get("province", "")
    city = location.get("city", "")

    if province and province != "全国":
        matched = [
            row
            for row in rows
            if province in row.get("region", "") or city in row.get("region", "")
        ]
    else:
        matched = rows

    recommended: List[Dict[str, str]] = []
    seen = set()
    for row in matched:
        key = (row.get("name", ""), row.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        recommended.append({
            "title": row.get("name", "未命名法律"),
            "desc": f"来自: {row.get('region', '') or '未知'}",
        })
        if len(recommended) >= 6:
            break

    return recommended


def send_personal_message_logic(sender_name: str, receiver_name: str, content: str, timestamp: str) -> Tuple[bool, str]:
    """
    校验发送者和接收者是否存在，创建 `personalChatMessage` 并添加到
    消息管理器中。消息的持久化由调用方异步触发，以避免在请求或
    WebSocket 主循环中执行阻塞 IO。
    """
    sender = user_manager.find_user(sender_name)
    receiver = user_manager.find_user(receiver_name)

    if not sender:
        return False, f"发送方「{sender_name}」不存在"
    if not receiver:
        return False, f"接收方「{receiver_name}」不存在"

    message = personalChatMessage(sender, receiver, content, timestamp)
    msg_manager.add_personal_message(message)

    # Persistence (disk write) should be triggered by the caller as a
    # background task. This keeps the hot path responsive.
    return True, "私信发送成功"


class ConnectionManager:
    def __init__(self) -> None:
        """管理按 `user_id` 索引的活动 WebSocket 连接。

        说明：此管理器为轻量实现，直接保存 `WebSocket` 对象；当应用
        水平扩展到多进程或多容器时，应替换为共享的 pub/sub 或实时层。
        """
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        # 接受来自客户端的 WebSocket 连接，并注册以便后续发送消息。
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info("用户 %s 建立WebSocket连接，当前活跃连接数：%s", user_id, len(self.active_connections))

    def disconnect(self, user_id: str) -> None:
        # 从活动连接表中移除用户的 WebSocket。该方法为同步调用，便于在
        # 清理路径中直接调用。
        if user_id in self.active_connections:
            self.active_connections.pop(user_id, None)
            logger.info("用户 %s 断开WebSocket连接，当前活跃连接数：%s", user_id, len(self.active_connections))

    async def send_to_user(self, user_id: str, message: Dict) -> None:
        # 向已连接的用户发送可序列化为 JSON 的消息；若连接不存在则记录日志并返回。
        websocket = self.active_connections.get(user_id)
        if not websocket:
            logger.warning("用户 %s 无活跃WebSocket连接，消息发送失败：%s", user_id, message)
            return
        await websocket.send_text(json.dumps(message, ensure_ascii=False))
        logger.info("向用户 %s 发送消息：%s", user_id, message)


manager = ConnectionManager()


async def _get_payload(request: Request) -> Optional[Dict]:
    try:
        return await request.json()
    except Exception:
        return None





# 使用 FastAPI 生命周期钩子替代模块级的 atexit 注册，以避免在
# 使用自动重载或多进程启动器时出现重复注册/多次保存的问题。


# 全局异常处理器，统一返回友好错误信息
@app.exception_handler(Exception)
async def handle_global_exception(request: Request, exc: Exception):
    error_msg = f"服务器内部错误：{exc}"
    logger.error(error_msg, exc_info=True)
    try:
        payload = await _get_payload(request) or dict(request.query_params)
    except Exception:
        payload = {}
    return JSONResponse(
        status_code=500,
        content={"code": 500, "error": error_msg, "request_data": payload},
    )
# ------------------- API: 获取所有关键词（去重）-------------------
@app.get('/api/keywords')
async def get_keywords():
    if cases_df.empty:
        return []
    # 将三个关键词列合并为一列，去重，并排除空字符串
    # 注意：pandas series 操作
    try:
        keywords = pd.concat([cases_df['关键词1'], cases_df['关键词2'], cases_df['关键词3']])
        unique_keywords = keywords[keywords != ''].unique().tolist()
        return unique_keywords
    except Exception as e:
        logger.error(f"Error getting keywords: {e}")
        return []

# ------------------- API: 获取案例（支持筛选）-------------------
@app.get('/api/cases')
async def get_cases(search: str = "", keyword: str = ""):
    if cases_df.empty:
        return []

    # 拷贝 DataFrame 避免修改原数据
    data = cases_df.copy()

    try:
        # 1. 按关键词筛选（精确匹配任意一个关键词列）
        if keyword:
            mask = (
                (data['关键词1'] == keyword) |
                (data['关键词2'] == keyword) |
                (data['关键词3'] == keyword)
            )
            data = data[mask]

        # 2. 按搜索词筛选（在案号或摘要中模糊匹配，大小写不敏感）
        if search:
            mask = (
                data['案号'].str.contains(search, case=False, na=False) |
                data['摘要'].str.contains(search, case=False, na=False)
            )
            data = data[mask]

        # 转换为字典列表返回
        result = data.to_dict(orient='records')
        return result
    except Exception as e:
        logger.error(f"Error getting cases: {e}")
        return []

# 已在文件顶部注册的全局异常处理器将处理所有未捕获异常，
# 避免在文件中重复定义同名处理函数导致覆盖或类型提示冲突。


@app.get("/")
async def root():
    return PlainTextResponse("Combined server is running.")


@app.get("/config")
async def get_config():
    # 返回前端可读取的运行时配置（可根据部署环境修改）
    # 在生产/HTTPS 环境下，前端应使用相对路径以避免混合内容被浏览器阻止
    return JSONResponse(content={"API_BASE": ""})


@app.post("/load_all_data")
async def load_all_data():
    try:
        load_all_data_on_start()
        return return_success(message="所有数据加载成功")
    except Exception as exc:
        return return_error(f"数据加载失败：{exc}", 500)


@app.post("/save_all_data")
async def save_all_data():
    try:
        save_all_data_on_exit()
        return return_success(message="所有数据保存成功")
    except Exception as exc:
        return return_error(f"数据保存失败：{exc}", 500)


@app.post("/user_register")
async def user_register(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    userid=data.get("id")
    username = data.get("username")
    identity = data.get("identity")
    password = data.get("password")
    location = data.get("location")
    role = data.get("role") or identity

    missing_fields = []
    if not userid:
        missing_fields.append("用户ID(id)")
    if not username:
        missing_fields.append("用户名(username)")
    if not identity:
        missing_fields.append("身份标识(identity)")
    if not password:
        missing_fields.append("密码(password)")
    if not location:
        missing_fields.append("位置(location)")

    if missing_fields:
        return return_error(f"注册失败：缺少必填参数 - {', '.join(missing_fields)}")

    if user_manager.find_user(username):
        return return_error(f"注册失败：用户名「{username}」已存在", 400)

    try:
        # 注册必须提供 id（作为账号）
        new_user = UserClass(userid, username, identity, password, location, role)
        user_manager.add_user(new_user)
        logger.info("用户注册成功：%s，身份：%s，位置：%s", username, identity, location)
        try:
            await run_in_thread_with_lock(user_manager.save_users, USER_FILE)
            logger.info("注册后用户数据已保存：%s", USER_FILE)
        except Exception as exc:
            logger.error("注册后保存用户数据失败：%s", exc, exc_info=True)
        profile = new_user.get_profile()
        profile['id'] = getattr(new_user, 'id', userid)
        return return_success(data={"user": profile}, message=f"用户「{username}」注册成功")
    except Exception as exc:
        return return_error(f"用户「{username}」注册失败：{exc}", 500)


@app.post("/user_login")
async def user_login(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    userid = data.get("id")
    password = data.get("password")

    if not userid:
        return return_error("登录失败：缺少用户ID(id)参数")
    if not password:
        return return_error("登录失败：缺少密码(password)参数")

    user_obj = None
    for u in user_manager.user_list:
        if getattr(u, 'id', None) == userid:
            user_obj = u
            break
    if not user_obj:
        return return_error(f"登录失败：用户ID「{userid}」不存在", 401)

    if user_obj.password != password:
        return return_error(f"登录失败：用户ID「{userid}」的密码错误", 401)

    user_obj.set_state("online")
    profile = user_obj.get_profile()
    profile.pop("password", None)
    profile['id'] = getattr(user_obj, 'id', None)
    return return_success(data={"user": profile}, message=f"用户登录成功")


@app.post("/user_friends")
async def user_friends(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    username = data.get("username")
    if not username:
        return return_error("查询失败：缺少用户名(username)参数")

    user_obj = user_manager.find_user(username)
    if not user_obj:
        return return_error(f"查询失败：用户名「{username}」不存在", 404)

    friends = [friend.get_profile() for friend in user_obj.get_friends()]
    return return_success(data={"friends": friends}, message=f"查询到用户「{username}」的好友列表")


@app.post("/user_state_search")
async def user_state_search(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    username = data.get("username")
    userid = data.get("id")
    if not username and not userid:
        return return_error("查询失败：缺少用户名(username)或用户ID(id)参数")

    user_in_state = []
    for u in user_manager.user_list:
        if username and getattr(u, 'username', None) == username:
            p = u.get_profile()
            p['id'] = getattr(u, 'id', None)
            user_in_state.append(p)
        elif userid and getattr(u, 'id', None) == userid:
            p = u.get_profile()
            p['id'] = getattr(u, 'id', None)
            user_in_state.append(p)

    if not user_in_state:
        return return_error(f"查询失败：未找到对应的用户信息", 404)

    return return_success(data={"users": user_in_state}, message="查询到用户的状态信息")


@app.post("/send_personal_message")
async def send_personal_message(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    sender_name = data.get("sender")
    receiver_name = data.get("receiver")
    content = data.get("content")
    timestamp = data.get("timestamp")

    missing_fields = []
    if not sender_name:
        missing_fields.append("发送方(sender)")
    if not receiver_name:
        missing_fields.append("接收方(receiver)")
    if not content:
        missing_fields.append("消息内容(content)")
    if not timestamp:
        missing_fields.append("时间戳(timestamp)")

    if missing_fields:
        return return_error(f"发送私信失败：缺少必填参数 - {', '.join(missing_fields)}")

    # 类型断言：上方已验证必填字段存在，向类型检查器表明它们为 str
    assert isinstance(sender_name, str) and isinstance(receiver_name, str) and isinstance(content, str) and isinstance(timestamp, str)

    ok, message = send_personal_message_logic(sender_name, receiver_name, content, timestamp)
    if not ok:
        return return_error(f"发送私信失败：{message}", 404)

    # 异步保存消息，避免阻塞当前请求
    try:
        asyncio.create_task(run_in_thread_with_lock(msg_manager.save_personal_messages, PERSONAL_MSG_FILE))
    except Exception:
        logger.exception("异步保存私信消息任务创建失败")

    return return_success(message=f"私信发送成功：从「{sender_name}」到「{receiver_name}」，内容：{content}")


@app.post("/send_group_message")
async def send_group_message(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    sender_name = data.get("sender")
    group_name = data.get("group")
    content = data.get("content")
    timestamp = data.get("timestamp")

    missing_fields = []
    if not sender_name:
        missing_fields.append("发送方(sender)")
    if not group_name:
        missing_fields.append("群组名(group)")
    if not content:
        missing_fields.append("消息内容(content)")
    if not timestamp:
        missing_fields.append("时间戳(timestamp)")

    if missing_fields:
        return return_error(f"发送群消息失败：缺少必填参数 - {', '.join(missing_fields)}")

    sender = user_manager.find_user(sender_name)
    group = group_manager.find_group(group_name)

    error_msg = []
    if not sender:
        error_msg.append(f"发送方「{sender_name}」不存在")
    if not group:
        error_msg.append(f"群组「{group_name}」不存在")

    if error_msg:
        return return_error(f"发送群消息失败：{'; '.join(error_msg)}", 404)

    # 确保 sender 和 group 已经存在（类型检查提示）
    assert sender is not None and group is not None
    try:
        assert isinstance(content, str) and isinstance(timestamp, str)
        message = groupChatMessage(sender, group, content, timestamp)
        msg_manager.add_group_message(message)
        return return_success(message=f"群消息发送成功：「{sender_name}」发送到群组「{group_name}」")
    except Exception as exc:
        return return_error(f"发送群消息失败：{exc}", 500)


@app.post("/get_personal_messages")
async def get_personal_messages(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")
    user1 = data.get("user1")
    user2 = data.get("user2")
    if not user1 or not user2:
        return return_error("查询失败：缺少 user1 或 user2 参数")

    u1 = user_manager.find_user(user1)
    u2 = user_manager.find_user(user2)
    if not u1 or not u2:
        return return_error(f"查询失败：用户不存在（{user1 if not u1 else ''} {user2 if not u2 else ''})", 404)

    try:
        messages = msg_manager.get_personal_messages(user1, user2)

        def to_str(val):
            return getattr(val, "username", str(val))

        msg_list = []
        for msg in messages:
            msg_list.append(
                {
                    "sender": to_str(getattr(msg, "sender", getattr(msg, "from_user", ""))),
                    "receiver": to_str(getattr(msg, "receiver", getattr(msg, "to_user", ""))),
                    "content": getattr(msg, "content", getattr(msg, "text", "")),
                    "timestamp": getattr(msg, "timestamp", getattr(msg, "time", "")),
                }
            )
        return return_success(data={"messages": msg_list}, message=f"查询到{user1}与{user2}的历史私聊消息，共{len(msg_list)}条")
    except Exception as exc:
        logger.error("查询历史私聊消息失败：%s", exc, exc_info=True)
        return return_error(f"查询历史私聊消息失败：{exc}", 500)


@app.get("/get_posts")
async def get_posts(request: Request):
    """
    获取帖子列表，支持按板块(section)筛选和按关键词(keyword)搜索。
    :param section: 板块名称（可选，如 'contract', 'owners', 'security', 'public_use'）
    :param keyword: 搜索关键词（可选）
    """
    section = request.query_params.get("section")
    keyword = request.query_params.get("keyword")

    try:
        # 获取所有帖子或特定板块的帖子
        if section:
            posts = post_manager.get_posts(section)
        else:
            posts = post_manager.get_posts(None) # 获取所有

        # 如果有关键词，进行过滤
        if keyword:
            keyword = str(keyword).lower().strip()
            filtered_posts = []
            for p in posts:
                title = str(getattr(p, 'title', '')).lower()
                content = str(getattr(p, 'content', '')).lower()
                if keyword in title or keyword in content:
                    filtered_posts.append(p)
            posts = filtered_posts

        # 按时间倒序排列（最新的在前）
        def parse_time(p):
            t = getattr(p, 'time', None)
            if not t:
                return datetime.datetime.min
            try:
                if isinstance(t, str):
                    return datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
                return t
            except Exception:
                return datetime.datetime.min

        posts.sort(key=parse_time, reverse=True)

        posts_dict = [p.to_dict() for p in posts]
        
        msg = f"查询成功"
        if section:
            msg += f"，板块「{section}」"
        if keyword:
            msg += f"，关键词「{keyword}」"
        msg += f"，共{len(posts_dict)}条数据"

        return return_success(
            data={"posts": posts_dict},
            message=msg,
        )
    except Exception as exc:
        return return_error(f"查询帖子失败：{exc}", 500, request_data=dict(request.query_params))


@app.get("/get_hot_posts")
async def get_hot_posts(limit: int = 8):
    """返回按热度排序的帖子（默认 top N=8）。
    当前热度计算：以评论数为主，时间为次要排序键（评论数降序，时间降序）。
    """
    try:
        posts = post_manager.get_posts(None)

        def parse_time(p):
            t = getattr(p, 'time', None)
            if not t:
                return datetime.datetime.min
            try:
                return datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return datetime.datetime.min

        posts_sorted = sorted(
            posts,
            key=lambda p: (len(getattr(p, 'comments', [])) if getattr(p, 'comments', None) is not None else 0, parse_time(p)),
            reverse=True,
        )

        top = posts_sorted[: max(1, int(limit))]
        posts_dict = [p.to_dict() for p in top]
        return return_success(data={"posts": posts_dict}, message=f"查询到热帖 top {len(posts_dict)}")
    except Exception as exc:
        logger.error("获取热帖失败：%s", exc, exc_info=True)
        return return_error(f"查询热帖失败：{exc}", 500)


@app.post("/create_post")
async def create_post(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    author = data.get("author")
    title = data.get("title")
    content = data.get("content")
    section = data.get("section")

    missing_fields = []
    if not author:
        missing_fields.append("作者(author)")
    if not title:
        missing_fields.append("标题(title)")
    if not content:
        missing_fields.append("内容(content)")
    if not section:
        missing_fields.append("板块(section)")

    if missing_fields:
        return return_error(f"创建帖子失败：缺少必填参数 - {', '.join(missing_fields)}")

    if not user_manager.find_user(author):
        return return_error(f"创建帖子失败：作者「{author}」不存在", 404)

    try:
        post = post_manager.add_post(author, title, content, section)
        try:
            await run_in_thread_with_lock(post_manager.save_posts, POST_FILE)
            logger.info("创建帖子后帖子数据已保存：%s", POST_FILE)
        except Exception as exc:
            logger.error("创建帖子后保存帖子数据失败：%s", exc, exc_info=True)
        return return_success(
            data={"post": post.to_dict()},
            message=f"帖子「{title}」创建成功（ID：{post.id}）",
        )
    except Exception as exc:
        return return_error(f"创建帖子「{title}」失败：{exc}", 500)


@app.get("/get_post_detail")
async def get_post_detail(request: Request):
    post_id_str = request.query_params.get("post_id")
    if not post_id_str:
        return return_error("查询帖子详情失败：缺少帖子ID(post_id)参数", request_data=dict(request.query_params))

    try:
        post_id = int(str(post_id_str))
    except ValueError:
        return return_error(f"查询帖子详情失败：帖子ID「{post_id_str}」不是有效的数字")

    post = post_manager.get_post(post_id)
    if not post:
        return return_error(f"查询帖子详情失败：未找到ID为{post_id}的帖子", 404)

    return return_success(data={"post": post.to_dict()}, message=f"查询到ID为{post_id}的帖子详情")


@app.post("/add_comment")
async def add_comment(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    post_id_str = data.get("post_id")
    author = data.get("author")
    content = data.get("content")

    missing_fields = []
    if not post_id_str:
        missing_fields.append("帖子ID(post_id)")
    if not author:
        missing_fields.append("评论作者(author)")
    if not content:
        missing_fields.append("评论内容(content)")

    if missing_fields:
        return return_error(f"添加评论失败：缺少必填参数 - {', '.join(missing_fields)}")

    try:
        post_id = int(str(post_id_str))
    except ValueError:
        return return_error(f"添加评论失败：帖子ID「{post_id_str}」不是有效的数字")

    if not user_manager.find_user(author):
        return return_error(f"添加评论失败：作者「{author}」不存在", 404)

    comment = post_manager.add_comment(post_id, author, content)
    if not comment:
        return return_error(f"添加评论失败：未找到ID为{post_id}的帖子", 404)
    try:
        await run_in_thread_with_lock(post_manager.save_posts, POST_FILE)
        logger.info("添加评论后帖子数据已保存：%s", POST_FILE)
    except Exception as exc:
        logger.error("添加评论后保存帖子数据失败：%s", exc, exc_info=True)
    return return_success(
        data={"comment": comment.to_dict()},
        message=f"成功为ID{post_id}的帖子添加评论（评论作者：{author}）",
    )


@app.post("/user_logout")
async def user_logout(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    username = data.get("username")
    userid = data.get("id")
    if not username and not userid:
        return return_error("登出失败：缺少用户名(username)或用户ID(id)参数")

    user_obj = None
    if username:
        user_obj = user_manager.find_user(username)
    if not user_obj and userid:
        for u in user_manager.user_list:
            if getattr(u, 'id', None) == userid:
                user_obj = u
                break

    if not user_obj:
        return return_error("登出失败：用户不存在", 404)

    user_obj.set_state("offline")
    return return_success(message=f"用户已成功登出，状态更新为离线")


@app.post("/add_friend")
async def add_friend(request: Request):
    data = await _get_payload(request)
    if not data:
        return return_error("请求参数不能为空，请传入JSON格式数据")

    username = data.get("username")
    friend_name = data.get("friend")

    if not username:
        return return_error("添加好友失败：缺少用户名(username)参数")
    if not friend_name:
        return return_error("添加好友失败：缺少好友用户名(friend)参数")

    if username == friend_name:
        return return_error(f"添加好友失败：不能添加自己（用户名：{username}）", 400)

    user_obj = user_manager.find_user(username)
    friend_obj = user_manager.find_user(friend_name)

    error_msg = []
    if not user_obj:
        error_msg.append(f"当前用户「{username}」不存在")
    if not friend_obj:
        error_msg.append(f"好友「{friend_name}」不存在")

    if error_msg:
        return return_error(f"添加好友失败：{'; '.join(error_msg)}", 404)
    # 向类型检查器表明 user_obj 和 friend_obj 已存在
    assert user_obj is not None and friend_obj is not None

    if friend_obj in user_obj.get_friends():
        return return_error(f"添加好友失败：「{username}」已添加「{friend_name}」为好友", 400)

    try:
        user_obj.add_friend(friend_obj)
        friend_obj.add_friend(user_obj)
        return return_success(message=f"添加好友成功：「{username}」和「{friend_name}」已互加为好友")
    except Exception as exc:
        return return_error(f"添加好友失败：{exc}", 500)


@app.post("/search")
async def api_search(request: Request):
    payload = await _get_payload(request) or {}
    keyword = _safe_text(payload.get("keyword"))
    if not keyword:
        return return_error("请提供搜索关键字", 400)

    rows = await get_data_rows()
    location = resolve_location(payload)
    all_results = build_results(rows, keyword)
    recommended = build_recommended(rows, location)

    try:
        page = int(payload.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(payload.get("page_size", 5))
    except (TypeError, ValueError):
        page_size = 5

    page_data = paginate_results(all_results, page, page_size)

    return JSONResponse(
        content={
            "location": location,
            "recommended": recommended,
            "results": page_data["results"],
            "page": page_data["page"],
            "page_size": page_data["page_size"],
            "total": page_data["total"],
        }
    )


@app.post("/search_posts")
async def search_posts(request: Request):
    data = await _get_payload(request) or {}
    keyword = _safe_text(data.get("keyword"))
    if not keyword:
        return return_error("请提供搜索关键字", 400)

    results = []
    for p in post_manager.post_list:
        title = _safe_text(getattr(p, 'title', ''))
        content = _safe_text(getattr(p, 'content', ''))
        if keyword.lower() in title.lower() or keyword.lower() in content.lower():
            results.append(p.to_dict())

    return return_success(data={"posts": results}, message=f"找到{len(results)}条相关帖子")


@app.post("/location")
@app.get("/location")
async def api_location(request: Request):
    if request.method == "GET":
        payload = {}
    else:
        payload = await _get_payload(request) or {}

    # 首先尝试使用请求体或 query 中的位置信息
    location = resolve_location(payload)

    # 如果前端未提供任何省市信息，则尝试从请求中提取客户端 IP 并调用第三方 IP 定位服务回退
    def _get_client_ip(req: Request) -> str:
        # 支持常见代理头
        forwarded = req.headers.get("x-forwarded-for") or req.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        try:
            client = getattr(req, "client", None)
            host = getattr(client, "host", None)
            return host or ""
        except Exception:
            return ""

    def _resolve_ip_to_location(ip: str) -> dict:
        if not ip:
            return {}
        try:
            # 使用 ip-api 免费接口（字段：status, regionName, city）
            resp = requests.get(f"http://ip-api.com/json/{ip}?fields=status,regionName,city,query", timeout=5)
            data = resp.json()
            if data.get("status") == "success":
                province = data.get("regionName") or ""
                city = data.get("city") or province or ""
                return {"province": province, "city": city}
        except Exception as exc:
            logger.debug("IP 定位请求失败：%s", exc)
        return {}

    # 规范化为字段安全的字典视图，避免类型检查器报错
    payload_dict = payload if isinstance(payload, dict) else {}

    # 判断是否需要 IP 回退：payload 未提供 province/city 且解析后只有默认值
    # 显式取值以避免在静态检查器中对 .get 的不确定性
    province_val = payload_dict["province"] if "province" in payload_dict else None
    city_val = payload_dict["city"] if "city" in payload_dict else None
    location_val = payload_dict["location"] if ("location" in payload_dict and isinstance(payload_dict["location"], dict)) else {}
    location_province = location_val["province"] if (isinstance(location_val, dict) and "province" in location_val) else None
    location_city = location_val["city"] if (isinstance(location_val, dict) and "city" in location_val) else None

    provided_province = bool(province_val or location_province)
    provided_city = bool(city_val or location_city)

    if not provided_province and not provided_city:
        client_ip = _get_client_ip(request)
        logger.info("/location: 尝试使用客户端 IP 回退定位，ip=%s", client_ip)
        ip_location = _resolve_ip_to_location(client_ip)
        if ip_location:
            # 以 IP 定位结果覆盖或补全 location
            location = resolve_location({"province": ip_location.get("province"), "city": ip_location.get("city")})

    return JSONResponse(content={"location": location})


@app.post("/api/legal")
async def legal_chat(request: Request):
    data = await _get_payload(request)
    if not data or "question" not in data:
        return return_error("请输入要咨询的法律问题", 400)

    question = str(data.get("question", "")).strip()
    if not question:
        return return_error("问题不能为空", 400)

    payload = {
        "model": "deepseek-v3.1:671b-cloud",
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": "你是一名中华人民共和国执业律师，请在回答中**必须**引用具体的法条编号（如《民法典》第23条）。\n如果法律里没有对应条文，请直接回复“暂无相关法条”。\n请使用简洁、正式的法律语言，切勿捏造法条内容。",
            },
            {"role": "user", "content": question},
        ],
    }

    try:
        logger.info("→ 请求 Ollama（受并发限制）: %s...", question[:30])
        # 在异步环境下使用 Semaphore 限制并发，并把阻塞的 requests 调用移到线程池中执行
        async with model_semaphore:
            try:
                resp = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=30)
                    ),
                    timeout=40,
                )
            except asyncio.TimeoutError:
                logger.exception("❌ 模型调用超时")
                return return_error("模型调用超时，请稍后重试", 504)

        resp.raise_for_status()
        answer = resp.json().get("message", {}).get("content", "暂无相关法条")
        logger.info("✅ 得到答案（前50字符）: %s", answer[:50])
        return JSONResponse(content={"answer": answer})
    except requests.exceptions.ConnectionError:
        logger.exception("❌ 无法连接到 Ollama")
        return return_error("无法连接到 Ollama，请先启动 Ollama", 500)
    except Exception as exc:
        logger.exception("❌ 未知错误")
        return return_error(f"服务器内部错误：{exc}", 500)


@app.websocket("/ws/private")
async def websocket_private_chat(websocket: WebSocket):
    user_id = websocket.query_params.get("user_id")
    if not user_id:
        logger.error("WebSocket连接失败：未提供user_id参数，关闭连接")
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            logger.info("收到用户 %s 发送的原始数据：%s", user_id, data)

            try:
                payload = json.loads(data)
            except json.JSONDecodeError as exc:
                logger.error("用户 %s JSON解析失败：%s", user_id, exc)
                await manager.send_to_user(user_id, {"type": "error", "message": "Invalid JSON payload."})
                continue

            sender = payload.get("from")
            receiver = payload.get("to")
            content = payload.get("content")
            timestamp = payload.get("ts")

            missing_fields = []
            if not sender:
                missing_fields.append("from")
            if not receiver:
                missing_fields.append("to")
            if not content:
                missing_fields.append("content")

            if missing_fields:
                error_msg = f"缺失必要字段：{', '.join(missing_fields)}"
                logger.error("用户 %s %s，payload：%s", user_id, error_msg, payload)
                await manager.send_to_user(user_id, {"type": "error", "message": "Missing fields: from/to/content."})
                continue

            ok, error_message = send_personal_message_logic(sender, receiver, content, timestamp)
            if not ok:
                logger.warning("WebSocket消息保存失败：%s", error_message)

            # 异步保存消息，避免阻塞 WebSocket 循环
            try:
                asyncio.create_task(run_in_thread_with_lock(msg_manager.save_personal_messages, PERSONAL_MSG_FILE))
            except Exception:
                logger.exception("异步保存私信消息任务创建失败")

            send_msg = {
                "type": "message",
                "from": sender,
                "to": receiver,
                "content": content,
                "ts": timestamp,
            }
            await manager.send_to_user(receiver, send_msg)

    except WebSocketDisconnect:
        logger.info("用户 %s 主动断开WebSocket连接", user_id)
        manager.disconnect(user_id)
    except Exception as exc:
        logger.critical("用户 %s 连接发生未预期异常：%s", user_id, exc, exc_info=True)
        manager.disconnect(user_id)
        await websocket.close(code=1011)


if __name__ == "__main__":
    import uvicorn

    # 以模块方式直接运行时，禁止 uvicorn 的 reload（reload 会启动
    # 监视器进程和子进程，可能导致多进程重复保存）。开发时推荐
    # 使用 `uvicorn 聊天和用户后端.Combined_server:app --reload` 在命令行
    uvicorn.run("Combined_server:app", host="0.0.0.0", port=8000, reload=False)

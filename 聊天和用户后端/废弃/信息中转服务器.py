from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import json
import requests
import logging
from logging.handlers import RotatingFileHandler

app = FastAPI()

# ===================== 日志配置 =====================
# 1. 定义日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 2. 配置日志存储路径（基于项目根目录）
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'websocket_chat.log')

# 3. 配置日志处理器（同时输出到控制台和文件，文件按大小轮转）
# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
# 文件处理器（轮转：单个文件最大5MB，保留5个备份）
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# 4. 配置根日志
logging.basicConfig(
    level=logging.INFO,  # 日志级别：DEBUG < INFO < WARNING < ERROR < CRITICAL
    handlers=[console_handler, file_handler]
)
# 获取当前模块的日志实例
logger = logging.getLogger(__name__)

# ===================== 原有路径配置 =====================
HTML_DIR = os.path.join(BASE_DIR, 'html')
CSS_DIR = os.path.join(BASE_DIR, 'css')
JS_DIR = os.path.join(BASE_DIR, 'js')

API_BASE = 'http://localhost:3000'

# ===================== 连接管理器（增加日志） =====================
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        # 记录连接建立日志
        logger.info(f"用户 {user_id} 建立WebSocket连接，当前活跃连接数：{len(self.active_connections)}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            self.active_connections.pop(user_id, None)
            # 记录连接断开日志
            logger.info(f"用户 {user_id} 断开WebSocket连接，当前活跃连接数：{len(self.active_connections)}")

    async def send_to_user(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)
        if not websocket:
            # 记录警告：接收方无活跃连接
            logger.warning(f"用户 {user_id} 无活跃WebSocket连接，消息发送失败：{message}")
            return
        await websocket.send_text(json.dumps(message, ensure_ascii=False))
        # 记录消息发送日志
        logger.info(f"向用户 {user_id} 发送消息：{message}")

manager = ConnectionManager()

# ===================== 页面与静态资源路由 =====================
@app.get('/')
def serve_private_chat():
    file_path = os.path.join(HTML_DIR, '私聊界面.html')
    logger.info(f"请求根路径，返回私聊页面：{file_path}")
    return FileResponse(file_path)

app.mount('/css', StaticFiles(directory=CSS_DIR), name='css')
app.mount('/js', StaticFiles(directory=JS_DIR), name='js')

# ===================== WebSocket核心逻辑（增加日志） =====================
@app.websocket('/ws/private')
async def websocket_private_chat(websocket: WebSocket):
    user_id = websocket.query_params.get('user_id')
    if not user_id:
        logger.error("WebSocket连接失败：未提供user_id参数，关闭连接")
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            logger.info(f"收到用户 {user_id} 发送的原始数据：{data}")

            # 解析JSON
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as e:
                error_msg = f"JSON解析失败：{str(e)}"
                logger.error(f"用户 {user_id} {error_msg}")
                await manager.send_to_user(user_id, {
                    'type': 'error',
                    'message': 'Invalid JSON payload.'
                })
                continue

            # 校验字段
            sender = payload.get('from')
            receiver = payload.get('to')
            content = payload.get('content')
            timestamp = payload.get('ts')

            if not sender or not receiver or not content:
                missing_fields = []
                if not sender: missing_fields.append('from')
                if not receiver: missing_fields.append('to')
                if not content: missing_fields.append('content')
                error_msg = f"缺失必要字段：{', '.join(missing_fields)}"
                logger.error(f"用户 {user_id} {error_msg}，payload：{payload}")
                await manager.send_to_user(user_id, {
                    'type': 'error',
                    'message': 'Missing fields: from/to/content.'
                })
                continue

            # 调用外部API
            try:
                api_url = f'{API_BASE}/send_personal_message'
                api_payload = {
                    'sender': sender,
                    'receiver': receiver,
                    'content': content,
                    'timestamp': timestamp
                }
                logger.info(f"调用外部API：{api_url}，参数：{api_payload}")
                response = requests.post(
                    api_url,
                    json=api_payload,
                    timeout=3
                )
                response.raise_for_status()  # 抛出HTTP状态码异常
                logger.info(f"外部API调用成功，响应状态码：{response.status_code}")
            except requests.RequestException as e:
                error_msg = f"外部API调用失败：{str(e)}"
                logger.error(f"用户 {user_id} {error_msg}")
                # 仅记录错误，不中断消息转发

            # 转发消息给接收方
            send_msg = {
                'type': 'message',
                'from': sender,
                'to': receiver,
                'content': content,
                'ts': timestamp
            }
            await manager.send_to_user(receiver, send_msg)

    except WebSocketDisconnect:
        logger.info(f"用户 {user_id} 主动断开WebSocket连接")
        manager.disconnect(user_id)
    except Exception as e:
        # 捕获所有未预期的异常，避免服务崩溃
        logger.critical(f"用户 {user_id} 连接发生未预期异常：{str(e)}", exc_info=True)
        manager.disconnect(user_id)
        await websocket.close(code=1011)  # 1011：服务器内部错误

# ========== 支持直接 python 信息中转服务器.py 启动 ===========
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        "信息中转服务器:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
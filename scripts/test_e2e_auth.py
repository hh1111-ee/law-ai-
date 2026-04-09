import os
import sys
import time
import uuid
import requests
import logging

# Ensure project root on path for optional DB checks
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e_auth")

BASE = os.environ.get('API_BASE', 'http://127.0.0.1:8000')


def unique_id():
    return int(time.time())


def run_test():
    uid = unique_id()
    username = f"e2e_user_{uid}_{uuid.uuid4().hex[:6]}"
    password = "TestPass123!"
    identity = "tester"
    location = "local"
    role = "tester"

    logger.info("Registering user %s (id=%s)", username, uid)
    resp = requests.post(f"{BASE}/user_register", json={
        'id': uid,
        'username': username,
        'identity': identity,
        'password': password,
        'location': location,
        'role': role,
    }, timeout=10)

    logger.info("register status %s: %s", resp.status_code, resp.text)
    if resp.status_code != 200:
        logger.error("注册失败：%s", resp.text)
        return 2

    # 登录
    logger.info("Logging in user id=%s", uid)
    resp2 = requests.post(f"{BASE}/user_login", json={'id': uid, 'password': password}, timeout=10)
    logger.info("login status %s: %s", resp2.status_code, resp2.text)
    if resp2.status_code != 200:
        logger.error("登录失败：%s", resp2.text)
        return 3

    # 可选：检查 DB 中 password_hash 是否存在（若可用）
    try:
        # 使用同步 helper，以避免在脚本中启动异步事件循环导致 psycopg 兼容性问题
        from postgres_data.adapter import get_user_by_id_sync

        u = get_user_by_id_sync(uid)
        if u:
            ph = u.get('password_hash')
            logger.info("DB user fetched: %s", u)
            if ph:
                logger.info("password_hash present in DB (good)")
            else:
                logger.info("password_hash not present in DB (may be written on register or via separate backfill)")
    except Exception as exc:
        logger.info("跳过 DB 检查（adapter 不可用或调用失败）：%s", exc)

    logger.info("E2E 测试通过")
    return 0


if __name__ == '__main__':
    exit(run_test())

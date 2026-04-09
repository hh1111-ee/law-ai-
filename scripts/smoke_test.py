import requests
import time
import sys

BASE = "http://127.0.0.1:8000"

def wait_ready(timeout=20):
    for i in range(timeout*2):
        try:
            r = requests.get(BASE + "/")
            print('root:', r.status_code, r.text)
            return True
        except Exception as e:
            time.sleep(0.5)
    print('server not ready', file=sys.stderr)
    return False

if not wait_ready():
    sys.exit(2)

# 1) user_register
print('\n== user_register ==')
reg_payload = {"id": 999901, "username": "smoke_user", "identity": "tester", "password": "pwd123", "location": "测试"}
r = requests.post(BASE + "/user_register", json=reg_payload, timeout=10)
print('status', r.status_code)
try:
    print(r.json())
except Exception:
    print(r.text)

# 2) user_login
print('\n== user_login ==')
login_payload = {"id": 999901, "password": "pwd123"}
r = requests.post(BASE + "/user_login", json=login_payload, timeout=10)
print('status', r.status_code)
try:
    print(r.json())
except Exception:
    print(r.text)

# 3) create_post
print('\n== create_post ==')
post_payload = {"author": "smoke_user", "title": "smoke title", "content": "smoke content", "section": "test"}
r = requests.post(BASE + "/create_post", json=post_payload, timeout=10)
print('status', r.status_code)
post_resp = None
try:
    post_resp = r.json()
    print(post_resp)
except Exception:
    print(r.text)

post_id = None
if post_resp and isinstance(post_resp, dict):
    post_id = post_resp.get('data', {}).get('post', {}).get('id')

# 4) add_comment
print('\n== add_comment ==')
if not post_id:
    print('no post_id, trying id 1')
    post_id = 1
comment_payload = {"post_id": post_id, "author": "smoke_user", "content": "nice post"}
r = requests.post(BASE + "/add_comment", json=comment_payload, timeout=10)
print('status', r.status_code)
try:
    print(r.json())
except Exception:
    print(r.text)

print('\nSmoke tests finished')

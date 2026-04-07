import os
import time
import requests

base = 'http://127.0.0.1:8000'

# 等待服务启动
print('等待服务就绪...')
for i in range(10):
    try:
        r = requests.get(base + '/get_posts')
        print('服务响应状态：', r.status_code)
        break
    except Exception as e:
        print('等待中...', i)
        time.sleep(1)

# 创建帖子
payload = {
    'author': '1',
    'title': 'smoke test 标题',
    'content': '这是一个自动化烟雾测试内容',
    'section': 'test'
}
print('创建帖子请求：', payload)
try:
    r = requests.post(base + '/create_post', json=payload, timeout=10)
    print('create_post', r.status_code, r.text)
    post = r.json().get('data', {}).get('post')
    post_id = post.get('id') if post else None
except Exception as e:
    print('create_post 请求失败：', e)
    post_id = None

# 添加评论
if post_id:
    payload = {'post_id': post_id, 'author': '2', 'content': '自动化测试评论'}
    try:
        r = requests.post(base + '/add_comment', json=payload, timeout=10)
        print('add_comment', r.status_code, r.text)
    except Exception as e:
        print('add_comment 请求失败：', e)
else:
    print('跳过添加评论，因为创建帖子失败')

print('测试完成')

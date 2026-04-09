import requests
import threading
import time
import random

BASE = 'http://127.0.0.1:8000'

NUM_THREADS = 10

results = []


def worker(i):
    try:
        author = str(random.randint(1, 5))
        payload = {
            'author': author,
            'title': f'smoke concurrent {i}',
            'content': '并发测试内容',
            'section': 'concurrent',
        }
        r = requests.post(BASE + '/create_post', json=payload, timeout=10)
        print(f'create_post {i}', r.status_code, r.text)
        post = r.json().get('data', {}).get('post') if r.status_code == 200 else None
        if post:
            post_id = post.get('id')
            payload2 = {'post_id': post_id, 'author': author, 'content': '并发评论'}
            r2 = requests.post(BASE + '/add_comment', json=payload2, timeout=10)
            print(f'add_comment {i}', r2.status_code, r2.text)
            results.append((i, r.status_code, r2.status_code))
        else:
            results.append((i, r.status_code, None))
    except Exception as e:
        print('worker exception', i, e)
        results.append((i, 'err', None))


if __name__ == '__main__':
    threads = []
    for i in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(i,))
        t.start()
        threads.append(t)
        time.sleep(0.1)

    for t in threads:
        t.join()

    print('Results:', results)

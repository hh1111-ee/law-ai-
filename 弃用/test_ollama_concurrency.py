#!/usr/bin/env python3
"""
并发测试脚本（线程池 + requests），用法:
  python scripts/test_ollama_concurrency.py [concurrency] [total_requests]
示例：并发 3，总共 6 个请求 -> python scripts/test_ollama_concurrency.py 3 6
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print('请先安装 requests: pip install requests')
    raise

concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 2
total = int(sys.argv[2]) if len(sys.argv) > 2 else concurrency
url = '  http://localhost:8000/api/legal'
payload = {'question': '并发测试：请返回一句短答。'}

def worker(i):
    t0 = time.time()
    try:
        r = requests.post(url, json=payload, timeout=60)
        elapsed = time.time() - t0
        return {'idx': i, 'status': r.status_code, 'time': elapsed, 'body': (r.text or '')[:300]}
    except Exception as e:
        return {'idx': i, 'status': 'ERR', 'time': time.time() - t0, 'body': str(e)}

def main():
    print(f'Starting test: concurrency={concurrency}, total={total}, url={url}')
    t_start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(worker, i) for i in range(total)]
        for f in as_completed(futures):
            res = f.result()
            results.append(res)
            print(f"#{res['idx']} status={res['status']} time={res['time']:.3f}s")

    elapsed = time.time() - t_start
    succ = [r for r in results if r['status'] == 200]
    errs = [r for r in results if r['status'] != 200]
    times = [r['time'] for r in results]
    print('\nSummary:')
    print(f'  Total requests: {total}')
    print(f'  Concurrency used: {concurrency}')
    print(f'  Elapsed wall time: {elapsed:.3f}s')
    if times:
        print(f'  Avg latency: {sum(times)/len(times):.3f}s  Min: {min(times):.3f}s  Max: {max(times):.3f}s')
    print(f'  Success(200): {len(succ)}  Errors/other: {len(errs)}')
    if errs:
        print('\nErrors details:')
        for e in errs:
            print(f"  #{e['idx']} status={e['status']} time={e['time']:.3f}s body={e['body']}")

if __name__ == '__main__':
    main()

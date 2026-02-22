import os, sys, json
# 确保可以导入后端模块
sys.path.append(os.path.abspath('聊天和用户后端'))
from post import PostManage

p = os.path.abspath(os.path.join('数据库', 'posts.pkl'))
pm = PostManage()
try:
    pm.load_posts(p)
except Exception as e:
    # 兼容旧命名
    try:
        pm.load_posts(p)
    except Exception as e2:
        print(json.dumps({'error': f'load failed: {e} ; {e2}'} , ensure_ascii=False))
        sys.exit(1)

out = []
for post in pm.post_list:
    out.append({
        'id': getattr(post, 'id', None),
        'section': getattr(post, 'section', None),
        'title': getattr(post, 'title', None),
        'time': getattr(post, 'time', None),
        'comments': len(getattr(post, 'comments', [])),
    })
print(json.dumps(out, ensure_ascii=False, indent=2))

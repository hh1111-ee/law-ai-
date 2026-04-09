import os
import sys
import random
import time
from datetime import datetime

def _import_combined_server():
    try:
        import Combined_server as cs
        return cs
    except Exception:
        this_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(this_dir, '..')),
            os.path.abspath(os.path.join(this_dir, '..', '聊天和用户后端')),
        ]
        for p in candidates:
            if p not in sys.path:
                sys.path.insert(0, p)
        try:
            import Combined_server as cs
            return cs
        except Exception as e:
            print("无法导入 Combined_server，请确保在项目根目录运行脚本或将模块路径加入 PYTHONPATH。错误：", e)
            print("已尝试的路径：", candidates)
            sys.exit(1)

cs = _import_combined_server()
xing=["李","王","张","刘","陈","杨","赵","黄","周","吴"]
ming=["伟","芳","娜","敏","静","丽","强","磊","军","洋"]
zhi=["义","勇","军","磊","涛","超","强","鹏","华","飞"]
address=["北京","上海","广州","深圳","杭州","南京","成都","武汉","重庆"]
zheye=["业主","物业","律师"]

def load_users():
    for i in range(1, 1000):
        id = i
        name = random.choice(xing) + random.choice(ming) + random.choice(zhi)
        location  = random.choice(address)
        identity = random.choice(zheye)
        try:
            user_obj = cs.UserClass(id, name, identity, "123", location)
            cs.user_manager.add_user(user_obj)
        except Exception as e:
            print("添加用户失败：", name, e)
    # 保存到 Combined_server 定义的用户文件
    try:
        cs.user_manager.save_users(cs.USER_FILE)
    except Exception as e:
        print("保存用户失败：", e)

if __name__ == "__main__":
    load_users()
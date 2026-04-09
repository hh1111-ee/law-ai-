#!/usr/bin/env python3
"""
生成并插入伪装数据到现有后端数据文件（用户/帖子/私信）。

用法:
    python scripts/seed_fake_data.py

说明:
 - 脚本会把 `聊天和用户后端` 目录加入 `sys.path`，导入 `Combined_server` 模块，使用其中的 manager 实例添加数据。
 - 运行后会调用后端的保存函数把数据写入磁盘（与服务器保存逻辑一致）。
 - 不依赖第三方库，使用随机生成的简单文本。
"""
import os
import sys
import random
import time
from datetime import datetime

# 尝试使用 Faker 生成更真实的数据
USE_FAKER = False
try:
    from faker import Faker
    fake = Faker('zh_CN')
    USE_FAKER = True
except Exception:
    fake = None


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT, "聊天和用户后端")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import Combined_server as cs
except Exception as e:
    print("无法导入 Combined_server，请确保在项目根目录运行脚本，错误：", e)
    sys.exit(1)


PROVINCES = [
    "北京",
    "上海",
    "广东",
    "浙江",
    "江苏",
    "山东",
    "河南",
    "四川",
    "湖北",
    "湖南",
]

IDENTITIES = ["owner", "property", "lawyer"]
SECTIONS = ["contract", "owners", "security", "public_use"]


def seed_users(n=10):
    created = []
    for i in range(1, n + 1):
        if USE_FAKER:
            name = fake.name()
            username = f"{''.join(name.split())}_{i:03d}"
            province = getattr(fake, 'province', lambda: random.choice(PROVINCES))()
            city = getattr(fake, 'city', lambda: province)()
            identity = random.choice(IDENTITIES)
            location = {"province": province, "city": city}
            password = "password123"
        else:
            username = f"faker_user_{i:03d}"
            if cs.user_manager.find_user(username):
                continue
            identity = random.choice(IDENTITIES)
            province = random.choice(PROVINCES)
            location = {"province": province, "city": province}
            password = "password123"

        try:
            user_obj = cs.UserClass(username, identity, password, location, identity)
            cs.user_manager.add_user(user_obj)
            created.append(username)
        except Exception as exc:
            print("添加用户失败：", username, exc)
    return created


def seed_posts(num_posts=30):
    created = []
    user_names = [u.username for u in getattr(cs.user_manager, 'user_list', [])]
    if not user_names:
        return created
    for i in range(num_posts):
        author = random.choice(user_names)
        if USE_FAKER:
            title = fake.sentence(nb_words=6)
            content = fake.paragraph(nb_sentences=4)
            # 随机时间：过去 180 天内
            created_time = fake.date_time_between(start_date='-180d', end_date='now')
        else:
            title = f"示例帖：关于第{i+1}项问题的讨论"
            content = (
                "这是自动生成的测试帖子，用于填充演示数据。"
                f" 创建时间：{datetime.now().isoformat()}。示例编号 {i+1}。"
            )
        section = random.choice(SECTIONS)
        try:
            post = cs.post_manager.add_post(author, title, content, section)
            # 如果 post 对象有时间字段，尝试赋值（兼容性：尽量不改后端结构）
            try:
                if hasattr(post, 'time') and USE_FAKER:
                    post.time = created_time.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
            created.append(getattr(post, 'id', f"{author}-{i}"))
        except Exception as exc:
            print("创建帖子失败：", exc)
    return created


def seed_personal_messages(num_msgs=50):
    created = 0
    users = getattr(cs.user_manager, 'user_list', [])
    if len(users) < 2:
        return created
    for i in range(num_msgs):
        s = random.choice(users)
        r = random.choice(users)
        if getattr(s, 'username', None) == getattr(r, 'username', None):
            continue
        if USE_FAKER:
            content = fake.sentence(nb_words=12)
            ts = fake.date_time_between(start_date='-90d', end_date='now').strftime('%Y-%m-%d %H:%M:%S')
        else:
            content = f"自动测试消息 #{i+1} — 这是一条伪造的私信。"
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            msg = cs.personalChatMessage(getattr(s, 'username', str(s)), getattr(r, 'username', str(r)), content, ts)
            cs.msg_manager.add_personal_message(msg)
            created += 1
        except Exception as exc:
            print("保存私信失败：", exc)
    return created


def main():
    print("开始插入固定伪装数据（3 用户、20 帖子、30 评论、50 私聊）...")

    # 先确保三位固定用户存在
    fixed_users = [
        {"username": "zhangsan", "identity": "owner", "password": "pass123", "location": {"province": "北京", "city": "北京"}},
        {"username": "lisi", "identity": "lawyer", "password": "pass123", "location": {"province": "上海", "city": "上海"}},
        {"username": "wangwu", "identity": "property", "password": "pass123", "location": {"province": "广东", "city": "广州"}},
    ]

    created_users = []
    for u in fixed_users:
        if cs.user_manager.find_user(u["username"]):
            created_users.append(u["username"])
            continue
        try:
            user_obj = cs.UserClass(u["username"], u["identity"], u["password"], u["location"], u["identity"])
            cs.user_manager.add_user(user_obj)
            created_users.append(u["username"])
        except Exception as exc:
            print("添加固定用户失败：", u["username"], exc)

    print(f"确保用户：{created_users}")

    # 清单化的 20 条帖子（作者轮换）
    topics = [
        "物业收费争议的法律依据与处理步骤",
        "合同违约的证据准备与索赔路径",
        "业主大会决议的效力问题",
        "租赁合同押金退还的法律处理",
        "劳动合同解除的合规流程",
        "网络侵权与个人信息保护的索赔要点",
        "房屋买卖合同纠纷的诉讼时效分析",
        "民间借贷合同的证据保存与起诉要点",
        "行政复议与行政诉讼的区别和适用",
        "婚姻财产分割中的财产评估方法",
        "交通事故责任认定与赔偿计算方法",
        "产品质量纠纷中的证明责任分配",
        "合同中约定违约金条款的合理性判断",
        "工伤认定的主要证据与申报流程",
        "公司股权转让的合同注意事项",
        "知识产权侵权的初步维权步骤",
        "建设工程质量纠纷的举证策略",
        "消费者权益保护投诉与司法途径",
        "环境污染损害赔偿的索赔流程",
        "债权转让中的通知与抗辩问题",
    ]

    post_ids = []
    authors = created_users
    for idx, topic in enumerate(topics[:20]):
        author = authors[idx % len(authors)]
        title = topic
        content = (
            f"{topic}。以下为相关要点：\n"
            "1. 确认争议事实并收集证据；\n"
            "2. 评估法律适用并估算主张的权利范围；\n"
            "3. 先行协商或通过仲裁/诉讼程序解决。"
        )
        section = SECTIONS[idx % len(SECTIONS)]
        try:
            post = cs.post_manager.add_post(author, title, content, section)
            post_ids.append(post.id)
        except Exception as exc:
            print("创建固定帖子失败：", exc)

    print(f"创建帖子：{len(post_ids)} 条，示例 id: {post_ids[:3]}")

    # 添加 30 条评论，分布在前若干帖子
    comment_texts = [
        "请问该问题是否需要律师函作为第一步？",
        "在实践中通常建议先保全证据后再提起诉讼。",
        "如果协商无果，诉讼是可行的法律途径。",
        "是否有合同文本或收据可以作为证据？",
        "可以参考相关司法解释来确定责任分配。",
        "建议就地咨询专业律师以获取具体操作流程。",
    ]

    c = 0
    for i in range(30):
        post_id = post_ids[i % len(post_ids)]
        author = authors[(i + 1) % len(authors)]
        content = comment_texts[i % len(comment_texts)]
        try:
            comment = cs.post_manager.add_comment(post_id, author, content)
            if comment:
                c += 1
        except Exception as exc:
            print("添加评论失败：", exc)

    print(f"添加评论：{c} 条")

    # 插入 50 条私聊（在三位用户间循环发送）
    pm_count = 0
    pm_texts = [
        "关于刚才讨论的问题，我想请教下具体证据如何保存。",
        "我这边准备了一份合同样本，是否可以作为证据？",
        "你认为先协商还是直接起诉更合适？",
        "若对方不回复，下一步该如何处理？",
        "能否推荐一位擅长此类案件的律师？",
    ]

    pairs = [("zhangsan", "lisi"), ("lisi", "wangwu"), ("wangwu", "zhangsan")]
    for i in range(50):
        s, r = pairs[i % len(pairs)]
        content = pm_texts[i % len(pm_texts)]
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            msg = cs.personalChatMessage(s, r, content, ts)
            cs.msg_manager.add_personal_message(msg)
            pm_count += 1
        except Exception as exc:
            print("插入私信失败：", exc)

    print(f"插入私信：{pm_count} 条")

    # 保存数据（使用后端现有的保存逻辑）
    try:
        cs.save_all_data_on_exit()
        print("数据已保存到磁盘（数据库文件）。")
    except Exception as exc:
        print("保存数据时发生错误：", exc)

    print("完成。可启动服务查看效果。")


if __name__ == '__main__':
    main()

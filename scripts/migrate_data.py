#!/usr/bin/env python
"""
导入 Excel 数据到 PostgreSQL 数据库
使用方法：作为 pre-deploy 命令运行，或在 Railway Shell 中执行
  python scripts/migrate_data.py
依赖：pandas, openpyxl, sqlalchemy, psycopg
退出码：0 = 成功，1 = 失败
"""

import os
import sys

# ---------------------------------------------------------------------------
# 确保项目根目录在 sys.path 中（不依赖 postgres_data 包，避免导入副作用）
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_SCRIPT_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

# ---------------------------------------------------------------------------
# 第三方依赖（requirements.txt 中已声明）
# ---------------------------------------------------------------------------
try:
    import pandas as pd
    from sqlalchemy import create_engine, text
except ImportError as _e:
    print(f"[migrate_data] 致命错误：缺少必要依赖 — {_e}")
    print("[migrate_data] 请确认 requirements.txt 中包含 pandas、openpyxl、sqlalchemy、psycopg")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 辅助：将 asyncpg/psycopg URL 规范化为同步 psycopg URL
# ---------------------------------------------------------------------------
def _to_sync_url(url: str) -> str:
    """将数据库 URL 转换为同步 psycopg 驱动格式。

    主应用使用 asyncpg，迁移脚本使用同步引擎，两者连接池完全独立，互不干扰。
    """
    if not url:
        return url
    # postgresql+asyncpg:// -> postgresql+psycopg://
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    # postgresql+psycopg2:// -> postgresql+psycopg://
    url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
    # 裸 postgresql:// -> postgresql+psycopg://
    if url.startswith("postgresql://") and "+" not in url.split("://")[0]:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    # postgres:// (Heroku/Railway 短格式) -> postgresql+psycopg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


# ---------------------------------------------------------------------------
# 直接用 SQL 建表，不依赖 ORM 模型导入
# ---------------------------------------------------------------------------
CREATE_EXAMPLE_LEGAL_SQL = """
CREATE TABLE IF NOT EXISTS example_legal (
    id         SERIAL PRIMARY KEY,
    region     VARCHAR(128),
    url        VARCHAR(1024),
    title      VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_EXAMPLE_RELATION_SQL = """
CREATE TABLE IF NOT EXISTS example_relation (
    id          SERIAL PRIMARY KEY,
    case_number VARCHAR(256) NOT NULL UNIQUE,
    url         VARCHAR(1024),
    summary     TEXT,
    keyword1    VARCHAR(128),
    keyword2    VARCHAR(128),
    keyword3    VARCHAR(128),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def create_tables(conn) -> None:
    """用原生 SQL 创建表（如果不存在），不依赖 ORM Base.metadata。"""
    print("[migrate_data] 检查并创建表...")
    conn.execute(text(CREATE_EXAMPLE_LEGAL_SQL))
    conn.execute(text(CREATE_EXAMPLE_RELATION_SQL))
    conn.commit()
    print("[migrate_data] 表检查/创建完成")


# ---------------------------------------------------------------------------
# 数据导入函数
# ---------------------------------------------------------------------------

def import_example_relation(conn, file_path: str) -> int:
    """将 案号.xlsx 导入 example_relation 表，跳过已存在的记录。"""
    if not os.path.exists(file_path):
        print(f"[migrate_data] 警告：案号文件不存在，跳过 — {file_path}")
        return 0

    print(f"[migrate_data] 读取案号文件：{file_path}")
    try:
        df = pd.read_excel(file_path, sheet_name=0)
    except Exception as exc:
        print(f"[migrate_data] 警告：读取案号 Excel 失败，跳过 — {exc}")
        return 0

    print(f"[migrate_data] 读取到 {len(df)} 行原始数据（案号）")

    # 列名映射
    df = df.rename(columns={
        '案号':   'case_number',
        '链接':   'url',
        '摘要':   'summary',
        '关键词1': 'keyword1',
        '关键词2': 'keyword2',
        '关键词3': 'keyword3',
    })

    required_cols = ['case_number', 'url', 'summary', 'keyword1', 'keyword2', 'keyword3']
    df = df[[c for c in required_cols if c in df.columns]]
    df = df.where(pd.notnull(df), None)
    df = df.drop_duplicates(subset=['case_number'])

    # 过滤掉 case_number 为空的行
    df = df[df['case_number'].notna()]
    print(f"[migrate_data] 去重/过滤后待导入 {len(df)} 条记录（案号）")

    inserted = 0
    skipped = 0
    for _, row in df.iterrows():
        case_num = row['case_number']
        existing = conn.execute(
            text("SELECT 1 FROM example_relation WHERE case_number = :cn"),
            {"cn": case_num},
        ).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute(
            text("""
                INSERT INTO example_relation
                    (case_number, url, summary, keyword1, keyword2, keyword3)
                VALUES
                    (:cn, :url, :summary, :k1, :k2, :k3)
            """),
            {
                "cn":      case_num,
                "url":     row.get('url'),
                "summary": row.get('summary'),
                "k1":      row.get('keyword1'),
                "k2":      row.get('keyword2'),
                "k3":      row.get('keyword3'),
            },
        )
        inserted += 1

    conn.commit()
    print(f"[migrate_data] 案号表导入完成：新增 {inserted} 条，跳过 {skipped} 条已存在")
    return inserted


def import_example_legal(conn, file_path: str) -> int:
    """将 地区.xlsx 导入 example_legal 表，跳过已存在的记录。"""
    if not os.path.exists(file_path):
        print(f"[migrate_data] 警告：地区文件不存在，跳过 — {file_path}")
        return 0

    print(f"[migrate_data] 读取地区文件：{file_path}")
    try:
        df = pd.read_excel(file_path, sheet_name=0)
    except Exception as exc:
        print(f"[migrate_data] 警告：读取地区 Excel 失败，跳过 — {exc}")
        return 0

    print(f"[migrate_data] 读取到 {len(df)} 行原始数据（法规）")

    df = df.rename(columns={
        '地区':   'region',
        '网页链接': 'url',
        '法规名称': 'title',
    })

    required_cols = ['region', 'url', 'title']
    df = df[[c for c in required_cols if c in df.columns]]

    # 过滤掉 title 为空的行
    df = df[df['title'].notna()]
    df['region'] = df['region'].where(pd.notnull(df['region']), None)
    df = df.drop_duplicates(subset=['title', 'region'])

    print(f"[migrate_data] 去重/过滤后待导入 {len(df)} 条记录（法规）")

    inserted = 0
    skipped = 0
    for _, row in df.iterrows():
        title  = row['title']
        region = row.get('region')
        existing = conn.execute(
            text("""
                SELECT 1 FROM example_legal
                WHERE title = :title
                  AND (region = :region OR (region IS NULL AND :region IS NULL))
            """),
            {"title": title, "region": region},
        ).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute(
            text("""
                INSERT INTO example_legal (region, url, title)
                VALUES (:region, :url, :title)
            """),
            {"region": region, "url": row.get('url'), "title": title},
        )
        inserted += 1

    conn.commit()
    print(f"[migrate_data] 法规表导入完成：新增 {inserted} 条，跳过 {skipped} 条已存在")
    return inserted


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main() -> int:
    """执行完整迁移流程，返回退出码（0 = 成功，1 = 失败）。"""
    print("[migrate_data] ===== 数据迁移脚本启动 =====")

    # 1. 获取并规范化数据库 URL
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        print("[migrate_data] 致命错误：未设置 DATABASE_URL 环境变量")
        return 1

    sync_url = _to_sync_url(raw_url)
    masked = sync_url.split("@")[-1] if "@" in sync_url else "<url>"
    print(f"[migrate_data] 使用数据库：...@{masked}")

    # 2. 确定 Excel 文件路径
    data_dir   = os.path.join(_ROOT_DIR, "数据")
    case_file  = os.path.join(data_dir, "案号.xlsx")
    legal_file = os.path.join(data_dir, "地区.xlsx")
    print(f"[migrate_data] 数据目录：{data_dir}")
    print(f"[migrate_data]   案号文件存在：{os.path.exists(case_file)}")
    print(f"[migrate_data]   地区文件存在：{os.path.exists(legal_file)}")

    # 3. 建立同步数据库连接
    try:
        engine = create_engine(
            sync_url,
            echo=False,
            pool_pre_ping=True,   # 连接前探活，避免使用失效连接
            pool_size=1,          # 迁移脚本只需单连接
            max_overflow=0,
        )
        print("[migrate_data] 数据库引擎创建成功，尝试连接...")
    except Exception as exc:
        print(f"[migrate_data] 致命错误：创建数据库引擎失败 — {exc}")
        return 1

    try:
        with engine.connect() as conn:
            print("[migrate_data] 数据库连接成功")

            # 4. 建表
            create_tables(conn)

            # 5. 导入数据
            import_example_relation(conn, case_file)
            import_example_legal(conn, legal_file)

    except Exception as exc:
        print(f"[migrate_data] 致命错误：数据库操作失败 — {exc}")
        return 1
    finally:
        # 显式释放连接池，避免与主应用连接池产生干扰
        try:
            engine.dispose()
            print("[migrate_data] 数据库连接池已释放")
        except Exception as exc:
            print(f"[migrate_data] 警告：释放连接池时出错 — {exc}")

    print("[migrate_data] ===== 数据迁移完成 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())

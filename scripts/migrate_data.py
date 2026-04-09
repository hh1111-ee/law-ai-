#!/usr/bin/env python
"""
导入 Excel 数据到 PostgreSQL 数据库
使用方法：在 Railway Shell 中运行 `python scripts/import_excel_data.py`
依赖：pandas, openpyxl, sqlalchemy, psycopg2-binary
"""

import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

# 添加项目根目录到 Python 路径（如果需要导入 models）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入模型，如果失败则直接创建表（简单方式）
try:
    from postgres_data import models
    from postgres_data.db_session import Base
    HAS_MODELS = True
except ImportError:
    HAS_MODELS = False
    # 如果没有模型，我们手动定义表结构（用于建表）
    from sqlalchemy import Column, Integer, String, Text, DateTime
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

    class ExampleLegal(Base):
        __tablename__ = 'example_legal'
        id = Column(Integer, primary_key=True, index=True)
        region = Column(String(128), nullable=True)
        url = Column(String(1024), nullable=True)
        title = Column(String(512), nullable=True)
        created_at = Column(DateTime, server_default=text('now()'))

    class ExampleRelation(Base):
        __tablename__ = 'example_relation'
        id = Column(Integer, primary_key=True, index=True)
        case_number = Column(String(256), unique=True, index=True, nullable=False)
        url = Column(String(1024), nullable=True)
        summary = Column(Text, nullable=True)
        keyword1 = Column(String(128), nullable=True)
        keyword2 = Column(String(128), nullable=True)
        keyword3 = Column(String(128), nullable=True)
        created_at = Column(DateTime, server_default=text('now()'))

# 从环境变量获取数据库连接 URL
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("错误：未设置 DATABASE_URL 环境变量")
    sys.exit(1)

# 创建同步引擎（用于导入，不影响主应用的异步引擎）
engine = create_engine(DATABASE_URL, echo=False)

def create_tables():
    """创建表（如果不存在）"""
    print("检查并创建表...")
    Base.metadata.create_all(bind=engine)
    print("表创建/检查完成")

def import_example_relation(file_path: str):
    """导入案号.xlsx 到 example_relation 表"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return 0

    df = pd.read_excel(file_path, sheet_name=0)  # 读取第一个 sheet
    print(f"读取到 {len(df)} 行原始数据（案号）")

    # 列名映射（根据实际 Excel 列名调整）
    df = df.rename(columns={
        '案号': 'case_number',
        '链接': 'url',
        '摘要': 'summary',
        '关键词1': 'keyword1',
        '关键词2': 'keyword2',
        '关键词3': 'keyword3'
    })

    # 只保留需要的列
    required_cols = ['case_number', 'url', 'summary', 'keyword1', 'keyword2', 'keyword3']
    df = df[[c for c in required_cols if c in df.columns]]

    # 处理空值
    df = df.where(pd.notnull(df), None)

    # 去重（按案号）
    df = df.drop_duplicates(subset=['case_number'])

    print(f"去重后待导入 {len(df)} 条记录（案号）")

    # 逐条插入，跳过已存在的
    inserted = 0
    skipped = 0
    with engine.connect() as conn:
        for _, row in df.iterrows():
            case_num = row['case_number']
            if case_num is None:
                continue
            # 检查是否已存在
            existing = conn.execute(
                text("SELECT 1 FROM example_relation WHERE case_number = :cn"),
                {"cn": case_num}
            ).fetchone()
            if existing:
                skipped += 1
                continue
            # 插入新记录
            conn.execute(
                text("""
                    INSERT INTO example_relation
                    (case_number, url, summary, keyword1, keyword2, keyword3)
                    VALUES (:cn, :url, :summary, :k1, :k2, :k3)
                """),
                {
                    "cn": case_num,
                    "url": row['url'],
                    "summary": row['summary'],
                    "k1": row['keyword1'],
                    "k2": row['keyword2'],
                    "k3": row['keyword3']
                }
            )
            inserted += 1
        conn.commit()
    print(f"案号表导入完成：新增 {inserted} 条，跳过 {skipped} 条已存在")
    return inserted

def import_example_legal(file_path: str):
    """导入地区.xlsx 到 example_legal 表"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return 0

    # 读取第一个 sheet（通常是“备份”）
    df = pd.read_excel(file_path, sheet_name=0)
    print(f"读取到 {len(df)} 行原始数据（法规）")

    # 列名映射
    df = df.rename(columns={
        '地区': 'region',
        '网页链接': 'url',
        '法规名称': 'title'
    })

    # 保留有效列
    required_cols = ['region', 'url', 'title']
    df = df[[c for c in required_cols if c in df.columns]]

    # 过滤掉法规名称为空的记录
    df = df[df['title'].notna()]
    # 地区为空时设为 None
    df['region'] = df['region'].where(pd.notnull(df['region']), None)

    # 去重（按标题和地区）
    df = df.drop_duplicates(subset=['title', 'region'])

    print(f"去重后待导入 {len(df)} 条记录（法规）")

    inserted = 0
    skipped = 0
    with engine.connect() as conn:
        for _, row in df.iterrows():
            title = row['title']
            region = row['region']
            # 检查是否已存在
            existing = conn.execute(
                text("SELECT 1 FROM example_legal WHERE title = :title AND (region = :region OR (region IS NULL AND :region IS NULL))"),
                {"title": title, "region": region}
            ).fetchone()
            if existing:
                skipped += 1
                continue
            conn.execute(
                text("""
                    INSERT INTO example_legal (region, url, title)
                    VALUES (:region, :url, :title)
                """),
                {
                    "region": region,
                    "url": row['url'],
                    "title": title
                }
            )
            inserted += 1
        conn.commit()
    print(f"法规表导入完成：新增 {inserted} 条，跳过 {skipped} 条已存在")
    return inserted

if __name__ == "__main__":
    # 确定文件路径（假设 Excel 文件放在项目根目录下的“数据”文件夹中）
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    case_file = os.path.join(BASE_DIR, "数据", "案号.xlsx")
    legal_file = os.path.join(BASE_DIR, "数据", "地区.xlsx")

    print("开始导入数据...")
    create_tables()
    import_example_relation(case_file)
    import_example_legal(legal_file)
    print("所有数据导入完成")
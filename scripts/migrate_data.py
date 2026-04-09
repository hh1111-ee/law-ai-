#!/usr/bin/env python
"""
异步导入 Excel 数据到 PostgreSQL（使用 asyncpg，无需 psycopg2）
在 Railway Shell 中运行：python scripts/import_excel_data_async.py
"""

import os
import sys
import asyncio
import pandas as pd
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从环境变量获取数据库 URL
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("错误：未设置 DATABASE_URL 环境变量")
    sys.exit(1)

# 创建异步引擎（使用 asyncpg）
engine = create_async_engine(DATABASE_URL, echo=False)

async def create_tables():
    """创建表（如果不存在）"""
    from postgres_data import models
    from postgres_data.db_session import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("表创建/检查完成")

async def import_example_relation(file_path: str):
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return 0
    df = pd.read_excel(file_path, sheet_name=0)
    df = df.rename(columns={
        '案号': 'case_number',
        '链接': 'url',
        '摘要': 'summary',
        '关键词1': 'keyword1',
        '关键词2': 'keyword2',
        '关键词3': 'keyword3'
    })
    df = df[['case_number', 'url', 'summary', 'keyword1', 'keyword2', 'keyword3']]
    df = df.where(pd.notnull(df), None)
    df = df.drop_duplicates(subset=['case_number'])
    print(f"待导入 {len(df)} 条案号记录")

    inserted = 0
    skipped = 0
    async with engine.begin() as conn:
        for _, row in df.iterrows():
            case_num = row['case_number']
            if not case_num:
                continue
            # 检查是否存在
            result = await conn.execute(
                text("SELECT 1 FROM example_relation WHERE case_number = :cn"),
                {"cn": case_num}
            )
            if result.fetchone():
                skipped += 1
                continue
            await conn.execute(
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
    print(f"案号表：新增 {inserted}，跳过 {skipped}")
    return inserted

async def import_example_legal(file_path: str):
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return 0
    df = pd.read_excel(file_path, sheet_name=0)
    df = df.rename(columns={
        '地区': 'region',
        '网页链接': 'url',
        '法规名称': 'title'
    })
    df = df[['region', 'url', 'title']]
    df = df[df['title'].notna()]
    df['region'] = df['region'].where(pd.notnull(df['region']), None)
    df = df.drop_duplicates(subset=['title', 'region'])
    print(f"待导入 {len(df)} 条法规记录")

    inserted = 0
    skipped = 0
    async with engine.begin() as conn:
        for _, row in df.iterrows():
            title = row['title']
            region = row['region']
            # 检查是否存在
            result = await conn.execute(
                text("SELECT 1 FROM example_legal WHERE title = :title AND (region = :region OR (region IS NULL AND :region IS NULL))"),
                {"title": title, "region": region}
            )
            if result.fetchone():
                skipped += 1
                continue
            await conn.execute(
                text("INSERT INTO example_legal (region, url, title) VALUES (:region, :url, :title)"),
                {"region": region, "url": row['url'], "title": title}
            )
            inserted += 1
    print(f"法规表：新增 {inserted}，跳过 {skipped}")
    return inserted

async def main():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    case_file = os.path.join(BASE_DIR, "数据", "案号.xlsx")
    legal_file = os.path.join(BASE_DIR, "数据", "地区.xlsx")

    print("开始异步导入...")
    await create_tables()
    await import_example_relation(case_file)
    await import_example_legal(legal_file)
    print("所有数据导入完成")

if __name__ == "__main__":
    asyncio.run(main())
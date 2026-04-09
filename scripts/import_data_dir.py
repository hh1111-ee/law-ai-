#!/usr/bin/env python3
"""
导入脚本：把 `数据` 目录下的 Excel/CSV 文件导入到 `example_relation` 和 `example_legal` 表。

依赖说明：
- 推荐安装数据库驱动和 Excel 解析库：
    `pip install "psycopg[binary]" openpyxl`

Windows 说明：
- 在 Windows 上运行异步 psycopg 时，默认的 ProactorEventLoop 可能会与 psycopg 的异步 I/O 产生兼容性问题。
  若出现 InterfaceError，可在外部设置 selector 事件循环策略：
    ```python
    import asyncio
    asyncio.set_event_loop_policy(asyncio.SelectorEventLoopPolicy())
    ```

用法：
    python scripts/import_data_dir.py --data-dir 数据 --commit
默认 dry-run（只打印将要插入的行数与示例）。
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List

import pandas as pd

 


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Ensure project root is on sys.path so this script (run from scripts/) can import
# the local `postgres_data` package. This handles running `python scripts/import_data_dir.py`
# without requiring PYTHONPATH or editable installs.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Runtime checks: ensure psycopg is available and adjust Windows event loop policy
try:
    import psycopg as _psycopg  # psycopg3 (installed via psycopg[binary])
except Exception:
    logging.error('缺少依赖 psycopg（安装：pip install "psycopg[binary]"），脚本退出')
    raise

# NOTE: Windows event-loop switching was previously used to work around
# compatibility issues with async drivers. This logic is deprecated —
# environment-specific event loop configuration should be handled outside
# this script (for example in the user's startup or a wrapper). If you
# still need to force a specific policy, set it before running Python:
#   import asyncio
#   asyncio.set_event_loop_policy(asyncio.SelectorEventLoopPolicy())

from postgres_data import models
from postgres_data.db_session import AsyncSessionLocal
def find_data_files(data_dir: str) -> List[Path]:
    p = Path(data_dir)
    if not p.exists():
        raise FileNotFoundError(data_dir)
    # 忽略临时/隐藏文件（例如 Excel 的锁文件以 '~$' 开头）和目录
    files = [f for f in p.iterdir()
             if f.is_file() and not f.name.startswith('~$') and not f.name.startswith('.')
             and f.suffix.lower() in ('.xlsx', '.xls', '.csv')]
    return files


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in ('.xlsx', '.xls'):
        try:
            return pd.read_excel(path)
        except PermissionError:
            logging.warning('无法打开文件（权限或被占用），跳过：%s', path)
            return pd.DataFrame()
        except ImportError:
            logging.error('缺少 Excel 引擎（openpyxl）。请安装：pip install openpyxl')
            return pd.DataFrame()
        except Exception:
            logging.exception('读取 Excel 文件失败，跳过：%s', path)
            return pd.DataFrame()
    return pd.read_csv(path)


def _cols_map(row):
    return {c.lower(): c for c in row.index}


def _norm(val):
    """Normalize pandas cell values: return None for NA/empty; strip and normalize numeric-like strings.

    Examples:
    - NaN -> None
    - 123.0 -> '123'
    - '  abc ' -> 'abc'
    """
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.lower() in ('nan', 'none'):
        return None
    # normalize floats like '123.0' -> '123'
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return s


def map_row_to_example_relation(row) -> dict:
    cols = _cols_map(row)
    def pick(*keys):
        for k in keys:
            if k in cols:
                return row[cols[k]]
        return None

    case_number = _norm(pick('case_number', '案号', 'case', 'id'))
    url = _norm(pick('url', '链接', '网页链接'))
    summary = _norm(pick('summary', '摘要', 'description'))
    k1 = _norm(pick('keyword1', '关键词1', '关键字1'))
    k2 = _norm(pick('keyword2', '关键词2', '关键字2'))
    k3 = _norm(pick('keyword3', '关键词3', '关键字3'))
    return {
        'case_number': case_number,
        'url': url,
        'summary': summary,
        'keyword1': k1,
        'keyword2': k2,
        'keyword3': k3,
    }


def map_row_to_example_legal(row) -> dict:
    cols = _cols_map(row)
    def pick(*keys):
        for k in keys:
            if k in cols:
                return row[cols[k]]
        return None

    region = _norm(pick('region', '地区', '区域', 'province', 'city'))
    url = _norm(pick('url', '链接', '网页链接'))
    title = _norm(pick('title', '法规名称', '说明'))
    return {
        'region': region,
        'url': url,
        'title': title,
    }


async def import_dir(data_dir: str, commit: bool = False):
    files = find_data_files(data_dir)
    logging.info('发现 %d 个数据文件', len(files))
    relations = []
    legals = []
    for f in files:
        logging.info('读取 %s', f)
        df = read_table(f)
        logging.info(' 表格行数: %d', len(df))
        for _, r in df.iterrows():
            # classify row: prefer ExampleRelation if contains case number
            rel = map_row_to_example_relation(r)
            if rel.get('case_number'):
                relations.append(rel)
                continue
            # otherwise try legal (region / title / url)
            leg = map_row_to_example_legal(r)
            if leg.get('region') or leg.get('title') or leg.get('url'):
                legals.append(leg)

    logging.info('解析得到 %d 条 ExampleRelation（案号），%d 条 ExampleLegal（法规/地区）', len(relations), len(legals))
    if not relations and not legals:
        logging.info('没有可插入的记录，退出')
        return
    # dry-run 输出样例
    if relations:
        logging.info('ExampleRelation 样例：%s', relations[0])
    if legals:
        logging.info('ExampleLegal 样例：%s', legals[0])
    if not commit:
        logging.info('未启用 --commit，退出（dry-run）')
        return

    # 如果要写入，先处理 regions 表（去重插入），再插入 cases 并关联 region_id
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        inserted_rel = 0
        inserted_leg = 0
        # 插入 ExampleLegal（去重：按 region+title+url 简单去重）
        for leg in legals:
            # 简单去重：若同 url 或（region + title）已存在则跳过
            exists = None
            if leg.get('url'):
                q = await session.execute(select(models.ExampleLegal).filter_by(url=leg.get('url')))
                exists = q.scalars().first()
            if not exists and leg.get('region') and leg.get('title'):
                q = await session.execute(select(models.ExampleLegal).filter_by(region=leg.get('region'), title=leg.get('title')))
                exists = q.scalars().first()
            if exists:
                logging.info('跳过已存在 ExampleLegal：%s', leg.get('title') or leg.get('url'))
            else:
                session.add(models.ExampleLegal(region=leg.get('region'), url=leg.get('url'), title=leg.get('title')))
                inserted_leg += 1

        # 插入 ExampleRelation（按 case_number 幂等）
        for rel in relations:
            q = await session.execute(select(models.ExampleRelation).filter_by(case_number=rel['case_number']))
            existing = q.scalars().first()
            if existing:
                logging.info('跳过已存在 ExampleRelation case_number=%s', rel['case_number'])
                continue
            session.add(models.ExampleRelation(case_number=rel['case_number'], url=rel.get('url'), summary=rel.get('summary'), keyword1=rel.get('keyword1'), keyword2=rel.get('keyword2'), keyword3=rel.get('keyword3')))
            inserted_rel += 1

        try:
            await session.commit()
            logging.info('已插入 %d 条 ExampleRelation，%d 条 ExampleLegal', inserted_rel, inserted_leg)
        except Exception:
            logging.exception('提交失败，回滚')
            await session.rollback()


def parse_args():
    p = argparse.ArgumentParser(description='导入 data 目录到 cases 表')
    p.add_argument('--data-dir', '-d', required=True, help='数据目录')
    p.add_argument('--commit', action='store_true', help='写入数据库（否则 dry-run）')
    return p.parse_args()


def main():
    args = parse_args()
    if not args.commit:
        logging.info('dry-run 模式，使用 --commit 写入数据库')
    # Use selector event loop on Windows for psycopg async compatibility
    if sys.platform.startswith('win'):
        import selectors as _selectors
        loop_factory = lambda: asyncio.SelectorEventLoop(_selectors.SelectSelector())
        asyncio.run(import_dir(args.data_dir, commit=args.commit), loop_factory=loop_factory)
    else:
        asyncio.run(import_dir(args.data_dir, commit=args.commit))


if __name__ == '__main__':
    main()

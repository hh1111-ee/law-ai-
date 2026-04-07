import asyncio
import os
import sys

# Ensure project root is on sys.path so `postgres_data` package is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from postgres_data.db_session import AsyncSessionLocal
from postgres_data.models import User

# # On Windows, prefer SelectorEventLoop for compatibility with psycopg async
# if sys.platform.startswith('win'):
#     try:
#         import asyncio as _asyncio
#         _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
#     except Exception:
#         pass

async def check(username=None, user_id=None):
    async with AsyncSessionLocal() as session:
        if username is not None:
            q = await session.execute(User.__table__.select().where(User.username == username))
            rows = q.fetchall()
            print('query by username rows:', rows)
        if user_id is not None:
            q = await session.execute(User.__table__.select().where(User.id == user_id))
            rows = q.fetchall()
            print('query by id rows:', rows)

if __name__ == '__main__':
    asyncio.run(check(username='1', user_id=1111))

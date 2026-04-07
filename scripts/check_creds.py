import asyncio, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from postgres_data import adapter

async def main():
    creds = await adapter.get_user_credentials(1111)
    print('creds:', creds)

if __name__ == '__main__':
    # On Windows, ensure selector event loop for psycopg async
    # if sys.platform.startswith('win'):
    #     # try:
    #     #     import asyncio as _asyncio
    #     #     _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
    #     # except Exception:
    #     #     pass
    asyncio.run(main())

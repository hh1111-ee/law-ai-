import asyncio
import json
import uuid
import logging
import os
from typing import Optional, List

logger = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except Exception:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except Exception:
        return default


class MessageRetryManager:
    """本地持久化重试队列。

    行为与配置：
    - 持久化文件：由环境变量 `MSG_RETRY_FILE` 指定，默认 `<BASE>/数据库/pending_messages.jsonl`。
    - 重试间隔：环境变量 `MSG_RETRY_INTERVAL`（秒），默认 5.0。
    - 最大重试次数：环境变量 `MSG_RETRY_MAX_RETRIES`，默认 5。
    - 最大队列长度：环境变量 `MSG_RETRY_QUEUE_MAXSIZE`，默认 1000。
    - 死信文件：环境变量 `MSG_DEAD_LETTER_FILE`，默认 `<file>.dead`。
    """
    def __init__(self, filepath: Optional[str] = None, retry_interval: Optional[float] = None, max_retries: Optional[int] = None, max_queue_size: Optional[int] = None, dead_letter: Optional[str] = None):
        # 从环境变量读取默认配置（实例化时可覆盖）
        self.filepath = filepath or os.environ.get('MSG_RETRY_FILE', os.path.join(os.path.dirname(__file__), '..', '数据库', 'pending_messages.jsonl'))
        self.retry_interval = retry_interval if retry_interval is not None else _env_float('MSG_RETRY_INTERVAL', 5.0)
        self.max_retries = max_retries if max_retries is not None else _env_int('MSG_RETRY_MAX_RETRIES', 5)
        self.max_queue_size = max_queue_size if max_queue_size is not None else _env_int('MSG_RETRY_QUEUE_MAXSIZE', 1000)
        self.dead_letter = dead_letter or os.environ.get('MSG_DEAD_LETTER_FILE', self.filepath + '.dead')

        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
        self._task: Optional[asyncio.Task] = None
        self._stop = False

    async def start(self):
        # 加载持久化文件到内存队列（以安全方式读取并在 event loop 中放入 asyncio.Queue）
        try:
            objs = await asyncio.to_thread(self._load_file_to_list)
            for obj in objs:
                # 如果文件中项超过队容量，此处会阻塞直到有空间
                await self._queue.put(obj)
        except Exception:
            logger.exception("MessageRetryManager: 加载持久化文件失败")
        self._task = asyncio.create_task(self._worker())
        logger.info("MessageRetryManager: started (file=%s interval=%s max_retries=%s queue_max=%s)", self.filepath, self.retry_interval, self.max_retries, self.max_queue_size)

    async def stop(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MessageRetryManager: stopped")

    def _load_file_to_list(self) -> List[dict]:
        out: List[dict] = []
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        out.append(obj)
                    except Exception:
                        logger.exception("MessageRetryManager: 解析持久化行失败")
        except FileNotFoundError:
            return out
        except Exception:
            logger.exception("MessageRetryManager: 读取持久化文件失败")
        return out

    async def _append_to_file(self, obj: dict):
        def _write():
            with open(self.filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        await asyncio.to_thread(_write)

    async def _remove_from_file(self, obj_id: str):
        def _rewrite():
            try:
                lines = []
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            j = json.loads(line)
                            if j.get('id') != obj_id:
                                lines.append(line)
                        except Exception:
                            lines.append(line)
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            except FileNotFoundError:
                return
            except Exception:
                logger.exception("MessageRetryManager: 重写持久化文件失败")
        await asyncio.to_thread(_rewrite)

    async def _append_to_dead_letter(self, obj: dict):
        def _write():
            with open(self.dead_letter, 'a', encoding='utf-8') as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        await asyncio.to_thread(_write)

    async def enqueue_personal(self, sender: int, receiver: int, content: str, ts: Optional[str] = None):
        obj = {
            'id': uuid.uuid4().hex,
            'type': 'personal',
            'retries': 0,
            'payload': {
                'sender': int(sender), 'receiver': int(receiver), 'content': content, 'ts': ts
            }
        }
        await self._append_to_file(obj)
        await self._queue.put(obj)
        logger.info("MessageRetryManager: enqueue personal %s->%s", sender, receiver)

    async def enqueue_group(self, group: str, sender: str, content: str, ts: Optional[str] = None):
        obj = {
            'id': uuid.uuid4().hex,
            'type': 'group',
            'retries': 0,
            'payload': {'group': group, 'sender': str(sender), 'content': content, 'ts': ts}
        }
        await self._append_to_file(obj)
        await self._queue.put(obj)
        logger.info("MessageRetryManager: enqueue group %s@%s", sender, group)

    async def _worker(self):
        # 延迟导入数据库适配器，避免启动时的循环导入问题
        try:
            from postgres_data import adapter as pg_adapter
        except Exception:
            pg_adapter = None

        while not self._stop:
            try:
                if self._queue.empty():
                    await asyncio.sleep(self.retry_interval)
                    continue
                item = await self._queue.get()
                obj_id = item.get('id')
                typ = item.get('type')
                payload = item.get('payload', {})
                retries = int(item.get('retries', 0))
                sent = False

                try:
                    if not (pg_adapter and getattr(pg_adapter, 'create_personal_message', None)):
                        # 如果没有适配器，放回队列并延迟
                        await asyncio.sleep(self.retry_interval)
                        # 增加重试计数
                        item['retries'] = retries + 1
                        if item['retries'] > self.max_retries:
                            logger.warning("MessageRetryManager: 达到最大重试，转入死信: %s", obj_id)
                            await self._append_to_dead_letter(item)
                            await self._remove_from_file(obj_id)
                            continue
                        await self._append_to_file(item)
                        await self._queue.put(item)
                        continue

                    if typ == 'personal':
                        try:
                            await pg_adapter.create_personal_message(payload.get('sender'), payload.get('receiver'), payload.get('content'), payload.get('ts'))
                            sent = True
                        except Exception:
                            logger.exception("MessageRetryManager: 发送 personal 到 DB 失败，稍后重试")
                    elif typ == 'group':
                        try:
                            await pg_adapter.create_group_message(payload.get('group'), payload.get('sender'), payload.get('content'), payload.get('ts'))
                            sent = True
                        except Exception:
                            logger.exception("MessageRetryManager: 发送 group 到 DB 失败，稍后重试")

                except Exception:
                    logger.exception("MessageRetryManager: worker 内部异常")

                if sent:
                    try:
                        await self._remove_from_file(obj_id)
                    except Exception:
                        logger.exception("MessageRetryManager: 从文件中移除已发送消息失败")
                else:
                    # 未发送成功，增加重试计数并判断是否进入死信
                    retries += 1
                    item['retries'] = retries
                    if retries > self.max_retries:
                        logger.warning("MessageRetryManager: 达到最大重试次数(%s)，将消息转入死信: %s", self.max_retries, obj_id)
                        try:
                            await self._append_to_dead_letter(item)
                            await self._remove_from_file(obj_id)
                        except Exception:
                            logger.exception("MessageRetryManager: 写入死信或清理持久化文件失败")
                        continue

                    # 将更新后的重试对象追加到持久化文件，并在循环结束后等待再放回队列
                    try:
                        await self._append_to_file(item)
                    except Exception:
                        logger.exception("MessageRetryManager: 更新持久化文件失败")
                    await asyncio.sleep(self.retry_interval)
                    await self._queue.put(item)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("MessageRetryManager: worker 主循环异常，继续")
                await asyncio.sleep(self.retry_interval)

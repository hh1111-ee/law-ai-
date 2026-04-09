import asyncio
import os
import json
import tempfile
import sys
import types
import time
import pytest

# Ensure project root on sys.path so imports work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from 聊天和用户后端.message_retry import MessageRetryManager


class DummyAdapter:
    def __init__(self, fail_times=0):
        self.calls = 0
        self.fail_times = fail_times

    async def create_personal_message(self, sender, receiver, content, ts=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated transient db error")
        return {'ok': True}

    async def create_group_message(self, group, sender, content, ts=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated transient db error")
        return {'ok': True}


@pytest.mark.asyncio
async def test_personal_message_retry_success(tmp_path, monkeypatch):
    retry_file = tmp_path / "pending.jsonl"
    # Monkeypatch postgres_data.adapter
    dummy = DummyAdapter(fail_times=1)
    mod = types.SimpleNamespace(create_personal_message=dummy.create_personal_message, create_group_message=dummy.create_group_message)
    sys.modules['postgres_data.adapter'] = mod

    mgr = MessageRetryManager(filepath=str(retry_file), retry_interval=0.2, max_retries=3, max_queue_size=10)
    await mgr.start()
    await mgr.enqueue_personal('alice', 'bob', 'hello', 'ts1')

    # Wait enough time for one retry and eventual success
    await asyncio.sleep(1.0)

    # Ensure file cleaned up (message should be removed on success)
    contents = retry_file.read_text(encoding='utf-8') if retry_file.exists() else ''
    assert contents.strip() == '' or contents.strip() == ''

    await mgr.stop()


@pytest.mark.asyncio
async def test_dead_letter_on_max_retries(tmp_path, monkeypatch):
    retry_file = tmp_path / "pending.jsonl"
    dead_file = tmp_path / "pending.jsonl.dead"

    # Adapter always fails
    dummy = DummyAdapter(fail_times=1000)
    mod = types.SimpleNamespace(create_personal_message=dummy.create_personal_message, create_group_message=dummy.create_group_message)
    sys.modules['postgres_data.adapter'] = mod

    mgr = MessageRetryManager(filepath=str(retry_file), retry_interval=0.1, max_retries=2, max_queue_size=10, dead_letter=str(dead_file))
    await mgr.start()
    await mgr.enqueue_personal('alice', 'bob', 'will fail', 'ts2')

    # Wait longer than retries*interval
    await asyncio.sleep(1.0)

    # The original pending file should be cleaned (removed entries), dead letter should contain item
    dead_contents = dead_file.read_text(encoding='utf-8') if dead_file.exists() else ''
    assert dead_contents.strip() != ''
    j = json.loads(dead_contents.strip().splitlines()[-1])
    assert j.get('type') == 'personal'
    assert j.get('payload', {}).get('content') == 'will fail'

    await mgr.stop()

-- scripts/create_personal_messages_table.sql
-- 仅创建 personal_messages 表。
-- 使用：
--   psql -h <host> -p <port> -U <user> -d <database> -f scripts/create_personal_messages_table.sql

BEGIN;

CREATE TABLE IF NOT EXISTS personal_messages (
    id SERIAL PRIMARY KEY,
    sender INTEGER NOT NULL,
    receiver INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;

-- 备注：脚本现在仅创建表，不包含索引或扩展操作。

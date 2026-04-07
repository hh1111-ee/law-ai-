-- create_db.sql
-- 使用方法：在 PowerShell 中临时设置 PGPASSWORD 后执行

CREATE USER welegal_user WITH PASSWORD 'REPLACE_ME';
CREATE DATABASE welegal_db OWNER welegal_user;
GRANT ALL PRIVILEGES ON DATABASE welegal_db TO welegal_user;
psql -h localhost -p 5432 -U welegal_user -d welegal_db  -c "CREATE EXTENSION IF NOT EXISTS pgvector;"
-- 如果需要你也可以在此加入更多角色/权限/扩展安装语句
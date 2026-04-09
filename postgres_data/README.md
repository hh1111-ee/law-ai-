该文件夹用于本地 PostgreSQL 数据目录（可选）。

说明：
- 如果你希望把 PostgreSQL 的数据目录放在项目内（便于备份/清理），可以在安装或初始化时指定此目录，例如 `D:\项目：ai法律平台\postgres_data`。
- 强烈建议不要将此目录提交到版本控制系统（其中包含二进制数据库文件）。
- 如果你使用安装器（EnterpriseDB），在安装向导中将 Data Directory 指向该路径；如果使用 `initdb`，使用 `initdb -D "<path>"` 指定目录。

示例（PowerShell）:
```powershell
# 初始化（假设 initdb 可用）
initdb -D "D:\\项目：ai法律平台\\postgres_data"
# 启动
pg_ctl -D "D:\\项目：ai法律平台\\postgres_data" -l "D:\\项目：ai法律平台\\postgres_data\\logfile" start
```

注意：该目录会快速增长随数据库写入，请确保目标磁盘有足够空间。
临时设置变量
$env:DATABASE_URL='postgresql+psycopg://welegal_user:xxxxxxx@localhost:5432/welegal_db'
删除变量
Remove-Item Env:\DATABASE_URL
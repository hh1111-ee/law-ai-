
好吧，卡壳了，之前不知道这是干什么的，现在我知道了，就写写吧
这是一个比赛用的demo，集成了ollama的gpt-oss-cloude，为什么用云模型呢，因为我太菜了
一个ai法律咨询平台
内置ai助手，社区模块，私聊模块，案例分析，诉讼流程引导，目前的社区的帖子功能只写了一个框架并没有测试
目前的bug：
1.登录注册，注册时如果添加延时或者中断提示，会导致表单切换回登录，不会自动登录回主页，目前不知道原因。
2.私聊信息交流时刷新消息后会导致页面刷新，使用edge和chrom浏览器，目前不知道原因。
操了，因为live server的问题，它居然监管全局，现在忽略了，应该好了
等路注册是结构性问题，已解决
主要使用三种语言，前端：HTML+CSS+JAVASCRIPT,后端：python3
后端依赖：Flask==3.0.3
fastapi==0.115.8
uvicorn==0.34.0
requests==2.32.3
openpyxl==3.1.5
pandas==3.0.0
主要框架：FastAPI（主后端/WS 支持），uvicorn（ASGI 服务器）；以及部分 Flask 模块（旧/次要）。
HTTP 客户端: requests（用于调用外部/本地服务，如 Ollama）。
AI 模型集成: Ollama HTTP API（目标地址示例：http://127.0.0.1:11434/api/chat，结合 asyncio.Semaphore 控制并发）。
数据处理 / 表格: pandas（DataFrame 处理案列数据），openpyxl（读取 Excel）。
实时通信: WebSocket（通过 FastAPI 的 WebSocket + asyncio 实现）
持久化方式: 以本地 pickle 文件存储（目录 数据库 下的 users.pkl、groups.pkl、posts.pkl、personal_messages.pkl、group_messages.pkl）。
日志与运维: Python logging（RotatingFileHandler 写入 combined_server.log）。
标准库依赖（代码中使用）: asyncio, threading, atexit, os, json, datetime 等。
开发/工具说明: CLAUDE.md文件 提到 Playwright/Chromium 的开发注意，但项目后端不强制依赖 Playwright。

采用模块化对象分类，对于用户，帖子等进行抽象以及类封装，留下群对象的扩展，给未来更多功能的实现。具有多个管理器，严谨的管理各个数据类型。
由于是演示用项目，特此说明，密码没采用哈希存储，而是采用明文存储，多处未做数据限制。另外由于本人技术不足未采用sql技术
对于前端：
大部分采用纯静态前端，
前端框架：采用原生DOM+自写脚本
ui/交互库：用 SweetAlert2（通过 CDN 引入）。
网络请求: 使用浏览器原生 fetch 发起 REST 请求（大量调用后端 API，例如 /search、/api/legal、帖子/消息相关接口）。
实时功能: 前端有与后端 WebSocket 交互的页面（私聊场景；后端在 Combined_server.py 提供 /ws/private）。
样式与字体: 使用项目本地 CSS（bigstyle.css）；部分页面备注使用 Google Fonts / FontAwesome
第三方 API: 前端脚本调用外部服务，如 OpenStreetMap Nominatim（反向地理编码）与 ip-api（定位），见 luoji.js。（调试中）
构建/打包: 无构建工具，直接以静态文件部署。
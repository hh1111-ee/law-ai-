// app_config.js: 加载运行时后端地址，包含对常见开发场景的回退策略
(function(){
  // 强制指定后端地址，避免请求发送到 Live Server 的 5502 端口
  const BACKEND = 'https://api.welegal.dpdns.org';
  const local=`http://localhost:8000`;
  // 先行设置全局 API_BASE 为 BACKEND，保证同步脚本能够立刻使用后端地址
  // 异步配置加载完成后会覆盖此值。
  try{ window.API_BASE = local; }catch(e){}

  // 尝试按顺序获取配置：同域 /config -> 本地后端 -> cpolar
   
})();

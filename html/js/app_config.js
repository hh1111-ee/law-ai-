// app_config.js: 加载运行时后端地址，包含对常见开发场景的回退策略
(function(){
  // 检测是否在本地（通过 hostname 或端口）
if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    window.API_BASE = "http://localhost:8000";
} else {
    window.API_BASE = "";  // 使用相对路径
}

  // 尝试按顺序获取配置：同域 /config -> 本地后端 -> cpolar
   
})();

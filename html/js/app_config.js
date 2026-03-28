// app_config.js: 加载运行时后端地址，包含对常见开发场景的回退策略
(async function(){
  const CPOLAR = 'http://localhost:8000';
  const LOCAL = 'http://localhost:8000';

  // 尝试按顺序获取配置：同域 /config -> 本地后端 -> cpolar
  async function tryFetchConfig(url){
    try{
      const r = await fetch(url, {cache: 'no-store'});
      if(r && r.ok) return await r.json();
    }catch(e){/* ignore */}
    return null;
  }

  try{
    let cfg = await tryFetchConfig('/config');
    if(!cfg) cfg = await tryFetchConfig(LOCAL + '/config');
    if(!cfg) cfg = await tryFetchConfig(CPOLAR + '/config');

    if(cfg){
      // 规范并清理配置中可能带的空白
      let base = (cfg.API_BASE || LOCAL || CPOLAR || '').toString().trim();
      // 如果页面通过 HTTPS 访问，避免使用明确的 http:// 路径（会被浏览器阻止）
      if(location.protocol === 'https:' && base.startsWith('http://')){
        base = '';
      }
      window.API_BASE = base;
      try{ localStorage.setItem('APP_CONFIG', JSON.stringify(cfg)); }catch(e){}
    }else{
      let base = window.API_BASE || LOCAL || CPOLAR || '';
      base = base.toString().trim();
      // 如果在 HTTPS 环境且默认回退为 http://localhost，会被浏览器阻止，
      // 且当页面不是在本地访问时，优先使用同域的 `api.` 子域（例如 welegal.us.ci -> api.welegal.us.ci）
      if (location.hostname && !location.hostname.startsWith('localhost') && !location.hostname.startsWith('127.') ) {
        // 若已明确指定 api 子域则保留，否则构造 api.<host>
        if (!base || base.startsWith('http://')) {
          const proto = location.protocol === 'https:' ? 'https:' : 'http:';
          const host = location.hostname.startsWith('api.') ? location.hostname : `api.${location.hostname}`;
          base = `${proto}//${host}`;
        }
      }
      if(location.protocol === 'https:' && base.startsWith('http://')) base = '';
      window.API_BASE = base;
    }
  }catch(e){
    let base = window.API_BASE || LOCAL || CPOLAR || '';
    base = base.toString().trim();
    if(location.protocol === 'https:' && base.startsWith('http://')) base = '';
    window.API_BASE = base;
  }
})();

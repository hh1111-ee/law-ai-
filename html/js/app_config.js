(async function(){
  try{
    const resp = await fetch('/config');
    if(resp.ok){
      const cfg = await resp.json();
      window.API_BASE = cfg.API_BASE || '';
      try{ localStorage.setItem('APP_CONFIG', JSON.stringify(cfg)); }catch(e){}
    }else{
      window.API_BASE = window.API_BASE || '';
    }
  }catch(e){
    window.API_BASE = window.API_BASE || '';
  }
})();

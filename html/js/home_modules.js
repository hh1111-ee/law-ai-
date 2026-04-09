/* home_modules.js
   负责首页模块的懒初始化与交互：IntersectionObserver、时间轴、横向模板下载、拓扑交互、快速表单验证
*/
(function(){
  'use strict';

  const MODULE_INIT = {
    hero(el){ el.classList.add('is-visible'); },
    waterfall(el){ el.classList.add('is-visible'); },
    community(el){ initCommunityScroll(el); },
    templates(el){ initTemplatesScroll(el); },
    timeline(el){ initTimeline(el); },
    topology(el){ initTopology(el); },
    quickform(el){ initQuickForm(el); }
  };

  function initObservers(){
    const io = new IntersectionObserver(onIntersect, { root: null, rootMargin: '0px 0px -8%', threshold: 0.12 });
    document.querySelectorAll('.module--lazy').forEach(el=> io.observe(el));
    function onIntersect(entries, observer){
      entries.forEach(entry=>{
        if(entry.isIntersecting){
          const el = entry.target; el.classList.add('is-visible');
          const moduleName = el.dataset.module;
          if(moduleName && typeof MODULE_INIT[moduleName] === 'function'){
            try{ MODULE_INIT[moduleName](el); }catch(e){ console.error('module init err', e); }
          }
          observer.unobserve(el);
        }
      });
    }
  }

  /* Community Forum Scroll */
  function initCommunityScroll(container){
    container.classList.add('is-visible');
    // Enable horizontal scroll with keyboard if user focuses on something inside
    container.addEventListener('keydown', (e)=>{
      const scrollArea = container.querySelector('.templates-scroll');
      if(scrollArea){
        if(e.key==='ArrowRight') scrollArea.scrollBy({left:300, behavior:'smooth'});
        if(e.key==='ArrowLeft') scrollArea.scrollBy({left:-300, behavior:'smooth'});
      }
    });
  }

  /* Templates: bind download buttons and keyboard navigation */
  function initTemplatesScroll(container){
    container.classList.add('is-visible');
    container.querySelectorAll('.download-btn').forEach(btn=>{
      btn.addEventListener('click', async (e)=>{
        const card = e.target.closest('.template-card');
        const id = card && card.dataset.templateId;
        try{ await downloadTemplate(id); }
        catch(err){ (window.Utils && Utils.showMessage) ? Utils.showMessage('下载失败') : alert('下载失败'); }
      });
    });
    // keyboard: left/right scroll
    container.addEventListener('keydown', (e)=>{
      if(e.key==='ArrowRight') container.scrollBy({left:300, behavior:'smooth'});
      if(e.key==='ArrowLeft') container.scrollBy({left:-300, behavior:'smooth'});
    });
  }

  async function downloadTemplate(id){
    if(!id) throw new Error('no-id');
    // 尝试 fetch 后端资源；若失败，回退到生成示例内容
    const url = `/templates/${id}`;
    try{
      const resp = await fetch(url, {cache:'no-store'});
      if(resp.ok){
        const blob = await resp.blob();
        triggerDownload(blob, `${id}.docx`);
        return;
      }
    }catch(e){ /* fallback below */ }
    // fallback sample
    const sample = `这是 ${id} 的示例模板。请在后台替换为真实文件。`;
    const blob = new Blob([sample], {type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'});
    triggerDownload(blob, `${id}.docx`);
  }

  function triggerDownload(blob, filename){
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename || 'template.docx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=> URL.revokeObjectURL(a.href), 3000);
  }

  /* Timeline */
  function initTimeline(container){
    container.classList.add('is-visible');
    const steps = container.querySelectorAll('.timeline-step');
    const detail = container.querySelector('.timeline-detail');
    const contents = {
      1: `<div class="detail-content">
            <h4>起诉立案阶段</h4>
            <p>原告向有管辖权的法院递交起诉状及相关证据材料。法院在收到材料后进行审查，符合立案条件的，在七日内立案并通知当事人交纳诉讼费。不符合条件的，裁定不予受理。</p>
            <ul class="detail-list">
                <li>准备起诉状正本及副本（按被告人数提供）</li>
                <li>原告身份证明（身份证复印件或营业执照）</li>
                <li>支持诉讼请求的初步证据材料</li>
            </ul>
          </div>`,
      2: `<div class="detail-content">
            <h4>诉前调解阶段</h4>
            <p>法院在立案前或立案后，通常会组织双方进行诉前调解。调解员会听取双方意见，促成和解。如果调解成功，法院出具调解书，具有强制执行力；调解不成，则转入正式审理程序。</p>
            <ul class="detail-list">
                <li>明确调解底线和可让步空间</li>
                <li>准备调解方案和相关证据</li>
                <li>调解书生效后与判决书具有同等效力</li>
            </ul>
          </div>`,
      3: `<div class="detail-content">
            <h4>庭前准备阶段</h4>
            <p>法院向被告送达起诉状副本，被告在十五日内提交答辩状。双方在法院指定的举证期限内提交证据。法院可能会组织庭前会议，交换证据，归纳争议焦点。</p>
            <ul class="detail-list">
                <li>被告按时提交书面答辩状</li>
                <li>双方整理并提交证据目录及复印件</li>
                <li>申请证人出庭或申请法院调查取证（如需）</li>
            </ul>
          </div>`,
      4: `<div class="detail-content">
            <h4>开庭审理阶段</h4>
            <p>法庭调查阶段，双方陈述诉辩意见，出示证据并进行质证。法庭辩论阶段，双方围绕争议焦点发表辩论意见。最后陈述阶段，双方作最后总结。庭审结束后，双方核对笔录并签字。</p>
            <ul class="detail-list">
                <li>准时出庭，遵守法庭纪律</li>
                <li>清晰、有逻辑地陈述事实和理由</li>
                <li>针对对方证据的真实性、合法性、关联性进行质证</li>
            </ul>
          </div>`,
      5: `<div class="detail-content">
            <h4>判决执行阶段</h4>
            <p>法院根据事实和法律作出判决。如不服一审判决，可在十五日内提起上诉。判决生效后，如败诉方拒不履行义务，胜诉方可向法院申请强制执行。</p>
            <ul class="detail-list">
                <li>仔细阅读判决书，决定是否上诉</li>
                <li>留意上诉期限，逾期将丧失上诉权</li>
                <li>准备强制执行申请书及财产线索（如需执行）</li>
            </ul>
          </div>`
    };
    steps.forEach(btn=> btn.addEventListener('click', ()=> switchTimelineStep(btn, steps, detail, contents)));
  }

  function switchTimelineStep(btn, allSteps, detail, contents){
    allSteps.forEach(s=> s.classList.remove('is-active'), s=> s.setAttribute('aria-expanded','false'));
    btn.classList.add('is-active'); btn.setAttribute('aria-expanded','true');
    const id = btn.dataset.step || '1';
    
    // 添加淡出淡入效果
    detail.style.opacity = 0;
    setTimeout(() => {
        detail.innerHTML = contents[id] || '';
        detail.style.opacity = 1;
    }, 200);
    
    try{ btn.scrollIntoView({inline:'center', behavior:'smooth'}); }catch(e){}
  }

  /* Topology: simple click interaction */
  function initTopology(container){
    container.classList.add('is-visible');
    container.addEventListener('click', (e)=>{
      const node = e.target.closest('.topology-node');
      if(!node) return;
      const key = node.dataset.node;
      const messages = { consult:'在线咨询服务', templates:'文书模板库', analysis:'案例分析引擎', flow:'诉讼流程工具' };
      const text = messages[key] || '服务节点';
      (window.Utils && Utils.showMessage) ? Utils.showMessage(text) : alert(text);
    });
  }

  /* Quick form validation + submit */
  function initQuickForm(container){
    container.classList.add('is-visible');
    const form = container.querySelector('#quickForm');
    if(!form) return;
    form.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const fd = new FormData(form);
      const name = fd.get('name')||''; const contact = fd.get('contact')||''; const question = fd.get('question')||'';
      if(!name.trim()||!contact.trim()||!question.trim()){
        (window.Utils && Utils.showMessage) ? Utils.showMessage('请完整填写必填项') : alert('请完整填写必填项');
        return;
      }
      try{
      // 异步提交到后端（示例端点），使用运行时 API_BASE 或回退到 api.<host>
      const winBase = (window.API_BASE || '').toString().trim();
      const proto = location && location.protocol === 'https:' ? 'https:' : 'http:';
      const host = (location && location.hostname && !location.hostname.startsWith('localhost') && !location.hostname.startsWith('127.')) ? `api.${location.hostname}` : 'localhost:8000';
      const base = winBase || `${proto}//${host}`;
      await fetch(base.replace(/\/$/, '') + '/api/quick-consult', { method:'POST', body: fd });
        (window.Utils && Utils.showMessage) ? Utils.showMessage('提交成功，我们会尽快联系您') : alert('提交成功');
        form.reset();
      }catch(e){
        (window.Utils && Utils.showMessage) ? Utils.showMessage('提交失败，请稍后重试') : alert('提交失败');
      }
    });
  }

  function initHomePageModules(){ initObservers(); }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', initHomePageModules); else initHomePageModules();

})();

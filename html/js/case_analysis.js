(function() {
    // ---------- 配置 ----------
    const API_BASE = (window.API_BASE || '').toString().trim();

    // ---------- DOM 元素 ----------
    const searchInput = document.getElementById('searchInput');
    const keywordsContainer = document.getElementById('keywordsContainer');
    const tableArea = document.getElementById('tableArea');

    // ---------- 状态 ----------
    let allKeywords = [];               // 存储所有关键词（用于渲染按钮）
    let currentKeyword = '';             // 当前选中的关键词
    let searchText = '';                  // 当前搜索词
    let debounceTimer = null;

    // ---------- 辅助函数：请求封装 ----------
    async function fetchAPI(url, params = {}) {
        const query = new URLSearchParams(params).toString();
        const winBase = (window.API_BASE || '').toString().trim();
        let base = '';
        if (winBase) base = winBase.replace(/\/$/, '');
        else {
            const proto = location && location.protocol === 'https:' ? 'https:' : 'http:';
            const host = (location && location.hostname && !location.hostname.startsWith('localhost') && !location.hostname.startsWith('127.')) ? `api.${location.hostname}` : 'localhost:8000';
            base = `${proto}//${host}`;
        }
        const fullUrl = base + url + (query ? '?' + query : '');
        console.debug('[case_analysis] fetch', fullUrl);
        const res = await fetch(fullUrl);
        if (!res.ok) {
            console.error('[case_analysis] fetch failed', fullUrl, res.status, await res.text().catch(()=>''));
            throw new Error(`HTTP error ${res.status}`);
        }
        return await res.json();
    }

    // ---------- 1. 加载关键词列表 ----------
    async function loadKeywords() {
        try {
            const data = await fetchAPI('/api/keywords');
            // 假设返回的是字符串数组，例如 ["合同","侵权","违约"]
            allKeywords = Array.isArray(data) ? data : [];
            renderKeywords();
        } catch (err) {
            console.error('关键词加载失败', err);
            keywordsContainer.innerHTML = `<span style="color:#b91c1c;">❌ 关键词加载失败，请检查后端</span>`;
        }
    }

    // 渲染关键词按钮
    function renderKeywords() {
        if (!allKeywords.length) {
            keywordsContainer.innerHTML = `<span style="color:#94a3b8;">⏳ 暂无关键词</span>`;
            return;
        }
        let html = '';
        allKeywords.forEach(kw => {
            const activeClass = (kw === currentKeyword) ? 'active' : '';
            html += `<button class="keyword-btn ${activeClass}" data-keyword="${kw}">${kw}</button>`;
        });
        // 如果当前有关键词筛选，加一个清除按钮
        if (currentKeyword) {
            html += `<button class="keyword-btn clear-btn" id="clearKeywordBtn">✕ 清除筛选</button>`;
        }
        keywordsContainer.innerHTML = html;

        // 给所有关键词按钮绑定事件
        document.querySelectorAll('.keyword-btn[data-keyword]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const kw = e.target.dataset.keyword;
                if (kw === currentKeyword) {
                    // 如果点击已激活的按钮，则取消选中（相当于清除）
                    currentKeyword = '';
                } else {
                    currentKeyword = kw;
                }
                renderKeywords();          // 重新渲染按钮高亮状态
                loadCases();                // 重新加载案例
            });
        });

        // 清除按钮事件（如果存在）
        const clearBtn = document.getElementById('clearKeywordBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                currentKeyword = '';
                renderKeywords();
                loadCases();
            });
        }
    }

    // ---------- 2. 加载案例列表（带筛选）----------
    async function loadCases() {
        // 显示加载中
        tableArea.innerHTML = `<div class="loading">⏳ 正在加载案例...</div>`;

        try {
            const params = {};
            if (searchText.trim() !== '') params.search = searchText.trim();
            if (currentKeyword !== '') params.keyword = currentKeyword;

            const cases = await fetchAPI('/api/cases', params);
            renderCases(cases);
        } catch (err) {
            console.error('案例加载失败', err);
            tableArea.innerHTML = `<div class="error">❌ 加载失败：${err.message}</div>`;
        }
    }

    // 渲染案例表格
    function renderCases(cases) {
        if (!cases || cases.length === 0) {
            tableArea.innerHTML = `<div class="no-data">📭 没有匹配的案例</div>`;
            return;
        }

        let tableHtml = `<table>
            <thead>
                <tr>
                    <th>案号</th>
                    <th>摘要</th>
                    <th>关键词</th>
                </tr>
            </thead>
            <tbody>`;

        cases.forEach(item => {
            // 摘要截断显示（保留60字符）
            const summary = item.摘要 || '';
            const shortSummary = summary.length > 70 ? summary.slice(0, 70) + '…' : summary;

            // 拼接三个关键词标签
            const kws = [item.关键词1, item.关键词2, item.关键词3].filter(k => k && k.trim() !== '');
            const keywordsHtml = kws.map(k => `<span class="keyword-tag">${k}</span>`).join('');
            const caseNumber=item.案号 || '—';
            const caseLink=item.链接||'';
            let caseNumberHtml=caseNumber;
            if(caseLink){
                caseNumberHtml=`<a href="${caseLink}" target="_blank" style="color:3b82f6;text-decoration;font-weight:500;">${caseNumber}</a>`;
            }
            tableHtml += `<tr>
                <td class="case-number">${caseNumberHtml}</td>
                <td class="summary" title="${summary.replace(/"/g, '&quot;')}">${shortSummary || '—'}</td>
                <td>${keywordsHtml || '—'}</td>
            </tr>`;
        });

        tableHtml += `</tbody></table>`;
        tableArea.innerHTML = tableHtml;
    }

    // ---------- 3. 搜索防抖处理 ----------
    function handleSearchInput() {
        searchText = searchInput.value;
        // 防抖：停止输入300ms后再请求
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            loadCases();
        }, 300);
    }

    // 监听搜索输入
    searchInput.addEventListener('input', handleSearchInput);

    // ---------- 4. 初始化 ----------
    (async function init() {
        // 先加载关键词
        await loadKeywords();
        // 再加载案例（无筛选条件）
        await loadCases();
    })();

})();
// ============================================
// AI法律平台 - 合并后的主逻辑
// ============================================

const DEFAULT_AVATAR = 'https://gd-hbimg.huaban.com/a0dcd065b11ba0951ae66436130cc6800671632a8bc0-9IxOal_fw236';
const API_HOST = window.location.hostname || 'localhost';
// 使用 window.API_BASE（若页面已设置）或回退到相对路径（避免 HTTPS 下的混合内容问题）
const API_BASE = (window.API_BASE || '').toString().trim();
// 统一构造后端 URL：优先使用 window.API_BASE，否则回退到 api.<host> 或本地
function apiUrl(path) {
    const winBase = (window.API_BASE || '').toString().trim();
    let base = '';
    if (winBase) base = winBase;
    else {
        try {
            const proto = location && location.protocol === 'https:' ? 'https:' : 'http:';
            const host = (location && location.hostname && !location.hostname.startsWith('localhost') && !location.hostname.startsWith('127.')) ? `api.${location.hostname}` : 'localhost:8000';
            base = `${proto}//${host}`;
        } catch (e) { base = 'http://localhost:8000'; }
    }
    return base.replace(/\/$/, '') + path;
}
// 开发便利：在页面卸载时清除客户端缓存（localStorage/sessionStorage/Cache Storage/ServiceWorker/IndexedDB）
// 仅在本地或当 URL 带有 ?dev_clear_cache=1 时启用，防止在生产环境误删数据
function clearClientCache() {
    try {
        console.log('[dev] 清理客户端缓存...');
        try { localStorage.clear(); } catch(e) { console.warn('localStorage clear failed', e); }
        try { sessionStorage.clear(); } catch(e) { console.warn('sessionStorage clear failed', e); }

        if (window.caches && caches.keys) {
            caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).catch(()=>{});
        }

        if (navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
            navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister())).catch(()=>{});
        }

        // 尝试删除所有 IndexedDB（非所有浏览器支持 indexedDB.databases）
        try {
            if (window.indexedDB && indexedDB.databases) {
                indexedDB.databases().then(dbs => {
                    dbs.forEach(db => {
                        try { indexedDB.deleteDatabase(db.name); } catch(e) {}
                    });
                }).catch(()=>{});
            }
        } catch(e) {}
    } catch (err) {
        console.error('[dev] 清理缓存异常', err);
    }
}

// 根据环境决定是否自动清理（只在开发时打开）
try {
    // 仅在显式传入查询参数 ?dev_clear_cache=1 时启用自动清理，
    // 避免本地开发（localhost）导航时意外清空 localStorage 导致登录信息丢失
    const DEV_CLEAR = location.search.indexOf('dev_clear_cache=1') !== -1;
    if (DEV_CLEAR) {
        window.addEventListener('beforeunload', clearClientCache);
        window.addEventListener('pagehide', clearClientCache);
    }
} catch(e) {}

const LOGIN_REDIRECT_URL = '主页.html';
// 注册/登录流程锁，防止在异步过程中切换表单或重复提交
let isAuthProcessing = false;

// 切换登录/注册表单
function switchTab(tabName) {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const loginTab = document.getElementById('loginTab');
    const registerTab = document.getElementById('registerTab');

    if (!loginForm || !registerForm || !loginTab || !registerTab) {
        return;
    }

    if (tabName === 'login') {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
        loginTab.classList.add('active');
        registerTab.classList.remove('active');
    } else {
        loginForm.style.display = 'none'; 
        registerForm.style.display = 'block';
        loginTab.classList.remove('active');
        registerTab.classList.add('active');
    }
}

// 获取用户位置
function getLocation() {
    const statusElement = document.getElementById('locationStatus');
    const autoLocationInput = document.getElementById('autoLocation');

    if (!statusElement || !autoLocationInput) {
        return;
    }

    if (!navigator.geolocation) {
        statusElement.textContent = '您的浏览器不支持地理定位';
        return;
    }

    statusElement.textContent = '正在获取位置...';

    navigator.geolocation.getCurrentPosition(
        position => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            // 使用逆地理编码获取地址（这里模拟获取）
            // 在实际应用中，可以使用地图API如高德、百度或Google Maps API
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`)
                .then(response => response.json())
                .then(data => {
                    const address = data.display_name || `${lat}, ${lng}`;
                    autoLocationInput.value = address;
                    statusElement.textContent = '位置已获取';
                    statusElement.style.color = '#4CAF50';
                })
                .catch(error => {
                    console.error('逆地理编码失败:', error);
                    autoLocationInput.value = `${lat}, ${lng}`;
                    statusElement.textContent = '位置获取完成（仅坐标）';
                    statusElement.style.color = '#FF9800';
                });
        },
        error => {
            let errorMessage = '';
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage = '用户拒绝了地理定位请求';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage = '位置信息不可用';
                    break;
                case error.TIMEOUT:
                    errorMessage = '获取位置超时';
                    break;
                default:
                    errorMessage = '发生未知错误';
                    break;
            }
            statusElement.textContent = errorMessage;
            statusElement.style.color = '#F44336';

            // 如果无法获取精确位置，尝试使用IP定位作为备选方案
            getIPLocation();
        }
    );
}

// IP定位作为备选方案
function getIPLocation() {
    // 这里使用免费的IP定位API（例如ip-api.com）
    // 实际部署时可能需要考虑API调用限制
    fetch('https://ipapi.co/json/')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const location = `${data.city}, ${data.regionName}, ${data.country}`;
                document.getElementById('autoLocation').value = location;
                document.getElementById('locationStatus').textContent = '使用IP定位';
            }
        })
        .catch(err => {
            console.error('IP定位也失败了:', err);
        });
}

function getStoredUser() {
    try {
        const raw = localStorage.getItem('currentUser');
        console.log('getStoredUser: localStorage currentUser =', raw);
        if (!raw || raw === 'undefined' || raw === 'null') {
            console.warn('getStoredUser: currentUser为空或非法，已清理localStorage');
            localStorage.removeItem('currentUser');
            return null;
        }
        let user;
        try {
            user = JSON.parse(raw);
            console.log('getStoredUser: 解析成功', user);
        } catch (e) {
            console.error('getStoredUser: JSON解析失败，已清理localStorage', e);
            localStorage.removeItem('currentUser');
            return null;
        }
        // 若后端只返回 id 而未返回 username，使用 id 填充 username 以保证前端显示逻辑正常
        try {
            if (user && !user.username && (user.id || user.id === 0)) {
                user.username = String(user.id);
                console.log('getStoredUser: 用 id 填充 username，value=', user.username);
                localStorage.setItem('currentUser', JSON.stringify(user));
            }
        } catch (e) {
            console.warn('getStoredUser: 填充 username 失败', e);
        }
        // 补充状态同步：仅在明确拥有 username 或 id 时才发起请求，避免发送空 JSON 导致服务器返回 400/404
        try {
            const payload = { username: user?.username || null, id: (user && (user.id || user.id === 0)) ? user.id : null };
            if (payload.username || payload.id !== null) {
                fetch(apiUrl('/user_state_search'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.users && data.users.length > 0) {
                            user.state = data.users[0].state;
                            localStorage.setItem('currentUser', JSON.stringify(user));
                            console.log('getStoredUser: 用户状态已同步', user);
                            renderNavUser();
                        }
                    })
                    .catch((err) => { console.error('getStoredUser: 用户状态同步失败', err); });
            } else {
                console.warn('getStoredUser: 未提供 username 或 id，跳过状态同步', payload);
            }
        } catch (e) {
            console.warn('getStoredUser: 状态同步流程异常', e);
        }
        return user;
    } catch (error) {
        console.error('getStoredUser: 读取用户信息失败', error);
        localStorage.removeItem('currentUser');
        return null;
    }
}

function getUserDisplayName(user) {
    return user?.nickname || user?.displayName || user?.username || '用户';
}

function getUserRoleLabel(user) {
    const rawRole = user?.identity || user?.role || user?.user_role || '普通用户';
    const roleMap = {
        owner: '业主方',
        property: '物业方',
        lawyer: '律师'
    };
    return roleMap[rawRole] || rawRole;
}

function renderNavUser() {
    const user = getStoredUser();
    const navContainers = document.querySelectorAll('[data-user-nav]');

    navContainers.forEach(container => {
        const authLink = container.querySelector('.nav-auth-link');
        const chip = container.querySelector('.user-chip');
        const dropdown = container.querySelector('.user-dropdown');
        const avatars = container.querySelectorAll('.user-avatar');
        const nameEls = container.querySelectorAll('.user-name, .user-dropdown-name');
        const roleEls = container.querySelectorAll('.user-role, .user-dropdown-role');
        const stateEls = container.querySelectorAll('.user-state');

        if (!authLink || !chip || !dropdown) {
            console.warn('renderNavUser: 必要元素未找到，跳过该容器');
            return;
        }

        if (!user) {
            authLink.style.display = 'flex';
            chip.style.display = 'none';
            dropdown.hidden = true;
            chip.setAttribute('aria-expanded', 'false');
            console.log('renderNavUser: 未登录，显示登录/注册按钮，隐藏用户按钮');
            return;
        }

        const displayName = getUserDisplayName(user);
        const roleLabel = getUserRoleLabel(user);
        const stateLabel = user.state || '未知';
            authLink.style.display = 'none';
            chip.style.display = 'flex';
            chip.hidden = false;
            dropdown.hidden = true;
            if (avatars && avatars.length > 0) {
                avatars.forEach(avatar => {
                    avatar.src = DEFAULT_AVATAR;
                    avatar.alt = `${displayName}头像`;
                });
            }
            nameEls.forEach(el => {
                el.textContent = displayName;
            });
            roleEls.forEach(el => {
                el.textContent = roleLabel;
            });
            stateEls.forEach(el => {
                el.textContent = stateLabel;
            });
            console.log('renderNavUser: 已登录，显示用户按钮，隐藏登录/注册按钮');
            console.log('renderNavUser: 用户名:', displayName, '角色:', roleLabel, '状态:', stateLabel);
    });
}

function closeAllDropdowns() {
    document.querySelectorAll('[data-user-nav] .user-dropdown:not([hidden])').forEach(dropdown => {
        dropdown.hidden = true;
        const chip = dropdown.closest('[data-user-nav]')?.querySelector('.user-chip');
        if (chip) {
            chip.setAttribute('aria-expanded', 'false');
        }
    });
}

function setupNavUserEvents() {
    document.addEventListener('click', event => {
        const target = event.target;
        const navContainer = target.closest('[data-user-nav]');

        if (!navContainer) {
            closeAllDropdowns();
            return;
        }

        const chip = navContainer.querySelector('.user-chip');
        const dropdown = navContainer.querySelector('.user-dropdown');
        if (!chip || !dropdown || chip.hidden) {
            return;
        }

        if (target.closest('.user-chip')) {
            const isOpen = !dropdown.hidden;
            dropdown.hidden = isOpen;
            chip.setAttribute('aria-expanded', String(!isOpen));
        }
    });

    document.addEventListener('click', event => {
        const logoutBtn = event.target.closest('.logout-btn');
        if (!logoutBtn) {
            return;
        }
        const user = getStoredUser();
        try {
            const payload = { username: user?.username || null, id: (user && (user.id || user.id === 0)) ? user.id : null };
            if (payload.username || payload.id !== null) {
                fetch(apiUrl('/user_logout'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }).then(() => {
                    localStorage.removeItem('currentUser');
                    renderNavUser();
                }).catch(err => {
                    console.error('logout: 请求异常', err);
                    localStorage.removeItem('currentUser');
                    renderNavUser();
                });
            } else {
                console.warn('logout: 无有效用户信息，直接清理 localStorage', payload);
                localStorage.removeItem('currentUser');
                renderNavUser();
            }
        } catch (e) {
            console.error('logout: 处理失败', e);
            localStorage.removeItem('currentUser');
            renderNavUser();
        }
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeAllDropdowns();
        }
    });
}

// 表单提交事件处理
const loginFormEl = document.getElementById('loginForm');
if (loginFormEl) {
    loginFormEl.addEventListener('submit', function (e) {
        e.preventDefault();
        // 处理登录逻辑（使用账号 ID 登录）
        const id = document.getElementById('loginId').value;
        const password = document.getElementById('loginPassword').value;

        fetch(apiUrl('/user_login'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, password })
        })
            .then(res => res.json())
            .then(data => {
                console.log('login: user_login response json', data);
                if (data.code !== 200) {
                    Utils.showMessage(data.error || '登录失败', 'error');
                    console.error('登录失败：后端返回非200', data);
                    return;
                }
                if (!data.data || !data.data.user) {
                    Utils.showMessage('登录成功，但未返回用户信息', 'warning');
                    console.error('登录成功，但未返回用户信息', data);
                    return;
                }
                localStorage.setItem('currentUser', JSON.stringify(data.data.user));
                Swal.fire({
                    icon: 'success',
                    title: '登录成功',
                    timer: 1200,
                    showConfirmButton: false,
                    position: 'top'
                });
                setTimeout(() => { window.location.href = LOGIN_REDIRECT_URL; }, 1200);
            })
            .catch((err) => {
                Utils.showMessage('登录请求失败，请检查网络', 'error');
                console.error('登录请求异常', err);
            });
    });
}

const registerFormEl = document.getElementById('registerForm');
if (registerFormEl) {
    registerFormEl.addEventListener('submit', function (e) {
        e.preventDefault();
        if (isAuthProcessing) {
            Utils.showMessage('正在提交，请稍候...', 'info');
            return;
        }
        isAuthProcessing = true;
        const loginTab = document.getElementById('loginTab');
        const registerTab = document.getElementById('registerTab');
        if (loginTab) loginTab.disabled = true;
        if (registerTab) registerTab.disabled = true;
        // 处理注册逻辑
        const identity = document.getElementById('regIdentity').value;
        const username = document.getElementById('regUsername').value;
        const regId = document.getElementById('regId').value;
        const password = document.getElementById('regPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const manualLocation = document.getElementById('manualLocation').value;
        const autoLocation = document.getElementById('autoLocation').value;

        // 简单验证
        if (password !== confirmPassword) {
            Utils.showMessage('两次输入的密码不一致', 'warning');
            console.warn('注册失败：两次密码不一致', { password, confirmPassword });
            isAuthProcessing = false;
            const loginTab = document.getElementById('loginTab');
            const registerTab = document.getElementById('registerTab');
            if (loginTab) loginTab.disabled = false;
            if (registerTab) registerTab.disabled = false;
            return;
        }

        if (!manualLocation && !autoLocation) {
            Utils.showMessage('请填写位置信息', 'warning');
            console.warn('注册失败：未填写位置信息', { manualLocation, autoLocation });
            isAuthProcessing = false;
            const loginTab = document.getElementById('loginTab');
            const registerTab = document.getElementById('registerTab');
            if (loginTab) loginTab.disabled = false;
            if (registerTab) registerTab.disabled = false;
            return;
        }

        const finalLocation = manualLocation || autoLocation;

        fetch(apiUrl('/user_register'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: regId,
                identity,
                username,
                password,
                location: finalLocation,
                role: identity
            })
        })
            .then(res => {
                console.log('register: fetch user_register response', res);
                return res.json();
            })
            .then(data => {
                console.log('register: user_register response json', data);
                if (data.code !== 200) {
                    Utils.showMessage(data.error || '注册失败', 'error');
                    console.error('注册失败：后端返回非200', data);
                    isAuthProcessing = false;
                    const loginTab = document.getElementById('loginTab');
                    const registerTab = document.getElementById('registerTab');
                    if (loginTab) loginTab.disabled = false;
                    if (registerTab) registerTab.disabled = false;
                    return Promise.reject('register failed');
                }
                // 注册成功后自动登录（使用账号 ID 登录）
                console.log('register: 开始自动登录', { id: regId, password });
                return fetch(apiUrl('/user_login'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: regId, password })
                });
            })
            .then(res => {
                console.log('register: fetch user_login response', res);
                if (!res || !res.ok) {
                    console.error('注册后自动登录失败：无响应', res);
                    return Promise.reject('no login response');
                }
                return res.json();
            })
            .then(data => {
                console.log('register: login result json', data);
                if (!data || data.code !== 200) {
                    Utils.showMessage(data.error || '注册成功，但自动登录失败', 'warning');
                    console.error('注册成功，但自动登录失败', data);
                    // 不自动切换到登录，允许用户留在注册表单并重试
                    isAuthProcessing = false;
                    const loginTab = document.getElementById('loginTab');
                    const registerTab = document.getElementById('registerTab');
                    if (loginTab) loginTab.disabled = false;
                    if (registerTab) registerTab.disabled = false;
                    return;
                }
                let user = null;
                if (data.data && data.data.user) {
                    user = data.data.user;
                }
                console.log('register: 自动登录返回 user', user);
                if (!user) {
                    Utils.showMessage('注册成功，但自动登录未返回用户信息', 'warning');
                    console.error('自动登录成功后未返回用户信息', data);
                    isAuthProcessing = false;
                    const loginTab = document.getElementById('loginTab');
                    const registerTab = document.getElementById('registerTab');
                    if (loginTab) loginTab.disabled = false;
                    if (registerTab) registerTab.disabled = false;
                    return;
                }
                localStorage.setItem('currentUser', JSON.stringify(user));
                console.log('register: localStorage 写入 currentUser', user);
                Swal.fire({
                    icon: 'success', // 图标：success/error/warning/info
                    title: '注册成功',
                    text: '已自动登录，即将跳转到首页',
                    timer: 2000, // 2秒后自动关闭
                    showConfirmButton: false, // 不显示确认按钮
                    position: 'top' // 显示位置
                }).then(() => {
                    // 在提示关闭后再跳转，确保用户能看到信息
                    window.location.href = LOGIN_REDIRECT_URL;
                    console.log('register: 页面跳转到', LOGIN_REDIRECT_URL);
                });
              
            })
            .catch((err) => {
                if (err !== 'register failed') {
                    Utils.showMessage('注册请求失败，请检查网络或稍后重试', 'error');
                    console.error('注册请求异常', err);
                }
                isAuthProcessing = false;
                const loginTab = document.getElementById('loginTab');
                const registerTab = document.getElementById('registerTab');
                if (loginTab) loginTab.disabled = false;
                if (registerTab) registerTab.disabled = false;
            });
    });
}

// 登录逻辑可同步修改（先判断res.ok），这里略

const Utils = {
    showMessage(message, type = 'info') {
        const existingAlert = document.querySelector('.global-alert');
        if (existingAlert) existingAlert.remove();

        const alert = document.createElement('div');
        alert.className = `global-alert alert-${type}`;
        alert.textContent = message;

        Object.assign(alert.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '12px 24px',
            borderRadius: '6px',
            color: 'white',
            zIndex: '9999',
            animation: 'slideInRight 0.3s ease',
            backgroundColor: this.getMessageColor(type),
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            fontWeight: '500'
        });

        document.body.appendChild(alert);

        setTimeout(() => {
            alert.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 3000);
    },

    getMessageColor(type) {
        const colors = {
            success: '#4CAF50',
            error: '#F44336',
            warning: '#FF9800',
            info: '#2196F3'
        };
        return colors[type] || colors.info;
    },

    addGlobalStyles() {
        if (document.querySelector('#global-animations')) return;

        const style = document.createElement('style');
        style.id = 'global-animations';
        style.textContent = `
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }

            @keyframes slideOutRight {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;

        document.head.appendChild(style);
    }
};

// 将 Utils 暴露到 window，保证页面脚本能通过 window.Utils 调用统一的消息接口
if (typeof window !== 'undefined') {
    window.Utils = Utils;
}

function setActiveNavLink() {
    const currentPath = window.location.pathname;
    const currentPage = currentPath.split('/').pop();

    const navLinks = document.querySelectorAll('.nav-menu a');
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        const isHome = currentPage === '' && (href === 'index.html' || href === '主页.html');
        const isStep = currentPage.includes('step') && (href === 'lawsuit-process.html' || href === '诉讼流程.html');

        if (href === currentPage || isHome || isStep) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

function bindKeyboardEvents() {
    document.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && document.querySelector('.auth-form-content[style*="block"]')) {
            const activeForm = document.querySelector('.auth-form-content:not([style*="display:none"])');
            if (activeForm) {
                activeForm.dispatchEvent(new Event('submit'));
            }
        }
    });
}

// ============================================
// 要素式起诉状生成器
// ============================================

class IndictmentGenerator {
    constructor() {
        this.currentStep = 1;
        this.formData = {};
        this.currentIndictment = null;
    }

    init() {
        this.bindEvents();
        this.updateProgress();
        this.setupFormValidation();
    }

    bindEvents() {
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const subInput = e.target.closest('.form-group').querySelector('.sub-input');
                if (subInput) {
                    subInput.style.display = e.target.checked ? 'block' : 'none';
                }
            });
        });

        const factDescription = document.getElementById('factDescription');
        if (factDescription) {
            factDescription.addEventListener('input', (e) => {
                document.getElementById('factCount').textContent = e.target.value.length;
            });
        }

        document.querySelectorAll('#indictmentForm input, #indictmentForm textarea').forEach(input => {
            input.addEventListener('input', () => {
                this.saveFormData();
            });
        });
    }

    setupFormValidation() {
        const requiredFields = document.querySelectorAll('[required]');
        requiredFields.forEach(field => {
            field.addEventListener('blur', () => {
                this.validateField(field);
            });
        });
    }

    validateField(field) {
        const formGroup = field.closest('.form-group');
        const errorElement = formGroup.querySelector('.error-message');

        if (!field.value.trim()) {
            this.showError(field, '此项为必填项');
            return false;
        } else {
            this.clearError(field);
            return true;
        }
    }

    validateStep(step) {
        const stepElement = document.getElementById(`step${step}`);
        const requiredInputs = stepElement.querySelectorAll('[required]');

        let isValid = true;
        requiredInputs.forEach(input => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    }

    showError(input, message) {
        const formGroup = input.closest('.form-group');
        let errorElement = formGroup.querySelector('.error-message');

        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'error-message';
            formGroup.appendChild(errorElement);
        }

        errorElement.textContent = message;
        errorElement.style.color = '#dc2626';
        errorElement.style.fontSize = '0.9rem';
        errorElement.style.marginTop = '5px';

        input.style.borderColor = '#dc2626';
    }

    clearError(input) {
        const formGroup = input.closest('.form-group');
        const errorElement = formGroup.querySelector('.error-message');

        if (errorElement) {
            errorElement.remove();
        }

        input.style.borderColor = '#e5e7eb';
    }

    nextStep(step) {
        if (this.validateStep(this.currentStep)) {
            this.saveStepData(this.currentStep);
            this.hideStep(this.currentStep);
            this.showStep(step);
            this.currentStep = step;
            this.updateProgress();
        }
    }

    prevStep(step) {
        this.hideStep(this.currentStep);
        this.showStep(step);
        this.currentStep = step;
        this.updateProgress();
    }

    hideStep(step) {
        const stepElement = document.getElementById(`step${step}`);
        if (stepElement) {
            stepElement.classList.remove('active');
            stepElement.style.display = 'none';
        }
    }

    showStep(step) {
        const stepElement = document.getElementById(`step${step}`);
        if (stepElement) {
            stepElement.classList.add('active');
            stepElement.style.display = 'block';
        }
    }

    updateProgress() {
        const steps = document.querySelectorAll('.progress-step');
        steps.forEach((step, index) => {
            step.classList.remove('active', 'completed');
            if (index + 1 < this.currentStep) {
                step.classList.add('completed');
            } else if (index + 1 === this.currentStep) {
                step.classList.add('active');
            }
        });
    }

    saveStepData(step) {
        const stepElement = document.getElementById(`step${step}`);
        if (!stepElement) return;

        const inputs = stepElement.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            const name = input.id || input.name;
            const value = input.type === 'checkbox' ? input.checked : input.value;

            if (name && value) {
                this.formData[name] = value;
            }
        });
    }

    saveFormData() {
        const form = document.getElementById('indictmentForm');
        if (!form) return;

        const formElements = form.elements;
        for (let i = 0; i < formElements.length; i++) {
            const element = formElements[i];
            const name = element.id || element.name;
            if (name) {
                const value = element.type === 'checkbox' ? element.checked : element.value;
                this.formData[name] = value;
            }
        }

        localStorage.setItem('indictmentFormData', JSON.stringify(this.formData));
    }

    loadFormData() {
        const savedData = localStorage.getItem('indictmentFormData');
        if (savedData) {
            this.formData = JSON.parse(savedData);
            this.populateForm(this.formData);
        }
    }

    populateForm(data) {
        for (const key in data) {
            const element = document.getElementById(key) || document.querySelector(`[name="${key}"]`);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = data[key];
                } else {
                    element.value = data[key];
                }
            }
        }
    }

    generateIndictment() {
        if (!this.validateStep(3)) {
            return;
        }

        this.saveStepData(3);
                    if (user.id) chip.dataset.userId = user.id;
        const formData = this.collectFormData();
        const indictmentContent = this.generateContent(formData);
        this.showResult(indictmentContent);
        this.nextStep(4);
    }

    collectFormData() {
        const data = {
            courtName: document.getElementById('courtName')?.value || '',
            caseType: document.getElementById('caseType')?.value || '',
            plaintiffName: document.getElementById('plaintiffName')?.value || '',
            plaintiffGender: document.getElementById('plaintiffGender')?.value || '',
            plaintiffBirthDate: document.getElementById('plaintiffBirthDate')?.value || '',
            plaintiffID: document.getElementById('plaintiffID')?.value || '',
            plaintiffAddress: document.getElementById('plaintiffAddress')?.value || '',
            plaintiffPhone: document.getElementById('plaintiffPhone')?.value || '',
            defendantName: document.getElementById('defendantName')?.value || '',
            defendantGender: document.getElementById('defendantGender')?.value || '',
            defendantBirthDate: document.getElementById('defendantBirthDate')?.value || '',
            defendantID: document.getElementById('defendantID')?.value || '',
            defendantAddress: document.getElementById('defendantAddress')?.value || '',
            defendantPhone: document.getElementById('defendantPhone')?.value || '',
            incidentDate: document.getElementById('incidentDate')?.value || '',
            factDescription: document.getElementById('factDescription')?.value || '',
            legalBasis: document.getElementById('legalBasis')?.value || ''
        };

        data.claims = this.getSelectedClaims();

        return data;
    }

    getSelectedClaims() {
        const selectedClaims = [];
        document.querySelectorAll('input[name="claims"]:checked').forEach(checkbox => {
            const claim = {
                type: checkbox.value,
                description: this.getClaimDescription(checkbox.value)
            };

            const subInput = checkbox.closest('.form-group').querySelector('.sub-input input');
            if (subInput && subInput.value) {
                claim.amount = subInput.value;
            }

            selectedClaims.push(claim);
        });
        return selectedClaims;
    }

    getClaimDescription(type) {
        const descriptions = {
            payment: '要求支付欠款',
            compensation: '要求赔偿损失',
            performance: '要求继续履行合同',
            termination: '要求解除合同',
            apology: '要求赔礼道歉',
            other: '其他诉讼请求'
        };
        return descriptions[type] || type;
    }

    generateContent(data) {
        const date = new Date().toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        const caseTypeMap = {
            civil: '民事',
            contract: '合同',
            labor: '劳动',
            property: '财产',
            debt: '债务',
            other: '其他'
        };

        let content = `民事起诉状

原告：${data.plaintiffName}，${data.plaintiffGender}，${data.plaintiffBirthDate ? `出生日期：${data.plaintiffBirthDate}` : ''}
${data.plaintiffID ? `身份证号：${data.plaintiffID}` : ''}
住址：${data.plaintiffAddress}
联系电话：${data.plaintiffPhone || '未提供'}

被告：${data.defendantName}，${data.defendantGender}，${data.defendantBirthDate ? `出生日期：${data.defendantBirthDate}` : ''}
${data.defendantID ? `身份证号：${data.defendantID}` : ''}
住址：${data.defendantAddress}
联系电话：${data.defendantPhone || '未提供'}

诉讼请求：
`;

        if (data.claims && data.claims.length > 0) {
            data.claims.forEach((claim, index) => {
                content += `${index + 1}. ${claim.description}`;
                if (claim.amount) {
                    content += `，金额：${claim.amount}元`;
                }
                content += '；\n';
            });
        } else {
            content += '1. 请求依法判令被告承担相应法律责任；\n';
        }

        content += `诉讼费用由被告承担。

事实与理由：
${data.factDescription || '根据相关事实和法律规定，提出上述诉讼请求。'}

${data.incidentDate ? `纠纷发生时间：${data.incidentDate}\n` : ''}
${data.caseType ? `案件类型：${caseTypeMap[data.caseType] || data.caseType}纠纷\n` : ''}

法律依据：
${data.legalBasis || '依据《中华人民共和国民法典》等相关法律规定。'}

综上，原告为维护自身合法权益，特向贵院提起诉讼，请求贵院依法裁判。

此致
${data.courtName || 'XXX人民法院'}

    具状人：${data.plaintiffName}
    ${date}
`;

        return content;
    }

    showResult(content) {
        const preview = document.getElementById('indictmentPreview');
        if (preview) {
            preview.innerHTML = `<pre style="white-space: pre-wrap; font-family: 'Microsoft YaHei', sans-serif; line-height: 1.6; padding: 1rem; background: #f8f9fa; border-radius: 8px; font-size: 14px;">${content}</pre>`;
        }

        this.currentIndictment = content;
    }

    downloadIndictment() {
        if (!this.currentIndictment) {
            alert('请先生成起诉状');
            return;
        }

        const blob = new Blob([this.currentIndictment], { type: 'text/plain;charset=utf-8' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `起诉状_${new Date().getTime()}.txt`;
        link.style.display = 'none';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        alert('起诉状已开始下载！');
    }

    copyToClipboard() {
        if (!this.currentIndictment) {
            alert('请先生成起诉状');
            return;
        }

        navigator.clipboard.writeText(this.currentIndictment)
            .then(() => alert('起诉状内容已复制到剪贴板！'))
            .catch(() => {
                const textArea = document.createElement('textarea');
                textArea.value = this.currentIndictment;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                alert('起诉状内容已复制到剪贴板！');
            });
    }

    printIndictment() {
        if (!this.currentIndictment) {
            alert('请先生成起诉状');
            return;
        }

        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>打印起诉状</title>
                <style>
                    body { font-family: 'Microsoft YaHei', sans-serif; line-height: 1.6; padding: 20px; margin: 0; }
                    pre { white-space: pre-wrap; margin: 0; }
                    @media print {
                        body { padding: 10mm; }
                        @page { margin: 20mm; }
                    }
                </style>
            </head>
            <body>
                <pre>${this.currentIndictment}</pre>
                <script>
                    window.onload = function() {
                        window.print();
                        setTimeout(function() {
                            window.close();
                        }, 1000);
                    }
                </script>
            </body>
            </html>
        `);
        printWindow.document.close();
    }

    editForm() {
        this.prevStep(1);
    }

    clearForm() {
        if (confirm('确定要清空所有表单数据吗？')) {
            document.getElementById('indictmentForm').reset();
            localStorage.removeItem('indictmentFormData');
            this.formData = {};
            this.currentStep = 1;
            this.showStep(1);
            this.hideStep(2);
            this.hideStep(3);
            this.hideStep(4);
            this.updateProgress();
        }
    }
}

const indictmentGenerator = new IndictmentGenerator();

// 全局函数导出
window.switchTab = switchTab;
window.getLocation = getLocation;
window.nextStep = (step) => indictmentGenerator.nextStep(step);
window.prevStep = (step) => indictmentGenerator.prevStep(step);
window.generateIndictment = () => indictmentGenerator.generateIndictment();
window.downloadIndictment = () => indictmentGenerator.downloadIndictment();
window.copyToClipboard = () => indictmentGenerator.copyToClipboard();
window.printIndictment = () => indictmentGenerator.printIndictment();
window.editForm = () => indictmentGenerator.editForm();

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function () {
    Utils.addGlobalStyles();
    renderNavUser();
    setupNavUserEvents();
    setActiveNavLink();
    bindKeyboardEvents();

    if (document.getElementById('indictmentForm')) {
        indictmentGenerator.init();
        indictmentGenerator.loadFormData();
    }
});
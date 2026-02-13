// ============================================
// AI法律平台 - 主JavaScript文件
// ============================================

const DEFAULT_AVATAR = 'https://gd-hbimg.huaban.com/a0dcd065b11ba0951ae66436130cc6800671632a8bc0-9IxOal_fw236';

// 1. 用户管理模块
const UserManager = {
    getStoredUser() {
        try {
            const raw = localStorage.getItem('currentUser');
            if (!raw) return null;
            return JSON.parse(raw);
        } catch (error) {
            console.error('读取用户信息失败:', error);
            return null;
        }
    },

    getUserDisplayName(user) {
        return user?.nickname || user?.displayName || user?.username || '用户';
    },

    getUserRoleLabel(user) {
        const rawRole = user?.identity || user?.role || user?.user_role || '普通用户';
        const roleMap = {
            owner: '业主方',
            property: '物业方',
            lawyer: '律师'
        };
        return roleMap[rawRole] || rawRole;
    },

    renderNavUser() {
        const user = this.getStoredUser();
        const navContainers = document.querySelectorAll('[data-user-nav]');

        navContainers.forEach(container => {
            const authLink = container.querySelector('.nav-auth-link');
            const chip = container.querySelector('.user-chip');
            const dropdown = container.querySelector('.user-dropdown');
            const avatars = container.querySelectorAll('.user-avatar');
            const nameEls = container.querySelectorAll('.user-name, .user-dropdown-name');
            const roleEls = container.querySelectorAll('.user-role, .user-dropdown-role');

            if (!authLink || !chip || !dropdown || avatars.length === 0) return;

            if (!user) {
                authLink.hidden = false;
                chip.hidden = true;
                dropdown.hidden = true;
                chip.setAttribute('aria-expanded', 'false');
                return;
            }

            const displayName = this.getUserDisplayName(user);
            const roleLabel = this.getUserRoleLabel(user);

            authLink.hidden = true;
            chip.hidden = false;
            
            avatars.forEach(avatar => {
                avatar.src = user.avatar || DEFAULT_AVATAR;
                avatar.alt = `${displayName}头像`;
            });
            
            nameEls.forEach(el => {
                el.textContent = displayName;
            });
            
            roleEls.forEach(el => {
                el.textContent = roleLabel;
            });
        });
    },

    setupNavUserEvents() {
        // 点击用户芯片切换下拉菜单
        document.addEventListener('click', (event) => {
            const target = event.target;
            const navContainer = target.closest('[data-user-nav]');
            
            // 点击其他地方关闭所有下拉菜单
            if (!navContainer) {
                this.closeAllDropdowns();
                return;
            }

            const chip = navContainer.querySelector('.user-chip');
            const dropdown = navContainer.querySelector('.user-dropdown');
            
            if (!chip || !dropdown || chip.hidden) return;

            // 点击用户芯片切换下拉菜单
            if (target.closest('.user-chip')) {
                this.toggleDropdown(chip, dropdown);
            }
        });

        // 退出登录
        document.addEventListener('click', (event) => {
            if (event.target.closest('.logout-btn')) {
                this.logout();
            }
        });

        // ESC键关闭下拉菜单
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllDropdowns();
            }
        });
    },

    toggleDropdown(chip, dropdown) {
        const isOpen = !dropdown.hidden;
        dropdown.hidden = isOpen;
        chip.setAttribute('aria-expanded', String(!isOpen));
    },

    closeAllDropdowns() {
        document.querySelectorAll('[data-user-nav] .user-dropdown').forEach(dropdown => {
            dropdown.hidden = true;
            const chip = dropdown.closest('[data-user-nav]')?.querySelector('.user-chip');
            if (chip) chip.setAttribute('aria-expanded', 'false');
        });
    },

    logout() {
        localStorage.removeItem('currentUser');
        this.renderNavUser();
        alert('已退出登录');
        
        // 如果在登录页，刷新页面
        if (window.location.pathname.includes('login.html')) {
            window.location.reload();
        }
    }
};

// 2. 登录注册功能
const AuthManager = {
    // 切换登录/注册表单
    switchTab(tabName) {
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
    },

    // 初始化表单事件
    initAuthForms() {
        const loginFormEl = document.getElementById('loginForm');
        if (loginFormEl) {
            loginFormEl.addEventListener('submit', this.handleLogin.bind(this));
        }
        
        const registerFormEl = document.getElementById('registerForm');
        if (registerFormEl) {
            registerFormEl.addEventListener('submit', this.handleRegister.bind(this));
        }
    },

    // 处理登录
    handleLogin(e) {
        e.preventDefault();
        
        const username = document.getElementById('loginUsername').value.trim();
        const password = document.getElementById('loginPassword').value;

        if (!username || !password) {
            alert('请填写用户名和密码');
            return;
        }

        // 模拟登录成功
        const user = {
            username: username,
            nickname: username,
            identity: 'owner',
            role: '普通用户',
            avatar: DEFAULT_AVATAR
        };

        localStorage.setItem('currentUser', JSON.stringify(user));
        UserManager.renderNavUser();
        
        alert('登录成功！');
        
        // 跳转到首页
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1000);
    },

    // 处理注册
    handleRegister(e) {
        e.preventDefault();
        
        const identity = document.querySelector('input[name="identity"]:checked')?.value || 'owner';
        const username = document.getElementById('regUsername').value.trim();
        const password = document.getElementById('regPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        // 验证
        if (password !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }
        
        if (!username || username.length < 3) {
            alert('用户名至少3个字符');
            return;
        }
        
        if (!password || password.length < 6) {
            alert('密码至少6个字符');
            return;
        }

        // 模拟注册成功
        const user = {
            username: username,
            nickname: username,
            identity: identity,
            role: this.getRoleLabel(identity),
            avatar: DEFAULT_AVATAR,
            location: document.getElementById('autoLocation')?.value || 
                     document.getElementById('manualLocation')?.value || '未设置'
        };

        localStorage.setItem('currentUser', JSON.stringify(user));
        UserManager.renderNavUser();
        
        alert('注册成功！已自动登录');
        
        // 跳转到首页
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1000);
    },

    getRoleLabel(identity) {
        const roleMap = {
            owner: '业主方',
            property: '物业方',
            lawyer: '律师'
        };
        return roleMap[identity] || '普通用户';
    }
};

// 3. 地理位置功能
const LocationService = {
    getLocation() {
        const statusElement = document.getElementById('locationStatus');
        const autoLocationInput = document.getElementById('autoLocation');
        
        if (!navigator.geolocation) {
            statusElement.textContent = '您的浏览器不支持地理定位';
            return;
        }
        
        statusElement.textContent = '正在获取位置...';
        statusElement.style.color = '#2196F3';
        
        navigator.geolocation.getCurrentPosition(
            position => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // 使用逆地理编码获取地址
                this.reverseGeocode(lat, lng)
                    .then(address => {
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
                switch(error.code) {
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
                
                // 尝试使用IP定位作为备选方案
                this.getIPLocation();
            }
        );
    },
    
    reverseGeocode(lat, lng) {
        return fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`)
            .then(response => response.json())
            .then(data => {
                return data.display_name || `${lat}, ${lng}`;
            });
    },
    
    getIPLocation() {
        fetch('https://ipapi.co/json/')
            .then(response => response.json())
            .then(data => {
                if(data.city) {
                    const location = `${data.city}, ${data.region}, ${data.country_name}`;
                    document.getElementById('autoLocation').value = location;
                    document.getElementById('locationStatus').textContent = '使用IP定位';
                }
            })
            .catch(err => {
                console.error('IP定位失败:', err);
            });
    }
};

// 4. 通用工具函数
const Utils = {
    // 显示消息提示
    showMessage(message, type = 'info') {
        // 移除现有提示
        const existingAlert = document.querySelector('.global-alert');
        if (existingAlert) existingAlert.remove();
        
        // 创建新提示
        const alert = document.createElement('div');
        alert.className = `global-alert alert-${type}`;
        alert.textContent = message;
        
        // 样式
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
        
        // 添加到页面
        document.body.appendChild(alert);
        
        // 3秒后自动移除
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

    // 添加CSS动画
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

// 5. 页面初始化
const App = {
    init() {
        // 添加全局样式
        Utils.addGlobalStyles();
        
        // 初始化用户管理
        UserManager.renderNavUser();
        UserManager.setupNavUserEvents();
        
        // 初始化认证表单
        AuthManager.initAuthForms();
        
        // 设置当前页面导航激活状态
        this.setActiveNavLink();
        
        // 绑定键盘事件
        this.bindKeyboardEvents();
    },

    setActiveNavLink() {
        const currentPath = window.location.pathname;
        const currentPage = currentPath.split('/').pop();
        
        const navLinks = document.querySelectorAll('.nav-menu a');
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === currentPage || 
                (currentPage === '' && href === 'index.html') ||
                (currentPage.includes('step') && href === 'lawsuit-process.html')) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    },

    bindKeyboardEvents() {
        // 回车键提交表单
        document.addEventListener('keypress', function(e) {
            if(e.key === 'Enter' && document.querySelector('.auth-form-content[style*="block"]')) {
                const activeForm = document.querySelector('.auth-form-content:not([style*="display:none"])');
                if(activeForm) {
                    activeForm.dispatchEvent(new Event('submit'));
                }
            }
        });
    }
};

// 6. 全局函数导出
window.switchTab = AuthManager.switchTab;
window.getLocation = LocationService.getLocation;
window.UserManager = UserManager;
window.AuthManager = AuthManager;

// 7. 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
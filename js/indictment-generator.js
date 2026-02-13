// ============================================
// 要素式起诉状生成器 - JavaScript逻辑
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
        // 复选框显示/隐藏子输入框
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const subInput = e.target.closest('.form-group').querySelector('.sub-input');
                if (subInput) {
                    subInput.style.display = e.target.checked ? 'block' : 'none';
                }
            });
        });

        // 字数统计
        const factDescription = document.getElementById('factDescription');
        if (factDescription) {
            factDescription.addEventListener('input', (e) => {
                document.getElementById('factCount').textContent = e.target.value.length;
            });
        }

        // 表单输入监听
        document.querySelectorAll('#indictmentForm input, #indictmentForm textarea').forEach(input => {
            input.addEventListener('input', () => {
                this.saveFormData();
            });
        });
    }

    setupFormValidation() {
        // 为所有必填字段添加验证提示
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

        // 保存表单数据
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

        // 保存所有表单数据
        const formElements = form.elements;
        for (let i = 0; i < formElements.length; i++) {
            const element = formElements[i];
            const name = element.id || element.name;
            if (name) {
                const value = element.type === 'checkbox' ? element.checked : element.value;
                this.formData[name] = value;
            }
        }

        // 保存到本地存储
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

        // 收集表单数据
        this.saveStepData(3);
        const formData = this.collectFormData();

        // 生成起诉状内容
        const indictmentContent = this.generateContent(formData);

        // 显示结果
        this.showResult(indictmentContent);

        // 进入第四步
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

        // 收集诉讼请求
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
            
            // 获取金额
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
            'payment': '要求支付欠款',
            'compensation': '要求赔偿损失',
            'performance': '要求继续履行合同',
            'termination': '要求解除合同',
            'apology': '要求赔礼道歉',
            'other': '其他诉讼请求'
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
            'civil': '民事',
            'contract': '合同',
            'labor': '劳动',
            'property': '财产',
            'debt': '债务',
            'other': '其他'
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
        
        // 添加诉讼请求
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
        
        // 保存内容供下载
        this.currentIndictment = content;
    }

    downloadIndictment() {
        if (!this.currentIndictment) {
            alert('请先生成起诉状');
            return;
        }
        
        // 创建Blob对象
        const blob = new Blob([this.currentIndictment], { type: 'text/plain;charset=utf-8' });
        
        // 创建下载链接
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `起诉状_${new Date().getTime()}.txt`;
        link.style.display = 'none';
        
        // 触发下载
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
            .catch(err => {
                console.error('复制失败:', err);
                // 备用方法
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

// 创建全局实例
const indictmentGenerator = new IndictmentGenerator();

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('indictmentForm')) {
        indictmentGenerator.init();
        indictmentGenerator.loadFormData();
    }
});

// 导出全局函数
window.nextStep = (step) => indictmentGenerator.nextStep(step);
window.prevStep = (step) => indictmentGenerator.prevStep(step);
window.generateIndictment = () => indictmentGenerator.generateIndictment();
window.downloadIndictment = () => indictmentGenerator.downloadIndictment();
window.copyToClipboard = () => indictmentGenerator.copyToClipboard();
window.printIndictment = () => indictmentGenerator.printIndictment();
window.editForm = () => indictmentGenerator.editForm();
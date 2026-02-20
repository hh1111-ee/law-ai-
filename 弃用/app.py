import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS  # 解决跨域

app = Flask(__name__)
CORS(app)  # 允许所有跨域请求，生产环境可配置更严格

# ------------------- 全局加载 Excel 数据 -------------------
# 假设 Excel 文件名为 cases.xlsx，请确保列名正确
EXCEL_FILE = '数据\案号.xlsx'
try:
    df = pd.read_excel(EXCEL_FILE, dtype=str)  # 所有列读为字符串，避免数字被转换
    # 确保列存在（如果列名不同，请在这里修改）
    required_cols = ['案号','链接', '摘要', '关键词1', '关键词2', '关键词3']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Excel 文件中缺少必要列: {col}")
    # 将 NaN 替换为空字符串
    df = df.fillna('')
    print(f"✅ 成功加载 {len(df)} 条案例")
except Exception as e:
    print(f"❌ 加载 Excel 失败: {e}")
    df = pd.DataFrame()  # 空 DataFrame，后续请求会返回空数据

# ------------------- API 1: 获取所有关键词（去重）-------------------
@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    if df.empty:
        return jsonify([])
    # 将三个关键词列合并为一列，去重，并排除空字符串
    keywords = pd.concat([df['关键词1'], df['关键词2'], df['关键词3']])
    unique_keywords = keywords[keywords != ''].unique().tolist()
    return jsonify(unique_keywords)

# ------------------- API 2: 获取案例（支持筛选）-------------------
@app.route('/api/cases', methods=['GET'])
def get_cases():
    if df.empty:
        return jsonify([])

    # 获取查询参数
    search_term = request.args.get('search', '').strip()
    keyword = request.args.get('keyword', '').strip()

    # 拷贝 DataFrame 避免修改原数据
    data = df.copy()

    # 1. 按关键词筛选（精确匹配任意一个关键词列）
    if keyword:
        mask = (
            (data['关键词1'] == keyword) |
            (data['关键词2'] == keyword) |
            (data['关键词3'] == keyword)
        )
        data = data[mask]

    # 2. 按搜索词筛选（在案号或摘要中模糊匹配，大小写不敏感）
    if search_term:
        mask = (
            data['案号'].str.contains(search_term, case=False, na=False) |
            data['摘要'].str.contains(search_term, case=False, na=False)
        )
        data = data[mask]

    # 转换为字典列表返回
    result = data.to_dict(orient='records')
    return jsonify(result)

# ------------------- 启动服务 -------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
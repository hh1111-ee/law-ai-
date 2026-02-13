# -------------------------------------------------
# server.py – 加入 CORS 支持
# -------------------------------------------------
import os, logging, requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS   # <‑‑ 新增

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="/")
CORS(app)                     # <‑‑ 这里开启跨域（默认允许所有来源）

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
SYSTEM_PROMPT = """
你是一名中华人民共和国执业律师，请在回答中**必须**引用具体的法条编号（如《民法典》第23条）。
如果法律里没有对应条文，请直接回复“暂无相关法条”。  
请使用简洁、正式的法律语言，切勿捏造法条内容。
"""

@app.route("/api/legal", methods=["POST", "OPTIONS"])
def legal_chat():
    # Flask‑CORS 已经自动处理 OPTIONS，下面只处理 POST
    if request.method == "OPTIONS":
        # 直接返回空响应让浏览器通过预检
        return ("", 204)

    try:
        data = request.get_json()
        if not data or "question" not in data:
            return jsonify({"error": "请输入要咨询的法律问题"}), 400

        question = data["question"].strip()
        if not question:
            return jsonify({"error": "问题不能为空"}), 400

        payload = {
            "model": "gpt-oss:120b-cloud",
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question}
            ]
        }

        logger.info(f"→ 向 Ollama 发送请求：{question[:30]}...")
        resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
        resp.raise_for_status()
        answer = resp.json().get("message", {}).get("content", "暂无相关法条")
        logger.info(f"✅ 得到答案（前50字符）: {answer[:50]}")
        return jsonify({"answer": answer})
    except requests.exceptions.ConnectionError:
        logger.exception("❌ 无法连接到 Ollama")
        return jsonify({"error": "无法连接到 Ollama，请先启动 Ollama"}), 500
    except Exception as e:
        logger.exception("❌ 未知错误")
        return jsonify({"error": f"服务器内部错误：{e}"}), 500

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "ai小助手.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

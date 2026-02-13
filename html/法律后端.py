# -------------------------------------------------
# server.py – Flask + CORS + 法律搜索 + 位置推荐
# -------------------------------------------------
import os, json, logging, requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ------------------- 配置 -----------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
AMAP_KEY = os.getenv("AMAP_KEY", "").strip()

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="/")
CORS(app)                      # 允许所有来源跨域（Live Server 5501 → Flask 5500）
print(f"启动服务：{app.url_map}")
# ---------- 1️⃣ IP 定位（简单实现） ----------
def get_location_by_ip(ip: str):
    """简化版：直接返回默认位置，跳过易出错的IP定位接口"""
    logger.info(f"跳过IP定位（IP: {ip}），使用默认位置")
    return {"province": "北京市", "city": "北京市"}

def get_location_by_geo(lat: float, lng: float):
    if not AMAP_KEY:
        logger.warning("AMAP_KEY 未配置，跳过高德反向地理编码")
        return None
    try:
        resp = requests.get(
            "https://restapi.amap.com/v3/geocode/regeo",
            params={
                "key": AMAP_KEY,
                "location": f"{lng},{lat}",
                "extensions": "base",
                "output": "JSON"
            },
            timeout=8
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return None
        comp = (data.get("regeocode") or {}).get("addressComponent") or {}
        province = comp.get("province") or ""
        city = comp.get("city") or ""
        if isinstance(city, list):
            city = city[0] if city else ""
        if not city:
            city = comp.get("district") or province
        if province:
            return {"province": province, "city": city or province}
    except Exception:
        logger.exception("高德反向地理编码失败")
    return None

# ---------- 2️⃣ 本地法规推荐（简易映射） ----------
LOCAL_LAWS = {
    "北京市": [
        {"title": "北京市物业管理条例", "desc": "北京地区物业管理基本规范"},
        {"title": "北京市房屋租赁管理规定", "desc": "北京房屋租赁市场管理办法"},
        {"title": "北京市业主大会和业主委员会指导规则", "desc": "业主组织运作指导文件"},
        {"title": "北京市住宅专项维修资金管理办法", "desc": "住宅维修资金的使用与监管"}
    ],
    "上海市": [
        {"title": "上海市住宅物业管理规定", "desc": "上海住宅物业管理细则"},
        {"title": "上海市房屋租赁管理条例", "desc": "上海租赁市场监管条例"},
        {"title": "上海市业主大会和业主委员会活动规则", "desc": "业主组织活动规范"},
        {"title": "上海市住宅维修资金管理规定", "desc": "住宅维修资金管理办法"}
    ],
    # 其它省份使用通用法规
    "default": [
        {"title": "物业管理条例", "desc": "全国物业管理基本法规"},
        {"title": "房屋租赁管理办法", "desc": "全国房屋租赁管理规定"},
        {"title": "业主大会和业主委员会指导规则", "desc": "业主组织运作的全国指导文件"},
        {"title": "住宅专项维修资金管理办法", "desc": "住宅维修资金管理的全国规范"}
    ]
}

def get_recommended_laws(province: str):
    return LOCAL_LAWS.get(province, LOCAL_LAWS["default"])

# ---------- 3️⃣ 国家法律数据库搜索（requests+BeautifulSoup） ----------
FLK_SEARCH_URL = "https://flk.npc.gov.cn/search/query"

# 法律后端.py  –  在原有代码的基础上替换此函数
def _search_npc_laws_requests(keyword: str, page: int = 1):
    """requests 兜底解析（页面结构变化时可能不稳定）。"""
    try:
        params = {
            "keyWord": keyword,
            "pageNum": page,
            "pageSize": 20,
            "sortBy": "relevance"
        }
        resp = requests.get(FLK_SEARCH_URL, params=params, timeout=12)
        resp.raise_for_status()
        html = resp.text

        # 轻量提取，防止完全空结果
        results = []
        for line in html.splitlines():
            if "title-content" in line and "href" in line:
                results.append({"name": "", "desc": "", "url": ""})
                break
        return results
    except Exception:
        logger.exception("国家法律库搜索出错（requests 兜底）")
        return []


def search_npc_laws(keyword: str, page: int = 1):
    """
    通过 Playwright 模拟浏览器抓取国家法律库搜索结果。
    每条记录 dict 包含:
        - name   : 标题
        - desc   : 摘要或简短描述
        - url    : 详情页完整 URL
    """
    def safe_text(locator):
        if locator.count() == 0:
            return ""
        try:
            return locator.inner_text(timeout=2000).strip()
        except Exception:
            text = locator.text_content() or ""
            return text.strip()

    try:
        params = {
            "keyWord": keyword,
            "pageNum": page,
            "pageSize": 20,
            "sortBy": "relevance"
        }
        url = f"https://flk.npc.gov.cn/search?{urlencode(params)}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale="zh-CN",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page_obj = context.new_page()
            page_obj.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_()
            )
            page_obj.goto(url, wait_until="domcontentloaded", timeout=45000)

            selectors = [
                "div.result-item",
                "ul.result-list li",
                ".result-list li",
                "div.list-item"
            ]
            found_selector = None
            for sel in selectors:
                try:
                    page_obj.wait_for_selector(sel, timeout=5000)
                    if page_obj.locator(sel).count() > 0:
                        found_selector = sel
                        break
                except PlaywrightTimeoutError:
                    continue

            results = []
            if found_selector:
                items = page_obj.locator(found_selector)
                for i in range(min(items.count(), 20)):
                    item = items.nth(i)
                    title_el = item.locator("a.title-content, a, .title-content").first
                    title = safe_text(title_el)
                    href = ""
                    if title_el.count() > 0:
                        href = title_el.get_attribute("href") or ""
                    if not href:
                        href = item.get_attribute("data-href") or ""

                    desc_el = item.locator("p, .c9, .summary, .result-desc, .info").first
                    desc = safe_text(desc_el)

                    if title:
                        if href and not href.startswith("http"):
                            href = "https://flk.npc.gov.cn" + href
                        results.append({
                            "name": title,
                            "desc": desc,
                            "url": href
                        })

            browser.close()
            return results
    except Exception:
        logger.exception("国家法律库搜索出错（playwright）")
        return _search_npc_laws_requests(keyword, page)

# -------------------------------------------------
# API: /search  → 前端发送 {keyword:"xxx", page:1}
# -------------------------------------------------
@app.route("/search", methods=["POST", "OPTIONS"])
def api_search():
    # 处理 CORS 预检
    if request.method == "OPTIONS":
        return ("", 204)

    try:
        payload = request.get_json(silent=True) or {}
        keyword = (payload.get("keyword") or "").strip()
        try:
            page = int(payload.get("page", 1))
        except (TypeError, ValueError):
            page = 1

        if not keyword:
            return jsonify({"error": "请提供搜索关键字"}), 400

        # ① 优先使用浏览器定位（前端传入经纬度），失败则用 IP
        location = None
        geo = payload.get("location") or {}
        if "lat" in geo and "lng" in geo:
            location = get_location_by_geo(geo["lat"], geo["lng"])
        if not location:
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
            client_ip = client_ip.split(",")[0].strip()
            location = get_location_by_ip(client_ip)

        # ② 本地法规推荐
        recommended = get_recommended_laws(location["province"])

        # ③ 远端检索
        remote_results = search_npc_laws(keyword, page=page)

        # 合并为统一结构返回给前端
        return jsonify({
            "location": location,
            "recommended": recommended,
            "results": remote_results,
            "page": page
        })
    except Exception as e:
        logger.exception("搜索接口异常")
        return jsonify({"error": f"服务器内部错误：{e}"}), 500

# -------------------------------------------------
# 静态页面返回（根路径直接返回 HTML）
# -------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "法律咨询.html")

# -------------------------------------------------
if __name__ == "__main__":
    # 这里把端口改成 5500（或者你想的任何空闲端口）
    app.run(host="0.0.0.0", port=5500, debug=True)

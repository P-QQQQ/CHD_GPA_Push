import os
import requests
import hashlib
from playwright.sync_api import sync_playwright

# --- 配置区 ---
USERNAME = os.environ.get('USERNAME')
PASSWORD = os.environ.get('PASSWORD')
SC_KEY = os.environ.get('SC_KEY')
TARGET_URL = os.environ.get('TARGET_URL')
LOGIN_URL = os.environ.get('LOGIN_URL', "https://ids.chd.edu.cn/authserver/login?service=http%3A%2F%2Fbkjw.chd.edu.cn%2Feams%2Fhome.action")

DATA_FILE = 'course_hashes.txt'
EXCLUDE_CATEGORIES = ["社会科学与公共责任", "科学探索与技术创新", "经典阅读与写作沟通"]

def send_wechat(title, content=""):
    if not SC_KEY: return
    url = f"https://sctapi.ftqq.com/{SC_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def get_md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def calculate_gpa(grade_list):
    total_credits_all = 0.0
    total_points_all = 0.0
    total_credits_filtered = 0.0
    total_points_filtered = 0.0

    for item in grade_list:
        try:
            c = float(item['credit'])
            p = float(item['point'])
            total_credits_all += c
            total_points_all += c * p
            
            if not any(ex in item['category'] for ex in EXCLUDE_CATEGORIES):
                total_credits_filtered += c
                total_points_filtered += c * p
        except (ValueError, TypeError):
            continue

    gpa_all = round(total_points_all / total_credits_all, 3) if total_credits_all > 0 else 0.0
    gpa_filtered = round(total_points_filtered / total_credits_filtered, 3) if total_credits_filtered > 0 else 0.0
    return gpa_all, gpa_filtered

def run_monitor():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print("🚀 正在登录...")
        page.goto(LOGIN_URL)
        page.fill('#username', USERNAME)
        page.fill('#password', PASSWORD)
        page.click('#login_submit')
        page.wait_for_load_state("networkidle")
        
        print(f"🎯 跳转成绩页: {TARGET_URL}")
        page.goto(TARGET_URL)
        
        # 1. 使用 Playwright 定位器等待数据加载
        data_table_selector = 'tbody[id$="_data"]'
        try:
            page.wait_for_selector(data_table_selector, timeout=20000)
        except Exception as e:
            print(f"❌ 等待表格超时: {e}")
            return

        # 2. 直接遍历行元素提取数据 (不使用 BeautifulSoup)
        rows = page.locator(f"{data_table_selector} tr").all()
        extracted_data = []

        for row in rows:
            # 获取该行下所有的 td 元素
            cols = row.locator("td").all_inner_texts()
            if len(cols) >= 13:
                item = {
                    "name": cols[3].strip(),
                    "category": cols[4].strip(),
                    "credit": cols[5].strip(),
                    "mid": cols[6].strip() or "-",    # 期中
                    "final": cols[7].strip() or "-",  # 期末
                    "usual": cols[8].strip() or "-",  # 平时
                    "total": cols[9].strip() or "-",  # 总评
                    "point": cols[12].strip() or "0"  # 绩点
                }
                extracted_data.append(item)

        browser.close()

        if not extracted_data:
            print("⚠️ 成绩单为空")
            return

        # 3. 差异比对逻辑
        known_hashes = set()
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                known_hashes = {line.strip() for line in f if line.strip()}

        new_items = []
        current_hashes = set()
        for item in extracted_data:
            h = get_md5(item['name'])
            current_hashes.add(h)
            if h not in known_hashes:
                new_items.append(item)

        # 4. 计算 GPA
        gpa_all, gpa_filtered = calculate_gpa(extracted_data)

        # 5. 推送逻辑
        if new_items:
            print(f"🔔 发现 {len(new_items)} 门新成绩！")
            
            # 更新指纹库
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                for h in current_hashes: f.write(f"{h}\n")

            # 构建详细消息
            new_grades_section = "### 🆕 新增详细成绩\n"
            for item in new_items:
                new_grades_section += (
                    f"**【{item['name']}】**\n"
                    f"- 绩点：`{item['point']}` | 学分：`{item['credit']}`\n"
                    f"- 组成：期中 `{item['mid']}` / 平时 `{item['usual']}` / 期末 `{item['final']}`\n"
                    f"- 总评：**{item['total']}**\n\n"
                )

            table_header = "\n### 📋 完整一览\n| 课程 | 总评 | 绩点 | 期末 |\n| :--- | :--- | :--- | :--- |\n"
            table_rows = ""
            for d in extracted_data:
                is_new = "🆕 " if get_md5(d['name']) not in known_hashes else ""
                table_rows += f"| {is_new}{d['name']} | {d['total']} | {d['point']} | {d['final']} |\n"

            # 第一次运行处理
            if len(known_hashes) == 0:
                title, head = "🚀 GPA服务初始化", "### ✅ 初始化成功\n"
            else:
                title, head = f"🎉 出分：{new_items[0]['name']}", ""

            full_content = (
                f"{head}{new_grades_section}"
                f"### 📈 实时统计\n"
                f"- **核心绩点: {gpa_filtered}**\n"
                f"- 总GPA: {gpa_all}\n"
                f"{table_header}{table_rows}"
            )
            send_wechat(title, full_content)
        else:
            print(f"😴 暂无更新。当前核心 GPA: {gpa_filtered}")

if __name__ == "__main__":
    run_monitor()
import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 配置区 ---
USERNAME = os.environ.get('USERNAME')
PASSWORD = os.environ.get('PASSWORD')
SC_KEY = os.environ.get('SC_KEY')
TARGET_URL = os.environ.get('TARGET_URL')
LOGIN_URL = os.environ.get('LOGIN_URL', "https://ids.chd.edu.cn/authserver/login?service=http%3A%2F%2Fbkjw.chd.edu.cn%2Feams%2Fhome.action")

# 改用 known_courses.txt 存储已出的课程名
DATA_FILE = 'known_courses.txt'
# 需要剔除计算 GPA 的课程类别
EXCLUDE_CATEGORIES = ["社会科学与公共责任", "科学探索与技术创新", "经典阅读与写作沟通"]

def send_wechat(title, content=""):
    """Server酱推送"""
    if not SC_KEY: return
    url = f"https://sctapi.ftqq.com/{SC_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def calculate_gpa(grade_list):
    """
    计算 GPA
    grade_list 格式: [(课程名, 类别, 学分, 绩点), ...]
    """
    total_credits_all = 0.0
    total_points_all = 0.0
    total_credits_filtered = 0.0
    total_points_filtered = 0.0

    for name, category, credit, point in grade_list:
        try:
            c = float(credit)
            p = float(point)
            
            # 1. 全口径统计
            total_credits_all += c
            total_points_all += c * p
            
            # 2. 核心课程统计（剔除指定类别）
            if not any(ex in category for ex in EXCLUDE_CATEGORIES):
                total_credits_filtered += c
                total_points_filtered += c * p
        except ValueError:
            continue

    gpa_all = round(total_points_all / total_credits_all, 3) if total_credits_all > 0 else 0.0
    gpa_filtered = round(total_points_filtered / total_credits_filtered, 3) if total_credits_filtered > 0 else 0.0
    
    return gpa_all, gpa_filtered

def get_html_via_playwright():
    """使用 Playwright 模拟登录并获取成绩页 HTML"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print("🚀 正在访问登录页面...")
        page.goto(LOGIN_URL)
        
        page.fill('#username', USERNAME)
        page.fill('#password', PASSWORD)
        page.click('#login_submit')
        
        page.wait_for_load_state("networkidle")
        
        print(f"🎯 正在跳转至成绩单页面: {TARGET_URL}")
        page.goto(TARGET_URL)
        
        try:
            page.wait_for_selector('tbody[id$="_data"]', timeout=20000)
            content = page.content()
            print("✅ 成功获取页面源码")
            return content
        except Exception as e:
            print(f"❌ 获取成绩表格超时或失败: {e}")
            return None
        finally:
            browser.close()

def check_and_push():
    try:
        # 1. 获取源码
        html_content = get_html_via_playwright()
        if not html_content: return

        # 2. 解析数据
        soup = BeautifulSoup(html_content, 'html.parser')
        grade_body = soup.find('tbody', id=lambda x: x and x.endswith('_data'))
        
        if not grade_body:
            print("❌ 解析失败：HTML 中未找到成绩数据体")
            return

        extracted_data = [] # 格式: (课程名, 类别, 学分, 绩点)
        rows = grade_body.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 13:
                name = cols[3].get_text(strip=True)
                category = cols[4].get_text(strip=True)
                credit = cols[5].get_text(strip=True)
                point = cols[12].get_text(strip=True)
                extracted_data.append((name, category, credit, point))

        if not extracted_data:
            print("⚠️ 成绩单为空")
            return

        # --- 核心修改逻辑开始 ---

        # 3. 读取本地已知的课程列表
        known_courses = set()
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                pass
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        known_courses.add(line.strip())        

        # 4. 构建当前课程字典 (方便查找数据)
        current_courses_dict = {item[0]: item for item in extracted_data}
        current_courses_set = set(current_courses_dict.keys())

        # 5. 计算差集：找出 "新出现的课程"
        new_courses_names = current_courses_set - known_courses

        # 6. 计算 GPA (无论是否有更新都算一下，用于展示)
        gpa_all, gpa_filtered = calculate_gpa(extracted_data)

        # 7. 判断推送逻辑
        if new_courses_names:
            print(f"🔔 发现 {len(new_courses_names)} 门新成绩！")
            
            # 更新本地文件
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                for name in current_courses_set:
                    f.write(f"{name}\n")

            # --- 构建推送消息 ---
            
            # A. 新成绩详情板块
            new_grades_msg = "### 🆕 本次更新\n"
            for name in new_courses_names:
                # 获取该课程的完整信息
                _, cat, cred, pt = current_courses_dict[name]
                # 绩点加粗逻辑
                pt_display = f"**{pt}**" if float(pt) >= 4.0 else pt
                new_grades_msg += f"- {name}: 绩点 {pt_display} (学分 {cred})\n"
            
            # B. 完整表格
            table_header = "\n### 📋 完整成绩单\n| 课程 | 类别 | 绩点 | 学分 |\n| :--- | :--- | :--- | :--- |\n"
            table_rows = ""
            for d in extracted_data:
                # 给新出的成绩行加个标记，或者保持原样
                is_new = "🆕 " if d[0] in new_courses_names else ""
                try:
                    p_display = f"**{d[3]}**" if float(d[3]) >= 4.0 else d[3]
                except:
                    p_display = d[3]
                table_rows += f"| {is_new}{d[0]} | {d[1]} | {p_display} | {d[2]} |\n"

            # C. 标题判断 (如果是第一次运行，或者没有旧数据)
            if len(known_courses) == 0:
                title = "🚀 CHD GPA推送：服务初始化"
                desc_start = "### ✅ 初始化完成\n已建立基准课程列表。\n\n"
            else:
                title = f"🎉 出分啦：{list(new_courses_names)[0]} 等"
                desc_start = ""

            # D. 组合最终消息
            content = (
                f"{desc_start}"
                f"{new_grades_msg}\n"
                f"### 📈 实时统计\n"
                f"- **核心绩点: {gpa_filtered}**\n"
                f"- 总GPA: {gpa_all}\n"
                f"{table_header}{table_rows}"
            )

            send_wechat(title, content)
            print("✅ 微信推送已发送")

        else:
            print(f"😴 监控中... 无新课程。核心 GPA: {gpa_filtered}")

    except Exception as e:
        print(f"❌ 程序运行错误: {e}")

if __name__ == "__main__":
    check_and_push()
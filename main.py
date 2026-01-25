import os
import hashlib
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- 配置区 ---
# 改为从环境变量读取账号密码，不再需要 COOKIE
USERNAME = os.environ.get('USERNAME')
PASSWORD = os.environ.get('PASSWORD')
SC_KEY = os.environ.get('SC_KEY')
TARGET_URL = os.environ.get('TARGET_URL')

# CAS 登录地址 (服务指向教务首页)
LOGIN_URL = os.environ.get('LOGIN_URL', "https://ids.chd.edu.cn/authserver/login?service=http%3A%2F%2Fbkjw.chd.edu.cn%2Feams%2Fhome.action")

HASH_FILE = 'last_hash.txt'
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
            # 使用 any() 检查当前课程类别是否包含在排除列表中
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
        # 生产环境使用 headless=True (无头模式)
        # 本地调试可改为 headless=False
        browser = p.chromium.launch(headless=True)
        # 设置较大的视口，防止网页布局压缩导致元素不可见
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print("🚀 正在访问登录页面...")
        page.goto(LOGIN_URL)
        
        # 填写账号密码
        # 注意：这里不判断是否存在输入框，直接填，因为每次 context 都是干净的
        page.fill('#username', USERNAME)
        page.fill('#password', PASSWORD)
        
        print("🖱️ 点击登录...")
        page.click('#login_submit')
        
        # 等待登录跳转完成 (networkidle 表示网络空闲，意味着加载完了)
        page.wait_for_load_state("networkidle")
        
        print(f"🎯 正在跳转至成绩单页面: {TARGET_URL}")
        page.goto(TARGET_URL)
        
        # 等待成绩表格加载出来 (id 以 _data 结尾的 tbody)
        try:
            page.wait_for_selector('tbody[id$="_data"]', timeout=20000)
            content = page.content()
            print("✅ 成功获取页面源码")
            return content
        except Exception as e:
            print(f"❌ 获取成绩表格超时或失败: {e}")
            # 可以截图保存方便 GitHub Actions Artifacts 查看
            # page.screenshot(path="error_screenshot.png")
            return None
        finally:
            browser.close()

def check_and_push():
    # 初始化 Hash 文件
    if not os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'w', encoding='utf-8') as f: f.write("")

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
            # 确保列数足够，防止解析表头或空行报错
            if len(cols) >= 13:
                name = cols[3].get_text(strip=True)
                category = cols[4].get_text(strip=True) # 类别在第5列
                credit = cols[5].get_text(strip=True)
                point = cols[12].get_text(strip=True)   # 绩点在第13列
                extracted_data.append((name, category, credit, point))

        if not extracted_data:
            print("⚠️ 成绩单为空")
            return

        # 3. 计算 GPA
        gpa_all, gpa_filtered = calculate_gpa(extracted_data)

        # 4. 生成哈希 (仅基于 课程名+绩点 判断变化)
        current_content = "".join([f"{d[0]}{d[3]}" for d in extracted_data])
        new_hash = hashlib.md5(current_content.encode('utf-8')).hexdigest()

        with open(HASH_FILE, 'r', encoding='utf-8') as f:
            last_hash = f.read().strip()

        # 5. 比对与推送
        if new_hash != last_hash:
            print("🔔 检测到成绩变动！")
            with open(HASH_FILE, 'w', encoding='utf-8') as f:
                f.write(new_hash)
            
            # 构建 Markdown 表格
            table_header = "| 课程 | 类别 | 绩点 | 学分 |\n| :--- | :--- | :--- | :--- |\n"
            table_rows = ""
            for d in extracted_data:
                # 高亮高分 (>= 4.0)
                try:
                    p_display = f"**{d[3]}**" if float(d[3]) >= 4.0 else d[3]
                except:
                    p_display = d[3]
                table_rows += f"| {d[0]} | {d[1]} | {p_display} | {d[2]} |\n"

            # 判断标题
            if last_hash == "":
                title = "🚀 CHD 监控：服务已激活"
                desc_start = "### ✅ 初始化成功\n系统已建立基准快照。\n\n"
            else:
                title = "🎉 长安大学：出新成绩了！"
                desc_start = "### 🚨 成绩更新检测\n发现成绩单发生变化！\n\n"

            # 组合最终消息
            content = (
                f"{desc_start}"
                f"### 📈 GPA 统计\n"
                f"- **核心绩点 (去水课): {gpa_filtered}**\n"
                f"- 全口径 GPA: {gpa_all}\n\n"
                f"### 📋 完整成绩单\n{table_header}{table_rows}"
            )

            send_wechat(title, content)
            print("✅ 微信推送已发送")
        else:
            print(f"😴 监控中... 无变动。核心 GPA: {gpa_filtered}")

    except Exception as e:
        print(f"❌ 程序运行错误: {e}")

if __name__ == "__main__":
    check_and_push()
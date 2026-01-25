import requests
import hashlib
import os
from bs4 import BeautifulSoup

# --- 从 GitHub Secrets 读取配置 ---
SC_KEY = os.environ.get('SC_KEY')
raw_cookie = os.environ.get('COOKIE') or ""
COOKIE = raw_cookie.replace('\n', '').replace('\r', '').strip()
TARGET_URL = os.environ.get('TARGET_URL')

HASH_FILE = 'last_hash.txt'
STATUS_FILE = 'cookie_status.txt'

def send_wechat(title, content=""):
    if not SC_KEY: return
    url = f"https://sctapi.ftqq.com/{SC_KEY}.send"
    # Server酱支持 Markdown 渲染
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"推送失败: {e}")

def calculate_gpa(grade_list):
    total_credits_all = 0.0
    total_points_all = 0.0
    total_credits_filtered = 0.0
    total_points_filtered = 0.0
    exclude_categories = ["社会科学与公共责任", "科学探索与技术创新", "经典阅读与写作沟通"]

    for name, category, credit, point in grade_list:
        try:
            c = float(credit)
            p = float(point)
            total_credits_all += c
            total_points_all += c * p
            if not any(ex in category for ex in exclude_categories):
                total_credits_filtered += c
                total_points_filtered += c * p
        except:
            continue
    gpa_all = total_points_all / total_credits_all if total_credits_all > 0 else 0
    gpa_filtered = total_points_filtered / total_credits_filtered if total_credits_filtered > 0 else 0
    return round(gpa_all, 3), round(gpa_filtered, 3)

def check_and_push():
    last_status = "valid"
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            last_status = f.read().strip()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        'Cookie': COOKIE,
        'Referer': TARGET_URL
    }

    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.encoding = 'utf-8'

        if "authserver/login" in response.url or "用户登录" in response.text:
            if last_status == "valid":
                send_wechat("⚠️ CHD 监控：Cookie 已失效", "> 请重新登录教务系统获取 Cookie 并更新 GitHub Secrets。")
                with open(STATUS_FILE, 'w') as f: f.write("expired")
            return

        if last_status == "expired":
            with open(STATUS_FILE, 'w') as f: f.write("valid")

        soup = BeautifulSoup(response.text, 'html.parser')
        grade_body = soup.find('tbody', id=lambda x: x and x.endswith('_data'))
        if not grade_body: return

        extracted_data = []
        rows = grade_body.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 13:
                name = cols[3].get_text(strip=True)
                category = cols[4].get_text(strip=True)
                credit = cols[5].get_text(strip=True)
                point = cols[12].get_text(strip=True)
                extracted_data.append((name, category, credit, point))

        gpa_all, gpa_filtered = calculate_gpa(extracted_data)
        current_content = "".join([f"{d[0]}{d[3]}" for d in extracted_data])
        new_hash = hashlib.md5(current_content.encode('utf-8')).hexdigest()

        last_hash = ""
        if os.path.exists(HASH_FILE):
            with open(HASH_FILE, 'r') as f: last_hash = f.read().strip()

        if new_hash != last_hash:
            with open(HASH_FILE, 'w') as f: f.write(new_hash)
            
            # 构建 Markdown 内容
            table_header = "| 课程名称 | 绩点 | 学分 | 课程类别 |\n| :--- | :--- | :--- | :--- |\n"
            table_rows = ""
            for d in extracted_data:
                p_val = d[3]
                try:
                    p_display = f"**{p_val}**" if float(p_val) >= 4.0 else p_val
                except:
                    p_display = p_val
                table_rows += f"| {d[0]} | {p_display} | {d[2]} | {d[1]} |\n"
            
            # 判断是【首次激活】还是【成绩更新】
            if last_hash == "":
                title = "🚀 CHD GPA监控：服务已成功激活！"
                content = f"### ✅ 监控启动成功\n> 系统已建立初始成绩快照，当前共有 **{len(extracted_data)}** 门课程。\n\n"
                content += f"### 📊 当前 GPA 统计\n- **核心绩点 (剔除类): {gpa_filtered}**\n- 全部科目 GPA: {gpa_all}\n\n"
                content += f"### 📚 初始成绩单快照\n{table_header}{table_rows}"
                content += "\n---\n*以后若有新成绩出炉，系统将自动推送变动。*"
            else:
                title = "🎉 长安大学：出新成绩了！"
                content = f"### 📊 GPA 统计更新\n- **核心绩点 (剔除类): {gpa_filtered}**\n- 全部科目 GPA: {gpa_all}\n\n"
                content += f"### 📚 最新成绩单\n{table_header}{table_rows}"

            send_wechat(title, content)
            print("推送已发送。")
        else:
            print(f"监控中... 无变动。当前 GPA: {gpa_filtered}")

    except Exception as e:
        print(f"运行出错: {e}")

if __name__ == "__main__":
    check_and_push()
# 🎓 CHD 成绩自动监控与推送 (CHD Grade Monitor)

基于 **GitHub Actions** 和 **Playwright** 的长安大学教务系统成绩监控脚本。

当新成绩发布时，自动计算最新 GPA 并通过微信（Server酱）推送详细的成绩变动通知。

---

## ✨ 功能特性

* **☁️ 云端运行**：利用 GitHub Actions 定时任务，无需本地挂机，完全免费。
* **🚀 自动登录**：使用 Playwright 模拟浏览器行为，自动处理 CAS 统一身份认证。
* **🔔 精准推送**：不再只是提示“有变化”，而是**直接告诉你哪门课出了成绩**，以及该课程的绩点和学分；推送期中成绩、期末成绩、平时成绩 以及 总评/绩点，全方位掌握得分详情。
* **📊 GPA 统计**：
    * **全GPA**：所有课程的平均绩点。
    * **核心GPA**：自动剔除“社会科学与公共责任”、“科学探索与技术创新”等选修类别后的绩点（可自定义）。
* **📝 状态同步**：通过 Git 自动维护 `known_courses.txt`，防止重复推送旧成绩。

## 🛠️ 快速部署

### 1. Fork 本仓库
点击右上角的 **Fork** 按钮，将本项目克隆到你自己的 GitHub 账号下。(首次使用时删除course_hashes.txt)

### 2. 配置环境变量 (Secrets)
进入你 Fork 后的仓库，点击 **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**，添加以下变量：

| Secret Name | 必填 | 描述 |
| :--- | :--- | :--- |
| `USERNAME` | ✅ | 教务系统/信息门户学号 |
| `PASSWORD` | ✅ | 登录密码 |
| `SC_KEY` | ✅ | Server酱 SendKey (用于微信推送，[获取地址](https://sct.ftqq.com/)) |
| `TARGET_URL` | ✅ | 成绩单页面的具体 URL |
| `LOGIN_URL` | ❌ | (可选) 登录页面的 URL，默认为 CHD 统一认证登录页 |

### 3. 启用 Workflow
1.  点击仓库上方的 **Actions** 标签。
2.  如果不显示绿色按钮，点击左侧的 `CHD_GPA_MONITOR`。
3.  你可以手动点击 **Run workflow** 进行第一次测试（初始化）。
4.  点击仓库上方的 **Settings** 标签。
5.  点击**Actions** 标签，并选择 **General**。
6.  将**Workflow permissions**设置为 **Read and write permissions**

## ⚙️ 运行逻辑

1.  **定时触发**：默认每 20 分钟运行一次（可在 `.github/workflows/main.yml` 中修改 `cron` 表达式）。
2.  **获取数据**：脚本模拟登录教务系统，抓取当前所有成绩。
3.  **比对差异**：
    * 脚本读取仓库中的 `known_courses.txt`。
    * 计算 **(当前抓取课程 - 已知课程)** 的差集。
4.  **推送通知**：
    * **如果有新课程**：计算 GPA，生成包含新课程详情的消息，通过 Server酱推送，并更新 `known_courses.txt`。
    * **如果无变化**：静默退出，不打扰。

## 🖥️ 本地开发/调试

如果你想在本地运行代码：

1.  安装依赖：
    ```bash
    pip install playwright requests
    playwright install chromium
    ```
2.  设置环境变量（推荐使用 `.env` 或直接在终端 export）：
    ```bash
    export USERNAME="你的学号"
    export PASSWORD="你的密码"
    export SC_KEY="你的Server酱Key"
    ```
3.  运行脚本：
    ```bash
    python main.py
    ```

## ⚠️ 免责声明

* 本项目仅供学习交流使用，**请勿用于任何商业用途**。
* 脚本模拟用户正常登录行为，频率较低（默认20分钟一次），不会对教务系统造成压力，但请勿恶意修改为高频请求。
* 使用本项目产生的任何后果（如账号风险等）由使用者自行承担。
* 请妥善保管你的 GitHub 仓库及 Secrets，防止个人信息泄露。

---

**License**: MIT

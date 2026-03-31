# IPv6 Notifier 脚本工具

这是一个轻量级的跨平台（针对 Windows 优化）的命令行工具，当 Windows PC 连接到网络时，能够自动获取本机分配的公网 IPv6 地址，并通过电子邮件推送到指定的收件箱。

---

## 整体架构设计

该工具基于 **事件触发驱动** 模型设计，架构包含三个核心层：

1. **触发层 (Trigger Layer)**：
   利用 Windows 系统自带的 **任务计划程序 (Task Scheduler)**。通过监听 Windows 的系统事件（如网络连接事件 `Event ID 10000` / `NetworkProfile`），当系统侦测到网络连接状态变更时，触发脚本运行。这种方式无须常驻后台运行，资源占用极低。
2. **逻辑层 (Logic Layer)**：
   由 Python 编写的核心脚本 (`ipv6_notifier.py`) 构成。启动后，脚本会读取配置文件，并通过网络接口抓取本机当前的公网 IPv6 地址。同时脚本会在本地文件 (`.last_ipv6`) 中缓存上一次发送的 IP 地址，**仅在 IP 发生变更时**才执行发送操作，避免邮箱被垃圾邮件填满。
3. **通知层 (Notification Layer)**：
   基于 Python 标准库 `smtplib` 和 `email` 模块，通过 SMTP/SMTP_SSL 协议加密连接至邮件服务商（如 QQ、网易、Gmail等），构建标准的 MIMEText 格式邮件，将获取到的 IPv6 地址推送到指定接收人。

---

## 地址获取方式

公网 IPv6 地址的获取采用了 **主备结合** 的双重保障方案：

1. **主要方案：外部 API 反向探测（优先使用）**
   脚本通过向提供 IP 检测服务的公网 API 发起 HTTPS GET 请求：
   - `https://v6.ident.me`
   - `https://api6.ipify.org`
   **优势**：由于 Windows 可能会为一个网卡分配多个 IPv6 地址（包括临时 IPv6、内网本地链路地址 `fe80::` 等），直接读取本地网卡配置解析起来非常复杂。通过外部 API 获取的，一定是能够与外界进行真实数据交换的 **真实出口公网 IPv6**。
   
2. **备用方案：UDP Socket 路由表查询**
   如果外部 API 访问受限，脚本会利用 `socket` 模块创建一个 UDP 连接，尝试连接 Google 的 IPv6 DNS (`2001:4860:4860::8888`)。此操作并不会真正发送数据，仅利用操作系统的网络栈和路由表来返回用于连接外部的本地接口 IPv6。
   **优势**：不依赖外部 Web 服务即可推断出出口 IP。

---

## 邮箱推送方案

基于 SMTP (Simple Mail Transfer Protocol) 构建的邮件推送：
- **安全传输**：默认使用端口 465 建立 SSL/TLS 加密通道 (`SMTP_SSL`)，防止密码及网络信息被中间人截获。
- **免依赖性**：仅使用了 Python 自带的 `smtplib`，不需要安装如 `yagmail` 等第三方库。
- **身份认证**：目前主流邮箱（如 QQ邮箱、网易邮箱）不再允许直接使用密码登录 SMTP，需要用户在邮箱设置中开启 SMTP 服务并生成**授权码**作为密码填入。

---

## 自动部署指南

下载 release 中 ipv6_notifier.exe 输入 config 后一键部署。

## 手动部署指南

### 步骤 1：环境准备与测试
1. 确保 Windows PC 安装了 [Python 3.6+](https://www.python.org/downloads/)。
2. 下载本项目的代码：
   - `ipv6_notifier.py`
   - `config.sample.json`
3. 复制 `config.sample.json` 并重命名为 `config.json`。
4. 编辑 `config.json`，填入你的邮箱信息：
   ```json
   {
       "smtp_server": "smtp.qq.com",      // 你的发件服务器 (QQ示例)
       "smtp_port": 465,                  // SSL 端口
       "smtp_user": "your_email@qq.com",  // 发件人邮箱
       "smtp_pass": "邮箱授权码",         // 邮箱获取的授权码，而非登录密码
       "receiver": "your_target@163.com"  // 接收通知的邮箱地址
   }
   ```
5. **手动测试演示**：
   打开 CMD 或 PowerShell，运行：
   ```cmd
   python ipv6_notifier.py -f
   ```
   *参数 `-f` 代表强制发送邮件，忽略本地的 IP 变更检测。*
   此时去你的接收邮箱检查是否收到了包含 IPv6 的邮件。

### 步骤 2：配置 Windows 任务计划程序 (开机及网络连接时触发)
为实现“连接到网络时自动推送”，我们需要借助 Windows 任务计划程序。

1. **打开任务计划程序**：
   按下 `Win + R` 键，输入 `taskschd.msc`，回车。
2. **创建基本任务**：
   在右侧点击 **"创建任务..."** (注意：不是基本任务，以便有更高级的触发器配置)。
3. **常规设置**：
   - 名称填写：`IPv6 Auto Notifier`。
   - 勾选 **“不管用户是否登录都要运行”** 和 **“使用最高权限运行”**。
4. **触发器设置 (核心)**：
   - 点击 **"新建"**。
   - **触发器类型 1：系统启动时**
     开始任务选择 **“启动时”**。
   - **触发器类型 2：发生网络事件时**
     开始任务选择 **“发生事件时”**。
     - 日志：`Microsoft-Windows-NetworkProfile/Operational`
     - 源：`NetworkProfile`
     - 事件 ID：`10000` (该事件代表成功连接到了一个网络)。
5. **操作设置**：
   - 点击 **"新建"**。
   - 操作：`启动程序`。
   - 程序或脚本：填写 `pythonw.exe` 的完整路径（例如 `C:\Python39\pythonw.exe`，如果不确定路径，可以填 `pythonw`，但为了稳定性推荐绝对路径）。
   - 添加参数：填入你脚本的**绝对路径**，建议用英文双引号包裹（例如 `"C:\Users\YourName\ipv6-notifier\ipv6_notifier.py"`）。
   - 起始于：填入脚本所在目录，**千万不要带引号，也不要以反斜杠 \ 结尾**（例如填入 `C:\Users\YourName\ipv6-notifier`，不要写成 `C:\Users\YourName\ipv6-notifier\`）。
6. **条件设置**：
   - 勾选 **“只有在以下网络连接可用时才启动”** -> 选择 **“任何连接”**。
7. **保存并测试**：
   - 点击确认并输入 Windows 账号密码保存任务。
   - 你可以尝试断开 WiFi 并重新连接，或者插拔网线，稍等片刻，观察是否能收到邮件推送。

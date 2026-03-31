import urllib.request
import urllib.error
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import json
import os
import sys
import argparse
import socket
import logging
import subprocess
import tempfile
import ctypes

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_ipv6_external():
    api_urls = [
        "https://v6.ident.me",
        "https://api6.ipify.org",
        "https://ipv6.icanhazip.com"
    ]
    for url in api_urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                if ":" in ip:
                    return ip
        except urllib.error.URLError:
            continue
    return None

def get_ipv6_socket():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(("2001:4860:4860::8888", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        return None

def send_email(config, ipv6_addr):
    sender = config.get("smtp_user")
    receiver = config.get("receiver")
    subject = f"【网络通知】Windows PC 的新 IPv6 地址: {ipv6_addr}"
    
    body = f"""
    您好：
    
    检测到您的 Windows PC 获得了新的公网 IPv6 地址。
    当前 IPv6 地址：{ipv6_addr}
    
    （此邮件由自动化脚本 ipv6_notifier 发送，请勿回复）
    """
    
    message = MIMEText(body, 'plain', 'utf-8')
    message['From'] = formataddr((str(Header("IPv6 Notifier", 'utf-8')), sender))
    message['To'] = receiver
    message['Subject'] = Header(subject, 'utf-8')
    
    try:
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 465)
        smtp_pass = config.get("smtp_pass")
        
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.starttls()
            
        server.login(sender, smtp_pass)
        server.sendmail(sender, [receiver], message.as_string())
        server.quit()
        logging.info("邮件发送成功！")
        return True
    except Exception as e:
        logging.error(f"邮件发送失败: {e}")
        return False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def create_scheduled_task(work_dir):
    if not is_admin():
        print("【错误】创建计划任务需要管理员权限！")
        print("请关闭本窗口，右键点击该 .exe 文件，选择【以管理员身份运行】。")
        return False

    if getattr(sys, 'frozen', False):
        command = sys.executable
        arguments = "--run"
    else:
        command = sys.executable
        arguments = f'"{os.path.abspath(__file__)}" --run'

    # 使用 Windows 任务计划程序 XML 配置模板，设置最高权限和隐藏运行
    xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>自动获取并推送公网 IPv6 地址</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="Microsoft-Windows-NetworkProfile/Operational"&gt;&lt;Select Path="Microsoft-Windows-NetworkProfile/Operational"&gt;*[System[Provider[@Name='NetworkProfile'] and EventID=10000]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <RunLevel>HighestAvailable</RunLevel>
      <UserId>S-1-5-18</UserId> <!-- SYSTEM 账号运行，实现完全静默 -->
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
      <WorkingDirectory>{work_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    fd, temp_xml = tempfile.mkstemp(suffix=".xml")
    with os.fdopen(fd, 'w', encoding='utf-16') as f:
        f.write(xml_content)

    try:
        # 删除旧任务（如果存在）
        subprocess.call(['schtasks', '/delete', '/tn', 'IPv6 Auto Notifier', '/f'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 导入新任务
        subprocess.run(['schtasks', '/create', '/tn', 'IPv6 Auto Notifier', '/xml', temp_xml], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("【成功】计划任务创建成功！程序将在开机和网络连接时自动后台静默运行。")
        return True
    except subprocess.CalledProcessError as e:
        print(f"【失败】计划任务创建失败。")
        return False
    finally:
        os.remove(temp_xml)

def interactive_setup(base_dir):
    print("="*50)
    print("     IPv6 Notifier 一键部署向导")
    print("="*50)
    
    if not is_admin():
        print("【警告】当前没有管理员权限！无法自动配置任务计划程序。")
        print("请关闭本窗口，然后右键点击本程序 ->【以管理员身份运行】。")
        input("\n按回车键退出...")
        sys.exit(1)

    print("\n[1/2] 正在配置邮箱信息...")
    smtp_server = input("请输入 SMTP 服务器地址 [默认 smtp.qq.com]: ").strip() or "smtp.qq.com"
    smtp_port = input("请输入 SMTP 端口 [默认 465]: ").strip() or "465"
    smtp_user = input("请输入发件人邮箱 (如 xxx@qq.com): ").strip()
    if not smtp_user:
        print("【错误】发件人邮箱不能为空！")
        input("\n按回车键退出...")
        sys.exit(1)
        
    smtp_pass = input("请输入邮箱授权码 (非登录密码): ").strip()
    receiver = input("请输入收件人邮箱 [默认与发件人相同]: ").strip() or smtp_user

    config = {
        "smtp_server": smtp_server,
        "smtp_port": int(smtp_port),
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
        "receiver": receiver
    }

    config_path = os.path.join(base_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"【成功】配置已保存至: {config_path}")

    print("\n[2/2] 正在自动配置 Windows 任务计划程序...")
    create_scheduled_task(base_dir)

    print("\n" + "="*50)
    print("部署已全部完成！您可以将此 .exe 文件放在任意安全的位置。")
    print("系统会在网络变化时自动在后台获取并发送 IPv6 地址。")
    print("="*50)
    input("按回车键退出...")
    sys.exit(0)

def main():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="获取并推送本机的公网IPv6地址到指定邮箱。")
    parser.add_argument("-c", "--config", default="config.json", help="指定配置文件名 (默认: config.json)")
    parser.add_argument("-f", "--force", action="store_true", help="强制发送邮件，即使IP未发生改变")
    parser.add_argument("--run", action="store_true", help="静默运行模式(由任务计划程序调用)")
    args = parser.parse_args()

    # 如果没有任何参数（即用户直接双击运行 exe），进入一键部署模式
    if not args.run and not args.force and len(sys.argv) == 1:
        interactive_setup(base_dir)
        return

    config_path = os.path.join(base_dir, args.config)
    if not os.path.exists(config_path):
        logging.error(f"找不到配置文件: {config_path}")
        sys.exit(1)
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        logging.error(f"解析配置文件失败: {e}")
        sys.exit(1)

    ipv6_addr = get_ipv6_external()
    if not ipv6_addr:
        ipv6_addr = get_ipv6_socket()

    if not ipv6_addr:
        logging.error("无法获取到 IPv6 地址，可能是当前网络不支持 IPv6。退出。")
        sys.exit(1)

    cache_file = os.path.join(base_dir, ".last_ipv6")
    last_ip = ""
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            last_ip = f.read().strip()
            
    if last_ip == ipv6_addr and not args.force:
        logging.info(f"IPv6 地址未发生变化 ({ipv6_addr})，跳过发送邮件。")
        sys.exit(0)

    if send_email(config, ipv6_addr):
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(ipv6_addr)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeBest 自动化全栈启动脚本 (跨平台版)
自动初始化环境，启动 WeBest Web 后端，并提供友好的提示。
"""

import os
import sys
import platform
import subprocess
import time
import shutil
import socket

DEFAULT_OPENCODE_SERVER_URL = "http://127.0.0.1:4096"
DEFAULT_OPENCODE_PROVIDER_ID = "zhipuai-coding-plan"
DEFAULT_OPENCODE_MODEL_ID = "glm-5-turbo"

WINDOWS_CREATION_FLAGS = 0
if os.name == "nt":
    WINDOWS_CREATION_FLAGS = (
        subprocess.CREATE_NEW_PROCESS_GROUP |
        subprocess.DETACHED_PROCESS
    )

def print_banner():
    print("=" * 60)
    print("    WeBest 启动向导       ")
    print("=" * 60)

def ensure_dirs(project_root):
    """确保日志等必要目录存在"""
    dirs = [
        os.path.join(project_root, "server", "domain-admin-master", "logs"),
        os.path.join(project_root, "all4win", "logs"),
        os.path.join(project_root, "all4win", "output")
    ]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)

def is_port_open(port, host="127.0.0.1", timeout=1.0):
    """检查端口是否已监听"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def wait_for_port(port, host="127.0.0.1", max_wait=15.0, interval=0.5):
    """轮询等待端口可用，避免启动稍慢时被误判失败"""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if is_port_open(port, host=host, timeout=1.0):
            return True
        time.sleep(interval)
    return False

def stop_process_by_port(port):
    """停止指定端口上的旧进程，避免继续跑旧代码"""
    system = platform.system().lower()
    try:
        if system == "windows":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                check=False,
            )
            pids = set()
            for line in result.stdout.splitlines():
                line = line.strip()
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pids.add(parts[-1])
            for pid in pids:
                subprocess.run(
                    ["taskkill", "/PID", pid, "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
        else:
            subprocess.run(
                ["pkill", "-f", f":{port}"],
                capture_output=True,
                text=True,
                check=False,
            )
    except Exception as e:
        print(f"[!] 清理端口 {port} 旧进程失败: {e}")

def can_import_module(command_prefix, module_name, cwd):
    """检查某个 python 命令是否可用并能导入指定模块"""
    try:
        result = subprocess.run(
            command_prefix + ["-c", f"import {module_name}; print('ok')"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False

def choose_backend_python(server_dir):
    """选择可用的 Python 解释器，确保能导入 waitress"""
    candidates = []
    if sys.executable:
        candidates.append([sys.executable])

    python_from_path = shutil.which("python")
    if python_from_path:
        candidates.append([python_from_path])

    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append([py_launcher, "-3"])

    seen = set()
    for cmd in candidates:
        key = tuple(cmd)
        if key in seen:
            continue
        seen.add(key)
        if can_import_module(cmd, "waitress", server_dir):
            return cmd

    raise RuntimeError("未找到可用的 Python 解释器或 waitress 未安装")


def normalize_opencode_server_url():
    """
    OpenCode SDK 必须连接 OpenCode Server，而不是 Anthropic 兼容地址。
    """
    current = (os.environ.get("OPENCODE_SERVER_URL") or "").strip()
    if not current:
        current = DEFAULT_OPENCODE_SERVER_URL
        print(f"[*] 未检测到 OPENCODE_SERVER_URL，已使用默认值: {current}")

    lowered = current.lower()
    if "open.bigmodel.cn/api/anthropic" in lowered:
        print("[!] 检测到 OPENCODE_SERVER_URL 指向 Anthropic 兼容地址，已自动切换为 OpenCode Server")
        current = DEFAULT_OPENCODE_SERVER_URL

    if not (current.startswith("http://") or current.startswith("https://")):
        current = "http://" + current

    os.environ["OPENCODE_SERVER_URL"] = current
    print(f"[*] 当前 OPENCODE_SERVER_URL: {current}")


def ensure_opencode_provider_config():
    """
    使用本机已配置的智谱 Coding Plan provider：
    - provider: zhipuai-coding-plan
    - model: glm-5-turbo
    """
    os.environ["OPENCODE_PROVIDER_ID"] = DEFAULT_OPENCODE_PROVIDER_ID
    os.environ["OPENCODE_ANTHROPIC_MODEL"] = DEFAULT_OPENCODE_MODEL_ID
    print(f"[*] OpenCode provider: {DEFAULT_OPENCODE_PROVIDER_ID}/{DEFAULT_OPENCODE_MODEL_ID}")


def start_opencode_server(project_root):
    """启动 OpenCode Server（端口 4096）"""
    print("\n[*] 正在启动 OpenCode Server (端口 4096)...")
    try:
        stop_process_by_port(4096)
        log_dir = os.path.join(project_root, "server", "domain-admin-master", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = open(os.path.join(log_dir, "opencode-server.log"), "a", encoding="utf-8")
        cmd = ["opencode", "serve", "--hostname", "127.0.0.1", "--port", "4096"]
        subprocess.Popen(
            cmd,
            cwd=project_root,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=WINDOWS_CREATION_FLAGS if os.name == "nt" else 0,
        )
        if wait_for_port(4096, max_wait=20):
            print("[√] OpenCode Server 已启动！(日志: server/domain-admin-master/logs/opencode-server.log)")
        else:
            raise RuntimeError("OpenCode Server 启动后未监听 4096 端口")
    except Exception as e:
        print(f"[!] 启动 OpenCode Server 失败: {e}")
        print("[!] 你也可以手动执行：opencode serve --hostname 127.0.0.1 --port 4096")

def start_server(project_root):
    """启动 WeBest Web Server"""
    server_dir = os.path.join(project_root, "server", "domain-admin-master")
    os.chdir(server_dir)
    
    # 忽略 Python 生成的 pyc 缓存文件
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    
    print("\n[*] 正在启动 WeBest 后端服务 (端口 8000)...")
    
    system = platform.system().lower()
    
    try:
        stop_process_by_port(8000)
        python_cmd = choose_backend_python(server_dir)
        if system == "windows":
            # Windows 下直接后台启动 waitress，避免 start/cmd 引发的进程与端口检测问题
            log_file = open(os.path.join(server_dir, "logs", "server.log"), "a", encoding="utf-8")
            cmd = python_cmd + ["-m", "waitress", "--port=8000", "domain_admin.main:app"]
            subprocess.Popen(
                cmd,
                cwd=server_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=WINDOWS_CREATION_FLAGS,
            )
            if wait_for_port(8000, max_wait=15):
                print("[√] 服务已在后台启动！(日志: server/domain-admin-master/logs/server.log)")
            else:
                raise RuntimeError("后端服务启动后未监听 8000 端口")
        else:
            # Linux / Mac 下使用 gunicorn，并在后台运行
            cmd = python_cmd + ["-m", "gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "domain_admin.main:app"]
            log_file = open("logs/server.log", "w")
            subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
            if wait_for_port(8000, max_wait=15):
                print("[√] 服务已在后台启动！(日志: server/domain-admin-master/logs/server.log)")
            else:
                raise RuntimeError("后端服务启动后未监听 8000 端口")
            
    except Exception as e:
        print(f"[!] 启动服务失败: {e}")
        sys.exit(1)

def start_frontend(project_root):
    """启动 WeBest Vue 前端"""
    frontend_dir = os.path.join(project_root, "frontend")
    if not os.path.exists(frontend_dir):
        return
        
    print("\n[*] 正在启动 WeBest 前端服务 (端口 3000)...")
    os.chdir(frontend_dir)
    
    system = platform.system().lower()
    try:
        stop_process_by_port(3000)
        if system == "windows":
            log_dir = os.path.join(frontend_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = open(os.path.join(log_dir, "frontend.log"), "a", encoding="utf-8")
            cmd = ["npm", "run", "dev"]
            subprocess.Popen(
                cmd,
                cwd=frontend_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=WINDOWS_CREATION_FLAGS,
                shell=True,
            )
            if wait_for_port(3000, max_wait=20):
                print("[√] 前端服务已在后台启动！(日志: frontend/logs/frontend.log)")
            else:
                print("[!] 前端进程已拉起，但 3000 端口暂未就绪，请查看 frontend/logs/frontend.log")
        else:
            cmd = ["npm", "run", "dev"]
            log_file = open("logs/frontend.log", "w") if os.path.exists("logs") else open(os.devnull, "w")
            subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
            print("[√] 前端服务已在后台启动！")
            
    except Exception as e:
        print(f"[!] 启动前端服务失败: {e}")

def print_instructions():
    print("\n" + "=" * 60)
    print("  如何使用自动化资产管线 (Hunter采集 -> 入库 -> DeepSeek分类)")
    print("=" * 60)
    print("您可以通过调用刚才新增的自动化接口，一键完成所有工作：\n")
    print("【方法】：发起 API 请求")
    print("POST http://127.0.0.1:8000/api/triggerFullAssetPipeline")
    print("Content-Type: application/json")
    print('Body: { "icp_keyword": "您的ICP备案号", "limit": 100 }')
    print("\n后台服务将自动依次执行：")
    print("  1. 调用 Hunter API 查询并拉取资产，完成去重与去蜜罐等清洗")
    print("  2. 将清洗后的 CSV 资产无缝导入到 WeBest 数据库")
    print("  3. 唤起 DeepSeek，从数据库读取资产，执行战术分类并回写结果")
    print("=" * 60)

def main():
    project_root = os.path.abspath(os.path.dirname(__file__))
    os.chdir(project_root)
    
    print_banner()
    ensure_dirs(project_root)
    normalize_opencode_server_url()
    ensure_opencode_provider_config()
    start_opencode_server(project_root)
    start_server(project_root)
    start_frontend(project_root)
    
    # 留给服务启动的时间
    time.sleep(2)
    print_instructions()
    print("\n[👉] 请在浏览器中访问前端界面: http://localhost:3000")
    print("[👉] 默认账号:   密码:")

if __name__ == "__main__":
    main()

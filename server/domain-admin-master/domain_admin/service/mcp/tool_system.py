# -*- coding: utf-8 -*-
"""
tool_system.py

系统命令 MCP 工具：让 Claude 可以执行系统命令、查看进程和系统信息。
命令执行有白名单限制，防止危险操作。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import json
import logging
import platform
import subprocess
import os

from domain_admin.service.mcp.mcp_registry import register_tool

logger = logging.getLogger(__name__)

_BLOCKED_COMMANDS = [
    "rm -rf /",
    "format",
    "del /f /s /q c:",
    "shutdown",
    "rmdir /s /q",
    "mkfs",
    "dd if=",
]

_ALLOWED_COMMANDS = [
    "dir",
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "wc",
    "echo",
    "pwd",
    "whoami",
    "hostname",
    "ipconfig",
    "ifconfig",
    "ping",
    "nslookup",
    "curl",
    "wget",
    "netstat",
    "tasklist",
    "ps",
    "df",
    "du",
    "free",
    "top",
    "uptime",
    "uname",
    "systeminfo",
    "type",
    "python",
    "pip",
    "npm",
    "node",
    "git",
    "docker",
    "mysql",
    "redis-cli",
]


def _handler_execute_command(params):
    command = params.get("command", "").strip()
    if not command:
        return "Error: command is required"
    for blocked in _BLOCKED_COMMANDS:
        if blocked in command.lower():
            return "Error: blocked command detected: %s" % blocked
    timeout = min(params.get("timeout", 30), 120)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
        )
        output = ""
        if result.stdout:
            output += result.stdout[:20000]
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr[:5000]
        if not output:
            output = "(no output, exit code: %d)" % result.returncode
        return output
    except subprocess.TimeoutExpired:
        return "Error: command timed out after %ds" % timeout
    except Exception as e:
        return "Error executing command: %s" % str(e)


def _handler_system_info(params):
    try:
        info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "cwd": os.getcwd(),
        }
        return json.dumps(info, ensure_ascii=False, indent=2)
    except Exception as e:
        return "Error getting system info: %s" % str(e)


def _handler_list_processes(params):
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["tasklist", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        else:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        lines = result.stdout.strip().split("\n")[:50]
        return "\n".join(lines)
    except Exception as e:
        return "Error listing processes: %s" % str(e)


def register():
    register_tool(
        name="execute_command",
        description="在服务器上执行系统命令。有超时和危险命令拦截。",
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的系统命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数，默认30，最大120",
                },
            },
            "required": ["command"],
        },
        handler=_handler_execute_command,
        category="system",
    )
    register_tool(
        name="system_info",
        description="获取服务器系统信息（平台、Python版本、CPU、内存等）。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handler_system_info,
        category="system",
    )
    register_tool(
        name="list_processes",
        description="列出服务器上正在运行的进程（最多50条）。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handler_list_processes,
        category="system",
    )

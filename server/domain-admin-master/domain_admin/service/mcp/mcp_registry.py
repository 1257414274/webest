# -*- coding: utf-8 -*-
"""
mcp_registry.py

MCP 工具注册中心：统一管理所有 MCP 工具的注册、发现、健康检查。
每个 MCP 工具遵循 Anthropic tool_use 规范，提供 name / description / input_schema / handler。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import logging
import time
import threading

logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()
_tools = {}
_tool_health = {}


def register_tool(name, description, input_schema, handler, category="general"):
    """
    注册一个 MCP 工具到全局注册中心。

    :param name: 工具唯一名称（与 Anthropic tool name 一致）
    :param description: 工具描述（会发给 Claude）
    :param input_schema: JSON Schema 格式的参数定义
    :param handler: 可调用对象，接收 dict 参数，返回 str 结果
    :param category: 工具分类标签
    """
    with _registry_lock:
        _tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "handler": handler,
            "category": category,
            "registered_at": time.time(),
        }
        _tool_health[name] = {
            "call_count": 0,
            "error_count": 0,
            "last_call_at": None,
            "last_error": None,
            "last_latency_ms": None,
        }
    logger.info("MCP tool registered: %s [%s]", name, category)


def get_tool(name):
    """获取单个工具定义"""
    return _tools.get(name)


def list_tools(category=None):
    """列出所有已注册工具，可按分类过滤"""
    tools = list(_tools.values())
    if category:
        tools = [t for t in tools if t["category"] == category]
    return tools


def get_anthropic_tools(category=None):
    """
    返回 Anthropic messages.create 所需的 tools 参数格式。
    即 [{"name": ..., "description": ..., "input_schema": ...}, ...]
    """
    tools = list_tools(category)
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"],
        }
        for t in tools
    ]


def call_tool(name, params):
    """
    调用指定工具并记录健康指标。

    :param name: 工具名称
    :param params: 工具参数 dict
    :return: str 工具执行结果
    """
    tool = _tools.get(name)
    if not tool:
        raise ValueError("MCP tool not found: %s" % name)

    health = _tool_health.get(name, {})
    t0 = time.time()
    try:
        result = tool["handler"](params)
        elapsed_ms = (time.time() - t0) * 1000
        health["call_count"] += 1
        health["last_call_at"] = time.time()
        health["last_latency_ms"] = round(elapsed_ms, 2)
        return str(result)
    except Exception as e:
        health["error_count"] += 1
        health["last_error"] = str(e)
        health["last_call_at"] = time.time()
        logger.error("MCP tool '%s' execution failed: %s", name, e)
        raise


def get_health_status():
    """返回所有工具的健康状态快照"""
    with _registry_lock:
        status = {}
        for name, info in _tool_health.items():
            tool = _tools.get(name, {})
            status[name] = {
                "category": tool.get("category", "unknown"),
                "call_count": info["call_count"],
                "error_count": info["error_count"],
                "error_rate": round(
                    info["error_count"] / max(1, info["call_count"]), 4
                ),
                "last_call_at": info["last_call_at"],
                "last_error": info["last_error"],
                "last_latency_ms": info["last_latency_ms"],
            }
        return status


def tool(name, description, input_schema, category="general"):
    """
    装饰器方式注册 MCP 工具。

    @tool("my_tool", "desc", {"type":"object","properties":{}})
    def my_handler(params):
        return "result"
    """

    def decorator(func):
        register_tool(name, description, input_schema, func, category)
        return func

    return decorator

# -*- coding: utf-8 -*-
"""
mcp_loader.py

MCP 工具自动加载入口。导入此模块即自动注册所有内置 MCP 工具。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import logging
import os

logger = logging.getLogger(__name__)

_loaded = False


def load_all():
    global _loaded
    if _loaded:
        return
    try:
        from domain_admin.service.mcp import (
            tool_filesystem,
            tool_database,
            tool_browser,
            tool_system,
            tool_api,
        )

        enabled = os.getenv("MCP_ENABLED_TOOLS", "").strip().lower()
        enabled_set = {x.strip() for x in enabled.split(",") if x.strip()} if enabled else set()

        def should_load(name):
            return not enabled_set or name in enabled_set

        if should_load("filesystem"):
            tool_filesystem.register()
        if should_load("database"):
            tool_database.register()
        if should_load("browser"):
            tool_browser.register()
        if should_load("system"):
            tool_system.register()
        if should_load("api"):
            tool_api.register()

        _loaded = True
        logger.info("All MCP tools loaded successfully")
    except Exception as e:
        logger.error("Failed to load MCP tools: %s", e)


def is_loaded():
    return _loaded

# -*- coding: utf-8 -*-
"""
tool_filesystem.py

文件系统 MCP 工具：让 Claude 可以读取文件、列出目录、搜索文件内容。
所有操作限制在项目根目录内，防止越权访问。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import os
import json
import logging

from domain_admin.service.mcp.mcp_registry import register_tool

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
)


def _safe_path(path):
    resolved = os.path.abspath(os.path.join(_PROJECT_ROOT, path))
    if not resolved.startswith(_PROJECT_ROOT):
        raise ValueError("Path traversal blocked: %s" % path)
    return resolved


def _handler_read_file(params):
    path = params.get("path", "")
    full = _safe_path(path)
    if not os.path.isfile(full):
        return "Error: file not found: %s" % path
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
        return content
    except Exception as e:
        return "Error reading file: %s" % str(e)


def _handler_list_directory(params):
    path = params.get("path", "")
    full = _safe_path(path)
    if not os.path.isdir(full):
        return "Error: directory not found: %s" % path
    try:
        entries = []
        for entry in sorted(os.listdir(full)):
            fp = os.path.join(full, entry)
            entries.append(
                {
                    "name": entry,
                    "type": "dir" if os.path.isdir(fp) else "file",
                    "size": os.path.getsize(fp) if os.path.isfile(fp) else None,
                }
            )
        return json.dumps(entries, ensure_ascii=False, indent=2)
    except Exception as e:
        return "Error listing directory: %s" % str(e)


def _handler_search_files(params):
    pattern = params.get("pattern", "")
    path = params.get("path", ".")
    full = _safe_path(path)
    if not os.path.isdir(full):
        return "Error: directory not found: %s" % path
    try:
        matches = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [
                d
                for d in dirs
                if d not in (".git", "__pycache__", "node_modules", ".venv")
            ]
            for f in files:
                if pattern.lower() in f.lower():
                    matches.append(os.path.relpath(os.path.join(root, f), _PROJECT_ROOT))
        return json.dumps(matches[:100], ensure_ascii=False, indent=2)
    except Exception as e:
        return "Error searching files: %s" % str(e)


def _handler_write_file(params):
    path = params.get("path", "")
    content = params.get("content", "")
    full = _safe_path(path)
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return "File written successfully: %s (%d bytes)" % (path, len(content))
    except Exception as e:
        return "Error writing file: %s" % str(e)


def register():
    register_tool(
        name="read_file",
        description="读取指定文件的内容。path 为相对于项目根目录的路径。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于项目根目录的文件路径",
                }
            },
            "required": ["path"],
        },
        handler=_handler_read_file,
        category="filesystem",
    )
    register_tool(
        name="list_directory",
        description="列出指定目录下的文件和子目录。path 为相对于项目根目录的路径。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于项目根目录的目录路径，默认为项目根",
                }
            },
            "required": [],
        },
        handler=_handler_list_directory,
        category="filesystem",
    )
    register_tool(
        name="search_files",
        description="在指定目录下按文件名关键词搜索文件。",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "文件名关键词",
                },
                "path": {
                    "type": "string",
                    "description": "搜索起始目录，默认为项目根",
                },
            },
            "required": ["pattern"],
        },
        handler=_handler_search_files,
        category="filesystem",
    )
    register_tool(
        name="write_file",
        description="将内容写入指定文件。path 为相对于项目根目录的路径。会自动创建中间目录。",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于项目根目录的文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容",
                },
            },
            "required": ["path", "content"],
        },
        handler=_handler_write_file,
        category="filesystem",
    )

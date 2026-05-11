# -*- coding: utf-8 -*-
"""
tool_api.py

API 调用 MCP 工具：让 Claude 可以调用外部 REST API、解析 JSON 响应。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import json
import logging

import requests

from domain_admin.service.mcp.mcp_registry import register_tool

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.timeout = 30


def _handler_call_api(params):
    url = params.get("url", "").strip()
    method = params.get("method", "GET").upper()
    headers_json = params.get("headers", "{}")
    query_json = params.get("query", "{}")
    body_json = params.get("body", None)
    if not url:
        return "Error: url is required"

    try:
        req_headers = json.loads(headers_json) if headers_json else {}
        req_query = json.loads(query_json) if query_json else {}
        req_body = json.loads(body_json) if body_json else None
    except json.JSONDecodeError as e:
        return "Error parsing JSON params: %s" % str(e)

    try:
        kwargs = {
            "timeout": 30,
            "headers": req_headers,
            "params": req_query,
            "allow_redirects": True,
        }
        if req_body is not None and method in ("POST", "PUT", "PATCH"):
            if req_headers.get("Content-Type", "").startswith("application/json"):
                kwargs["json"] = req_body
            else:
                kwargs["data"] = req_body

        resp = _SESSION.request(method, url, **kwargs)
        resp_data = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": None,
        }
        try:
            resp_data["body"] = resp.json()
        except Exception:
            resp_data["body"] = resp.text[:20000]
        return json.dumps(resp_data, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return "Error calling API: %s" % str(e)


def _handler_hunter_search(params):
    query = params.get("query", "").strip()
    api_key = params.get("api_key", "").strip()
    page = params.get("page", 1)
    page_size = params.get("page_size", 20)
    if not query:
        return "Error: query is required"
    if not api_key:
        return "Error: api_key is required"
    try:
        resp = _SESSION.get(
            "https://hunter.qianxin.com/openApi/search",
            params={
                "api-key": api_key,
                "search": query,
                "page": page,
                "page_size": page_size,
            },
            timeout=30,
        )
        return json.dumps(resp.json(), ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return "Error calling Hunter API: %s" % str(e)


def register():
    register_tool(
        name="call_api",
        description="调用外部 REST API。支持自定义 method/headers/query/body。",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "API URL",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP 方法",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                },
                "headers": {
                    "type": "string",
                    "description": "JSON 格式请求头",
                },
                "query": {
                    "type": "string",
                    "description": "JSON 格式查询参数",
                },
                "body": {
                    "type": "string",
                    "description": "JSON 格式请求体",
                },
            },
            "required": ["url"],
        },
        handler=_handler_call_api,
        category="api",
    )
    register_tool(
        name="hunter_search",
        description="调用奇安信 Hunter 空间测绘搜索引擎 API。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Hunter 搜索语法",
                },
                "api_key": {
                    "type": "string",
                    "description": "Hunter API Key",
                },
                "page": {
                    "type": "integer",
                    "description": "页码，默认1",
                },
                "page_size": {
                    "type": "integer",
                    "description": "每页条数，默认20",
                },
            },
            "required": ["query", "api_key"],
        },
        handler=_handler_hunter_search,
        category="api",
    )

# -*- coding: utf-8 -*-
"""
tool_browser.py

浏览器自动化 MCP 工具：让 Claude 可以抓取网页内容、提取页面信息。
基于 requests + 简单 HTML 解析，无需 Selenium/Playwright 依赖。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import json
import logging
import re

import requests
from html.parser import HTMLParser

from domain_admin.service.mcp.mcp_registry import register_tool

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
)
_SESSION.timeout = 30


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._pieces = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._pieces.append(data)

    def get_text(self):
        return re.sub(r"\s+", " ", " ".join(self._pieces)).strip()


def _handler_fetch_url(params):
    url = params.get("url", "").strip()
    if not url:
        return "Error: url is required"
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    try:
        resp = _SESSION.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            try:
                return json.dumps(resp.json(), ensure_ascii=False, indent=2)[:30000]
            except Exception:
                pass
        extractor = _TextExtractor()
        extractor.feed(resp.text)
        text = extractor.get_text()
        return text[:30000] if text else resp.text[:30000]
    except Exception as e:
        return "Error fetching URL: %s" % str(e)


def _handler_extract_links(params):
    url = params.get("url", "").strip()
    if not url:
        return "Error: url is required"
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    try:
        resp = _SESSION.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        links = re.findall(r'href=["\'](https?://[^"\']+)', resp.text)
        unique = list(dict.fromkeys(links))
        return json.dumps(unique[:200], ensure_ascii=False, indent=2)
    except Exception as e:
        return "Error extracting links: %s" % str(e)


def _handler_http_request(params):
    url = params.get("url", "").strip()
    method = params.get("method", "GET").upper()
    headers_str = params.get("headers", "{}")
    body = params.get("body", "")
    if not url:
        return "Error: url is required"
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    try:
        req_headers = json.loads(headers_str) if headers_str else {}
        kwargs = {"timeout": 30, "headers": req_headers, "allow_redirects": True}
        if body and method in ("POST", "PUT", "PATCH"):
            kwargs["data"] = body
        resp = _SESSION.request(method, url, **kwargs)
        return json.dumps(
            {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:20000],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception as e:
        return "Error making request: %s" % str(e)


def register():
    register_tool(
        name="fetch_url",
        description="抓取指定 URL 的页面内容并提取纯文本。支持 HTTP/HTTPS。",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的 URL 地址",
                }
            },
            "required": ["url"],
        },
        handler=_handler_fetch_url,
        category="browser",
    )
    register_tool(
        name="extract_links",
        description="从指定 URL 页面中提取所有超链接。",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要提取链接的 URL 地址",
                }
            },
            "required": ["url"],
        },
        handler=_handler_extract_links,
        category="browser",
    )
    register_tool(
        name="http_request",
        description="发起自定义 HTTP 请求（GET/POST/PUT/DELETE），可设置 headers 和 body。",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "请求 URL",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP 方法，默认 GET",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
                },
                "headers": {
                    "type": "string",
                    "description": "JSON 格式的请求头",
                },
                "body": {
                    "type": "string",
                    "description": "请求体（POST/PUT 时使用）",
                },
            },
            "required": ["url"],
        },
        handler=_handler_http_request,
        category="browser",
    )

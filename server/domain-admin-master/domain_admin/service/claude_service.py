# -*- coding: utf-8 -*-
"""
claude_service.py

Claude 服务：会话管理 + 消息收发 + Anthropic SDK tool_use 多轮调用 + MCP 工具集成。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import json
import logging
import traceback
from datetime import datetime

from anthropic import Anthropic
from anthropic import AuthenticationError, APIConnectionError, RateLimitError

from domain_admin.config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS
from domain_admin.model.base_model import db
from domain_admin.model.claude_conversation_model import ClaudeConversationModel
from domain_admin.model.claude_message_model import ClaudeMessageModel
from domain_admin.service.mcp import mcp_loader, mcp_registry
from domain_admin.utils.flask_ext.app_exception import AppException

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10
_schema_checked = False


def _resolve_model_name(model_name=None):
    candidate = (model_name or ANTHROPIC_MODEL or "").strip()
    if candidate.lower().startswith("claude"):
        return candidate
    return "claude-3-5-sonnet-latest"


def _resolve_base_url():
    base_url = (ANTHROPIC_BASE_URL or "").strip()
    if not base_url:
        return None
    if base_url.startswith("http://") or base_url.startswith("https://"):
        return base_url
    return None


def _get_client():
    if not ANTHROPIC_API_KEY:
        raise AppException("Claude 未配置：请在后端环境变量中设置 ANTHROPIC_API_KEY")

    kwargs = {"api_key": ANTHROPIC_API_KEY}
    base_url = _resolve_base_url()
    if base_url:
        kwargs["base_url"] = base_url

    return Anthropic(**kwargs)


def _ensure_mcp_loaded():
    if not mcp_loader.is_loaded():
        mcp_loader.load_all()


def _ensure_schema():
    global _schema_checked
    if _schema_checked:
        return
    try:
        columns = db.get_columns(ClaudeMessageModel._meta.table_name)
        col_names = {c.name for c in columns}
        if "tool_calls" not in col_names:
            cursor = db.cursor()
            cursor.execute("ALTER TABLE tb_claude_message ADD COLUMN tool_calls TEXT NULL")
            cursor.close()
        _schema_checked = True
    except Exception as e:
        logger.warning("Ensure Claude schema failed: %s", e)


def create_conversation(user_id, title=None, model_name=None):
    model_name = _resolve_model_name(model_name)
    title = title or "新对话"

    row = ClaudeConversationModel.create(
        user_id=user_id,
        title=title,
        model_name=model_name,
        is_active=True,
        create_time=datetime.now(),
        update_time=datetime.now(),
    )
    return {"conversation_id": row.id}


def list_conversations(user_id, limit=50):
    qs = (
        ClaudeConversationModel.select()
        .where((ClaudeConversationModel.user_id == user_id) & (ClaudeConversationModel.is_active == True))
        .order_by(ClaudeConversationModel.update_time.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "model_name": row.model_name,
            "update_time": str(row.update_time),
        }
        for row in qs
    ]


def get_messages(user_id, conversation_id, limit=200):
    _ensure_schema()
    conv = ClaudeConversationModel.get_by_id(conversation_id)
    if not conv or conv.user_id != user_id:
        raise AppException("会话不存在或无权限")

    qs = (
        ClaudeMessageModel.select()
        .where(ClaudeMessageModel.conversation_id == conversation_id)
        .order_by(ClaudeMessageModel.id.asc())
        .limit(limit)
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "tool_calls": m.tool_calls,
            "create_time": str(m.create_time),
        }
        for m in qs
    ]


def delete_conversation(user_id, conversation_id):
    conv = ClaudeConversationModel.get_by_id(conversation_id)
    if not conv or conv.user_id != user_id:
        raise AppException("会话不存在或无权限")
    ClaudeMessageModel.delete().where(ClaudeMessageModel.conversation_id == conversation_id).execute()
    conv.delete_instance()
    return {"msg": "deleted"}


def rename_conversation(user_id, conversation_id, title):
    conv = ClaudeConversationModel.get_by_id(conversation_id)
    if not conv or conv.user_id != user_id:
        raise AppException("会话不存在或无权限")
    title = (title or "").strip()
    if not title:
        raise AppException("会话名称不能为空")
    ClaudeConversationModel.update(
        title=title,
        update_time=datetime.now(),
    ).where(ClaudeConversationModel.id == conversation_id).execute()
    return {"msg": "updated"}


def _execute_tool_calls(content_blocks):
    """
    从 Claude 响应的 content blocks 中提取 tool_use 块，
    调用对应 MCP 工具并返回 tool_result 格式。
    """
    tool_results = []
    tool_call_summaries = []

    for block in content_blocks:
        if block.type != "tool_use":
            continue

        tool_name = block.name
        tool_input = block.input
        tool_use_id = block.id

        summary = {"tool": tool_name, "input": tool_input}
        try:
            result = mcp_registry.call_tool(tool_name, tool_input)
            summary["status"] = "success"
        except Exception as e:
            result = "Tool execution error: %s" % str(e)
            summary["status"] = "error"
            summary["error"] = str(e)

        summary["result_preview"] = (result or "")[:200]
        tool_call_summaries.append(summary)

        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result,
            }
        )

    return tool_results, tool_call_summaries


def _run_with_tools(client, model, messages, tools):
    """
    执行带 tool_use 的多轮 Claude 调用，直到 Claude 不再请求工具或达到最大轮次。
    返回 (final_text, all_tool_summaries)
    """
    all_tool_summaries = []
    current_messages = list(messages)

    for round_idx in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=int(ANTHROPIC_MAX_TOKENS),
                messages=current_messages,
                tools=tools,
            )
        except AuthenticationError:
            raise AppException("Claude 调用失败：ANTHROPIC_API_KEY 无效，请检查配置")
        except RateLimitError:
            raise AppException("Claude 调用失败：触发限流，请稍后重试")
        except APIConnectionError:
            raise AppException("Claude 调用失败：网络连接异常，请检查代理或网络")
        except Exception as e:
            raise AppException("Claude 调用失败: %s" % (str(e),))

        if resp.stop_reason == "tool_use":
            assistant_content = []
            for block in resp.content:
                assistant_content.append({"type": block.type, "text": getattr(block, "text", "")} if block.type == "text" else {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})

            current_messages.append({"role": "assistant", "content": assistant_content})

            tool_results, round_summaries = _execute_tool_calls(resp.content)
            all_tool_summaries.extend(round_summaries)

            current_messages.append({"role": "user", "content": tool_results})
            logger.info(
                "tool_use round %d: called %d tools",
                round_idx + 1,
                len(round_summaries),
            )
        else:
            final_text = ""
            for block in resp.content:
                if block.type == "text":
                    final_text += block.text
            return final_text.strip(), all_tool_summaries

    return "（达到最大工具调用轮次，自动停止）", all_tool_summaries


def send_message(user_id, conversation_id, content):
    if not content or not content.strip():
        raise AppException("消息内容不能为空")

    conv = ClaudeConversationModel.get_by_id(conversation_id)
    if not conv or conv.user_id != user_id:
        raise AppException("会话不存在或无权限")

    _ensure_schema()
    _ensure_mcp_loaded()

    ClaudeMessageModel.create(
        conversation_id=conversation_id,
        role="user",
        content=content.strip(),
        create_time=datetime.now(),
    )

    history = (
        ClaudeMessageModel.select()
        .where(ClaudeMessageModel.conversation_id == conversation_id)
        .order_by(ClaudeMessageModel.id.asc())
    )

    messages = []
    for m in history:
        role = m.role
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": m.content})

    client = _get_client()
    model = _resolve_model_name(conv.model_name)
    tools = mcp_registry.get_anthropic_tools()

    if tools:
        answer, tool_summaries = _run_with_tools(client, model, messages, tools)
    else:
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=int(ANTHROPIC_MAX_TOKENS),
                messages=messages,
            )
        except AuthenticationError:
            raise AppException("Claude 调用失败：ANTHROPIC_API_KEY 无效")
        except RateLimitError:
            raise AppException("Claude 调用失败：触发限流")
        except APIConnectionError:
            raise AppException("Claude 调用失败：网络连接异常")
        except Exception as e:
            raise AppException("Claude 调用失败: %s" % (str(e),))

        answer = ""
        blocks = getattr(resp, "content", None) or []
        answer = "".join([getattr(b, "text", "") for b in blocks]).strip()
        tool_summaries = []

    tool_calls_json = None
    if tool_summaries:
        tool_calls_json = json.dumps(tool_summaries, ensure_ascii=False)

    ClaudeMessageModel.create(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        tool_calls=tool_calls_json,
        create_time=datetime.now(),
    )

    ClaudeConversationModel.update(update_time=datetime.now()).where(
        ClaudeConversationModel.id == conversation_id
    ).execute()

    return {"answer": answer, "tool_calls": tool_summaries}


def get_mcp_status():
    _ensure_mcp_loaded()
    return {
        "loaded": mcp_loader.is_loaded(),
        "tools": [
            {"name": t["name"], "category": t["category"], "description": t["description"]}
            for t in mcp_registry.list_tools()
        ],
        "health": mcp_registry.get_health_status(),
    }

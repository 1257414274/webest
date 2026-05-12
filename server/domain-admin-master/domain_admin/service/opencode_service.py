# -*- coding: utf-8 -*-
"""
opencode_service.py

OpenCode 独立功能模块：
- 统一封装 OpenCode Server 调用
- 任务落库与状态管理
- 数据隔离（按 user_id）
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from flask import Response, stream_with_context

from domain_admin.config import (
    OPENCODE_SERVER_URL,
    OPENCODE_API_KEY,
    OPENCODE_TIMEOUT_SECONDS,
    OPENCODE_ANTHROPIC_MODEL,
    OPENCODE_PROVIDER_ID,
    ANTHROPIC_API_KEY,
)
from domain_admin.model.opencode_task_model import OpencodeTaskModel
from domain_admin.utils.flask_ext.app_exception import AppException

logger = logging.getLogger(__name__)
_BRIDGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "opencode_sdk_bridge")
)
_BRIDGE_SCRIPT = os.path.join(_BRIDGE_DIR, "bridge.mjs")


def _normalize_base_url():
    base_url = (OPENCODE_SERVER_URL or "").strip()
    if not base_url:
        raise AppException("OpenCode 未配置：请设置 OPENCODE_SERVER_URL")
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        raise AppException("OpenCode 配置错误：OPENCODE_SERVER_URL 必须包含 http:// 或 https://")
    if "open.bigmodel.cn/api/anthropic" in base_url.lower():
        raise AppException(
            "OpenCode SDK 需要连接 OpenCode Server 地址，不能直接使用 Anthropic 兼容地址。"
            "请将 OPENCODE_SERVER_URL 改为 OpenCode Server，例如 http://127.0.0.1:4096"
        )
    return base_url.rstrip("/")


def _build_execute_payload(prompt, context, user_id, retry_of_task_id=None, session_id=None):
    payload = {
        "model": OPENCODE_ANTHROPIC_MODEL,
        "prompt": prompt.strip(),
        "context": context or "",
        "user_id": user_id,
    }
    if retry_of_task_id:
        payload["retry_of_task_id"] = retry_of_task_id
    if session_id:
        payload["session_id"] = str(session_id)
    return payload


def _ensure_sdk_bridge():
    if not os.path.exists(_BRIDGE_SCRIPT):
        raise AppException("未找到 OpenCode SDK 桥接脚本: %s" % _BRIDGE_SCRIPT)


def _resolve_provider_api_key():
    """
    对于本机已登录的 provider（如 zhipuai-coding-plan），
    优先使用 OpenCode 自身凭证，不强制覆写 key。
    """
    provider_id = (OPENCODE_PROVIDER_ID or "").strip().lower()
    if provider_id in ("zhipuai-coding-plan", "zhipu-coding-plan"):
        return ""
    return (OPENCODE_API_KEY or ANTHROPIC_API_KEY or "").strip()


def _call_sdk_bridge(action, payload):
    _ensure_sdk_bridge()
    cmd = ["node", _BRIDGE_SCRIPT, action]
    try:
        p = subprocess.run(
            cmd,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=_BRIDGE_DIR,
            timeout=max(10, int(OPENCODE_TIMEOUT_SECONDS) + 10),
        )
    except Exception as e:
        raise AppException("调用 OpenCode SDK 失败: %s" % str(e))

    if p.returncode != 0:
        stderr = (p.stderr or "").strip()[:500]
        logger.error("OpenCode SDK bridge error (%s): %s", action, stderr or "unknown error")
        raise AppException("OpenCode SDK 执行失败: %s" % (stderr or "unknown error"))

    stdout = (p.stdout or "").strip()
    if not stdout:
        raise AppException("OpenCode SDK 返回为空")
    try:
        return json.loads(stdout)
    except Exception:
        raise AppException("OpenCode SDK 返回格式错误: %s" % stdout[:300])


def _sdk_execute(prompt, context, user_id, task_name, retry_of_task_id=None, session_id=None):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "model": OPENCODE_ANTHROPIC_MODEL,
        "providerId": OPENCODE_PROVIDER_ID,
        "taskName": task_name,
        "prompt": prompt,
        "context": context or "",
        "userId": user_id,
        "retryOfTaskId": retry_of_task_id,
        "sessionId": session_id,
    }
    return _call_sdk_bridge("execute", payload)


def _sdk_health():
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
    }
    return _call_sdk_bridge("health", payload)


def _sdk_cancel(session_id):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
        "sessionId": session_id,
    }
    return _call_sdk_bridge("cancel", payload)


def _sdk_session_list(limit=50, search=""):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
        "limit": int(limit or 50),
        "search": search or "",
    }
    return _call_sdk_bridge("session_list", payload)


def _sdk_session_messages(session_id, limit=100):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
        "sessionId": str(session_id),
        "limit": int(limit or 100),
    }
    return _call_sdk_bridge("session_messages", payload)


def _sdk_create_session(title="OpenCode会话"):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
        "title": title or "OpenCode会话",
    }
    return _call_sdk_bridge("create_session", payload)


def _sdk_delete_session(session_id):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
        "sessionId": str(session_id),
    }
    return _call_sdk_bridge("delete_session", payload)


def _sdk_rename_session(session_id, title):
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "providerId": OPENCODE_PROVIDER_ID,
        "sessionId": str(session_id),
        "title": title or "OpenCode会话",
    }
    return _call_sdk_bridge("rename_session", payload)


def _start_sdk_stream(prompt, context, user_id, task_name, session_id=None):
    _ensure_sdk_bridge()
    payload = {
        "baseUrl": _normalize_base_url(),
        "apiKey": _resolve_provider_api_key(),
        "model": OPENCODE_ANTHROPIC_MODEL,
        "providerId": OPENCODE_PROVIDER_ID,
        "taskName": task_name,
        "prompt": prompt,
        "context": context or "",
        "userId": user_id,
        "sessionId": session_id,
    }
    cmd = ["node", _BRIDGE_SCRIPT, "stream"]
    try:
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=_BRIDGE_DIR,
            bufsize=1,
        )
        p.stdin.write(json.dumps(payload, ensure_ascii=False))
        p.stdin.close()
        return p
    except Exception as e:
        raise AppException("启动 OpenCode SDK 流式任务失败: %s" % str(e))


def execute_task(user_id, prompt, context="", task_name="", session_id=None):
    if not prompt or not prompt.strip():
        raise AppException("prompt 不能为空")

    task_name = (task_name or "").strip() or "OpenCode任务"
    context = context or ""
    request_payload = _build_execute_payload(
        prompt=prompt,
        context=context,
        user_id=user_id,
        session_id=session_id,
    )

    row = OpencodeTaskModel.create(
        user_id=user_id,
        task_name=task_name,
        prompt=prompt.strip(),
        context=context,
        status="running",
        request_payload=json.dumps(request_payload, ensure_ascii=False),
        create_time=datetime.now(),
        update_time=datetime.now(),
    )

    try:
        sdk_data = _sdk_execute(
            prompt=prompt.strip(),
            context=context,
            user_id=user_id,
            task_name=task_name,
            session_id=session_id,
        )
        response_data = sdk_data.get("response") or sdk_data
        latency_ms = int(sdk_data.get("latency_ms") or 0)
        remote_task_id = str(
            sdk_data.get("session_id")
            or response_data.get("task_id")
            or response_data.get("id")
            or response_data.get("request_id")
            or ""
        )
        row.status = "success"
        row.remote_task_id = remote_task_id
        row.response_payload = json.dumps(response_data, ensure_ascii=False)
        row.latency_ms = latency_ms
        row.update_time = datetime.now()
        row.save()
    except Exception as e:
        row.status = "failed"
        row.error_message = str(e)
        row.update_time = datetime.now()
        row.save()
        raise

    return _to_task_dict(row)


def get_task_list(user_id, page=1, size=20, status=None):
    page = max(1, int(page or 1))
    size = max(1, min(200, int(size or 20)))
    cond = (OpencodeTaskModel.user_id == user_id)
    if status:
        cond = cond & (OpencodeTaskModel.status == status)

    qs = (
        OpencodeTaskModel.select()
        .where(cond)
        .order_by(OpencodeTaskModel.id.desc())
        .paginate(page, size)
    )
    total = OpencodeTaskModel.select().where(cond).count()
    return {
        "total": total,
        "list": [_to_task_dict(item, include_payload=False) for item in qs],
    }


def get_task_detail(user_id, task_id):
    row = OpencodeTaskModel.select().where(
        (OpencodeTaskModel.id == task_id) & (OpencodeTaskModel.user_id == user_id)
    ).get_or_none()
    if not row:
        raise AppException("任务不存在")
    return _to_task_dict(row, include_payload=True)


def retry_task(user_id, task_id):
    row = OpencodeTaskModel.select().where(
        (OpencodeTaskModel.id == task_id) & (OpencodeTaskModel.user_id == user_id)
    ).get_or_none()
    if not row:
        raise AppException("任务不存在")

    row.status = "running"
    row.error_message = ""
    row.retry_count = int(row.retry_count or 0) + 1
    row.update_time = datetime.now()
    row.save()

    request_payload = _build_execute_payload(
        prompt=row.prompt,
        context=row.context or "",
        user_id=user_id,
        retry_of_task_id=row.id,
    )
    row.request_payload = json.dumps(request_payload, ensure_ascii=False)
    row.save()

    try:
        sdk_data = _sdk_execute(
            prompt=row.prompt,
            context=row.context or "",
            user_id=user_id,
            task_name=row.task_name or "OpenCode任务",
            retry_of_task_id=row.id,
            session_id=row.remote_task_id or None,
        )
        response_data = sdk_data.get("response") or sdk_data
        latency_ms = int(sdk_data.get("latency_ms") or 0)
        row.status = "success"
        row.remote_task_id = str(
            sdk_data.get("session_id")
            or response_data.get("task_id")
            or response_data.get("id")
            or row.remote_task_id
            or ""
        )
        row.response_payload = json.dumps(response_data, ensure_ascii=False)
        row.latency_ms = latency_ms
        row.update_time = datetime.now()
        row.save()
    except Exception as e:
        row.status = "failed"
        row.error_message = str(e)
        row.update_time = datetime.now()
        row.save()
        raise

    return _to_task_dict(row)


def cancel_task(user_id, task_id):
    row = OpencodeTaskModel.select().where(
        (OpencodeTaskModel.id == task_id) & (OpencodeTaskModel.user_id == user_id)
    ).get_or_none()
    if not row:
        raise AppException("任务不存在")

    # 若 OpenCode Server 支持取消接口则尝试调用，不强依赖
    if row.remote_task_id:
        try:
            _sdk_cancel(row.remote_task_id)
        except Exception as e:
            logger.warning("Cancel remote opencode task failed: %s", e)

    row.status = "cancelled"
    row.update_time = datetime.now()
    row.save()
    return {"msg": "cancelled"}


def health_check():
    sdk_data = _sdk_health()
    response_data = sdk_data.get("response") or sdk_data
    latency_ms = int(sdk_data.get("latency_ms") or 0)
    return {
        "status": "ok",
        "latency_ms": latency_ms,
        "server": response_data,
    }


def create_session(user_id, title=""):
    _ = user_id
    sdk_data = _sdk_create_session(title=title or "OpenCode会话")
    response_data = sdk_data.get("response") or {}
    return {
        "session_id": str(sdk_data.get("session_id") or response_data.get("id") or ""),
        "title": response_data.get("title") or title or "OpenCode会话",
    }


def delete_session(user_id, session_id):
    _ = user_id
    if not session_id:
        raise AppException("session_id 不能为空")
    sdk_data = _sdk_delete_session(session_id=session_id)
    return sdk_data.get("response") or {"deleted": True, "session_id": str(session_id)}


def rename_session(user_id, session_id, title):
    _ = user_id
    if not session_id:
        raise AppException("session_id 不能为空")
    sdk_data = _sdk_rename_session(session_id=session_id, title=title)
    response_data = sdk_data.get("response") or {}
    return {
        "session_id": str(session_id),
        "title": response_data.get("title") or title or "OpenCode会话",
    }


def list_sessions(user_id, limit=50, search=""):
    _ = user_id
    sdk_data = _sdk_session_list(limit=limit, search=search)
    response_data = sdk_data.get("response")
    if not isinstance(response_data, list):
        response_data = []
    result = []
    for item in response_data:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("id") or item.get("sessionID") or item.get("session_id") or "")
        if not session_id:
            continue
        result.append({
            "session_id": session_id,
            "title": item.get("title") or "OpenCode会话",
            "updated_at": str(item.get("updatedAt") or item.get("updated_at") or item.get("time", {}).get("updated") or ""),
            "raw": item,
        })
    return {"list": result}


def get_session_messages(user_id, session_id, limit=100):
    _ = user_id
    if not session_id:
        raise AppException("session_id 不能为空")
    sdk_data = _sdk_session_messages(session_id=session_id, limit=limit)
    response_data = sdk_data.get("response")
    if not isinstance(response_data, list):
        response_data = []

    messages = []
    for item in response_data:
        if not isinstance(item, dict):
            continue
        info = item.get("info") if isinstance(item.get("info"), dict) else item
        parts = item.get("parts")
        if not isinstance(parts, list):
            parts = []
        role = info.get("role") or "assistant"
        text_chunks = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            t = part.get("type")
            if t in ("text", "reasoning", "thinking"):
                text = part.get("text") or part.get("content") or ""
                if text:
                    text_chunks.append(str(text))
        text = "".join(text_chunks).strip()
        if not text:
            text = str(info.get("content") or "")
        messages.append({
            "id": str(info.get("id") or ""),
            "role": role,
            "text": text,
            "create_time": str(info.get("createdAt") or info.get("create_time") or ""),
        })
    return {"session_id": str(session_id), "list": messages}


def get_metrics(user_id):
    total = OpencodeTaskModel.select().where(OpencodeTaskModel.user_id == user_id).count()
    success = OpencodeTaskModel.select().where(
        (OpencodeTaskModel.user_id == user_id) & (OpencodeTaskModel.status == "success")
    ).count()
    failed = OpencodeTaskModel.select().where(
        (OpencodeTaskModel.user_id == user_id) & (OpencodeTaskModel.status == "failed")
    ).count()
    running = OpencodeTaskModel.select().where(
        (OpencodeTaskModel.user_id == user_id) & (OpencodeTaskModel.status == "running")
    ).count()
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "running": running,
        "success_rate": round(float(success) / max(1, total), 4),
    }


def stream_execute_task(user_id, prompt, context="", task_name="", session_id=None):
    if not prompt or not prompt.strip():
        raise AppException("prompt 不能为空")

    task_name = (task_name or "").strip() or "OpenCode任务"
    context = context or ""

    request_payload = _build_execute_payload(
        prompt=prompt,
        context=context,
        user_id=user_id,
        session_id=session_id,
    )
    row = OpencodeTaskModel.create(
        user_id=user_id,
        task_name=task_name,
        prompt=prompt.strip(),
        context=context,
        status="running",
        request_payload=json.dumps(request_payload, ensure_ascii=False),
        create_time=datetime.now(),
        update_time=datetime.now(),
    )

    def _sse(event_name, data_obj):
        return "event: %s\ndata: %s\n\n" % (
            event_name,
            json.dumps(data_obj, ensure_ascii=False),
        )

    @stream_with_context
    def generate():
        full_text_chunks = []
        begin_ts = time.time()
        process = None
        done_received = False
        current_session_id = str(session_id or "")
        try:
            process = _start_sdk_stream(
                prompt=prompt.strip(),
                context=context,
                user_id=user_id,
                task_name=task_name,
                session_id=current_session_id or None,
            )
            yield _sse("meta", {
                "task_id": row.id,
                "status": "running",
                "session_id": str(current_session_id or row.remote_task_id or ""),
            })

            for raw_line in process.stdout:
                if not raw_line or not raw_line.strip():
                    continue
                try:
                    data = json.loads(raw_line.strip())
                except Exception:
                    continue

                event_type = str(data.get("event") or "").strip()
                if event_type == "meta":
                    event_session_id = str(data.get("session_id") or "")
                    if event_session_id:
                        current_session_id = event_session_id
                        row.remote_task_id = event_session_id
                        row.update_time = datetime.now()
                        row.save()
                    continue
                if event_type == "thinking":
                    text = str(data.get("text") or "")
                    if text:
                        full_text_chunks.append(text)
                        yield _sse("thinking", {"text": text})
                    continue
                if event_type == "delta":
                    text = str(data.get("text") or "")
                    if text:
                        full_text_chunks.append(text)
                        yield _sse("delta", {"text": text})
                    continue
                if event_type == "error":
                    msg = str(data.get("message") or "OpenCode 流式执行失败")
                    raise AppException(msg)
                if event_type == "done":
                    done_received = True
                    break

            if process:
                return_code = process.wait(timeout=max(5, int(OPENCODE_TIMEOUT_SECONDS)))
                if return_code != 0 and not done_received:
                    err = (process.stderr.read() or "").strip()[:500]
                    raise AppException(err or "OpenCode SDK 流式执行失败")

            final_text = "".join(full_text_chunks).strip()
            row.status = "success"
            row.response_payload = json.dumps(
                {"text": final_text, "session_id": row.remote_task_id or ""},
                ensure_ascii=False
            )
            row.latency_ms = int((time.time() - begin_ts) * 1000)
            row.update_time = datetime.now()
            row.save()
            yield _sse("done", {"task_id": row.id, "status": "success"})
        except Exception as e:
            row.status = "failed"
            row.error_message = str(e)
            row.update_time = datetime.now()
            row.save()
            if process:
                try:
                    process.kill()
                except Exception:
                    pass
            yield _sse("error", {"task_id": row.id, "message": str(e)})

    return Response(generate(), mimetype="text/event-stream")


def _to_task_dict(row, include_payload=False):
    data = {
        "id": row.id,
        "task_name": row.task_name,
        "status": row.status,
        "remote_task_id": row.remote_task_id,
        "latency_ms": row.latency_ms,
        "retry_count": row.retry_count,
        "error_message": row.error_message,
        "create_time": str(row.create_time),
        "update_time": str(row.update_time),
    }
    if include_payload:
        data["prompt"] = row.prompt
        data["context"] = row.context
        data["request_payload"] = row.request_payload
        data["response_payload"] = row.response_payload
    return data

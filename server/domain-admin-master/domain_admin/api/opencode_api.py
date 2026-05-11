# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from flask import request, g

from domain_admin.enums.role_enum import RoleEnum
from domain_admin.service import auth_service, opencode_service


@auth_service.permission(role=RoleEnum.USER)
def opencode_execute():
    task_name = request.json.get("task_name", "")
    prompt = request.json.get("prompt", "")
    context = request.json.get("context", "")
    session_id = request.json.get("session_id", "")
    return opencode_service.execute_task(
        user_id=g.user_id,
        task_name=task_name,
        prompt=prompt,
        context=context,
        session_id=session_id,
    )


@auth_service.permission(role=RoleEnum.USER)
def opencode_task_list():
    page = request.json.get("page", 1)
    size = request.json.get("size", 20)
    status = request.json.get("status")
    return opencode_service.get_task_list(
        user_id=g.user_id,
        page=page,
        size=size,
        status=status,
    )


@auth_service.permission(role=RoleEnum.USER)
def opencode_task_detail():
    task_id = request.json.get("task_id")
    return opencode_service.get_task_detail(g.user_id, task_id)


@auth_service.permission(role=RoleEnum.USER)
def opencode_retry_task():
    task_id = request.json.get("task_id")
    return opencode_service.retry_task(g.user_id, task_id)


@auth_service.permission(role=RoleEnum.USER)
def opencode_cancel_task():
    task_id = request.json.get("task_id")
    return opencode_service.cancel_task(g.user_id, task_id)


@auth_service.permission(role=RoleEnum.USER)
def opencode_health():
    return opencode_service.health_check()


@auth_service.permission(role=RoleEnum.USER)
def opencode_metrics():
    return opencode_service.get_metrics(g.user_id)


@auth_service.permission(role=RoleEnum.USER)
def opencode_stream():
    data = request.json or {}
    task_name = data.get("task_name", "")
    prompt = data.get("prompt", "")
    context = data.get("context", "")
    session_id = data.get("session_id", "")
    return opencode_service.stream_execute_task(
        user_id=g.user_id,
        task_name=task_name,
        prompt=prompt,
        context=context,
        session_id=session_id,
    )


@auth_service.permission(role=RoleEnum.USER)
def opencode_create_session():
    title = (request.json or {}).get("title", "")
    return opencode_service.create_session(g.user_id, title=title)


@auth_service.permission(role=RoleEnum.USER)
def opencode_delete_session():
    session_id = (request.json or {}).get("session_id", "")
    return opencode_service.delete_session(g.user_id, session_id=session_id)


@auth_service.permission(role=RoleEnum.USER)
def opencode_rename_session():
    data = request.json or {}
    session_id = data.get("session_id", "")
    title = data.get("title", "")
    return opencode_service.rename_session(g.user_id, session_id=session_id, title=title)


@auth_service.permission(role=RoleEnum.USER)
def opencode_session_list():
    data = request.json or {}
    limit = data.get("limit", 50)
    search = data.get("search", "")
    return opencode_service.list_sessions(g.user_id, limit=limit, search=search)


@auth_service.permission(role=RoleEnum.USER)
def opencode_session_messages():
    data = request.json or {}
    session_id = data.get("session_id", "")
    limit = data.get("limit", 100)
    return opencode_service.get_session_messages(g.user_id, session_id=session_id, limit=limit)

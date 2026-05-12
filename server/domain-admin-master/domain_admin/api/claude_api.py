# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from flask import request, g

from domain_admin.enums.role_enum import RoleEnum
from domain_admin.service import auth_service, claude_service


@auth_service.permission(role=RoleEnum.USER)
def create_claude_conversation():
    title = request.json.get('title', '新对话')
    model_name = request.json.get('model_name')
    return claude_service.create_conversation(g.user_id, title=title, model_name=model_name)


@auth_service.permission(role=RoleEnum.USER)
def get_claude_conversations():
    limit = request.json.get('limit', 50)
    return {"list": claude_service.list_conversations(g.user_id, limit=limit)}


@auth_service.permission(role=RoleEnum.USER)
def get_claude_messages():
    conversation_id = request.json.get('conversation_id')
    return {"list": claude_service.get_messages(g.user_id, conversation_id)}


@auth_service.permission(role=RoleEnum.USER)
def send_claude_message():
    conversation_id = request.json.get('conversation_id')
    content = request.json.get('content', '')
    return claude_service.send_message(g.user_id, conversation_id, content)


@auth_service.permission(role=RoleEnum.USER)
def delete_claude_conversation():
    conversation_id = request.json.get('conversation_id')
    return claude_service.delete_conversation(g.user_id, conversation_id)


@auth_service.permission(role=RoleEnum.USER)
def get_claude_mcp_status():
    return claude_service.get_mcp_status()


@auth_service.permission(role=RoleEnum.USER)
def rename_claude_conversation():
    conversation_id = request.json.get('conversation_id')
    title = request.json.get('title', '')
    return claude_service.rename_conversation(g.user_id, conversation_id, title)

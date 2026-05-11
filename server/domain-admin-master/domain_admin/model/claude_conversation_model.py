# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from datetime import datetime

from peewee import AutoField, IntegerField, CharField, DateTimeField, BooleanField

from domain_admin.model.base_model import BaseModel


class ClaudeConversationModel(BaseModel):
    """Claude 会话表"""
    id = AutoField(primary_key=True)
    user_id = IntegerField(index=True)
    title = CharField(default='新对话')
    model_name = CharField(default='claude-3-5-sonnet-latest')
    is_active = BooleanField(default=True)
    create_time = DateTimeField(default=datetime.now)
    update_time = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'tb_claude_conversation'

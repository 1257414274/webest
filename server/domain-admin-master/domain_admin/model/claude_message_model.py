# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from datetime import datetime

from peewee import AutoField, IntegerField, CharField, TextField, DateTimeField

from domain_admin.model.base_model import BaseModel


class ClaudeMessageModel(BaseModel):
    """Claude 消息表"""
    id = AutoField(primary_key=True)
    conversation_id = IntegerField(index=True)
    role = CharField()
    content = TextField(default='')
    tool_calls = TextField(null=True, default=None)
    input_tokens = IntegerField(null=True)
    output_tokens = IntegerField(null=True)
    create_time = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'tb_claude_message'

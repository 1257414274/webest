# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from datetime import datetime

from peewee import AutoField, IntegerField, CharField, TextField, DateTimeField

from domain_admin.model.base_model import BaseModel


class OpencodeTaskModel(BaseModel):
    """OpenCode 任务表"""
    id = AutoField(primary_key=True)
    user_id = IntegerField(index=True)
    task_name = CharField(default='OpenCode任务')
    prompt = TextField(default='')
    context = TextField(default='')
    status = CharField(default='pending', index=True)
    remote_task_id = CharField(default='', index=True)
    request_payload = TextField(default='')
    response_payload = TextField(default='')
    error_message = TextField(default='')
    latency_ms = IntegerField(default=0)
    retry_count = IntegerField(default=0)
    create_time = DateTimeField(default=datetime.now)
    update_time = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'tb_opencode_task'

# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from datetime import datetime

from peewee import AutoField, IntegerField, CharField, DateTimeField, BooleanField

from domain_admin.model.base_model import BaseModel


class UserSessionModel(BaseModel):
    """用户会话表（支持多设备并发登录）"""
    id = AutoField(primary_key=True)
    user_id = IntegerField(index=True)
    session_id = CharField(unique=True, index=True)
    token_jti = CharField(unique=True, index=True)
    device_id = CharField(default='', index=True)
    device_name = CharField(default='')
    ip = CharField(default='')
    user_agent = CharField(default='')
    is_active = BooleanField(default=True, index=True)
    login_time = DateTimeField(default=datetime.now)
    last_active_time = DateTimeField(default=datetime.now)
    expire_time = DateTimeField()
    revoked_time = DateTimeField(null=True)
    revoke_reason = CharField(default='')

    class Meta:
        table_name = 'tb_user_session'

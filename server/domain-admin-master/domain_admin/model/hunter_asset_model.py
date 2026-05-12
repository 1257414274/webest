# -*- coding: utf-8 -*-
"""
hunter_asset_model.py
"""
from __future__ import print_function, unicode_literals, absolute_import, division

from peewee import CharField, IntegerField, DateTimeField, TextField, SQL

from domain_admin.model.base_model import BaseModel
from domain_admin.utils import datetime_util

class HunterAssetModel(BaseModel):
    """
    Hunter资产表
    """
    id = IntegerField(primary_key=True, constraints=[SQL('AUTO_INCREMENT')])
    
    # 核心字段（预先定义）
    ip = CharField(default='', null=True, verbose_name="IP地址")
    port = CharField(default='', null=True, verbose_name="端口")
    domain = CharField(default='', null=True, verbose_name="域名")
    url = CharField(default='', null=True, verbose_name="URL")
    web_title = CharField(default='', null=True, verbose_name="网站标题")
    company = CharField(default='', null=True, verbose_name="公司")
    
    # 记录的创建和更新时间
    create_time = DateTimeField(default=datetime_util.get_datetime, verbose_name="创建时间")
    update_time = DateTimeField(default=datetime_util.get_datetime, verbose_name="更新时间")

    class Meta:
        table_name = 'tb_hunter_asset'

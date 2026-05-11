# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division
from flask import request, g

from domain_admin import config
from domain_admin.enums.role_enum import RoleEnum
from domain_admin.service import auth_service
from domain_admin.utils.flask_ext.app_exception import AppException


def login():
    """
    用户登录
    """
    username = request.json['username']
    password = request.json['password']

    device_id = request.headers.get('X-Device-Id', '')
    device_name = request.headers.get('X-Device-Name', '')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
    user_agent = request.headers.get('User-Agent', '')

    return auth_service.login(
        username=username,
        password=password,
        device_id=device_id,
        device_name=device_name,
        ip=ip,
        user_agent=user_agent,
    )


def login_by_email():
    """
    邮箱登录
    """

    email = request.json['email']
    code = request.json['code']

    return auth_service.login_by_email(email, code)


def send_code():
    """
    发送验证码
    """
    email = request.json['email']

    if not config.ENABLED_REGISTER:
        raise AppException("请联系管理员开放注册")

    auth_service.send_verify_code_async(email)


@auth_service.permission(role=RoleEnum.USER)
def get_my_sessions():
    return {'list': auth_service.get_my_sessions(g.user_id)}


@auth_service.permission(role=RoleEnum.USER)
def logout_current_session():
    return auth_service.logout_current_session(g.user_id, g.session_id)


@auth_service.permission(role=RoleEnum.USER)
def logout_other_sessions():
    return auth_service.logout_other_sessions(g.user_id, g.session_id)


@auth_service.permission(role=RoleEnum.USER)
def logout_session_by_id():
    session_id = request.json.get('session_id')
    return auth_service.logout_session_by_id(g.user_id, session_id)

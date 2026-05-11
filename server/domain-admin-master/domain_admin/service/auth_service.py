# -*- coding: utf-8 -*-
"""
auth_service.py
"""
from __future__ import print_function, unicode_literals, absolute_import, division

from functools import wraps
from datetime import datetime, timedelta

from flask import g

from domain_admin.config import MAX_CONCURRENT_SESSIONS, SESSION_IDLE_TIMEOUT_MINUTES
from domain_admin.enums.role_enum import RoleEnum, ROLE_PERMISSION
from domain_admin.enums.status_enum import StatusEnum
from domain_admin.model.user_session_model import UserSessionModel
from domain_admin.model.user_model import UserModel
from domain_admin.service import token_service, notify_service, async_task_service
from domain_admin.utils import bcrypt_util, cache_util, validate_util, secret_util
from domain_admin.utils.flask_ext.app_exception import AppException


def _create_session_for_user(user_row, device_id='', device_name='', ip='', user_agent=''):
    """创建用户会话，并签发绑定 session_id 的 token"""
    session_id = secret_util.get_random_secret()
    token_jti = secret_util.get_random_secret()
    now = datetime.utcnow()
    expire_time = token_service.get_token_expire_time()

    UserSessionModel.create(
        user_id=user_row.id,
        session_id=session_id,
        token_jti=token_jti,
        device_id=(device_id or '')[:128],
        device_name=(device_name or '')[:128],
        ip=(ip or '')[:64],
        user_agent=(user_agent or '')[:512],
        is_active=True,
        login_time=now,
        last_active_time=now,
        expire_time=expire_time,
    )

    _enforce_session_limit(user_row.id)

    token = token_service.encode_token({
        'user_id': user_row.id,
        'sid': session_id,
        'jti': token_jti,
    })
    return token, session_id, expire_time


def _enforce_session_limit(user_id):
    """并发会话数控制：超限时自动回收最旧会话"""
    active_qs = (
        UserSessionModel.select()
        .where(
            (UserSessionModel.user_id == user_id)
            & (UserSessionModel.is_active == True)
        )
        .order_by(UserSessionModel.last_active_time.asc())
    )
    active_sessions = list(active_qs)
    if len(active_sessions) <= MAX_CONCURRENT_SESSIONS:
        return

    over_count = len(active_sessions) - MAX_CONCURRENT_SESSIONS
    to_revoke = active_sessions[:over_count]
    now = datetime.utcnow()
    for item in to_revoke:
        item.is_active = False
        item.revoked_time = now
        item.revoke_reason = 'concurrent_limit'
        item.save()


def login(username, password, device_id='', device_name='', ip='', user_agent=''):
    """
    用户登录
    :param username: 用户名
    :param password: 明文密码
    :return: string token
    """
    if not username:
        raise AppException('用户名不能为空')

    if not password:
        raise AppException('密码不能为空')

    user_row = UserModel.select().where(
        UserModel.username == username
    ).get_or_none()

    if not user_row:
        raise AppException('用户名或密码错误')

    if not bcrypt_util.check_password(password, user_row.password):
        raise AppException('用户名或密码错误')

    if not user_row.status:
        raise AppException('账号不可用')

    token, session_id, expire_time = _create_session_for_user(
        user_row=user_row,
        device_id=device_id,
        device_name=device_name,
        ip=ip,
        user_agent=user_agent,
    )
    return {
        'token': token,
        'session_id': session_id,
        'expire_time': str(expire_time),
    }


def register(username, password, password_repeat):
    """
    用户注册
    :param username: 用户名
    :param password: 明文密码
    :param password_repeat: 重复密码
    :return:
    """
    user_row = UserModel.select().where(
        UserModel.username == username
    ).get_or_none()

    if user_row:
        raise AppException('用户已存在')

    if password != password_repeat:
        raise AppException('密码不一致')

    return UserModel.create(
        username=username,
        password=bcrypt_util.encode_password(password)
    )


def permission(role=RoleEnum.ADMIN):
    """
    权限控制
    :param role:
    :return:
    """

    def outer_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if role is None:
                # 跳过权限校验
                pass
            else:
                current_user_id = g.user_id

                if not current_user_id:
                    raise AppException('用户未登录')

                user_row = UserModel.get_by_id(current_user_id)
                if not user_row:
                    raise AppException('用户不存在')

                if user_row.status != StatusEnum.Enabled:
                    raise AppException('用户已禁用')

                if not has_role_permission(current_role=user_row.role, need_permission=role):
                    raise AppException('暂无权限')

                # 当前用户数据全局可用
                g.current_user_row = user_row

            # execute
            ret = func(*args, **kwargs)

            return ret

        return wrapper

    return outer_wrapper


def has_role_permission(current_role, need_permission):
    """
    角色权限判断
    :param current_role:
    :param need_permission:
    :return:
    """
    if not need_permission:
        return True

    current_permission = []

    for item in ROLE_PERMISSION:
        if item['role'] == current_role:
            current_permission = item['permission']

    return need_permission in current_permission


@async_task_service.async_task_decorator("发送邮箱验证码")
def send_verify_code_async(email):
    send_verify_code(email)


def send_verify_code(email):
    if not validate_util.is_email(email):
        raise AppException('邮箱格式不正确')

    code = secret_util.get_random_password()

    cache_util.set_value(key=email, value=code, expire=5 * 60)

    notify_service.send_email_to_user(
        template='code-email.html',
        subject='验证码',
        data={'code': code},
        email_list=[email]
    )


def login_by_email(email, code):
    if not validate_util.is_email(email):
        raise AppException('邮箱格式不正确')

    if not code:
        raise AppException('验证码不能为空')

    cache_code = cache_util.get_value(email)

    if cache_code and code == cache_code:
        pass
    else:
        raise AppException('验证码不正确')

    user_row = UserModel.select().where(
        UserModel.username == email
    ).get_or_none()

    if not user_row:
        user_row = UserModel.create(
            username=email,
            password=''
        )

    token, session_id, expire_time = _create_session_for_user(user_row=user_row)
    return {
        'token': token,
        'session_id': session_id,
        'expire_time': str(expire_time),
    }


def validate_session(user_id, session_id, token_jti):
    """校验会话是否有效，并更新活动时间"""
    if not session_id or not token_jti:
        raise AppException('登录状态无效，请重新登录', code=401)

    row = UserSessionModel.select().where(
        (UserSessionModel.user_id == user_id)
        & (UserSessionModel.session_id == session_id)
        & (UserSessionModel.token_jti == token_jti)
    ).get_or_none()

    if not row:
        raise AppException('会话不存在，请重新登录', code=401)

    if not row.is_active:
        raise AppException('该会话已下线，请重新登录', code=401)

    if row.expire_time and row.expire_time < datetime.utcnow():
        row.is_active = False
        row.revoked_time = datetime.utcnow()
        row.revoke_reason = 'expired'
        row.save()
        raise AppException('会话已过期，请重新登录', code=401)

    row.last_active_time = datetime.utcnow()
    row.save()
    return row


def get_my_sessions(user_id):
    qs = (
        UserSessionModel.select()
        .where(UserSessionModel.user_id == user_id)
        .order_by(UserSessionModel.login_time.desc())
    )
    return [
        {
            'id': item.id,
            'session_id': item.session_id,
            'device_id': item.device_id,
            'device_name': item.device_name,
            'ip': item.ip,
            'is_active': bool(item.is_active),
            'login_time': str(item.login_time),
            'last_active_time': str(item.last_active_time),
            'expire_time': str(item.expire_time),
            'revoke_reason': item.revoke_reason,
        }
        for item in qs
    ]


def logout_current_session(user_id, session_id):
    row = UserSessionModel.select().where(
        (UserSessionModel.user_id == user_id)
        & (UserSessionModel.session_id == session_id)
        & (UserSessionModel.is_active == True)
    ).get_or_none()
    if not row:
        return {'msg': 'ok'}
    row.is_active = False
    row.revoked_time = datetime.utcnow()
    row.revoke_reason = 'logout_current'
    row.save()
    return {'msg': 'ok'}


def logout_session_by_id(user_id, session_id):
    row = UserSessionModel.select().where(
        (UserSessionModel.user_id == user_id)
        & (UserSessionModel.session_id == session_id)
    ).get_or_none()
    if not row:
        raise AppException('会话不存在')
    row.is_active = False
    row.revoked_time = datetime.utcnow()
    row.revoke_reason = 'logout_by_user'
    row.save()
    return {'msg': 'ok'}


def logout_other_sessions(user_id, current_session_id):
    now = datetime.utcnow()
    UserSessionModel.update(
        is_active=False,
        revoked_time=now,
        revoke_reason='logout_others',
    ).where(
        (UserSessionModel.user_id == user_id)
        & (UserSessionModel.session_id != current_session_id)
        & (UserSessionModel.is_active == True)
    ).execute()
    return {'msg': 'ok'}

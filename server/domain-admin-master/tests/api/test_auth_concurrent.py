# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

import uuid

from domain_admin.model.user_model import UserModel
from domain_admin.utils import bcrypt_util


def _json(resp):
    if hasattr(resp, "json") and isinstance(resp.json, dict):
        return resp.json
    return resp.get_json()


def _login(client, username, password, device_id):
    resp = client.post(
        "/api/login",
        json={"username": username, "password": password},
        headers={
            "x-device-id": device_id,
            "x-device-name": "pytest",
        },
    )
    return _json(resp)


def _ensure_user(username, password):
    row = UserModel.select().where(UserModel.username == username).get_or_none()
    if row:
        row.password = bcrypt_util.encode_password(password)
        row.status = True
        row.save()
        return row
    return UserModel.create(
        username=username,
        password=bcrypt_util.encode_password(password),
    )


def test_multi_user_concurrent_login(client):
    u1 = "u1_%s@test.local" % uuid.uuid4().hex[:8]
    u2 = "u2_%s@test.local" % uuid.uuid4().hex[:8]
    p1 = "pass123456"
    p2 = "pass123456"
    _ensure_user(u1, p1)
    _ensure_user(u2, p2)

    r1 = _login(client, u1, p1, "dev-u1")
    r2 = _login(client, u2, p2, "dev-u2")

    assert r1["code"] == 0
    assert r2["code"] == 0
    assert r1["data"]["token"] != r2["data"]["token"]

    s1 = client.post("/api/getMySessions", json={}, headers={"x-token": r1["data"]["token"]})
    s2 = client.post("/api/getMySessions", json={}, headers={"x-token": r2["data"]["token"]})
    j1 = _json(s1)
    j2 = _json(s2)
    assert j1["code"] == 0
    assert j2["code"] == 0
    assert len(j1["data"]["list"]) >= 1
    assert len(j2["data"]["list"]) >= 1


def test_logout_other_sessions_kicks_old_token(client):
    username = "u_%s@test.local" % uuid.uuid4().hex[:8]
    password = "pass123456"
    _ensure_user(username, password)

    first = _login(client, username, password, "dev-1")
    second = _login(client, username, password, "dev-2")
    assert first["code"] == 0
    assert second["code"] == 0

    # 在第二个会话上注销其它会话
    kick = client.post(
        "/api/logoutOtherSessions",
        json={},
        headers={"x-token": second["data"]["token"]},
    )
    assert _json(kick)["code"] == 0

    # 第一个会话应失效
    check_old = client.post(
        "/api/getMySessions",
        json={},
        headers={"x-token": first["data"]["token"]},
    )
    assert _json(check_old)["code"] == 401

    # 第二个会话仍可用
    check_new = client.post(
        "/api/getMySessions",
        json={},
        headers={"x-token": second["data"]["token"]},
    )
    assert _json(check_new)["code"] == 0

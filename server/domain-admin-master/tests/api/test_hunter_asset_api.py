# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from domain_admin.service import hunter_asset_service
from domain_admin.utils.flask_ext.app_exception import AppException


def _json(resp):
    if hasattr(resp, "json") and isinstance(resp.json, dict):
        return resp.json
    return resp.get_json()


def test_update_classified_asset_status_success(client, token, monkeypatch):
    monkeypatch.setattr(
        hunter_asset_service,
        "update_asset_penetration_status",
        lambda asset_id, is_completed: {
            "asset_id": int(asset_id),
            "penetration_status": "completed" if is_completed else "pending",
        },
    )

    resp = client.post(
        "/api/updateClassifiedAssetStatus",
        json={"asset_id": 1, "is_completed": True},
        headers={"x-token": token},
    )
    data = _json(resp)
    assert data["code"] == 0
    assert data["data"]["penetration_status"] == "completed"


def test_update_classified_asset_remark_success(client, token, monkeypatch):
    monkeypatch.setattr(
        hunter_asset_service,
        "update_asset_penetration_remark",
        lambda asset_id, remark: {
            "asset_id": int(asset_id),
            "penetration_remark": remark,
        },
    )

    resp = client.post(
        "/api/updateClassifiedAssetRemark",
        json={"asset_id": 2, "remark": "已完成验证"},
        headers={"x-token": token},
    )
    data = _json(resp)
    assert data["code"] == 0
    assert data["data"]["penetration_remark"] == "已完成验证"


def test_update_classified_asset_status_error_branch(client, token, monkeypatch):
    def _raise_error(asset_id, is_completed):
        raise AppException("更新失败")

    monkeypatch.setattr(hunter_asset_service, "update_asset_penetration_status", _raise_error)
    resp = client.post(
        "/api/updateClassifiedAssetStatus",
        json={"asset_id": 3, "is_completed": True},
        headers={"x-token": token},
    )
    data = _json(resp)
    assert data["code"] != 0


def test_update_classified_asset_remark_error_branch(client, token, monkeypatch):
    def _raise_error(asset_id, remark):
        raise AppException("保存失败")

    monkeypatch.setattr(hunter_asset_service, "update_asset_penetration_remark", _raise_error)
    resp = client.post(
        "/api/updateClassifiedAssetRemark",
        json={"asset_id": 4, "remark": "x"},
        headers={"x-token": token},
    )
    data = _json(resp)
    assert data["code"] != 0

# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import, division

from domain_admin.service import opencode_service


def _json(resp):
    if hasattr(resp, "json") and isinstance(resp.json, dict):
        return resp.json
    return resp.get_json()


def test_opencode_execute_and_query(client, token, monkeypatch):
    def fake_execute(prompt, context, user_id, task_name, retry_of_task_id=None, session_id=None):
        return {
            "session_id": "oc-session-1",
            "latency_ms": 88,
            "response": {"result": "ok"},
        }

    monkeypatch.setattr(opencode_service, "_sdk_execute", fake_execute)

    execute_resp = client.post(
        "/api/opencodeExecute",
        json={
            "task_name": "测试任务",
            "prompt": "请返回ok",
            "context": "ctx",
        },
        headers={"x-token": token},
    )
    execute_data = _json(execute_resp)
    assert execute_data["code"] == 0
    task_id = execute_data["data"]["id"]

    list_resp = client.post(
        "/api/opencodeTaskList",
        json={"page": 1, "size": 10},
        headers={"x-token": token},
    )
    list_data = _json(list_resp)
    assert list_data["code"] == 0
    assert list_data["data"]["total"] >= 1

    detail_resp = client.post(
        "/api/opencodeTaskDetail",
        json={"task_id": task_id},
        headers={"x-token": token},
    )
    detail_data = _json(detail_resp)
    assert detail_data["code"] == 0
    assert detail_data["data"]["task_name"] == "测试任务"


def test_opencode_retry_cancel_metrics(client, token, monkeypatch):
    def fake_execute(prompt, context, user_id, task_name, retry_of_task_id=None, session_id=None):
        return {
            "session_id": "oc-session-2",
            "latency_ms": 120,
            "response": {"result": "ok"},
        }

    monkeypatch.setattr(opencode_service, "_sdk_execute", fake_execute)
    monkeypatch.setattr(opencode_service, "_sdk_cancel", lambda session_id: {"cancelled": True})

    execute_resp = client.post(
        "/api/opencodeExecute",
        json={"task_name": "重试任务", "prompt": "hello"},
        headers={"x-token": token},
    )
    execute_data = _json(execute_resp)
    assert execute_data["code"] == 0
    task_id = execute_data["data"]["id"]

    retry_resp = client.post(
        "/api/opencodeRetryTask",
        json={"task_id": task_id},
        headers={"x-token": token},
    )
    retry_data = _json(retry_resp)
    assert retry_data["code"] == 0
    assert int(retry_data["data"]["retry_count"]) >= 1

    cancel_resp = client.post(
        "/api/opencodeCancelTask",
        json={"task_id": task_id},
        headers={"x-token": token},
    )
    cancel_data = _json(cancel_resp)
    assert cancel_data["code"] == 0

    metrics_resp = client.post(
        "/api/opencodeMetrics",
        json={},
        headers={"x-token": token},
    )
    metrics_data = _json(metrics_resp)
    assert metrics_data["code"] == 0
    assert "total" in metrics_data["data"]

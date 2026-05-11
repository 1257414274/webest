import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_driver import DBDriver
from config import Config

def test_config():
    config = Config()
    assert 'db' in config.config_data
    assert 'server' in config.config_data
    assert config.server['batch_size'] == 5000

@patch('db_driver.PooledDB')
def test_db_driver_init(mock_pooled_db):
    driver = DBDriver()
    mock_pooled_db.assert_called_once()

@patch('db_driver.PooledDB')
def test_db_execute_query(mock_pooled_db):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [{'id': 1}]
    
    mock_pooled_db.return_value.connection.return_value = mock_conn
    
    driver = DBDriver()
    res = driver.execute_query("SELECT 1")
    assert res == [{'id': 1}]

@patch('hunter_asset_classifier.call_deepseek')
def test_classifier_parse_ai(mock_call_deepseek):
    from hunter_asset_classifier import parse_ai_response
    mock_response = '```json\n{"admin_panels": [{"序号": 1, "confidence": 0.9}]}\n```'
    parsed = parse_ai_response(mock_response)
    assert 'admin_panels' in parsed
    assert parsed['admin_panels'][0]['confidence'] == 0.9


@pytest.mark.parametrize(
    "framework,raw_item",
    [
        ("SpringBoot", {"reason": "命中了/actuator/env路径且状态码200，Header中X-Powered-By: SpringBoot 2.3.x，响应出现activeProfiles字段，符合SpringBoot管理端点暴露特征。", "action": "[SAFE-POC] 目标URL:http://x/actuator/env; Header:User-Agent=SafeScanner; Payload:<NO-EXEC-CMD>; 成功判定:返回200且含activeProfiles"}),
        ("Struts2", {"reason": "命中/app/login.action路径，返回包包含struts字样且状态码200，结合历史路径特征与响应头Server信息，判定为Struts2应用入口。", "action": "1. OGNL表达式注入链路\n2. 文件上传到执行链路\n3. 鉴权绕过到后台链路"}),
        ("ThinkPHP", {"reason": "路径含/index.php?s=/home，响应头包含ThinkPHP关键字且状态码200，页面指纹与ThinkPHP默认路由规则一致，判定为ThinkPHP资产。", "action": "[SAFE-POC] 目标URL:http://x/index.php?s=/; 参数:s=; Payload:<NO-WRITE-FILE>; 成功判定:返回框架异常页或路由命中信息"}),
        ("WebLogic", {"reason": "命中/console/login/LoginForm.jsp并返回200，Header出现WebLogic标识，页面标题含Oracle WebLogic Server，符合中间件控制台特征。", "action": "[SAFE-POC] 目标URL:http://x/console/login/LoginForm.jsp; Header:User-Agent=SafeScanner; Payload:<NO-EXEC-CMD>; 成功判定:出现登录页面并识别版本信息"}),
        ("Fastjson", {"reason": "应用返回包中存在fastjson版本信息，接口状态码200，结合反序列化相关字段命中与组件名称，判定存在Fastjson攻击面。", "action": "[SAFE-POC] 目标URL:http://x/api/test; Header:Content-Type:application/json; Payload:<NO-EXEC-CMD>; 成功判定:响应出现反序列化异常关键字"}),
        ("Shiro", {"reason": "请求返回Set-Cookie含rememberMe字段且状态码200，Header和路径特征与Shiro鉴权组件一致，判定为Shiro安全框架资产。", "action": "[SAFE-POC] 目标URL:http://x/login; Header:Cookie=rememberMe=test; Payload:<NO-EXEC-CMD>; 成功判定:响应返回rememberMe删除或异常提示"}),
        ("Tomcat", {"reason": "命中/manager/html路径，状态码401并返回Tomcat realm认证信息，Server头包含Apache-Coyote，判断为Tomcat管理端口暴露。", "action": "[SAFE-POC] 目标URL:http://x/manager/html; Header:Authorization=Basic test; Payload:<NO-EXEC-CMD>; 成功判定:返回401/403且包含Tomcat Manager标识"}),
        ("Jenkins", {"reason": "命中/jenkins/login并返回200，页面标题显示Jenkins，Header存在X-Jenkins字段，证据链完整可判定为Jenkins服务。", "action": "[SAFE-POC] 目标URL:http://x/jenkins/script; Header:Jenkins-Crumb=test; Payload:<NO-EXEC-CMD>; 成功判定:接口返回脚本权限提示"}),
        ("GitLab", {"reason": "访问/users/sign_in状态码200，HTML中出现GitLab字样且响应头符合Rails应用特征，综合判断为GitLab登录资产。", "action": "[SAFE-POC] 目标URL:http://x/users/sign_in; Header:User-Agent=SafeScanner; Payload:<NO-WRITE-FILE>; 成功判定:页面返回authenticity_token字段"}),
        ("Nacos", {"reason": "命中/nacos/index.html状态码200，响应内容包含Nacos控制台标题，且Header/静态资源路径符合Nacos控制台特征。", "action": "[SAFE-POC] 目标URL:http://x/nacos/v1/auth/users/login; 参数:username=test; Payload:<NO-EXEC-CMD>; 成功判定:返回鉴权错误码或token字段"}),
    ],
)
def test_reason_action_completeness(framework, raw_item):
    from hunter_asset_classifier import _normalize_action, _normalize_framework, _normalize_reason

    item = dict(raw_item)
    item["framework"] = framework
    reason = _normalize_reason(item)
    action = _normalize_action(item)
    fw = _normalize_framework(item)

    assert fw == framework
    assert len(reason) >= 50
    assert any(token in reason for token in ["路径", "Header", "状态码", "响应", "端口"])
    lines = [line.strip() for line in action.splitlines() if line.strip()]
    assert len(lines) >= 2
    assert all(line.split(".")[0].isdigit() for line in lines)
    assert "[SAFE-POC]" not in action
    assert "Payload" not in action
    assert "目标URL" not in action

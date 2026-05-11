# -*- coding: utf-8 -*-
"""
@File    : default_config.py
@Date    : 2023-06-13
"""
from __future__ import print_function, unicode_literals, absolute_import, division

from domain_admin.utils import secret_util, md5_util
from domain_admin.version import VERSION

# 管理员默认的 账号，用户名
DEFAULT_ADMIN_USERNAME = 'webest666'
DEFAULT_ADMIN_PASSWORD = '8D673F2a!'

# header请求头中携带 token 参数名称
TOKEN_KEY = 'X-Token'

# header请求头中携带 language 参数名称
LANGUAGE_KEY = 'X-Language'

# 默认的token有效时长 单位：天
DEFAULT_TOKEN_EXPIRE_DAYS = 7

# 默认的过期提醒时间 单位：天
DEFAULT_BEFORE_EXPIRE_DAYS = 3

# 默认续期时间 单位：天
DEFAULT_RENEW_DAYS = 30

# secret_key
DEFAULT_SECRET_KEY = secret_util.get_random_secret()

# prometheus_key
DEFAULT_PROMETHEUS_KEY = md5_util.md5(DEFAULT_SECRET_KEY)

# 默认数据库链接
DEFAULT_DB_CONNECT_URL = "sqlite:///database/database.db"

# 默认的ssh连接端口
DEFAULT_SSH_PORT = 22

# 项目主页地址
PROJECT_HOME_URL = 'https://github.com/mouday/domain-admin'

# user agent
USER_AGENT = "Mozilla/5.0 (compatible; DomainAdmin/{version}; +{url})".format(
    version=VERSION,
    url=PROJECT_HOME_URL,
)

# 是否启用单点登录
OIDC_ENABLED = False

# Anthropic / Claude 默认配置
DEFAULT_ANTHROPIC_API_KEY = 'ed492a959a0245ed825debf248727ba1.dq6DdfLqRtVfKpZS'
DEFAULT_ANTHROPIC_BASE_URL = 'https://open.bigmodel.cn/api/anthropic'
DEFAULT_ANTHROPIC_MODEL = 'glm-5-turbo'
DEFAULT_ANTHROPIC_MAX_TOKENS = 2048

# OpenCode 默认配置
DEFAULT_OPENCODE_SERVER_URL = 'http://127.0.0.1:4096'
DEFAULT_OPENCODE_EXECUTE_PATH = '/v1/messages'
DEFAULT_OPENCODE_HEALTH_PATH = '/v1/models'
DEFAULT_OPENCODE_API_KEY = 'ed492a959a0245ed825debf248727ba1.dq6DdfLqRtVfKpZS'
DEFAULT_OPENCODE_TIMEOUT_SECONDS = 30
DEFAULT_OPENCODE_MAX_RETRIES = 2
DEFAULT_OPENCODE_PROVIDER_ID = 'zhipuai-coding-plan'
DEFAULT_OPENCODE_ANTHROPIC_MODEL = 'glm-5-turbo'
DEFAULT_OPENCODE_ANTHROPIC_MAX_TOKENS = DEFAULT_ANTHROPIC_MAX_TOKENS

# 登录会话控制（支持多设备并发）
DEFAULT_MAX_CONCURRENT_SESSIONS = 5
DEFAULT_SESSION_IDLE_TIMEOUT_MINUTES = 60 * 24 * 7

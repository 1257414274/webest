# 多用户并发登录认证方案（WeBest）

## 架构概览
- 认证模式升级为 `JWT + 会话表`：JWT 负责无状态鉴权，会话表负责状态控制与同步失效。
- 会话存储使用 MySQL 表 `tb_user_session`，天然支持多实例共享，满足分布式部署。
- 每次登录生成独立 `sid(session_id)` 和 `jti(token_jti)`，写入会话表并写入 JWT。

## 核心能力
- 多用户并发登录：不同用户互不影响，可同时在线。
- 多设备并发登录：同一用户可多个设备同时登录。
- 并发上限控制：`MAX_CONCURRENT_SESSIONS` 超限时自动回收最旧活跃会话。
- 会话同步失效：任一设备执行“退出其他设备”后，其他 token 立即失效。
- 会话有效性校验：每次请求校验 `user_id + sid + jti + is_active + expire_time`。

## 新增 API
- `POST /api/getMySessions`：查询当前用户会话列表
- `POST /api/logoutCurrentSession`：退出当前会话
- `POST /api/logoutOtherSessions`：退出其它设备会话
- `POST /api/logoutSessionById`：按会话 ID 踢出指定会话

## 登录请求头增强
- `X-Device-Id`：设备唯一标识（前端持久化）
- `X-Device-Name`：设备名称（如 `web` / `windows`）

## 配置项
- `MAX_CONCURRENT_SESSIONS`：同一用户最大并发会话数（默认 5）
- `SESSION_IDLE_TIMEOUT_MINUTES`：预留字段，当前主要使用 token 过期控制
- `TOKEN_EXPIRE_DAYS`：token 过期天数（沿用现有配置）

## 运维监控建议
- 关键指标：
  - 活跃会话数（按用户/全局）
  - 登录成功率、失败率
  - 会话失效原因分布（过期/主动退出/并发回收）
  - 401 鉴权失败趋势
- 告警建议：
  - 登录失败率异常升高
  - 单用户活跃会话异常暴增
  - 401 在 5 分钟窗口内突增

## 部署说明
1. 发布代码后自动创建 `tb_user_session`（由 peewee init_database 处理）。
2. 设置环境变量：
   - `MAX_CONCURRENT_SESSIONS=5`
   - `TOKEN_EXPIRE_DAYS=7`
3. 重启服务。
4. 验证：
   - 两个不同用户同时登录成功；
   - 同一用户双设备登录后执行“退出其他设备”，旧 token 失效。

## 兼容性说明
- 保持原有 `/api/login` 返回结构兼容，仍包含 `token`。
- 新增 `session_id`、`expire_time` 字段，旧前端不会受影响。

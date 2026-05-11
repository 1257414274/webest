# OpenCode 模块集成说明

## 概览
OpenCode 已作为 WeBest 的独立功能模块接入，当前采用 `OpenCode JS/TS SDK + Node bridge + Python service` 方案，统一走 WeBest 的 JWT 鉴权与权限控制。

## 后端模块
- 模型：`domain_admin/model/opencode_task_model.py`
- 服务：`domain_admin/service/opencode_service.py`
- API：`domain_admin/api/opencode_api.py`
- 路由：`domain_admin/router/api_map.py`
- SDK桥接：`opencode_sdk_bridge/bridge.mjs`
- SDK依赖：`opencode_sdk_bridge/package.json`

## 前端模块
- 页面：`frontend/src/views/opencode/index.vue`
- 路由：`frontend/src/router/index.ts`
- 菜单：`frontend/src/layout/index.vue`

## API 列表
- `POST /api/opencodeExecute`：执行 OpenCode 任务
- `POST /api/opencodeTaskList`：分页查询任务
- `POST /api/opencodeTaskDetail`：查询任务详情
- `POST /api/opencodeRetryTask`：重试任务
- `POST /api/opencodeCancelTask`：取消任务
- `POST /api/opencodeHealth`：服务健康检查
- `POST /api/opencodeMetrics`：当前用户任务统计
- `POST /api/opencodeStream`：SSE流式执行（实时返回思考/输出）

## 配置项（.env）
- `OPENCODE_SERVER_URL`：OpenCode Server 地址（必须 http/https，例如 `http://127.0.0.1:4096`）
- `OPENCODE_API_KEY`：服务鉴权 token（可选）
- `OPENCODE_TIMEOUT_SECONDS`：请求超时秒数
- `OPENCODE_ANTHROPIC_MODEL`：Anthropic 兼容模型名（默认跟随 `DEFAULT_ANTHROPIC_MODEL`）
- 默认模型已固定为 `glm-5-turbo`

## SDK桥接安装
1. 进入目录：`server/domain-admin-master/opencode_sdk_bridge`
2. 安装依赖：`npm install`
3. 若需手动验证：
   - 健康检查：`node bridge.mjs health`
   - 普通执行：`node bridge.mjs execute`
   - 流式执行：`node bridge.mjs stream`

## Anthropic 适配
- 通过 OpenCode Server 内的 provider 配置接入 Anthropic 兼容模型。
- `OPENCODE_SERVER_URL` 必须是 OpenCode Server，不可直接填 `https://open.bigmodel.cn/api/anthropic`。
- 通过 SDK `auth.set({ id: "anthropic", key })` 注入密钥。
- 通过 SDK `session.prompt` 传入模型：
  - `providerID: "anthropic"`
  - `modelID: "glm-5-turbo"`

## SSE 流式输出
- OpenCode 页面支持 `SSE流式执行` 按钮。
- 后端流式链路：`event.subscribe -> bridge.ndjson -> Flask SSE`。
- 流式事件：
  - `thinking`：模型思考片段
  - `delta`：正文增量输出
  - `error`：错误信息
  - `done`：完成标记

## 数据隔离与安全
- 所有任务数据按 `user_id` 隔离，禁止跨用户读取。
- 服务请求支持 `Bearer Token`，推荐在 HTTPS 下部署 OpenCode 服务。
- 任务执行、重试、取消都记录状态，便于审计与追踪。

## 使用方式
1. 在左侧菜单进入 `OpenCode`。
2. 输入 `任务名称 / Prompt / 上下文`，点击“执行任务”。
3. 在任务列表中查看状态、重试或取消任务。
4. 点击“详情”可查看请求与响应载荷。

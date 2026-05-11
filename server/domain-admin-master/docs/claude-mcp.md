# Claude + MCP 集成说明

## 概览
本模块为 WeBest 的 Anthropic SDK 集成增强版本，支持 Claude 通过 MCP 工具自动执行：
- 浏览器自动化（网页抓取、链接提取、HTTP 请求）
- 文件系统操作（读写文件、列目录、搜索文件）
- 数据库操作（列出表结构、只读 SQL 查询）
- API 调用（通用 REST API / Hunter API）
- 系统命令执行（带危险命令拦截）

## 主要后端模块
- `domain_admin/service/mcp/mcp_registry.py`: 工具注册、发现、健康统计
- `domain_admin/service/mcp/mcp_loader.py`: 动态加载 MCP 工具，支持环境变量控制
- `domain_admin/service/mcp/tool_*.py`: 各工具适配器
- `domain_admin/service/claude_service.py`: Claude 对话 + tool_use 多轮调度
- `domain_admin/api/claude_api.py`: Claude API 接口

## 已实现 API
- `POST /api/createClaudeConversation`
- `POST /api/getClaudeConversations`
- `POST /api/getClaudeMessages`
- `POST /api/sendClaudeMessage`
- `POST /api/deleteClaudeConversation`
- `POST /api/getClaudeMcpStatus`

## 环境变量
- `ANTHROPIC_API_KEY`: Anthropic API Key
- `ANTHROPIC_BASE_URL`: 可选，自定义网关地址（必须带 http/https）
- `ANTHROPIC_MODEL`: 默认模型，建议以 `claude` 开头
- `ANTHROPIC_MAX_TOKENS`: 每次回答最大 token
- `MCP_ENABLED_TOOLS`: 可选，按分类启用工具，逗号分隔
  - 示例：`filesystem,database,browser,system,api`

## 快速使用示例
1. 启动后端和前端。
2. 登录后进入左侧 `Claude` 页面。
3. 提问如：
   - 请读取 `frontend/src/router/index.ts` 并总结路由结构
   - 请列出数据库所有表并展示 `tb_hunter_asset` 字段
   - 请抓取 https://example.com 页面标题和主要内容
4. Claude 会自动触发 MCP 工具，前端可看到工具调用结果摘要。

## 安全策略
- 文件系统访问限制在项目目录内，防止路径穿越
- 数据库仅允许只读查询（拦截写操作）
- 系统命令工具有危险命令拦截与超时控制
- API 工具默认超时与错误捕获

## 健康检查
调用 `POST /api/getClaudeMcpStatus` 可查看：
- MCP 是否成功加载
- 已注册工具列表
- 每个工具调用次数、错误率、最近延迟

## 向后兼容
原有 Claude 接口保持不变，新增 MCP 功能不会影响旧调用方式。

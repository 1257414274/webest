# 作战协同平台 - 资产智能分类模块 (服务端版)

该模块负责从数据库中定期拉取 `pending` 状态的测绘资产数据，调用 DeepSeek 大模型进行战术级攻击面分析，识别高危端口、管理后台和高危应用，并将分类与置信度结果通过 UPSERT 事务回写到数据库，便于其他模块调度使用。

## 服务端部署与运维

### 环境准备

1. Python 3.10+
2. 安装依赖：
   ```bash
   pip install -r requirements-server.txt
   ```

### 数据库配置

推荐使用 MySQL 5.7+，可以通过提供的 docker-compose 文件快速启动测试库：
```bash
docker-compose up -d
```

### 配置文件 (config.yaml)

在项目根目录下修改 `config.yaml` 文件配置数据库连接与策略：
```yaml
db:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "123456"
  database: data
  pool_size: 10
  timeout: 30

server:
  batch_size: 5000
  confidence_threshold: 0.85
  cache_ttl: 300

log:
  level: INFO
  format: "[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d - %(message)s"
  file: "logs/classifier_server_%Y%m%d.log"
```

### 启动服务

```bash
# 执行服务端处理流程（将会初始化数据库并开启批量处理）
python hunter_asset_classifier.py
```

终端将会使用 tqdm 显示实时进度条、剩余时间与均值准确率。异常发生时，单条异常不会阻断整体执行，数据将被送入 `tactic_dead_letter` 表。

### 回滚方案

如果运行过程中出现环境崩溃或脏数据，可以通过以下步骤恢复：
1. 本程序的入库采用 `UPSERT` 原子操作，如果中途失败，数据库层面事务会自动回滚批次（默认5000/批）。
2. 对于完全无法恢复的死信记录，可以查询 `tactic_dead_letter` 拿到 `asset_id` 与报错原因。
3. 可手动将 `tactic_classification` 中的错误分类状态改回 `pending`，重启服务即可自动重试。

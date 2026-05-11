#!/usr/bin/env python3
"""
作战协同平台 - 资产智能分类模块
从数据库读取待分类资产，调用 DeepSeek 思考模型进行战术级分类：
  - 管理后台（登录页、后台入口）
  - 高危应用（已知风险产品）
  - 高危端口（SSH/FTP/数据库等）
并将分类结果回写数据库。
"""

import argparse
import json
import sys
import time
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
import traceback

from tqdm import tqdm
from openai import OpenAI

from config import config
from db_driver import db, init_db

# ============================================================
# 配置
# ============================================================
DEEPSEEK_API_KEY = "sk-4401440412584cff8b2722477e3bdb30"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"

# 请求超时
REQUEST_TIMEOUT = 90

# 初始化日志
log_conf = config.log
logging.basicConfig(
    level=getattr(logging, log_conf.get('level', 'INFO').upper()),
    format=log_conf.get('format', '[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d - %(message)s'),
    handlers=[
        logging.FileHandler(time.strftime(log_conf.get('file', 'logs/classifier_server_%Y%m%d.log'))),
        logging.StreamHandler(sys.stdout)
    ]
)

SYSTEM_PROMPT = """# 角色设定
你是一名具备10年+实战经验的红队攻防专家、漏洞挖掘专家和网络安全专家。

# 核心要求（非常重要）
保持原有分类逻辑不变：继续按既有的三类分类体系、关键词命中规则、风险标签规则、优先级定义执行，不得删减或改写原判断标准。

# 任务
分析网络空间测绘资产数据，从红队攻击者视角识别高价值攻击目标，按以下三类输出：
- admin_panels（管理后台）
- high_risk_apps（高危应用）
- high_risk_ports（高危端口）

---

## 分类一：管理后台
识别所有 Web 管理入口、登录页面、控制台、后台系统。

**URL特征关键词（不区分大小写）：**
- 路径含: admin, manage, login, console, dashboard, control, cpanel, backend, system, panel, cros, user, auth, signin, signup, register, password, reset, entry, portal, main, index, home, setup, install, config, setting, debug, monitor, status, health, info, test, dev, api-docs, swagger, graphql, actuator, druid, trace, env, heapdump
- 常见后台路径: /wp-admin, /wp-login, /administrator, /phpmyadmin, /adminer, /manager/html, /console, /solr, /kibana, /grafana, /jenkins, /geoserver, /geonetwork, /railsserver, /sitecore, /umbraco, /orchard, /nacos, /sentinel, /dubbo, /skywalking, /zipkin, /apollo, /xxl-job, /xxlconf, /canal, /seata, /spring-cloud, /eureka, /config, /gateway

**标题特征关键词（不区分大小写）：**
- 登录, 管理, 后台, 控制台, 系统, 监控, 配置, 面板, 平台, 中心
- Login, Admin, Dashboard, Console, Panel, Management, Control, Monitor, System, Platform, Portal, Center, Setup, Install, Welcome, Index, Home
- 特殊: 请输入密码, Please enter, Sign in, 用户登录, 系统登录, 身份验证

**产品特征：**
- CMS后台: WordPress(wp-admin), Drupal(/admin), Joomla(/administrator), DedeCMS(/dede), ThinkPHP, BlueCMS
- 数据库管理: phpMyAdmin, Adminer, Mongo Express, Redis Commander, PGAdmin
- 服务器管理: cPanel, Plesk, Webmin, BT Panel(宝塔), AMH, WDCP, LuManager
- 容器/云: Kubernetes Dashboard, Portainer, Rancher, OpenShift, Nomad
- DevOps: Jenkins, GitLab, Gitea, Gogs, Drone CI, Travis, Bamboo, TeamCity
- 文件管理: AList, FileManager, KodExplorer, Seafile, Nextcloud
- 监控面板: Grafana, Zabbix, Prometheus, Kibana, Nagios, Cacti
- API文档: Swagger UI, Knife4j, Showdoc, YApi, Rap, ApiFox, GraphQL Playground
- 远程访问: Guacamole, Apache Guacamole, noVNC, WebSSH, Terminal
- IoT/工控: IoT管理面板, PLC管理界面, SCADA系统
- VPN: OpenVPN Access Server, WireGuard Admin
- 邮件: Roundcube, RainLoop, Mailcow, iRedAdmin
- OA/ERP: 致远OA, 泛微OA, 畅捷通, 用友, 金蝶, 致远, 蓝凌

---

## 分类二：高危应用
识别运行已知风险产品/组件/框架的资产，这些是红队首选攻击面。

**框架/中间件（重点关注历史RCE漏洞）：**
- Java系: SpringBoot(actuator), WebLogic, JBoss, Tomcat, WebSphere, Struts2, Shiro, Fastjson, Log4j2, Dubbo, Resin, GlassFish, Jetty, Undertow, WildFly
- .NET系: IIS, Exchange, SharePoint, DotNetNuke, Umbraco, SiteCore, Orchard
- PHP系: ThinkPHP, Laravel, CodeIgniter, Yii, CakePHP, Slim, Symfony, Zend
- Python系: Django(admin), Flask(debug), FastAPI(docs), Celery(Flower), Jupyter Notebook
- Node系: Express, Next.js(dev), Nuxt.js(dev), Vite(dev)
- Go系: Gin(debug), Beego(admin)

**数据存储（重点关注未授权访问）：**
- ElasticSearch(9200), MongoDB(27017), Redis(6379), Memcached(11211)
- CouchDB(5984), Cassandra(9042), HBase(16010), Neo4j(7474)
- InfluxDB(8086), ClickHouse(8123), TiDB(10080), TDengine(6041)
- MySQL(3306), PostgreSQL(5432), MSSQL(1433), Oracle(1521)

**消息队列/注册中心（重点关注未授权+RCE）：**
- Nacos(8848), Apollo(8070), Sentinel(8080), Spring Cloud Config
- RabbitMQ(15672), Kafka(9092), ActiveMQ(8161), RocketMQ(9876)
- ZooKeeper(2181), Consul(8500), Etcd(2379), Eureka(8761)
- XXL-Job(8080/9999), XXL-Conf, Canal(11111), Seata(8091)

**CI/CD/DevOps（重点关注命令执行）：**
- Jenkins, GitLab CE/EE, Gitea, Gogs, Drone CI, Tekton, ArgoCD
- Harbor(443), Nexus Repository, Artifactory, SonarQube, Gitbucket
- Docker Registry(5000/5044), Quay, ChartMuseum

**监控/日志（重点关注信息泄露+SSRF）：**
- Grafana(3000), Kibana(5601), Zabbix(80/10051), Prometheus(9090)
- SkyWalking(8080), Zipkin(9411), Jaeger(16686), Pinpoint
- ELK Stack, Splunk(8000), Graylog(9000), Loki(3100)

**文档/知识库（重点关注未授权+文件上传）：**
- Swagger UI, Showdoc, YApi, Rap, Wiki.js, Confluence
- MinIO(9000/9001), HDFS(9870), YARN(8088), Spark(8080/4040)

**开发调试工具暴露（高风险信号）：**
- Vite Dev Server, Webpack Dev Server, Django Debug Toolbar
- PHPInfo页面, ASP.NET错误页, Tomcat Manager, JBoss Admin
- Actuator(env/heapdump/trace/mappings/beans), Druid Monitor
- SpringBoot Admin, Arthas, JConsole, VisualVM

---

## 分类三：高危端口
识别暴露在公网的非Web高风险端口服务。

**远程控制（最高优先级）：**
- 22(SSH), 23(Telnet), 3389(RDP), 5900(VNC), 5985/5986(WinRM)
- 2222(SSH备用), 22222(SSH备用), 443(OpenVPN), 1194(OpenVPN)
- 5500(VNC备用), 5800(noVNC), 6667(IRC), 6000-6010(X11)

**数据库（核心目标）：**
- 3306(MySQL), 5432(PostgreSQL), 1433(MSSQL), 1521(Oracle)
- 27017/27018(MongoDB), 6379(Redis), 9200/9300(ElasticSearch)
- 11211(Memcached), 5984(CouchDB), 7001(Cassandra)
- 9042(Cassandra CQL), 8086(InfluxDB), 8123(ClickHouse)
- 5000(Sybase/DB2), 5234(达梦), 1830(Neo4j Bolt)

**文件共享/传输：**
- 21(FTP), 69(TFTP), 445(SMB/CIFS), 139(NetBIOS)
- 2049(NFS), 873(Rsync), 22(SSH/SFTP)
- 20(FTP数据), 989/990(FTPS)

**目录服务：**
- 389(LDAP), 636(LDAPS), 3268/3269(AD全局目录)
- 88(Kerberos), 464(Kerberos密码修改), 749(Kerberos admin)

**邮件服务（信息收集/钓鱼）：**
- 25(SMTP), 110(POP3), 143(IMAP), 465(SMTPS), 993(IMAPS), 995(POP3S)
- 587(SMTP提交), 2525(SMTP备用)

**容器/编排：**
- 2375/2376(Docker API), 5000(Registry), 443(K8s API)
- 10250(Kubelet), 30000-32767(K8s NodePort), 2380(Etcd)

**大数据：**
- 9000(HDFS), 8088(YARN), 9870(HDFS Web), 16010(HBase)
- 9092(Kafka), 2181(ZooKeeper), 7077(Spark), 8081(Flink)
- 10000(HiveServer2), 9083(Hive Metastore)

**工控/SCADA（特殊关注）：**
- 502(Modbus), 102(S7comm), 4840(OPC UA), 20000(DNP3)
- 1911(CIP), 2222/4840(EtherNet/IP), 789/7923(IEC 104)

---

# 风险优先级定义（沿用）
- P0-致命: 可直接远程未授权获取系统权限
- P1-高危: 可获取敏感信息或绕过认证
- P2-中危: 需组合利用或特定条件
- P3-低危: 信息收集价值

# 在原有输出基础上新增字段（仅新增，不改变原字段）
每条结果必须新增并返回：
- reason: 判断逻辑（不少于50字，必须包含命中路径/关键Header/状态码/端口或响应包证据）
- framework: 识别框架或组件名称（如 SpringBoot/Struts2/ThinkPHP/WebLogic/Fastjson 等）
- action: 仅返回“可能存在的攻击路径”，可返回多条，可返回操作指令、命令、Payload、步骤或成功判定描述。

# 输出格式
严格返回JSON，不要输出任何其他文字：
{
  "admin_panels": [
    {
      "序号": 1,
      "链接": "http://...",
      "网站标题": "...",
      "风险标签": "管理后台",
      "优先级": "P1-高危",
      "framework": "SpringBoot",
      "reason": "命中了 /api/v1/admin 路径，响应状态码200，Header出现X-Powered-By: SpringBoot，且页面含管理入口关键词，综合判定为SpringBoot后台资产，建议优先验证未授权接口与暴露端点。",
      "action": "1. Actuator端点未授权访问\n2. 敏感配置泄露路径\n3. 默认口令或弱口令登录路径",
      "攻击面": "未授权访问/弱口令/默认凭据",
      "建议操作": "与 action 含义一致的简述",
      "备注": "可选"
    }
  ],
  "high_risk_apps": [
    {
      "序号": 1,
      "产品名称": "...",
      "厂商名称": "...",
      "风险标签": "护网行动,两高一弱",
      "优先级": "P0-致命",
      "framework": "Struts2",
      "reason": "命中 .action 路径特征且状态码200，Header与响应内容均出现Struts2相关特征字段，结合历史漏洞面判定为高危应用资产，需优先执行无害化验证。",
      "action": "1. 历史RCE漏洞利用路径（如OGNL表达式链）\n2. 上传点到代码执行链路\n3. 鉴权绕过到后台管理链路",
      "攻击面": "历史RCE漏洞检测面",
      "建议操作": "与 action 含义一致的简述",
      "备注": "可选"
    }
  ],
  "high_risk_ports": [
    {
      "序号": 1,
      "风险标签": "红队攻防,两高一弱,运维管控",
      "优先级": "P1-高危",
      "IP地址": "x.x.x.x",
      "端口": 22,
      "协议": "tcp",
      "服务": "ssh",
      "产品": "OpenSSH",
      "版本": "8.0",
      "framework": "OpenSSH",
      "reason": "公网开放22端口，握手响应可识别OpenSSH banner，连接状态可达，结合远程管理面暴露风险判定为高危端口资产，建议优先执行基线与口令策略验证。",
      "action": "1. 弱口令爆破登录路径\n2. 版本漏洞利用路径\n3. 凭据复用横向移动路径",
      "攻击面": "弱口令/版本漏洞",
      "建议操作": "与 action 含义一致的简述",
      "备注": "可选"
    }
  ]
}

# 约束
- 每条资产只归入一个最匹配类别（沿用原逻辑）。
- 风险标签沿用原选项与规则。
- 优先级排序沿用原规则：同一资产命中多个攻击面时取最高优先级。
- reason/framework/action 为必填；reason 少于50字视为无效输出。
- action 只允许输出攻击路径，建议使用编号列表（如“1. ...\n2. ...”），至少 2 条。
- action 中禁止出现命令、Payload、利用步骤、成功判定、[SAFE-POC]、<NO-EXEC-CMD> 等执行性内容。
- 只返回JSON，不要解释性文字。
"""


def fetch_assets(batch_size=5000, since_time=None, total_limit=0):
    """
    按批次拉取待分类资产数据
    仅读取状态为 “pending” 且 create_time 在 7 天内的记录
    """
    effective_since = since_time or (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    
    # 假设待分类资产存储在 tb_hunter_asset 表中，但为了满足要求，我们需要：
    # 状态为 "pending" 且 create_time 在 7 天内的记录。
    # 这里我们通过 LEFT JOIN tactic_classification tc 来判断是否已分类。
    # 如果 tc.status is null 或 tc.status = 'pending'，则认为是 pending。
    
    sql = """
        SELECT ha.id as asset_id, ha.ip, ha.port, ha.domain, ha.url, ha.web_title, 
               ha.company, ha.update_time as last_update_time
        FROM tb_hunter_asset ha
        LEFT JOIN tactic_classification tc ON ha.id = tc.asset_id
        WHERE ha.create_time >= %s
        AND (tc.status IS NULL OR tc.status = 'pending')
        LIMIT %s
    """
    
    offset = 0
    cache = {}
    
    yielded_count = 0
    while True:
        current_fetch_size = int(batch_size)
        if total_limit and total_limit > 0:
            remain = int(total_limit) - yielded_count
            if remain <= 0:
                break
            current_fetch_size = min(current_fetch_size, remain)

        # 添加 offset，或者简单的如果每次拿没处理的就不用 offset，这里用 offset 保险
        fetch_sql = sql.replace("LIMIT %s", f"LIMIT %s OFFSET {offset}")
        rows = db.execute_query(fetch_sql, (effective_since, current_fetch_size))
        
        if not rows:
            break
            
        yield rows
        offset += len(rows)
        yielded_count += len(rows)
        
        # 缓存逻辑 (简单实现 TTL 300s)
        current_time = time.time()
        for row in rows:
            cache[row['asset_id']] = (row, current_time)
            
        # 清理过期缓存
        expired_keys = [k for k, v in cache.items() if current_time - v[1] > config.server.get('cache_ttl', 300)]
        for k in expired_keys:
            del cache[k]


def format_batch_for_ai(batch: list[dict], batch_idx: int) -> str:
    """将一批资产格式化为AI可读的文本"""
    lines = [f"以下第 {batch_idx + 1} 批资产数据，共 {len(batch)} 条：\n"]
    for i, asset in enumerate(batch):
        core_fields = {
            "ip": asset.get("ip", ""),
            "port": asset.get("port", ""),
            "domain": asset.get("domain", ""),
            "url": asset.get("url", ""),
            "web_title": asset.get("web_title", ""),
            "protocol": asset.get("protocol", ""),
            "base_protocol": asset.get("base_protocol", ""),
            "banner": (asset.get("banner", "") or "")[:1000],
            "body": (asset.get("body", "") or "")[:500],
            "header_server": asset.get("header_server", ""),
            "header": (asset.get("header", "") or "")[:500],
            "component": asset.get("component", ""),
            "status_code": asset.get("status_code", ""),
            "os": asset.get("os", ""),
            "is_web": asset.get("is_web", ""),
            "ssl_certificate": (asset.get("ssl_certificate", "") or "")[:200],
            "as_org": asset.get("as_org", ""),
            "isp": asset.get("isp", ""),
            "ip_tag": asset.get("ip_tag", ""),
        }
        lines.append(f"[{i + 1}] {json.dumps(core_fields, ensure_ascii=False)}")
    return "\n".join(lines)


# 复用OpenAI客户端
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _client


def call_deepseek(messages: list[dict]) -> str:
    """调用DeepSeek，优先使用非流式响应，避免长时间卡在流式迭代"""
    client = _get_client()

    for attempt in range(1, 4):
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                stream=False,
                timeout=REQUEST_TIMEOUT,
            )
            elapsed = time.time() - t0
            content = (response.choices[0].message.content or "").strip()
            logging.info(
                "DeepSeek返回成功，耗时 %.1fs，内容预览: %s",
                elapsed,
                content[:300].replace("\n", " "),
            )
            return content
        except Exception as e:
            wait = attempt * 5
            logging.warning("第%s次调用DeepSeek失败: %s，%ss后重试", attempt, e, wait)
            time.sleep(wait)

    raise RuntimeError("DeepSeek连续3次调用失败")


def parse_ai_response(content: str) -> dict:
    """从AI回复中提取JSON"""
    # 尝试直接解析
    text = content.strip()

    # 去掉可能的 markdown 代码块包裹
    if text.startswith("```"):
        lines = text.split("\n")
        # 跳过 ```json 和末尾的 ```
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # 找到 JSON 的起止位置
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        return json.loads(json_str)

    logging.error("DeepSeek原始响应无法提取JSON，内容预览: %s", text[:500])
    raise ValueError(f"无法从AI回复中提取JSON: {text[:200]}")


def _pick(item: dict, keys: list[str], default=""):
    for k in keys:
        if k in item and item.get(k) not in (None, ""):
            return item.get(k)
    return default


def _safe_text(value, fallback=""):
    if value is None:
        return fallback
    return str(value).strip() or fallback


def _normalize_reason(item: dict) -> str:
    reason = _safe_text(_pick(item, ["reason", "判断逻辑", "备注"]), "")
    if len(reason) < 50:
        reason = (
            "命中资产特征后证据不足，已降级为待人工复核。当前仅识别到基础指纹，"
            "建议结合路径、Header、状态码与响应包进行二次验证后再执行深入测试。"
        )
    return reason


def _normalize_framework(item: dict) -> str:
    return _safe_text(_pick(item, ["framework", "框架", "产品名称", "产品"]), "Unknown")


def _normalize_action(item: dict) -> str:
    raw = _pick(item, ["action", "操作建议", "建议操作", "攻击路径", "attack_paths"], "")
    candidates = []

    if isinstance(raw, list):
        for v in raw:
            text = _safe_text(v, "")
            if text:
                candidates.append(text)
    else:
        text = _safe_text(raw, "")
        # 清理常见提示词或执行性标记，保留“攻击路径”语义文本
        text = re.sub(r"\[SAFE-POC\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<NO-[A-Z-]+>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(目标URL|Header|Payload|成功判定)\s*[:：].*", "", text, flags=re.IGNORECASE)
        if text:
            parts = re.split(r"[\n;；|]+", text)
            candidates.extend(parts)

    cleaned = []
    for p in candidates:
        p = re.sub(r"^\s*\d+[\.、\)]\s*", "", _safe_text(p, ""))
        p = re.sub(r"^\s*[-*]\s*", "", p)
        p = p.strip("，,。;； ")
        if not p:
            continue
        if p not in cleaned:
            cleaned.append(p)

    # 若模型未给出可用路径，则尝试从攻击面字段回退
    if not cleaned:
        attack_surface = _safe_text(_pick(item, ["攻击面", "attack_surface"]), "")
        if attack_surface:
            for token in re.split(r"[\/、,，\|]+", attack_surface):
                t = _safe_text(token, "")
                if t and t not in cleaned:
                    cleaned.append(t)

    if not cleaned:
        cleaned = ["未授权访问路径", "弱口令/默认凭据路径", "历史漏洞利用路径"]

    return "\n".join(f"{idx + 1}. {path}" for idx, path in enumerate(cleaned[:6]))


def classify_batch(batch: list[dict], batch_idx: int) -> dict:
    """对一批资产调用AI进行分类"""
    user_content = format_batch_for_ai(batch, batch_idx)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    logging.info(f"  [批次{batch_idx + 1}] 发送 {len(batch)} 条资产到DeepSeek...")
    try:
        raw = call_deepseek(messages)
        result = parse_ai_response(raw)
        
        # 处理置信度阈值和状态
        threshold = config.server.get('confidence_threshold', 0.85)
        for category in ["admin_panels", "high_risk_apps", "high_risk_ports"]:
            if category in result:
                for item in result[category]:
                    # 模拟一个置信度(实际API需要配置返回，这里如果没有就默认1.0)
                    confidence = float(item.get("置信度", 1.0))
                    item["confidence"] = confidence
                    if confidence < threshold:
                        item["status"] = "uncertain"
                    else:
                        item["status"] = "classified"
                    item["reason"] = _normalize_reason(item)
                    item["framework"] = _normalize_framework(item)
                    item["action"] = _normalize_action(item)
                    if not _safe_text(item.get("建议操作"), ""):
                        item["建议操作"] = item["action"]
                    if not _safe_text(item.get("备注"), ""):
                        item["备注"] = item["reason"]
                        
        return result
    except Exception as e:
        logging.error(f"批次 {batch_idx + 1} 分类异常: {e}\n{traceback.format_exc()}")
        # 返回空结果以防中断
        return {"admin_panels": [], "high_risk_apps": [], "high_risk_ports": []}

def write_results_to_db(results: dict, batch: list[dict]):
    """将结果回写数据库，支持 UPSERT 和失败重试"""
    # 建立序号与资产ID的映射
    idx_to_id = {i + 1: asset['asset_id'] for i, asset in enumerate(batch)}
    
    upsert_sql = """
        INSERT INTO tactic_classification (
            asset_id, predicted_tactic, confidence, status,
            priority, reason, framework, action,
            suggestion, risk_tag, attack_surface, remark,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE 
            predicted_tactic = VALUES(predicted_tactic),
            confidence = VALUES(confidence),
            status = VALUES(status),
            priority = VALUES(priority),
            reason = VALUES(reason),
            framework = VALUES(framework),
            action = VALUES(action),
            suggestion = VALUES(suggestion),
            risk_tag = VALUES(risk_tag),
            attack_surface = VALUES(attack_surface),
            remark = VALUES(remark),
            updated_at = CURRENT_TIMESTAMP
    """
    
    args_list = []

    def _seq_of(item):
        for key in ("序号", "序 号", "序 号 ", "sequence", "seq"):
            if key in item:
                return item.get(key)
        return None
    
    for category in ["admin_panels", "high_risk_apps", "high_risk_ports"]:
        for item in results.get(category, []):
            seq = _seq_of(item)
            if seq in idx_to_id:
                asset_id = idx_to_id[seq]
                tactic = category
                confidence = item.get("confidence", 1.0)
                status = item.get("status", "classified")
                priority = str(item.get("优先级", "") or "").strip()
                reason = _normalize_reason(item)
                framework = _normalize_framework(item)
                action = _normalize_action(item)
                suggestion = str(item.get("建议操作", "") or action).strip()
                risk_tag = str(item.get("风险标签", "") or "").strip()
                attack_surface = str(item.get("攻击面", "") or "").strip()
                remark = str(item.get("备注", "") or reason).strip()
                args_list.append((
                    asset_id, tactic, confidence, status,
                    priority, reason, framework, action,
                    suggestion, risk_tag, attack_surface, remark
                ))
                
    if not args_list:
        return 0

    # 回写前参数数量自检，避免 SQL 占位符数量与实参数量不一致导致隐晦报错
    placeholder_count = upsert_sql.count("%s")
    first_arg_len = len(args_list[0]) if args_list else 0
    if placeholder_count != first_arg_len:
        sample_asset_id = str(args_list[0][0]) if args_list and args_list[0] else "-"
        logging.error(
            "回写SQL参数自检失败: 占位符=%s, 参数数=%s, sample_asset_id=%s, sql_head=%s",
            placeholder_count,
            first_arg_len,
            sample_asset_id,
            " ".join(upsert_sql.strip().split())[:220],
        )
        return 0
        
    # 尝试写入数据库，带重试机制
    retries = 3
    for attempt in range(retries):
        try:
            rowcount = db.execute_many(upsert_sql, args_list)
            return len(args_list) # 返回实际影响的条目数
        except Exception as e:
            if attempt < retries - 1:
                logging.warning(f"回写数据库失败，重试中 ({attempt+1}/{retries})...")
                time.sleep(2)
            else:
                logging.error(f"回写数据库彻底失败: {e}")
                # 写入死信表
                dead_letter_sql = "INSERT INTO tactic_dead_letter (asset_id, error_msg) VALUES (%s, %s)"
                dead_letter_args = [(str(arg[0]), str(e)) for arg in args_list]
                try:
                    db.execute_many(dead_letter_sql, dead_letter_args)
                    logging.info(f"已将 {len(dead_letter_args)} 条失败记录写入死信表")
                except Exception as dle:
                    logging.error(f"写入死信表失败: {dle}")
                return 0

def classify_all_assets(since_time=None, total_limit=0):
    """分批分类全部资产并更新数据库"""
    t_start = time.time()
    
    batch_size = config.server.get('batch_size', 5000)
    
    # 由于 DeepSeek 推理能力限制，我们实际发送给 AI 的小批次可能需要更小
    ai_batch_size = 30 # 保持原有的较小批次给AI，如 30~500
    
    total_processed = 0
    total_written = 0
    total_anomalies = 0
    total_confidence = 0.0
    recent_confidences = []
    
    # 获取总数用于 tqdm
    try:
        count_sql = """
            SELECT count(*) as total FROM tb_hunter_asset ha
            LEFT JOIN tactic_classification tc ON ha.id = tc.asset_id
            WHERE ha.create_time >= %s AND (tc.status IS NULL OR tc.status = 'pending')
        """
        effective_since = since_time or (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        total_count = db.execute_query(count_sql, (effective_since,))[0]['total']
        if total_limit and total_limit > 0:
            total_count = min(int(total_count), int(total_limit))
    except Exception:
        total_count = 0
        
    logging.info(f"开始批量分类，预计总条数: {total_count}")
    
    with tqdm(total=total_count, desc="分类进度") as pbar:
        for db_batch in fetch_assets(batch_size=batch_size, since_time=since_time, total_limit=total_limit):
            # 对从DB取出的每大批，按 AI 允许的小批次处理
            for i in range(0, len(db_batch), ai_batch_size):
                ai_batch = db_batch[i:i + ai_batch_size]
                batch_idx = (total_processed + i) // ai_batch_size
                
                result = classify_batch(ai_batch, batch_idx)
                
                # 统计和回写
                written = write_results_to_db(result, ai_batch)
                
                # 计算平均置信度和异常
                batch_confidences = []
                for cat in ["admin_panels", "high_risk_apps", "high_risk_ports"]:
                    for item in result.get(cat, []):
                        if "confidence" in item:
                            batch_confidences.append(item["confidence"])
                            recent_confidences.append(item["confidence"])
                            
                if not batch_confidences:
                    total_anomalies += len(ai_batch)
                
                total_processed += len(ai_batch)
                total_written += written
                
                # 更新进度条和描述
                recent_avg_conf = sum(recent_confidences[-100:]) / len(recent_confidences[-100:]) if recent_confidences else 0
                pbar.set_postfix({'acc': f"{recent_avg_conf:.2f}"})
                pbar.update(len(ai_batch))
                
                # 每完成10%记录一次INFO
                if total_count > 0 and total_processed % max(1, (total_count // 10)) == 0:
                    logging.info(f"进度: {total_processed}/{total_count} | 写入: {total_written} | 异常: {total_anomalies} | 最近100条均置信度: {recent_avg_conf:.2f}")

    elapsed = time.time() - t_start
    logging.info(f"\n[*] AI分类完成，总耗时 {elapsed:.1f}s | 总读取: {total_processed} | 总写入: {total_written}")




def main():
    parser = argparse.ArgumentParser(
        description="资产智能分类 - 服务端模块"
    )
    parser.add_argument(
        "--since-time",
        default="",
        help="仅分类该时间之后创建的资产，格式: YYYY-mm-dd HH:MM:SS",
    )
    parser.add_argument(
        "--total-limit",
        type=int,
        default=0,
        help="本次最多分类数量（0为不限制）",
    )
    args = parser.parse_args()

    # 1. 初始化数据库及表
    init_db()
    logging.info(f"\n{'='*60}")
    logging.info(f"[*] 资产智能分类服务端已启动")
    logging.info(f"{'='*60}")

    # 2. 分类处理主循环
    classify_all_assets(
        since_time=(args.since_time or "").strip() or None,
        total_limit=max(0, int(args.total_limit or 0)),
    )

if __name__ == "__main__":
    main()

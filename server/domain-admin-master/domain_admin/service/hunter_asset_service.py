# -*- coding: utf-8 -*-
"""
hunter_asset_service.py
"""
import os
import sys
import subprocess
import traceback
import csv
import io
from datetime import datetime

def run_asset_classification_job(since_time=None, total_limit=None):
    """
    定期执行资产分类任务
    """
    logger.info("Starting asset classification job...")
    try:
        # 获取all4win目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # server/domain-admin-master/domain_admin/service -> all4win
        project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
        all4win_dir = os.path.join(project_root, "all4win")
        
        script_path = os.path.join(all4win_dir, "hunter_asset_classifier.py")
        
        if not os.path.exists(script_path):
            logger.error(f"Asset classification script not found: {script_path}")
            return
            
        # 考虑到依赖和环境，直接用子进程调用
        # 这里假定执行环境和 python 路径正确
        cmd = [sys.executable, script_path]
        if since_time:
            cmd.extend(["--since-time", str(since_time)])
        if total_limit is not None:
            try:
                limit_num = int(total_limit)
                if limit_num > 0:
                    cmd.extend(["--total-limit", str(limit_num)])
            except Exception:
                pass

        process = subprocess.Popen(
            cmd,
            cwd=all4win_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Asset classification job finished successfully.\nDeepSeek output:\n{stdout}")
        else:
            logger.error(f"Asset classification job failed with return code {process.returncode}: {stderr}")
            
    except Exception as e:
        logger.error(f"Failed to run asset classification job: {traceback.format_exc()}")

from peewee import SqliteDatabase, MySQLDatabase, PostgresqlDatabase, CharField, TextField
from playhouse.migrate import migrate, SqliteMigrator, MySQLMigrator, PostgresqlMigrator

from domain_admin.log import logger
from domain_admin.model.base_model import db
from domain_admin.model.hunter_asset_model import HunterAssetModel
from domain_admin.utils.flask_ext.app_exception import AppException


def _sql_placeholder():
    return "?" if isinstance(db, SqliteDatabase) else "%s"


def _ensure_tactic_classification_columns():
    """
    确保 tactic_classification 具备渗透状态与备注字段
    """
    table_name = "tactic_classification"
    if table_name not in db.get_tables():
        raise AppException("未找到 tactic_classification 表，请先执行分类任务后重试")

    columns = {col.name for col in db.get_columns(table_name)}
    alter_sql = []
    if "penetration_status" not in columns:
        alter_sql.append("ALTER TABLE tactic_classification ADD COLUMN penetration_status VARCHAR(32) DEFAULT 'pending'")
    if "penetration_remark" not in columns:
        alter_sql.append("ALTER TABLE tactic_classification ADD COLUMN penetration_remark TEXT")
    if "reason" not in columns:
        alter_sql.append("ALTER TABLE tactic_classification ADD COLUMN reason TEXT")
    if "framework" not in columns:
        alter_sql.append("ALTER TABLE tactic_classification ADD COLUMN framework VARCHAR(255)")
    if "action" not in columns:
        alter_sql.append("ALTER TABLE tactic_classification ADD COLUMN action TEXT")

    for sql in alter_sql:
        db.execute_sql(sql)


def _quote_identifier(identifier):
    if isinstance(db, MySQLDatabase):
        return "`%s`" % str(identifier).replace("`", "``")
    return '"%s"' % str(identifier).replace('"', '""')


def _find_optional_column(table_name, candidates):
    table_set = set(db.get_tables())
    if table_name not in table_set:
        return None
    columns = {col.name for col in db.get_columns(table_name)}
    for c in candidates:
        if c in columns:
            return c
    return None

def get_migrator(database):
    """
    获取对应的数据库 Migrator
    """
    if isinstance(database, SqliteDatabase):
        return SqliteMigrator(database)
    elif isinstance(database, MySQLDatabase):
        return MySQLMigrator(database)
    elif isinstance(database, PostgresqlDatabase):
        return PostgresqlMigrator(database)
    else:
        raise AppException("Unsupported database type for migration")

def dynamic_adjust_schema(csv_headers):
    """
    基于CSV的字段结构动态调整数据库表结构
    包括新增字段
    """
    table_name = HunterAssetModel._meta.table_name
    migrator = get_migrator(db)
    
    # 获取当前表的所有列名
    columns = db.get_columns(table_name)
    existing_columns = {col.name for col in columns}
    
    # 获取需要新增的字段
    new_columns = []
    for header in csv_headers:
        # 清理列名中的非法字符（简单处理）
        safe_header = header.strip().replace(' ', '_').replace('-', '_').lower()
        if safe_header not in existing_columns and safe_header != '':
            new_columns.append(safe_header)
            
    if new_columns:
        logger.info(f"Adding new columns to {table_name}: {new_columns}")
        operations = []
        for col_name in new_columns:
            # 默认使用 TextField 以支持长文本，避免长度不足的问题
            new_field = TextField(null=True)
            operations.append(migrator.add_column(table_name, col_name, new_field))
            
            # 同时动态给模型添加属性，以便后续ORM操作
            setattr(HunterAssetModel, col_name, new_field)
            if hasattr(HunterAssetModel._meta, 'add_field'):
                HunterAssetModel._meta.add_field(col_name, new_field)
            
        try:
            migrate(*operations)
        except Exception as e:
            logger.error(f"Failed to dynamic adjust schema: {traceback.format_exc()}")
            raise AppException(f"动态调整表结构失败: {str(e)}")

def trigger_full_asset_pipeline(icp_keyword, limit=100, user_id=0):
    """
    手动触发完整的自动化资产处理流水线
    1. 自动调用 Hunter API 获取并导出 CSV
    2. 自动读取生成的 CSV 并入库 (动态表结构支持)
    3. 自动触发后台 DeepSeek 战术分类任务
    """
    from domain_admin.service import async_task_service
    
    @async_task_service.async_task_decorator(f"资产自动化流水线: {icp_keyword}")
    def do_full_pipeline():
        try:
            logger.info(f"Start full asset pipeline for ICP: {icp_keyword}, Limit: {limit}")
            pipeline_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 获取 all4win 目录的绝对路径，并添加到 sys.path 以便直接导入 hunter_icp_asset_collector
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
            all4win_dir = os.path.join(project_root, "all4win")
            
            if all4win_dir not in sys.path:
                sys.path.append(all4win_dir)
                
            import hunter_icp_asset_collector
            
            # Step 1: 自动拉取资产并导出 CSV
            logger.info("Step 1: Running collection...")
            # -1 表示全部拉取
            csv_path = hunter_icp_asset_collector.run_collection(icp_keyword, limit)
            
            if not csv_path or not os.path.exists(csv_path):
                raise AppException(f"未找到相关资产或生成CSV失败: {icp_keyword}")
                
            # Step 2: 自动读取并入库
            logger.info(f"Step 2: Importing CSV {csv_path} into database...")
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                # 包装为 StringIO 以兼容原有基于流的处理逻辑
                import_result = import_csv_data(f, user_id)
                logger.info(f"Import result: Success={import_result['success_count']}, Error={import_result['error_count']}")
                
            # Step 3: 触发 DeepSeek 分类
            logger.info("Step 3: Triggering DeepSeek classification job...")
            run_asset_classification_job(
                since_time=pipeline_start_time,
                total_limit=import_result.get("success_count", 0),
            )
            
            logger.info(f"Full pipeline finished successfully for ICP: {icp_keyword}")
            
        except Exception as e:
            logger.error(f"Failed to execute full asset pipeline: {traceback.format_exc()}")
            
    return do_full_pipeline()

def get_classified_assets(keyword='', page=1, size=50):
    """
    获取已分类的资产列表，支持分页和关键字搜索
    """
    from domain_admin.model.base_model import db
    
    offset = (page - 1) * size
    
    _ensure_tactic_classification_columns()

    # 基础查询 SQL (只展示有分类结果的数据，过滤掉待处理的 pending)
    sql_base = """
        FROM tb_hunter_asset ha
        INNER JOIN tactic_classification tc ON ha.id = tc.asset_id
        WHERE tc.status != 'pending'
    """
    
    params = []
    if keyword:
        sql_base += " AND (ha.ip LIKE %s OR ha.domain LIKE %s OR ha.company LIKE %s)"
        like_kw = f"%{keyword}%"
        params.extend([like_kw, like_kw, like_kw])
        
    # 查询总数
    count_sql = f"SELECT COUNT(ha.id) as total {sql_base}"
    cursor = db.cursor()
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    
    tc_columns = {col.name for col in db.get_columns("tactic_classification")} if "tactic_classification" in db.get_tables() else set()
    ha_columns = {col.name for col in db.get_columns("tb_hunter_asset")} if "tb_hunter_asset" in db.get_tables() else set()

    def _build_text_expr(output_alias, tc_candidates, ha_candidates):
        parts = []
        for col in tc_candidates:
            if col in tc_columns:
                parts.append(f"NULLIF(TRIM(tc.{_quote_identifier(col)}), '')")
        for col in ha_candidates:
            if col in ha_columns:
                parts.append(f"NULLIF(TRIM(ha.{_quote_identifier(col)}), '')")
        if not parts:
            return f"'' AS {output_alias}"
        return f"COALESCE({', '.join(parts)}, '') AS {output_alias}"

    priority_expr = _build_text_expr(
        "deepseek_priority",
        ["priority", "risk_priority", "priority_level", "优先级"],
        ["priority", "risk_priority", "priority_level", "优先级"],
    )
    suggestion_expr = _build_text_expr(
        "deepseek_action",
        ["action", "suggestion", "advice", "recommended_action", "action_advice", "建议操作"],
        ["action", "suggestion", "advice", "recommended_action", "action_advice", "建议操作"],
    )
    framework_expr = _build_text_expr(
        "deepseek_framework",
        ["framework", "component", "product_name", "框架"],
        ["framework", "component", "product_name", "框架"],
    )
    reason_expr = _build_text_expr(
        "deepseek_reason",
        ["reason", "remark", "判断逻辑"],
        ["reason", "remark", "判断逻辑"],
    )

    # 查询数据
    data_sql = f"""
        SELECT 
            ha.id, ha.ip, ha.port, ha.domain, ha.url, ha.web_title, ha.company,
            tc.predicted_tactic, tc.confidence, tc.status AS classification_status, tc.updated_at,
            COALESCE(tc.penetration_status, 'pending') AS penetration_status,
            COALESCE(tc.penetration_remark, '') AS penetration_remark,
            {priority_expr},
            {suggestion_expr},
            {framework_expr},
            {reason_expr}
        {sql_base}
        ORDER BY ha.id DESC
        LIMIT %s OFFSET %s
    """
    params.extend([size, offset])
    
    cursor.execute(data_sql, params)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    
    list_data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    
    return {
        "list": list_data,
        "total": total,
        "page": page,
        "size": size
    }


def update_asset_penetration_status(asset_id, is_completed):
    """
    更新资产渗透状态
    """
    _ensure_tactic_classification_columns()
    state = "completed" if bool(is_completed) else "pending"
    placeholder = _sql_placeholder()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    update_sql = (
        f"UPDATE tactic_classification "
        f"SET penetration_status = {placeholder}, updated_at = {placeholder} "
        f"WHERE asset_id = {placeholder}"
    )
    cursor = db.cursor()
    try:
        cursor.execute(update_sql, (state, now_str, int(asset_id)))
        if cursor.rowcount <= 0:
            raise AppException("未找到对应资产分类记录")
    finally:
        cursor.close()
    return {"asset_id": int(asset_id), "penetration_status": state}


def update_asset_penetration_remark(asset_id, remark):
    """
    更新资产渗透备注
    """
    _ensure_tactic_classification_columns()
    placeholder = _sql_placeholder()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    remark_text = (remark or "").strip()

    update_sql = (
        f"UPDATE tactic_classification "
        f"SET penetration_remark = {placeholder}, updated_at = {placeholder} "
        f"WHERE asset_id = {placeholder}"
    )
    cursor = db.cursor()
    try:
        cursor.execute(update_sql, (remark_text, now_str, int(asset_id)))
        if cursor.rowcount <= 0:
            raise AppException("未找到对应资产分类记录")
    finally:
        cursor.close()

    return {"asset_id": int(asset_id), "penetration_remark": remark_text}

def trigger_asset_classification(user_id=0):
    """
    手动触发异步分类任务
    """
    from domain_admin.service import async_task_service
    
    # 包装为异步任务执行
    @async_task_service.async_task_decorator("资产智能分类")
    def do_classification():
        run_asset_classification_job()
        
def import_csv_data(file_stream, current_user_id=0):
    """
    导入CSV数据
    实现数据验证、重复数据检测、异常处理和事务管理
    """
    # 1. 解析 CSV 头部
    reader = csv.DictReader(file_stream)
    if not reader.fieldnames:
        raise AppException("CSV 文件为空或没有表头")
        
    csv_headers = reader.fieldnames
    
    # 2. 动态调整表结构
    dynamic_adjust_schema(csv_headers)
    
    # 3. 准备导入数据
    success_count = 0
    error_count = 0
    error_logs = []
    
    batch_size = 500
    batch_data = []
    
    # 获取当前表已有的所有列名（经过动态调整后）
    columns = db.get_columns(HunterAssetModel._meta.table_name)
    valid_fields = {col.name for col in columns}
    
    with db.atomic() as txn:
        try:
            for row_index, row in enumerate(reader, start=2): # 行号从2开始(含表头)
                # 数据验证与清洗
                insert_dict = {}
                for key, val in row.items():
                    if key is None:
                        continue
                    safe_key = key.strip().replace(' ', '_').replace('-', '_').lower()
                    if safe_key in valid_fields:
                        insert_dict[safe_key] = val.strip() if val else ''
                
                # 必填项检测 (假设 ip 必须存在)
                if not insert_dict.get('ip'):
                    error_count += 1
                    error_logs.append(f"第 {row_index} 行: 缺少必要字段 ip")
                    continue
                    
                # 重复数据检测（基于 ip 和 port，视业务需求而定）
                # 这里为了性能，可以在外部进行批量去重，但由于可能有百万级数据，我们先在内存做简单排重或者依靠唯一索引
                # 这里做个简单的重复检查逻辑（可选）
                
                batch_data.append(insert_dict)
                
                # 批量插入
                if len(batch_data) >= batch_size:
                    _batch_insert(batch_data)
                    success_count += len(batch_data)
                    batch_data = []
            
            # 插入剩余数据
            if batch_data:
                _batch_insert(batch_data)
                success_count += len(batch_data)
                
        except Exception as e:
            txn.rollback()
            logger.error(f"CSV Import Failed: {traceback.format_exc()}")
            raise AppException(f"数据导入失败，已回滚: {str(e)}")

    return {
        "success_count": success_count,
        "error_count": error_count,
        "error_logs": error_logs[:100] # 只返回前100条错误日志防止过长
    }

def _batch_insert(batch_data):
    """
    执行批量插入，避免动态字段未正确绑定到ORM导致插入失败
    """
    if not batch_data:
        return
    
    table_name = HunterAssetModel._meta.table_name
    
    # 提取所有出现过的列名
    columns = set()
    for row in batch_data:
        columns.update(row.keys())
        
    columns = list(columns)
    
    # 手动补充 create_time 和 update_time (应用层默认值)
    from domain_admin.utils import datetime_util
    current_time = datetime_util.get_datetime()
    
    if 'create_time' not in columns:
        columns.append('create_time')
        for row in batch_data:
            row['create_time'] = current_time
            
    if 'update_time' not in columns:
        columns.append('update_time')
        for row in batch_data:
            row['update_time'] = current_time
    
    # 获取占位符 (SQLite 用 '?', MySQL/Postgres 用 '%s')
    placeholder = '?' if isinstance(db, SqliteDatabase) else '%s'
    placeholders = ", ".join([placeholder] * len(columns))
    cols_str = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
    
    # 构造参数
    params = []
    for row in batch_data:
        params.append(tuple(row.get(col, None) for col in columns))
        
    # 执行插入
    cursor = db.cursor()
    try:
        for chunk in [params[i:i + 100] for i in range(0, len(params), 100)]:
            cursor.executemany(sql, chunk)
    finally:
        cursor.close()

# -*- coding: utf-8 -*-
"""
tool_database.py

数据库 MCP 工具：让 Claude 可以查询数据库表结构、执行只读 SQL 查询。
所有写操作（INSERT/UPDATE/DELETE/DROP/ALTER/CREATE）被拦截。
"""
from __future__ import print_function, unicode_literals, absolute_import, division

import json
import logging
import re

from domain_admin.service.mcp.mcp_registry import register_tool
from domain_admin.model.base_model import db

logger = logging.getLogger(__name__)

_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|RENAME|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _handler_list_tables(params):
    try:
        tables = db.get_tables()
        result = []
        for t in tables:
            try:
                columns = db.get_columns(t)
                col_info = [
                    {"name": c.name, "type": str(c.data_type)} for c in columns
                ]
                result.append({"table": t, "columns": col_info})
            except Exception:
                result.append({"table": t, "columns": []})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return "Error listing tables: %s" % str(e)


def _handler_execute_query(params):
    sql = params.get("sql", "").strip()
    if not sql:
        return "Error: SQL is empty"
    if _WRITE_PATTERN.search(sql):
        return "Error: Write operations are not allowed. Only SELECT queries are permitted."
    if ";" in sql.rstrip(";")[:-1]:
        return "Error: Only single SQL statement is allowed."
    sql = sql.rstrip(";")
    try:
        cursor = db.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        cursor.close()
        result = {"columns": columns, "rows": [list(r) for r in rows[:500]], "rowcount": len(rows)}
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return "Error executing query: %s" % str(e)


def _handler_describe_table(params):
    table_name = params.get("table_name", "").strip()
    if not table_name:
        return "Error: table_name is required"
    try:
        columns = db.get_columns(table_name)
        col_info = []
        for c in columns:
            col_info.append(
                {
                    "name": c.name,
                    "type": str(c.data_type),
                    "nullable": c.null,
                    "default": str(c.default) if c.default else None,
                    "primary_key": c.primary_key,
                }
            )
        return json.dumps(col_info, ensure_ascii=False, indent=2)
    except Exception as e:
        return "Error describing table: %s" % str(e)


def register():
    register_tool(
        name="list_tables",
        description="列出数据库中所有表及其字段结构。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=_handler_list_tables,
        category="database",
    )
    register_tool(
        name="execute_query",
        description="执行只读 SQL 查询（仅允许 SELECT）。结果最多返回 500 行。",
        input_schema={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SELECT SQL 语句",
                }
            },
            "required": ["sql"],
        },
        handler=_handler_execute_query,
        category="database",
    )
    register_tool(
        name="describe_table",
        description="查看指定表的字段结构、类型、默认值等信息。",
        input_schema={
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "表名",
                }
            },
            "required": ["table_name"],
        },
        handler=_handler_describe_table,
        category="database",
    )

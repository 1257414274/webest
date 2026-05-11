# -*- coding: utf-8 -*-
import time
import logging
import traceback
from contextlib import contextmanager

from dbutils.pooled_db import PooledDB
import pymysql
from pymysql.cursors import DictCursor

from config import config

class DBDriver:
    def __init__(self):
        db_conf = config.db
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=db_conf.get('pool_size', 10),
            mincached=2,
            maxcached=5,
            maxshared=3,
            blocking=True,
            maxusage=None,
            setsession=[],
            ping=0,
            host=db_conf.get('host', '127.0.0.1'),
            port=db_conf.get('port', 3306),
            user=db_conf.get('user', 'root'),
            password=db_conf.get('password', ''),
            database=db_conf.get('database', 'data'),
            charset='utf8mb4',
            cursorclass=DictCursor,
            connect_timeout=db_conf.get('timeout', 30)
        )

    @contextmanager
    def get_connection(self):
        conn = None
        retries = 3
        for attempt in range(retries):
            try:
                conn = self.pool.connection()
                break
            except Exception as e:
                if attempt < retries - 1:
                    logging.warning(f"Database connection failed, retrying in 3 seconds... ({attempt+1}/{retries})")
                    time.sleep(3)
                else:
                    logging.error(f"Failed to get database connection after {retries} attempts: {e}")
                    raise

        try:
            yield conn
        finally:
            if conn:
                conn.close()

    def execute_query(self, sql, args=None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, args)
                return cursor.fetchall()

    def execute_update(self, sql, args=None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(sql, args)
                    conn.commit()
                    return cursor.rowcount
                except Exception as e:
                    conn.rollback()
                    raise

    def execute_many(self, sql, args_list):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.executemany(sql, args_list)
                    conn.commit()
                    return cursor.rowcount
                except Exception as e:
                    conn.rollback()
                    raise

db = DBDriver()

def init_db():
    """初始化目标表 tactic_classification 和 dead_letter_table"""
    create_tactic_table = """
    CREATE TABLE IF NOT EXISTS tactic_classification (
        asset_id VARCHAR(255) PRIMARY KEY,
        predicted_tactic VARCHAR(255),
        confidence FLOAT,
        status VARCHAR(50),
        priority VARCHAR(64),
        reason TEXT,
        framework VARCHAR(255),
        action TEXT,
        suggestion TEXT,
        risk_tag VARCHAR(255),
        attack_surface TEXT,
        remark TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    create_dead_letter_table = """
    CREATE TABLE IF NOT EXISTS tactic_dead_letter (
        id INT AUTO_INCREMENT PRIMARY KEY,
        asset_id VARCHAR(255),
        error_msg TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    # 假设源表叫 tb_hunter_asset 且里面有个 id，如果没有 asset_id 字段，我们在这里增加一个 view 或者直接用 tb_hunter_asset
    
    db.execute_update(create_tactic_table)
    db.execute_update(create_dead_letter_table)
    _ensure_tactic_classification_columns()
    logging.info("Database tables initialized.")


def _ensure_tactic_classification_columns():
    """
    向后兼容旧表结构：补齐新增分析字段
    """
    try:
        rows = db.execute_query("SHOW COLUMNS FROM tactic_classification")
        existing = {r.get("Field") for r in rows}
    except Exception:
        return

    alter_sql_list = []
    if "priority" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN priority VARCHAR(64) NULL")
    if "reason" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN reason TEXT NULL")
    if "framework" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN framework VARCHAR(255) NULL")
    if "action" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN action TEXT NULL")
    if "suggestion" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN suggestion TEXT NULL")
    if "risk_tag" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN risk_tag VARCHAR(255) NULL")
    if "attack_surface" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN attack_surface TEXT NULL")
    if "remark" not in existing:
        alter_sql_list.append("ALTER TABLE tactic_classification ADD COLUMN remark TEXT NULL")

    for sql in alter_sql_list:
        try:
            db.execute_update(sql)
        except Exception as e:
            logging.warning(f"Alter tactic_classification failed: {e}")

if __name__ == '__main__':
    init_db()

# -*- coding: utf-8 -*-
import os
import yaml
import argparse

class Config:
    def __init__(self, env='prod'):
        self.env = env
        self.config_data = self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # 支持通过环境变量覆盖数据库配置，便于容器化部署
        db_data = data.setdefault('db', {})
        env_mapping = {
            'DB_HOST': ('host', str),
            'DB_PORT': ('port', int),
            'DB_USER': ('user', str),
            'DB_PASSWORD': ('password', str),
            'DB_NAME': ('database', str),
            'DB_POOL_SIZE': ('pool_size', int),
            'DB_TIMEOUT': ('timeout', int),
        }
        for env_key, (cfg_key, caster) in env_mapping.items():
            raw = os.getenv(env_key)
            if raw in (None, ''):
                continue
            try:
                db_data[cfg_key] = caster(raw)
            except Exception:
                # 非法值时保留原配置
                pass

        return data

    @property
    def db(self):
        return self.config_data.get('db', {})

    @property
    def server(self):
        return self.config_data.get('server', {})

    @property
    def log(self):
        return self.config_data.get('log', {})

def get_config():
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env', default='prod', choices=['prod', 'dev'], help='Environment')
    args, _ = parser.parse_known_args()
    return Config(env=args.env)

config = get_config()

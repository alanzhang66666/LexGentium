"""
配置模块 - 兼容导入
由于config是git配置文件，使用config.py来导出settings
"""
from settings import settings

__all__ = ['settings']





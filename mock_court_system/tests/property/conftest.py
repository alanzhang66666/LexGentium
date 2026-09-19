"""Property 测试统一配置。

SQLite 存储首次初始化在本机冷目录下可能超过 Hypothesis 默认 200ms
deadline（属环境抖动而非语义失败），统一关闭 deadline。
"""
from hypothesis import HealthCheck, settings

settings.register_profile(
    "property",
    deadline=None,
    suppress_health_check=list(HealthCheck),
)
settings.load_profile("property")

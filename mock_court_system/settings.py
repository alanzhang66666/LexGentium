"""
配置管理模块
支持从环境变量和 YAML 文件加载配置
"""
from typing import Optional, Dict, Any
from pathlib import Path
import yaml
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class APIConfig(BaseSettings):
    """API 配置"""
    # 远程法庭模拟服务地址，仅 main.py 批处理路径使用，Web 服务不依赖。
    # 通过环境变量 COURT_API_BASE_URL 显式配置，不在代码中硬编码。
    model_config = SettingsConfigDict(env_prefix="COURT_API_")

    base_url: str = Field(default="")
    api_key: str = Field(default="")
    timeout: int = Field(default=120)
    scenario_prefix: str = Field(default="")


class LLMConfig(BaseSettings):
    """LLM 配置"""
    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: str = Field(default="deepseek")
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.deepseek.com")
    model: str = Field(default="deepseek-flash")
    fast_model: str = Field(default="")
    fast_max_tokens: int = Field(default=512)
    thinking: str = Field(default="enabled")
    reasoning_effort: str = Field(default="high")
    fast_thinking: str = Field(default="disabled")
    fast_reasoning_effort: str = Field(default="low")
    demo_mode: bool = Field(default=False)
    temperature: float = Field(default=0.1)
    max_tokens: int = Field(default=4096)
    timeout: int = Field(default=60)


class TeamConfig(BaseSettings):
    """团队配置"""
    model_config = SettingsConfigDict(env_prefix="")

    team_id: str = Field(default="")


class ScenarioConfig(BaseSettings):
    """场景配置"""
    max_turns: int = 20
    instruction_mode: str = "template"
    verbose: bool = True


class DataConfig(BaseSettings):
    """数据路径配置"""
    test_dir: str = "../cail2025_智能体模拟法庭-复赛阶段-数据集"
    output_dir: str = "./output"


class LoggingConfig(BaseSettings):
    """日志配置"""
    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = Field(default="INFO")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "./logs/app.log"


class Settings(BaseSettings):
    """全局配置"""
    api: APIConfig = Field(default_factory=APIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    dashscope_api_key: str = Field(default="")
    team: TeamConfig = Field(default_factory=TeamConfig)
    scenarios: Dict[str, ScenarioConfig] = Field(default_factory=dict)
    data: DataConfig = Field(default_factory=DataConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> "Settings":
        """从 YAML 文件加载配置"""
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            # 返回默认配置
            return cls()

        with open(yaml_file, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        # 替换环境变量
        config_dict = cls._replace_env_vars(config_dict)

        # 解析场景配置
        scenarios = {}
        if "scenarios" in config_dict:
            for scenario_name, scenario_cfg in config_dict["scenarios"].items():
                scenarios[scenario_name] = ScenarioConfig(**scenario_cfg)
            config_dict["scenarios"] = scenarios

        # 创建配置对象
        api_cfg = APIConfig(**config_dict.get("api", {}))
        llm_cfg = LLMConfig(**config_dict.get("llm", {}))
        team_cfg = TeamConfig(**config_dict.get("team", {}))
        data_cfg = DataConfig(**config_dict.get("data", {}))
        logging_cfg = LoggingConfig(**config_dict.get("logging", {}))

        return cls(
            api=api_cfg,
            llm=llm_cfg,
            team=team_cfg,
            scenarios=scenarios,
            data=data_cfg,
            logging=logging_cfg,
        )

    @staticmethod
    def _replace_env_vars(config: Any) -> Any:
        """递归替换配置中的环境变量"""
        if isinstance(config, dict):
            return {k: Settings._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [Settings._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            return os.getenv(env_var, "")
        return config

    def get_scenario_config(self, scenario: str) -> ScenarioConfig:
        """获取指定场景的配置"""
        return self.scenarios.get(
            scenario,
            ScenarioConfig(
                max_turns=20 if scenario != "CI" else 50,
                instruction_mode="template",
                verbose=True,
            ),
        )


# 全局配置实例
settings = Settings.from_yaml()

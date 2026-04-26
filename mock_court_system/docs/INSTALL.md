# 模拟法庭多智能体系统 - 安装和运行指南

## 快速开始

### 1. 安装依赖

在 `mock_court_multiagents` 目录下执行：

```powershell
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`：

```powershell
Copy-Item .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```bash
# 模拟法庭 API
COURT_API_BASE_URL=http://47.116.195.100:43385
COURT_API_KEY=你的API密钥

# LLM 配置 (DeepSeek 或 OpenAI 兼容)
LLM_API_KEY=你的LLM_API密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 项目配置
TEAM_ID=你的队伍ID

# 日志级别
LOG_LEVEL=INFO
```

### 3. 运行测试

```powershell
# 运行单个 CD 案例
python main.py --scenario CD --limit 1

# 运行所有 CD 案例
python main.py --scenario CD

# 运行所有场景
python main.py --all
```

## 项目结构说明

```
mock_court_multiagents/
├── agents/                 # 智能体模块
│   ├── base_agent.py      # 基础智能体抽象类
│   ├── cd_agent.py        # CD 场景（起诉状生成）
│   ├── dd_agent.py        # DD 场景（答辩状生成）- 待实现
│   └── ci_agent.py        # CI 场景（法庭判决）- 待实现
│
├── core/                   # 核心组件
│   ├── schemas.py         # 数据模型定义
│   ├── llm_client.py      # LLM 客户端封装（支持 LangChain）
│   ├── api_client.py      # 模拟法庭 API 客户端
│   └── state_machine.py   # 状态机实现（用于 CI 场景）
│
├── utils/                  # 工具函数
│   ├── data_loader.py     # 数据加载
│   ├── dialog_history.py  # 对话历史管理
│   ├── result_generator.py # 结果生成
│   └── logger.py          # 日志配置
│
├── config/                 # 配置管理
│   └── settings.py        # 配置类定义
│
├── output/                 # 输出目录（自动创建）
├── logs/                   # 日志目录（自动创建）
│
├── .env                    # 环境变量（需自行创建）
├── .env.example           # 环境变量示例
├── config.yaml            # 配置文件
├── requirements.txt       # 依赖列表
├── main.py               # 主入口
└── README.md             # 项目说明
```

## 框架特性

### 1. 基于 LangChain 的架构
- 统一的 LLM 接口，支持多种后端（DeepSeek、OpenAI 等）
- 灵活的智能体基类，易于扩展
- 完善的 Prompt 管理

### 2. 模块化设计
- **agents**: 各场景的智能体实现
- **core**: 核心组件（LLM、API、数据模型）
- **utils**: 通用工具函数
- **config**: 配置管理

### 3. 配置系统
- 支持环境变量和 YAML 配置
- 分场景配置（CD/DD/CI）
- 灵活的参数设置

## 开发指南

### 添加新场景的智能体

1. 在 `agents/` 目录下创建新文件（如 `dd_agent.py`）
2. 继承 `BaseAgent` 类：

```python
from .base_agent import BaseAgent

class DDAgent(BaseAgent):
    def __init__(self, api_client, llm, max_turns=20, verbose=False):
        super().__init__(api_client, llm, "DD", max_turns, verbose)
    
    def run_case(self, case_id: str, **kwargs):
        # 实现你的逻辑
        pass
```

3. 在 `agents/__init__.py` 中导出
4. 在 `main.py` 中添加运行函数

### 自定义配置

编辑 `config.yaml` 文件：

```yaml
scenarios:
  CD:
    max_turns: 20
    instruction_mode: template  # 或 llm
    verbose: true
```

### 日志系统

日志会同时输出到控制台和文件（`logs/app.log`）：

```python
from utils import setup_logger

logger = setup_logger(level="INFO", log_file="logs/app.log")
logger.info("这是一条日志")
```

## 常见问题

### 1. 找不到测试数据

确保测试数据在正确的位置：
- 默认路径：`../模拟法庭-初赛-数据集/测试集/`
- 可在 `config.yaml` 中修改 `data.test_dir`

### 2. API 调用失败

检查：
- `.env` 中的 `COURT_API_KEY` 是否正确
- 网络连接是否正常
- 查看日志文件了解详细错误信息

### 3. LLM 调用失败

检查：
- `.env` 中的 `LLM_API_KEY` 是否正确
- `LLM_BASE_URL` 是否正确
- 尝试降低 `temperature` 参数

## 下一步计划

- [ ] 实现 DD Agent（答辩状生成）
- [ ] 实现 CI Agent（法庭判决）
- [ ] 添加更多 Prompt 模板
- [ ] 支持批量处理
- [ ] 添加单元测试
- [ ] 性能优化

## 许可证

MIT License

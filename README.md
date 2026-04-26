# 模拟法庭多智能体系统项目

本仓库是一个围绕 **LegalFlow 模拟法庭多智能体系统** 建设的项目工作区，包含可运行的前后端系统、评估实验模块、法律数据与法条检索资源，以及申报、答辩、商业计划和参考文献等归档材料。

## 项目定位

本项目面向民事诉讼与纠纷解决场景，尝试使用大语言模型构建多智能体模拟法庭系统。系统将原告、被告、法官、调解参与者等角色抽象为不同 Agent，并结合博弈论、策略演化、法律检索、调解流程和多维评估方法，实现从案件输入、诉辩生成、庭审推演、调解协商到结果评估的完整流程模拟。

## 当前仓库结构

```text
.
├── mock_court_system/          # 主工程：Next.js 前端 + FastAPI 后端
├── evaluation/                 # 顶层评估结果目录
├── 归档/                       # 项目材料归档
│   ├── 申报材料/               # 基金/启研申请书、推荐意见、正文材料等
│   ├── 答辩与展示材料/         # 答辩稿、PPT、展示材料、技术问题回答等
│   ├── 参考文献/               # 项目相关论文 PDF
│   ├── 商业计划与市场材料/     # 商业计划书、市场分析、执行摘要等
│   ├── 图片与附件/             # 图片、截图和附件材料
│   └── 临时脚本与提取文本/     # 文档处理脚本和临时提取文本
├── .venv/                      # Python 虚拟环境
├── .vscode/                    # VS Code 配置
├── .cursor/                    # Cursor 配置
└── README.md                   # 本说明文件
```

## 主工程说明

主工程位于：

```text
mock_court_system/
```

它是当前项目的核心代码目录，包含前端页面、后端 API、智能体模块、博弈引擎、评估框架、法律数据库和实验脚本。

主要结构如下：

```text
mock_court_system/
├── app/                        # Next.js 前端页面
├── components/                 # 前端组件
├── agents/                     # 多智能体模块
├── core/                       # 核心推理、博弈、检索与流程引擎
├── evaluation/                 # 评估框架与实验脚本
├── data/                       # 数据集、SQLite 状态库、法条索引等
├── database/                   # 数据库相关资源
├── docs/                       # 工程文档和项目文档
├── scripts/                    # 数据处理、测试和辅助脚本
├── tests/                      # 测试目录
├── api_server.py               # FastAPI 后端主入口
├── main.py                     # 批处理/场景运行入口
├── package.json                # 前端依赖与脚本
└── requirements.txt            # Python 依赖
```

## 技术栈

前端：

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- Radix UI
- Recharts

后端：

- FastAPI
- LangChain
- OpenAI SDK
- Pydantic
- SQLite
- FAISS
- BM25 / jieba
- Uvicorn

## 核心功能模块

### 1. 多智能体模拟

系统包含多个法律任务 Agent：

- `CDAgent`：原告侧起诉状/主张生成。
- `DDAgent`：被告侧答辩状/抗辩生成。
- `CIAgent`：庭审、裁判和裁判理由生成。
- `SimAgent`：当事人角色模拟与策略行为生成。

对应目录：

```text
mock_court_system/agents/
```

### 2. 博弈论与策略推演

系统包含博弈建模、纳什均衡、策略反思、收益矩阵、反事实推演和策略演化等能力。

相关文件集中在：

```text
mock_court_system/core/
```

代表性模块：

- `game_engine.py`
- `nash_equilibrium.py`
- `nash_bargaining.py`
- `evolutionary_dynamics.py`
- `extensive_form.py`

### 3. 案件流程编排

系统支持从案件输入到诉辩、庭审、裁判、调解和结果评估的流程编排。

代表性模块：

- `case_orchestrator.py`
- `state_machine.py`
- `mediation_engine.py`
- `liability_chain.py`

### 4. 法律检索与知识增强

项目内置法律数据库和索引文件，支持基于法条数据库的检索增强。

相关资源：

```text
mock_court_system/data/legal_articles.db
mock_court_system/data/legal_articles.index
mock_court_system/data/legal_articles_id_map.npy
```

代表性模块：

- `law_retriever.py`
- `progressive_rag.py`
- `dual_mode_reasoning.py`

### 5. 评估体系

系统内置多维评估框架，用于评估法律推理质量、流程合规性、调解结果、行为对称性、责任链解释性等。

相关目录：

```text
mock_court_system/evaluation/
```

代表性模块：

- `lexeval_cognitive.py`
- `j1eval_metrics.py`
- `outcome_evaluator.py`
- `solution_evaluator.py`
- `multi_layer_evaluator.py`
- `cadd_framework.py`
- `game_eval.py`

## 前端页面

主工程前端包含以下页面路由：

- `/`：首页。
- `/about`：项目介绍。
- `/conversation`：会话式模拟入口。
- `/simulate`：快速模拟入口。
- `/full-simulation`：完整案件流程模拟。
- `/evaluation`：评估任务与结果页面。
- `/database`：法律数据库/法条检索页面。
- `/api-history`：API 调用历史页面。
- `/settings`：系统与 LLM 配置页面。
- `/system`：系统状态页面。
- `/docs`：项目文档页面。

## 后端 API 能力

后端主入口：

```text
mock_court_system/api_server.py
```

主要 API 类型包括：

- 健康检查：`/health`
- LLM 配置：`/config/llm`
- 会话管理：`/conversation/*`
- 完整案件模拟：`/case/full-simulation`
- 博弈会话：`/game/*`
- 调解流程：`/mediation/*`
- 法条检索：`/database/search`
- 评估任务：`/evaluate`、`/game/{game_id}/evaluate/*`
- 责任链与反事实推理：`/game/{game_id}/liability-chain`
- 渐进式 RAG、双模式推理、多法官推理等扩展能力。

## 快速启动

进入主工程目录：

```bash
cd mock_court_system
```

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

安装前端依赖：

```bash
npm install
```

配置环境变量：

```bash
# 根据本地实际情况配置 .env
# 重点配置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 等字段
```

启动后端：

```bash
python api_server.py
```

启动前端：

```bash
npm run dev
```

默认访问地址：

```text
后端：http://localhost:8000
前端：http://localhost:3000
```

## 重要数据与本地状态

主工程内已有若干本地数据和状态文件：

```text
mock_court_system/data/app_state.sqlite3
mock_court_system/data/conversations.sqlite3
mock_court_system/data/game_sessions.sqlite3
mock_court_system/data/legal_articles.db
mock_court_system/data/legal_articles.index
```

这些文件用于保存应用状态、会话记录、博弈记录和法条检索索引。迁移、清理或提交仓库前需要确认是否包含敏感数据或临时实验数据。

## 项目材料归档

顶层散落的申报书、答辩材料、论文和商业计划书已经整理到：

```text
归档/
```

归档目录只用于保存项目支撑材料，不作为系统运行入口。

## 注意事项

- 当前主工程是 `mock_court_system/`，优先从该目录启动和维护。
- `.env` 可能包含 LLM 服务地址和密钥，提交或共享前应检查敏感信息。
- `node_modules/`、`.next/`、`.venv/` 属于本地环境或构建产物，不建议作为正式交付内容。
- `api_server.py` 当前承担大量后端路由和业务逻辑，后续维护时可以考虑拆分为独立 router 模块。
- 项目包含工程实现和申报/答辩材料两类内容，后续若开源或交付，建议进一步拆分代码仓库与材料归档。

## 推荐使用入口

日常开发和演示优先使用：

```text
mock_court_system/
```

推荐页面入口：

```text
/conversation
/simulate
/full-simulation
/evaluation
/database
/settings
```

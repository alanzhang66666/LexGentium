# 模拟法庭多智能体系统项目

本仓库是一个围绕 **LexGentium 模拟法庭多智能体系统** 建设的项目工作区，包含可运行的前后端系统、评估实验模块、法律数据与法条检索资源，以及申报、答辩、商业计划和参考文献等归档材料。

## 项目定位

本项目面向民事诉讼与纠纷解决场景，尝试使用大语言模型构建多智能体模拟法庭系统。系统将原告、被告、法官、调解参与者等角色抽象为不同 Agent，并结合博弈论、策略演化、法律检索、调解流程和多维评估方法，实现从案件输入、诉辩生成、庭审推演、调解协商到结果评估的完整流程模拟。

## 当前仓库结构

```text
.
├── mock_court_system/          # 主工程：Next.js 前端 + FastAPI 后端
├── evaluation/                 # 顶层评估结果目录
├── 归档/                       # 项目材料归档（详见 归档/README.md）
│   ├── 申报材料/               # 启研申请书终稿、推荐意见、正文与附图
│   ├── 商业计划与市场材料/     # 商业计划书、市场分析、分章扩写
│   └── 参考文献/               # 项目相关论文 PDF
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
├── api/routers/                # FastAPI 薄路由（业务在 api/services/）
├── core/                       # 博弈、检索、调解与流程引擎
├── evaluation/                 # 评测任务与 evaluation/lib/ 指标
├── data/                       # 会话/博弈 SQLite、数据集（非法条库）
├── database/                   # 法条 SQLite + FAISS 索引
├── docs/                       # 工程文档
├── scripts/                    # 辅助脚本
├── tests/                      # 测试
├── api_server.py               # FastAPI 薄壳入口
├── main.py                     # 离线批跑（非 Web 主入口）
├── package.json
└── requirements.txt
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

相关资源（法条库在 `database/`，不在 `data/`）：

```text
mock_court_system/database/legal_articles.db
mock_court_system/database/legal_articles.index
mock_court_system/database/legal_articles_id_map.npy
```

代表性模块：

- `law_retriever.py`
- `progressive_rag.py`
- `dual_mode_reasoning.py`

### 5. 评估体系

系统内置多维评估框架，用于评估法律推理质量、流程合规性、调解结果、行为对称性、责任链解释性等。

相关目录：

```text
mock_court_system/evaluation/lib/
```

代表性模块：

- `evaluation/lib/lexeval_cognitive.py`
- `evaluation/lib/j1eval_metrics.py`
- `evaluation/lib/outcome_evaluator.py`
- `evaluation/lib/solution_evaluator.py`
- `evaluation/lib/multi_layer_evaluator.py`
- `evaluation/lib/cadd_framework.py`
- `evaluation/lib/game_eval.py`

## 前端页面

主工程前端包含以下页面路由：

- `/` `/about` `/docs`：营销页。
- `/conversation`：开庭（申请/答辩/听证）。
- `/mediation`：独立五阶段调解工作台。
- `/full-simulation`：全案。
- `/court3d`：3D 观庭（R3F，占位人物 + 导演层）。
- `/evaluation`：复盘（对照 / 策略推演 / 程序合规；有 `game_id` 时可打博弈评测）。
- `/system`：系统枢纽（健康、映射表、实验面板），不是四页合一。
- `/simulate`：无状态调试单轮（在「系统」菜单）。
- `/database` `/settings` `/api-history`：法条、LLM、调用记录。

## 后端 API 能力

后端入口 `api_server.py` 是薄壳；路由在 `api/routers/`，业务在 `api/services/`。

已接线（有 Next 代理 + 页面）：

- `/health`、`/config/llm`、`/conversation/*`、`/case/full-simulation`
- `/game` 创建/列表/详情/SSE 轮次/反事实
- `/mediation/*`（独立调解工作台）
- `/evaluate`、`/game/{id}/evaluate/*`（复盘策略页按钮）
- `/case/progressive-rag`、`/dual-mode-reasoning`、`/multi-judge`（系统页实验面板）
- `/database/search`、`/reference/cases`

`game.py` 里仍有一份与 `/case/*` 重复的创新接口，实验面板走 `/case/*`。未做页面的管理接口（如 `DELETE /game`、非 SSE `round`、equilibrium）仍以 Swagger 为准。

## 快速启动

环境要求：

- Python **3.9+**（在 3.9 实测通过；建议使用 `requirements.lock` 复现已验证的依赖组合）
- Node.js **20+**（在 24 实测通过）

进入主工程目录：

```bash
cd mock_court_system
```

安装 Python 依赖（二选一）：

```bash
pip install -r requirements.txt        # 宽松版本（开发）
pip install -r requirements.lock       # 锁定版本（可复现，实测通过组合）
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

> 路径说明：`main.py` 是依赖远程法庭模拟服务（`COURT_API_BASE_URL`）的历史批处理/实验入口，
> 日常使用请从 `api_server.py`（Web 服务）启动，Web 主路径不依赖任何远程服务。

主工程内已有若干本地数据和状态文件：

```text
mock_court_system/data/app_state.sqlite3
mock_court_system/data/conversations.sqlite3
mock_court_system/data/game_sessions.sqlite3
mock_court_system/data/checkpoints.sqlite3
mock_court_system/data/llm_cache.sqlite3
mock_court_system/database/legal_articles.db
mock_court_system/database/legal_articles.index
```

`data/` 存会话与运行时状态；法条索引在 `database/`。迁移或提交前确认是否含密钥或实验数据。

## 项目材料归档

申报书、商业计划和参考文献已整理到 `归档/`，清单见 `归档/README.md`。该目录只保存项目支撑材料，不是系统运行入口。答辩/展示大文件因超过 GitHub 单文件限制，未纳入仓库。

## 注意事项

- 当前主工程是 `mock_court_system/`，优先从该目录启动和维护。
- `.env` 可能包含 LLM 服务地址和密钥，提交或共享前应检查敏感信息。
- `node_modules/`、`.next/`、`.venv/` 属于本地环境或构建产物，不建议作为正式交付内容。
- `api_server.py` 已拆为薄壳，路由在 `api/routers/`。
- 项目包含工程实现和申报/答辩材料两类内容，后续若开源或交付，建议进一步拆分代码仓库与材料归档。

## 推荐使用入口

日常开发和演示优先使用：

```text
mock_court_system/
```

推荐页面入口：

```text
/conversation
/mediation
/full-simulation
/court3d
/evaluation
/system
/database
/settings
```

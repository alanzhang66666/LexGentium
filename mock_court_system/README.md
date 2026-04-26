# LegalFlow - 模拟法庭多智能体博弈系统

基于大语言模型的民事诉讼全流程模拟系统，融合博弈论强化学习实现原被告策略对抗与进化。

## 学术基础

本系统融合四篇前沿论文的核心思想：

| 论文 | 会议 | 本系统对应模块 |
|------|------|--------------|
| **LexEval** (2409.20288) | NeurIPS 2024 | 六层法律认知能力评测框架 (`evaluation/lib/lexeval_cognitive.py`) |
| **J1-ENVS / J1-EVAL** (2507.04037) | 2025 | PFS 程序合规追踪 + JUD/REA/LAW 细粒度评测 + Big Five 人格 (`evaluation/lib/j1eval_metrics.py`) |
| **AgentMediation** (2509.06586) | AAAI 2026 | TKI 五策略 + 五阶段调解 + 群体极化检测 + LLM-as-a-judge 四指标评测 |
| **CADD** (2511.11715) | 2025 | Behavior-Liability-Statute 推理链 + 对称行为记录 + 渐进式基准 |

## 系统架构

```
┌─────────────────────────────────────────────────┐
│                  API Server (FastAPI)            │
├──────────┬──────────┬───────────┬────────────────┤
│ 会话管理  │ 博弈引擎  │ 调解引擎   │ 评测系统       │
├──────────┼──────────┼───────────┼────────────────┤
│ CDAgent  │GameEngine│Mediation  │ LexEval 六层    │
│ DDAgent  │Nash均衡   │Engine     │ J1-EVAL PFS    │
│ CIAgent  │策略进化   │(HDR 5阶段)│ AgentMed 四指标 │
│ SimAgent │收益矩阵   │           │ CADD 推理链     │
├──────────┴──────────┴───────────┴────────────────┤
│              Core (LLM Client / StateMachine)    │
└─────────────────────────────────────────────────┘
```

## 目录结构

```
mock_court_system/
├── agents/                     # 智能体
│   ├── cd_agent.py             # 起诉状生成（律师Agent）
│   ├── dd_agent.py             # 答辩状生成（律师Agent）
│   ├── ci_agent.py             # 庭审判决（法官Agent）
│   └── sim_agent.py            # 角色模拟（当事人Agent, TKI策略）
├── core/                       # 核心引擎
│   ├── game_engine.py          # 博弈引擎（纳什均衡+策略进化+反事实推演）
│   ├── nash_equilibrium.py     # 纳什均衡追踪器（5×5收益矩阵）
│   ├── case_orchestrator.py    # 全流程编排器（CD→DD→CI, per-party策略注入）
│   ├── mediation_engine.py     # 五阶段调解引擎（Harvard HDR框架）
│   ├── liability_chain.py      # Behavior-Liability-Statute推理链
│   ├── state_machine.py        # 庭审状态机（J1-EVAL PFS合规追踪）
│   ├── llm_client.py           # LLM统一客户端
│   ├── schemas.py              # 数据模型定义
│   ├── game_session_store.py   # 博弈会话SQLite持久化
│   ├── conversation_store.py   # 对话会话存储
│   └── law_retriever.py        # 法条检索（FAISS+BM25）
├── evaluation/                 # 评测系统
│   ├── lib/
│   │   ├── lexeval_cognitive.py    # LexEval六层认知能力评测
│   │   ├── j1eval_metrics.py       # J1-EVAL细粒度指标+Big Five
│   │   ├── outcome_evaluator.py    # AgentMediation四指标LLM-as-a-judge
│   │   ├── solution_evaluator.py   # 方案质量+争议原因分类+群体极化
│   │   ├── multi_layer_evaluator.py # 三层评测（结果/过程/合法性）
│   │   └── cadd_framework.py       # CADD对称行为+可解释决策+渐进基准
│   ├── data/                   # 原始评测数据（20条种子）
│   └── run_evaluation.py       # 评测执行入口
├── data/
│   └── dataset_1000/           # 1000条民事判决书数据集
│       ├── train/              # 600条（CD/DD/CI ground truth）
│       ├── val/                # 200条
│       ├── test/               # 200条
│       └── dataset_meta.json   # 数据集元信息
├── database/                   # 法条数据库（SQLite+FAISS索引）
├── scripts/                    # 工具脚本
│   ├── build_dataset.py        # 数据集构建（从ClaimGen-CN适配）
│   ├── verify_dataset.py       # 数据集验证
│   └── test_api_endpoints.py   # API端点冒烟测试
├── tests/                      # 单元测试
├── docs/                       # 项目文档
├── app/                        # Next.js前端
├── api_server.py               # FastAPI后端入口（~50+端点）
├── settings.py                 # 配置管理
├── requirements.txt            # Python依赖
└── package.json                # Node.js依赖
```

## 快速启动

```bash
# 1. 安装依赖
cd mock_court_system
pip install -r requirements.txt
npm install

# 2. 配置环境
cp .env.example .env
# 编辑 .env 设置 LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 3. 启动后端
python api_server.py          # http://localhost:8000

# 4. 启动前端（另一个终端）
npm run dev                   # http://localhost:3000
```

## 核心API

### 博弈管理
| 端点 | 说明 |
|------|------|
| `POST /game/create` | 创建博弈会话（配置策略、争议原因） |
| `POST /game/{id}/round` | 推进一轮博弈 |
| `POST /game/{id}/stream-round` | SSE流式推进 |
| `GET /game/{id}/equilibrium` | 纳什均衡分析 |
| `POST /game/{id}/strategy/counterfactual` | 反事实推演 |

### 调解
| 端点 | 说明 |
|------|------|
| `POST /mediation/create` | 创建调解会话 |
| `POST /mediation/{id}/preliminary` | 阶段I: 初步介绍 |
| `POST /mediation/{id}/statement` | 阶段II: 当事人陈述 |
| `POST /mediation/{id}/options` | 阶段III: 方案生成 |
| `POST /mediation/{id}/bargain` | 阶段IV: 多轮协商 |
| `POST /mediation/{id}/close` | 阶段V: 结案 |

### 评测
| 端点 | 说明 |
|------|------|
| `POST /game/{id}/evaluate/outcome` | AgentMediation四指标 |
| `POST /game/{id}/evaluate/composite` | 综合评测 |
| `POST /game/{id}/evaluate/lexeval` | LexEval六层认知 |
| `GET /game/{id}/liability-chain` | CADD推理链 |
| `GET /game/{id}/compliance/realtime` | J1-EVAL PFS |

## 数据集

**来源**: ClaimGen-CN (HuggingFace: Josieeee/ClaimGen-CN, EMNLP 2025)
- 207,748条中国裁判文书网真实民事判决书中采样1000条
- 覆盖29种民事案由
- 按3:1:1划分为训练集(600)/验证集(200)/测试集(200)
- 每条数据适配为CD/DD/CI三场景ground truth

## 引用

如果使用本系统，请引用以下论文：

```bibtex
@article{li2024lexeval,
  title={LexEval: A Comprehensive Chinese Legal Benchmark for Evaluating Large Language Models},
  author={Li, Haitao and others},
  journal={NeurIPS 2024 Datasets and Benchmarks},
  year={2024}
}

@article{jia2025j1bench,
  title={Ready Jurist One: Benchmarking Language Agents for Legal Intelligence in Dynamic Environments},
  author={Jia, Zheng and others},
  year={2025}
}

@article{chen2025agentmediation,
  title={Simulating Dispute Mediation with LLM-Based Agents for Legal Research},
  author={Chen, Junjie and others},
  journal={AAAI 2026},
  year={2025}
}

@article{shen2025cadd,
  title={CADD: A Chinese Traffic Accident Dataset for Statute-Based Liability Attribution},
  author={Shen, Yunfei and Wu, Zhongcheng},
  year={2025}
}
```

# LexGentium 0.8

国际商事仲裁听证仿真：Next.js 工作台 + FastAPI 多智能体后端。一场听证一个 `session_id`，**开庭 → 观庭 → 复盘**。

引擎内部仍用 CD / DD / CI 任务标签（申请准备、答辩准备、仲裁听证）。版本 **0.8.0**（`package.json`）。

## 学术基础

| 论文 | 会议 | 本系统对应模块 |
|------|------|----------------|
| **LexEval** (2409.20288) | NeurIPS 2024 | 六层法律认知评测（`evaluation/lib/lexeval_cognitive.py`） |
| **J1-ENVS / J1-EVAL** (2507.04037) | 2025 | PFS 程序合规 + JUD/REA/LAW + Big Five（`evaluation/lib/j1eval_metrics.py`） |
| **AgentMediation** (2509.06586) | AAAI 2026 | TKI 五策略 + HDR 五阶段调解 + 四指标评测 |
| **CADD** (2511.11715) | 2025 | Behavior-Liability-Statute 推理链 + 对称行为 + 渐进基准 |

## 系统架构

```
浏览器 ──► Next.js :3000 /api/* ──► FastAPI :8000
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                 会话/全案          GameEngine       MediationEngine
                 CD DD CI Sim       Nash / 进化      HDR 五阶段
                    │                 │                 │
                    └──────── HearingRuntime / PleadRuntime ────────┘
                                      │
                         SQLite + 法条 FAISS/BM25
```

生产路径：CI 走 `HearingRuntime`（`CI_USE_GRAPH`），CD/DD 走 `PleadRuntime`（`PLEAD_USE_RUNTIME`）。全案由 `CaseOrchestrator` 编排；博弈 `GameEngine` 包一层编排器。`/mediation` 是独立调解；庭内 CI 和解仍走会话流。

## 工作台页面

营销壳：`/` `/about` `/docs`。工作台四组（`Ctrl+K` 同组）：

| 组 | 路由 |
|----|------|
| 开庭 | `/conversation` `/conversation/[id]` `/full-simulation` `/mediation` |
| 观庭 | `/court3d` `/court3d/[id]` `/court3d/replay` |
| 复盘 | `/evaluation`（对照 / 策略 / 合规）`/evaluation/reports/[id]` |
| 系统 | `/login` `/register` `/system` `/settings` `/database` `/api-history` `/simulate` |

`/login` 测通已有 LLM；`/register` 写入配置。都是 `sessionStorage` 软解锁，没有用户表。设了 `API_TOKEN` 时请求带 `Authorization`。

配色：`ink` / `parchment` / `seal`（`DESIGN.md`）。

## 快速启动

```bash
cd mock_court_system
pip install -r requirements.txt
npm install
cp .env.example .env          # LLM_API_KEY、LLM_BASE_URL、LLM_MODEL
python api_server.py          # http://localhost:8000
npm run dev                   # http://localhost:3000
```

打开 `/register` 或 `/login`，再进 `/conversation`。3D：`/court3d`；离线回放：`/court3d/replay`。角色替换见 `docs/COURT3D_ASSET_SPEC.md`（`public/court3d/models/` 目前为空，运行时用胶囊人）。

完整步骤：`docs/INSTALL.md`。部署：`docs/DEPLOY.md`。

## 目录结构

```
mock_court_system/
├── app/                        # Next 页面 + /api BFF
├── components/                 # 双壳导航、听证、court3d、配色
├── lib/                        # api 客户端、session、court3d 导演
├── agents/                     # CD / DD / CI / Sim
├── api/routers/                # FastAPI 薄路由
├── api/services/               # 会话、博弈、评测、SSE、links
├── core/                       # 博弈、调解、检索、Hearing/Plead runtime
├── evaluation/lib/             # LexEval / J1 / CADD / AgentMed 指标
├── data/                       # 运行时 SQLite、dataset_1000 元数据
├── database/                   # 法条 SQLite + FAISS
├── public/court3d/             # casts、replay；models/ 待放入 VRM
├── docs/                       # INSTALL / DEPLOY / ARCHITECTURE / 评测 / 3D
├── scripts/                    # 批跑、bench、重建索引（非 Web 入口）
├── tests/
├── api_server.py               # FastAPI 装配入口
├── main.py                     # 离线批跑（依赖 COURT_API_*，非 Web）
├── DESIGN.md
├── package.json                # 0.8.0
└── requirements.txt
```

## 核心 API

浏览器只打 `/api/*`。下列为 FastAPI 路径。

### 会话与全案

| 端点 | 说明 |
|------|------|
| `POST /conversation/start` | 开一场，返回 `session_id` |
| `POST /conversation/{id}/message/stream` | 页面发言（SSE） |
| `POST /case/full-simulation` | 全案，可选回写 `links.task_id` |

非流式 `POST /conversation/{id}/message` 仅调试。

### 博弈（复盘「策略推演」；需先为本场开局）

| 端点 | 说明 |
|------|------|
| `POST /game/create` | 创建并回写 `links.game_id` |
| `POST /game/{id}/stream-round` | SSE 推演一轮 |
| `POST /game/{id}/round` | 非流式一轮 |
| `GET /game/{id}/equilibrium` | 纳什均衡 |
| `POST /game/{id}/strategy/set` | 设定 TKI |
| `POST /game/{id}/strategy/reflect` | 策略反思 |
| `POST /game/{id}/strategy/counterfactual` | 反事实 |
| `DELETE /game/{id}` | 删局（页面二次确认） |

### 调解（`/mediation`；庭内和解仍走会话）

| 端点 | 说明 |
|------|------|
| `POST /mediation/create` | 独立调解会话 |
| `POST /mediation/{id}/preliminary` … `/close` | HDR 五阶段 |

### 博弈评测（有 `links.game_id` 时策略栏出按钮）

| 端点 | 说明 |
|------|------|
| `POST /game/{id}/evaluate/outcome` | AgentMediation 四指标 |
| `POST /game/{id}/evaluate/lexeval` | LexEval |
| `POST /game/{id}/evaluate/j1eval` | J1-EVAL |
| `GET /game/{id}/liability-chain` | CADD 责任链 |
| `POST /game/{id}/evaluate/behavior-symmetry` | 对称行为 |
| `GET /game/{id}/strategy/payoff-matrix` | 收益矩阵 |

系统页实验面板走 **`POST /case/progressive-rag|dual-mode-reasoning|multi-judge`**。`game.py` 里另有会话版同名接口，两者并存。

Web 对照主路是 **`POST /evaluate`**。别名：`/api/evaluation/status|results|reports`。

## 数据与 ID

- 会话：`data/conversations.sqlite3`
- 评测任务：`data/app_state.sqlite3`
- 博弈 / 调解：`data/game_sessions.sqlite3`、`data/mediation_sessions.sqlite3`
- Checkpoint / LLM 缓存：`data/checkpoints.sqlite3`、`data/llm_cache.sqlite3`
- 法条：`database/legal_articles.db` + `.index` + `_id_map.npy`

`input_json.links`：`task_id` / `game_id` / `report_id`。独立调解 `med_*` 不进这三键。前端本场：`lexgentium.lastSessionId`。

`data/dataset_1000/` 仓库内目前是 `dataset_meta.json` 与 100 条三案由摘要，**没有** train/val/test 全文 jsonl。选案走 `GET /reference/cases`。完整 1000 条需按 `scripts/build_dataset.py` 从 ClaimGen-CN 重建。

## 环境旗

见 `.env.example`：`CI_USE_GRAPH`、`PLEAD_USE_RUNTIME`、`LLM_CACHE`、`CI_LEGACY_ANALYSIS`、`API_TOKEN`、`LLM_FAST_MODEL`。

## 引用

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

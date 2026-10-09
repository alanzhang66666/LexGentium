# LexGentium 1.0 CODEMAP

盘点截止 **2026-10-09**。B–F 已搬家。本页是现役分层地图，不是施工前标签稿。

观庭产品入口是 `/hearing-3d`（LIVE Phase A，供应商 OBJ + PBR，程序化人物 fallback，非正式 VRM）。旧 `/court3d` `/court3d/[id]` `/court3d/replay` **重定向**到这里。胶囊渲染、导播、TTS、conversation/full/replay 适配器已删。留下 `labels` / `parseSse` / `gameStream`。没有独立 3D FastAPI。

权威现状仍是 [`SYSTEM_STATUS.md`](SYSTEM_STATUS.md)。本页只回答：每个夹什么身份、谁在用、删了主环会死吗。

## 标签

| 标签 | 意思 |
|------|------|
| **LIVE** | Web 主路。开庭 / 书状 / 听证 / 复盘 / 研究工作台 |
| **RESEARCH** | 研究轨。民事训练集不要掺 |
| **OFFLINE** | 批跑 / 最近邻。不是 Web |
| **LAB** | 实验。删了主环还能开庭 |
| **FOSSIL** | 旧结果 / 旧表 / 论文图。别当现役答案 |
| **FROZEN** | 本轮不搬、不改 |

一夹可以有两个标签（例如 `LIVE+管子`）。

---

## 冻：剧场 + 管子

| 路径 | 标签 | 谁用 | 删了主环会死吗 |
|------|------|------|----------------|
| `app/court3d/` | REDIRECT | 三页都转到 `/hearing-3d` | 产品观庭不走这里 |
| `lib/court3d/` | 管子 | parseSse / protocol（labels）/ gameStream | 删了复盘博弈 SSE 会疼 |
| `public/court3d/` | LEGACY | 旧剧组 JSON / 空 models。replay 已删 | 产品页不读 |
| `app/hearing-3d/` | LIVE Phase A | 现役观庭（供应商 OBJ + PBR，程序化人物 fallback） | **会死观庭**。非正式 VRM |
| `components/hearing-3d/` | LIVE Phase A | 场景、OBJ/PBR 角色、程序化 fallback、HUD、事件适配 | 同上 |
| `public/hearing-3d/` | LIVE Phase A | 事件/卡司/布局合同 + OBJ/PBR 运行资产与样例 | 同上 |
| `docs/COURT3D_ASSET_SPEC.md` | FROZEN | 换 VRM 说明书 | 不会。换模型的人会迷路 |
| 仓库根 `3D建模方案/` | FROZEN | 设计稿 | 不会。不是运行时 |

管子（URL + 帧形状冻结；**文件可搬，字段不能拧**）：

| 适配器 | 打谁 | 帧 |
|--------|------|-----|
| `lib/court3d/adapters/gameStream.ts` | `POST /api/game/{gameId}/stream-round` | `round_start` `strategy_switch` `score_update` |
| `lib/court3d/parseSse.ts` | 复盘博弈 SSE 与 `lib/api/sse.ts` | `delta` / `final` 等块 |

SSE 发言最小字段：`role` / `text` / `degraded?` / `sub_stage?`。一场一个 `session_id`。博弈只认 `links.game_id`。

改开庭之后，观庭冒烟：开一场 → `/hearing-3d?sessionId=` 有历史发言；输入框 SSE 能追加 `utterance_committed`。博弈分 HUD 不在新观庭里（仍在 `evaluation` 策略栏）。

---

## 顶层 12 项

| # | 路径 | 标签 | 谁 import / 打开 | 删了主环会死吗 |
|---|------|------|------------------|----------------|
| 1 | `api_server.py` | LIVE | 人跑 Web；装 `api.routers` + `api.state` | **会死**。唯一 Web 入口 |
| 2 | `main.py` | OFFLINE | 人跑批处理；`settings`；`COURT_API_*` | 不会。Web 不走这里 |
| 3 | `agents/` | LIVE | `api.runtime`、`case_orchestrator`、测试、`main.py` | **会死**。CD/DD/CI/Sim。提示词原文别改 |
| 4 | `api/` | LIVE（部分管子） | `api_server` → routers → services | **会死**。薄路由+业务。见下表拆档 |
| 5 | `core/graphs/` | LIVE（管子后面） | CI/CD/DD runtime、全案图、checkpoint | **会死**。Hearing / Plead 默认开。可分包，勿改 SSE 字段 |
| 6 | `core/research/` | RESEARCH | 研究路由、开庭水合、主张链、量表 | 无 pack 时民事不改。正式案仍 = 0 |
| 7 | `app/` | LIVE + 旧岛重定向 | Next 页 + `/api/*` BFF | **会死**。观庭 href 走 `/hearing-3d` |
| 8 | `evaluation/lib/` | LIVE + RESEARCH | `api/state`、`api/services/evaluation.py`、`research_eval.py`、`game.py`、`sim_agent` | **复盘会死**。量表在这里。旧 `CD.py` `DD.py` `CI.py` `game_eval.py` 已去 `lab/legacy/` |
| 9 | `evaluation/results/` | LIVE 输出 | `eval_config.yaml` `output.root`；Web 对照新报告 | 不会。空夹 + README。旧跑数在 `归档/评测化石/results/` |
| 10 | `scripts/` | 混（见下） | 人跑 | 不会。Web 不依赖 |
| 11 | `tests/` | LIVE 护栏 | pytest 68 个 test 模块 | 不会立刻死。搬 `core/` / research 前先跑 |
| 12 | `docs/` | 混 | 人读 | 不会。`COURT3D_ASSET_SPEC` 冻。旧 76 项表 / 离线备选 / 申请书图已去 `归档/` |

### `api/` 拆档

| 路径 | 标签 | 说明 |
|------|------|------|
| `api/routers/conversation.py` `case.py` `game.py` | LIVE+管子 | 可搬家，不可改 3 条 SSE URL/帧 |
| `api/services/conversation.py` `simulation.py` `game.py` `sse.py` | LIVE+管子 | 同上 |
| `api/services/links.py` | LIVE+管子 | `task_id` / `game_id` / `report_id` |
| `api/routers/research.py` + research services | RESEARCH | 不经 court3d |
| `api/routers/evaluate.py` + `services/evaluation.py` | LIVE | Web `POST /evaluate` |
| `api/routers/health.py` `api/routers/config.py` `api/routers/database.py` | LIVE | 系统页。不是已删的根 `config.py` |
| `api/routers/mediation.py` | LIVE 半官方 | 独立 `med_*`，不是庭内和解 |
| `api/routers/legacy.py` `innovation.py` | LAB | `/simulate`、实验面板 |
| `api/state.py` | LIVE | 运行时装配。import `settings`、`api.schemas`、`api.runtime` |
| `api/schemas.py` | LIVE | Pydantic 模型。原根文件 `api_schemas.py` |
| `api/runtime.py` | LIVE | 智能体装配 + `MockApiClient`。原根文件 `api_runtime.py` |

### `app/` 拆档

| 路径 | 标签 |
|------|------|
| `app/court3d/**` | REDIRECT → `/hearing-3d` |
| `app/hearing-3d/**` | LIVE 观庭（供应商 OBJ + PBR，程序化人物 fallback，非正式 VRM） |
| `app/conversation/**` `app/full-simulation/` `app/evaluation/**` | LIVE；观庭 href 走 `/hearing-3d` |
| `app/research/**` | RESEARCH |
| `app/mediation/` | LIVE 半官方 |
| `app/login/` `register/` `system/` `settings/` `database/` `api-history/` | LIVE 系统 |
| `app/simulate/` | LAB |
| `app/page.tsx` `about/` `docs/` | LIVE 营销壳 |
| `app/api/conversation/**` `case/**` `game/**` | LIVE+管子（BFF 路径冻） |
| `app/api/research/**` `evaluate/**` `mediation/**` | 随对应档 |
| `app/api/case/progressive-rag` 等实验代理 | LAB |

### `scripts/` 拆档

| 文件 | 标签 | 干什么 |
|------|------|--------|
| `build_dataset.py` `verify_dataset.py` | LIVE 数据 | 民事 1000 条重建；仓库已含 train / val / test JSONL 与配套 GT |
| `reindex_database.py` | LIVE 数据 | 法条 FAISS |
| `bench_hearing.py` `bench_plead.py` | LIVE 基线 | 听证/书状窗口 |
| `eval_ci_with_j1bench.py` | OFFLINE | J1 批跑 |
| `evaluate_hybrid_solution.py` | OFFLINE | 最近邻/混合 |
| `run_experiments.py` `run_preliminary_experiments.py` | LAB | 论文实验 |
| `test_api_endpoints.py` | LAB | 手搓接口检查 |

### `tests/` 68 个 test 模块

| 文件 | 护哪 |
|------|------|
| `test_hearing_*` `test_plead_*` `test_cd_context_window` `test_ci_concurrency` `test_llm_budget` `test_inference_speed` | LIVE runtime |
| `test_reasoning_contracts` `test_reasoning_execution` `test_fact_ledger` | LIVE 推理 Phase 0/1 |
| `test_session_*` `test_pack_hydration` | LIVE 会话 / 水合 |
| `test_research_*` | RESEARCH |
| `test_eval_attribution` `test_game_score_degraded` | LIVE 复盘 |
| `test_law_retrieval` `test_faiss` `test_new_db` | LIVE 法条 |
| `test_offline_governance` | OFFLINE 边界 |

`e2e/` 有 3 个 Playwright spec：主流程 smoke、旧 `/court3d` 重定向、冷启动性能；`/hearing-3d` 另有 Vitest（`components/hearing-3d/*.test.ts`，`npm run test:3d`）。旧胶囊页无单测，渲染已删。

---

## 12 项以外（整理时会碰到）

### 根上 Python（C 已收口）

人只记两个门：`api_server.py`（Web）、`main.py`（离线）。

| 路径 | 标签 | 谁 import | 删了主环会死吗 |
|------|------|-----------|----------------|
| `settings.py` | LIVE 配置 | `api/state.py` `main.py` 两个脚本。不是门 | **会死**。真配置。原 `config.py` 薄壳已删 |
| `api/schemas.py` | LIVE | 几乎所有 `api/routers/*`、`api/state.py` | **会死** |
| `api/runtime.py` | LIVE | `api/state.py`；测试和 bench 用 `MockApiClient` | **会死** |

### `core/` 其余（不在 12 项里）

| 路径 | 标签 |
|------|------|
| `store/` | LIVE 存储：会话 / 评测任务 / 博弈 / 调解。不是 `graphs/checkpoint` |
| `llm_client.py` `law_retriever.py` `schemas.py` `state_machine.py` `langchain_utils.py` | LIVE |
| `case_orchestrator.py` `game_engine.py` `mediation_engine.py` | LIVE / 半官方 |
| `case_bundle.py` `fact_ledger.py` `issue_graph.py` `irac.py` `judgment_validator.py` `reasoning_state.py` | LIVE 推理 Phase 0/1。Web 听证主路用。不要搬进 `lab/` / `offline/` |
| `nash_*.py` `extensive_form.py` `evolutionary_dynamics.py` | LIVE 博弈数学 |
| `api_client.py` | LIVE 客户端。可选挂 `offline/` 最近邻/混合模拟 |
| `offline/` | OFFLINE：`api_reconstructor` `llm_api_simulator` `evaluator`。`main.py --use-reconstructor` 与混合批跑 |
| `lab/` | LAB：P-RAG / Dual-Mode / Multi-Judge / 责任链。**不经听证 SSE** |

### `evaluation/` 其余

| 路径 | 标签 | 谁用 |
|------|------|------|
| `run_evaluation.py` converters / adapters / evaluators | LIVE | `api/services/evaluation.py`（Web 对照） |
| `lib/research_rubric.py` | RESEARCH | `api/services/research_eval.py` |
| `lib/lexeval_*` `j1eval_*` `cadd_*` `outcome_*` `solution_*` `multi_layer_*` | LIVE | `api/state.py`、博弈评测路由 |
| `lab/` | LAB | 论文批跑。`python evaluation/lab/run_*.py`。新输出 `evaluation/results/` |
| `lab/legacy/` | LAB | `CD.py` `DD.py` `CI.py` `game_eval.py` `utils_func.py`。Web 不 import |
| `data/test_run/` | LIVE 夹具 | 对照评测小样 |
| `results/` | LIVE 输出 | 新对照报告。不要提交 |
| `fossil/` | 指针 | 旧跑数已去仓库根 `归档/评测化石/results/` |

### 数据与别的夹

| 路径 | 标签 | 说明 |
|------|------|------|
| `data/research_packs/` | RESEARCH 夹具 / 候选包 | `enf-cn-notice-001`、`cisg-art79-sample-001` 是 SAMPLE；`enf-us-yingfan-amazon-001` 是 `0.1.0-draft` 候选演示包，均不算正式案 |
| `data/dataset_1000/` | LIVE 民事 | `train / val / test：600 / 200 / 200`，各有 `case_info.jsonl` 和配套 CD/DD/CI GT |
| `data/*.sqlite3` | LIVE 运行时 | 不提交 |
| `database/` | LIVE | 法条 + FAISS |
| `components/` | LIVE | 导航、听证文字、研究控件、ui；`hearing-3d/` 为现役观庭。旧 `court3d/` 渲染已删 |
| `lib/api/` `lib/session/` `lib/research/` | LIVE / RESEARCH | 前端客户端。`lib/labels.ts` import 了 court3d `Actor` 类型，改时小心 |
| `utils/` | LIVE 杂 | logger / data_loader / dialog_history |
| 仓库根 `归档/申报材料/figures/` | FOSSIL | 申请书插图（原 `docs/figures/`） |
| 仓库根 `归档/工程化石/` | FOSSIL | 旧 76 项表、`API_ALTERNATIVES`、`API_RECONSTRUCTION` |
| 仓库根 `归档/评测化石/results/` | FOSSIL | 2026-04 旧跑数 |

仓库根 `法学材料/` `归档/` 本来就不是运行入口，本图不收。

---

## 已做 / 下一刀

- **B 已做（2026-09-15）**：`evaluation/` 拆成 LIVE 对照链 / `lab/` / `fossil/`。地图见 [`evaluation/README.md`](../evaluation/README.md)。
- **C 已做（2026-09-15）**：`api_schemas.py` → `api/schemas.py`，`api_runtime.py` → `api/runtime.py`，删除 `config.py`。根上只留 `api_server.py` / `main.py` 两扇门 + `settings.py` 配置。
- **D 已做（2026-09-15）**：LAB 出列。`evaluation/lib/{CD,DD,CI,game_eval,utils_func}` → `evaluation/lab/legacy/`；`core/` 四个实验引擎 → `core/lab/`。`core/__init__` 不再导出它们。
- **E 已做（2026-09-15）**：离线重建入 `core/offline/`。`api_client.py` 仍留在 `core/`（Web 智能体客户端）。`graphs/` 未动。
- **F 已做（2026-09-15）**：四个 `*_store` 入 `core/store/`。听证 checkpoint 仍在 `graphs/`。
- **化石已出 `docs/`（2026-09-16）**：`figures/` → `归档/申报材料/figures/`；旧 STATUS / API 备选 → `归档/工程化石/`；推理 v1 → `归档/技术报告/`；`evaluation/fossil/results/` → `归档/评测化石/results/`。
- 观庭产品入口已换成 `/hearing-3d`。`/court3d` 三页重定向。胶囊渲染 / 导播 / TTS / conversation·full·replay 适配器已删（2026-09-16）。留下 labels / parseSse / gameStream。

下一刀若继续：博弈数学（`nash_*` / `extensive_form` / `evolutionary_dynamics`）入 `core/game/`。不要动 `graphs/`。

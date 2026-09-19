# LexGentium

国际商事仲裁听证仿真工作台。能跑的代码只在 `mock_court_system/`。版本 `0.8.0`。

## 怎么跑

两个终端都进 `mock_court_system`：`python api_server.py`（:8000）和 `npm run dev`（:3000）。先 `cp .env.example .env`，填 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`。

## 技术栈

Next.js 16 BFF + FastAPI。CD / DD / CI / Sim 智能体。听证走 `HearingRuntime`，书状走 `PleadRuntime`。民事评测是 LexEval / J1 / CADD；研究量表在 `evaluation/lib/research_rubric.py`。

## 目录

- `mock_court_system/` 唯一启动入口。不要把申报稿、3D 设计、法学母表拷进 `public/`。
- `法学材料/` 包含指南、候选母表，以及 `案例材料/` 下 67 份原文/标注素材；其中 15 份标注均未完成独立复核，不是正式研究包。
- `归档/` 申报、商计、论文、外仓推理对照稿、工程化石、评测化石。不是运行入口。
- `3D建模方案/` 设计稿（说明书在 `说明/`）。

## 现役边界（下一轮不看到就会做错）

1. 民事 `dataset_1000` 和 RESEARCH（CISG / 纽约公约执行）分轨。不要把研究包装进民事训练集。
2. `data/research_packs/` 里两个 SAMPLE 是技术夹具，**不算**正式研究案。正式研究包 = 0。
   `法学材料/案例材料/` 的 15 份未复核标注也不计入正式研究包，案例 25 还是 AI 辅助初标待确认。
3. 未知事实保持 unknown，禁止补造。材料不足用 `admit_insufficient` 停。
4. 研究论证轮次：纽约执行 12、CISG 第 79 条 10。只计原被告发言。到上限不要再打 CI LLM。
5. 书记员 / extract / score 用 `LLM_FAST_MAX_TOKENS`（默认 512）。判决不要截短。全案自动 CI 默认最多 30 步（`CI_MAX_AUTO_TURNS`）。
6. 不要提交 `.env`、`*.sqlite3`、`data/session_predictions/`。没有真文件时不要建空的选案/原文/规则卡夹。
7. Web 主路是 LLM 智能体。`core/offline/api_reconstructor` / `main.py` 最近邻只给离线批跑。
8. Phase 0/1 已在本树（`core/case_bundle.py` / 事实台账 / IRAC / `reasoning_meta`）。`归档/技术报告/` 仍是外仓对照稿，不要当未落地说明。分层地图：`mock_court_system/docs/CODEMAP.md`。

下一步：法学侧填正式研究包，不要先扩民事引擎。

观庭产品入口是 `/hearing-3d`。旧 `/court3d` 重定向，不要再把胶囊厅当现役观庭。

权威现状：`mock_court_system/docs/SYSTEM_STATUS.md`。

# LexGentium 1.0 系统现状

盘点截止 **2026-10-09**。产品名：国际商事仲裁研究平台。版本 **1.0.0**。以当前仓库代码为准。2026-09-11 的 76 项原表已挪到 [`归档/工程化石/SYSTEM_STATUS_2026-09-11.md`](../../归档/工程化石/SYSTEM_STATUS_2026-09-11.md)，那份表**不再是现役答案**。分层地图见 [`CODEMAP.md`](CODEMAP.md)。

## 一句话

民事工作台能开庭、观庭、复盘。研究工作台（`/research`）已接通。正式法学研究案 **0**。`enf-cn-notice-001`、`cisg-art79-sample-001` 是 SAMPLE 夹具；`enf-us-yingfan-amazon-001` 是 `0.1.0-draft` 候选演示包，尚未独立复核。

## 现役事实

| 面 | 现在是什么 | 不是什么 |
|----|------------|----------|
| 产品 | Next 页；`/conversation` `/research` `/hearing-3d` `/evaluation` | 没有账号表；软解锁。旧 `/court3d` 重定向 |
| 运行时 | HearingRuntime + PleadRuntime 默认开 | 无研究包时民事 CD/DD/CI 不改 |
| 研究工程 | 角色材料过滤、主张链、派生 `run_id`、六维量表、导出 | 不是已标完的 10–20 案 |
| 研究数据 | SAMPLE：`enf-cn-notice-001`、`cisg-art79-sample-001`；候选：`enf-us-yingfan-amazon-001`（`0.1.0-draft`，尚未独立复核） | 正式 pack = 0 |
| 法学材料 | 指南 + 原始母表 + `案例材料/`（67 份素材、15 份已填标注） | 15 份均未完成独立复核；不是正式 pack |
| 民事数据 | `dataset_1000/` 的 train / val / test：600 / 200 / 200；各有 `case_info.jsonl` 和配套 CD/DD/CI GT | CASE 编号在不同划分重名，需保存完整数据集身份 |
| 3D | 观庭 = `/hearing-3d`（供应商 OBJ + PBR，程序化人物 fallback）。旧 `/court3d` 重定向 | 非正式 VRM。胶囊渲染已删；留下 parseSse / labels / gameStream |
| 推理 | Phase 0/1 已合并：`case_bundle` / 台账 / IRAC / `reasoning_meta`；clerk/extract/score ≤512 token；自动 CI ≤30；研究 10/12 轮停 | LAB（P-RAG / Dual-Mode / Multi-Judge）不经听证 SSE |
| 分层 | `core/lab` `core/offline` `core/store`；`evaluation/lab`。旧跑数在 `归档/评测化石/` | 旧跑数不是现役答案 |
| 测试 | `tests/` 含 68 个 test 模块，覆盖 research / reasoning / property / contract / integration；`e2e/` 有 3 个 Playwright spec（journey、旧路由重定向、性能）；另有观庭 Vitest | 观庭视觉不在自动化检查内，需本机浏览器核对 `/hearing-3d` |

## 已接通的研究入口

- `/research`、`/research/packs/[dataset]/[cluster]`
- `/conversation` 选研究包水合
- `/conversation/[sessionId]` 主张链
- `/evaluation?pane=research`
- FastAPI：`/research/packs|runs|evaluate|review|compare|export`

不经旧胶囊厅。观庭产品入口是 `/hearing-3d`。

## 明确未做（法学内容）

- 正式研究包、规则卡、原文锚点回填
- `案例材料/` 中 15 份标注的独立复核（案例 25 仍是 AI 辅助初标待确认）
- `RESEARCH_PROTOCOL.md` 独立成文（约束写在根目录 `AGENTS.md`）
- 3D VRM（观庭已是供应商 OBJ + 程序化 fallback，非正式 VRM）
- 正式研究包不能由民事 1000 条数据替代

## 发布状态

工作台保留开庭 / 研究 / 观庭 / 复盘 / 系统导航；`/court3d` 重定向到 `/hearing-3d`。发布与合并状态以 GitHub 当前分支、PR 和 CI 检查为准。

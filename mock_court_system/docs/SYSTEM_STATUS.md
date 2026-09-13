# LexGentium 0.8 系统现状

盘点截止 **2026-09-14**。以当前仓库代码为准。2026-09-11 的 76 项原表已挪到 [`SYSTEM_STATUS_2026-09-11.md`](SYSTEM_STATUS_2026-09-11.md)，那份表**不再是现役答案**。

## 一句话

民事工作台能开庭、观庭、复盘。研究工作台（`/research`）已接通。正式法学研究案 **0**。两个 SAMPLE 包是夹具。

## 现役事实

| 面 | 现在是什么 | 不是什么 |
|----|------------|----------|
| 产品 | Next 21 页；`/conversation` `/research` `/court3d` `/evaluation` | 没有账号表；软解锁 |
| 运行时 | HearingRuntime + PleadRuntime 默认开 | 无研究包时民事 CD/DD/CI 不改 |
| 研究工程 | 角色材料过滤、主张链、派生 `run_id`、六维量表、导出 | 不是已标完的 10–20 案 |
| 研究数据 | SAMPLE：`enf-cn-notice-001`、`cisg-art79-sample-001` | 正式 pack = 0 |
| 法学材料 | `法学材料/指南与工作簿/` + 原始母表 | 候选 ≠ 已标注 |
| 民事数据 | `dataset_1000/` 只有 meta + 100 条摘要 | **没有** train/val/test jsonl |
| 3D | 胶囊人；`models/` 空 | 设计稿在仓库根 `3D建模方案/` |
| 推理加速 | clerk/extract/score ≤512 token；自动 CI ≤30；研究 10/12 轮停 | 外仓 Phase 0 质量栈未移植 |
| 测试 | `tests/` 21 个文件，含 research / inference_speed | 无前端 E2E |

## 已接通的研究入口

- `/research`、`/research/packs/[dataset]/[cluster]`
- `/conversation` 选研究包水合
- `/conversation/[sessionId]` 主张链
- `/evaluation?pane=research`
- FastAPI：`/research/packs|runs|evaluate|review|compare|export`

不经 court3d。

## 明确未做（法学内容）

- 正式研究包、规则卡、原文锚点回填
- `RESEARCH_PROTOCOL.md` 独立成文（约束写在根目录 `AGENTS.md`）
- 3D VRM
- 完整 1000 条民事 jsonl（需 `scripts/build_dataset.py`）

## 发布状态

本地 `main` 已推到 `origin/main`（`ab7f2c4`，2026-09-12）。本机 live 页面本次**未**重新点验。

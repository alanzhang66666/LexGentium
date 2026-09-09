# LexGentium 0.8

国际商事仲裁**听证仿真**工作台。一场听证一个 `session_id`，开庭 → 观庭 → 复盘共用同一会话。

可运行代码在 [`mock_court_system/`](mock_court_system/)。版本号见该目录 `package.json`（当前 **0.8.0**）。

## 仓库结构

```text
.
├── mock_court_system/          # 主工程：Next.js 16 + FastAPI（日常从这里启动）
├── 3D建模方案/                 # 离线角色/场景设计稿，不进 public/
├── 归档/                       # 申报、商计、参考文献（不是运行入口）
├── .venv/                      # 本地 Python 环境（勿提交）
└── README.md
```

评测代码与指标在 `mock_court_system/evaluation/`，仓库根目录不再放空的 `evaluation/`。

## 主工程做什么

`mock_court_system/` 把原告/被告律师、仲裁庭、当事人抽象为 Agent（`CD` / `DD` / `CI` / `Sim`），并接上博弈推演、五阶段调解、法条检索和多维评测。

| 环 | 页面 | 作用 |
|----|------|------|
| 开庭 | `/conversation` `/full-simulation` `/mediation` | 申请/答辩/听证、全案、独立 HDR 调解 |
| 观庭 | `/court3d` `/court3d/[id]` `/court3d/replay` | 3D 听证（无 VRM 时用胶囊人） |
| 复盘 | `/evaluation` | 对照 / 策略推演 / 程序合规 |
| 系统 | `/login` `/register` `/system` `/settings` `/database` | 软解锁、健康、LLM、法条 |

浏览器只请求 Next 的 `/api/*`，再由服务端代理到 FastAPI（默认 `:8000`）。

## 技术栈

- 前端：Next.js 16、React 19、TypeScript、Tailwind CSS 4、Radix UI、Three.js / R3F
- 后端：FastAPI、LangChain、OpenAI 兼容 SDK、SQLite、FAISS、BM25 / jieba

配色三套：`ink`（默认）/ `parchment` / `seal`，见 `mock_court_system/DESIGN.md`。

## 快速启动

需要 Python **3.9+**、Node.js **20+**。

```bash
cd mock_court_system
pip install -r requirements.txt    # 可复现：requirements.lock
npm install
cp .env.example .env               # 填写 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
python api_server.py               # http://localhost:8000
npm run dev                        # http://localhost:3000
```

1. 打开 `/register` 写入模型配置，或 `/login` 测通已有配置（软解锁，无用户表）。
2. `/conversation` 开一场 → `/court3d/{session_id}` 观庭 → `/evaluation?session=…` 复盘。
3. 更细的步骤见 [`mock_court_system/docs/INSTALL.md`](mock_court_system/docs/INSTALL.md)。

可选：`.env` 里设 `API_TOKEN` 后，除 `/health` 外后端需要 `Authorization: Bearer`。

## 数据落在哪

| 用途 | 路径 |
|------|------|
| 会话 / 评测任务 / 博弈 / 调解 / checkpoint / LLM 缓存 | `mock_court_system/data/*.sqlite3` |
| 法条库 + FAISS | `mock_court_system/database/legal_articles.*` |
| 开庭选案索引 | `data/dataset_1000/`（仓库内是元数据与 100 条摘要，不是完整 1000 条 jsonl） |

`session_id` 可通过 `input_json.links` 挂上 `task_id`（全案）、`game_id`（博弈）、`report_id`（对照报告）。独立调解是另一套 `med_*` id。

`.env` 和 SQLite 不要提交。

## 文档

| 文件 | 内容 |
|------|------|
| [`mock_court_system/README.md`](mock_court_system/README.md) | 架构、API、论文对应 |
| [`docs/INSTALL.md`](mock_court_system/docs/INSTALL.md) | 安装与本机运行 |
| [`docs/DEPLOY.md`](mock_court_system/docs/DEPLOY.md) | 部署 |
| [`docs/ARCHITECTURE.md`](mock_court_system/docs/ARCHITECTURE.md) | 页面 / 代理 / 运行时 |
| [`docs/EVALUATION_GUIDE.md`](mock_court_system/docs/EVALUATION_GUIDE.md) | Web 复盘与离线评测 |
| [`docs/COURT3D_ASSET_SPEC.md`](mock_court_system/docs/COURT3D_ASSET_SPEC.md) | 3D 角色替换规格 |
| [`DESIGN.md`](mock_court_system/DESIGN.md) | 视觉与双壳导航 |
| [`归档/README.md`](归档/README.md) | 申报与参考文献清单 |

`3D建模方案/` 只作设计参考，不要拷进 `public/court3d/models/`。

## 归档

`归档/` 存放申请书终稿、商业计划和论文 PDF，不是启动入口。超过 GitHub 100MB 的答辩/展示文件未纳入仓库。

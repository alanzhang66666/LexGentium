# LexGentium 0.8 安装与运行（Web 主路径）

本指南对应目录 **`mock_court_system/`**（`package.json` 版本 **0.8.0**）。日常开发与演示走 **FastAPI + Next.js**，不走远程批跑。

环境要求：Python **3.9+**，Node.js **20+**。

## 1. 安装依赖

在 `mock_court_system` 目录下：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# 可复现组合：pip install -r requirements.lock
npm install
```

Linux / macOS：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install
```

## 2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

至少填写：

```bash
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

法条向量重建（可选）需要 `DASHSCOPE_API_KEY`（或兼容的 `LLM_API_KEY`），然后：

```bash
python scripts/reindex_database.py
```

法条库在 `database/`（`legal_articles.db` / `.index`），不在 `data/`。

## 3. 启动（Web 主路径）

两个终端，均在 `mock_court_system`：

```bash
python api_server.py          # http://localhost:8000  Swagger: /docs
npm run dev                   # http://localhost:3000
```

浏览器只打 Next（默认 3000）。后端路由在 `api/routers/`，`api_server.py` 只做装配。

推荐入口：`/register` 或 `/login`（写入/测通 LLM，软解锁）→ `/conversation`（开庭）→ `/hearing-3d?sessionId=`（观庭）→ `/evaluation`（复盘）。一场听证一个 `session_id`。旧 `/court3d` 会转到 `/hearing-3d`。

可选环境旗见 `.env.example`：`CI_USE_GRAPH`、`PLEAD_USE_RUNTIME`、`LLM_CACHE`、`API_TOKEN`。配色三套（ink / parchment / seal）在工作台顶栏切换。

## 4. 常见问题

1. **无法连接后端**：先起 `python api_server.py`，确认 `.env` 里 `BACKEND_URL` 与监听地址一致。
2. **LLM 失败**：检查 `LLM_API_KEY` / `LLM_BASE_URL`；庭审可继续走离线兜底（回复带 `degraded`）。
3. **法条检索未就绪**：`GET /health` 看 `law_retriever_ready`。缺索引时按上面 `reindex` 重建。
4. **找不到 train/val/test jsonl**：仓库里的 `data/dataset_1000/` 只有元数据与 100 条摘要。Web 选案走 `/reference/cases`；完整 1000 条需按 `scripts/build_dataset.py` 重建。附录批跑另有自己的测试集路径。

---

## 附录：批跑（`main.py`）

`main.py` 依赖 `COURT_API_BASE_URL` / `COURT_API_KEY`，用于离线批量跑 CD/DD/CI，**不是** Web 入口。

```bash
python main.py --scenario CD --limit 1
python main.py --scenario CD
python main.py --all
```

场景智能体已实现（`agents/cd_agent.py`、`dd_agent.py`、`ci_agent.py`）。评测 Web 入口见 `docs/EVALUATION_GUIDE.md`。

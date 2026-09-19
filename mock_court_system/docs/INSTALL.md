# LexGentium 1.0 安装与运行（Web 主路径）

本指南对应目录 **`mock_court_system/`**（版本 **1.0.0**）。这是唯一安装、构建和部署工作目录。
日常开发与演示走 **FastAPI + Next.js** 双进程，不走远程批跑。

环境要求：Python **3.9+**，Node.js **20+**。

## 1. 安装依赖（仅锁文件）

在 `mock_court_system` 目录下，只用锁文件安装，不使用未锁定命令：

```bash
python -m venv venv
# Linux/macOS: source venv/bin/activate
# Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.lock
npm ci
```

`npm ci` 严格按 `package-lock.json` 还原；`requirements.lock` 是固定版本集合。
机器可校验的完整命令目录见 `deploy/commands.yaml`（每条含 cwd、前置条件、预期退出码/结果）。

## 2. 配置环境变量

```bash
cp .env.example .env
```

至少填写（生产模板见 `deploy/production.env.template`）：

```bash
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
BACKEND_URL=http://127.0.0.1:8000
```

外部可达部署还必须设置 `API_TOKEN`（并通常设置 `BACKEND_API_TOKEN`、`API_ALLOWED_ORIGINS`）。
非 loopback 绑定且缺少 `API_TOKEN` 时后端会在接受连接前拒绝启动。
法条向量重建（可选）需要 `DASHSCOPE_API_KEY`，然后 `python scripts/reindex_database.py`。

## 3. 启动（Web 主路径）

两个 Web 入口进程，均在 `mock_court_system` 下启动：

```bash
python api_server.py          # FastAPI 后端，默认 127.0.0.1:8000
npm run build && npx next start -p 3000   # 生产前端+BFF；开发用 npm run dev
```

浏览器只访问 Next（默认 3000），业务请求走同源 `/api/*` BFF 代理；凭据只存在于服务端环境。
首次使用走 `/register` 或 `/login` 写入/测通 LLM 配置（软解锁，不是用户账号系统），
再进 `/conversation` 开庭、`/hearing-3d?sessionId=` 观庭、`/evaluation` 复盘。

健康检查：`GET /health/live`（存活）、`GET /health/ready`（逐组件就绪）。

## 4. 离线批跑（非 Web 入口）

`main.py` 与 `core/offline/api_reconstructor` 只用于离线批量，**不是** Web 入口：

```bash
python main.py --scenario CD --limit 1
```

## 5. 常见问题

1. **无法连接后端**：先起 `python api_server.py`，确认 `.env` 里 `BACKEND_URL` 与监听地址一致。
2. **LLM 失败**：检查 `LLM_API_KEY`/`LLM_BASE_URL`；庭审可继续走离线兜底（回复带 `degraded`）。
3. **法条检索未就绪**：`GET /health/ready` 看 `law_retrieval`；缺索引时按上文 `reindex` 重建。
4. **民事数据集**：仓库内 `dataset_1000` 缺完整 train/validation/test JSONL 分片；
   完整 1000 条需按 `scripts/build_dataset.py` 重建，且与研究数据始终分轨。

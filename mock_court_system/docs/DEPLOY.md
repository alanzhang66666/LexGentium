# LexGentium 1.0 部署指南

部署目录是 **`mock_court_system/`**（版本 **1.0.0**），唯一安装/构建/部署工作目录。
Web 主路径为两个进程：**`api_server.py`（FastAPI 后端）** 和 **`npx next start`（Next.js BFF 前端）**。
`main.py` 与 `core/offline/api_reconstructor` 是离线批跑路径，不是 Web 入口，不要对外暴露。

可校验命令目录在 `deploy/commands.yaml`；校验器为 `python scripts/validate_deployment_docs.py --check`。

## 1. 数据现状披露（部署前必读）

- 正式研究包数量：**0**。
- `enf-cn-notice-001` 与 `cisg-art79-sample-001` 两个 SAMPLE 是**技术夹具**（Technical_Fixture），不是正式研究案。
- `法学材料/案例材料/` 的 **15** 份已填标注均未完成独立复核；案例 **25** 仍是 AI 辅助初标、待确认。
- 民事 `dataset_1000` 缺完整 train/validation/test JSONL 分片，与研究数据始终分轨。
- 研究论证轮次上限：纽约公约执行 12、CISG 第 79 条 10（仅计当事人发言）；未知事实保持 `unknown`。

## 2. 服务器准备（non-root）

- OS：Ubuntu 20.04/22.04 或同等；2 核 2–4GB；Python 3.9+、Node.js 20+。
- 创建 non-root 服务账户 `lexgentium`；FastAPI 与 Next 可共用该账户或分设两个 non-root 账户。
- 代码放 `/opt/lexgentium/mock_court_system`；运行时数据、log、evidence 放 `/var/lib/lexgentium/{data,logs,evidence}`，
  仅这些路径对服务账户可写（见 unit 的 `ReadWritePaths`）。

```bash
sudo useradd --system --home /opt/lexgentium --shell /usr/sbin/nologin lexgentium
sudo mkdir -p /var/lib/lexgentium/{data,logs,evidence} /opt/lexgentium
sudo chown -R lexgentium:lexgentium /var/lib/lexgentium /opt/lexgentium
```

## 3. 安装与配置

以 `lexgentium` 身份在 `mock_court_system` 执行（仅锁文件安装）：

```bash
cd /opt/lexgentium/mock_court_system
python3 -m venv venv
venv/bin/pip install -r requirements.lock
npm ci
cp deploy/production.env.template .env   # 或 cp .env.example .env
```

填写 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`。非 loopback 绑定（`API_HOST` 非 127.0.0.1）
**必须**同时设置 `API_TOKEN`，否则进程在接受连接前拒绝启动。

## 4. 进程模型（systemd，non-root）

模板在 `deploy/`：`lexgentium-api.service` 与 `lexgentium-web.service`。
两个单元均以 `User=lexgentium` 运行，声明 `ReadWritePaths`/`ProtectSystem=strict`/`NoNewPrivileges`。

```bash
sudo cp deploy/lexgentium-api.service deploy/lexgentium-web.service /etc/systemd/system/
sudo systemctl daemon-reload
```

## 5. Startup order

启动顺序固定，逐级确认 readiness：

1. 挂载/权限检查：`/var/lib/lexgentium/*` 存在且属 `lexgentium`。
2. `sudo systemctl start lexgentium-api` → 轮询 `curl -fsS http://127.0.0.1:8000/health/live`
   与 `/health/ready`（逐组件；任一 required 失败返回 503）。
3. `sudo systemctl start lexgentium-web` → `curl -fsS http://127.0.0.1:3000/login` 返回 200。
4. BFF smoke：`deploy/commands.yaml` 中各 `smoke.*` 条目逐条执行预期结果。

Shutdown 顺序相反：先 `systemctl stop lexgentium-web` 停止接收新工作，
再 `stop lexgentium-api`；两个单元均声明 `TimeoutStopSec` 作为 graceful shutdown 上限，
后端在停止前取消未提交 operation 并 flush evidence。

## 6. 外部可达：TLS / proxy / token

仅当部署对主机外可达时适用，三者缺一不可：

- **TLS termination**：在代理层终止 TLS，模板 `deploy/nginx.conf.template`。
- **Trusted proxy**：仅信任的代理地址允许写入 `X-Forwarded-*` 头；其他来源的 forwarded header 一律视为不可信。
- **API_TOKEN**：后端校验 `Authorization: Bearer`；BFF 只从服务端环境读 `API_TOKEN`/`BACKEND_API_TOKEN`，
  浏览器不可见；`/docs`、`/redoc`、`/openapi.json` 与受保护路由使用同一 Token 校验。
- 浏览器 state-changing 请求带 `Origin` 时必须在 `API_ALLOWED_ORIGINS` 内，否则 BFF/后端返回 403。

## 7. 日志、metric 与告警

- 日志：每个请求一条 JSON completion log（request_id、route template、method、status、duration、关联 ID），
  journald 收集：`journalctl -u lexgentium-api -u lexgentium-web`。
- Metric：`lexgentium_` 前缀指标（request/error counter、duration histogram、active SSE gauge、LLM 计数）。
- 告警：`monitoring/rules.yaml`（5m 错误率、2m readiness），处置手册 `docs/RUNBOOK.md`。

## 8. Backup / restore / upgrade / rollback

命令均来自 `deploy/commands.yaml`：

- **Backup**：`ops.backup` — 快照含 identity/schema/digest，写到源码树外。
- **Restore**：`ops.restore` — 仅进空 data root，先验 digest，再跑 migration/readiness 与抽样 fingerprint。
- **Upgrade**：先备份；部署新 immutable artifact；跑 migration precheck；readiness 通过后才切换流量。
- **Rollback**：`ops.rollback` — 恢复前一 immutable artifact 与兼容数据快照，验证 `/health/ready`；
  失败不切换生产 data root。RPO ≤24h、恢复/回滚 ≤4h 由 release rehearsal 证明。

## 9. 验证 checklist

```bash
curl -fsS http://127.0.0.1:8000/health/live     # 存活
curl -fsS http://127.0.0.1:8000/health/ready    # 就绪（逐组件）
curl -fsS http://127.0.0.1:3000/login           # BFF/前端可达
python scripts/validate_deployment_docs.py --check   # 文档与命令目录一致
```

## 10. 注意事项

- 不要以 root 运行任一服务；生产进程一律交由 systemd 管理，不用手工后台托管命令。
- 不要提交 `.env`、`*.sqlite3` 或 `data/session_predictions/`。
- 浏览器永不需要也无法设置 API Token；登录/注册页只做 LLM 配置软解锁。

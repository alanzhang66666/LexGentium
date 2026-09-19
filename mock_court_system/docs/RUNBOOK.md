# Runbook — 运维告警处置

告警规则声明在 `monitoring/rules.yaml`，状态机实现与窗口语义测试在 `monitoring/`。
每条规则触发事件携带 `operator_link` 指向本文件对应小节。

## stable-route-error-rate

**规则**：5 分钟窗口内稳定路由请求数 ≥ 20 且错误率 > 5%，在 60s 求值周期内 firing；
条件清除满一个求值窗口后 resolved。

**处置**：
1. 用触发事件关联的 `request_id`/route template 拉取该窗口 JSON request log，定位错误码分布。
2. 区分 `backend_unavailable`/`backend_timeout`（下游）与 `validation_failed`/`internal_error`（本服务）。
3. 下游故障按 DEPLOY.md 的依赖检查顺序确认 SQLite/模型端点；本服务错误按 release gate 决定是否回滚。

## readiness-failure

**规则**：`/health/ready` 任一 required 组件连续失败 2 分钟，在 60s 求值周期内 firing；
恢复后满一个求值窗口 resolved 并记录 `recovered_at`。

**处置**：
1. 读 readiness 响应中的 `failed`/`reason` 集合定位组件（configuration / conversation_store /
   runtime_store / evaluation_store / research_store / law_retrieval / hearing_runtime / plead_runtime）。
2. 按 DEPLOY.md 启动顺序倒查：挂载/权限 → migration precheck → lifespan readiness。
3. 恢复后确认 `recovered_at` 已记录；未记录说明清除未满一个求值窗口，属预期。

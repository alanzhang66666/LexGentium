# Implementation Plan: Release Readiness Optimization

## Overview

本计划只修改 `mock_court_system/` 中的产品、测试、部署与发布工具，以及本任务明确要求的现有安装/部署文档；不修改本 spec 的 `requirements.md`、`design.md`、`.config.kiro`，不修改仓库根法律材料、归档或 3D 设计稿。任务按设计的 Phase A–G 迁移顺序增量推进，优先关闭评测契约、CI 30 步、BFF、浏览器 Token、SSE/幂等取消、生产安全、SQLite、评测来源、可观测性和发布门禁 blocker。

每个叶子任务都给出完成验收与非 watch 验证命令。命令工作目录均为 `mock_court_system/`。命令中出现的新脚本或 npm script 由对应任务先实现；不得用开发服务器或 watch 模式作为任务验收。

## Tasks

- [ ] 1. Phase A — 固化工具链、范围、版本和优先契约
  - [x] 1.1 核验并精确锁定属性测试与 E2E 依赖
    - 先根据 `requirements.lock`、`package-lock.json`、Python/Node/Next/Vitest 实际版本做兼容性核验，再把 Hypothesis、fast-check、Playwright 及其直接新增工具以**核验后的精确版本**写入依赖声明和锁文件；计划中不得预填或猜测版本。
    - 新增 `test:release`、`test:e2e` 等一次性脚本，保持 `test:3d` 独立且不进入本 feature 的发布结论。
    - 验收：锁文件无范围占位或未解析项，干净安装解析一致。
    - 验证：`python -m pip check && npm ci && npm ls --depth=0`
    - _Requirements: 18.1, 18.2, 18.3, 19.4_

  - [x] 1.2 建立范围、路由、配置与版本声明源
    - 新增 `release/routes.yaml`、`release/configuration.yaml`、共享版本常量和 catalog loader；从 FastAPI/Next 实际路由生成差异报告，稳定/实验路由严格分区。
    - 把 `SYSTEM_STATUS.md` 摘要、正式包 0、两个 SAMPLE 夹具、15 份未独立复核、案例 25 待确认、民事 split 缺失和观庭视觉排除编码为可校验 inventory，不复制材料、不创建空材料目录。
    - 验收：所有版本表面为 `1.0.0`，旧 `/court3d` 仅列重定向契约，`components/hearing-3d` 视觉检查不进入 gate。
    - 验证：`python -m pytest tests/release/test_manifest_inventory.py -q`
    - _Requirements: 1.1–1.5, 1.10, 2.1–2.10, 18.3, 18.4, 20.13_

  - [x] 1.3 优先关闭评测 schema、路由与 BFF 类型漂移
    - 对齐 `api/schemas.py`、`api/routers/evaluate.py`、`api/services/evaluation.py` 和对应 `app/api/evaluate/**`、TypeScript 类型中的 `session_id`、`run_id`、`report_id`、任务状态与错误字段。
    - 保持现有兼容字段，拒绝未声明输入；此任务只修正合同，不提前实现 provenance 存储。
    - 验收：schema 序列化、路由返回和 BFF 类型无隐式运行时字段。
    - 验证：`python -m pytest tests/test_eval_attribution.py tests/contract/test_evaluation_schema_contract.py -q && npm run lint`
    - _Requirements: 3.10, 4.2, 4.9, 15.1, 15.5, 15.6_

  - [x]* 1.4 编写属性测试：Property 1 排除范围不影响发布结论
    - 在 `tests/property/test_release_gate_properties.py` 验证任意观庭视觉结果变化不改变 gate 结论。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_1 -q`
    - **Property 1: 排除范围不影响发布结论**
    - **Validates: Requirements 1.3, 18.3**

  - [x]* 1.5 编写属性测试：Property 3 路由清单完整分区
    - 验证每条 route 恰属 stable/experimental 之一且稳定项字段完整。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_3 -q`
    - **Property 3: 路由清单完整分区**
    - **Validates: Requirements 2.1, 2.2**

  - [x]* 1.6 编写属性测试：Property 4 版本表面一致
    - 验证仅当 package、UI、health、manifest 全为 `1.0.0` 时通过。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_4 -q`
    - **Property 4: 版本表面一致**
    - **Validates: Requirements 2.5**

  - [x]* 1.7 编写属性测试：Property 5 民事 split 缺失集合准确
    - 对 train/validation/test 任意现存子集验证差集结果。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_5 -q`
    - **Property 5: 民事 split 缺失集合准确**
    - **Validates: Requirements 2.6**

- [ ] 2. Phase A/D — 统一 Request、错误和 BFF 合同
  - [x] 2.1 实现 RequestContextMiddleware 与 PublicError
    - 新增 `api/middleware/request_context.py`、`api/errors.py`、`api/contracts/common.py`，改造 `api_server.py`：合法传入 Request ID 原样保留，否则只生成一个；统一 422/500 安全错误和每请求上下文。
    - 验收：响应头、响应体和结构化上下文使用同一 ID，错误不含 Secret、绝对路径、stack、prompt、对话或法律原文。
    - 验证：`python -m pytest tests/contract/test_backend_api_contract.py -k 'request_id or error or validation' -q`
    - _Requirements: 4.7–4.9, 6.1, 6.9, 16.4–16.6_

  - [x] 2.2 实现共享 JSON/SSE BFF 代理
    - 将 `lib/backend-fetch.ts` 演进为 `lib/backend-proxy.ts`、`lib/backend-stream.ts`，让 Route Handler 声明目标而不复制代理逻辑。
    - 区分连接失败 502 与响应头超时 504；保持 status、media type、Request ID、资源 ID、错误值和 SSE 字节顺序，检测后端 ID 不一致为 contract violation。
    - 验收：浏览器只调用同源 `/api/*`，BFF 错误不泄露后端 URL 或原始异常。
    - 验证：`npm run test:release -- --run lib/backend-proxy.contract.test.ts lib/backend-stream.contract.test.ts`
    - _Requirements: 4.1–4.6, 4.11, 4.12, 5.3_

  - [x] 2.3 迁移稳定 Route Handler 到共享代理
    - 逐类迁移 config、conversation、case/full-case、mediation、research、evaluate、health、game 的 `app/api/**/route.ts`；保持 URL、方法和成功 payload 兼容。
    - 验收：catalog 中每个 Stable_Route 都有代理声明；状态、身份、错误不再被 Route Handler 固定为 200 或改写。
    - 验证：`npm run test:release -- --run app/api && npm run lint`
    - _Requirements: 3.1–3.13, 4.1–4.6_

  - [x]* 2.4 编写评测 schema/路由/BFF 契约回归测试
    - 覆盖成功、422、多字段缺失、not-found、500、Request ID 和 `report_id/session_id/run_id`。
    - 验证：`python -m pytest tests/contract/test_evaluation_schema_contract.py -q && npm run test:release -- --run app/api/evaluate`
    - _Requirements: 3.10, 4.2, 4.4, 4.9, 15.5, 15.6_

  - [x]* 2.5 编写 API/BFF 响应类契约测试
    - 参数化 stable response class 的 success、validation、auth、not-found、internal error、timeout、unavailable 和 ID/status preservation。
    - 验证：`python -m pytest tests/contract/test_backend_api_contract.py tests/contract/test_bff_contract.py -q`
    - _Requirements: 4.11, 4.12, 18.6_

  - [x]* 2.6 编写属性测试：Property 13 BFF 保持后端契约
    - 使用 fast-check 在 `lib/backend-proxy.property.test.ts` 生成 JSON/SSE 响应组合。
    - 验证：`npm run test:release -- --run lib/backend-proxy.property.test.ts -t 'Property 13'`
    - **Property 13: BFF 保持后端契约**
    - **Validates: Requirements 4.2, 4.3, 4.4, 5.3**

  - [x]* 2.7 编写属性测试：Property 14 Request ID 归一化且端到端一致
    - 验证合法 ID 保留、非法/缺失 ID 单次生成并贯穿响应与日志。
    - 验证：`python -m pytest tests/property/test_request_contract_properties.py -k property_14 -q`
    - **Property 14: Request ID 归一化且端到端一致**
    - **Validates: Requirements 4.7, 4.8**

  - [x]* 2.8 编写属性测试：Property 15 Validation Error 集合完整
    - 生成多违规请求，验证 field path/reason 完整且无 Secret。
    - 验证：`python -m pytest tests/property/test_request_contract_properties.py -k property_15 -q`
    - **Property 15: Validation Error 集合完整**
    - **Validates: Requirements 4.9**

  - [x]* 2.9 编写属性测试：Property 16 契约身份不匹配必定拒绝发布
    - 验证任一 status/Request ID mismatch 都使 gate no-go。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_16 -q`
    - **Property 16: 契约身份不匹配必定拒绝发布**
    - **Validates: Requirements 4.12**

- [ ] 3. Phase B — 配置、Secret 与 Production_Profile 安全边界
  - [x] 3.1 实现 ConfigurationManager 与生产配置校验
    - 在 `settings.py`、`core/configuration.py`、`api/services/configuration.py` 实现 profile、范围、immutable snapshot、固定 `********` mask、连接测试分类和 temp+fsync+replace 原子更新。
    - 操作接受时捕获配置快照；写失败保留旧 fingerprint/identity；新旧并发操作不串配置。
    - 验收：production 缺必填变量 readiness 失败；配置文件权限受限；fallback/empty/auth/timeout 不得 connected。
    - 验证：`python -m pytest tests/integration/test_configuration_manager.py -q`
    - _Requirements: 3.1–3.3, 6.2, 7.1–7.12_

  - [x] 3.2 移除浏览器 Token 并改为 BFF server-only 认证
    - 删除 `lib/session/unlock.ts` 的 API Token storage/header 行为；软解锁只保留非敏感 UI 状态。BFF 仅从 server-only 配置读取 Token。
    - 验收：Token 不进入 cookie、local/session storage、URL、markup、浏览器日志或 payload；浏览器不能覆盖 BFF Token。
    - 验证：`npm run test:release -- --run lib/session app/login app/register app/settings`
    - _Requirements: 8.3–8.5_

  - [x] 3.3 实现生产认证、Origin、Body Limit 与 docs 保护
    - 在 FastAPI lifespan/认证依赖和 BFF 入口实现非 loopback 无 Token 启动失败、Protected_Route 401、docs 同认证、双层 413、state-changing Origin allowlist fail-closed。
    - 验收：拒绝发生在 socket/业务、持久化或 LLM 调用之前，错误和日志不回显认证材料。
    - 验证：`python -m pytest tests/integration/test_security_profile.py -q && npm run test:release -- --run lib/backend-security.test.ts`
    - _Requirements: 8.1–8.7, 8.9, 8.10, 8.12_

  - [x] 3.4 完成配置页面安全结果与输入恢复
    - 改造 `/register`、`/login` 及相关 API client：显示配置 identity、固定 mask、connected/degraded/failed 和 Request ID；失败保留非 Secret 字段且不持久保存 Secret。
    - 验收：错误采用 PublicError；显式 retry 复用原 Operation ID；登录/注册文案不声称账号认证。
    - 验证：`npm run test:release -- --run app/register app/login lib/session`
    - _Requirements: 2.4, 3.1–3.3, 3.12, 6.5, 7.4, 7.10_

  - [x]* 3.5 编写 Production_Profile 与 Secret 安全集成测试
    - 覆盖三种不同长度 Secret、原子写故障、并发配置快照、外绑/Token/docs、Origin、body limit、markup 和浏览器存储扫描。
    - 验证：`python -m pytest tests/integration/test_configuration_manager.py tests/integration/test_security_profile.py -q && npm run test:release -- --run lib/backend-security.test.ts`
    - _Requirements: 7.12, 8.11, 8.12, 18.10_

  - [x]* 3.6 编写属性测试：Property 25 Secret 恒定掩码与敏感字段删除
    - 验证任意 Secret/内部错误经所有公开序列化出口后只剩固定 mask 且无禁止字段。
    - 验证：`python -m pytest tests/property/test_configuration_properties.py -k property_25 -q`
    - **Property 25: Secret 恒定掩码与敏感字段删除**
    - **Validates: Requirements 6.9, 7.4, 7.5, 8.7, 16.6**

  - [x]* 3.7 编写属性测试：Property 26 Production 配置验证与变量 catalog 完备
    - 验证缺失、类型、范围、连接分类和 catalog 三组分类。
    - 验证：`python -m pytest tests/property/test_configuration_properties.py -k property_26 -q`
    - **Property 26: Production 配置验证与变量 catalog 完备**
    - **Validates: Requirements 7.2, 7.3, 7.10, 7.11**

  - [x]* 3.8 编写属性测试：Property 27 操作捕获接受时配置快照
    - 验证并发接受/提交时间序列下快照不会中途切换。
    - 验证：`python -m pytest tests/property/test_configuration_properties.py -k property_27 -q`
    - **Property 27: 操作捕获接受时配置快照**
    - **Validates: Requirements 7.8, 7.9**

  - [x]* 3.9 编写属性测试：Property 28 外部绑定强制认证
    - 验证 production host/token 组合，loopback 与非 loopback 规则准确。
    - 验证：`python -m pytest tests/property/test_configuration_properties.py -k property_28 -q`
    - **Property 28: 外部绑定强制认证**
    - **Validates: Requirements 8.1**

  - [x]* 3.10 编写属性测试：Property 29 生成文本只按文本呈现
    - 使用 fast-check 生成 HTML/script/event/unicode 字符串，验证 textContent 等值且无执行节点。
    - 验证：`npm run test:release -- --run lib/security/generated-text.property.test.ts -t 'Property 29'`
    - **Property 29: 生成文本只按文本呈现**
    - **Validates: Requirements 8.8**

  - [x]* 3.11 编写属性测试：Property 30 Origin allowlist fail-closed
    - 生成 Origin/方法组合，验证未允许请求 403 且 backend invocation 为零。
    - 验证：`npm run test:release -- --run lib/backend-security.property.test.ts -t 'Property 30'`
    - **Property 30: Origin allowlist fail-closed**
    - **Validates: Requirements 8.10**

- [ ] 4. Phase C/D — Operation Ledger、统一 SSE、幂等与取消
  - [x] 4.1 实现 OperationStore 与状态机
    - 新增 `core/store/operation_store.py`，实现 input digest 冲突、begin/running/commit/fail/cancel、terminal 与 commit CAS、资源回放、call/commit counters。
    - 验收：同 ID+同输入回放；同 ID+不同输入 409；committed 后不可变且 commit_count<=1。
    - 验证：`python -m pytest tests/test_operation_store.py -q`
    - _Requirements: 3.4, 4.10, 5.8, 5.9, 6.6, 11.3_

  - [x] 4.2 实现 Python/TypeScript 对称 SSE_Event_Codec
    - 演进 `api/services/sse.py`、`lib/api/sse.ts`、`lib/court3d/parseSse.ts`：统一 envelope、sequence、id/event/data、typed decode error；前端先双读旧 terminal，后端只写新格式。
    - 验收：合法 round trip 保持全部字段，未知类型/ID 漂移/非递增 sequence 不产生业务事件。
    - 验证：`python -m pytest tests/contract/test_sse_contract.py -q && npm run test:release -- --run lib/api/sse.test.ts`
    - _Requirements: 5.1–5.5, 5.10, 5.11_

  - [x] 4.3 实现 OperationCoordinator、StreamLifecycle 与取消令牌
    - 新增 `api/services/operation_coordinator.py`，首事件 <=1s，terminal CAS，duplicate metric；disconnect 前后 commit 分流，迟到 worker 失去 commit capability。
    - 验收：pre-commit 5s 内取消且 fingerprint 不变；post-commit 保留结果；重试不重复 LLM/final。
    - 验证：`python -m pytest tests/integration/test_sse_lifecycle.py -q`
    - _Requirements: 5.1, 5.4–5.9, 5.12, 6.5, 6.6_

  - [x] 4.4 接入会话、全案与 game 流并更新消费者
    - 将 `api/services/conversation.py`、`simulation.py`、`game.py` 及对应路由/BFF/客户端接入 coordinator；保持现有 URL 和适用 role/text/degraded/sub_stage。
    - 验收：会话、FullCase、game 每个 operation 恰一 terminal，UI 按 sequence 展示并只保存一个 final。
    - 验证：`python -m pytest tests/contract/test_sse_contract.py tests/integration/test_sse_lifecycle.py -q && npm run test:release -- --run lib/api/sse.test.ts`
    - _Requirements: 3.6–3.8, 5.1–5.12, 18.6_

  - [x]* 4.5 编写 SSE 成功、故障、断开、重试和竞态测试
    - 保存 event count、sequence、cancel duration、commit/LLM count 与前后 fingerprint；覆盖重复 terminal 和网络分块。
    - 验证：`python -m pytest tests/contract/test_sse_contract.py tests/integration/test_sse_lifecycle.py -q`
    - _Requirements: 5.12, 18.6, 18.11_

  - [x]* 4.6 编写属性测试：Property 7 Operation ID 幂等提交
    - 参数化 mutation 类型和任意重试次数，验证逻辑资源、commit、LLM 与领域计数不重复。
    - 验证：`python -m pytest tests/property/test_operation_properties.py -k property_7 -q`
    - **Property 7: Operation ID 幂等提交**
    - **Validates: Requirements 3.4, 4.10, 5.9, 6.6, 9.11, 10.9, 11.3, 14.9, 15.10, 18.11**

  - [x]* 4.7 编写属性测试：Property 8 流事件关联身份一致
    - 验证一个 operation 全部事件保持 Operation/Request/Session identity。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_8 -q`
    - **Property 8: 流事件关联身份一致**
    - **Validates: Requirements 3.6, 5.3**

  - [x]* 4.8 编写属性测试：Property 9 Delta 按序且 final 只持久化一次
    - 生成 delta 与网络切分，验证重组全文和单 final。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_9 -q`
    - **Property 9: Delta 按序且 final 只持久化一次**
    - **Validates: Requirements 3.7**

  - [x]* 4.9 编写属性测试：Property 17 SSE sequence 严格递增
    - 验证任意事件序列的非负、严格递增、不重复 sequence。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_17 -q`
    - **Property 17: SSE sequence 严格递增**
    - **Validates: Requirements 5.2**

  - [x]* 4.10 编写属性测试：Property 18 SSE terminal exactly-once
    - 生成 terminal 竞争顺序，验证首个接受、其余忽略及 metric 增量。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_18 -q`
    - **Property 18: SSE terminal exactly-once**
    - **Validates: Requirements 5.4, 5.5, 5.8**

  - [x]* 4.11 编写属性测试：Property 19 提交边界决定断开结果
    - 生成 disconnect/commit 时序，验证 fingerprint 与 commit count。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_19 -q`
    - **Property 19: 提交边界决定断开结果**
    - **Validates: Requirements 5.6, 5.7**

  - [x]* 4.12 编写属性测试：Property 20 SSE codec 往返
    - 生成合法 SseEventV1，验证 encode/decode 语义等价。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_20 -q`
    - **Property 20: SSE codec 往返**
    - **Validates: Requirements 5.10**

  - [x]* 4.13 编写属性测试：Property 21 非法 SSE 不产生业务事件
    - 生成未知类型、缺 identity、非递增 sequence 输入，验证 typed error 与零业务事件。
    - 验证：`python -m pytest tests/property/test_sse_codec_properties.py -k property_21 -q`
    - **Property 21: 非法 SSE 不产生业务事件**
    - **Validates: Requirements 5.11**

- [ ] 5. Phase E — LLM 治理与 Hearing/Plead Runtime 正确性
  - [x] 5.1 优先修复 CI 自动 60/30 不一致
    - 在 `core/case_orchestrator.py` 实现并复用 `ci_auto_turn_limit`，缺省 30，删除 `min(max_turns*3,60)` 语义；达到上限先提交 terminal，不再调用 CI LLM。
    - 验收：现有 `tests/test_inference_speed.py` 导入有效；默认/配置 limit、重复 step 均无额外 call。
    - 验证：`python -m pytest tests/test_inference_speed.py tests/test_ci_concurrency.py -q`
    - _Requirements: 10.7–10.9, 18.1_

  - [x] 5.2 实现 CheckpointV2 与 RuntimeUnitOfWork
    - 扩展 `core/graphs/checkpoint.py` 并新增 `api/services/runtime_unit_of_work.py`；迁入统一 runtime state DB，双读旧 checkpoint、单写 v2，将 conversation/checkpoint/operation commit 放入同一事务。
    - 验收：turn 的 checkpoint/session/operation/number/fingerprint 原子一致；失败保留上一 fingerprint。
    - 验证：`python -m pytest tests/test_hearing_checkpoint.py tests/test_plead_checkpoint.py tests/integration/test_runtime_restart.py -q`
    - _Requirements: 10.3, 10.4, 10.10, 11.2_

  - [x] 5.3 完成 runtime 恢复、隔离、路由与有界上下文
    - 改造 `core/graphs/hearing_runtime.py`、`plead_runtime.py` 和 runtime 装配：最高 committed turn 恢复、>=10 session 隔离、默认 graph 路由、Plead 最近 K turn。
    - 验收：相同文本不合并 identity；restart 后恢复 stage/dialog/facts/links/reasoning/actions。
    - 验证：`python -m pytest tests/test_hearing_graph_parity.py tests/test_ci_concurrency.py tests/test_cd_context_window.py tests/integration/test_runtime_restart.py -q`
    - _Requirements: 3.5, 10.1–10.6, 10.11, 10.12_

  - [x] 5.4 实现 LLMCallContext、缓存身份与预算
    - 演进 `core/llm_client.py`，新增 `core/prompt_registry.py`：purpose/model/config/prompt/input digest 全等缓存；fast 512/配置值，judgment strong+`LLM_MAX_TOKENS`，绝对 deadline，完整判决，空白不伪成功。
    - 验收：迟到响应不能 commit；调用记录含全部关联/identity/token/latency/degraded 字段且无 raw prompt。
    - 验证：`python -m pytest tests/test_llm_budget.py tests/integration/test_llm_gateway.py -q`
    - _Requirements: 6.2, 9.1–9.12_

  - [x] 5.5 实现 UnknownFactGuard 与材料不足停止
    - 将 `core/fact_ledger.py`、reasoning state、research claim flow 接入无来源 assertion rejection；缺材料持久化 `admit_insufficient`，不合成替代结论/引用，停止后续 support/CI 调用。
    - 验收：未知保持 `unknown/absent`，无 anchor 为 unavailable；达到 10/12 party limit 后零额外 CI call。
    - 验证：`python -m pytest tests/test_fact_ledger.py tests/test_reasoning_execution.py tests/test_research_runtime.py -q`
    - _Requirements: 6.7, 6.8, 9.8, 13.1–13.11_

  - [x]* 5.6 编写 runtime、LLM、并发、重启与故障注入测试
    - 覆盖 10 sessions、相同文本、checkpoint failure、restart、30-step、fast/judgment request capture、timeout/empty/late response/cache。
    - 验证：`python -m pytest tests/test_ci_concurrency.py tests/test_inference_speed.py tests/integration/test_runtime_restart.py tests/integration/test_llm_gateway.py -q`
    - _Requirements: 9.12, 10.12, 18.7, 18.8_

  - [x]* 5.7 编写属性测试：Property 24 未知事实与材料不足保持
    - 验证 unknown/absent、claim 非 established、`admit_insufficient` 与停止生成。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_24 -q`
    - **Property 24: 未知事实与材料不足保持**
    - **Validates: Requirements 6.7, 6.8, 9.8, 13.1, 13.2, 13.3, 13.4, 13.11**

  - [x]* 5.8 编写属性测试：Property 31 LLM purpose 决定模型层与预算
    - 验证 fast 三用途和 judgment 的 tier/token 参数。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_31 -q`
    - **Property 31: LLM purpose 决定模型层与预算**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4**

  - [x]* 5.9 编写属性测试：Property 32 判决完整持久化且空白不伪成功
    - 验证非空 judgment 字符等值持久化及空白 response 不成功提交。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_32 -q`
    - **Property 32: 判决完整持久化且空白不伪成功**
    - **Validates: Requirements 9.5, 9.6**

  - [x]* 5.10 编写属性测试：Property 33 LLM 调用记录完整
    - 覆盖成功、失败、缓存、降级终态记录字段。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_33 -q`
    - **Property 33: LLM 调用记录完整**
    - **Validates: Requirements 9.7**

  - [x]* 5.11 编写属性测试：Property 34 Cache identity 全等才命中
    - 逐字段扰动 identity，验证任一差异 miss。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_34 -q`
    - **Property 34: Cache identity 全等才命中**
    - **Validates: Requirements 9.9, 9.10**

  - [x]* 5.12 编写属性测试：Property 35 Runtime turn 原子 checkpoint
    - 验证 committed turn 的五项 identity/fingerprint 不出现部分提交。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_35 -q`
    - **Property 35: Runtime turn 原子 checkpoint**
    - **Validates: Requirements 10.3**

  - [x]* 5.13 编写属性测试：Property 36 Plead 上下文窗口有界
    - 生成任意 history/K，验证最后 K 项和顺序。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_36 -q`
    - **Property 36: Plead 上下文窗口有界**
    - **Validates: Requirements 10.6**

  - [x]* 5.14 编写属性测试：Property 37 停止条件后零额外 LLM 调用
    - 参数化 FullCase、NYC、CISG、admit_insufficient 的限制和终态。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_37 -q`
    - **Property 37: 停止条件后零额外 LLM 调用**
    - **Validates: Requirements 10.7, 10.8, 13.4, 13.5, 13.6, 13.9**

  - [x]* 5.15 编写属性测试：Property 38 相同文本不合并会话身份
    - 验证不同 session 的 operation/checkpoint/correlation 始终不同。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_38 -q`
    - **Property 38: 相同文本不合并会话身份**
    - **Validates: Requirements 10.11**

  - [x]* 5.16 编写属性测试：Property 42 研究发言只计当事人角色且去重
    - 生成混合角色与重复 operation 序列，验证计数。
    - 验证：`python -m pytest tests/property/test_runtime_budget_properties.py -k property_42 -q`
    - **Property 42: 研究发言只计当事人角色且去重**
    - **Validates: Requirements 13.5, 13.6, 13.7, 13.8, 13.10**

- [ ] 6. Phase C — Store Registry、迁移、备份恢复与会话归档
  - [x] 6.1 实现 StoreRegistry 和 additive migrations
    - 新增 `core/store/registry.py`、`migrations.py`，登记 operation/conversation/runtime/evaluation/research 等 required store、schema version 和事务 probe。
    - 验收：probe insert/select/delete 不改业务记录；未知高版本返回 migration_required；不生成或提交实际 `*.sqlite3`。
    - 验证：`python -m pytest tests/integration/test_sqlite_migration_backup_restore.py -k 'registry or migration or probe' -q`
    - _Requirements: 11.1, 11.2, 16.2, 16.3_

  - [x] 6.2 实现 SQLite 在线备份、校验和 clean restore
    - 新增 `core/store/backup.py`，用连接 backup API 生成 store snapshots 和原子 manifest；restore 仅进空 data root，先验 digest，再 migration/readiness 和抽样 fingerprint。
    - 验收：记录 identity/schema/time/digest/max commit；计算 RPO age 和 RTO；失败不覆盖当前 data root。
    - 验证：`python -m pytest tests/integration/test_sqlite_migration_backup_restore.py -k 'backup or restore or digest or fingerprint' -q`
    - _Requirements: 11.8–11.13, 19.7, 20.4_

  - [x] 6.3 实现 Conversation Archive Codec 与事务导入
    - 新增 `core/archive/conversation.py`，完成 parse-all-errors、stable pretty print、preserve/remap identity 和 export-import-export semantic digest；验证成功后才写事务。
    - 验收：invalid archive 不改 record count/fingerprint；合法归档保持 stage/dialog/links/unknown/reasoning/operation identities。
    - 验证：`python -m pytest tests/test_conversation_archive.py -q`
    - _Requirements: 11.4–11.7_

  - [x]* 6.4 编写 SQLite 迁移、失败原子性、备份与恢复集成测试
    - 覆盖 probe、unsupported schema、restart persistence、invalid import、idempotent retry、digest、sample fingerprints、RPO/RTO 计时。
    - 验证：`python -m pytest tests/integration/test_sqlite_migration_backup_restore.py tests/test_conversation_archive.py -q`
    - _Requirements: 11.13, 18.8, 20.4_

  - [x]* 6.5 编写属性测试：Property 23 持久化失败不改变已提交状态
    - 参数化配置、checkpoint、导入、data boundary 的 pre-commit failure point。
    - 验证：`python -m pytest tests/property/test_operation_properties.py -k property_23 -q`
    - **Property 23: 持久化失败不改变已提交状态**
    - **Validates: Requirements 6.4, 7.7, 10.10, 11.5, 12.10, 12.11**

  - [x]* 6.6 编写属性测试：Property 39 Conversation Archive 语义往返
    - 生成合法 archive，验证 pretty-print 可解析和 normalized digest 等值。
    - 验证：`python -m pytest tests/property/test_archive_properties.py -k property_39 -q`
    - **Property 39: Conversation Archive 语义往返**
    - **Validates: Requirements 11.4, 11.6, 11.7**

- [ ] 7. Phase E — 民事/研究分轨、研究治理与停止条件
  - [x] 7.1 实现显式 DataBoundaryClassifier
    - 新增 `core/data_boundaries.py`，以 schema discriminator 区分 civil/research；两个 import boundary 对称拒绝错轨并比较双轨 fingerprint。
    - 验收：civil session 无 research identity 时不水合空 research block；不得创建空选案/原文/规则卡目录。
    - 验证：`python -m pytest tests/test_pack_hydration.py tests/integration/test_data_boundaries.py -q`
    - _Requirements: 12.1–12.3, 12.10–12.12_

  - [x] 7.2 实现 Research Governance、FormalReviewV2 与 Pack Codec
    - 演进 `core/research/*`：固定两个 SAMPLE 为 Technical_Fixture，formal 资格要求完整独立复核五字段及 digest；实现严格 parse/pretty-print/register/compare。
    - 验收：正式数量仍为 0，15 份未复核和案例 25 不注册为 formal；unknown/anchor 状态往返保持。
    - 验证：`python -m pytest tests/test_research_identity.py tests/test_research_workbook.py tests/test_research_annotation.py -q`
    - _Requirements: 12.4–12.9, 14.1–14.9_

  - [x] 7.3 将研究计数和材料不足终态接入 operation/runtime
    - party utterance 仅计 claimant/respondent 且按 Operation ID 去重；NYC 12、CISG 10 和 admit_insufficient 后提交终态并阻止 CI/support call。
    - 验收：非当事人角色不改变计数，重复 operation 不改变计数，终点后 call count 为零。
    - 验证：`python -m pytest tests/test_research_runtime.py tests/test_reasoning_execution.py -q`
    - _Requirements: 13.1–13.11_

  - [x] 7.4 更新研究 inventory/API/UI 与导出比较
    - 更新 research API、`/research`、pack 页面和 evaluation research pane：显示 formal=0、fixture、未复核与 case 25；无 formal pack 返回 no_formal_pack，不回退选择 SAMPLE。
    - 导出包含 pack/run/rubric/model/config/degraded/unknown/anchor；不兼容 identity 拒绝直接比分。
    - 验收：研究状态不污染 civil namespace 或 session fingerprint。
    - 验证：`python -m pytest tests/test_research_eval_export.py tests/test_research_identity.py -q && npm run test:release -- --run app/research lib/research`
    - _Requirements: 2.7–2.9, 3.11, 12.8, 12.9, 14.7, 14.8_

  - [x]* 7.5 编写研究 inventory、codec、边界和计数集成测试
    - 覆盖 formal=0、两夹具、15/case25、双向错轨、round trip、incomplete review、digest mismatch、duplicate register、limit call counts。
    - 验证：`python -m pytest tests/integration/test_data_boundaries.py tests/test_research_runtime.py tests/test_research_workbook.py -q`
    - _Requirements: 12.13, 13.12, 14.10, 18.9_

  - [x]* 7.6 编写属性测试：Property 6 正式研究资格与库存计数
    - 生成库存/复核字段，验证 fixture、未复核、case25 排除和 formal 判定。
    - 验证：`python -m pytest tests/property/test_research_governance_properties.py -k property_6 -q`
    - **Property 6: 正式研究资格与库存计数**
    - **Validates: Requirements 2.7, 2.8, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 14.5, 14.6**

  - [x]* 7.7 编写属性测试：Property 12 无研究包不会改变民事状态
    - 生成 civil state 和空研究分类，验证 empty/no-pack 与 fingerprint 等值。
    - 验证：`python -m pytest tests/property/test_research_governance_properties.py -k property_12 -q`
    - **Property 12: 无研究包不会改变民事状态**
    - **Validates: Requirements 3.11**

  - [x]* 7.8 编写属性测试：Property 40 民事与研究数据分轨
    - 验证 schema/location/identifier/selector/evaluation namespace 及 session hydration 不交叉。
    - 验证：`python -m pytest tests/property/test_research_governance_properties.py -k property_40 -q`
    - **Property 40: 民事与研究数据分轨**
    - **Validates: Requirements 12.1, 12.2, 12.3, 15.8**

  - [x]* 7.9 编写属性测试：Property 41 错轨导入对称拒绝
    - 双向生成 schema-valid 错轨数据，验证拒绝和双 fingerprint 不变。
    - 验证：`python -m pytest tests/property/test_research_governance_properties.py -k property_41 -q`
    - **Property 41: 错轨导入对称拒绝**
    - **Validates: Requirements 12.10, 12.11**

  - [x]* 7.10 编写属性测试：Property 43 Research Pack parse-print-parse 往返
    - 验证 schema/identity/dataset/cluster/version/visibility/anchor/claim/unknown/review 保持。
    - 验证：`python -m pytest tests/property/test_research_governance_properties.py -k property_43 -q`
    - **Property 43: Research Pack parse-print-parse 往返**
    - **Validates: Requirements 14.1, 14.3, 14.4**

  - [x]* 7.11 编写属性测试：Property 44 Research run 比较只允许兼容身份
    - 逐字段改变 dataset/cluster/pack/rubric identity，验证 compatibility error。
    - 验证：`python -m pytest tests/property/test_research_governance_properties.py -k property_44 -q`
    - **Property 44: Research run 比较只允许兼容身份**
    - **Validates: Requirements 14.8**

- [ ] 8. Phase C/E — Evaluation Provenance 与不可变报告
  - [x] 8.1 实现 provenance store 与 evaluation task 原子接受
    - 新增 `core/store/evaluation_provenance_store.py`，迁移 task/report schema；评分前持久化完整 immutable provenance，完成后 report/provenance/result digest 不可更新。
    - 验收：一个 operation 恰一个 task/report/provenance；重试回放既有 identity。
    - 验证：`python -m pytest tests/test_eval_attribution.py tests/integration/test_evaluation_provenance.py -q`
    - _Requirements: 15.2–15.5, 15.10_

  - [x] 8.2 从已提交会话构建评测输入并移除 session_predictions
    - 新增 `api/services/evaluation_input.py`，只从 latest committed ordered dialog 构造 digest；legacy 文件接口只用 runtime data root 下 task-scoped 临时文件并清理。
    - 验收：产品代码不读写/创建 `data/session_predictions/`，缺输入 422 且 report count 不变。
    - 验证：`python -m pytest tests/integration/test_evaluation_provenance.py -k 'input or session_predictions or missing' -q`
    - _Requirements: 15.1, 15.6, 15.9_

  - [x] 8.3 接通 API/BFF/UI 报告来源与降级标记
    - 返回 report、metric、provenance、Correlation_Context；civil LexEval/J1/CADD 与 research rubric 分 namespace；degraded input 标 affected metrics。
    - 验收：UI 从 initiating session/input 链到唯一 report，restart 后仍可检索。
    - 验证：`python -m pytest tests/integration/test_evaluation_provenance.py -q && npm run test:release -- --run app/evaluation app/api/evaluate`
    - _Requirements: 3.10, 6.3, 15.3–15.8_

  - [x]* 8.4 编写 provenance-before-score、不可变、重试和无 session_predictions 测试
    - 验证 digest 重算、字段完整、缺输入状态不变、降级 metrics、namespace、report count 和源码路径扫描。
    - 验证：`python -m pytest tests/test_eval_attribution.py tests/integration/test_evaluation_provenance.py -q`
    - _Requirements: 15.11, 18.5, 18.11_

  - [x]* 8.5 编写属性测试：Property 11 Evaluation Report 唯一归属
    - 验证完成 evaluation 恰一 report、initiating identity 和 provenance。
    - 验证：`python -m pytest tests/property/test_evaluation_provenance_properties.py -k property_11 -q`
    - **Property 11: Evaluation Report 唯一归属**
    - **Validates: Requirements 3.10, 15.4**

  - [x]* 8.6 编写属性测试：Property 22 Degraded 状态全链传播
    - 验证 response、persisted result、provenance 及 affected metrics。
    - 验证：`python -m pytest tests/property/test_evaluation_provenance_properties.py -k property_22 -q`
    - **Property 22: Degraded 状态全链传播**
    - **Validates: Requirements 6.3, 15.7**

  - [x]* 8.7 编写属性测试：Property 45 Evaluation 输入只来自最新已提交有序对话
    - 生成 committed/uncommitted turn，验证排序、筛选和稳定 digest。
    - 验证：`python -m pytest tests/property/test_evaluation_provenance_properties.py -k property_45 -q`
    - **Property 45: Evaluation 输入只来自最新已提交有序对话**
    - **Validates: Requirements 15.1**

  - [x]* 8.8 编写属性测试：Property 46 Evaluation provenance 完整且报告一对一不可变
    - 验证 provenance 先于结果、字段完整、unique association 和 immutable report。
    - 验证：`python -m pytest tests/property/test_evaluation_provenance_properties.py -k property_46 -q`
    - **Property 46: Evaluation provenance 完整且报告一对一不可变**
    - **Validates: Requirements 15.2, 15.3, 15.4**

  - [x]* 8.9 编写属性测试：Property 47 缺失评测输入不创建报告
    - 生成缺字段组合，验证 422、field errors 和 report count。
    - 验证：`python -m pytest tests/property/test_evaluation_provenance_properties.py -k property_47 -q`
    - **Property 47: 缺失评测输入不创建报告**
    - **Validates: Requirements 15.6**

- [ ] 9. Phase F — Liveness、Readiness、日志、指标与告警
  - [x] 9.1 拆分 liveness 与 component readiness
    - 新增 `/health/live`、`/health/ready`；live 不访问外部 LLM/SQLite 业务记录/law retrieval，ready 分别探测 configuration/stores/law/runtime，旧 `/health` 仅兼容摘要。
    - 验收：任一 required component 失败返回 503 和稳定 reason；无路径、文件名、Secret、stack。
    - 验证：`python -m pytest tests/integration/test_health_observability.py -k 'live or ready' -q`
    - _Requirements: 16.1–16.3_

  - [x] 9.2 实现 completion log 与固定指标 catalog
    - 新增 `api/observability/*`：每请求恰一 JSON completion log，按可用性投影 correlation；实现 request/error/latency/active SSE/LLM/degraded/persistence/duplicate terminal/CI call 指标。
    - 验收：低基数 label，不以 Request/Session 作 label；SSE gauge 1s 内更新；默认日志禁 raw content。
    - 验证：`python -m pytest tests/integration/test_health_observability.py -k 'log or metric or sse' -q`
    - _Requirements: 16.4–16.8_

  - [x] 9.3 实现可测试告警状态机与 monitoring 配置
    - 在 `monitoring/` 定义 5m error rate、2m readiness、60s evaluation 与 recovery window；记录触发/恢复时间和 operator link。
    - 验收：请求数不足不 firing；阈值持续满足才 firing；清除完整窗口才 resolved。
    - 验证：`python -m pytest monitoring/tests -q`
    - _Requirements: 16.9–16.12_

  - [x]* 9.4 编写健康隔离、日志红线、指标转换和告警恢复测试
    - 覆盖依赖隔离、每组件故障、一请求一日志、forbidden scan、gauge/metric/alert transitions。
    - 验证：`python -m pytest tests/integration/test_health_observability.py monitoring/tests -q`
    - _Requirements: 16.13, 18.6_

  - [x]* 9.5 编写属性测试：Property 48 Readiness 失败集合准确
    - 生成 component 状态组合，验证 status 和 failed/reason 集合。
    - 验证：`python -m pytest tests/property/test_observability_properties.py -k property_48 -q`
    - **Property 48: Readiness 失败集合准确**
    - **Validates: Requirements 16.3**

  - [x]* 9.6 编写属性测试：Property 49 日志关联字段按可用性投影
    - 生成 RequestContext 可选字段，验证必填和可用 identity 投影。
    - 验证：`python -m pytest tests/property/test_observability_properties.py -k property_49 -q`
    - **Property 49: 日志关联字段按可用性投影**
    - **Validates: Requirements 16.4, 16.5**

  - [x]* 9.7 编写属性测试：Property 50 告警状态机符合窗口规则
    - 生成 request/error/readiness 时间序列，验证 firing/resolved/recovered_at。
    - 验证：`python -m pytest tests/property/test_observability_properties.py -k property_50 -q`
    - **Property 50: 告警状态机符合窗口规则**
    - **Validates: Requirements 16.9, 16.10, 16.11**

  - [x]* 9.8 编写属性测试：Property 51 Metric catalog 完整
    - 生成 metric declarations，验证 manifest 所需全部 catalog 字段。
    - 验证：`python -m pytest tests/property/test_observability_properties.py -k property_51 -q`
    - **Property 51: Metric catalog 完整**
    - **Validates: Requirements 16.12**

- [ ] 10. Phase A/F — Release Manifest、Evidence、Gap 与 Gate
  - [x] 10.1 实现 canonical manifest、evidence 与 gap 模型
    - 新增 `core/release/*`，实现 Version/Commit 绑定、环境/命令/时间/exit/sample/digest/correlation evidence、one-of gap classification 和 inventory disclosure。
    - 验收：runtime data/evidence root 在源码外；内容/数据缺口不增加 blocker count；open engineering blocker 可识别。
    - 验证：`python -m pytest tests/release/test_manifest_inventory.py tests/integration/test_release_evidence.py -q`
    - _Requirements: 1.6–1.10, 18.14, 20.1–20.8, 20.13_

  - [x] 10.2 实现 deterministic gate 与 append-only decision chain
    - 实现 mandatory evidence 校验、go/no-go 唯一决策、failed criteria closure action 和 previous digest hash chain；任何 failed/timeout/样本不足/关联缺失/commit mismatch fail-closed。
    - 验收：open blocker、关键 drill/test/build 失败均 no-go；历史修改/删除/重排可检测。
    - 验证：`python -m pytest tests/release/test_gate_three_runs.py tests/integration/test_release_evidence.py -q`
    - _Requirements: 18.12, 18.13, 20.2–20.12_

  - [x] 10.3 实现 scope、source-control 与敏感产物扫描
    - 扫描 inspected/excluded paths、tracked `.env`、`*.sqlite3`、`data/session_predictions/`、空法律材料目录和 evidence/source 混放；仅报告观庭视觉为 excluded。
    - 验收：扫描不读取/上传 Secret，不删除用户数据；任何违规产生 blocker evidence。
    - 验证：`python scripts/release_gate.py scan-source --root .`
    - _Requirements: 1.1–1.4, 1.10, 12.12, 15.9, 20.6, 20.7_

  - [x]* 10.4 编写 manifest/inventory/evidence/gate/decision 集成测试
    - 覆盖 route/status diff、版本 mismatch、gap 分类、digest/commit/stale evidence、go/no-go、decision chain 和 disclosure 独立性。
    - 验证：`python -m pytest tests/release tests/integration/test_release_evidence.py -q`
    - _Requirements: 2.10, 18.12–18.14, 20.1–20.13_

  - [x]* 10.5 编写属性测试：Property 2 Gap 恰有一个主分类且按分类影响 gate
    - 生成 gap 集合，验证 one-of、blocker no-go 和 disclosure 计数。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_2 -q`
    - **Property 2: Gap 恰有一个主分类且按分类影响 gate**
    - **Validates: Requirements 1.6, 1.8, 1.9, 20.2**

  - [x]* 10.6 编写属性测试：Property 54 三连跑不允许失败或间歇通过
    - 生成同 Commit 三轮 check 矩阵，验证仅全绿通过。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_54 -q`
    - **Property 54: 三连跑不允许失败或间歇通过**
    - **Validates: Requirements 18.12**

  - [x]* 10.7 编写属性测试：Property 55 Required check 与 evidence fail-closed
    - 生成失败、超时、样本/关联/记录/digest/commit 异常组合，验证 no-go。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_55 -q`
    - **Property 55: Required check 与 evidence fail-closed**
    - **Validates: Requirements 18.13, 18.14, 20.1, 20.3, 20.8, 20.9**

  - [x]* 10.8 编写属性测试：Property 57 Gate 决策确定且唯一
    - 验证完整输入只生成一个字段完整 go 或覆盖失败集合的 no-go。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_57 -q`
    - **Property 57: Gate 决策确定且唯一**
    - **Validates: Requirements 20.4, 20.10, 20.11**

  - [x]* 10.9 编写属性测试：Property 58 决策日志可检测篡改
    - 生成 decision chain 并变更/删除/重排历史，验证失败。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_58 -q`
    - **Property 58: 决策日志可检测篡改**
    - **Validates: Requirements 20.12**

  - [x]* 10.10 编写属性测试：Property 59 发布披露与 blocker 状态独立
    - 改变 inventory disclosure，验证 blocker count 不随之变化。
    - 验证：`python -m pytest tests/property/test_release_gate_properties.py -k property_59 -q`
    - **Property 59: 发布披露与 blocker 状态独立**
    - **Validates: Requirements 20.13**

- [ ] 11. Phase F — 非观庭 Web 主旅程与自动浏览器验证
  - [x] 11.1 统一非观庭页面状态、错误、身份与实验标签
    - 更新 conversation/full-simulation/mediation/research/evaluation/system 页面：Operation/Request/Session/Task/med/report identity、PublicError、输入恢复、retry、empty/degraded/terminal 状态。
    - 从 route catalog 渲染实验标签；所有外部/生成文本用 React text rendering，不用 `dangerouslySetInnerHTML`。
    - 验收：每个主旅程成功/失败都有明确可恢复结果，研究空态不改 civil state。
    - 验证：`npm run test:release -- --run app lib`
    - _Requirements: 2.3, 3.1–3.12, 6.5, 8.8_

  - [x] 11.2 建立 Playwright 一次性 E2E harness 与故障注入夹具
    - 配置隔离 runtime data root、provider/backend stubs、可编排 backend restart、trace/evidence 输出；不依赖手工启动或 watch server。
    - 验收：测试可在单命令内启动/停止受管进程并清理，观庭视觉和 screenshot comparison 不进入 suite。
    - 验证：`npm run test:e2e -- --list`
    - _Requirements: 3.13, 18.5_

  - [ ]* 11.3 编写非观庭成功/失败 E2E traces
    - 覆盖 config、conversation create/stream/resume、FullCase terminal、mediation identity、evaluation report、research empty/formal=0、liveness/readiness；每类一成功一注入失败。
    - 验证：`npm run test:e2e`
    - _Requirements: 3.1–3.13, 18.5_

  - [ ]* 11.4 仅编写旧 `/court3d` 三路由重定向契约测试
    - 验证 `/court3d`、`/[sessionId]`、`/replay` 的 status、target 和必要参数；不打开、截图或评价 `/hearing-3d` 视觉。
    - 验证：`npm run test:e2e -- e2e/legacy-court3d-redirect.spec.ts`
    - _Requirements: 1.2–1.4, 18.3, 18.4_

  - [x]* 11.5 编写属性测试：Property 10 调解身份与会话身份隔离
    - 生成现存 Session ID 集合，验证 `med_*` 唯一且不替换 links。
    - 验证：`python -m pytest tests/property/test_identity_properties.py -k property_10 -q`
    - **Property 10: 调解身份与会话身份隔离**
    - **Validates: Requirements 3.9**

- [ ] 12. Phase F — 性能统计、容量拒绝与资源释放
  - [x] 12.1 实现性能样本、环境身份与 nearest-rank 统计
    - 新增 `core/release/statistics.py` 和 sample schema；使用单调时钟，记录 raw/excluded/p50/p95/max/error、provider/local duration、环境与参数 digest。
    - 验收：环境或样本不足只能 invalid；baseline identity 严格比较。
    - 验证：`python -m pytest tests/test_release_statistics.py -q`
    - _Requirements: 17.1, 17.4, 17.7, 17.10, 17.11_

  - [x] 12.2 实现 release benchmark runner 并扩展 hearing/plead 基准
    - 新增 `scripts/benchmark_release.py`，复用 `bench_hearing.py`/`bench_plead.py`；支持 non-LLM 10 clients/5m/>=300、runtime 各>=30、批准 baseline 与 evidence 输出。
    - 验收：脚本是有限时长非 watch 命令，外部 LLM latency 分离，失败/排除有 reason。
    - 验证：`python scripts/benchmark_release.py --help && python -m pytest tests/integration/test_benchmark_runner.py -q`
    - _Requirements: 17.2, 17.5–17.7_

  - [ ] 12.3 实现 Web cold-navigation 性能自动采样
    - 在 Playwright performance project 中对每个非观庭 entry page 采 30 次，固定网络 profile，定位 primary action readiness 并输出 evidence。
    - 验收：不足 30 或 profile mismatch 为 invalid；不采 `/hearing-3d` 视觉。
    - 验证：`npm run test:e2e -- --project=performance`
    - _Requirements: 17.3, 17.10_

  - [x] 12.4 实现高成本操作容量 semaphore 与 FullCase 资源释放
    - 饱和前置返回 429 `capacity_exceeded` + 正整数 Retry-After；FullCase terminal 后 10s 内清 queue/worker/runtime reference。
    - 验收：拒绝前无 LLM/持久化；completed/failed/cancelled 都释放。
    - 验证：`python -m pytest tests/integration/test_capacity_and_release.py -q`
    - _Requirements: 17.8, 17.9_

  - [x]* 12.5 编写属性测试：Property 52 nearest-rank p95 正确
    - 生成非空有限 duration 列表与排列，验证 `ceil(.95*n)-1`。
    - 验证：`python -m pytest tests/property/test_release_statistics_properties.py -k property_52 -q`
    - **Property 52: nearest-rank p95 正确**
    - **Validates: Requirements 17.4**

  - [x]* 12.6 编写属性测试：Property 53 性能证据有效性 fail-closed
    - 生成样本数、环境、字段和 provider/local latency 组合，验证 pass/invalid。
    - 验证：`python -m pytest tests/property/test_release_statistics_properties.py -k property_53 -q`
    - **Property 53: 性能证据有效性 fail-closed**
    - **Validates: Requirements 17.1, 17.7, 17.10, 17.11**

- [ ] 13. Phase F/G — 可执行部署资产、安装/部署文档与恢复回滚
  - [x] 13.1 实现机器可校验的部署模板和文档命令 catalog
    - 新增非 root service/proxy/env 模板与 `deploy/commands.yaml`，实现 renderer/checker 更新 `docs/INSTALL.md`、`docs/DEPLOY.md`；每条命令含 cwd、前置条件、参数、预期退出码/结果。
    - 文档明确唯一 cwd、双进程、offline 路径、TLS/proxy/token、权限、startup/shutdown、health/metrics、数据现状与限制。
    - 验收：安装只用锁文件；不得示例 root/nohup/unlocked install；不含真实 Secret/绝对本机路径。
    - 验证：`python scripts/validate_deployment_docs.py --check`
    - _Requirements: 19.1–19.11_

  - [x] 13.2 实现自动备份、恢复、升级与回滚演练脚本
    - 新增有限执行的 `scripts/release_rehearsal.py` 子命令，使用 clean data root、immutable artifact、受管进程和 readiness 轮询；记录身份、权限、transcript、duration、fingerprints。
    - 验收：恢复/回滚 <=4h 门槛可判定，失败不切换生产 root，RPO age <=24h 可证明。
    - 验证：`python scripts/release_rehearsal.py --help && python -m pytest tests/integration/test_release_rehearsal.py -q`
    - _Requirements: 11.9–11.12, 19.5–19.13, 20.4_

  - [x]* 13.3 编写 clean install、非 root 权限、smoke、backup/restore/rollback 自动验证
    - 使用临时/容器化 Release_Test_Environment，不手工运行长驻 server；验证所有 Documented_Command 的 exit/result 和未声明依赖。
    - 验证：`python -m pytest tests/integration/test_release_rehearsal.py -q`
    - _Requirements: 19.11–19.13, 20.4, 20.9_

  - [x]* 13.4 编写属性测试：Property 56 部署文档主题完整
    - 生成 journey/operations topic 集合，验证每项至少一个字段完整的 Documented_Command。
    - 验证：`python -m pytest tests/property/test_deployment_catalog_properties.py -k property_56 -q`
    - **Property 56: 部署文档主题完整**
    - **Validates: Requirements 19.7, 19.8**

- [ ] 14. Phase G — 自动质量门禁与候选发布演练
  - [x] 14.1 实现 release gate CLI 与分阶段有限命令
    - 完成 `scripts/release_gate.py` 的 scan、test、build、contract、security、recovery、e2e、performance、deploy、verify 子命令；每项写 content-addressed evidence。
    - 验收：命令固定 cwd/环境/Version/Commit；任一步失败/timeout/样本或关联缺失立即 no-go，不启动 watch。
    - 验证：`python scripts/release_gate.py --help && python -m pytest tests/release -q`
    - _Requirements: 18.1–18.14, 20.1–20.9_

  - [x] 14.2 实现同 Commit 三连跑和测试范围过滤
    - 让 critical non-LLM checks 同 Commit 连续三次；release Vitest 排除 `components/hearing-3d` 视觉测试但保留独立 `test:3d`，重定向合同仍必跑。
    - 验收：任一 intermittent/fail 阻断；三轮 evidence 可关联且 digest 不覆盖。
    - 验证：`python scripts/release_gate.py test --critical-runs 3 --dry-run`
    - _Requirements: 18.1–18.4, 18.12_

  - [x] 14.3 生成候选 manifest/evidence 并执行自动发布演练
    - 对指定 `1.0.0` + full Commit ID 执行 source scan、full pytest、typecheck、build、contract、安全、并发、重启、boundary、E2E、performance、backup/restore、rollback；生成 manifest 和 append-only decision。
    - 验收：当前缺法律内容只披露不伪造；任何 mandatory failure 只能产出 no-go；evidence 在源码外。
    - 验证：`python scripts/release_gate.py verify --version 1.0.0 --commit HEAD`
    - _Requirements: 18.1–18.14, 20.1–20.13_

  - [x]* 14.4 编写 release CLI 端到端自测
    - 用小型受管夹具验证命令顺序、失败短路、evidence digest、commit binding、GO/NO-GO 和恢复/回滚要求，不依赖真实外部 LLM。
    - 验证：`python -m pytest tests/release tests/integration/test_release_rehearsal.py -q`
    - _Requirements: 18.13, 18.14, 20.3, 20.4, 20.8–20.12_

- [ ] 15. Final checkpoint — Ensure all tests pass, ask the user if questions arise.
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional during incremental implementation and can be skipped for a faster engineering iteration；但候选版本要取得 GO，Requirements 18/20 指定的 mandatory tests/evidence 仍必须全部执行并通过。
- 每个 property task 对应设计中的一个且仅一个 Correctness Property；Hypothesis/fast-check 均应至少运行 100 examples/runs，并把失败 seed/counterexample 写入 evidence。
- 新依赖的**具体版本不在本计划中臆测**。Task 1.1 必须先以现有 Python/Node/Next/Vitest 锁文件核验兼容性，再提交精确版本和更新后的 lock。
- 所有产品代码、测试、脚本、部署模板和运行文档改动限定在 `mock_court_system/`；本 spec 的 requirements/design/config 保持不变。
- `/hearing-3d`、`components/hearing-3d` 的视觉、模型、HUD、动画和体验不参与实现或 gate；仅验证旧 `/court3d` 重定向合同。`lib/court3d/parseSse.ts` 只作为共享协议管子演进。
- 两个 SAMPLE 永远是 Technical_Fixture；15 份标注仍未独立复核；案例 25 仍待确认；formal pack 在满足完整复核条件前为 0。不得补造 unknown、引用或正式状态。
- 不创建空选案/原文/规则卡目录，不跟踪 `.env`、`*.sqlite3`、`data/session_predictions/`；测试和 evidence 使用源码树外的临时/runtime root。
- 依赖图按文件冲突与迁移依赖分波次；同一 wave 内任务可并行，后一 wave 必须等待所有前序 wave 完成。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1", "6.1", "7.1", "8.1", "9.1", "10.1", "12.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2", "6.2", "7.2", "8.2", "9.2", "10.2", "12.2"] },
    { "id": 3, "tasks": ["2.3", "3.3", "4.3", "5.1", "6.3", "7.3", "9.3", "10.3", "11.1", "12.3", "13.1"] },
    { "id": 4, "tasks": ["3.4", "4.4", "5.2", "7.4", "12.4", "13.2", "14.1"] },
    { "id": 5, "tasks": ["5.3", "5.4", "5.5", "6.4", "8.3", "8.4", "9.4", "10.4", "11.2", "13.3"] },
    { "id": 6, "tasks": ["2.4", "2.5", "3.5", "4.5", "5.6", "7.5", "11.3", "11.4"] },
    { "id": 7, "tasks": ["1.4", "2.6", "3.6", "4.6", "5.7", "7.6", "8.5", "9.5", "12.5"] },
    { "id": 8, "tasks": ["2.7", "3.7", "4.7", "5.8", "7.7", "8.6", "9.6", "10.5", "11.5", "12.6"] },
    { "id": 9, "tasks": ["1.5", "2.8", "3.8", "4.8", "5.9", "6.5", "7.8", "8.7", "9.7"] },
    { "id": 10, "tasks": ["1.6", "3.9", "4.9", "5.10", "6.6", "7.9", "8.8", "9.8"] },
    { "id": 11, "tasks": ["1.7", "3.10", "4.10", "5.11", "7.10", "8.9", "13.4"] },
    { "id": 12, "tasks": ["2.9", "3.11", "4.11", "5.12", "7.11"] },
    { "id": 13, "tasks": ["4.12", "5.13", "10.6"] },
    { "id": 14, "tasks": ["4.13", "5.14", "10.7"] },
    { "id": 15, "tasks": ["5.15", "10.8"] },
    { "id": 16, "tasks": ["5.16", "10.9"] },
    { "id": 17, "tasks": ["10.10"] },
    { "id": 18, "tasks": ["14.2"] },
    { "id": 19, "tasks": ["14.3"] },
    { "id": 20, "tasks": ["14.4"] }
  ]
}
```

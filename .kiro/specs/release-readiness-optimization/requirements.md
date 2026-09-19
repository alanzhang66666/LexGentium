# Requirements Document

## Introduction

本规格定义 LexGentium 1.0 在观庭展示范围之外达到发布就绪所需的可验证要求与发布门禁。`mock_court_system/` 是唯一运行入口，`mock_court_system/docs/SYSTEM_STATUS.md` 是现役能力、数据数量和已知限制的权威来源。候选版本固定为 `1.0.0`，Web 主路径保持 Next.js BFF → FastAPI → CD、DD、CI、Sim 智能体；CI 听证使用 `HearingRuntime`，CD/DD 书状使用 `PleadRuntime`。

本轮只验证非观庭产品能力。`/hearing-3d`、旧 `/court3d` 对应的场景、模型、HUD、动画、观演体验以及 `components/hearing-3d` 的视觉质量均排除在实现和发布验收之外；旧 `/court3d` 只验证重定向到 `/hearing-3d`。本轮不得通过扩展民事引擎替代法律内容建设，也不得修改正式研究内容数量的事实。

发布基线包含以下不可变事实：正式研究包数量为 0；`enf-cn-notice-001` 与 `cisg-art79-sample-001` 是技术夹具；15 份已填标注均未完成独立复核；案例 25 是待确认的 AI 辅助初标；`dataset_1000` 与 CISG/《纽约公约》研究数据分轨；未知事实保持 `unknown`；材料不足以 `admit_insufficient` 停止；纽约公约执行研究仅计原告和被告发言 12 次，CISG 第 79 条研究仅计原告和被告发言 10 次，到上限不得再调用 CI LLM；书记员、抽取和评分默认使用 512 个快速 Token；判决在强模型配置上限内不做应用层额外截短；全案自动 CI 最多 30 步；`.env`、`*.sqlite3` 与 `data/session_predictions/` 不得进入发布源代码控制。

每项 Release_Gate 结果必须绑定候选版本和提交身份。时间阈值使用单调时钟测量；数量阈值使用可审计计数器测量；状态不变性使用操作前后持久化状态指纹验证；成功、失败、降级、取消和去重结果均必须产生可关联的 Release_Evidence。

## Glossary

- **Release_Readiness_Program**：本规格定义的审计、增强、验证和发布决策工作。
- **LexGentium_System**：从 `mock_court_system/` 启动的 LexGentium 1.0 Web 系统。
- **Authoritative_Status**：`mock_court_system/docs/SYSTEM_STATUS.md` 对现役能力、数量和限制的权威陈述。
- **Web_Workbench**：除 Observation_Presentation 外的 Next.js 用户界面。
- **Backend_API**：由 `api_server.py` 装配的 FastAPI 服务。
- **BFF**：浏览器与 Backend_API 之间的 Next.js `/api/*` 服务端代理层。
- **Stable_Route**：Release_Manifest 中列为稳定且纳入兼容性承诺的 Web 或 API 路由。
- **Experimental_Route**：Release_Manifest 中明确标记为实验且不纳入稳定兼容性承诺的 Web 或 API 路由。
- **Protected_Route**：Production_Profile 下需要有效 API_Token 的 Backend_API 路由。
- **Non_Observation_Main_Journey**：不经过 Observation_Presentation 的配置、开庭、书状、全案、调解、研究、评测和系统诊断用户旅程。
- **Observation_Presentation**：`/hearing-3d`、旧 `/court3d` 重定向及对应场景、模型、HUD、动画、观演体验和 `components/hearing-3d` 视觉质量。
- **LLM_Agent_Layer**：CD、DD、CI 和 Sim 智能体及智能体使用的 LLM 调用能力。
- **CI_LLM_Call**：由 CI 智能体发起的一次 LLM 请求。
- **Hearing_Runtime**：CI 听证主路径使用的有状态运行时。
- **Plead_Runtime**：CD 和 DD 书状主路径使用的有状态运行时。
- **Full_Case_Run**：由全案编排创建并以 Task_ID 标识的自动执行过程。
- **Session_ID**：唯一标识一场持久化会话的不可变标识符。
- **Task_ID**：唯一标识一个后台任务的不可变标识符。
- **Operation_ID**：由客户端或系统分配、用于幂等和去重的一次逻辑操作标识符。
- **Request_ID**：唯一标识一次 HTTP 请求并用于关联响应、日志和指标的标识符。
- **Correlation_Context**：由 Request_ID、Session_ID、Task_ID、Operation_ID、`game_id`、`report_id` 或 `run_id` 中适用字段组成的关联信息。
- **State_Fingerprint**：对规范化持久化状态计算的稳定摘要，用于比较操作前后状态是否相同。
- **SSE**：服务器通过文本事件流传输开始、增量、完成、取消或错误事件的协议。
- **SSE_Event_Codec**：生成和解析 LexGentium SSE 事件的协议组件。
- **Terminal_Event**：一次 SSE 操作的 `complete`、`error` 或 `cancelled` 终止事件。
- **Degraded_Mode**：外部 LLM 或可选依赖不可用时，系统明确标记受限结果并保持可恢复操作的状态。
- **Civil_Dataset**：`data/dataset_1000/` 下服务于民事评测与案例选择的数据轨。
- **Research_Subsystem**：处理 CISG 与《纽约公约》执行研究包、研究运行、主张链和研究量表的数据轨。
- **Research_Pack**：遵循研究包结构并供 Research_Subsystem 读取的版本化材料集合。
- **Formal_Research_Pack**：带有完整独立复核身份、时间、版本和结论的 Research_Pack。
- **Technical_Fixture**：仅用于开发、演示或自动测试且不构成正式法律研究内容的 SAMPLE 数据。
- **Unverified_Legal_Material**：尚未完成独立复核的原文、标注或 AI 辅助初标材料。
- **Research_Pack_Codec**：按照声明的研究包模式版本解析和验证 Research_Pack 的组件。
- **Research_Pack_Pretty_Printer**：把结构化 Research_Pack 输出为稳定、可再次解析格式的组件。
- **Conversation_Archive_Codec**：导入和导出会话归档的组件。
- **Conversation_Archive_Pretty_Printer**：把结构化会话归档输出为稳定、可再次解析格式的组件。
- **Unknown_Fact**：输入材料未提供且无法从获准材料确定、状态值为 `unknown` 的事实。
- **Insufficient_Material_Decision**：值为 `admit_insufficient`、表示材料不足并停止继续补造论证的决定。
- **Engineering_Release_Blocker**：妨碍系统安全、正确、可恢复或可运维发布的工程缺陷。
- **Legal_Content_Gap**：因正式法律材料缺少或复核未完成而形成的内容缺口。
- **Data_Capability_Limitation**：数据数量、完整性或用途边界导致且需要披露的能力限制。
- **Accepted_Risk**：经责任人和批准人记录接受、但不属于 Engineering_Release_Blocker 的残余风险。
- **Release_Gate**：决定 Candidate_Release 能否发布的自动检查、人工审查和证据要求集合。
- **Release_Evidence**：绑定 Version_ID 与 Commit_ID 的测试、扫描、性能、恢复、回滚及审批记录。
- **Version_ID**：候选版本的语义化版本标识，本规格固定为 `1.0.0`。
- **Commit_ID**：生成 Candidate_Release 的完整源代码提交哈希。
- **Production_Profile**：用于正式部署并启用生产安全约束的运行配置。
- **Secret**：LLM 密钥、API_Token、远程服务凭据及其他认证材料。
- **Secret_Mask**：API 返回 Secret 时使用的固定字符串 `********`，与 Secret 长度和内容无关。
- **API_Token**：BFF 访问 Protected_Route 时从服务器端配置取得的认证令牌。
- **Public_Error_Detail**：不包含 Secret、堆栈、绝对路径、原始提示词或内部实现名称，并包含稳定错误代码、可操作描述和 Request_ID 的错误对象。
- **Liveness_Check**：只确认 Backend_API 进程能够接收并响应请求的检查。
- **Readiness_Check**：确认 Stable_Route 所需配置、存储、法律检索和运行时组件可用的检查。
- **Operational_Metric**：使用固定名称、类型、单位和标签集合记录的运行指标。
- **Monitoring_Configuration**：定义 Operational_Metric 采集、聚合窗口、告警阈值和处理链接的配置。
- **Approved_Baseline**：记录硬件、软件、模型、数据夹具、网络和测试参数并经批准的性能参考结果。
- **Performance_Sample**：一次带有开始时间、结束时间、结果、关联身份和环境身份的性能观测。
- **Release_Test_Environment**：记录 CPU、内存、操作系统、Python、Node.js、依赖锁文件、网络配置和外部服务替身的可重复测试环境。
- **Release_Manifest**：记录 Version_ID、Commit_ID、构建产物、路由、配置概要、数据状态、已知限制和 Release_Evidence 链接的发布清单。
- **Candidate_Release**：等待 Release_Gate 审批的特定 Version_ID 与 Commit_ID 组合。
- **Evaluation_Report**：一次评测生成并以 `report_id` 标识的不可变结果。
- **Evaluation_Provenance**：评测输入摘要、会话身份、预测身份、评测器版本、量表版本、配置身份、模型身份、时间和降级状态的记录。
- **Release_Documentation**：面向版本使用者的发布说明集合。
- **Installation_Documentation**：说明依赖安装和本地启动的安装文档。
- **Deployment_Documentation**：说明生产启动、安全、运维和恢复的部署文档。
- **Documented_Command**：在 Installation_Documentation 或 Deployment_Documentation 中给出工作目录、前置条件、参数和预期退出码的可执行命令。
- **Recovery_Point_Objective**：生产持久化数据允许丢失的最大时间窗口，本规格为 24 小时。
- **Recovery_Time_Objective**：从恢复开始到 Stable_Route 恢复就绪的最大时间，本规格为 4 小时。

## Requirements

### Requirement 1: 范围与发布分类

**User Story:** As a 发布负责人, I want 明确可执行范围和缺口分类, so that 工程验收不会混入观庭视觉或未完成的法律内容生产。

#### Acceptance Criteria

1. THE Release_Readiness_Program SHALL limit product-code inspection, modification, build, test, packaging, and deployment evidence to `mock_court_system/`.
2. THE Release_Readiness_Program SHALL classify Observation_Presentation as outside this feature's implementation scope and Release_Gate acceptance scope.
3. THE Release_Gate SHALL exclude `components/hearing-3d` visual quality, scene fidelity, model quality, HUD appearance, animation quality, and viewing experience from pass-or-fail calculations.
4. WHEN `/court3d` or a nested legacy `/court3d` route is requested, THE Release_Gate SHALL verify only the redirect target, redirect status, and preserved route parameters required to reach `/hearing-3d`.
5. THE Release_Readiness_Program SHALL use Authoritative_Status as the sole current-status source when repository documents disagree about implemented capability or data quantity.
6. WHEN a release gap is recorded, THE Release_Readiness_Program SHALL assign exactly one primary classification from Engineering_Release_Blocker, Legal_Content_Gap, Data_Capability_Limitation, Accepted_Risk, or out-of-scope.
7. WHEN a release gap is recorded, THE Release_Readiness_Program SHALL record gap identity, classification, observable trigger, expected result, actual result, owner, status, and evidence link.
8. IF an Engineering_Release_Blocker has status other than closed, THEN THE Release_Gate SHALL produce a no-go result.
9. WHEN a Legal_Content_Gap or Data_Capability_Limitation remains open, THE Release_Manifest SHALL disclose the item without changing the Engineering_Release_Blocker count.
10. THE Release_Evidence SHALL contain a scope report listing every inspected product path and every excluded Observation_Presentation path.

### Requirement 2: 发布能力清单与产品声明

**User Story:** As a 产品负责人, I want 发布声明与可验证能力一致, so that 用户能够区分稳定功能、实验功能、技术夹具和数据限制。

#### Acceptance Criteria

1. THE Release_Manifest SHALL enumerate each Stable_Route by method, path, authentication requirement, response mode, and owning journey.
2. THE Release_Manifest SHALL enumerate each Experimental_Route in a section separate from Stable_Route entries.
3. WHEN an Experimental_Route is presented in Web_Workbench, THE Web_Workbench SHALL display an `实验功能` label before the first user action that invokes the route.
4. THE Web_Workbench SHALL describe `/login` and `/register` as LLM configuration access without describing either route as user-account authentication.
5. THE LexGentium_System SHALL report Version_ID `1.0.0` identically in package metadata, user-facing version text, health metadata, and Release_Manifest.
6. WHEN Civil_Dataset lacks any train, validation, or test JSONL split, THE Web_Workbench SHALL name each missing split at the civil case-selection point.
7. WHEN Formal_Research_Pack count is queried, THE Research_Subsystem SHALL return `0` until at least one pack satisfies every formal-review field requirement.
8. WHEN research pack inventory is displayed, THE Web_Workbench SHALL label both SAMPLE records as Technical_Fixture and exclude both SAMPLE records from the formal count.
9. WHEN legal material inventory is displayed, THE Web_Workbench SHALL report 15 annotations as lacking independent review and case 25 as pending confirmation.
10. THE Release_Evidence SHALL contain an automated comparison showing zero mismatches among route inventory, version surfaces, formal-pack count, fixture labels, and Authoritative_Status.

### Requirement 3: 非观庭前端主流程

**User Story:** As a 平台用户, I want 非观庭工作台的核心操作具有明确成功和失败结果, so that 用户能够恢复、重试并定位每次操作。

#### Acceptance Criteria

1. WHEN a user submits schema-valid LLM configuration on `/register`, THE Web_Workbench SHALL display success, the configuration identity, and Secret_Mask without displaying the submitted Secret.
2. IF LLM configuration submission fails before persistence, THEN THE Web_Workbench SHALL display Public_Error_Detail and preserve the submitted non-secret fields for retry.
3. WHEN a user tests stored LLM configuration on `/login`, THE Web_Workbench SHALL display exactly one of connected, degraded, or failed with the associated Request_ID.
4. WHEN a user starts a valid conversation on `/conversation`, THE LexGentium_System SHALL create exactly one Session_ID for the Operation_ID and navigate to `/conversation/{Session_ID}`.
5. WHEN a user reopens a persisted Session_ID after a Backend_API restart, THE Web_Workbench SHALL restore the latest committed stage, ordered dialog, links, reasoning metadata, and available actions.
6. WHEN a user submits one session message, THE Web_Workbench SHALL associate all SSE events and the final utterance with the same Session_ID, Operation_ID, and Request_ID.
7. WHEN a session message completes, THE Web_Workbench SHALL display each delta in sequence-number order and persist exactly one final utterance.
8. WHEN a user starts a Full_Case_Run, THE Web_Workbench SHALL display Task_ID and one of queued, running, completed, failed, or cancelled until a Terminal_Event is observed.
9. WHEN a user starts an independent mediation, THE Web_Workbench SHALL create one `med_*` identity that does not equal or replace any Session_ID.
10. WHEN an evaluation completes, THE Web_Workbench SHALL link exactly one `report_id` to the initiating Session_ID or explicit evaluation input identity.
11. WHEN no Research_Pack exists for a selected category, THE Web_Workbench SHALL display an empty-state result and keep the civil-session State_Fingerprint unchanged.
12. IF a Non_Observation_Main_Journey fails before commit, THEN THE Web_Workbench SHALL preserve user-entered non-secret input until explicit retry or discard.
13. THE Release_Evidence SHALL contain one successful and one injected-failure browser trace for each Non_Observation_Main_Journey category.

### Requirement 4: BFF 与 Backend API 契约

**User Story:** As an API consumer, I want BFF 与 Backend_API 保持状态码、身份和错误语义, so that 客户端能够确定请求结果。

#### Acceptance Criteria

1. WHEN Web_Workbench sends a browser business request, THE Web_Workbench SHALL address a BFF route rather than a Backend_API origin.
2. WHEN BFF receives a non-streaming Backend_API response, THE BFF SHALL preserve the Backend_API HTTP status code, response media type, resource identifiers, and Request_ID without value translation.
3. WHEN BFF receives an SSE Backend_API response, THE BFF SHALL preserve HTTP status, `text/event-stream` media type, Request_ID, event order, and event payload values.
4. IF Backend_API returns an error, THEN THE BFF SHALL return the same status code and an error envelope containing stable error code, Public_Error_Detail, and the same Request_ID.
5. IF BFF cannot establish a Backend_API connection before the configured connection timeout, THEN THE BFF SHALL return status `502`, code `backend_unavailable`, and a BFF-generated Request_ID.
6. IF Backend_API does not complete response headers before the configured response timeout, THEN THE BFF SHALL return status `504`, code `backend_timeout`, and Request_ID.
7. WHEN Backend_API receives a request with a valid incoming Request_ID, THE Backend_API SHALL return the same Request_ID in response headers and structured logs.
8. WHEN Backend_API receives a request without a valid Request_ID, THE Backend_API SHALL generate one Request_ID and return the generated value in response headers and structured logs.
9. IF Backend_API rejects request validation, THEN THE Backend_API SHALL return status `422` and identify every rejected field by stable field path and reason code.
10. WHEN a state-changing route accepts Operation_ID, THE Backend_API SHALL return the same Operation_ID with the created or existing logical resource.
11. THE Release_Evidence SHALL contain one success, validation, authentication, not-found, injected internal-error, timeout, and unavailable-backend contract result for each Stable_Route response class declared in Release_Manifest.
12. IF a contract result contains a status-code or Request_ID mismatch, THEN THE Release_Gate SHALL reject Candidate_Release.

### Requirement 5: SSE 可靠性、取消与去重

**User Story:** As a 会话用户, I want 每个流式操作按序且只终止一次, so that 断线、重试和重复事件不会产生重复法律输出。

#### Acceptance Criteria

1. WHEN Backend_API accepts an SSE operation, THE Backend_API SHALL emit a protocol-valid `start` or heartbeat event within 1 second in Release_Test_Environment.
2. WHEN SSE_Event_Codec emits events, THE SSE_Event_Codec SHALL assign monotonically increasing sequence numbers within one Operation_ID.
3. WHEN BFF forwards SSE events, THE BFF SHALL preserve Operation_ID, Request_ID, sequence number, type, role, text, degraded, and `sub_stage` values.
4. WHEN an SSE operation completes successfully, THE Backend_API SHALL emit exactly one `complete` Terminal_Event and zero `error` or `cancelled` Terminal_Event values for the Operation_ID.
5. IF an SSE operation fails, THEN THE Backend_API SHALL emit exactly one `error` Terminal_Event containing Operation_ID, Request_ID, stable error code, and Public_Error_Detail.
6. WHEN a client disconnects before a persistent commit, THE LexGentium_System SHALL cancel associated in-process work within 5 seconds and keep the pre-operation State_Fingerprint unchanged.
7. WHEN a client disconnects after a persistent commit, THE LexGentium_System SHALL retain the committed result and avoid a second commit for the Operation_ID.
8. WHEN a Terminal_Event has been accepted for an Operation_ID, THE LexGentium_System SHALL ignore subsequent Terminal_Event values for that Operation_ID and increment a duplicate-terminal metric once per ignored event.
9. WHEN a completed Operation_ID is retried, THE LexGentium_System SHALL return the existing logical result without invoking another LLM or appending another final utterance.
10. THE SSE_Event_Codec SHALL preserve Operation_ID, Request_ID, sequence number, type, role, text, degraded, and `sub_stage` through an encode-decode round trip.
11. IF SSE_Event_Codec receives an unsupported event type or non-increasing sequence number, THEN THE SSE_Event_Codec SHALL return a typed protocol error without emitting a decoded business event.
12. THE Release_Evidence SHALL contain event counts, ordered sequence values, cancellation duration, commit count, LLM-call count, and State_Fingerprint comparison for SSE success, failure, disconnect, and retry scenarios.

### Requirement 6: 统一错误处理与降级

**User Story:** As an operator, I want 故障产生可关联且可恢复的结果, so that 依赖故障不会静默改变状态或产生无依据结论。

#### Acceptance Criteria

1. IF an unhandled Backend_API exception occurs, THEN THE Backend_API SHALL return status `500` with code `internal_error`, Public_Error_Detail, and Request_ID.
2. IF an LLM request exceeds the configured timeout, THEN THE LLM_Agent_Layer SHALL stop waiting within 5 seconds after the configured timeout and record purpose, model identity, elapsed time, and Request_ID.
3. WHEN Degraded_Mode produces content, THE LexGentium_System SHALL set `degraded=true` on the response, persisted output, and downstream Evaluation_Provenance.
4. IF a required persistence operation fails, THEN THE LexGentium_System SHALL return a persistence error and preserve the last committed State_Fingerprint.
5. IF an operation fails before state commit and is classified retriable, THEN THE Web_Workbench SHALL present one retry action carrying the original Operation_ID.
6. WHEN a retry succeeds, THE LexGentium_System SHALL create or commit exactly one logical result for the Operation_ID.
7. IF available materials cannot establish a requested legal conclusion, THEN THE LLM_Agent_Layer SHALL return an Insufficient_Material_Decision and identify each missing Unknown_Fact.
8. WHEN an Insufficient_Material_Decision is returned, THE LexGentium_System SHALL persist `admit_insufficient` as the terminal reasoning result without a synthesized replacement conclusion.
9. WHEN Public_Error_Detail is emitted, THE LexGentium_System SHALL omit Secret, stack trace, absolute path, raw prompt, full dialog text, and raw legal material.
10. THE Release_Evidence SHALL contain injected timeout, dependency failure, persistence failure, degraded response, retry, and insufficient-material results with Correlation_Context and State_Fingerprint comparisons.

### Requirement 7: 配置与 Secret 管理

**User Story:** As a deployer, I want 配置更新具备验证、原子性和恒定掩码, so that 启动和运行时配置不会泄漏或部分写入。

#### Acceptance Criteria

1. WHEN Production_Profile starts, THE LexGentium_System SHALL validate all required environment variables before Readiness_Check can succeed.
2. IF `LLM_API_KEY`, `LLM_BASE_URL`, or `LLM_MODEL` is missing or empty in Production_Profile, THEN THE Readiness_Check SHALL report component `configuration` as failed and identify the variable name without its value.
3. IF a numeric configuration value is outside its documented inclusive range, THEN THE LexGentium_System SHALL reject the configuration and return the variable name, supplied type, minimum, and maximum.
4. WHEN an API returns any Secret field, THE Backend_API SHALL return Secret_Mask exactly, independent of the Secret length and content.
5. THE LexGentium_System SHALL exclude unmasked Secret values from logs, metrics, traces, error envelopes, health responses, browser payloads, and Release_Evidence.
6. WHEN LLM configuration persistence succeeds, THE LexGentium_System SHALL atomically replace the complete configuration and restrict the resulting file to the service account.
7. IF LLM configuration persistence fails before atomic replacement, THEN THE LexGentium_System SHALL preserve the previous configuration State_Fingerprint and active configuration identity.
8. WHEN LLM configuration changes successfully, THE LLM_Agent_Layer SHALL apply the new configuration identity only to operations accepted after the commit time.
9. WHILE an operation accepted before a configuration commit remains active, THE LLM_Agent_Layer SHALL retain the configuration identity captured at operation acceptance.
10. IF configuration connectivity testing receives fallback content, empty content, authentication failure, or timeout, THEN THE Backend_API SHALL report connectivity status `failed` or `degraded` rather than `connected`.
11. THE Release_Manifest SHALL classify every supported configuration variable as required or optional, secret or non-secret, and browser-visible or server-only.
12. THE Release_Evidence SHALL contain success, invalid-range, failed-write, concurrent in-flight update, and redaction tests using at least three Secret values of different lengths.

### Requirement 8: 生产安全基线

**User Story:** As a security reviewer, I want 外部监听采用强制认证和最小暴露, so that 生产部署不会公开特权能力或敏感元数据。

#### Acceptance Criteria

1. WHERE Production_Profile configures Backend_API on a non-loopback address, THE LexGentium_System SHALL require a non-empty API_Token before process startup succeeds.
2. IF Production_Profile configures a non-loopback address without API_Token, THEN THE LexGentium_System SHALL terminate startup with a non-zero exit code before accepting a socket connection.
3. IF a request without valid API_Token targets Protected_Route, THEN THE Backend_API SHALL return status `401` and omit authentication material from response and logs.
4. WHEN BFF calls Protected_Route, THE BFF SHALL obtain API_Token only from server-only configuration and omit API_Token from browser-visible headers and payloads.
5. THE Web_Workbench SHALL omit API_Token from cookies, local storage, session storage, URLs, browser logs, and rendered markup.
6. WHERE Production_Profile enables interactive API documentation, THE Backend_API SHALL require the same API_Token validation used by Protected_Route.
7. THE Readiness_Check SHALL omit absolute filesystem paths, Secret values, database filenames, and internal stack information.
8. WHEN Web_Workbench renders external or generated plain text, THE Web_Workbench SHALL display markup characters as text rather than executable HTML or script.
9. IF a request body exceeds the documented byte limit for the target route, THEN THE LexGentium_System SHALL return status `413` before persistence or LLM invocation.
10. IF a state-changing BFF request has an Origin outside the configured allowlist, THEN THE BFF SHALL return status `403` before forwarding to Backend_API.
11. THE Release_Evidence SHALL report zero unresolved critical-severity runtime dependency vulnerabilities and list owner, mitigation, and expiry for each accepted lower-severity finding.
12. THE Release_Evidence SHALL contain loopback, external-bind, missing-token, invalid-token, documentation-access, markup, body-limit, and origin-policy security results.

### Requirement 9: LLM 智能体质量与预算

**User Story:** As a 法律工作流用户, I want 智能体预算、模型和产出身份可核验, so that 成本控制不会截断判决或掩盖降级推理。

#### Acceptance Criteria

1. WHEN purpose is clerk, extract, or score, THE LLM_Agent_Layer SHALL select the configured fast model tier.
2. WHEN `LLM_FAST_MAX_TOKENS` is absent, THE LLM_Agent_Layer SHALL use a maximum output-token value of 512 for clerk, extract, and score.
3. WHEN `LLM_FAST_MAX_TOKENS` is configured within its documented range, THE LLM_Agent_Layer SHALL pass the configured value to clerk, extract, and score requests.
4. WHEN purpose is judgment, THE LLM_Agent_Layer SHALL select the configured strong model tier and pass `LLM_MAX_TOKENS` as the model output limit.
5. WHEN a judgment response is returned within `LLM_MAX_TOKENS`, THE LLM_Agent_Layer SHALL persist the complete returned judgment without an additional application-layer character, sentence, or token truncation.
6. IF an LLM response is empty or contains only whitespace, THEN THE LLM_Agent_Layer SHALL classify the operation as failed or degraded and avoid committing an unmarked successful utterance.
7. WHEN an LLM operation terminates, THE LexGentium_System SHALL record purpose, model identity, configuration identity, prompt-version identity, latency, provider token counts when available, degraded status, Operation_ID, and Request_ID.
8. IF an LLM response states an Unknown_Fact as established, THEN THE LLM_Agent_Layer SHALL keep the reasoning-state value `unknown` and record the unsupported assertion as rejected.
9. WHEN a cached LLM result is reused, THE LLM_Agent_Layer SHALL require matching purpose, model identity, configuration identity, prompt-version identity, and deterministic-input digest.
10. IF any cache identity field differs, THEN THE LLM_Agent_Layer SHALL treat the cache entry as a miss.
11. WHEN an LLM call is retried with the same Operation_ID after a committed result, THE LLM_Agent_Layer SHALL return the committed result without issuing another provider request.
12. THE Release_Evidence SHALL contain captured request parameters for fast and judgment purposes, full-judgment length comparison, empty-response behavior, unknown-fact rejection, and cache identity tests.

### Requirement 10: HearingRuntime 与 PleadRuntime 正确性

**User Story:** As a 案件参与人, I want 听证和书状状态隔离、可恢复且有步数上限, so that 并发会话和自动执行不会交叉或失控。

#### Acceptance Criteria

1. WHERE `CI_USE_GRAPH=1`, THE Hearing_Runtime SHALL serve the default CI Web path.
2. WHERE `PLEAD_USE_RUNTIME=1`, THE Plead_Runtime SHALL serve the default CD and DD Web paths.
3. WHEN a runtime commits a turn, THE LexGentium_System SHALL persist checkpoint identity, Session_ID, Operation_ID, turn number, and State_Fingerprint atomically.
4. WHEN Backend_API restarts after a committed turn, THE LexGentium_System SHALL resume Session_ID from the highest committed turn number.
5. WHILE at least 10 Session_ID values execute concurrently, THE Hearing_Runtime SHALL keep mutable dialog, stage, counters, facts, links, and checkpoints isolated by Session_ID.
6. WHEN Plead_Runtime assembles a prompt, THE Plead_Runtime SHALL include no more than the configured number of recent conversation turns.
7. WHEN Full_Case_Run starts automatic CI progression without `CI_MAX_AUTO_TURNS`, THE Hearing_Runtime SHALL apply a maximum of 30 automatic CI steps.
8. WHEN Full_Case_Run reaches the configured automatic CI step limit, THE Hearing_Runtime SHALL emit the terminal limit result without initiating another CI_LLM_Call.
9. IF an automatic CI step is retried with the same Operation_ID, THEN THE Hearing_Runtime SHALL preserve the committed step count and avoid a duplicate CI_LLM_Call.
10. IF checkpoint persistence fails, THEN THE LexGentium_System SHALL report Session_ID, Operation_ID, and failed turn number while preserving the prior checkpoint State_Fingerprint.
11. WHEN two sessions use identical user text, THE Hearing_Runtime SHALL retain distinct Session_ID, Operation_ID, checkpoint, and correlation identities.
12. THE Release_Evidence SHALL contain runtime routing, 10-session isolation, restart-resume, failed-checkpoint, duplicate-step, context-window, 30-step, and no-extra-call results.

### Requirement 11: 持久化、导入导出与恢复

**User Story:** As an operator, I want 持久化操作具备模式验证、幂等和恢复证据, so that 重试、升级或重启不会丢失或重复用户工作。

#### Acceptance Criteria

1. WHEN LexGentium_System starts, THE Readiness_Check SHALL perform a read-write-delete probe against each required SQLite store without altering existing business records.
2. IF a required SQLite store has an unsupported schema version, THEN THE Readiness_Check SHALL report `migration_required` and reject business readiness.
3. WHEN a state-changing request repeats an Operation_ID, THE LexGentium_System SHALL return the existing logical resource and preserve resource count.
4. WHEN Conversation_Archive_Codec imports a valid archive, THE Conversation_Archive_Codec SHALL preserve Session_ID policy, stages, dialog order, links, Unknown_Fact values, reasoning metadata, and operation identities defined by the archive schema.
5. IF Conversation_Archive_Codec receives an invalid archive, THEN THE Conversation_Archive_Codec SHALL return one field error with path and reason code for each schema violation while preserving record count and pre-import State_Fingerprint.
6. THE Conversation_Archive_Pretty_Printer SHALL emit an archive accepted by Conversation_Archive_Codec under the declared schema version.
7. THE Conversation_Archive_Codec SHALL preserve normalized semantic content and identifiers through an export-import-export round trip.
8. WHEN a backup is created, THE LexGentium_System SHALL record backup identity, schema versions, start time, completion time, file digest, and maximum included commit time.
9. THE Release_Readiness_Program SHALL set Recovery_Point_Objective to no more than 24 hours.
10. THE Release_Readiness_Program SHALL set Recovery_Time_Objective to no more than 4 hours.
11. WHEN a release-compatible backup is restored into a clean Release_Test_Environment, THE Readiness_Check SHALL succeed within Recovery_Time_Objective.
12. WHEN a release-compatible backup restore completes, THE LexGentium_System SHALL match every sampled Session_ID, Task_ID, and `report_id` record to the source State_Fingerprint.
13. THE Release_Evidence SHALL contain invalid-import state comparison, idempotent retry count, restart persistence, backup digest verification, restore duration, sampled record comparison, and achieved recovery-point age.

### Requirement 12: 民事数据与研究数据分轨

**User Story:** As a 数据责任人, I want 民事与研究资产在所有边界保持分轨, so that 民事基准、夹具和未复核材料不会被陈述为正式研究内容。

#### Acceptance Criteria

1. THE LexGentium_System SHALL store Civil_Dataset and Research_Pack records under distinct schemas, locations, identifiers, API fields, selectors, and evaluation namespaces.
2. WHEN a civil session starts without Research_Pack identity, THE LexGentium_System SHALL omit research context and research identifiers from session input and persisted state.
3. WHEN a research session starts, THE LexGentium_System SHALL persist dataset, cluster, pack version, review status, and `run_id` independently from Civil_Dataset identifiers.
4. THE Research_Subsystem SHALL classify `enf-cn-notice-001` and `cisg-art79-sample-001` as Technical_Fixture.
5. WHEN Formal_Research_Pack count is calculated, THE Research_Subsystem SHALL exclude both Technical_Fixture records.
6. WHEN Formal_Research_Pack count is calculated, THE Research_Subsystem SHALL exclude all 15 annotations lacking independent review.
7. THE Research_Subsystem SHALL classify case 25 as AI-assisted initial annotation pending confirmation.
8. WHEN Formal_Research_Pack count is calculated under Authoritative_Status, THE Research_Subsystem SHALL return exactly `0`.
9. IF a user requests a Formal_Research_Pack while formal count is zero, THEN THE Research_Subsystem SHALL return an explicit `no_formal_pack` result without selecting Technical_Fixture or Unverified_Legal_Material.
10. IF Research_Pack content is submitted to a Civil_Dataset import boundary, THEN THE LexGentium_System SHALL reject the request without changing either data-track State_Fingerprint.
11. IF Civil_Dataset content is submitted to a Research_Pack import boundary, THEN THE LexGentium_System SHALL reject the request without changing either data-track State_Fingerprint.
12. WHEN no source file exists for a selection, source-text, or rule-card asset, THE Release_Readiness_Program SHALL leave the corresponding path absent rather than creating an empty directory.
13. THE Release_Evidence SHALL contain inventory counts, classification values, two-way boundary rejection, civil-session context inspection, and State_Fingerprint comparisons.

### Requirement 13: 法律事实完整性与研究停止条件

**User Story:** As a 法律研究者, I want 不确定事实和论证上限成为可审计状态, so that 系统不会补造事实、权威或超限论证。

#### Acceptance Criteria

1. WHEN source material omits a fact required by a claim, THE Research_Subsystem SHALL store the fact value as `unknown` with source status `absent`.
2. IF a claim depends on an Unknown_Fact, THEN THE Research_Subsystem SHALL identify the Unknown_Fact in the claim chain and avoid marking the claim as established.
3. IF available material cannot support a requested claim, THEN THE Research_Subsystem SHALL create an Insufficient_Material_Decision with value `admit_insufficient`.
4. WHEN an Insufficient_Material_Decision is committed, THE Research_Subsystem SHALL stop support generation for the affected claim and record zero subsequent support-generation LLM calls.
5. WHEN a New York Convention enforcement run counts its twelfth claimant-or-respondent utterance, THE Research_Subsystem SHALL terminate the argument round.
6. WHEN a CISG Article 79 run counts its tenth claimant-or-respondent utterance, THE Research_Subsystem SHALL terminate the argument round.
7. WHEN an argument counter is updated, THE Research_Subsystem SHALL count only utterances whose role is claimant or respondent.
8. WHEN clerk, tribunal, system, tool, or observer utterances occur, THE Research_Subsystem SHALL keep the claimant-or-respondent argument counter unchanged.
9. WHEN either research argument limit is reached, THE Research_Subsystem SHALL initiate zero additional CI_LLM_Call values for that argument round.
10. IF a duplicate party utterance carries an already committed Operation_ID, THEN THE Research_Subsystem SHALL keep the argument counter unchanged.
11. WHEN a legal source anchor is absent, THE Research_Subsystem SHALL store anchor status `unavailable` without generating replacement citation text.
12. THE Release_Evidence SHALL contain role-by-role counter traces, duplicate-operation traces, terminal turn numbers, CI_LLM_Call counts after each limit, Unknown_Fact state, and `admit_insufficient` stop traces.

### Requirement 14: Research Pack 解析、复核与输出

**User Story:** As a 研究维护者, I want 研究包解析、复核资格和导出可往返验证, so that 夹具与未复核材料无法获得正式状态。

#### Acceptance Criteria

1. WHEN Research_Pack_Codec receives a schema-valid pack, THE Research_Pack_Codec SHALL return a structured Research_Pack containing the declared schema version and pack identity.
2. IF Research_Pack violates the declared schema, THEN THE Research_Pack_Codec SHALL return one field error with path and reason code for each schema violation without registering the pack.
3. THE Research_Pack_Pretty_Printer SHALL emit a representation accepted by Research_Pack_Codec under the same declared schema version.
4. THE Research_Pack_Codec SHALL preserve dataset, cluster, version, role-material visibility, source anchors, claims, Unknown_Fact values, and review status through a parse-print-parse round trip.
5. WHEN a Research_Pack requests formal status, THE Research_Subsystem SHALL require independent-reviewer identity, review timestamp, reviewed pack version, review outcome, and reviewed-content digest.
6. IF any formal-review field is missing or the reviewed-content digest differs, THEN THE Research_Subsystem SHALL classify the Research_Pack as non-formal.
7. WHEN Research_Subsystem exports a run, THE Research_Subsystem SHALL include pack identity, `run_id`, rubric version, model identity, configuration identity, degraded status, Unknown_Fact values, and source-anchor availability.
8. IF two research runs differ in dataset, cluster, pack version, or rubric version, THEN THE Research_Subsystem SHALL reject direct score comparison with a compatibility error.
9. WHEN a Research_Pack registration repeats the same pack identity and content digest, THE Research_Subsystem SHALL preserve pack count and return the existing record.
10. THE Release_Evidence SHALL contain valid parse, multi-field invalid parse, failed-registration state comparison, round trip, incomplete-review, digest-mismatch, duplicate-registration, export, and incompatible-comparison results.

### Requirement 15: 评测与结果可追溯性

**User Story:** As an evaluator, I want 每个分数绑定不可变输入和完整来源, so that 评测结果能够复现、去重和审计。

#### Acceptance Criteria

1. WHEN a Web evaluation starts from Session_ID, THE LexGentium_System SHALL derive prediction input from the latest committed ordered dialog for that Session_ID.
2. WHEN an evaluation task is accepted, THE LexGentium_System SHALL persist Evaluation_Provenance before score computation begins.
3. THE Evaluation_Provenance SHALL contain input digest, Session_ID when applicable, prediction identity, evaluator version, rubric version, configuration identity, model identity, creation time, Operation_ID, and degraded status.
4. WHEN an evaluation completes, THE LexGentium_System SHALL associate the immutable result with exactly one `report_id` and one Evaluation_Provenance record.
5. WHEN Evaluation_Report is retrieved, THE Backend_API SHALL return `report_id`, metric results, Evaluation_Provenance, and Correlation_Context.
6. IF required evaluation input is missing, THEN THE Backend_API SHALL return status `422` with each missing field path and preserve report count.
7. WHEN evaluation input includes Degraded_Mode output, THE Evaluation_Report SHALL identify each metric affected by degraded input.
8. THE LexGentium_System SHALL store civil LexEval, J1, and CADD results in a namespace distinct from Research_Subsystem rubric results.
9. WHEN Web evaluation input is generated, THE LexGentium_System SHALL derive input from persisted application state without reading or creating `data/session_predictions/`.
10. WHEN an evaluation Operation_ID is retried, THE LexGentium_System SHALL return the existing Task_ID or `report_id` without creating a second Evaluation_Report.
11. THE Release_Evidence SHALL contain input-digest recomputation, provenance-field checks, report immutability, missing-input state comparison, degraded-metric labeling, namespace separation, retry report count, and absence of `data/session_predictions/` access.

### Requirement 16: 可观测性与健康状态

**User Story:** As an operator, I want 存活、就绪、日志、指标和告警具有固定语义, so that 故障能够在不暴露案件内容的情况下被检测和关联。

#### Acceptance Criteria

1. WHEN Liveness_Check is requested, THE Backend_API SHALL report process availability without accessing an external LLM, required SQLite business records, or law retrieval.
2. WHEN Readiness_Check is requested, THE Backend_API SHALL report configuration, each required SQLite store, law retrieval, Hearing_Runtime, and Plead_Runtime as separate named components.
3. IF any required readiness component fails, THEN THE Readiness_Check SHALL return a non-2xx status and identify each failed component with a stable reason code.
4. WHEN a Backend_API request terminates, THE LexGentium_System SHALL emit exactly one structured request log containing Request_ID, route template, method, status, and duration milliseconds.
5. WHEN Correlation_Context fields are available, THE LexGentium_System SHALL include each available non-secret identity in the structured request log.
6. THE LexGentium_System SHALL omit raw prompts, raw legal materials, full dialog text, Secret values, and absolute paths from default production logs.
7. THE LexGentium_System SHALL publish Operational_Metric values for request count, error count, request latency, active SSE streams, LLM failures, degraded responses, persistence failures, duplicate Terminal_Event values, and CI_LLM_Call count.
8. WHEN an SSE stream opens or closes, THE LexGentium_System SHALL update active-SSE gauge within 1 second.
9. WHEN rolling 5-minute Stable_Route request count reaches at least 20 and error rate exceeds 5 percent, THE Monitoring_Configuration SHALL enter alert state within 60 seconds.
10. WHEN Readiness_Check remains unsuccessful for 2 continuous minutes, THE Monitoring_Configuration SHALL enter alert state within 60 seconds.
11. WHEN an alert condition clears for one complete evaluation window, THE Monitoring_Configuration SHALL record recovery time and return the alert to resolved state.
12. THE Release_Manifest SHALL document each Operational_Metric name, type, unit, label set, alert expression, evaluation interval, and operator-response link.
13. THE Release_Evidence SHALL contain liveness dependency-isolation, per-component readiness failure, one-log-per-request, forbidden-field scan, metric transitions, alert trigger, and alert recovery results.

### Requirement 17: 性能与资源边界

**User Story:** As a release engineer, I want 性能结论基于明确样本和 p95 规则, so that 候选版本的回归与容量拒绝可重复验证。

#### Acceptance Criteria

1. THE Release_Evidence SHALL identify Release_Test_Environment and Approved_Baseline for every performance result.
2. WHEN non-LLM Stable_Route endpoints receive 10 concurrent clients for 5 continuous minutes, THE Backend_API SHALL process at least 300 successful-or-failed Performance_Sample values with p95 latency at or below 500 milliseconds and error rate below 1 percent.
3. WHEN production Web_Workbench serves each Non_Observation_Main_Journey entry page for 30 cold-navigation samples, THE Web_Workbench SHALL enable the primary action within 3 seconds at p95 under the documented network profile.
4. WHEN p95 is calculated, THE Release_Readiness_Program SHALL sort all valid Performance_Sample durations and select the nearest-rank 95th-percentile value.
5. WHEN Hearing_Runtime executes at least 30 samples of the approved hearing benchmark, THE Candidate_Release SHALL keep p95 local turn latency within 20 percent above Approved_Baseline under identical model and fixture identities.
6. WHEN Plead_Runtime executes at least 30 samples of the approved pleading benchmark, THE Candidate_Release SHALL keep p95 local turn latency within 20 percent above Approved_Baseline under identical model and fixture identities.
7. WHEN a performance sample uses an external LLM, THE Release_Evidence SHALL report provider latency separately from local processing latency.
8. IF Backend_API reaches a documented concurrency limit, THEN THE Backend_API SHALL return status `429`, stable code `capacity_exceeded`, and a positive integer retry interval before accepting additional work.
9. WHEN Full_Case_Run reaches completed, failed, or cancelled state, THE LexGentium_System SHALL release associated in-process queues and runtime resources within 10 seconds.
10. IF any performance test has fewer than the required valid samples or differs from Approved_Baseline environment identity, THEN THE Release_Gate SHALL classify the result as invalid rather than passed.
11. THE Release_Evidence SHALL contain raw sample count, excluded-sample reasons, p50, p95, maximum, error rate, resource-release duration, and test parameter digest.

### Requirement 18: 自动化测试与质量门禁

**User Story:** As a maintainer, I want 发布门禁覆盖端到端、契约、并发、重启、边界和安全行为, so that 候选版本具有可重复的工程证据。

#### Acceptance Criteria

1. THE Release_Gate SHALL run the complete Python test suite under `mock_court_system/tests/` with zero failed tests.
2. THE Release_Gate SHALL run TypeScript type checking with zero errors and a production Next.js build with exit code `0`.
3. THE Release_Gate SHALL exclude Observation_Presentation visual quality and `components/hearing-3d` visual tests from this feature's acceptance calculation.
4. THE Release_Gate SHALL verify legacy `/court3d` only through redirect contract tests to `/hearing-3d`.
5. THE Release_Gate SHALL run browser E2E tests for configuration success and failure, conversation creation, ordered streaming, session resume after restart, Full_Case_Run status, evaluation report retrieval, research empty state, and readiness display.
6. THE Release_Gate SHALL run API/BFF contract tests for success, validation, authentication, not-found, internal error, timeout, unavailable backend, status-code preservation, Request_ID preservation, and SSE Terminal_Event behavior.
7. THE Release_Gate SHALL run concurrency tests with at least 10 simultaneous Session_ID values and verify zero cross-session identity or state mismatches.
8. THE Release_Gate SHALL run committed-state recovery tests across Backend_API restart and verify State_Fingerprint equality.
9. THE Release_Gate SHALL run two-way Civil_Dataset and Research_Pack boundary rejection tests and verify unchanged State_Fingerprint values.
10. THE Release_Gate SHALL run security tests for Secret_Mask constancy, forbidden-data redaction, external-bind token enforcement, cross-origin rejection, request-size limits, markup encoding, and production API-document access.
11. THE Release_Gate SHALL run operation-retry tests that verify unchanged logical resource count and no duplicate LLM call after commit.
12. WHEN critical non-LLM gate tests run three consecutive times against the same Commit_ID, THE Release_Gate SHALL require zero failed and zero intermittently passing tests across all three runs.
13. IF any required automated check fails, times out, lacks required samples, or lacks Correlation_Context, THEN THE Release_Gate SHALL reject Candidate_Release.
14. THE Release_Evidence SHALL record check identity, exact Documented_Command, start time, duration, exit code, result, Version_ID, Commit_ID, environment identity, sample count, and artifact digest for each gate check.

### Requirement 19: 文档与部署可重复性

**User Story:** As a deployer, I want 安装、最小权限部署、备份和回滚步骤可执行, so that 新环境不依赖隐藏知识并可在故障后恢复。

#### Acceptance Criteria

1. THE Release_Documentation SHALL identify `mock_court_system/` as the only Web installation, build, and deployment working directory.
2. THE Release_Documentation SHALL identify `api_server.py` and the production Next.js server as the two Web entry processes.
3. THE Release_Documentation SHALL identify `main.py` and `core/offline/api_reconstructor` as offline batch paths rather than Web entry processes.
4. THE Installation_Documentation SHALL use repository Python dependency declarations and npm lock files without an unlocked dependency-install command.
5. THE Deployment_Documentation SHALL run Backend_API and Next.js under distinct or shared non-root service accounts with write access limited to documented runtime-data paths.
6. WHERE Production_Profile is reachable outside the host, THE Deployment_Documentation SHALL require TLS termination, trusted proxy addresses, forwarded-header policy, and API_Token configuration.
7. THE Deployment_Documentation SHALL define startup order, per-process readiness check, graceful shutdown timeout, log location, metric endpoint, backup, restore, upgrade, and rollback steps.
8. THE Deployment_Documentation SHALL provide one Documented_Command and expected result for each Non_Observation_Main_Journey smoke-test category.
9. THE Deployment_Documentation SHALL state Formal_Research_Pack count `0`, identify both SAMPLE records as Technical_Fixture, identify 15 annotations as not independently reviewed, and identify case 25 as pending confirmation.
10. THE Deployment_Documentation SHALL state that Civil_Dataset lacks complete train, validation, and test JSONL files and remains separate from Research_Subsystem data.
11. WHEN each Documented_Command runs in a clean Release_Test_Environment, THE Documented_Command SHALL produce its documented exit code and result without undeclared files, variables, privileges, or working-directory changes.
12. WHEN rollback instructions run against Candidate_Release, THE Deployment_Documentation SHALL restore the prior approved version and achieve successful Readiness_Check within Recovery_Time_Objective.
13. THE Release_Evidence SHALL contain non-root process identity, filesystem permission check, clean-environment command transcript, smoke-test results, backup transcript, restore transcript, and rollback duration.

### Requirement 20: 发布审批、回滚与证据

**User Story:** As a release owner, I want go/no-go 决策由完整且不可混淆的证据驱动, so that 工程阻断项、内容缺口和残余风险均可审计。

#### Acceptance Criteria

1. THE Release_Gate SHALL require one Release_Manifest bound to Version_ID `1.0.0` and one full Commit_ID.
2. THE Release_Gate SHALL require zero open Engineering_Release_Blocker records.
3. THE Release_Gate SHALL require every mandatory Release_Evidence record to identify the same Commit_ID as Candidate_Release or a descendant artifact built from that Commit_ID.
4. THE Release_Gate SHALL require a successful backup-and-restore drill and a successful rollback drill against Candidate_Release.
5. WHEN Legal_Content_Gap, Data_Capability_Limitation, or Accepted_Risk remains open, THE Release_Gate SHALL require item identity, impact, owner, approving identity, acceptance time, expiry or review time, and mitigation.
6. THE Release_Gate SHALL require a source-control scan with zero tracked `.env` files, zero tracked `*.sqlite3` files, and zero tracked paths under `data/session_predictions/`.
7. THE Release_Gate SHALL require generated runtime data and Release_Evidence artifacts to reside outside immutable application source artifacts.
8. IF a mandatory evidence record is missing, stale, digest-invalid, or bound to a different Commit_ID, THEN THE Release_Gate SHALL produce a no-go result.
9. IF backup restore, rollback, security, contract, data-boundary, restart, concurrency, E2E, build, type-check, or required test verification fails, THEN THE Release_Gate SHALL produce a no-go result.
10. WHEN every Release_Gate criterion passes, THE Release_Readiness_Program SHALL produce one go decision containing decision time, approver identity, Version_ID, Commit_ID, Release_Manifest digest, and Release_Evidence links.
11. WHEN any Release_Gate criterion fails, THE Release_Readiness_Program SHALL produce one no-go decision listing each failed criterion, evidence link, owner, and required closure action.
12. WHEN a go or no-go decision is produced, THE Release_Readiness_Program SHALL preserve the decision as an append-only audit record whose digest is referenced by Release_Manifest.
13. THE Release_Manifest SHALL disclose Formal_Research_Pack count `0`, both Technical_Fixture identities, the 15 unreviewed annotations, case 25 pending confirmation, Civil_Dataset incompleteness, and Observation_Presentation exclusion separately from Engineering_Release_Blocker status.

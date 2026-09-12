# LexGentium 推理优化技术报告

> 版本：2026-09-10  
> 范围：案件数据契约、CI 庭审状态机、事实与证据推理、法律检索、双模式推理、多法官聚合、博弈更新与实验评估  
> 方法：代码静态审计、离线回归测试、历史与新实验结果对比；不把 LLM 输出长度或自评分数等同于法律推理质量

---

## 1. 执行摘要

LexGentium 已经具备完整的法律推理骨架：CD/DD/CI 三阶段、庭审状态机、混合检索、结构化判决、Behavior-Liability-Statute 责任链、快慢双模式、多法官聚合和博弈评估。但当前最主要的问题不是模型“不够会思考”，而是**进入模型的案件信息、状态和证据不够稳定，输出后的校验也不够严格**。

优先级最高的三项问题是：

1. **案件数据契约错位**：实验和编排器传入 `case_id/cause/case_description/plaintiff_claims/plaintiff_name/defendant_name`，CIAgent 却主要读取 `id/case_type/claim_description/plaintiff_info/defendant_info/third_party_findings`。结果可能是判决提示词退化为“原告/被告/民事纠纷/空诉请/空客观事实”。
2. **庭审状态每轮重置、回放不完整**：CIAgent 每次 API 调用重建 StateMachine，再用启发式规则回放历史；法官侧写入的程序状态、证据完毕、质证和调解状态不能可靠恢复，且存在写错字段的问题。这会导致重复提问、阶段漂移、最大轮次耗尽以及不稳定判决。
3. **推理成功与降级失败没有语义隔离**：LLM JSON 失败时多处返回 `{}`，评分再默认成 0.5；实验的 api_hybrid 又把真实 API 分数和伪随机 fallback 分数混入同一收益矩阵。因此 `api_success`、SPNE/NE 指标和推理质量可能被“技术成功但语义失败”的样本污染。

结论：**下一阶段不建议继续增加 Chain-of-Thought 提示词或更多 Agent。应先建立可追踪的事实-证据-争点-法条-结论链和严格的失败门控。**

---

## 2. 当前实验结论的证据边界

### 2.1 三个批次对比

| 批次 | API 成功 | 进化方法 | 权重 win/reason/evidence | SPNE | NE | 差值 | 统计结论 |
|---|---:|---|---|---:|---:|---:|---|
| 2026-04-19 旧批次 | 0/24 | fictitious_play | 0.55/0.25/0.20 | 0.70 | 0.60 | +0.10 | 全部 fallback，不能证明真 API 表现 |
| 2026-09-10 第一批 | 17/18 | best_response | 0.50/0.25/0.25 | 0.30 | 0.70 | -0.40 | 配置不同，不可与旧批次比较；p=0.127 |
| 2026-09-10 v2 对齐批 | 1/18 | fictitious_play | 0.55/0.25/0.20 | 0.40 | 0.30 | +0.10 | 17/18 fallback；95% CI [-0.3, 0.5]，p=1.0 |

v2 日志包含大量 402/502（日志命中次数，不等于独立请求数）：LLM 402 与 HTTP 402 各 50 条、HTTP 502 为 18 条，另有少量 400。说明指标主要反映 fallback 模型和随机分数逻辑，不是真实法律推理。

### 2.2 “SPNE/NE 准确率”的实际含义

`evaluation/run_two_step_small_sample.py:580-601` 先从同一收益矩阵计算 NE/SPNE，再判断末轮观察策略是否与这些预测相同。这个指标是**策略预测一致率**，不是法律判决准确率，也不是 SPNE 理论正确率。

主要问题：

- 预测与评估使用同一批收益矩阵，属于 in-sample 自洽性，不是泛化能力；
- 只评估最后一轮 10 个样本，统计功效很弱；
- `api_hybrid` 在 API 失败时使用伪随机本地分数（`run_two_step_small_sample.py:351-358`），真实与 synthetic 数据混入同一矩阵；
- by-cause ESS 分析重新调用 `score_from_case`（`run_two_step_small_sample.py:677-688`），即使某些案件 API 成功，分案由分析仍可能完全使用 synthetic 分数；
- evolution_method 传入 API，但本地策略选择仍固定采用 cause prior + best response + exploration（`run_two_step_small_sample.py:312-330`），配置名与本地演化逻辑不完全一致。

建议把当前 `spne_acc/ne_acc` 重命名为 `spne_strategy_agreement/ne_strategy_agreement`，避免论文和界面产生过度解释。

---

## 3. 核心推理问题审计

## 3.1 P0：案件数据契约错位

CIAgent 在 `agents/ci_agent.py:314-330` 构造 CaseInfo 时读取：

- `id`
- `plaintiff_info.name`
- `defendant_info.name`
- `case_type`
- `claim_description` 或 `claim`
- `third_party_findings`

实验数据和 `_build_case_info` 实际提供：

- `case_id`
- `plaintiff_name`
- `defendant_name`
- `cause`
- `plaintiff_claims`
- `case_description`

这会直接削弱 `_get_judgment_prompt` 的案件基本信息、诉讼请求、客观事实和检索 query。模型再强，也是在错误或空上下文上推理。

**修复方案：CanonicalCaseBundle**

```text
CanonicalCaseBundle
├── case_id
├── cause
├── parties
│   ├── plaintiff{name, attributes, source}
│   └── defendant{name, attributes, source}
├── claims[] {id, text, amount, legal_basis?, source}
├── case_facts[] {id, text, source, admitted?, disputed?}
├── evidence[] {id, provider, content, purpose, authenticity_status}
└── metadata {dataset_source, jurisdiction, decision_date}
```

在 API 边界一次性完成旧字段兼容映射，后续 Agent 禁止直接读取任意字典键。映射后必须做 schema 校验：缺少 cause、claims、case_facts 时返回可解释错误，而不是以空字符串继续生成判决。

## 3.2 P0：CI 状态重置与回放漂移

`agents/ci_agent.py:115-159` 每次 `process_turn` 都：

- 新建 StateMachine；
- 清空 dialogue/evidences/extracted；
- 回放除最后一条之外的历史；
- 仅对非 Judge 消息调用 `_fast_update_state`。

具体缺陷：

- 法官模板在生成时设置的 `court_composition_announced/procedure_announced` 无法从 Judge 消息回放；
- `_fast_update_state` 对调查阶段的“没有/完毕/无异议”只执行 `pass`（`ci_agent.py:194-197`）；
- 开庭回放写入 `absence_acknowledged`（`ci_agent.py:181`），但 StateMachine 真正要求的是 `absence_asked_mask`（`state_machine.py:59,120`）；
- 证据、质证等待、关闭争点、调解状态都不能完整恢复；
- `name_confirmed_by_dialogue` 未随新 session 显式重置，存在跨会话残留风险；
- API 层共享一个 CIAgent 实例（`api/state.py:111-116`），并发会话可能互相覆盖 `case_info/state_machine/dialogue/judgment_json`。

**推荐方案：每个会话持久化 ReasoningState，而不是每轮重放自然语言。**

```text
ConversationRecord
├── dialog_history
├── reasoning_state
│   ├── court_state + sub_stage
│   ├── phase flags
│   ├── fact_ledger
│   ├── evidence_ledger
│   ├── dispute_graph
│   └── degradation/provenance
└── version
```

StateMachine 应增加 `to_dict()/from_dict()`；每次消息只对“最新事件”做 reducer 更新，并以 SQLite 乐观锁（version）保存。每个 session 拥有独立 CIAgent context，或彻底让 Agent 无状态、所有状态显式传参。

LLM 只负责提出结构化事件：

```json
{"event":"EVIDENCE_SUBMITTED","party":"plaintiff","evidence_id":"E1","confidence":0.91}
```

规则层负责验证事件是否合法并更新状态。低置信事件不得自动推动流程。

## 3.3 P0：失败被吞成正常推理

`core/llm_client.py:253-339` 的 `chat_json` 对非 400 HTTP 错误和未知异常返回 `{}`。随后：

- CIAgent 可能把空 judgment_json 格式化为系统提示或空字段判决；
- GameEngine 评分把缺失字段默认成 0.5（`game_engine.py:359-365`）；
- API 可能返回 HTTP 200 和完整数值，看起来“成功”；
- 实验只根据 HTTP 层决定 api_success，无法识别语义降级。

**修复方案：统一 ReasoningResult 信封**

```json
{
  "status": "ok | degraded | failed",
  "value": {},
  "provenance": {"model":"...","prompt_version":"...","retrieval_ids":[]},
  "errors": [{"code":"LLM_402","retryable":false}],
  "confidence": 0.0
}
```

要求：

- 判决 JSON 缺少 facts/issues/laws/dispositions 任一必需字段，状态不得为 ok；
- `degraded/failed` 案件不得写入真实 API 收益矩阵；
- api_success 必须定义为“HTTP 成功 + schema 有效 + 无降级 + 判决校验通过”；
- 实验 strict 模式下，只要真实 API 成功率低于 95%，整个批次判 invalid，不输出主结论。

## 3.4 P1：证据推理仍以文本为中心

CIAgent 目前靠关键词触发证据抽取（`ci_agent.py:511-514`），再由 LLM 判断是否提交证据。重复证据会直接把当事人标记为“无更多证据”（`ci_agent.py:1434-1443`），这在逻辑上不成立：重复提交不等于举证完毕。

建议构造 **Fact-Evidence Ledger**：

| 事实主张 | 主张方 | 争议状态 | 举证责任 | 支持证据 | 反证 | 可信度 | 裁判采用 |
|---|---|---|---|---|---|---:|---|
| 借款交付 | 原告 | disputed | 原告 | E1 转账记录 | — | 0.92 | adopted |
| 已经还款 | 被告 | disputed | 被告 | E3 收据 | E1流水 | 0.35 | rejected |

每条判决事实必须引用 ledger 中的 source id。无证据的争议事实不得被自动写成“本院查明”。

## 3.5 P1：RAG 有检索，但缺少法条真实性验证

现有优点：向量 + BM25 + RRF + rerank，且有 135 条精选法条库。

主要问题：

- 主 CI 判决只做一次 query（`ci_agent.py:1094-1115`），ProgressiveRAG 主要存在于独立接口，并未进入 `run_full_case` 主链；
- query 取客观事实或摘要前 1000 字，未按争议焦点拆分；
- 提示词写“仅供参考，请优先适用”，语义自相矛盾；
- 生成的 `applicable_laws` 没有回查 SQLite，模型可编造法条编号或条文内容；
- LiabilityChain 是从生成后的判决再用同类 LLM 抽取（`liability_chain.py:117-162`），属于事后自解释，不是独立验证；
- LiabilityChain 的“法条覆盖”只检查数字是否出现在判决文本（`liability_chain.py:208-215`），不能证明引用正确。

**推荐：Issue-driven Verified RAG**

1. 从 FactLedger 生成 2-5 个争议焦点；
2. 每个争点独立生成检索 query；
3. 只允许引用数据库返回的 `law_id/law_name/article_number/content`；
4. 输出前回查法条编号与内容；
5. 如果无命中，输出 `insufficient_legal_basis`，禁止模型自由编造；
6. 记录每条法律结论的 `retrieval_id + issue_id`。

当前法条库只有 135 条，报告和 UI 必须明确“实验精选库”，不能表现为通用法律数据库。

## 3.6 P1：Dual-mode 的“信息增益”偏好长文本

启发式分数（`dual_mode_reasoning.py:93-109`）主要依赖：

- 输出长度比；
- 法条数量；
- 分点数量；
- 法律术语频率。

这会奖励冗长、堆法条和格式化输出，不能验证事实正确性或法条适用性。LLM 评分又由同一模型比较自己生成的 fast/slow 输出（`dual_mode_reasoning.py:159-176`），存在自评循环。最终阈值大于 0.3 就推荐 slow（`dual_mode_reasoning.py:205`），门槛过低。

**改为 risk/uncertainty routing：**

仅当出现以下任一条件才启动 slow mode：

- 争议事实多、证据冲突；
- 涉及多个请求权基础或竞合法条；
- 检索结果低置信或互相冲突；
- 快模式结论与规则基线不一致；
- 多法官分歧；
- 高金额、弱势方、时效或程序性风险。

slow mode 的胜出标准应是：引用有效、事实一致、诉请逐项处理、规则测试通过，而不是更长。

## 3.7 P1：Multi-judge 不是独立法官，聚合过于粗糙

默认 additional_llms 为空（`multi_judge.py:158-165`），三个“法官”通常仍是同一模型，仅 persona 和温度不同。agreement 只检查判决文本是否出现“支持/驳回”等关键词（`multi_judge.py:127-152`），无法处理“部分支持不同诉请”的真实判决结构。

建议改成职责分工，而非三个同质判决：

1. **裁判生成器**：形成逐项裁判；
2. **事实与证据审查员**：只检查每个事实是否有证据支持；
3. **法条核验员**：回查法规库，验证法条存在性和适用关系；
4. **一致性审查员**：检查事实、理由、主文、金额是否矛盾；
5. **最终聚合器**：只能从已验证的候选结论中选择或要求重生成。

一致性应按 claim_id 比较每项 disposition（support/reject/partial + amount），而不是全文关键词。

## 3.8 P1：同一模型生成又评分，形成闭环偏差

GameEngine 用同一个 llm：

- 生成诉辩与判决；
- 评分 plaintiff_win_rate/reasoning_quality/evidence_strength（`game_engine.py:337-365`）；
- 再用分数更新收益矩阵和策略。

这样模型的写作风格、偏好和评分偏差会被反馈到下一轮，可能制造“策略收敛”的假象。字面诉请覆盖规则（`game_engine.py:314-331`）只检查诉请前 40 字是否原样出现在判决中，易漏同义表达，也会奖励复制诉请文本。

建议至少做到：

- generator 与 evaluator 使用不同模型/不同 prompt family；
- 规则评价优先，LLM evaluator 只补充无法规则化的项；
- 对裁判主文做结构化 disposition 解析后评分；
- 报告 evaluator 模型、prompt version、温度和失败率；
- 关键基准增加人工双盲标注或真实文书对照。

---

## 4. 目标推理架构

```text
API Input
  ↓
Case Normalizer + Schema Gate
  ↓
CanonicalCaseBundle
  ↓
Fact/Evidence Ledger ───────┐
  ↓                         │
Issue Decomposer            │
  ↓                         │
Verified RAG (per issue)    │
  ↓                         │
IRAC Reasoner per issue     │
  ↓                         │
Claim Disposition Table     │
  ↓                         │
Fact/Citation/Amount/Logic Validators
  ↓                         │
Risk Router ── low risk → Fast Judgment
           └─ high risk → Critics + Revision
  ↓
StructuredJudgment + provenance + confidence + degradation
  ↓
Renderer（判决书文本）
```

推荐核心输出结构：

```json
{
  "facts": [{"id":"F1","text":"...","sources":["E1"],"status":"adopted"}],
  "issues": [{"id":"I1","question":"借款是否实际交付"}],
  "laws": [{"law_id":81,"article":"民法典第676条","verified":true,"issue_ids":["I2"]}],
  "analysis": [{"issue_id":"I1","rule_ids":["L1"],"fact_ids":["F1"],"application":"..."}],
  "dispositions": [{"claim_id":"C1","result":"partial","amount":80000,"reason_issue_ids":["I1"]}],
  "validation": {"schema":true,"citations":true,"facts":true,"amounts":true},
  "status":"ok",
  "confidence":0.83
}
```

---

## 4.5 实施进度（2026-09-11 更新）

**Phase 0 已落地（全部经离线契约测试验证，套件 24/24 通过）：**

| 项目 | 状态 | 位置 |
|---|---|---|
| CanonicalCaseBundle 新旧字段兼容映射 + warnings/validation_errors | ✅ | `core/case_bundle.py` |
| CI 字段契约修复（真实数据集样本测试通过：案号/案由/姓名/诉请/事实全保真） | ✅ | `agents/ci_agent.py:_build_case_info` |
| StateMachine `to_dict/from_dict/apply_dict` 序列化 | ✅ | `core/state_machine.py` |
| 回放 bug 修复：`absence_acknowledged`→`absence_asked_mask`；法官程序性标志回放 | ✅ | `agents/ci_agent.py:_fast_update_state` |
| `process_turn(reasoning_state=)` 持久化恢复路径（旧回放路径保留兼容） | ✅ | `agents/ci_agent.py:process_turn` |
| reasoning_state 全链路：conversation 存取（`input_json["_reasoning_state"]`，零 schema 变更），send_message 与 stream_message 两端接入 | ✅ | `api/state.py` + `api/routers/conversation.py` |
| JudgmentValidator（ok/degraded/failed 三级 + 缺失清单），CI 判决后校验 | ✅ | `core/judgment_validator.py` |
| Verified RAG 法条回查：`verify_citations` 解析书名号+中文数字条号，与 legal_articles.db 比对，未命中标 unverified；接入 CI 判决流与 `_report` | ✅ | `core/judgment_validator.py` + `agents/ci_agent.py` |
| 契约测试 12 个用例（数据保真/旧契约/真实样本/判决校验/状态往返/法条回查命中与未命中） | ✅ | `tests/test_reasoning_contracts.py` |

**Phase 0 补充落地（同日第二批）：**
- `extract_ci_reasoning_state` 下沉至 `core/reasoning_state.py`（避免 core→api 循环导入），`api/state.py` 的 save 函数复用；
- orchestrator `run_stage_ci` 跨轮维护 `reasoning_state`：每轮从 CIAgent 提取快照传入下一轮 `process_turn`，game round 场景同样消除重放漂移（`_agent_turn` 已透传）；
- `name_confirmed_by_dialogue` 纳入状态序列化与恢复（消除跨会话残留）；
- 新增编排器级测试：验证第二轮回合收到的状态快照非空且包含 state_machine。

**Phase 0 收尾全部完成（同日第三批）：**
- 会话级隔离：新增 `new_session_ci_agent()` 工厂（chains 轻对象按请求构造、law_retriever 单例共享），conversation 的 send/stream 两端点 CI 场景改用独立实例，消除共享实例并发覆盖窗口；测试验证两次工厂调用实例独立、检索器共享；
- 元数据传播：`ConversationMessageResponse.reasoning_meta`（judgment_status / citation_report / case_warnings）随响应与 SSE final 事件下发，前端类型已同步（`lib/conversation-types.ts`）；
- 环境修复：Xcode CLT 路径变化导致 venv 解释器断链，已基于 CommandLineTools Python 3.9.6 + requirements.lock 重建 `.venv-test`，全套 26/26 通过、tsc 零错误。

**Phase 1 第一块已落地（2026-09-12，Fact/Evidence Ledger）：**
- `core/fact_ledger.py`：EvidenceLedger（内容规范化去重，重复提交只累加计数）+ FactLedger（占位事实主张、证据挂载/反证、争议状态、adjudicate）+ `disputed_without_evidence()` 无证据争议清单 + 完整序列化；
- CI 集成：证据抽取成功即入账并自动创建占位事实主张；**重复提交不再误标"举证完毕"**（报告 P0 审计 3.4 的逻辑修正）；判决提示词注入台账文本，要求"本院查明"逐条引用 F/E 编号，无证据争议事实显式警告不得写入；
- `extract_ci_reasoning_state` 携带 ledger（三路径持久化覆盖）；`_report` 增加台账摘要（claims/evidence/无证据争议清单）；
- 测试：新增 ledger 用例 9 个，全套 **35/35 通过**。

**已知待办（转入 Phase 1 余下）：**
- 前端 UI 展示 reasoning_meta（判决语义状态徽标、未验证法条提示）；
- IssueGraph 争点分解 + per-issue IRAC + 逐诉请 Disposition Table（Phase 1 核心，依赖 Ledger）；
- fact_finding 引用校验（verify_facts：判决查明事实须回指 ledger F/E 编号）。

## 5. 分阶段实施路线图

## Phase 0：先修推理底座（1-3 天，最高优先级）

1. 增加 CanonicalCaseBundle 和兼容映射；
2. 修复 CIAgent 字段契约并补样本级测试；
3. 每 session 独立 ReasoningState；移除共享 CIAgent 可变状态；
4. StateMachine 增加序列化/反序列化与事件 reducer；
5. 重复证据不得自动标记“举证完毕”；
6. 统一 ReasoningResult，传播 degraded/failed；
7. 实验 strict 模式：真实成功率 <95% 直接判批次无效；
8. 保留已修复的策略顺序更新和快慢推理真并发测试。

**验收：**

- 实验样本传入 CI 后，case_id/cause/facts/claims/party names 100% 保真；
- 同一历史从持久化状态恢复后得到同一 sub_stage；
- 100 个并发双会话测试无状态串案；
- LLM 失败不会生成 0.5 的“有效评分”；
- API semantic success 与 HTTP success 分开统计。

## Phase 1：证据化裁判（3-7 天）

1. Fact/Evidence Ledger；
2. 争点分解（IssueGraph）；
3. ProgressiveRAG 接入主编排器；
4. 法条白名单与数据库回查；
5. per-issue IRAC 输出；
6. 诉请逐项 disposition；
7. 事实、法条、金额、结论四类 validator；
8. 校验不通过时只重写失败部分，不重跑整个庭审。

**验收：**

- 法条引用有效率 100%；
- 每项诉请都有裁判结论，覆盖率 ≥95%；
- 判决采纳事实全部能回指至少一个 evidence/source；
- 人名、金额、时间等关键实体前后一致率 ≥98%；
- 无依据事实幻觉率 ≤5%。

## Phase 2：自适应推理与审查（3-5 天）

1. 将 DualMode 从“长度信息增益”改成风险/不确定性路由；
2. 多法官改为 generator + evidence critic + citation verifier + consistency critic；
3. generator 与 evaluator 模型分离；
4. 多 critic 只返回结构化缺陷列表；
5. revision 模块局部修补，而不是整篇重写。

**验收：**

- 简单案件 fast mode 占比 ≥60%，准确率不低于 slow baseline 2 个百分点；
- 高风险案件 validator 失败率比当前下降 ≥40%；
- critic 的缺陷定位可复现率 ≥85%；
- 平均 LLM 调用量不增加超过 20%。

## Phase 3：重做实验评估（1-2 周）

1. 分离 train/calibration/test 案件；
2. 所有 payoff/equilibrium 只在 train/calibration 构建；
3. 在未参与建矩阵的 test 案件上比较策略预测；
4. API 与 fallback 分开报告，主结果只接受 strict API 数据；
5. 使用 ≥100 案、≥5 seeds；按案件 cluster bootstrap；
6. 指标分层：法律结论、事实忠实、法条有效、证据覆盖、程序合规、策略预测；
7. 明确预注册 evolution_method/payoff_weights/model/prompt version；
8. 将“SPNE/NE accuracy”更名为“strategy prediction agreement”。

**主结论门槛：**

- API semantic success ≥95%；
- 95% CI 不跨 0；
- 多 seed 方向一致；
- 替换 generator/evaluator 模型后结论不反转；
- fallback 数据不进入主结果。

---

## 6. 推荐的第一迭代任务包

建议下一轮只做以下四项，不同时改 prompt、模型和博弈参数：

1. `CaseNormalizer + CanonicalCaseBundle`；
2. `ReasoningState` 持久化，去除 CI 每轮重置/不完整回放；
3. `ReasoningResult.status/degraded/errors/provenance` 全链传播；
4. 增加 15-20 个离线契约测试：字段保真、状态恢复、并发隔离、LLM 失败门控、证据重复处理。

完成后再接 Fact/Evidence Ledger。这样能把推理优化建立在确定的数据和状态上，避免继续通过 prompt 补丁掩盖底层错误。

---

## 7. 当前代码的可复用优势

不建议推倒重来，以下组件可直接保留：

- StateMachine 的主/子阶段设计和合规报告；
- StructuredJudgment 的 facts/issues/laws/liability/conclusion 骨架；
- BM25 + FAISS + RRF 的检索底座；
- ProgressiveRAG 的阶段证据池接口；
- LiabilityChain 的输出结构（改为 verifier 输入，而非自证评分）；
- 流式输出、路由拆分、Reasoning 执行测试；
- 已恢复的交替策略更新语义；
- 已修复的 CI 判决终止召回。

---

## 8. 最终判断

LexGentium 目前是“功能模块完整、推理契约不够严格”的系统。当前模型已经足以完成高质量法律文本生成；继续换更强模型只会提高成本，不能解决字段丢失、状态漂移、证据不可追踪、法条未验证和实验混合 fallback 的问题。

正确的优化顺序是：

1. **数据正确**；
2. **状态稳定**；
3. **证据可追踪**；
4. **法条可验证**；
5. **失败可见**；
6. **最后才是 prompt、模型与博弈参数调优**。

只要 Phase 0 和 Phase 1 完成，LexGentium 的提升会比继续堆 Agent 或 CoT 更真实，也更容易形成可发表、可复现的科研证据。

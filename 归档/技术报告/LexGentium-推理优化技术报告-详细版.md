# LexGentium 推理优化技术报告（详细版）

> 版本：v2.0（2026-09-12）  
> 前置版本：v1（2026-09-10，`归档/技术报告/LEXGENTIUM_REASONING_OPTIMIZATION_REPORT.md`，已随 PR #2 提交后从 `docs/` 挪出）  
> 评估对象：`github.com/Hanyuan9766/LexGentium`（原 legalflow），main + PR #2 分支 `feat/lexgentium-optimizations`  
> 审计方法：逐文件静态审计（带行号引用）、离线契约测试（26 用例）、三批真实实验对比、运行时日志分析  
> 基本立场：不把 LLM 输出长度、自评分数或"HTTP 200"等同于法律推理质量

---

## 目录

1. 执行摘要
2. 系统推理架构现状（调用链全景）
3. 实验证据边界与统计功效分析
4. 逐模块问题审计（P0/P1 八项，含代码证据与修复方案）
5. 目标推理架构设计
6. 实施进度记录（Phase 0 三批，已全部落地）
7. 分阶段实施路线图（任务分解、依赖、工时）
8. 性能与调用量成本分析
9. 风险登记册
10. 附录：验收测试清单、术语表、相关文件索引

---

## 1. 执行摘要

LexGentium 是面向民事诉讼场景的多智能体模拟法庭：CD（起诉状）→ DD（答辩状）→ CI（庭审+判决）三阶段管道，叠加庭审状态机、法条混合检索（BM25+FAISS+RRF+Rerank）、结构化判决、Behavior-Liability-Statute 责任链、快/慢双模式推理、五阶段调解、三法官聚合、TKI 策略演化博弈（NE/SPNE/ESS）和多层评估框架。约 2.65 万行 Python + 6.8 千行 TypeScript。

**核心判断：系统的推理骨架完整且有多篇论文方法支撑，当前瓶颈不在"模型不够聪明"，而在推理的输入契约、状态管理和输出校验三个底座。** 模型每次"思考"所依赖的案件要素（案号/当事人/诉请/客观事实）在进入 CI 前会被字段错位静默丢弃；庭审状态每轮被重建并用关键词启发式重放；LLM 失败被吞成 `{}` 后以 0.5 的"有效评分"继续流转；实验把真实 API 结果与伪随机 fallback 混入同一收益矩阵。

**Phase 0（推理底座修复）已全部落地**：数据契约规范化、推理状态持久化与全链路传递、会话级并发隔离、判决三级校验、法条回查（Verified RAG 最小版）、推理元数据向前端传播。测试 26/26 通过、tsc 零错误，改动已作为 PR #2 提交（16 文件）。

**下一步最高优先级**：Phase 1 证据化裁判（Fact/Evidence Ledger + 逐争点 IRAC + 法条白名单），以及严格模式下的正式实验重跑。不建议继续增加 CoT 提示词或 Agent 数量。

---

## 2. 系统推理架构现状（调用链全景）

### 2.1 Web 服务路径（日常使用入口）

```text
浏览器
  → Next.js route handler（app/api/*，16 个，纯代理，SSE 流式透传）
    → FastAPI api_server.py（62 行薄壳：鉴权中间件 + 路由装配）
      → api/routers/conversation.py 等十个 router
        → api/state.py（运行时装配 + ReasoningState 存取 + run_agent_turn）
          → api_runtime.create_runtime()（LLMClient + CD/DD/CI/Sim 四 Agent + 编排器 + 博弈/调解引擎）
            → CIAgent.process_turn(dialog_history, case_id, input_json, reasoning_state)
              ├── _build_case_info → normalize_case_payload（CanonicalCaseBundle）★新增
              ├── 状态恢复（reasoning_state）或启发式回放 ★新增恢复路径
              ├── _step → _analyze_state_with_llm（书记员 JSON）→ _update_phase → try_transition
              ├── _next_instruction（模板或 LLM 指令）
              └── JUDGMENT 态 → _make_judgment
                    ├── 检索：LawRetriever.search（BM25+向量+RRF+Rerank，单 query）
                    ├── judgment_chain（结构化判决 JSON）
                    ├── validate_judgment（三级校验）★新增
                    └── verify_citations（法条库回查）★新增
```

### 2.2 博弈实验路径（科研入口）

```text
run_two_step_small_sample.py
  → 分层抽样（stratified_sample, seed 固定）
  → 每轮：随机选 ≤3 案走 API（/game/create + /game/{id}/round → run_game_round）
      → FullCaseOrchestrator.run_full_case（CD→DD→CI 三阶段，per-party SimAgent 策略注入）
        → evaluate_judgment（LLM 评分 + 诉请覆盖规则分混合）
        → NashEquilibriumTracker.record_round → analyze（均衡快照）
      → 其余案件 score_from_case（伪随机本地分数）
  → 末轮策略 vs ExtensiveFormGame 求解的 NE/SPNE → "策略预测一致率"（现名 spne_acc/ne_acc）
  → Step2：复制者动态 + ESS 验证
```

### 2.3 关键文件索引

| 文件 | 行数 | 职责 |
|---|---:|---|
| `api_server.py` | 62 | 薄壳：中间件、路由装配、启动 |
| `api/state.py` | ~600 | 共享状态、ReasoningState 存取、run_agent_turn |
| `api/routers/*.py`（10 个） | ~1900 | 65 条路由按功能域拆分 |
| `agents/ci_agent.py` | ~1580 | 庭审法官：状态推进、书记员分析、判决生成 |
| `core/game_engine.py` | ~800 | 博弈轮次、评分、策略进化、反事实 |
| `core/law_retriever.py` | ~330 | 双路检索 + RRF + Rerank + 单例工厂 |
| `core/case_bundle.py` ★ | ~170 | 案件数据规范化契约 |
| `core/judgment_validator.py` ★ | ~150 | 判决三级校验 + 法条回查 |
| `core/reasoning_state.py` ★ | ~30 | 推理状态提取（api/core 共用） |
| `core/state_machine.py` | ~530 | 庭审状态机 + 序列化 ★ + 合规打分 |
| `evaluation/run_two_step_small_sample.py` | ~870 | SPNE/NE 对比实验 |

★ = 本轮推理优化新增/重点修改

---

## 3. 实验证据边界与统计功效分析

### 3.1 三批次实测对比

| 批次 | 时间 | API 成功 | evolution_method | 权重 w/r/e | SPNE | NE | Δ | p 值 | 判定 |
|---|---|---:|---|---|---:|---:|---:|---:|---|
| 旧批次 20260419_231633 | 4 月（Windows） | **0/24** | fictitious_play | .55/.25/.20 | 0.70 | 0.60 | +0.10 | 1.0 | 全 fallback，无真 API 证据 |
| 第一批 20260910_092525 | 09-10 | **17/18** | best_response（默认值误用） | .50/.25/.25（默认值） | 0.30 | 0.70 | -0.40 | 0.127 | 配置错位，与旧批不可比 |
| v2 对齐批 20260910_112630 | 09-10 | **1/18** | fictitious_play | .55/.25/.20 | 0.40 | 0.30 | +0.10 | 1.0 | 遭遇 402/502 风暴，17/18 fallback |

### 3.2 失败模式分解（v2 运行日志）

| 错误类别 | 日志命中 | 说明 |
|---|---:|---|
| LLM 402（额度） | 50 | glm-private 套餐耗尽 |
| HTTP 402 | 50 | 同上（requests 路径） |
| HTTP 502 | 18 | gateway 中转过载 |
| LLM/HTTP 400 | 各 2 | 参数问题（少量） |

结论：**三批实验中没有任何一批同时满足"真实 API 高成功率 + 与对照配置一致"**。当前 SPNE>NE（或反转）的所有数字都不能作为方法有效性的证据。

### 3.3 统计功效：n=10 检测不了目标效应

当前指标是配对二分类（同一案件上 SPNE 命中 vs NE 命中）。要检测 Δ=0.1 的配对差异（基线命中率 ~0.5，双侧 α=0.05，功效 0.8），经典配对设计约需 **n≈100-200 个有效案件**；n=10 时即使观察到 Δ=0.4，95% CI 也宽达 ±0.4 以上（v2 实测 CI [-0.3, 0.5] 恰好印证）。此外探索项（eps 退火 + 8%/92% 确定性扰动，`run_two_step_small_sample.py:320-330`）会主动制造偏离均衡的策略，进一步稀释信号。

**实验重做要求**（Phase 3 详述）：≥100 案、≥5 seeds、train/calibration/test 分离、strict API 语义成功率 ≥95%、按案件 cluster bootstrap。

### 3.4 指命名更正建议

`spne_acc/ne_acc` 实测的是"末轮观察策略与同一收益矩阵推导出的均衡预测的一致率"（in-sample），建议更名为 `spne_strategy_agreement/ne_strategy_agreement`，并在所有图表注明"非法律判决准确率"。

---

## 4. 逐模块问题审计

以下每项按【现状 → 代码证据 → 影响 → 修复 → 验收】组织。标注 ✅ 的为已在本轮修复。

### 4.1 P0 ✅ 案件数据契约错位

**现状**：实验与编排器传入新契约字段，CIAgent 读取旧契约字段。

**代码证据**：
- 实验侧 `_build_case_info`（`run_two_step_small_sample.py:240-248`）提供 `case_id/cause/case_description/plaintiff_claims/plaintiff_name/defendant_name`（实测数据集首行 keys：`['case_description','case_id','cause','defendant_name','plaintiff_claims','plaintiff_name','sampled_category']`）；
- CIAgent `_build_case_info`（修复前 `ci_agent.py:314-330`）读取 `id/plaintiff_info/defendant_info/case_type/claim_description/claim/third_party_findings`；
- 判决提示词 `_get_judgment_prompt`（`ci_agent.py:1067-1160`）直接引用 `self.case_info.claim_description/third_party_findings`。

**影响**：判决生成的"案件基本信息/诉讼请求/客观事实"三块全部空置或占位；检索 query 退化为空/摘要；当事人姓名退化为"原告/被告"字面量——提示词里"被告确认为『被告』"这类自我矛盾。

**修复（已落地）**：新增 `core/case_bundle.py` 的 `normalize_case_payload()`，在 CI 边界一次完成新旧映射，产出 `CanonicalCaseBundle`（含 warnings 与 `validation_errors()`）；`_build_case_info` 改走 bundle，并把 `case_warnings` 记入 agent 状态与 `_report`。

**验收（已通过）**：真实数据集首行样本归一化后 case_id/cause/双方姓名/两条诉请/事实全保真（`test_reasoning_contracts.py::test_real_dataset_sample_passes_contract`）；旧契约字段兼容；缺字段显式报告。

### 4.2 P0 ✅ CI 状态每轮重置与回放漂移

**代码证据**（修复前）：
- `process_turn`（`ci_agent.py:115-133`）每次新建 StateMachine、清空 dialogue/evidences/extracted；
- 回放仅对非 Judge 消息调 `_fast_update_state`，而法官生成"独任庭构成/简易程序"时写入的 `court_composition_announced/procedure_announced` 标志在回放中永久丢失；
- 开庭回放误写不存在的 `p["absence_acknowledged"]`，状态机检查的是 `absence_asked_mask`（`state_machine.py:59,120`）——"缺席审理后果告知"永远无法通过；
- 重复证据被直接标记"举证完毕"（`ci_agent.py:1434-1443`）；
- API 层共享单例 CIAgent（并发覆盖窗口）。

**修复（已落地）**：
- `StateMachine.to_dict/from_dict/apply_dict`（`state_machine.py`）；
- `process_turn(reasoning_state=)`：传入持久化状态直接恢复（dialogue/evidences/extracted/judgment/name_confirmed 全量），恢复失败降级回放路径；
- 回放修复：`absence_asked_mask` 正确写入；法官消息回放恢复庭构成/程序标志；
- orchestrator `run_stage_ci` 跨轮维护快照（`core/reasoning_state.py` 提取，`_agent_turn` 透传）；
- conversation 双端点接入存取（`input_json["_reasoning_state"]`，零 schema 变更）；
- 会话级隔离 `new_session_ci_agent()`（chains 轻构造、law_retriever 单例共享），两端点改用独立实例。

**验收（已通过）**：状态机往返保真；恢复后继续推进不误跳阶段；编排器第二轮回合收到非空快照；工厂两次调用实例独立而检索器共享；离线治理测试全过。

**遗留**：orchestrator 路径的 ReasoningState 尚未随 game session 落库（进程内快照，重启后仍靠回放路径兜底）。

### 4.3 P0 ◐ 失败被吞成正常推理（部分完成）

**代码证据**：`chat_json`（`llm_client.py:253-339`）非 400 错误返回 `{}`；`evaluate_judgment`（`game_engine.py:359-365`）缺字段默认 0.5；实验按 HTTP 判 api_success。

**已落地**：`core/judgment_validator.py` 三级校验（ok/degraded/failed + 缺失清单），CI 判决后调用并记录 `judgment_status`；`reasoning_meta`（judgment_status/citation_report/case_warnings）随响应与 SSE final 事件下发；schema 与前端类型同步。

**待办**：
- `chat_json` 返回信封化（status/errors），而非调用方各自判空；
- `evaluate_judgment` 在 judgment_status != ok 时不产出"有效分数"；
- 实验 strict 模式（真实语义成功率 <95% 判批次 invalid）。

### 4.4 P1 证据推理以文本为中心

**代码证据**：证据抽取靠关键词前置过滤（`ci_agent.py:511-514`：出现"证据/凭证/合同/微信聊天/录音"才触发 LLM 抽取）——不出现关键词的证据（如口头承认收款）被漏掉；重复证据即标"举证完毕"（`ci_agent.py:1434-1443`）；调查阶段完成条件要求双方 `no_more_evidence`（`state_machine.py:123-133`），配合上一条会提前终止举证。

**修复方向（Phase 1）**：Fact-Evidence Ledger——每条事实主张绑定主张方/争议状态/举证责任/支持证据/反证/可信度/裁判采用；判决"本院查明"逐条引用 ledger source id；重复提交只做去重提示，不改举证状态；举证完毕只能由当事人明确意思表示触发。

### 4.5 P1 ◐ RAG 缺真实性验证（最小版已落地）

**代码证据**：主判决单 query（`ci_agent.py:1094-1115`，query 取 findings/summary/claims 前 1000 字）；ProgressiveRAG 四阶段接口完整但未接主链（`progressive_rag.py:180-219`，仅 `/game/{id}/progressive-rag` 等独立端点调用）；提示词"参考法条（仅供参考，请优先适用）"语义冲突（`ci_agent.py:1112-1115`）；生成法条无回查。

**已落地**：`verify_citations`（`judgment_validator.py`）——解析书名号法律名 + 条号（支持中文数字"第六百七十六条"→676），与 legal_articles.db 的 `(law_name, article_number)` 集合比对，未命中标 `verified:false` 并进 unverified 清单；CI 判决流接入，结果进 `_report` 与 reasoning_meta。

**待办（Phase 1）**：按争点拆分多 query；只允许引用库内法条（白名单）；无命中输出 `insufficient_legal_basis`；ProgressiveRAG 接入主编排；法条库扩容或明确"135 条实验精选库"边界声明。

### 4.6 P1 Dual-mode 信息增益偏好长文本

**代码证据**：启发式 = 0.2×长度比 + 0.3×法条增量 + 0.3×分点数 + 0.2×术语频率（`dual_mode_reasoning.py:93-109`）；LLM 评分同模型自评（`:159-176`，且提示词含"结论一致性"维度但实现只取 4 项均值、`overall_quality` 与 `conclusion_consistency` 字段被丢弃）；>0.3 即推荐 slow（`:205`）。

**修复方向（Phase 2）**：风险路由（证据冲突/多请求权基础/检索冲突/快慢不一致/多法官分歧/高金额弱势方时效 → slow）；slow 胜出标准改为引用有效+事实一致+诉请逐项处理+validator 通过；评估者与生成者模型分离；`conclusion_consistency` 一票否决（结论矛盾时信息增益归零）。

### 4.7 P1 Multi-judge 非独立、聚合粗糙

**代码证据**：默认 `additional_llms=[]`（`multi_judge.py:158-165`），三法官 = 同模型 × 3 persona（standard/pragmatic/protective，`:74-78`）× 温度 0.1/0.2/0.3；agreement 为"支持/驳回"关键词布尔比对（`:127-152`），无法表达"部分支持诉请 1、驳回诉请 2"；meta_judge 失败静默回落多数票（`:330` 附近）；`_classify_stance` 关键词法同源（`:237-254`）。

**修复方向（Phase 2）**：职责化 critics（事实审查/法条核验/一致性检查）+ 按claim_id 的 disposition 比对；接入不同 provider 模型实现真正异构；dissenting_opinions 结构化（当前恒为空 list，meta_judge 路径从未填充）。

### 4.8 P1 同模型生成+评分闭环

**代码证据**：`evaluate_judgment`（`game_engine.py:337-380`）用同一 llm 评分自己生成的判决，分数直接进收益矩阵驱动策略进化；字面诉请覆盖规则取诉请前 40 字做子串匹配（`:314-331`），奖励判决复制诉请原文。

**修复方向（Phase 2/3）**：generator/evaluator 模型分离；结构化 disposition 解析后按 claim 评分；披露 evaluator 元数据；关键基准人工双盲。

---

## 5. 目标推理架构设计

### 5.1 组件与数据流

```text
API Input（任意旧/新字段）
  ↓ ① CaseNormalizer（normalize_case_payload）
CanonicalCaseBundle ──校验失败→ 400 + validation_errors
  ↓ ② SessionCIContext（reasoning_state 恢复或初始化）
StateMachine + FactLedger + EvidenceLedger
  ↓ ③ 事件抽取（LLM 提议 → 规则验证）
状态推进（每事件一个 reducer，低置信不推动）
  ↓ ④ Issue Decomposer（从 Ledger 生成 2-5 争点）
  ↓ ⑤ Verified RAG（每争点独立 query → 白名单法条）
  ↓ ⑥ IRAC Reasoner（每争点：Issue-Rule-Application-Conclusion）
  ↓ ⑦ Disposition Table（逐诉请 support/reject/partial + 金额）
  ↓ ⑧ Validators（schema/citation/fact/amount/logic 四类）
  ↓ ⑨ Risk Router（低风险→输出；高风险→Critics→局部修订→⑧ 复验）
StructuredJudgment {facts,issues,laws,analysis,dispositions,validation,provenance,confidence,status}
  ↓
Renderer（判决书文本；reasoning_meta 附带下发）
```

### 5.2 核心接口草案

```python
# core/case_bundle.py（已落地）
normalize_case_payload(payload: dict) -> CanonicalCaseBundle

# core/reasoning_state.py（已落地）
extract_ci_reasoning_state(ci_agent) -> dict

# Phase 1 新增
class FactLedger:
    add_claim(claim_id, text, party, burden) -> None
    attach_evidence(claim_id, evidence_id, stance) -> None
    adjudicate(claim_id, status, reasoning_ref) -> None      # 只能由判决校验器调用
    unresolved_disputed() -> list                            # 无证据争议事实清单

class IssueGraph:
    decompose(fact_ledger) -> list[Issue]                    # LLM 提议 + 去重
    attach_laws(issue_id, verified_laws) -> None

def validate_judgment(j) -> tuple[status, missing]            # 已落地
def verify_citations(j, law_db_path) -> CitationReport        # 已落地
def verify_facts(j, fact_ledger) -> FactReport                # Phase 1
def verify_amounts(j, claims) -> AmountReport                 # Phase 1
```

### 5.3 输出契约（StructuredJudgment v2）

```json
{
  "facts":      [{"id":"F1","text":"…","sources":["E1"],"status":"adopted|disputed"}],
  "issues":     [{"id":"I1","question":"借款是否实际交付","fact_ids":["F1"]}],
  "laws":       [{"law_id":81,"ref":"《民法典》第676条","verified":true,"issue_ids":["I2"]}],
  "analysis":   [{"issue_id":"I1","rule_ids":[81],"fact_ids":["F1"],"application":"…"}],
  "dispositions":[{"claim_id":"C1","result":"partial","amount":80000,"reason_issue_ids":["I1"]}],
  "validation": {"schema":true,"citations":true,"facts":true,"amounts":true,"logic":true},
  "provenance": {"model":"deepseek-v4-flash","prompt_version":"judg-v3","retrieval_ids":["R1","R2"]},
  "status":     "ok",
  "confidence": 0.83
}
```

---

## 6. 实施进度记录（Phase 0 三批全部落地）

### 第一批（数据契约 + 校验器）

- `core/case_bundle.py`：`normalize_case_payload` 新旧映射、warnings、`validation_errors()`
- CI `_build_case_info` 接入；真实数据集样本契约测试通过
- `core/judgment_validator.py`：`validate_judgment` 三级校验

### 第二批（状态持久化 + 回放修复）

- StateMachine `to_dict/from_dict/apply_dict`
- 回放修复：`absence_asked_mask`（原误写 `absence_acknowledged`）；法官程序标志回放
- `process_turn(reasoning_state=)` 恢复路径；`_reset_replay_state` 显式化
- orchestrator `run_stage_ci` 跨轮快照传递；`_agent_turn` 透传
- `name_confirmed_by_dialogue` 序列化/恢复

### 第三批（隔离 + 传播 + 环境）

- `new_session_ci_agent()` 工厂；send/stream 端点独立实例；`run_agent_turn(ci_agent=)` 注入
- `reasoning_meta`（judgment_status/citation_report/case_warnings）随响应与 SSE final 下发；`api_schemas.py` + `lib/conversation-types.ts` 同步
- Verified RAG `verify_citations`（中文数字条号）接入 CI 判决流
- 环境修复：Xcode CLT python3 断链 → 基于 CommandLineTools 3.9.6 + requirements.lock 重建 `.venv-test`

**测试基线：26/26 通过（`tests/test_reasoning_contracts.py` 15 + `test_reasoning_execution.py` 4 + 原有 7）；tsc 零错误；next build 通过。**

### 执行语义修正（同批）

- 快/慢双模式：修复"submit 后立即 result"的假并行（现先同时提交两个 future 再取结果），同步屏障测试可复现旧缺陷
- 策略进化：`evolve_both_strategies` 恢复原告→被告顺序执行（best_response 读对方当前策略、fictitious_play 读双方历史，并行引入调度不确定性）；参数化测试验证调用顺序与调用线程

---

## 7. 分阶段实施路线图（细化）

### Phase 0 — 推理底座 ✅ 已完成（实际 3 天）

| # | 任务 | 状态 |
|---|---|---|
| 0.1 | CanonicalCaseBundle + 兼容映射 | ✅ |
| 0.2 | CI 字段契约修复 + 样本级测试 | ✅ |
| 0.3 | ReasoningState 序列化 + 全链路传递（conversation + orchestrator） | ✅ |
| 0.4 | 回放 bug 修复（absence 字段、法官标志、name_confirmed） | ✅ |
| 0.5 | JudgmentValidator 三级校验 | ✅ |
| 0.6 | Verified RAG 法条回查最小版 | ✅ |
| 0.7 | 会话级并发隔离 | ✅ |
| 0.8 | reasoning_meta 传播（schema + 前端类型 + SSE） | ✅ |
| 0.9 | 执行语义修正（真并行/顺序进化）+ 回归测试 | ✅ |
| 0.10 | 实验 strict 模式（批次有效性门控） | ⏳ 转 Phase 3 |

### Phase 1 — 证据化裁判（3-7 天）

| # | 任务 | 依赖 |
|---|---|---|
| 1.1 | FactLedger + EvidenceLedger（数据结构 + reducer） | 0.3 |
| 1.2 | 书记员事件化改造（LLM 提议事件 → 规则验证） | 1.1 |
| 1.3 | IssueGraph 争点分解 | 1.1 |
| 1.4 | ProgressiveRAG 接入 run_full_case 主链 | 1.3 |
| 1.5 | 法条白名单（只许引用库内法条）+ 无命中输出 insufficient_legal_basis | 0.6 |
| 1.6 | per-issue IRAC 生成 + 逐诉请 Disposition Table | 1.3-1.5 |
| 1.7 | 四类 validator：fact（回指 ledger）/citation/amount/logic | 1.6 |
| 1.8 | 局部修订器（只重写校验失败部分） | 1.7 |

**验收**：法条引用有效率 100%；诉请 disposition 覆盖率 ≥95%；"本院查明"事实 100% 可回指 ledger source；实体（人名/金额/日期）一致率 ≥98%；无依据事实幻觉率 ≤5%。

### Phase 2 — 自适应推理与审查（3-5 天）

任务与验收见 v1 报告 §5 Phase 2，补充：`conclusion_consistency` 一票否决；dissenting_opinions 结构化；meta_judge 失败回落需记录降级事件。

### Phase 3 — 实验重做（1-2 周）

1. 数据集三分：train/calibration/test（按案件切，禁止跨集）；
2. 收益矩阵/均衡只在 train+calibration 构建；
3. test 案件上评估策略预测与法律指标；
4. strict 语义成功率门控（<95% 批次 invalid）；
5. n≥100、seeds≥5、cluster bootstrap（按案件聚类）；
6. 指标分层：法律结论正确性（对 ground truth）/事实忠实/法条有效/证据覆盖/程序合规/策略预测一致率；
7. 预注册 evolution_method、payoff_weights、model、prompt_version；
8. 指标更名 strategy prediction agreement；
9. 对照维度预注册：SPNE vs NE × evolution_method × 模型（第一批的"反转"现象值得作为独立研究点）。

---

## 8. 性能与调用量成本分析

### 8.1 单次完整案件（game round）LLM 调用分解

| 阶段 | 调用构成 | 修复前实测 | 修复后预期 |
|---|---|---:|---:|
| CD 对话 | 律师-当事人多轮，每轮 1 次 | ~10-20 | ~10-20 |
| DD 对话 | 同上 | ~10-20 | ~10-20 |
| CI 庭审 | 法官指令 + 当事人发言 × 轮数 + 书记员分析 | 打满 60 轮 → ~120+ | 判决召回修复后 ~20-30 轮 → ~40-60 |
| CI 策略反思 | SimAgent 每 4 轮 1 次（降频后） | ~15 | ~4 |
| 评分 | 判决评分 1 次 | 1 | 1 |
| **合计** | | **~145-158（实测 25 分钟/terra，6 分钟/deepseek-flash）** | **预计 ~60-90** |

### 8.2 实验批次成本（10 案 × 6 轮 × 3 API 案件/轮 = 180 API 案件）

- 修复前（庭审打满）：~180 × 150 调用 ≈ 2.7 万次 LLM 调用
- 修复后：~180 × 70 ≈ 1.26 万次
- glm deepseek-v4-flash 单次 1.3-3.6s：批次墙钟约 1.5-4 小时（与 v2 实测同量级）
- Phase 1 的 per-issue 检索会增加每案 4-12 次检索（BM25 本地毫秒级；embedding 走 API 时 +4-12 次）——可接受

### 8.3 已实现性能项（实测）

| 项 | 数据 |
|---|---|
| 多法官并行 | 3 法官 ~100s → 24.4s |
| 流式首字 | 非流式等待 3.6s → 首字 1.26s |
| 单轮对话 | 30s（思考模型）→ 3.6s（deepseek-v4-flash） |
| BM25 单例 | 冷启动 -2.7s |
| 重试链 | 故障最坏 25 次 → 10 次 |

---

## 9. 风险登记册

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| R1 | flash 级模型法律推理深度不足，影响 SPNE/NE 实验信号 | 高 | Phase 3 用双模型对照；实验指标与生成质量分层评估 |
| R2 | 法条库仅 135 条，Verified RAG 会高频"无命中" | 高 | 扩容法条库或按 dataset 案由声明覆盖边界；insufficient_legal_basis 是正确行为而非失败 |
| R3 | glm-private 额度按日波动（402 复发） | 中 | cron 探测自动化已验证；strict 模式避免半降级数据；备胎 gateway 需解决 503/延迟 |
| R4 | ReasoningState schema 演进破坏旧会话恢复 | 中 | to_dict 带 version 字段（已做）；from_dict 对缺失键走默认值（已做） |
| R5 | Phase 1 改造期间 PR #2 与主链漂移 | 中 | 每完成一个任务包即追加 commit（curl 跟随重定向路径已验证） |
| R6 | 提示词里"仅供参考，请优先适用"类自相矛盾指令残留 | 中 | Phase 1 prompt 版本化重写，全量评审 |
| R7 | 实验脚本在 Python 3.10+ 与 3.9 行为差异 | 低 | 已修 PEP 604；CI 里加 3.9/3.11 双版本跑测 |

---

## 10. 附录

### 10.1 验收测试清单（现有 26 个）

- `tests/test_reasoning_contracts.py`（15）：实验字段保真 / 旧契约兼容 / 缺字段告警 / 真实样本契约 / 判决三级校验（完整、空、部分）/ 状态机往返 / 恢复后推进 / legacy 恢复 / 法条回查命中与未命中 / 中文数字 / ReasoningState 经 record 往返 / orchestrator 跨轮传递 / 工厂隔离
- `tests/test_reasoning_execution.py`（4）：双模式真并发屏障 / 三种进化方法顺序与调用线程
- `tests/test_offline_governance.py`（3）+ `test_law_retrieval/test_new_db/test_faiss/test_submission_api`（4）：离线治理与存储

### 10.2 术语表

| 术语 | 含义 |
|---|---|
| CanonicalCaseBundle | 规范化案件数据契约（进入推理的唯一可信案件来源） |
| ReasoningState | CIAgent 推理过程可序列化快照（状态机+对话+证据+判决+标志） |
| degraded | HTTP 成功但语义不完整（缺字段/降级路径产出），不得计入有效样本 |
| Fact-Evidence Ledger | 事实主张与证据的结构化台账（Phase 1 核心） |
| strategy prediction agreement | 原 spne_acc/ne_acc 的更名建议（策略预测一致率，非法律准确率） |
| strict 模式 | 语义成功率 <95% 时整批实验判无效的门控 |

### 10.3 相关交付物索引

| 交付物 | 位置 |
|---|---|
| 本报告 | `workspace/default/LexGentium-推理优化技术报告-详细版.md` |
| 精简版（随 PR #2） | `归档/技术报告/LEXGENTIUM_REASONING_OPTIMIZATION_REPORT.md` |
| PR #1（性能/安全/重构/改名，已合并） | `Hanyuan9766/LexGentium#1` |
| PR #2（推理优化 Phase 0，16 文件，待合并） | `Hanyuan9766/LexGentium#2` |
| 实验结果 | `mock_court_system/evaluation/results/two_step_small_sample_20260910_*` |
| 初版技术评估报告 | `workspace/default/legalflow-技术报告.md` |

---

*报告完。核心一句话：先让推理"吃对数据、记住状态、验过输出"，再谈让模型"想得更好"。*

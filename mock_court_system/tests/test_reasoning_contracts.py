"""推理契约测试：数据保真、状态恢复、判决校验、并发隔离。"""
import sys, os, json
sys.path.insert(0, os.getcwd())

import pytest

from core.case_bundle import normalize_case_payload
from core.fact_ledger import FactLedger
from core.judgment_validator import validate_judgment
from core.state_machine import StateMachine
from core.schemas import CourtState


# ---------- 数据契约 ----------

def test_experiment_payload_fields_survive_normalization():
    """实验数据契约（case_id/case_description/plaintiff_name...）必须完整保留。"""
    payload = {
        "case_id": "CASE-0222",
        "cause": "金融借款合同纠纷",
        "case_description": "被告陈秀雯向原告借款700万元，逾期未还。",
        "plaintiff_claims": ["归还本金700万元", "支付利息1624373.33元"],
        "plaintiff_name": "梁磊",
        "defendant_name": "高文涛",
    }
    b = normalize_case_payload(payload)
    assert b.case_id == "CASE-0222"
    assert b.cause == "金融借款合同纠纷"
    assert b.plaintiff.name == "梁磊"
    assert b.defendant.name == "高文涛"
    assert [c.text for c in b.claims] == ["归还本金700万元", "支付利息1624373.33元"]
    assert "陈秀雯" in b.case_facts
    assert b.validation_errors() == []


def test_legacy_payload_fields_still_supported():
    """旧契约（id/claim_description/plaintiff_info）兼容映射。"""
    payload = {
        "id": "LEGACY-1",
        "case_type": "民间借贷纠纷",
        "claim_description": "请求返还借款本金10万元",
        "plaintiff_info": {"name": "张三"},
        "defendant_info": {"name": "李四"},
    }
    b = normalize_case_payload(payload)
    assert b.case_id == "LEGACY-1"
    assert b.cause == "民间借贷纠纷"
    assert b.plaintiff.name == "张三"
    assert b.defendant.name == "李四"
    assert b.claims_text == "请求返还借款本金10万元"
    assert b.validation_errors() == ["missing case_description/third_party_findings"]


def test_missing_critical_fields_are_reported_not_silently_defaulted():
    b = normalize_case_payload({"case_id": "X"})
    errs = b.validation_errors()
    assert any("claims" in e for e in errs)
    assert any("case_description" in e for e in errs)
    assert any("name missing" in w for w in b.warnings)


def test_real_dataset_sample_passes_contract():
    """真实数据集首行样本必须通过完整契约。"""
    import json
    row = json.loads(open("data/dataset_1000/small_sample_100_three_causes.jsonl").readline())
    b = normalize_case_payload(row)
    assert b.case_id == row["case_id"]
    assert b.plaintiff.name == row["plaintiff_name"]
    assert b.defendant.name == row["defendant_name"]
    assert len(b.claims) == len(row["plaintiff_claims"])
    assert b.cause == row["cause"]
    assert b.validation_errors() == []


# ---------- 判决校验 ----------

def test_complete_judgment_is_ok():
    j = {
        "fact_finding": "本院查明：被告借款10万元未还。",
        "dispute_focus": ["借款是否实际交付"],
        "legal_analysis": "本院认为：借贷关系成立。",
        "judgment_result": "判决如下：被告偿还本金10万元。",
        "applicable_laws": [{"law": "民法典第676条"}],
        "liability_mapping": {"plaintiff_claims": ["还款"], "court_adoption": ["支持"]},
    }
    assert validate_judgment(j)[0] == "ok"


def test_empty_or_non_dict_judgment_is_failed():
    assert validate_judgment({})[0] == "failed"
    assert validate_judgment(None)[0] == "failed"
    assert validate_judgment("文本")[0] == "failed"


def test_partial_judgment_is_degraded_with_missing_list():
    status, missing = validate_judgment({
        "fact_finding": "本院查明：事实清楚。",
        "judgment_result": "判决如下：驳回。",
    })
    assert status == "degraded"
    assert "dispute_focus" in missing
    assert "legal_analysis" in missing


# ---------- 状态机序列化 ----------

def _advance_state_machine(sm: StateMachine):
    p = sm.opening_phase
    p["plaintiff_verified"] = True
    p["defendant_verified"] = True
    p["court_composition_announced"] = True
    p["procedure_announced"] = True
    p["rights_informed_mask"] = {"plaintiff": True, "defendant": True}
    p["recusal_asked_mask"] = {"plaintiff": True, "defendant": True}
    p["absence_asked_mask"] = {"plaintiff": True, "defendant": True}
    sm.try_transition()


def test_state_machine_roundtrip_preserves_phase_state():
    sm = StateMachine()
    _advance_state_machine(sm)
    assert sm.current_state == CourtState.INVESTIGATION

    restored = StateMachine.from_dict(sm.to_dict())
    assert restored.current_state == CourtState.INVESTIGATION
    assert restored.opening_phase == sm.opening_phase
    assert [s.value for s in restored.state_history] == [s.value for s in sm.state_history]


def test_restored_state_continues_investigation_correctly():
    sm = StateMachine()
    _advance_state_machine(sm)
    sm.investigation_phase["plaintiff_stated"] = True
    data = sm.to_dict()

    restored = StateMachine.from_dict(data)
    restored.investigation_phase["defendant_responded"] = True
    # 未完成条件不满足时不应误跳阶段
    restored.try_transition()
    assert restored.current_state == CourtState.INVESTIGATION


def test_from_dict_of_legacy_empty_state_starts_at_opening():
    sm = StateMachine.from_dict({
        "version": 1,
        "current_state": CourtState.OPENING.value,
        "current_sub_stage": "opening_identity",
        "state_history": [CourtState.OPENING.value],
        "sub_stage_history": ["opening_identity"],
        "compliance_log": [],
        "phases": {},
    })
    assert sm.current_state == CourtState.OPENING
    assert sm.opening_phase["plaintiff_verified"] is False


# ---------- 法条回查（Verified RAG） ----------

def test_verify_citations_hit_and_miss_against_real_db():
    """真实法条库：民法典第676条应命中；第9999条应标记 unverified。"""
    from core.judgment_validator import verify_citations
    retriever = None
    try:
        from core.law_retriever import get_shared_law_retriever
        retriever = get_shared_law_retriever()
    except Exception:
        pytest.skip("law db unavailable")
    j = {"applicable_laws": [
        {"law": "《中华人民共和国民法典》第676条", "content": "逾期利息"},
        {"law": "《中华人民共和国民法典》第99999条", "content": "不存在"},
    ]}
    report = verify_citations(j, retriever.db_path)
    assert report["checked"] == 2
    assert report["verified"] >= 1
    assert any("99999" in u for u in report["unverified"])
    # 判决对象内联标记
    assert j["applicable_laws"][0].get("verified") is True
    assert j["applicable_laws"][1].get("verified") is False


def test_verify_citations_chinese_article_number():
    """中文数字条号（第六百七十六条）应能解析并命中。"""
    from core.judgment_validator import verify_citations, cn_to_int
    assert cn_to_int("六百七十六") == 676
    assert cn_to_int("十二") == 12
    try:
        from core.law_retriever import get_shared_law_retriever
        retriever = get_shared_law_retriever()
    except Exception:
        pytest.skip("law db unavailable")
    j = {"applicable_laws": [{"law": "《中华人民共和国民法典》第六百七十六条"}]}
    report = verify_citations(j, retriever.db_path)
    assert report["verified"] == 1


# ---------- ReasoningState 往返 ----------

def test_ci_reasoning_state_roundtrip_via_record():
    """推理状态经 record.input_json 往返后可完整恢复（CI 场景跨轮不漂移）。"""
    from dataclasses import asdict
    from core.schemas import PartyRole, Message, Evidence
    from api.state import ci_reasoning_state_from_record, save_ci_reasoning_state

    class FakeCIAgent:
        pass

    class FakeSM:
        def to_dict(self):
            return {"version": 1, "current_state": "investigation", "phases": {}}

    agent = FakeCIAgent()
    agent.state_machine = FakeSM()
    agent.dialogue = [Message(role=PartyRole.JUDGE, content="现在开庭。", timestamp="2026-01-01T00:00:00")]
    agent.evidences = [Evidence(evidence_id="E1", provider=PartyRole.PLAINTIFF,
                                content="借条", purpose="证明借贷关系")]
    agent.extracted = {"plaintiff_claim": {"amount": "10万"}}
    agent.judgment_json = None
    agent.judgment_status = "failed"
    agent.finished = False

    class FakeRecord:
        input_json = {"case_description": "x"}

    rec = FakeRecord()
    save_ci_reasoning_state(rec, agent)
    state = ci_reasoning_state_from_record(rec)
    assert state["state_machine"]["current_state"] == "investigation"
    assert state["dialogue"][0]["role"] == "Judge"
    assert state["evidences"][0]["provider"] == "Plaintiff"
    # 可 JSON 序列化（落库前提）
    json.dumps(state, ensure_ascii=False)


# ---------- orchestrator CI 跨轮状态传递 ----------

def test_run_stage_ci_threads_reasoning_state_across_turns():
    """编排器 CI 阶段应把上一轮提取的推理状态传给下一轮 process_turn。"""
    from core.case_orchestrator import FullCaseOrchestrator

    calls = []

    class FakeCI:
        def __init__(self):
            self.rounds = 0
            self.state_machine = type("SM", (), {"to_dict": lambda self: {
                "version": 1, "current_state": "opening", "phases": {}}})()
            self.dialogue = []
            self.evidences = []
            self.extracted = {}
            self.judgment_json = None
            self.judgment_status = "failed"
            self.finished = False
            self.name_confirmed_by_dialogue = {"plaintiff": False, "defendant": False}

        def process_turn(self, dialog_history, case_id, input_json, reasoning_state=None):
            calls.append(reasoning_state)
            self.rounds += 1
            return "对原告说：请陈述诉讼请求。"

    class FakeSim:
        def simulate_plaintiff_with_strategy(self, *a, **k):
            return "原告陈述：被告借款未还。"

        def simulate_defendant_with_strategy(self, *a, **k):
            return "被告答辩：已还款。"

    fake_ci = FakeCI()
    fake_llm = type("L", (), {
        "chat_model": None,
        "chat_completion": staticmethod(lambda messages, **k: "当事人发言。"),
        "chat_json": staticmethod(lambda messages, **k: {}),
    })()
    orch = FullCaseOrchestrator(
        llm_client=fake_llm, cd_agent=None, dd_agent=None,
        ci_agent=fake_ci, sim_agent=FakeSim(), max_turns_per_stage=3,
    )
    result = orch.run_stage_ci(
        {"case_id": "T", "case_description": "测试"},
        complaint_text="诉状", defense_text="答辩",
    )
    assert len(calls) >= 2
    assert calls[0] is None  # 第一轮无历史状态
    # 第二轮起应收到上一轮提取的完整状态快照
    for st in calls[1:]:
        assert isinstance(st, dict) and "state_machine" in st
    assert result.final_document


# ---------- 会话级隔离 ----------

def test_new_session_ci_agent_returns_isolated_instances_with_shared_retriever():
    """工厂每次返回独立 CIAgent（并发隔离），law_retriever 仍是共享单例。"""
    os.environ.setdefault("LLM_API_KEY", "")
    for mod in ("api_server", "api", "api.state", "api_runtime", "config", "settings"):
        sys.modules.pop(mod, None)
    from api import state
    a1 = state.new_session_ci_agent()
    a2 = state.new_session_ci_agent()
    assert a1 is not a2
    assert a1.state_machine is not a2.state_machine
    assert a1.dialogue is not a2.dialogue
    # 单例检索器共享（重资源只加载一次）
    if a1.law_retriever is not None:
        assert a1.law_retriever is a2.law_retriever


# ---------- IssueGraph 争点分解 ----------

def _make_ledger_with_positions():
    ledger = FactLedger()
    ev, _ = ledger.evidence.submit("plaintiff", "转账记录10万元", "交付")
    ledger.add_claim("被告向原告借款10万元", "plaintiff", evidence_id=ev.evidence_id)
    ledger.add_claim("被告已归还全部欠款", "defendant")
    return ledger


def test_decompose_rule_based_never_empty_and_binds_facts():
    from core.issue_graph import IssueGraph, decompose
    ledger = _make_ledger_with_positions()
    graph = IssueGraph()
    issues = decompose(ledger, graph, llm=None)
    assert issues, "rule-based decomposition must never be empty"
    for i in issues:
        assert i.question
        assert all(f in ledger.claims for f in i.fact_ids)


def test_decompose_with_llm_uses_valid_fact_ids():
    from core.issue_graph import IssueGraph, decompose
    ledger = _make_ledger_with_positions()

    class FakeLLM:
        def chat_json(self, messages, **k):
            return {"issues": [
                {"question": "10万元借款是否实际交付", "fact_ids": ["F1"]},
                {"question": "还款抗辩是否有证据", "fact_ids": ["F2", "F99"]},  # F99 应被过滤
            ]}

    graph = IssueGraph()
    issues = decompose(ledger, graph, llm=FakeLLM())
    assert len(issues) == 2
    assert issues[0].fact_ids == ["F1"]
    assert issues[1].fact_ids == ["F2"]  # F99 被过滤
    assert graph.as_prompt_text().count("[I") == 2


def test_issue_graph_roundtrip():
    from core.issue_graph import IssueGraph
    g = IssueGraph()
    g.add_issue("争点一", ["F1"])
    g.attach_law("I1", 81)
    data = g.to_dict()
    restored = IssueGraph.from_dict(data)
    assert restored.issues["I1"].law_ids == [81]
    assert json.dumps(data, ensure_ascii=False)


# ---------- 诉请覆盖与事实引用校验 ----------

def test_verify_dispositions_full_and_partial_coverage():
    from core.judgment_validator import verify_dispositions
    judgment = {"liability_mapping": {
        "plaintiff_claims": ["归还本金10万元", "支付利息"],
        "court_adoption": ["支持本金", "利息部分支持"],
    }}
    r = verify_dispositions(judgment, ["归还本金10万元", "支付利息"])
    assert r["coverage"] == 1.0 and not r["missing"]

    r2 = verify_dispositions({"liability_mapping": {
        "plaintiff_claims": ["归还本金10万元"], "court_adoption": ["支持"]}},
        ["归还本金10万元", "支付利息"])
    assert r2["coverage"] == 0.5
    assert r2["missing"] and r2["missing"][0].startswith("支付利息")


def test_verify_fact_references_detects_unknown_refs():
    from core.fact_ledger import FactLedger
    from core.judgment_validator import verify_fact_references
    ledger = FactLedger()
    ledger.add_claim("借款交付", "plaintiff")  # F1
    text = "本院查明：[F1] 借款交付事实清楚；另 [F7] 与 [E_x] 亦经查明。"
    r = verify_fact_references(text, ledger)
    assert "F7" in r["unknown_refs"]       # F7 不存在 → 幻觉引用
    assert not r["no_references"]


def test_verify_fact_references_flags_no_references():
    from core.fact_ledger import FactLedger
    from core.judgment_validator import verify_fact_references
    ledger = FactLedger()
    ledger.add_claim("借款交付", "plaintiff")
    r = verify_fact_references("本院查明：借款已交付。", ledger)
    assert r["no_references"]

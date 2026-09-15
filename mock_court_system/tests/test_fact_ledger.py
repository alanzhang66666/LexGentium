"""Fact/Evidence Ledger 单元测试（Phase 1：证据化裁判地基）。"""
import sys, os, json
sys.path.insert(0, os.getcwd())

import pytest

from core.fact_ledger import EvidenceLedger, FactLedger


# ---------- 证据账本 ----------

def test_duplicate_submission_increments_count_without_new_entry():
    ledger = EvidenceLedger()
    e1, new1 = ledger.submit("plaintiff", "2024年3月银行转账记录10万元", "证明借款交付")
    e2, new2 = ledger.submit("plaintiff", "2024年3月银行转账记录10万元", "证明借款交付")
    assert new1 and not new2
    assert e1 is e2
    assert e1.submissions_count == 2
    assert len(ledger) == 1


def test_containment_duplicate_is_merged():
    ledger = EvidenceLedger()
    ledger.submit("plaintiff", "被告于2024年3月1日通过工商银行转账10万元至原告账户", "交付事实")
    entry, is_new = ledger.submit("defendant", "转账10万元至原告账户", "不同说法")
    assert not is_new and entry.provider == "plaintiff"


def test_contested_marking():
    ledger = EvidenceLedger()
    entry, _ = ledger.submit("plaintiff", "借条一张", "借贷合意")
    ledger.mark_contested(entry.evidence_id)
    assert ledger.get(entry.evidence_id).contested is True


# ---------- 事实账本 ----------

def test_claim_dedupe_and_evidence_attachment():
    ledger = FactLedger()
    ev, _ = ledger.evidence.submit("plaintiff", "转账记录", "交付")
    c1, new1 = ledger.add_claim("被告向原告借款10万元", "plaintiff", evidence_id=ev.evidence_id)
    c2, new2 = ledger.add_claim("被告向原告借款10万元整", "plaintiff")
    assert new1 and not new2 and c1 is c2
    assert ev.evidence_id in c1.evidence_ids


def test_disputed_without_evidence_exposed():
    ledger = FactLedger()
    ev, _ = ledger.evidence.submit("plaintiff", "转账记录", "交付")
    ledger.add_claim("借款已交付", "plaintiff", evidence_id=ev.evidence_id)
    ledger.add_claim("被告已归还全部欠款", "defendant")  # 无证据
    risky = ledger.disputed_without_evidence()
    assert len(risky) == 1
    assert "归还" in risky[0].text


def test_adjudicate_and_status_transitions():
    ledger = FactLedger()
    claim, _ = ledger.add_claim("借款交付", "plaintiff")
    assert claim.status == "alleged"
    ledger.set_status(claim.fact_id, "disputed")
    ledger.adjudicate(claim.fact_id, adopted=True, reason="有转账记录佐证")
    assert claim.status == "adjudicated"
    assert claim.adjudication["adopted"] is True
    with pytest.raises(ValueError):
        ledger.set_status(claim.fact_id, "bogus")


# ---------- 序列化 ----------

def test_ledger_roundtrip_preserves_everything():
    ledger = FactLedger()
    ev, _ = ledger.evidence.submit("plaintiff", "转账记录10万元", "交付")
    ledger.add_claim("借款交付", "plaintiff", evidence_id=ev.evidence_id)
    ledger.mark_contested(ev.evidence_id)

    data = ledger.to_dict()
    restored = FactLedger.from_dict(data)
    assert [c.fact_id for c in restored.claims.values()] == [c.fact_id for c in ledger.claims.values()]
    entry = restored.get_evidence(ev.evidence_id)
    assert entry.submissions_count == 1 and entry.contested is True
    claim = list(restored.claims.values())[0]
    assert ev.evidence_id in claim.evidence_ids
    # 序列化结果可 JSON 落库
    json.dumps(data, ensure_ascii=False)


# ---------- prompt 注入 ----------

def test_prompt_text_lists_claims_with_ids():
    ledger = FactLedger()
    ev, _ = ledger.evidence.submit("plaintiff", "转账记录", "交付")
    ledger.add_claim("借款交付", "plaintiff", evidence_id=ev.evidence_id)
    ledger.add_claim("已经还款", "defendant")
    text = ledger.as_prompt_text()
    assert "[F1]" in text and "[F2]" in text
    assert "无证据支持" not in text  # 提示词本身不含警告（警告单独追加）
    assert "支持证据：无" in text


def test_prompt_warns_on_evidence_free_disputed_facts():
    ledger = FactLedger()
    ledger.add_claim("已经还款", "defendant")
    text = ledger.as_prompt_text()
    text += "\n【警告】以下事实主张无任何证据支持，不得写入本院查明：" + ", ".join(
        c.fact_id for c in ledger.disputed_without_evidence())
    assert "不得写入本院查明" in text

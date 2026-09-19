"""Release gate CLI 端到端自测（Task 14.4）。

用小型受管夹具验证：命令顺序、失败短路、evidence content-addressed
digest、commit binding、GO/NO-GO、append-only decision chain，
不依赖真实外部 LLM 或真实检查命令。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import release_gate as cli  # noqa: E402
from core.release.checks import (  # noqa: E402
    CheckSpec,
    load_evidence,
    persist_evidence,
    run_check,
)
from core.release.evidence import EvidenceRecord, EvidenceResult  # noqa: E402
from core.release.gate import validate_chain  # noqa: E402

COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40


def _spec(check_id="fixture", command=None, timeout=30, mandatory=True, min_samples=0):
    return CheckSpec(
        check_id=check_id,
        kind="subprocess" if command else "in_process",
        mandatory=mandatory,
        command=tuple(command or ()),
        timeout_seconds=timeout,
        min_samples=min_samples,
        owner="test",
        closure_action="fix fixture",
    )


@pytest.fixture()
def ev_root(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    return root


def _passing_spec():
    return _spec(
        check_id="ok",
        command=[sys.executable, "-c", "import sys; sys.exit(0)"],
    )


def test_passing_check_produces_valid_evidence(ev_root):
    record, _ = run_check(_passing_spec(), commit_id=COMMIT, run_id="r1")
    assert record.result == EvidenceResult.PASS.value
    assert record.exit_code == 0
    assert record.commit_id == COMMIT
    assert record.is_valid_for_gate()


def test_failing_check_fail_closed(ev_root):
    spec = _spec(command=[sys.executable, "-c", "import sys; sys.exit(3)"])
    record, _ = run_check(spec, commit_id=COMMIT, run_id="r1")
    assert record.result == EvidenceResult.FAIL.value
    assert record.exit_code == 3
    assert not record.is_valid_for_gate()


def test_timeout_check_fail_closed(ev_root):
    spec = _spec(
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        timeout=1,
    )
    record, _ = run_check(spec, commit_id=COMMIT, run_id="r1")
    assert record.result == EvidenceResult.TIMEOUT.value
    assert not record.is_valid_for_gate()


def test_evidence_is_content_addressed(ev_root):
    r1, _ = run_check(_passing_spec(), commit_id=COMMIT, run_id="r1")
    r2, _ = run_check(_passing_spec(), commit_id=COMMIT, run_id="r1", run_index=1)
    p1 = persist_evidence(r1, {"x": 1})
    p2 = persist_evidence(r2, {"x": 1})
    # 不同 run_index → 不同 digest → 不同文件，不互相覆盖
    assert p1 != p2
    assert len(list((ev_root / "records").glob("*.json"))) == 2


def test_verify_no_go_on_missing_evidence(ev_root, monkeypatch):
    monkeypatch.setattr(cli, "_load_gaps", lambda: [])
    rc = cli.main(
        [
            "verify",
            "--version",
            "1.0.0",
            "--commit",
            COMMIT,
            "--evidence-root",
            str(ev_root),
        ]
    )
    assert rc == 1
    decisions = (ev_root / "decisions.jsonl").read_text().strip().splitlines()
    assert len(decisions) == 1
    rec = json.loads(decisions[0])
    assert rec["type"] == "no_go"
    assert "unit_tests_critical" in rec["failed_criteria"]


def test_verify_go_with_fixture_catalog(ev_root, monkeypatch, capsys):
    # 只含一条 mandatory fixture check 的 catalog
    spec = _passing_spec()
    monkeypatch.setattr(cli, "load_check_catalog", lambda: [spec])
    monkeypatch.setattr(cli, "_load_gaps", lambda: [])

    record, _ = run_check(spec, commit_id=COMMIT, run_id="r1")
    persist_evidence(record)

    rc = cli.main(
        [
            "verify",
            "--version",
            "1.0.0",
            "--commit",
            COMMIT,
            "--evidence-root",
            str(ev_root),
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "go"
    assert out["chain_valid"] is True


def test_verify_no_go_on_commit_mismatch(ev_root, monkeypatch, capsys):
    spec = _passing_spec()
    monkeypatch.setattr(cli, "load_check_catalog", lambda: [spec])
    monkeypatch.setattr(cli, "_load_gaps", lambda: [])

    # 证据绑定别的 commit → 对候选 commit 必须 no_go
    record, _ = run_check(spec, commit_id=OTHER_COMMIT, run_id="r1")
    persist_evidence(record)

    rc = cli.main(
        [
            "verify",
            "--version",
            "1.0.0",
            "--commit",
            COMMIT,
            "--evidence-root",
            str(ev_root),
        ]
    )
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "no_go"
    assert out["evidence_records"] == 0  # 非本 commit 证据不采纳


def test_decision_chain_detects_tampering(ev_root, monkeypatch):
    spec = _passing_spec()
    monkeypatch.setattr(cli, "load_check_catalog", lambda: [spec])
    monkeypatch.setattr(cli, "_load_gaps", lambda: [])

    record, _ = run_check(spec, commit_id=COMMIT, run_id="r1")
    persist_evidence(record)
    for _ in range(2):
        cli.main(
            [
                "verify",
                "--version",
                "1.0.0",
                "--commit",
                COMMIT,
                "--evidence-root",
                str(ev_root),
            ]
        )
    lines = (ev_root / "decisions.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2

    # 篡改第一条 → 链校验失败
    tampered = json.loads(lines[0])
    tampered["approver"] = "mallory"
    lines[0] = json.dumps(tampered, sort_keys=True)
    (ev_root / "decisions.jsonl").write_text("\n".join(lines) + "\n")

    log = cli._load_decision_log(ev_root)
    ok, reason = validate_chain(list(log.records))
    assert not ok
    assert "digest" in reason or "mismatch" in reason


def test_verify_rejects_short_commit(ev_root):
    rc = cli.main(
        [
            "verify",
            "--version",
            "1.0.0",
            "--commit",
            "abc123",
            "--evidence-root",
            str(ev_root),
        ]
    )
    assert rc == 2


def test_verify_rejects_version_mismatch(ev_root):
    rc = cli.main(
        [
            "verify",
            "--version",
            "9.9.9",
            "--commit",
            COMMIT,
            "--evidence-root",
            str(ev_root),
        ]
    )
    assert rc == 2


def test_load_evidence_roundtrip(ev_root):
    record, _ = run_check(_passing_spec(), commit_id=COMMIT, run_id="r1")
    persist_evidence(record)
    loaded = load_evidence(ev_root)
    assert len(loaded) == 1
    assert loaded[0].evidence_id == record.evidence_id
    assert loaded[0].digest() == record.digest()

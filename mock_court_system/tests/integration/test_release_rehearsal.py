"""Release rehearsal drill 集成测试（Task 13.2）。

覆盖：full 全链路通过、损坏备份拒绝、非空 restore root 拒绝、
升级失败回滚保留生产内容、RPO 超限拒绝、逻辑名→默认文件名映射。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import release_rehearsal as rr  # noqa: E402


def _seed_db(root: Path, row_id: str = "seed-1") -> None:
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(root / "conversations.sqlite3"))
    conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT)")
    conn.execute("INSERT OR REPLACE INTO sessions VALUES (?, '{}')", (row_id,))
    conn.commit()
    conn.close()


def _read_ids(db: Path) -> list:
    conn = sqlite3.connect(str(db))
    try:
        return [r[0] for r in conn.execute("SELECT id FROM sessions ORDER BY id")]
    finally:
        conn.close()


class TestFullDrill:
    def test_full_passes(self, tmp_path, capsys):
        rc = rr.main(["full", "--workdir", str(tmp_path / "w")])
        transcript = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert transcript["verdict"] == "pass"
        assert transcript["failure_reasons"] == []
        step_names = [s["step"] for s in transcript["steps"]]
        assert step_names == [
            "seed_fixture",
            "backup",
            "restore",
            "fingerprint_compare",
            "rpo_check",
        ]
        compare = transcript["steps"][3]
        assert compare["match"] is True

    def test_full_restores_logical_to_default_filenames(self, tmp_path, capsys):
        rc = rr.main(["full", "--workdir", str(tmp_path / "w")])
        transcript = json.loads(capsys.readouterr().out)
        assert rc == 0
        restored = next(tmp_path.glob("w/*_restored"))
        names = {f.name for f in restored.glob("*.sqlite3")}
        # descriptor 默认文件名，不是备份里的逻辑名
        assert "conversations.sqlite3" in names
        assert "conversation_store.sqlite3" not in names
        assert _read_ids(restored / "conversations.sqlite3") == ["rehearsal-fixture"]

    def test_full_transcript_identity(self, tmp_path, capsys):
        rr.main(["full", "--workdir", str(tmp_path / "w")])
        transcript = json.loads(capsys.readouterr().out)
        ident = transcript["identity"]
        assert ident["version_id"]
        assert ident["environment_identity"]
        assert transcript["schema"] == "release-rehearsal-v1"


class TestBackupRestoreDrill:
    def test_backup_then_restore(self, tmp_path, capsys):
        src = tmp_path / "src"
        _seed_db(src, "prod-row")
        rc = rr.main(["backup", "--data-root", str(src), "--dest", str(tmp_path / "bak")])
        t = json.loads(capsys.readouterr().out)
        assert rc == 0 and t["verdict"] == "pass"

        dst = tmp_path / "dst"
        rc = rr.main(["restore", "--backup", str(tmp_path / "bak"), "--data-root", str(dst)])
        t = json.loads(capsys.readouterr().out)
        assert rc == 0 and t["verdict"] == "pass"
        assert _read_ids(dst / "conversations.sqlite3") == ["prod-row"]

    def test_corrupted_backup_rejected(self, tmp_path, capsys):
        src = tmp_path / "src"
        _seed_db(src)
        rr.main(["backup", "--data-root", str(src), "--dest", str(tmp_path / "bak")])
        capsys.readouterr()
        victim = next((tmp_path / "bak").glob("*.sqlite3"))
        victim.write_bytes(b"corrupted-not-sqlite")
        rc = rr.main(["restore", "--backup", str(tmp_path / "bak"), "--data-root", str(tmp_path / "dst")])
        t = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert t["verdict"] == "fail"
        assert t["failure_reasons"]

    def test_nonempty_restore_root_refused(self, tmp_path, capsys):
        src = tmp_path / "src"
        _seed_db(src)
        rr.main(["backup", "--data-root", str(src), "--dest", str(tmp_path / "bak")])
        capsys.readouterr()
        dst = tmp_path / "dst"
        dst.mkdir()
        (dst / "conversations.sqlite3").write_bytes(b"occupied")
        rc = rr.main(["restore", "--backup", str(tmp_path / "bak"), "--data-root", str(dst)])
        t = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert t["verdict"] == "fail"


class TestRollbackDrill:
    def test_simulated_failure_preserves_production(self, tmp_path, capsys):
        prod = tmp_path / "prod"
        _seed_db(prod, "precious")
        rc = rr.main(
            [
                "rollback",
                "--production", str(prod),
                "--backup", str(tmp_path / "bak"),
                "--simulate-failure",
            ]
        )
        t = json.loads(capsys.readouterr().out)
        assert rc == 0, t["failure_reasons"]
        assert t["verdict"] == "pass"
        # 生产 root 恢复出原业务行，升级 marker 不残留
        assert _read_ids(prod / "conversations.sqlite3") == ["precious"]
        assert not (prod / ".upgrade_in_progress").exists()
        steps = [s["step"] for s in t["steps"]]
        assert "restore_production" in steps
        assert "quarantine_damaged_root" in steps

    def test_no_failure_keeps_root_unchanged(self, tmp_path, capsys):
        prod = tmp_path / "prod"
        _seed_db(prod, "stable")
        rc = rr.main(["rollback", "--production", str(prod), "--backup", str(tmp_path / "bak")])
        t = json.loads(capsys.readouterr().out)
        assert rc == 0, t["failure_reasons"]
        assert _read_ids(prod / "conversations.sqlite3") == ["stable"]
        assert "restore_production" not in [s["step"] for s in t["steps"]]

    def test_rpo_violation_fails(self, tmp_path, capsys):
        # 源数据最后提交时间在 48h 前 → 备份的 RPO age 超过 24h 上限
        prod = tmp_path / "prod"
        prod.mkdir(parents=True)
        old = (datetime.utcnow() - timedelta(hours=48)).isoformat() + "Z"
        conn = sqlite3.connect(str(prod / "conversations.sqlite3"))
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, payload TEXT, created_at TEXT)"
        )
        conn.execute("INSERT INTO sessions VALUES ('stale', '{}', ?)", (old,))
        conn.commit()
        conn.close()
        rc = rr.main(["rollback", "--production", str(prod), "--backup", str(tmp_path / "bak")])
        t = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert any("rpo" in r for r in t["failure_reasons"])


class TestDeploymentDrill:
    """Task 13.3：clean install / 非 root / smoke / backup-restore 自动验证。"""

    CATALOG = ROOT / "deploy" / "commands.yaml"

    def _catalog(self):
        import yaml

        return yaml.safe_load(self.CATALOG.read_text(encoding="utf-8"))

    def test_catalog_entries_declare_result_or_exit(self):
        catalog = self._catalog()
        assert catalog["commands"], "empty deployment command catalog"
        ids = set()
        for entry in catalog["commands"]:
            assert entry.get("id") and entry["id"] not in ids
            ids.add(entry["id"])
            assert entry.get("command"), entry["id"]
            assert entry.get("cwd"), entry["id"]
            assert entry.get("expected_result") is not None or "expected_exit" in entry, entry["id"]

    def test_catalog_covers_all_journeys(self):
        catalog = self._catalog()
        journeys = {c.get("journey") for c in catalog["commands"] if c.get("journey")}
        for journey in (
            "configuration", "conversation", "simulate", "full_simulation",
            "mediation", "research", "evaluation", "system",
        ):
            assert journey in journeys, f"missing smoke command for {journey}"

    def test_deployment_docs_validator_exits_zero(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_deployment_docs.py")],
            cwd=str(ROOT),
            capture_output=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stdout.decode()[-500:] + proc.stderr.decode()[-500:]

    def test_rehearsal_cli_help_exits_zero(self):
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "release_rehearsal.py"), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            timeout=60,
        )
        assert proc.returncode == 0

    def test_health_smoke_in_process(self, tmp_path, monkeypatch):
        """不驻留 server 的 smoke：in-process ASGI 命中 liveness/readiness。"""
        monkeypatch.setenv("OPERATION_DB_PATH", str(tmp_path / "ops.sqlite3"))
        monkeypatch.setenv("CONVERSATION_DB_PATH", str(tmp_path / "conv.sqlite3"))
        monkeypatch.setenv("RUNTIME_DATA_ROOT", str(tmp_path))
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setenv("LLM_BASE_URL", "")
        monkeypatch.setenv("LLM_MODEL", "")
        stale = [m for m in list(sys.modules) if m == "api_server" or m.startswith("api.")]
        for m in stale:
            sys.modules.pop(m, None)
        from fastapi.testclient import TestClient
        import api_server

        client = TestClient(api_server.app)
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "ok"
        ready = client.get("/health/ready")
        assert ready.status_code in (200, 503)
        assert "components" in ready.json()

    def test_rehearsal_reports_non_root_identity(self, tmp_path, capsys):
        rr.main(["full", "--workdir", str(tmp_path / "w")])
        transcript = json.loads(capsys.readouterr().out)
        assert transcript["identity"]["non_root"] is True


class TestFingerprint:
    def test_meta_tables_excluded(self, tmp_path):
        root = tmp_path / "root"
        _seed_db(root, "x")
        before = rr._db_content_fingerprint(root)
        conn = sqlite3.connect(str(root / "conversations.sqlite3"))
        conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
        conn.execute("CREATE TABLE _readiness_probe (id INTEGER)")
        conn.execute("INSERT INTO schema_migrations VALUES (1)")
        conn.commit()
        conn.close()
        assert rr._db_content_fingerprint(root) == before

    def test_business_change_detected(self, tmp_path):
        root = tmp_path / "root"
        _seed_db(root, "x")
        before = rr._db_content_fingerprint(root)
        conn = sqlite3.connect(str(root / "conversations.sqlite3"))
        conn.execute("INSERT INTO sessions VALUES ('y', '{}')")
        conn.commit()
        conn.close()
        assert rr._db_content_fingerprint(root) != before

    def test_unreadable_db_flagged(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "broken.sqlite3").write_bytes(b"garbage-header" * 100)
        fp = rr._db_content_fingerprint(root)
        assert fp["broken.sqlite3"] == "unreadable"

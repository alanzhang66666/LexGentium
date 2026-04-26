"""API 端点冒烟测试"""
import requests
import json
import sys

BASE = "http://localhost:8000"
passed = 0
failed = 0

def test(name, method, url, **kwargs):
    global passed, failed
    try:
        r = getattr(requests, method)(url, timeout=5, **kwargs)
        ok = r.status_code in (200, 201)
        status = "PASS" if ok else f"FAIL({r.status_code})"
        if ok:
            passed += 1
        else:
            failed += 1
        detail = ""
        try:
            body = r.json()
            if isinstance(body, dict):
                detail = str({k: str(v)[:60] for k, v in list(body.items())[:3]})
        except Exception:
            pass
        print(f"  [{status}] {name}: {r.status_code} {detail[:120]}")
        return r.json() if ok else None
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}: {e}")
        return None

print("=== API Endpoint Smoke Test ===\n")

# Basic
test("Health", "get", f"{BASE}/health")
test("LLM Config", "get", f"{BASE}/config/llm")
test("DB Stats", "get", f"{BASE}/database/stats")
test("API History Stats", "get", f"{BASE}/api-history/stats")
test("Conv List", "get", f"{BASE}/conversation/list")
test("Eval Results", "get", f"{BASE}/evaluation/results")

# Game session
data = test("Game Create", "post", f"{BASE}/game/create", json={
    "case_info": {"case_id": "SMOKE-001", "case_description": "冒烟测试"},
    "plaintiff_strategy": "collaborating",
    "defendant_strategy": "competing",
    "max_rounds": 2,
})

if data:
    gid = data["game_id"]
    test("Game Status", "get", f"{BASE}/game/{gid}")
    test("Strategy Set", "post", f"{BASE}/game/{gid}/strategy/set", json={
        "party": "plaintiff", "strategy_type": "compromising",
    })
    test("Payoff Matrix", "get", f"{BASE}/game/{gid}/strategy/payoff-matrix")
    test("Equilibrium", "get", f"{BASE}/game/{gid}/equilibrium")
    test("Convergence", "get", f"{BASE}/game/{gid}/equilibrium/convergence")
    test("Strategy History", "get", f"{BASE}/game/{gid}/strategy/history")
    test("Game List", "get", f"{BASE}/game/list")
    test("Game Delete", "delete", f"{BASE}/game/{gid}")

# Mediation
med = test("Mediation Create", "post", f"{BASE}/mediation/create", json={
    "case_info": {"case_id": "MED-001", "case_description": "测试调解"},
})
if med:
    mid = med["session_id"]
    test("Mediation Status", "get", f"{BASE}/mediation/{mid}/status")

# Conversation start
conv = test("Conv Start", "post", f"{BASE}/conversation/start", json={
    "scenario": "CD", "case_id": "TEST-CD",
})
if conv:
    sid = conv["session_id"]
    test("Conv Get", "get", f"{BASE}/conversation/{sid}")
    test("Conv Delete", "delete", f"{BASE}/conversation/{sid}")

print(f"\n=== Results: {passed} passed, {failed} failed ===")
if failed:
    sys.exit(1)

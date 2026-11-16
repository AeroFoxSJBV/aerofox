"""Stability features: polling jobs, persisted sessions, empty-answer guard, queue progress and health counters."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from aerofox.agent import llm, progress
from aerofox.agent.state import SessionStore
from aerofox.api import app as appmod

client = TestClient(appmod.app)


def _wait_job(jid, timeout=60):
    after, events, t0 = 0, [], time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/chat/jobs/{jid}", params={"after": after})
        assert r.status_code == 200
        body = r.json()
        events += body["events"]
        after = body["next"]
        if body["done"]:
            return body["result"], events
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_job_endpoint_returns_same_contract_as_chat():
    r = client.post("/api/chat/jobs", json={"message": "Compare Saffire-II runs 2-5 and 2-6"})
    assert r.status_code == 200 and len(r.json()["job_id"]) == 32
    result, _ = _wait_job(r.json()["job_id"])
    direct = client.post("/api/chat", json={"message": "Compare Saffire-II runs 2-5 and 2-6"}).json()
    for key in ("session_id", "answer", "blocks", "evidence", "warnings", "project", "mode", "request_id"):
        assert key in result
    assert result["answer"] == direct["answer"]
    assert [b["type"] for b in result["blocks"]] == [b["type"] for b in direct["blocks"]]


@pytest.mark.parametrize("jid", ["../etc", "x" * 32, "0" * 31, "A" * 32])
def test_job_poll_rejects_bad_or_unknown_ids(jid):
    assert client.get(f"/api/chat/jobs/{jid}").status_code == 404


def test_job_validation_matches_chat():
    assert client.post("/api/chat/jobs", json={"message": ""}).status_code == 422
    assert client.post("/api/chat/jobs", json={"message": "x" * 5000}).status_code == 422


def test_health_reports_service_counters_and_queue():
    before = client.get("/api/health").json()["service"]["turns"]
    client.post("/api/chat", json={"message": "What is Saffire?"})
    h = client.get("/api/health").json()
    assert h["service"]["turns"] == before + 1
    assert h["service"]["offline_answers"] >= 1 and "disabled" in h["service"]["offline_reasons"]
    assert h["queue"]["max_waiting"] >= 1


def test_sessions_survive_a_restart(tmp_path):
    db = str(tmp_path / "s.sqlite3")
    a = SessionStore(10, 3600, db)
    s = a.get_or_create(None)
    s.remember("user", "my habitat uses Nomex at 57 kPa")
    s.project = s.project.model_copy(update={"pressure_kPa": 57.0})
    a.persist(s)
    b = SessionStore(10, 3600, db)                # a new process after a crash or restart
    restored = b.get(s.id)
    assert restored is not None and restored.project.pressure_kPa == 57.0
    assert restored.turns[-1].text.startswith("my habitat")


def test_expired_sessions_are_not_restored(tmp_path):
    db = str(tmp_path / "s.sqlite3")
    a = SessionStore(10, 1, db)
    s = a.get_or_create(None)
    a.persist(s)
    time.sleep(1.2)
    assert SessionStore(10, 1, db).get(s.id) is None


@pytest.mark.parametrize("text", [
    "**Evidence:** [FLEX-1]\n\n**Next step:** [FLEX-1]",
    "Summary:\n- Key points:",
    "[FLEX-1]",
])
def test_ground_rejects_heading_only_answers(text):
    results = [{"ok": True, "tool": "search_evidence", "evidence": ["FLEX-1"], "summary": "", "data": {}}]
    with pytest.raises(llm.LLMUnavailable):
        llm._ground(text, results)


def test_ground_keeps_real_explanations_and_bold_list_items():
    results = [{"ok": True, "tool": "search_evidence", "evidence": ["FLEX-1"], "summary": "", "data": {}}]
    text = ("Flames in microgravity lack buoyant flow, so oxygen reaches them by diffusion [FLEX-1].\n"
            "- **Cabin atmosphere** controls how readily materials ignite [FLEX-1].")
    out, removed = llm._ground(text, results)
    assert "diffusion" in out and "Cabin atmosphere" in out and removed == 0


def test_queue_reports_position_while_waiting(monkeypatch):
    events = []
    release = threading.Event()

    def holder():
        with llm._queue(time.monotonic() + 30):
            release.wait(10)
    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.2)
    timer = threading.Timer(3, release.set)
    timer.start()
    with progress.use_sink(events.append):
        with llm._queue(time.monotonic() + 30):
            pass
    t.join()
    assert any(e["stage"] == "queue" and e["position"] == 1 and e["eta_s"] > 0 for e in events)


def test_progress_sink_errors_never_break_a_turn():
    def bad(_):
        raise RuntimeError("boom")
    with progress.use_sink(bad):
        progress.emit({"type": "status"})

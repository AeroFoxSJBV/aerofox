"""Progress events for the current request (queue position, stage, tool), plus service counters.

Code anywhere in a turn calls emit(); the job endpoint installs a sink with use_sink().
Counters feed /api/health so failures are visible instead of silent.
"""
from __future__ import annotations

import contextvars
import threading
import time
from collections import Counter
from contextlib import contextmanager

_SINK: contextvars.ContextVar = contextvars.ContextVar("aerofox_progress_sink", default=None)
STARTED = time.time()
COUNTS: Counter = Counter()
_LOCK = threading.Lock()


def emit(event: dict) -> None:
    sink = _SINK.get()
    if sink is not None:
        try:
            sink(event)
        except Exception:  # progress must never break a turn
            pass


@contextmanager
def use_sink(sink):
    token = _SINK.set(sink)
    try:
        yield
    finally:
        _SINK.reset(token)


def count(key: str, n: int = 1) -> None:
    with _LOCK:
        COUNTS[key] += n


def snapshot() -> dict:
    with _LOCK:
        c = dict(COUNTS)
    turns = c.get("turns", 0)
    offline = sum(v for k, v in c.items() if k.startswith("offline:"))
    return {"uptime_s": round(time.time() - STARTED), "turns": turns, "llm_answers": c.get("llm_answers", 0),
            "offline_answers": offline, "offline_rate": round(offline / turns, 3) if turns else None,
            "offline_reasons": {k.split(":", 1)[1]: v for k, v in c.items() if k.startswith("offline:")}}

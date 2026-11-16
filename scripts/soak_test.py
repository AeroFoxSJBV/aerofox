"""Judge-style soak test through the same path the browser uses (start a job, then poll it).

    python scripts/soak_test.py --base http://127.0.0.1:8012 --judges 3
    python scripts/soak_test.py --base https://<your-public-link> --judges 3 --rounds 2

Several "judges" ask different questions AT THE SAME TIME. For each answer it reports whether the local model
answered (mode=llm) or the offline engine took over, how long it took, and the biggest queue position seen.
Use it before the judging window, through the PUBLIC link, to see what the judges will see.
Start a local server with a high AEROFOX_RATE_PER_MINUTE, since all simulated judges share one address.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import statistics
import time
import urllib.request

QUESTIONS = [
    "Why does the curve keep descending after visible extinction in FLEX-035?",
    "We are planning a surface outpost on the Moon. Chart which fire barrier needs verification first.",
    "Show the independent measurements for Saffire-II flow, especially sample 2-6.",
    "Mostre um gráfico de como o oxigênio se relaciona com a taxa de queima de gotas no FLEX.",
    "What did Apollo 1 teach engineers about cabin atmospheres?",
    "How could shared return air move contamination from a battery bay? Model the difference if I isolate it.",
]


def call(base, path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "AeroFox-soak-test"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def judge(base, i, rounds):
    rows, sid = [], None
    for k in range(rounds):
        q = QUESTIONS[(i + k) % len(QUESTIONS)]
        t0 = time.time()
        job = call(base, "/api/chat/jobs", {"message": q, "session_id": sid})
        after, worst, result = 0, 0, None
        while time.time() - t0 < 600:
            p = call(base, f"/api/chat/jobs/{job['job_id']}?after={after}")
            after = p["next"]
            worst = max([worst] + [e.get("position", 0) for e in p["events"] if e.get("stage") == "queue"])
            if p["done"]:
                result = p["result"]
                break
            time.sleep(1)
        sid = (result or {}).get("session_id", sid)
        rows.append({"judge": i, "question": q[:60], "mode": (result or {}).get("mode", "timeout"),
                     "reason": ((result or {}).get("generation") or {}).get("reason"),
                     "seconds": round(time.time() - t0, 1), "max_queue_position": worst})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8012")
    ap.add_argument("--judges", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=1)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    with cf.ThreadPoolExecutor(a.judges) as ex:
        rows = [r for f in [ex.submit(judge, base, i, a.rounds) for i in range(a.judges)] for r in f.result()]
    llm = sum(r["mode"] == "llm" for r in rows)
    print(f"\n{llm}/{len(rows)} answers written by the local model; "
          f"median {statistics.median(r['seconds'] for r in rows):.0f} s, max {max(r['seconds'] for r in rows):.0f} s; "
          f"health: {call(base, '/api/health').get('service')}")


if __name__ == "__main__":
    main()

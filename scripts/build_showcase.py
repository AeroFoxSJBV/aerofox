"""Build the static AeroFox showcase: the real interface replaying REAL answers recorded from the local model.

    python scripts/build_showcase.py --base http://127.0.0.1:8012          # server running with the local model

Output: showcase/ (index.html + the unchanged frontend + recorded.js). It needs no server, so it can be hosted for
free (GitHub Pages, a static host) and works as a backup link for the judges when the team computer is off.
Every recorded answer keeps its model name, timing, tools, sources and warnings; nothing is written by hand.
Only answers that came from the local model (mode "llm") are kept, unless --allow-offline is given.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "showcase"

CONVERSATIONS = [
    ["Compare Saffire-II runs 2-5 and 2-6: were they tested at the same airflow?"],
    ["I'm designing a lunar habitat. What are the main fire safety factors I should consider? Show me a chart.",
     "And on Mars?"],
    ["Investigate FLEX-035: what happened after the visible flame went out?",
     "Explain that in simpler terms."],
    ["Compare ventilation designs for a battery bay: connected versus isolated compartments."],
    ["Show me a fire-safety verification flowchart for an EVA suit."],
    ["Mostre um gráfico de como o oxigênio se relaciona com a taxa de queima de gotas no FLEX."],
    ["What did Apollo 1 teach engineers about cabin atmospheres?"],
]
LIBRARY = ["investigations", "findings", "references", "fields", "provenance"]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(base, path, raw=False):
    with OPENER.open(base + path, timeout=60) as r:
        data = r.read()
    return data.decode("utf-8") if raw else json.loads(data)


def post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with OPENER.open(req, timeout=400) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8012")
    ap.add_argument("--allow-offline", action="store_true")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    health = get(base, "/api/health")
    if not health["llm"]["ready"] and not a.allow_offline:
        raise SystemExit("The local model is not ready; start AeroFox with the model first.")
    rec = {"recorded_at": time.strftime("%Y-%m-%d"), "model": health["llm"]["model"], "runtime": health["llm"]["runtime"],
           "health": {k: health[k] for k in ("status", "version", "snapshot", "evidence_items", "tables")} | {
               "llm": {"configured": True, "ready": True, "model": health["llm"]["model"] + " (recorded)",
                       "runtime": health["llm"]["runtime"]}},
           "library": {name: get(base, f"/api/library/{name}") for name in LIBRARY},
           "turns": [], "sessions": {}, "evidence": {}, "files": {}}
    evidence_ids = set()
    for conv in CONVERSATIONS:
        sid, kept = None, []
        for q in conv:
            r = post(base, "/api/chat", {"message": q, "session_id": sid})
            print(f"{r['mode']:7} {r['elapsed_s']:6.1f}s {q[:70]}", flush=True)
            if r["mode"] != "llm" and not a.allow_offline:
                print("        (skipped: not written by the local model)")
                break
            sid = r["session_id"]
            kept.append({"message": q, "result": r, "first": not kept})
            evidence_ids.update(e["id"] for e in r["evidence"])
            evidence_ids.update(re.findall(r"\[([A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)*)\]", r["answer"]))
            for b in r["blocks"]:
                for key in ("csv_url", "mermaid_url"):
                    if b.get(key):
                        rec["files"][b[key]] = get(base, b[key], raw=True)
        if kept:
            rec["turns"] += kept
            try:
                rec["sessions"][sid] = get(base, f"/api/sessions/{sid}")
            except OSError:          # public-demo servers do not expose conversation snapshots
                pass
    for f in rec["library"]["findings"]:
        evidence_ids.add(f["id"])
    for eid in sorted(evidence_ids):
        try:
            rec["evidence"][eid] = get(base, "/api/evidence/" + urllib.parse.quote(eid))
        except OSError:
            pass
    for name in ("flex_tests", "flex_droplet_fits", "flex035_timeseries", "saffire_samples", "saffire2_flow", "bass2_tests",
                 "same_reduced", "same_r_detectors", "cfi_tests", "investigations"):
        try:
            rec["files"][f"/api/datasets/{name}.csv"] = get(base, f"/api/datasets/{name}.csv", raw=True)
        except OSError:
            pass

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "frontend", OUT)
    (OUT / "recorded.js").write_text("window.AEROFOX_RECORDED = " + json.dumps(rec, ensure_ascii=False) + ";\n", encoding="utf-8")
    shutil.copy(ROOT / "scripts" / "showcase_replay.js", OUT / "showcase_replay.js")
    html = (OUT / "index.html").read_text(encoding="utf-8")
    html = html.replace("<title>AeroFox — Flame in Freefall</title>", "<title>AeroFox Showcase</title>")
    html = html.replace('<script src="app.js"></script>',
                        '<script src="recorded.js"></script>\n<script src="showcase_replay.js"></script>\n<script src="app.js"></script>')
    (OUT / "index.html").write_text(html, encoding="utf-8")
    n = len(rec["turns"])
    print(f"showcase/ written: {n} recorded answers, {len(rec['evidence'])} sources, {len(rec['files'])} downloads")


if __name__ == "__main__":
    main()

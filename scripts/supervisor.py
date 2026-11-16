"""AeroFox supervisor: starts the local model, the web app and (optionally) a public tunnel, and keeps them alive.

    python scripts/supervisor.py                         # local only, port 8012
    python scripts/supervisor.py --tunnel cloudflare     # + free Cloudflare Quick Tunnel (random URL)
    python scripts/supervisor.py --tunnel cloudflare-named   # fixed URL; needs CLOUDFLARE_TUNNEL_TOKEN and AEROFOX_PUBLIC_URL
    python scripts/supervisor.py --tunnel tailscale      # fixed https://<machine>.<tailnet>.ts.net URL (Tailscale Funnel)

Every 10 s it checks each component and restarts only the one that failed, with increasing back-off.
Logs: logs/supervisor.log, logs/app.log, logs/llama-server.log, logs/cloudflared.log. State: logs/status.json.
Nothing here uses a paid service or exposes the model port: only the AeroFox web port is published.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
WINDOWS = os.name == "nt"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if WINDOWS else 0
_log_lock = threading.Lock()


def _load_dotenv(path: Path) -> None:
    """Same minimal .env reader as the backend: values already in the environment win."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with _log_lock:
        print(f"[AeroFox] {msg}", flush=True)
        with open(LOGS / "supervisor.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def rotate(path: Path, limit: int = 20 * 1024 * 1024) -> None:
    if path.exists() and path.stat().st_size > limit:
        path.replace(path.with_suffix(path.suffix + ".1"))


def http_ok(url: str, timeout: float = 5, want_json_key: str | None = None):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}) if "127.0.0.1" in url else urllib.request.ProxyHandler())
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "AeroFox-supervisor"}), timeout=timeout) as r:
            body = json.loads(r.read()) if want_json_key is not None else None
            return True, body
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__


def keep_awake() -> None:
    """Prevent Windows sleep while the supervisor runs (display may still turn off)."""
    if WINDOWS:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


class Component:
    """A child process with a health check and exponential back-off restarts."""

    def __init__(self, name: str, start, healthy, grace_s: float = 30, fails_to_restart: int = 3):
        self.name, self._start, self._healthy = name, start, healthy
        self.grace_s, self.fails_to_restart = grace_s, fails_to_restart
        self.proc = None
        self.started_at = 0.0
        self.fails = 0
        self.restarts = 0
        self.backoff = 5.0
        self.next_try = 0.0
        self.state = "stopped"
        self.detail = ""

    def start(self) -> None:
        try:
            self.proc = self._start()
            self.started_at, self.fails, self.state = time.time(), 0, "starting"
            log(f"{self.name}: started")
        except Exception as exc:  # noqa: BLE001
            self.state, self.detail = "failed", str(exc)[:300]
            self.next_try = time.time() + self.backoff
            log(f"{self.name}: start failed ({self.detail}); retry in {self.backoff:.0f} s")
            self.backoff = min(self.backoff * 2, 300)

    def stop(self) -> None:
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()

    def check(self) -> None:
        now = time.time()
        if self.state in ("failed", "stopped"):
            if now >= self.next_try:
                self.start()
            return
        dead = self.proc is not None and self.proc.poll() is not None
        ok = (not dead) and self._healthy()
        if ok:
            if self.state != "running":
                log(f"{self.name}: healthy")
            self.state, self.fails, self.backoff, self.detail = "running", 0, 5.0, ""
            return
        if self.state == "starting" and not dead and now - self.started_at < self.grace_s:
            return
        self.fails += 1
        self.detail = "process exited" if dead else f"health check failed ({self.fails}/{self.fails_to_restart})"
        if dead or self.fails >= self.fails_to_restart:
            log(f"{self.name}: {self.detail}; restarting (restart #{self.restarts + 1})")
            self.stop()
            self.restarts += 1
            self.state, self.next_try = "failed", now + self.backoff
            self.backoff = min(self.backoff * 2, 300)

    def info(self) -> dict:
        return {"state": self.state, "restarts": self.restarts, "detail": self.detail,
                "pid": self.proc.pid if self.proc and self.proc.poll() is None else None}


def python_exe() -> str:
    venv = ROOT / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
    return str(venv) if venv.exists() else sys.executable


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8012)
    ap.add_argument("--tunnel", choices=["none", "cloudflare", "cloudflare-named", "tailscale"], default="none")
    ap.add_argument("--model-profile", choices=["auto", "gpu", "cpu"], default="auto")
    ap.add_argument("--external-local-model", action="store_true",
                    help="monitor an already running model at AEROFOX_LLM_URL instead of starting it")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    for f in ("supervisor.log", "app.log", "cloudflared.log", "llama-server.log"):
        rotate(LOGS / f)
    keep_awake()
    log(f"supervisor starting (port {a.port}, tunnel {a.tunnel}, profile {a.model_profile})")

    env = dict(os.environ, PYTHONUTF8="1")
    if a.tunnel != "none":
        env["AEROFOX_PUBLIC_DEMO"] = "1"     # public mode: no conversation snapshots, no API docs
        env["AEROFOX_TRUST_PROXY"] = "1"     # rate-limit by the visitor address the tunnel forwards
    model_info = {"alias": env.get("AEROFOX_MODEL", "aerofox-qwen-1.5b"),
                  "endpoint": env.get("AEROFOX_LLM_URL", "http://127.0.0.1:8793")}

    # ------------------------------------------------------------------ model
    def start_model():
        if a.external_local_model:
            return None
        cmd = os.environ.get("AEROFOX_MODEL_CMD")          # Linux/macOS servers (see deploy/oracle)
        if cmd:
            fh = open(LOGS / "llama-server.log", "ab")
            return subprocess.Popen(shlex.split(cmd), stdout=fh, stderr=subprocess.STDOUT)
        import local_model
        proc, alias, endpoint = local_model.start_default(a.model_profile)
        model_info.update(alias=alias, endpoint=endpoint)
        return proc

    def model_healthy():
        import local_model
        return local_model.ready(model_info["endpoint"], model_info["alias"])

    model = Component("model", start_model, model_healthy, grace_s=300)

    # ------------------------------------------------------------------ app
    def start_app():
        e = dict(env, AEROFOX_MODEL=model_info["alias"], AEROFOX_LLM_URL=model_info["endpoint"])
        fh = open(LOGS / "app.log", "ab")
        return subprocess.Popen([python_exe(), "-m", "uvicorn", "aerofox.api.app:app", "--host", "127.0.0.1",
                                 "--port", str(a.port), "--no-access-log", "--timeout-keep-alive", "30"],
                                cwd=ROOT / "backend", env=e, stdout=fh, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)

    app_url = f"http://127.0.0.1:{a.port}"
    app = Component("app", start_app, lambda: http_ok(app_url + "/api/health", 5)[0], grace_s=60)

    # ------------------------------------------------------------------ tunnel
    public = {"url": os.environ.get("AEROFOX_PUBLIC_URL", "") if a.tunnel in ("cloudflare-named", "tailscale") else ""}

    def find_cloudflared():
        for c in (shutil.which("cloudflared"), r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                  r"C:\Program Files\cloudflared\cloudflared.exe", str(ROOT / "tools" / "cloudflared.exe")):
            if c and Path(c).exists():
                return c
        raise RuntimeError("cloudflared not found (Windows: winget install --id Cloudflare.cloudflared)")

    def start_tunnel():
        if a.tunnel == "cloudflare":
            public["url"] = ""
            p = subprocess.Popen([find_cloudflared(), "tunnel", "--no-autoupdate", "--protocol", "http2",
                                  "--url", app_url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 creationflags=NO_WINDOW)

            def read():
                with open(LOGS / "cloudflared.log", "a", encoding="utf-8") as fh:
                    for line in p.stdout:
                        fh.write(line)
                        fh.flush()
                        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                        if m and public["url"] != m.group(0):
                            public["url"] = m.group(0)
                            (LOGS / "public_url.txt").write_text(public["url"] + "\n")
                            log("=" * 60)
                            log(f"PUBLIC LINK: {public['url']}")
                            log("=" * 60)
            threading.Thread(target=read, daemon=True).start()
            return p
        if a.tunnel == "cloudflare-named":
            token = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN")
            if not token or not public["url"]:
                raise RuntimeError("set CLOUDFLARE_TUNNEL_TOKEN and AEROFOX_PUBLIC_URL (see docs/ESTABILIDADE.md)")
            fh = open(LOGS / "cloudflared.log", "ab")
            # the token is passed through the environment, never on the command line or in logs
            return subprocess.Popen([find_cloudflared(), "tunnel", "--no-autoupdate", "run"],
                                    env=dict(os.environ, TUNNEL_TOKEN=token), stdout=fh, stderr=subprocess.STDOUT,
                                    creationflags=NO_WINDOW)
        if a.tunnel == "tailscale":
            ts = shutil.which("tailscale") or r"C:\Program Files\Tailscale\tailscale.exe"
            subprocess.run([ts, "funnel", "--bg", str(a.port)], check=True, capture_output=True, timeout=60)
            if not public["url"]:
                out = subprocess.run([ts, "status", "--json"], capture_output=True, text=True, timeout=30).stdout
                public["url"] = "https://" + json.loads(out)["Self"]["DNSName"].rstrip(".")
            log(f"PUBLIC LINK (fixed): {public['url']}")
            return None
        return None

    def tunnel_healthy():
        if not public["url"]:
            return False
        ok, body = http_ok(public["url"] + "/api/health", 15, "status")
        return ok and isinstance(body, dict) and body.get("status") == "ok"

    # A Quick Tunnel gets a NEW random URL when restarted, so it is only restarted when its process dies or the public
    # health check has failed for ~10 minutes (cloudflared reconnects by itself after short network drops).
    tunnel = (Component("tunnel", start_tunnel, tunnel_healthy, grace_s=90,
                        fails_to_restart=10 if a.tunnel == "cloudflare" else 3) if a.tunnel != "none" else None)

    # ------------------------------------------------------------------ run
    stopping = threading.Event()

    def shutdown(*_):
        stopping.set()
    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    model.start()
    opened = False
    last_tunnel_check = 0.0
    try:
        while not stopping.is_set():
            model.check()
            if model.state == "running" or a.external_local_model:
                if app.state == "stopped" and app.proc is None and app.restarts == 0 and app.next_try == 0:
                    app.start()
                else:
                    app.check()
            if tunnel and app.state == "running":
                if tunnel.state == "stopped" and tunnel.restarts == 0 and tunnel.next_try == 0:
                    tunnel.start()
                elif time.time() - last_tunnel_check >= 60 or tunnel.state != "running":
                    last_tunnel_check = time.time()
                    tunnel.check()
            if app.state == "running" and not opened and not a.no_browser:
                opened = True
                import webbrowser
                webbrowser.open(app_url)
            status = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "local_url": app_url, "public_url": public["url"],
                      "model": {**model.info(), **model_info}, "app": app.info(),
                      "tunnel": tunnel.info() if tunnel else None}
            (LOGS / "status.json").write_text(json.dumps(status, indent=1))
            stopping.wait(10)
    finally:
        log("supervisor stopping")
        for c in (tunnel, app, model):
            if c:
                c.stop()


if __name__ == "__main__":
    main()

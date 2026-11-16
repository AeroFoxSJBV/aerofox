/* AeroFox showcase: answers the interface's /api calls from answers recorded with build_showcase.py.
   Nothing is generated here. Questions that were not recorded get an honest message pointing to the live demo. */
(() => {
  "use strict";
  const R = window.AEROFOX_RECORDED;
  const norm = (s) => String(s || "").trim().replace(/\s+/g, " ").toLowerCase();
  const byPair = new Map(), byText = new Map();
  for (const t of R.turns) {
    byPair.set(t.result.session_id + "|" + norm(t.message), t);
    if (t.first && !byText.has(norm(t.message))) byText.set(norm(t.message), t);
  }
  const firsts = R.turns.filter((t) => t.first).map((t) => t.message);
  const jobs = {};
  const hex = (n) => Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => b.toString(16).padStart(2, "0")).join("");
  const reply = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "X-Request-ID": "showcase" } });
  const realFetch = window.fetch.bind(window);

  function notRecorded(sid, text) {
    const pt = /[ãõçáéíóú]|\b(você|voce|qual|como|mostre|explique)\b/i.test(text);
    return {
      session_id: sid || hex(16), request_id: "showcase", mode: "offline", model: null, language: pt ? "pt" : "en",
      notice: pt ? "Vitrine gravada: esta pergunta não foi gravada." : "Recorded showcase: this question was not recorded.",
      answer: (pt ? "Esta página é uma vitrine estática com respostas reais gravadas do modelo local do AeroFox. Ela não gera respostas novas. Experimente uma das perguntas gravadas:\n"
                  : "This page is a static showcase of real answers recorded from AeroFox's local model. It cannot write new answers. Try one of the recorded questions:\n")
        + firsts.map((q) => "- " + q).join("\n"),
      blocks: [], evidence: [], warnings: [], verified_results: [], project: {}, project_changes: {}, tools: [],
      usage: null, generation: { status: "showcase" }, elapsed_s: 0,
    };
  }

  window.fetch = async (input, opts = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const i = url.pathname.indexOf("/api/");
    if (i < 0) return realFetch(input, opts);
    const path = url.pathname.slice(i), method = (opts.method || "GET").toUpperCase();
    await new Promise((r) => setTimeout(r, 60));
    let m;
    if (path === "/api/health") return reply(R.health);
    if ((m = path.match(/^\/api\/library\/(\w+)$/))) return R.library[m[1]] ? reply(R.library[m[1]]) : reply({ detail: "not found" }, 404);
    if ((m = path.match(/^\/api\/evidence\/(.+)$/))) {
      const e = R.evidence[decodeURIComponent(m[1])];
      return e ? reply(e) : reply({ detail: "This source was not included in the recorded showcase." }, 404);
    }
    if (path === "/api/sessions" && method === "POST") return reply({ session_id: hex(16), project: {} });
    if ((m = path.match(/^\/api\/sessions\/([a-f0-9]+)\/project$/))) return reply({ detail: "Project inputs need the live AeroFox server; this page only replays recorded answers." }, 403);
    if ((m = path.match(/^\/api\/sessions\/([a-f0-9]+)$/))) return R.sessions[m[1]] ? reply(R.sessions[m[1]]) : reply({ detail: "unknown session" }, 404);
    if (path === "/api/chat/jobs" && method === "POST") {
      const body = JSON.parse(opts.body || "{}");
      const t = byPair.get((body.session_id || "") + "|" + norm(body.message)) || byText.get(norm(body.message));
      const id = hex(16);
      jobs[id] = { t0: Date.now(), result: t ? t.result : notRecorded(body.session_id, body.message), tools: t ? t.result.tools.map((x) => x.name) : [] };
      return reply({ job_id: id, request_id: "showcase" });
    }
    if ((m = path.match(/^\/api\/chat\/jobs\/([a-f0-9]{32})$/))) {
      const job = jobs[m[1]];
      if (!job) return reply({ detail: "unknown job" }, 404);
      // A short replay of the stages the live server reports; the recorded answer keeps its real timing.
      const dt = Date.now() - job.t0, all = [{ type: "status", stage: "planning" }];
      if (dt > 900) all.push({ type: "status", stage: "tools", tools: job.tools });
      if (dt > 1800) all.push({ type: "status", stage: "answering" });
      const after = +url.searchParams.get("after") || 0, done = dt > 2600;
      return reply({ events: all.slice(after), next: all.length, done, result: done ? job.result : null });
    }
    return reply({ detail: "Not available in the recorded showcase." }, 404);
  };

  // Downloads (CSV / Mermaid) come from the recording instead of the server.
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[download]");
    if (!a) return;
    const path = new URL(a.getAttribute("href"), location.href).pathname, i = path.indexOf("/api/");
    if (i < 0) return;
    e.preventDefault();
    const text = R.files[path.slice(i)];
    if (text == null) { alert("This file was not included in the recorded showcase."); return; }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([text], { type: path.endsWith(".csv") ? "text/csv" : "text/plain" }));
    link.download = path.split("/").pop();
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 5000);
  }, true);

  // A clear label: this is a recording, with the date and model, plus the recorded questions as one-click chips.
  document.addEventListener("DOMContentLoaded", () => {
    const note = document.createElement("div");
    note.className = "showcase-note";
    note.innerHTML = `<p><strong>Recorded showcase.</strong> Real answers from AeroFox's local open-weight model (${R.model}, ${R.runtime}), recorded on ${R.recorded_at}. Nothing on this page is generated live. Pick a recorded question:</p><div class="showcase-chips"></div>`;
    for (const q of firsts) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip-btn"; b.textContent = q;
      b.onclick = () => { const input = document.querySelector("#input"); input.value = q; document.querySelector("#composer").requestSubmit(); };
      note.querySelector(".showcase-chips").append(b);
    }
    const engine = document.querySelector("#engineLabel");
    new MutationObserver(() => {
      if (engine.textContent.startsWith("Local model ready")) engine.textContent = engine.textContent.replace("Local model ready", "Recorded answers");
    }).observe(engine, { childList: true, characterData: true, subtree: true });
    const lede = document.querySelector(".lede");
    lede.after(note);
    const follow = R.turns.filter((t) => !t.first).map((t) => t.message);
    if (follow.length) document.querySelector("#input").placeholder = `Recorded follow-ups: ${follow.join(" · ")}`;
    const st = document.createElement("style");
    st.textContent = ".showcase-note{max-width:760px;margin:14px auto 4px;padding:12px 14px;border:1px dashed #c55a11;border-radius:10px;font-size:13px;text-align:left;background:rgba(197,90,17,.05)}.showcase-note p{margin:0 0 8px}.showcase-chips{display:flex;flex-wrap:wrap;gap:6px}.showcase-chips .chip-btn{white-space:normal;text-align:left}";
    document.head.append(st);
  });
})();

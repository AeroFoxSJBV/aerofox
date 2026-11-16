# Project presentation: https://drive.google.com/file/d/1IigNrD4RkP0JqnkyVig3a6cp-zgWLfEA/view?usp=sharing

# Usage Example: https://github.com/user-attachments/assets/240509f2-f080-4744-af4f-53fd5e23e7c7


# 🦊 AeroFox: Evidence-Grounded Spacecraft Fire Safety Assistant

> **NASA Space Apps Challenge 2026** | Challenge: *Flame in Freefall* | Developed by Team **AeroFox**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Verification tests: 74 passed](https://img.shields.io/badge/verification%20tests-74%20passed-brightgreen.svg)](tests/)

---

## 📌 Overview & Scope

AeroFox is an evidence-grounded engineering workbench designed to summarize, query, and interpret microgravity combustion data from NASA's Physical Sciences Informatics (PSI) repository.

Rather than relying on an ungrounded black-box LLM, AeroFox strictly decouples:

1. **Curated NASA Experimental Snapshots:** 24 combustion investigations and 22 experiment tables from NASA PSI.
2. **Deterministic Scientific Tools:** Verified Python routines for linear regression (droplet burning rates), unit conversions, exploration atmosphere mapping, and multi-zone passive tracer transport.
3. **Local Open-Weight Inference:** Query planning and concise synthesis using open-weight Qwen models running locally via llama.cpp without third-party API dependencies.

---

## 🔬 Core Scientific Audits & Findings

* **FLEX Identifier Reconciliation:** Reconciled 119 mismatched test rows in the PSI-69 FLEX table using Combustion Integrated Rack (CIR) identifiers, restoring droplet burning rate correlation from r = 0.729 to r = 0.987.
* **Saffire-II Flow Telemetry Discrepancy:** Uncovered that specimen 2-6 experienced actual anemometer flow around 25 cm/s, resolving a discrepancy with the nominal 20 cm/s catalog entry.
* **Post-Extinction Droplet Regression (FLEX-035):** Captured continuing droplet shrinkage after optical hot-flame extinction, separating physical observation from published cool-flame hypotheses.
* **Exploration Atmosphere Mapping:** Evaluated candidate Artemis exploration atmospheres (e.g., 56.5 kPa / 34% O2) against archived solid-fuel tests, exposing direct microgravity coverage gaps.

---

## 🚀 Quick Start (Windows)

Requires [Python 3.11 or 3.12 (64-bit)](https://www.python.org/downloads/windows/).

```
git clone https://github.com/AeroFoxSJBV/aerofox
cd aerofox
START_AEROFOX.bat
```

Note: On first startup, START\_AEROFOX.bat automatically verifies SHA-256 checksums, downloads the pinned llama.cpp runtime and GGUF weights, and launches the interface at http://127.0.0.1:8000. On a computer without a compatible NVIDIA GPU, run `START_AEROFOX.bat --model-profile cpu`. To publish your own copy on the internet, use `START_AEROFOX_PUBLICO.bat` (see [docs/ESTABILIDADE.md](docs/ESTABILIDADE.md)). For macOS or Linux, see [docs/MODEL_RUNTIME.md](docs/MODEL_RUNTIME.md).

---

## 🌐 Live Prototype & Infrastructure Notes

> **Live Demo URL:** https://aerofox-ex0thermic.tail2885d4.ts.net *(fixed address, hosted on a team member's computer via Tailscale Funnel)*
>
> **Static Showcase:** https://aerofoxsjbv.github.io/aerofox/ *(GitHub Pages, always online)*

### ⚠️ Important Notice for Reviewers & Judges:

AeroFox was designed and built within the 48-hour window of the NASA Space Apps Challenge, and from the start we chose to keep it **100% free and independent**: no paid cloud GPU, no commercial AI API and no subscription of any kind. The live demo therefore runs on one team member's laptop, an NVIDIA RTX 3050 with 6 GB of memory running the open-weight Qwen3-4B model through llama.cpp, and reaches the internet through a free Tailscale Funnel link. That choice keeps every answer reproducible and the whole evidence pipeline under our control, but it also means the live demo inherits the limits of a single home computer:

* **One Answer at a Time:** A laptop GPU only has room for one copy of the model, so visitors wait in a visible queue of up to six people, each seeing their position and an estimated time. A typical answer takes 15 to 60 seconds, and longer when several judges ask at the same moment.
* **Potential Intermittent Availability:** The demo is only reachable while that laptop is on, awake and online. A power cut, an automatic Windows update or a drop in the home internet connection makes the link unreachable until the machine is back. The address itself is fixed and does not change when the computer restarts.
* **Self-Healing, but not Instant:** A supervisor checks the model, the web application and the tunnel every 10 seconds and restarts whatever fails. In our tests the application recovered on its own in about 20 seconds and the model in about one minute. During that minute, answers come from the deterministic offline evidence engine, which is clearly labelled in the interface. If you see *"Cannot reach the AeroFox server"*, refreshing the page after a few seconds is usually enough.
* **Offline / Local Verification:** If the live link is slow or unavailable, the [static showcase](https://aerofoxsjbv.github.io/aerofox/) shows the real interface replaying answers recorded from the local model (CPU profile, Qwen2.5-1.5B), and the entire application can be reproduced on any Windows machine with `START_AEROFOX.bat`. Our recorded demonstration pitch and the technical documentation in the `docs/` and `reports/` folders are also available.

### 🛠️ What Changed in v1.1.2 (Stability Release)

Version 1.1.2 keeps the same model, NASA data, scientific tools and prompts as v1.1.1. It only changes how the application stays online when several judges use it at once:

* **No More Cut-Off Answers:** The browser starts each answer as a background job and checks its progress every second, so long answers are never dropped by the tunnel. Visitors see the current step (*"Waiting for the model: position 2"*, *"Computing with NASA data…"*, *"Writing the answer…"*) and a live timer.
* **A Real Queue:** Up to six visitors wait for the local model for up to 240 seconds, instead of falling back to the offline engine after 25 seconds.
* **Supervisor with Automatic Restarts:** `scripts/supervisor.py` watches every component, restarts only what failed and keeps logs in `logs/`.
* **Fixed Public Address:** A free Tailscale Funnel link replaces the temporary Cloudflare Quick Tunnel address that changed on every restart (Quick Tunnel is still supported).
* **Conversations Survive Restarts:** Sessions are stored in SQLite and expire after 6 hours.
* **Guard Against Empty Answers:** Replies made only of headings and citations are rejected and regenerated.
* **Transparent Health Check:** `/api/health` reports how many answers came from the model and how many from the offline engine, and why.

**Verified on the demo host:** 74/74 automated tests passed; 3 simultaneous judges through the public link received 3/3 answers written by the local model; forced-crash tests recovered automatically (application ~20 s, model ~1 min). Full details (in Portuguese): [docs/ESTABILIDADE.md](docs/ESTABILIDADE.md) and [MUDANCAS_ESTABILIDADE.md](MUDANCAS_ESTABILIDADE.md), with raw numbers in [reports/stability_comparison_1.1.2.json](reports/stability_comparison_1.1.2.json).

---

## 🛰️ NASA Data Lineage

* **NASA PSI Accessions:** PSI-69 (FLEX), PSI-99 (Saffire-II), PSI-101 (SAME-R), PSI-25 (BASS-II), PSI-117.
* **NASA Technical Publications (NTRS):** NASA/TP-2015-216046 (FLEX), NTRS 20170008805 (Saffire), NTRS 20210011385 (BASS-II), NTRS 20130000422 (SAME-R), NTRS 20260002050 (Exploration Atmospheres).
* **Standards:** NASA-STD-6001B (Material Flammability), NASA-STD-7009B (Models and Simulations Credibility).

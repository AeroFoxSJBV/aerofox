```
# 🦊 AeroFox: Evidence-Grounded Spacecraft Fire Safety Assistant

&gt; **NASA Space Apps Challenge 2026** | Challenge: *Flame in Freefall*  
&gt; Developed by Team **AeroFox**

[![License: Apache 2.0](https://github.com/hannaginsicke/aerofox)](LICENSE) [![Verification Tests: 59 Passed](https://github.com/hannaginsicke/aerofox)](tests/)

## 📌 Overview &amp; Scope
AeroFox is an evidence-grounded engineering workbench designed to summarize, query, and interpret microgravity combustion data from NASA's Physical Sciences Informatics (PSI) repository.

Rather than relying on an ungrounded black-box LLM, AeroFox strictly decouples:
1. **Curated NASA Experimental Snapshots:** 24 combustion investigations and 22 experiment tables from NASA PSI.
2. **Deterministic Scientific Tools:** Verified Python routines for linear regression (droplet burning rates), unit conversions, exploration atmosphere mapping, and multi-zone passive tracer transport.
3. **Local Open-Weight Inference:** Query planning and concise synthesis using open-weight Qwen models running locally via llama.cpp without third-party API dependencies.

---

## 🔬 Core Scientific Audits &amp; Findings
- **FLEX Identifier Reconciliation:** Reconciled 119 mismatched test rows in the PSI-69 FLEX table using Combustion Integrated Rack (CIR) identifiers, restoring droplet burning rate correlation from r = 0.729 to r = 0.987.
- **Saffire-II Flow Telemetry Discrepancy:** Uncovered that specimen 2-6 experienced actual anemometer flow around 25 cm/s, resolving a discrepancy with the nominal 20 cm/s catalog entry.
- **Post-Extinction Droplet Regression (FLEX-035):** Captured continuing droplet shrinkage after optical hot-flame extinction, separating physical observation from published cool-flame hypotheses.
- **Exploration Atmosphere Mapping:** Evaluated candidate Artemis exploration atmospheres (e.g., 56.5 kPa / 34% O₂) against archived solid-fuel tests, exposing direct microgravity coverage gaps.

---

## 🚀 Quick Start (Windows)
```bash
git clone https://github.com/hannaginsicke/aerofox
cd aerofox
START_AEROFOX.bat

## 🌐 Live Prototype &amp; Infrastructure Notes

An interactive demonstration instance of the AeroFox interface is accessible via a temporary tunnel during judging:

&gt; **Live Demo URL:** https://treo-usc-hardcover-stops.trycloudflare.com *(Hosted via Cloudflare Quick Tunnel on a local host machine)*

### ⚠️ Important Notice for Reviewers &amp; Judges:

* **Ephemeral Session Architecture:** Due to hackathon infrastructure constraints and to avoid third-party proprietary hosting costs, this live prototype runs on a local development host linked through a free Cloudflare Quick Tunnel.
* **Potential Intermittent Availability:** If the host machine enters sleep mode, restarts, or experiences a network disconnection, the tunnel session may close or regenerate with a new endpoint.
* **Offline / Local Verification:** In the event that the live tunnel link is momentarily unreachable, the entire AeroFox application can be reproduced deterministically on any Windows machine using the provided `START_AEROFOX.bat` script, or verified through our recorded demonstration pitch and technical documentation in the `docs/` and `reports/` folders.

```

Note: On first startup, START\_AEROFOX.bat automatically verifies SHA-256 checksums, downloads the pinned llama.cpp runtime and GGUF weights, and launches the interface at http://127.0.0.1:8000.

---

## 🛰️ NASA Data Lineage

* **NASA PSI Accessions:** PSI-69 (FLEX), PSI-99 (Saffire-II), PSI-101 (SAME-R), PSI-25 (BASS-II), PSI-117.
* **NASA Technical Publications (NTRS):** NASA/TP-2015-216046 (FLEX), NTRS 20170008805 (Saffire), NTRS 20210011385 (BASS-II), NTRS 20130000422 (SAME-R), NTRS 20260002050 (Exploration Atmospheres).
* **Standards:** NASA-STD-6001B (Material Flammability), NASA-STD-7009B (Models and Simulations Credibility).

# AI assistance disclosure

AI coding assistants (Claude Code, by Anthropic, and OpenAI Codex) supported the team in three areas:

- **Code optimization:** reviewing and refactoring the backend, the web interface and the scientific tools, and writing automated tests that check every change.
- **Stability:** improving how the live demo stays online when several people use it at once: the visible queue for the local model, answers produced in the background with progress updates, a supervisor that restarts failed components automatically, and load and crash tests.
- **Data organization:** helping structure the NASA snapshot (file inventories, the data dictionary, checksums and provenance records) so that every value can be traced back to its NASA source.

The team reviewed every change and is responsible for the scientific analysis, its interpretation and the conclusions. No AI-generated records were added to NASA data: every measurement comes from the sources listed in [DATA_SOURCES.md](DATA_SOURCES.md).

The running app uses a local open-weight Qwen model for tool planning and generated synthesis. Compartment calculations, numerical analyses and figures are produced from scientific code and the verified NASA snapshot. Synthetic scenarios are labeled.

Consult the [Space Apps participant terms](https://www.spaceappschallenge.org/legal/) before submission.

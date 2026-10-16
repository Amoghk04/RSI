# Open questions

Rule: if something is ambiguous or blocking, write it here and continue with the most conservative interpretation. Do not silently invent requirements.

Status: `open` | `assumed` | `resolved`.

---

### Q-001: Model, provider, and dollar budget
- Status: **resolved** (2026-10-15)
- Answer: **OpenRouter**, prototype cap **$50** total; increase budget only if dev signals are good.
- Defaults: `configs/base.yaml` — `google/gemini-2.5-flash` for agent, user-sim, and proposer; `total_dollars: 50`, `per_round_dollars: 4`, `per_candidate_dollars: 1`. Verify slug/pricing on OpenRouter before M6 paid runs.
- Env: `OPENROUTER_API_KEY` (see `.env.example`).

### Q-002: Confirm telecom compositional pool is usable
- Status: **resolved** (2026-10-15) — agent decision, owner delegated
- Answer: Upstream `tasks.json` ships **all 2,285** telecom tasks (MIT). **`test` = upstream `base` (114)**. **`opt` / `val` / `select` = stratified sample from pool = full \\ base (2,171 tasks)**. Do **not** use upstream `train`/`test` keys as our splits (`train` overlaps `base`). Generator: `scripts/make_splits.py`; rules in `data/splits/README.md`. Pin `tau2_bench_commit` in manifest at freeze.

### Q-003: ITBench variant and task identity
- Status: open — **blocks M11, but verify before M6 so we do not over-promise**
- Need: ITBench-Lite SRE (35 snapshots, Apache 2.0) vs ITBench-AA public (40)? Are they the same incidents under different ids? Can `ROOT_CAUSE_ENTITY` be scored by string/structure match without a judge?
- Conservative until answered: adapter targets Lite SRE snapshots; headline scorer is our entity match (D-003); treat n≈35 as underpowered and allow an "inconclusive" label.

### Q-004: Seeds and split ratios given budget
- Status: **resolved for prototype** (2026-10-15); revisit at freeze if budget increases
- Answer: **2 seeds** (`[0, 1]`) for all prototype / Phase A runs. At freeze, use **3 seeds** for Phase C only if ≥$15 remains after dev and ablations. Split ratios on telecom pool: 40% / 20% / 15% opt/val/select (see `data/splits/README.md`).

### Q-005: H4 second-model experiment?
- Status: open
- Need: yes/no, and which second model (API vs quantized 7B–14B on Kaggle).
- Conservative: implement the `LLMClient` open-model backend, do not schedule H4 runs until answered.

### Q-006: Released-code license
- Status: **resolved** (2026-10-15) — **not** a substitute for lawyer review
- Answer: **AGPL-3.0** for the public repo (true open source, OSI). **Commercial use** that cannot comply with AGPL requires a **separate commercial license** — see `docs/COMMERCIAL.md` and `LICENSE`. Before launch: paste full AGPL text, audit deps in `docs/LICENSES.md`, add contact email in `COMMERCIAL.md`.
- Public posts may say "open source (AGPL)" only after that audit; until then treat as unpublished.

### Q-007: User-simulator failure policy on τ²
- Status: assumed (conservative)
- Assumption: if the benchmark flags a user-sim hallucination / instruction deviation, **re-run that (task, seed) once**; if still flagged, mark the trial `invalid` and exclude it from both arms of the pair. Same rule for every condition. Do not feed invalid traces to the diagnoser.
- Confirm or override before freeze.

### Q-008: Public narrative vs scientific claims
- Status: assumed
- Assumption: LinkedIn / X posts may describe the project and cite **already-written** ledger entries. They MUST NOT cite unpublished `test` numbers, MUST distinguish Phase A (dev) from Phase C (frozen), and MUST NOT use the word "RSI" as a claim of recursive self-modification of weights. See DESIGN.md §1.1 and §17.
- Confirm tone before first public post.

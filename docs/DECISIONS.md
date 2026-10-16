# Decisions log

Rule: every change that touches **YELLOW** code or a **RED** invariant gets an entry here (what, why, impact on past results). Owner-approved RED changes are marked **RED-APPROVED**.

Format:

```
### D-<nnn>: <short name>
- Date:
- Zone: RED | YELLOW | GREEN
- What changed:
- Why:
- Impact on past results:
- Owner:
```

---

### D-001: Four-way splits (`opt` / `val` / `select` / `test`)
- Date: 2026-10-15
- Zone: RED
- What changed: Split protocol now has a fourth split, `select`. `val` may be subsampled and rotated during the loop. `select` is frozen, never shown to proposers/diagnosers, and used once to re-score top-K champions before finalist promotion. `test` remains append-only and unseen until Phase C.
- Why: Repeatedly querying the same `val` tasks is adaptive data analysis. Independent val-gated loops have shown +val / ~0 test. A one-shot `select` audit catches that before freeze.
- Impact on past results: none (no runs yet). Future runs that omit `select` are not comparable.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-002: Dev benchmark is τ² telecom, not airline
- Date: 2026-10-15
- Zone: YELLOW (benchmark choice before freeze)
- What changed: Development slice is **telecom**, not airline. Preferred split construction: `opt`/`val`/`select` drawn from the compositional pool excluding the official 114-task subsample; official 114 is `test`. Fallback if the pool is not shippable: power-aware split of the 114, documented as underpowered.
- Why: Airline has 50 tasks (gate would see ~10 `val` tasks) and 40–47% user-simulator error. Telecom has 114 official tasks, a 2,285-task generator, and 16% simulator error (6% critical).
- Impact on past results: none.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-003: ITBench headline metric is programmatic entity match, not the official judge toolkit
- Date: 2026-10-15
- Zone: RED (I1: scorers programmatic) / YELLOW (adapter)
- What changed: For ITBench-Lite / ITBench-AA, the **headline** score is entity precision/recall/F1 (and pass/fail derived from it) computed in our adapter by matching the agent's structured diagnosis against `ground_truth.yaml`. Official LLM-as-judge metrics (`ROOT_CAUSE_REASONING`, etc.) are **not** in the main results. They MAY be logged as unlabeled diagnostics, never fed to the loop.
- Why: I1 and the non-goal "no LLM-as-judge in headline numbers." The official evaluation toolkit is judge-based for reasoning metrics.
- Impact on past results: none. Numbers will **not** be comparable to ITBench-Evaluations leaderboard rows that use a judge. State this in every table.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-004: A/A noise-floor gating and rotating `val`
- Date: 2026-10-15
- Zone: GREEN (gate variant) with YELLOW validator support
- What changed: Default gate family is G3 plus (a) reject unless paired delta exceeds a calibrated A/A noise floor and (b) `val` subsets rotate; scores compared via a sampling-weighted estimator. Leakage linter is a hard reject.
- Why: Mean-delta > 0 on a reused `val` set accepts noise. Rotation without a Horvitz–Thompson / Hájek correction makes rounds incomparable.
- Impact on past results: none.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-005: Itemized playbook surface (ACE-style) as the default notes representation
- Date: 2026-10-15
- Zone: YELLOW (`HarnessSpec` artifact shape)
- What changed: Notes/skills artifacts default to an itemized playbook: bullets with stable IDs, edited only via ADD / UPDATE / REMOVE. Full-document rewrite of notes is an explicitly named strategy, not the default. A prune pass (drop a bullet if `val` does not get worse) is a regularizer, not a required gate.
- Why: Repeated full rewrites cause brevity bias and context collapse. Bounded typed edits already exist (I10); bullets make credit assignment and prune possible.
- Impact on past results: none.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-006: GEPA baseline is `optimize_anything`; ACE is baseline B4
- Date: 2026-10-15
- Zone: YELLOW (experiment runner / baselines)
- What changed: B1 uses GEPA's `optimize_anything` API with `dict[str, str]` candidates, shared train/val, held-out `test_set` unused during opt, and `max_token_cost` matched to our all-in token budget. New baseline **B4: ACE** (Generator / Reflector / Curator, incremental deltas) under the same budget and splits.
- Why: `optimize_anything` (2026) is the current GEPA entry point and already has generalization mode. ACE is the closest competitor for the notes surface; omitting it would overstate novelty.
- Impact on past results: none.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-007: Matched budget counts every token
- Date: 2026-10-15
- Zone: RED (I5 / I8 clarification)
- What changed: The matched optimization budget includes agent rollouts, user-simulator calls, diagnoser, proposer, and any ACE/GEPA reflection. Not proposer-only.
- Why: τ² cost is dominated by conversation rollouts. Matching proposer tokens only would favor our loop.
- Impact on past results: none.
- Owner: Amogh (explicit approval, 2026-10-15)

### D-009: OpenRouter prototype budget and default models (Q-001)
- Date: 2026-10-15
- Zone: YELLOW (configs)
- What changed: Provider OpenRouter; hard cap $50 total; default model `google/gemini-2.5-flash` for agent, user_sim, proposer; caps in `configs/base.yaml`.
- Why: Owner prototype budget; single model for matched comparisons (I8).
- Impact on past results: none.
- Owner: Amogh

### D-010: AGPL-3.0 public license + commercial license path (Q-006)
- Date: 2026-10-15
- Zone: YELLOW (legal/docs)
- What changed: Public license AGPL-3.0 (`LICENSE`, `docs/COMMERCIAL.md`). Production / proprietary embedding requires a commercial license from the copyright holder.
- Why: Owner wants free OSS use and paid commercial use. AGPL is OSI-approved; copyleft drives commercial conversations without blocking research.
- Impact on past results: none. Dependency compatibility MUST be checked before release (some deps may be incompatible with strong copyleft).
- Owner: Amogh

### D-011: τ² telecom manifest from full pool minus `base` (Q-002)
- Date: 2026-10-15
- Zone: RED (split construction) / YELLOW (generator script)
- What changed: `test` = upstream `base` (114). `opt`/`val`/`select` from 2,171-task pool (all `tasks.json` ids minus `base`), stratified by intent and subtask depth. `scripts/make_splits.py` + `data/splits/README.md`.
- Why: Full compositional pool ships in repo; holding out `base` prevents leaderboard-task leakage into the loop.
- Impact on past results: none until first manifest is committed.
- Owner: Amogh (delegated to agent)

### D-015: Telecom tool surfaces are recorded and shown to the proposer
- Date: 2026-10-16
- Zone: YELLOW
- What changed: Live traces include `agent_tools` and `user_tools` from the τ² telecom toolkits. The default harness tells the agent to ask the user for device actions. `configs/tau2-dev.yaml` sets `champion_audit: false`. Names are also written in `docs/ONBOARDING.md`.
- Why: The agent was calling user-device tools and getting "tool not found". A full loop that then scores all 325 `select` tasks is not the dev command.
- Impact on past results: none. Earlier slice harnesses keep their old ids. New runs start from a new default harness id.
- Owner: Amogh (delegated to agent)

### D-014: Live τ² traces do not supply task ids as playbook hints
- Date: 2026-10-16
- Zone: YELLOW
- What changed: A failed live telecom episode no longer appends `diagnosis_hint` with `missing_token` set to the task id. P2 still copies toy and mock skill tokens into the playbook, and it refuses a hint or model edit whose text is a task id.
- Why: The live smoke accepted a playbook bullet that was the failed task id. That memorizes the task name. Toy `TOK-A` hints stay, because the reference loop depends on them.
- Impact on past results: none. The smoke accept is not a baseline. Later P2 runs will call the proposer model when there is no skill token.
- Owner: Amogh (delegated to agent)

### D-013: Debug runs may skip ChampionAudit
- Date: 2026-10-16
- Zone: YELLOW
- What changed: `loop.champion_audit` defaults to true. When false, the orchestrator finishes on the current harness and does not read `select`. Guard-set refresh is limited to `val_tasks_per_round`.
- Why: A one-round live smoke was scoring all 325 telecom `select` tasks after the loop, including when nothing was accepted. `select` is reserved for the one-shot finalist audit (D-001, M9).
- Impact on past results: none. The stopped smoke run is not a baseline. Configs that omit the field still audit.
- Owner: Amogh (delegated to agent)

### D-012: τ² adapter uses harness instructions + optional live bridge (M6)
- Date: 2026-10-16
- Zone: YELLOW
- What changed: `adapters/tau2/` with mock-domain CI path (`tau2_mock.json`), committed `tau2_telecom.json`, LLM bridge into τ² `generate()` when `use_live_tau2`, baselines B0/B2/B3 CLI, strategies `p1_naive` + `g0_always`.
- Why: M6 acceptance — dev telecom adapter, logged baselines, cost-by-role, user-sim exclusion counters.
- Impact on past results: none (new benchmark path).
- Owner: Amogh (delegated to agent)

### D-008: Product trajectory is out of band of the scientific protocol
- Date: 2026-10-15
- Zone: YELLOW (docs only)
- What changed: DESIGN.md §1.1 records a long-term product intent (governed RSI for third-party agents; later, governed weight updates). That intent MUST NOT change invariants, splits, scorers, or what we claim from Phase C.
- Why: The v1 artifact is a credible, pre-registered benchmark proof. Mixing startup narrative into results is a defect.
- Impact on past results: none.
- Owner: Amogh (explicit approval, 2026-10-15)

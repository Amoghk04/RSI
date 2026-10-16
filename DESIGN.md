# RSI-Harness: Design Document (v0.2)

Working name: `rsi-harness`. Rename freely.

**Audience:** the Cursor agent that builds this repo, and the owner who reviews it.
**Status:** draft for build. v0.2 incorporates owner-approved changes from 2026-10-15 (see `docs/DECISIONS.md` D-001–D-008). Sections marked MUST are fixed. Sections marked MAY are open for experimentation.

---

## 0. How to use this document

1. Read the whole document before writing code.
2. Words mean what they say: **MUST** = non-negotiable, **SHOULD** = default unless you record a reason, **MAY** = your call.
3. The repo has three zones (see section 14): **RED** (invariants, do not change), **YELLOW** (change only with a note in `docs/DECISIONS.md`), **GREEN** (experiment freely).
4. Do not assume facts about external projects (benchmarks, libraries, APIs). **Read their current repos and docs and verify** before coding against them. Where this document says "verify", that is mandatory.
5. If something is ambiguous or blocks you, write the question in `docs/QUESTIONS.md` and continue with the most conservative interpretation. Do not silently invent requirements.
6. Never fabricate results, benchmark numbers, or citations. If a run did not happen, there is no number.
7. Product intent (section 1.1) MUST NOT leak into scientific claims, configs, or the loop.

---

## 1. Goal and non-goals

### Goal

Build a **benchmark-agnostic framework** that takes an existing LLM agent and a benchmark with programmatic scoring, and improves the agent's **harness** (prompts, tool descriptions, notes/skills, simple routing guidance) through an **evidence-gated improvement loop**, with **model weights frozen**.

Then evaluate the *same frozen framework* on several different benchmarks, without per-benchmark tuning, and publish the results (code, configs, seeds, write-up).

The framework's claim is *governed self-improvement*: every change is versioned, justified by evidence, validated on held-out tasks, and reversible.

The scientific headline is **not** "we beat GEPA." It is: **how much harness-optimization gain survives a pre-registered held-out test, across agent types, at a small matched budget.** The generalization gap (H3) is a first-class result. Null and negative results count.

### 1.1 Product trajectory (out of band of the protocol)

The owner intends, later, a company that sells **governed, secure self-improvement** for third-party AI agents, eventually including live **weight** updates. That is **not** this repo's v1 deliverable.

v1 exists to produce a **credible public proof** that a governed loop can improve real agents without touching weights, with an audit trail a stranger can inspect. That proof is the input to a later open-source core and, after that, B2B. Details live in `docs/IDEAS.md`. Implications that **are** binding on this repo:

- The **product-shaped artifacts** are the adapter protocol, the evidence package, the lineage DAG, the append-only ledger, and the gate — not a clever proposer.
- Do not implement a UI, hosted service, or weight-update path in v1.
- Do not advertise recursive weight self-modification. v1 language is *governed harness improvement* (see section 17).
- License and dependency review (`docs/LICENSES.md`, Q-006) MUST be done before any public post or "open source" claim.

### Non-goals (v1)

- Weight updates or fine-tuning of any kind.
- Self-modification of source code or of the benchmark/scorer. Evolvable surface is **text/config artifacts only**.
- Any UI, dashboard, or hosted service. CLI and files only.
- Domain-specific tricks (finance, legal, medical, etc.). Core MUST stay domain-blind.
- Claims about production readiness, safety certification, or clinical/financial suitability.
- Matching or citing official ITBench judge-based leaderboard numbers as if they were ours (D-003).

### Project boundaries (MUST)

- Public datasets, public benchmarks, and open-source agents only.
- No proprietary, employer, or confidential data or information anywhere in the repo, prompts, logs, or docs.
- Check each benchmark's and each dependency's license for the intended use (research publication now, possible commercial use later). Record findings in `docs/LICENSES.md`.

---

## 2. Research questions and hypotheses

Pre-register these in `docs/PROTOCOL.md` before any final run.

- **H1 (main):** On at least two benchmarks of different agent types, the frozen framework improves held-out pass rate over the untouched agent, with a paired-bootstrap 95% CI excluding zero. If the minimum detectable effect (section 9.1) is larger than the observed delta, the result is labeled **inconclusive**, not a win.
- **H2:** At equal **all-in** optimization budget (every token: agent, user-sim, diagnoser, proposer; every dollar), the framework matches or beats off-the-shelf baselines (GEPA via `optimize_anything`, and ACE). Non-inferiority counts as a result; a win is a bonus.
- **H3:** The gate and regularizers reduce the generalization gap (optimization-set gain minus held-out gain) versus an ungated version. This is the **headline methodological claim**.
- **H4 (optional):** Gains transfer to at least one other model (a second API model or a small open model). User-simulator settings stay fixed when the agent model changes.

Null and negative results MUST be reported. They are part of the finding.

---

## 3. Constraints that shape the design

| Constraint | Consequence |
|---|---|
| Owner laptop: i7, **no CUDA GPU** | Development, orchestration, tests run on CPU. Never require a local GPU. |
| Free Kaggle GPU (about 30 GPU hours/week, T4/P100, ~16 GB each, long sessions are capped; verify current limits) | Optional: serve a small open model (7B to 14B, quantized) for a second-model experiment. Long runs MUST be resumable and batch-friendly. |
| Small budget for cheap API models | One cheap model plays agent, user-simulator, and proposer by default. LLM calls are the cost driver. **Cache and meter everything.** |
| Programmatic scoring only | No LLM-as-judge in the main results. This removes self-preference bias from the headline numbers. |
| Docker may be unavailable on Kaggle (verify) | Do not choose benchmarks that require Docker for the first round. |
| τ² conversations are slow and sequential | `LLMClient` MUST support async calls with rate limits; the cache MUST be safe under concurrency (SQLite WAL). |
| Small *n* on ITBench | Eval 2 is allowed to be inconclusive; do not stretch splits to manufacture a CI. |

---

## 4. Invariants (RED zone: MUST NOT change without owner approval)

These protect the validity of the published results. The Cursor agent MUST implement them and MUST NOT weaken them while experimenting.

- **I1 Scorers are untouchable.** Scoring is programmatic and comes from the benchmark **or**, where the official toolkit is a judge, from an adapter-local **entity/state match** declared in `docs/DECISIONS.md` (currently D-003 for ITBench). The loop, proposers, and diagnosers cannot read, modify, or influence scorer logic. They MUST NOT be given ground-truth expected actions, hidden policy, or "reference trajectories" built from answers.
- **I2 Splits are fixed by manifest.** Task splits (`opt`, `val`, `select`, `test`) are generated once from a seeded manifest, committed to the repo, and hashed. Nothing changes them afterward.
- **I3 The loop never sees `test` or `select` during optimization.** No `test` or `select` task, trace, score, or aggregate may be passed to any proposer, diagnoser, gate, or logger accessible during optimization. `select` is readable only by the champion-audit path after the loop stops proposing. `test` is readable only by the Phase C reporter. Enforce this in code (separate access paths) and with tests.
- **I4 Declared evolvable surface only.** The adapter declares which artifacts are editable. Everything else (benchmark policy, tools' behavior, scorer, environment) is **protected**. An edit outside the surface MUST be rejected by the harness manager, not by convention.
- **I5 All LLM calls go through one metered, cached client.** It enforces hard budget caps and logs every call. Direct SDK calls elsewhere are a defect. The matched budget (I8) counts **all** roles (D-007).
- **I6 Every accepted version has an evidence package** (diff, motivating traces, validation results, cost, parent). See Appendix C.
- **I7 The core is benchmark-blind.** `core/` MUST NOT import from `adapters/`. Benchmark-specific logic lives only in adapters. Add a test that fails if this is violated.
- **I8 Matched comparisons.** Baselines and the framework use the same model, same task sets, same seeds, and the same **all-in** optimization budget (or are reported at several budgets).
- **I9 Final test evaluation is append-only.** Final `test` results are written to an immutable results ledger. Re-running after seeing test results is labeled **post-hoc** and reported separately.
- **I10 Edits are bounded.** A single candidate may change at most the configured number of artifacts and characters (and, for playbooks, bullets). Large rewrites are allowed only as an explicitly named strategy with its own budget.
- **I11 Leakage linter.** A candidate that copies literal strings from `opt` task payloads (ids, names, unique phrases above a configured length) MUST be rejected. Core computes overlap with task payloads it is given; adapters MUST NOT put scorer internals into payloads. This is benchmark-blind string overlap, not a semantic judge.

---

## 5. Architecture

### 5.1 Data flow

```
 Benchmark Adapter  --run(task, harness, seed)-->  RunResult (score, trace, cost, valid)
        ^                                              |
        |                                              v
   HarnessSpec <--accept/reject-- Gate <-- paired evidence <-- Validator
        ^                                                          ^
        |                                                          |
   Proposer <-- Diagnosis <-- Diagnoser <-- failures/successes (opt split only)
        ^
   SearchPolicy (greedy | beam | population | ...)   Budget meter wraps everything

 After the loop: ChampionAudit reads select (not opt) and ranks top-K.
 Phase C reporter reads test. Neither path is importable from proposers.
```

### 5.2 Components

1. **Benchmark Adapter** (YELLOW): thin wrapper around an external benchmark. Exposes tasks per split, runs one task with a given harness and seed, declares the editable surface, returns a programmatic score and a trace. No optimization logic.
2. **HarnessSpec** (YELLOW): an immutable, content-addressed bundle of named text artifacts (e.g. `system_prompt`, `tool:<name>.description`, `notes/<topic>.md` as an **itemized playbook**, `routing_hints`). Has `id` (hash) and `parent_id` (lineage). Playbook artifacts SHOULD be a JSON list of `{id, text, useful, harmful}` bullets, not a free-form blob (D-005).
3. **HarnessManager** (RED for validation, GREEN for storage format): applies typed edits, enforces I4, I10, I11, stores versions as a lineage DAG, supports rollback to any ancestor. Playbook ops are ADD / UPDATE / REMOVE by bullet id. Full-document `replace` of a playbook is a named strategy.
4. **LLMClient** (RED): one wrapper with disk cache, cost metering, hard caps, retries, seeded sampling, **async + rate limit**, concurrent-safe cache. Cache key MUST include model, messages, parameters, and a `sample_index` so different seeds still produce different samples. Cache namespaces for `select`/`test` runs MUST be disjoint from opt (I3).
5. **TraceStore** (YELLOW): SQLite (WAL) plus JSONL. Stores traces, scores, costs, per task, per version, per seed. Opt traces MUST NOT be readable via the select/test accessors.
6. **Diagnoser** (GREEN): turns failures (and optionally successes) into a structured diagnosis for the proposer. MUST NOT receive `select`/`test` traces.
7. **Proposer** (GREEN): generates candidate edits (typed patches) given the current harness, diagnosis, and lineage memory.
8. **Validator** (YELLOW): runs current vs candidate on the same `val` tasks and seeds, producing **paired evidence**. MAY evaluate a rotating subset of `val` (section 7.4) and MUST estimate full-`val` performance with a sampling-weighted estimator when it does.
9. **Gate** (GREEN in dev, **frozen** for final): decides accept/reject from paired evidence plus constraints (section 7.4).
10. **SearchPolicy** (GREEN): controls which versions are explored and how budget is spent (greedy, beam, population, successive halving).
11. **Orchestrator** (YELLOW): the round loop that wires the above together. Resumable. After the loop, runs **ChampionAudit** on `select`.
12. **ChampionAudit** (YELLOW): one-shot re-score of the top-K accepted versions (plus B0) on the frozen `select` split. Picks the finalist for freeze. MUST NOT run during proposing rounds.
13. **Experiment Runner and Reporter** (YELLOW): runs configs, writes ledgers, produces tables and plots. The reporter is the only component allowed to read `test`.

### 5.3 The loop (reference version)

```
state = load_or_init(config)            # resumable
while not budget_exhausted(state) and not patience_exhausted(state):
    batch    = sample(opt_tasks, state.batch_size)
    results  = run(current, batch)                      # traces stored; drop invalid
    diag     = diagnoser.diagnose(results)              # opt split only
    cands    = proposer.propose(current, diag, lineage_memory)   # <= K candidates
    for c in cands:
        if leakage_linter.reject(c, opt_payloads):
            log(c, reject="i11"); continue
        ev   = validator.compare(current, c, val_tasks, seeds)   # paired; maybe rotated
        dec  = gate.decide(current, c, ev)
        log(c, ev, dec)
    current  = search_policy.select(current, accepted_candidates)
    checkpoint(state)

finalist = champion_audit(top_k_accepted, select_tasks, seeds)   # not during loop
# Phase C, frozen tag only:
# reporter.evaluate(finalist, test_tasks) -> ledger.jsonl
```

---

## 6. Data splits and freeze protocol (RED)

### 6.1 Splits

Each benchmark's tasks are partitioned into:

| Split | Who may see it | Role |
|---|---|---|
| `opt` | loop (diagnoser, proposer, gate's motivating traces) | learn |
| `val` | validator + gate during the loop | accept/reject; MAY be subsampled and rotated |
| `select` | ChampionAudit only, after the loop | pick a finalist among accepted versions |
| `test` | Phase C reporter only | published numbers |

Also keep a small **guard set** drawn from `val`: tasks the current version already passes. The gate uses it to detect regressions. Guard-set membership is allowed to grow as versions pass more `val` tasks; the *pool* it draws from is still `val`.

**Suggested sizes (owner may change before freeze):**

- If a large compositional pool exists (telecom, Q-002): draw `opt` / `val` / `select` from the pool **excluding** the official evaluation subsample; the official subsample is `test`. Record the exclusion list in the manifest. This is the preferred construction: public-leaderboard tasks never enter the loop.
- If only the official set exists: default **40% / 20% / 15% / 25%** (`opt`/`val`/`select`/`test`), stratified by any available difficulty or category label. Write the minimum detectable effect (section 9.1) into the manifest notes. If `n` is too small for four splits (ITBench ~35), **drop `select`**, keep `opt`/`val`/`test`, and say so. Do not invent tasks.

Manifest: `data/splits/<benchmark>.json` with task ids, seed, generation script hash, split ratios, and whether `select` exists. Commit it, then never touch it.

### 6.2 Two phases

**Phase A: Development (allowed to iterate)**
- Use the **dev benchmark** only (section 10). Use `opt`, `val`, and `select` only. Compare variants here. Select a single finalist configuration using **`select` scores**, not `val` scores, once ChampionAudit exists. Until then, `val` is allowed for design decisions and MUST be labeled as such.

**Phase B: Freeze**
- Create a git tag `freeze-<date>`. Write `docs/PROTOCOL.md` containing: final config hash, model names and versions, budgets, seeds, benchmark versions, split manifest hashes, hypotheses, minimum detectable effects, and the exact report template.
- After the tag, framework code and configs MUST NOT change for final runs.

**Phase C: Final evaluation**
- Run the frozen framework unchanged on the evaluation benchmarks (and on the dev benchmark's `test`, reported separately). Report on `test` splits. Results go to the append-only ledger (I9).

Anything done after seeing test results is labeled post-hoc.

---

## 7. Experiment space (GREEN zone: where you are encouraged to try things)

The aim is to find the strongest design. You MAY implement any of the options below, combinations of them, or ideas of your own, as long as the invariants hold and each experiment is logged (section 7.6).

### 7.1 Editable surface granularity

Compare, at equal budget:
- S1: system prompt only.
- S2: system prompt + tool descriptions.
- S3: S2 + persistent notes/skills as an **itemized playbook** (default notes representation, D-005).
- S3-blob: S2 + notes as a free-form markdown file (ablation: does itemizing help?).
- S4: S3 + simple routing/workflow hints (e.g. when to ask a clarifying question, when to call which tool first).

Hypothesis to test: more surface helps up to a point and then overfits. Itemized notes SHOULD resist context collapse relative to S3-blob.

### 7.2 Diagnoser variants

- D0: none (proposer sees raw failed traces).
- D1: per-trace critique, then merge.
- D2: cluster failures by cause, then diagnose each cluster.
- D3: contrastive: pair a failure with a similar success. **Preferred cheap contrast:** same `task_id`, different seed (τ² is stochastic). MUST NOT build the success by peeking at ground truth.
- D4: counterfactual probing (re-run a failed task with a candidate hint and observe).
- D5: your own.

**Forbidden import:** "reference trajectories" that give the agent the answer and then align the failure to that path. That reads scorer internals (I1).

### 7.3 Proposer and search variants

- P1: single-shot rewrite from failure summary (naive baseline).
- P2: reflective, per-cause targeted edits, small patches only (playbook ADD/UPDATE/REMOVE).
- P3: population with Pareto selection across tasks (GEPA-style; use `optimize_anything` as **baseline B1**, and implement your own variant as the framework).
- P4: beam or tree search over versions in the lineage DAG.
- P5: multi-proposer ensemble (different prompts/temperatures) with deduplication.
- P6: lineage-aware proposer (sees previously rejected edits and why, avoids repeats, can combine two accepted ancestors).
- P7: successive halving across candidates to save budget (cheap screen on few `val` tasks, expand only promising ones).
- P8: prune pass: for each playbook bullet, propose REMOVE; keep the removal if estimated `val` does not drop beyond tolerance.
- P9: your own.

A Meta-Harness-style "proposer browses the trace filesystem" experiment is allowed only with an **opt-only** view (I3) and MUST be tagged in the log. Do not make it the default on a cheap proposer.

### 7.4 Gate and regularization variants

The gate decides acceptance. Variants to compare:
- G1: greedy: accept if mean paired delta > margin.
- G2: paired bootstrap: accept if lower bound of the delta CI > 0.
- G3: G2 plus a **guard set** rule: reject if more than X% of previously passing guard tasks now fail.
- G4: G3 plus an **edit-size penalty** (prefer small diffs; require larger gains for larger edits).
- G5: sequential testing (stop early on a clear win or loss to save budget).
- G6: Pareto acceptance (must not worsen any task category beyond tolerance).
- **G7 (default direction):** G3 plus **A/A noise floor**: before the loop, run the baseline harness twice on `val` with different seeds (or a disjoint inner split of `val` if seeds are too few) and estimate σ of the paired delta under no real change. Accept only if observed delta > max(margin, k·σ) with k default 1.0.
- **G8:** G7 plus **rotating `val` subsets**. Sample a subset each round, biased toward tasks whose recent pass rate is near 0.5 (informative). Compare using a Horvitz–Thompson / Hájek estimator of the full-`val` mean so rounds stay on one scale. MUST store inclusion probabilities with the evidence package.
- G9: your own.

Hard rejects (not variants): I4, I10, **I11 leakage linter**.

Regularizers to ablate: edit-size cap, artifact-length cap, bullet-count cap, rollback on later regression, replay of old failures, diversity pressure, "simplicity" preference, prune pass (P8).

### 7.5 Second-order improvement (EXPERIMENTAL track, clearly labeled)

You MAY test letting the framework improve **its own proposer/diagnoser prompts**, using the same gate and a separate dev-only evaluation. This track:
- MUST be tagged `experimental-second-order` in all logs.
- MUST NOT touch invariants, scorers, splits, or the gate's final-test procedure.
- MUST have its own budget cap.
- Only enters the finalist if it beats first-order variants on dev `select` (or `val` if `select` is absent) and passes review (record in `docs/DECISIONS.md`).
- MUST NOT appear in public posts as "the system rewrites itself."

### 7.6 How to run experiments (MUST)

For each experiment:
1. Write a hypothesis in `experiments/EXPERIMENTS.md` (template in Appendix D).
2. Define it as a config file under `configs/experiments/` (config hash recorded).
3. Run on **dev `opt`/`val` only** (ChampionAudit on `select` when choosing a finalist).
4. Record results, cost, and a verdict (adopt / drop / revisit) in the log.
5. Keep the code for dropped variants in `strategies/archive/` with a one-line reason. Do not delete negative results.

Promotion to finalist requires: wins on dev **`select`** (or `val` if no `select`) over the current best, at comparable all-in cost, across at least 2 seeds (or paired bootstrap if only 1), and no weakening of any invariant.

### 7.7 Autonomy levels for the agent

- **Level 1:** implement the baseline architecture and reference variants exactly as specified.
- **Level 2:** explore the variants in 7.1 to 7.5 within the dev benchmark.
- **Level 3:** propose new components or interfaces. Write the rationale in `docs/IDEAS.md` and note the change in `docs/DECISIONS.md` if it touches YELLOW code.

Go to Level 3 only after Level 1 is green and at least a few Level 2 experiments are logged.

---

## 8. Baselines and ablations

Baselines (all use the same model, tasks, seeds, and **all-in** budget):

- **B0:** untouched agent, default harness.
- **B1:** GEPA via [`optimize_anything`](https://gepa-ai.github.io/gepa/api/optimize_anything/optimize_anything/) (**verify** current API). Pass a `dict[str, str]` candidate (one key per artifact), `dataset` = opt, `valset` = val, do **not** pass `test_set` into the optimizer. Set `max_token_cost` (or equivalent) to the same all-in budget. Document default recommended settings.
- **B2:** naive loop: one LLM rewrite of the system prompt from failure summaries, no gate (accept always).
- **B3:** naive loop with a simple greedy gate (G1).
- **B4:** ACE (Generator / Reflector / Curator, incremental playbook deltas). Same splits, same all-in budget. **Verify** package/API. If ACE cannot be run fairly, drop B4 and record why in `DECISIONS.md` — do not pretend.

Ablations on the finalist:
- Remove the gate (always accept).
- Remove the diagnoser.
- Remove the guard set.
- Remove edit-size regularization.
- Remove I11 leakage linter (dev only; never in Phase C finalist unless it lost on `select`).
- Remove itemized playbook (S3-blob).
- Vary optimization budget (e.g. 25%, 50%, 100%) to produce a performance-versus-budget curve.
- Swap the agent model (H4), **holding user-sim fixed**, if budget allows.

---

## 9. Statistics and reporting

- **Primary metric:** pass rate (or the benchmark's native programmatic metric) on `test`.
- **Secondary (τ²):** pass^k (task counts only if all k seeds succeed). Harness edits often move reliability more than mean pass rate. Report pass^1 and pass^k for the same k used in rollouts.
- **Paired design:** same tasks and seeds before and after. Report mean delta with a 95% **paired bootstrap** CI over tasks (and over seeds if there are at least 3).
- For pass/fail outcomes also report a paired test (e.g. McNemar) and the raw counts of tasks flipped in each direction.
- **Seeds:** at least 3 per final condition if the budget allows. If not, say so and report the weaker evidence honestly.
- **Invalid trials:** user-sim deviations / infrastructure errors are re-run once then excluded from **both** arms (Q-007). Report the exclusion count.
- **Also report:**
  - generalization gap (opt gain minus test gain), and val-minus-select gap as a sanity check,
  - accept rate and rejection reasons (including I11),
  - regressions introduced and later rolled back,
  - cost: tokens **by role**, dollars, wall time per benchmark,
  - cost per +1 percentage point,
  - lineage depth, number of accepted edits, playbook bullet count,
  - failures of the framework (benchmarks where it did not help).
- **Multiple comparisons:** many variants were tried in dev. Only the finalist is evaluated on test, so no test-set variant selection. State this in the write-up.
- **Claims discipline:** results hold for the stated model(s), benchmark versions, and budgets. Do not generalize beyond them. A gain on a cheap or small model does not imply a gain on frontier models. Do not compare our ITBench entity-match numbers to judge-based published rows.

Output artifacts: `results/ledger.jsonl` (append-only), `results/tables/*.md`, `results/plots/*.png`, `results/REPORT.md`, plus a `REPRODUCE.md` with exact commands.

### 9.1 Power and minimum detectable effect (MUST before freeze)

For each benchmark, write into `PROTOCOL.md`:

- n = number of `test` tasks,
- assumed discordant fraction d (default 0.2 unless a pilot says otherwise),
- approximate 95% CI half-width for a paired pass-rate delta: `1.96 * sqrt(d / n)`,
- **minimum detectable effect** ≈ that half-width (CI excluding zero needs |delta| larger than this, roughly).

Worked conservative sketches (replace with real n after manifests exist):

| Setting | n test | half-width at d=0.2 | Honest label if |delta| is smaller |
|---|---|---|---|
| telecom official 114 as test | 114 | ~8 pp | inconclusive |
| airline 50, 25% test | 13 | ~24 pp | do not use as H1 |
| ITBench-Lite 35, no select, 40% test | 14 | ~23 pp | Eval 2 may be qualitative / inconclusive |

If H1 cannot be powered on a benchmark, that benchmark is a **transfer check**, not a hypothesis test. Say so in the protocol before seeing numbers.

---

## 10. Benchmarks and adapters

**Verify everything in this section against the current upstream repos before coding.** Names, install steps, task counts, and licenses may differ from what is assumed here. Pin commit hashes.

### 10.1 Suggested suite

| Role | Benchmark | Why | Notes |
|---|---|---|---|
| Dev | `toy-bench` (synthetic) | Unit tests of loop mechanics at zero cost | Deterministic mock agent whose behavior depends on harness text. Build first. |
| Dev | **τ²-bench telecom** (not airline) | Dual-control tool use; lower user-sim error than airline/retail | Preferred: opt/val/select from compositional pool excluding official 114; official 114 is test (Q-002). Pin τ²/τ³ commit; banking scores changed in v1.0.1 — do not mix. |
| Eval 1 | **τ²-bench** remaining official domain(s) unused in opt | Different domain, same agent type | Protect domain policy: only an *additive* guidance artifact is editable. Airline/retail have high user-sim error: report exclusion counts. |
| Eval 2 | **ITBench-Lite SRE snapshots** (or ITBench-AA public if verified equivalent) | Operational diagnosis; no live Kubernetes | Headline score = programmatic entity match against `ground_truth.yaml` (D-003). Underpowered; allow inconclusive. Skip live k8s. |
| Optional | A coding benchmark | Third agent type | Skip if it needs Docker or heavy infra. Check licenses. |

The owner may change this before the freeze. The framework MUST NOT assume any particular benchmark.

τ² adapter extra rules:
- Keep user-simulator **model, temperature, and instructions** fixed across before/after and across H4 agent swaps.
- Prefer tasks whose reward is database / required-action state, not NL-assertion-only, if the current repo distinguishes them. **Verify.** If mixed, stratify and report both, but H1 uses the programmatic subset.
- Voice / full-duplex / audio conditions are out of v1.

ITBench adapter extra rules:
- Agent sees snapshot files (alerts, metrics, events, traces, objects), not `ground_truth.yaml`.
- Output is structured JSON of root-cause entities. Score by set match (precision/recall/F1; pass if F1 ≥ configured threshold, default 1.0 for "identified the entity set").
- Judge metrics MAY be computed offline for a footnote, never as a loop signal, never as H1.

### 10.2 Adapter requirements

- Implement `BenchmarkAdapter` (Appendix A).
- Declare the editable surface and protected parts explicitly. **Never expose the benchmark's ground-truth rules, scorer, or hidden state to the loop.**
- Expose the agent's harness inputs (system prompt addition, tool descriptions, notes) via `HarnessSpec` artifacts. If the benchmark's agent cannot accept a given artifact type, do not declare it.
- Return a score in [0, 1] from programmatic checks, plus a trace (messages, tool calls, outcomes), cost, and `valid: bool`.
- Include a smoke test that runs 2 to 3 tasks with the mock LLM or a cached transcript.
- Record the benchmark's version/commit and license in the adapter's metadata.
- Keep user-simulator settings (if any) fixed across before/after comparisons.

---

## 11. Compute and cost engineering

- **Cache every LLM call** (disk, keyed per I5). A crashed or resumed run MUST NOT pay twice.
- **Hard budget caps** in config: total dollars/tokens, per-round cap, per-candidate cap. The meter MUST stop the run cleanly and checkpoint.
- **Resumable runs:** state (current version, lineage, round, RNG state, budgets) checkpointed after each round to disk.
- **Batch-friendly on Kaggle:** a single CLI entry point (`python -m rsi_harness run --config ...`) that reads and writes only under a configurable `WORKDIR` (default `/kaggle/working` when present). Do not rely on interactive sessions.
- **Cheap-first development:** use `toy-bench` and a tiny slice of the dev benchmark for all debugging. Large runs only after the loop is validated.
- **Model roles:** default one cheap model for agent, user-simulator, and proposer. Allow separate model settings per role in config (a stronger proposer is an experiment, not a default).
- **Determinism:** temperature and seeds in config; document nondeterminism that remains.
- **Concurrency:** async completions, rate limits, SQLite WAL, cache key includes `sample_index`.
- **Optional open-model path:** an adapter-independent `LLMClient` backend for a locally served open model (e.g. via an OpenAI-compatible server). Never required for the main results.

---

## 12. Repo layout, stack, and standards

```
rsi-harness/
  DESIGN.md
  README.md
  docs/            PROTOCOL.md  DECISIONS.md  QUESTIONS.md  IDEAS.md  LICENSES.md
  core/            types.py  harness.py  llm.py  budget.py  trace_store.py
                   validator.py  orchestrator.py  stats.py  audit.py   # RED/YELLOW
  strategies/      diagnosers/  proposers/  gates/  search/  archive/   # GREEN
  adapters/        toy_bench/  tau2/  itbench/                        # YELLOW
  configs/         base.yaml  experiments/  final/
  data/splits/     <benchmark>.json                                   # RED once committed
  experiments/     EXPERIMENTS.md  runs/
  results/         ledger.jsonl  tables/  plots/  REPORT.md
  tests/           unit/  integration/  invariants/
  scripts/         make_splits.py  report.py
```

- Python 3.11+, `uv` (or pip-tools) for dependencies, `pydantic` for configs and schemas, `typer` for the CLI, `pytest`, `ruff`, type hints throughout.
- A model-abstraction library (e.g. `litellm`) is acceptable inside `LLMClient` only. **Verify** current versions.
- SQLite for the trace store (WAL). JSONL for logs and ledger.
- Every module has docstrings stating its invariants. Keep functions small and pure where possible.
- Tests: `tests/invariants/` MUST include checks for I3 (no test/select leakage), I4 (edits outside surface rejected), I5 (no direct LLM calls outside the client), I7 (core does not import adapters), I11 (leakage linter), and budget-cap enforcement.
- CI (simple): lint, type check, unit tests with the mock LLM. No paid API calls in CI.

---

## 13. Milestones and acceptance criteria

| # | Milestone | Acceptance |
|---|---|---|
| M0 | Scaffold, config system, CLI, CI | `rsi-harness --help` works; CI green |
| M1 | `LLMClient` with cache, meter, caps, async; `TraceStore` WAL | Replaying a run costs $0; hitting the cap stops and checkpoints; concurrent cache test — **done** |
| M2 | `HarnessSpec` and `HarnessManager` with lineage, playbook ops, I4/I10/I11, rollback | Out-of-surface and leaking edits rejected; rollback restores exact hash — **done** |
| M3 | `toy-bench` and mock agent | Reference loop provably improves toy score in tests — **done** |
| M4 | Reference loop (P2 + G7) end to end, resumable, ChampionAudit stub | Interrupt and resume yields identical final state — **done** |
| M5 | Splits manifest generator (4-way), leakage tests, stats module, A/A helper | I2/I3/I11 tests pass; bootstrap, McNemar, Hájek estimator unit-tested on synthetic data |
| M6 | τ² telecom adapter + baselines B0, B2, B3 on dev | Baseline numbers reproduced and logged; cost by role; user-sim exclusions counted |
| M7 | GEPA `optimize_anything` (B1) and ACE (B4) under same all-in budget | Runs under the same logging; if B4 blocked, decision logged |
| M8 | Strategy plugins + experiment runner; at least 6 logged experiments | Entries in `EXPERIMENTS.md` with verdicts |
| M9 | Ablations and finalist selection on dev **`select`** | Finalist config file chosen; selection rationale documented |
| M10 | **Freeze** (tag, `PROTOCOL.md` including MDEs) | Owner sign-off |
| M11 | ITBench (offline, entity match) adapter; final runs on all evaluation benchmarks | Ledger entries; REPRODUCE.md verified; underpowered evals labeled |
| M12 | Report, plots, write-up draft, release checklist | `REPORT.md` complete; license check done |

Stop and ask (via `QUESTIONS.md`) if a milestone's acceptance cannot be met within budget.

Public posts (section 17) MAY follow M3 (mechanics), M6 (dev-val, labeled), M10 (protocol), M12 (test). Not before.

---

## 14. Change governance and zones

| Zone | What | Rule |
|---|---|---|
| **RED** | Invariants I1 to I11, `LLMClient` caps, split manifests, scorer access, final-test procedure, results ledger, ChampionAudit isolation | No change without owner approval |
| **YELLOW** | Adapters, `HarnessSpec`, validator, orchestrator, trace store, stats, ChampionAudit | Change allowed with an entry in `docs/DECISIONS.md` (what, why, impact on past results) |
| **GREEN** | `strategies/`, `configs/experiments/`, `experiments/`, `docs/IDEAS.md` | Experiment freely, but log it |

Working agreements for the agent:
- Small commits, clear messages, one concern per commit.
- Write or update tests with every change.
- Never run paid large batches without checking the configured budget cap first.
- When results surprise you (too good or too bad), look for a bug or leakage before celebrating or tuning.
- Prefer deleting complexity to adding it. A simpler strategy that ties a complicated one wins.

---

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Overfitting to `val` or the dev benchmark | Four-way splits, rotating val, A/A noise floor, ChampionAudit, freeze protocol, untouched `test`, generalization-gap reporting |
| Reward hacking of the proxy | Programmatic scorers only, protected benchmark internals, I11, review accepted diffs by hand for a sample |
| Noisy results from small samples | Paired design, bootstrap CIs, multiple seeds, pre-registered MDE, honest "inconclusive" label |
| Budget overruns | Caching, hard caps, cheap-first development, successive halving, all-in metering |
| Benchmark changes upstream | Pin versions and commits; record in the ledger |
| Weak proposer (cheap model) | Treat a stronger proposer as a logged experiment; report the model dependence |
| Leakage via logs or caches | I3 tests; separate cache namespaces for `select`/`test` runs |
| Scope creep | Non-goals list; Level 3 work only after Level 1 and 2 are done |
| License problems blocking publication or later commercial use | `docs/LICENSES.md` early; no public post until Q-006 |
| Crowded 2026 harness-opt field | Claim H3 (governed generalization), not "first to evolve a harness" |
| User-sim noise on τ² | Telecom first; exclusion policy Q-007 |
| Mixing startup narrative into results | Section 1.1 and 17 |

---

## 16. Open questions for the owner (confirm before M6)

Tracked in `docs/QUESTIONS.md`:

1. ~~Q-001~~ **resolved:** OpenRouter, $50 prototype (`configs/base.yaml`).
2. ~~Q-002~~ **resolved:** telecom `test` = upstream `base` (114); opt/val/select from pool of 2,171 (`scripts/make_splits.py`).
3. **Q-003 (ITBench):** Lite SRE vs ITBench-AA — still open; default Lite + entity match (D-003).
4. ~~Q-004 (prototype)~~ **resolved:** 2 seeds; 3 at Phase C if budget remains.
5. **Q-005:** H4 second model — still open.
6. ~~Q-006~~ **resolved:** AGPL-3.0 public + `docs/COMMERCIAL.md` for paid commercial use.

---

## 17. Public narrative (LinkedIn / X)

Binding on anything posted about this repo:

- No unpublished `test` numbers. Dev `val` MUST be labeled **not a claim**.
- Do not say the system modifies weights, "recursively self-improves its source," or is production-ready.
- Preferred frame: *governed harness improvement* — versioned diffs, evidence packages, rollback, held-out test.
- Show one accepted edit (diff + why + val/select evidence), not a leaderboard flex.
- If a CI includes zero, the post says inconclusive, not "we improved it."
- License: no "open source" until Q-006 is resolved.

---

## Appendix A: Interface sketches (Python, illustrative; adapt freely, keep the contracts)

```python
from dataclasses import dataclass, field
from typing import Protocol, Literal, Any

Split = Literal["opt", "val", "select", "test"]

@dataclass(frozen=True)
class Task:
    id: str
    benchmark: str
    payload: dict[str, Any]          # opaque to core; MUST NOT contain scorer internals

@dataclass(frozen=True)
class Bullet:
    id: str
    text: str
    useful: int = 0
    harmful: int = 0

@dataclass(frozen=True)
class HarnessSpec:
    id: str                          # content hash of artifacts
    parent_id: str | None
    artifacts: dict[str, str]        # serialized; playbooks are JSON lists of Bullet

@dataclass(frozen=True)
class Edit:
    artifact: str
    op: Literal["replace", "append", "insert", "delete", "add_bullet", "update_bullet", "remove_bullet"]
    text: str = ""
    anchor: str | None = None        # insert/replace-within, or bullet id
    bullet_id: str | None = None

@dataclass
class Cost:
    prompt_tokens: int
    completion_tokens: int
    dollars: float
    seconds: float
    by_role: dict[str, float] = field(default_factory=dict)  # agent, user_sim, proposer, ...

@dataclass
class RunResult:
    task_id: str
    harness_id: str
    seed: int
    score: float                     # [0,1], programmatic
    passed: bool
    valid: bool                      # False => excluded from both arms
    trace: list[dict[str, Any]]
    cost: Cost
    error: str | None = None

@dataclass(frozen=True)
class SurfaceDecl:
    editable: dict[str, dict]        # artifact name -> {max_chars, description, kind}
    protected: list[str]             # human-readable list of what must not change

class BenchmarkAdapter(Protocol):
    name: str
    version: str
    def tasks(self, split: Split) -> list[Task]: ...
    def surface(self) -> SurfaceDecl: ...
    def default_harness(self) -> HarnessSpec: ...
    def run(self, task: Task, harness: HarnessSpec, llm: "LLMClient", seed: int) -> RunResult: ...

class Diagnoser(Protocol):
    def diagnose(self, failures: list[RunResult], successes: list[RunResult]) -> "Diagnosis": ...

class Proposer(Protocol):
    def propose(self, current: HarnessSpec, diagnosis: "Diagnosis",
                memory: "LineageMemory", k: int) -> list[list[Edit]]: ...

@dataclass
class PairedEvidence:
    task_ids: list[str]
    seeds: list[int]
    current_scores: list[float]
    candidate_scores: list[float]
    inclusion_probs: list[float] | None  # for rotating val
    estimated_full_val_delta: float | None
    guard_regressions: int
    edit_chars: int
    aa_sigma: float | None
    cost: Cost

class Gate(Protocol):
    def decide(self, current: HarnessSpec, candidate: HarnessSpec,
               evidence: PairedEvidence) -> "Decision": ...

class SearchPolicy(Protocol):
    def select(self, current: HarnessSpec, accepted: list[HarnessSpec],
               lineage: "Lineage") -> HarnessSpec: ...

class ChampionAudit(Protocol):
    def pick(self, candidates: list[HarnessSpec], select_tasks: list[Task],
             seeds: list[int]) -> HarnessSpec: ...
```

## Appendix B: Example config

```yaml
run_id: dev-tau2-telecom-p2-g7-001
workdir: ./runs            # /kaggle/working on Kaggle
seed: 7
benchmark:
  name: tau2
  domain: telecom          # dev slice (D-002)
  splits_manifest: data/splits/tau2_telecom.json
models:
  agent:      {name: <cheap-model>, temperature: 0.0}
  user_sim:   {name: <cheap-model>, temperature: 0.0}  # frozen across H4
  proposer:   {name: <cheap-model>, temperature: 0.7}
budget:
  total_dollars: 20.0      # all-in: every role
  per_round_dollars: 1.0
  per_candidate_dollars: 0.25
loop:
  rounds: 15
  opt_batch: 12
  candidates_per_round: 3
  val_tasks: 20            # rotating subset size if G8
  seeds: [0, 1]
  patience: 4
  champion_top_k: 3
strategies:
  surface: S3              # itemized playbook
  diagnoser: {name: d3_contrastive_seed}
  proposer:  {name: p2_reflective, max_edit_chars: 800, max_bullets_touched: 3}
  gate:      {name: g7_aa_guard, alpha: 0.05, guard_tolerance: 0.05, k_sigma: 1.0}
  search:    {name: greedy}
  leakage_linter: {min_literal_len: 12}
```

## Appendix C: Evidence package (one per accepted version)

```json
{
  "version_id": "h_9f3a...",
  "parent_id": "h_41bc...",
  "diff": [{"artifact": "notes/playbook.json", "op": "add_bullet", "bullet_id": "b_12", "text": "..."}],
  "motivating_task_ids": ["..."],
  "diagnosis_summary": "...",
  "validation": {
    "task_ids": ["..."], "seeds": [0,1],
    "mean_delta": 0.06, "ci95": [0.01, 0.11],
    "estimated_full_val_delta": 0.05,
    "aa_sigma": 0.02,
    "flipped_to_pass": 5, "flipped_to_fail": 1,
    "guard_regressions": 0
  },
  "gate": {"name": "g7_aa_guard", "decision": "accept", "reason": "..."},
  "i11": {"rejected_literals": []},
  "cost": {"dollars": 0.31, "prompt_tokens": 0, "completion_tokens": 0, "by_role": {}},
  "created_at": "..."
}
```

## Appendix D: Experiment log entry template

```
### EXP-<nnn>: <short name>
- Date / config hash / git commit:
- Hypothesis:
- Variant(s) vs baseline (what changed):
- Benchmark / split / seeds / budget (all-in):
- Results (opt, val, select; never test): table
- Cost by role:
- Observations (including surprises and suspected bugs):
- Verdict: adopt | drop | revisit
- Follow-ups:
```

## Appendix E: PROTOCOL.md template (written at freeze)

```
Freeze tag:
Date:
Framework commit / config hash:
Models and versions (agent, user_sim, proposer):
Benchmarks, versions/commits, licenses:
Split manifests (hashes) and whether select exists:
Budgets (all-in) and seeds:
Minimum detectable effects per benchmark:
Hypotheses H1 to H4 (as written before final runs):
Baselines B0–B4 and ablations to be run:
Primary and secondary metrics (including pass^k):
Statistical procedures (paired bootstrap, McNemar, Hájek if G8):
ITBench scorer: adapter entity match, not official judge (D-003):
Report template location:
Deviations allowed: none. Anything else is labeled post-hoc.
```

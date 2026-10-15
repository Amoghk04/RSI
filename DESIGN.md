# RSI-Harness: Design Document (v0.1)

Working name: `rsi-harness`. Rename freely.

**Audience:** the Cursor agent that builds this repo, and the owner who reviews it.
**Status:** draft for build. Sections marked MUST are fixed. Sections marked MAY are open for experimentation.

---

## 0. How to use this document

1. Read the whole document before writing code.
2. Words mean what they say: **MUST** = non-negotiable, **SHOULD** = default unless you record a reason, **MAY** = your call.
3. The repo has three zones (see section 14): **RED** (invariants, do not change), **YELLOW** (change only with a note in `docs/DECISIONS.md`), **GREEN** (experiment freely).
4. Do not assume facts about external projects (benchmarks, libraries, APIs). **Read their current repos and docs and verify** before coding against them. Where this document says "verify", that is mandatory.
5. If something is ambiguous or blocks you, write the question in `docs/QUESTIONS.md` and continue with the most conservative interpretation. Do not silently invent requirements.
6. Never fabricate results, benchmark numbers, or citations. If a run did not happen, there is no number.

---

## 1. Goal and non-goals

### Goal

Build a **benchmark-agnostic framework** that takes an existing LLM agent and a benchmark with programmatic scoring, and improves the agent's **harness** (prompts, tool descriptions, notes/skills, simple routing guidance) through an **evidence-gated improvement loop**, with **model weights frozen**.

Then evaluate the *same frozen framework* on several different benchmarks, without per-benchmark tuning, and publish the results (code, configs, seeds, write-up).

The framework's claim is *governed self-improvement*: every change is versioned, justified by evidence, validated on held-out tasks, and reversible.

### Non-goals (v1)

- Weight updates or fine-tuning of any kind.
- Self-modification of source code or of the benchmark/scorer. Evolvable surface is **text/config artifacts only**.
- Any UI, dashboard, or hosted service. CLI and files only.
- Domain-specific tricks (finance, legal, medical, etc.). Core MUST stay domain-blind.
- Claims about production readiness, safety certification, or clinical/financial suitability.

### Project boundaries (MUST)

- Public datasets, public benchmarks, and open-source agents only.
- No proprietary, employer, or confidential data or information anywhere in the repo, prompts, logs, or docs.
- Check each benchmark's and each dependency's license for the intended use (research publication now, possible commercial use later). Record findings in `docs/LICENSES.md`.

---

## 2. Research questions and hypotheses

Pre-register these in `docs/PROTOCOL.md` before any final run.

- **H1 (main):** On at least two benchmarks of different agent types, the frozen framework improves held-out pass rate over the untouched agent, with a paired-bootstrap 95% CI excluding zero.
- **H2:** At equal optimization budget (tokens/dollars), the framework matches or beats an off-the-shelf optimizer baseline (GEPA or equivalent). Non-inferiority counts as a result; a win is a bonus.
- **H3:** The gate and regularizers reduce the generalization gap (optimization-set gain minus held-out gain) versus an ungated version.
- **H4 (optional):** Gains transfer to at least one other model (a second API model or a small open model).

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

---

## 4. Invariants (RED zone: MUST NOT change without owner approval)

These protect the validity of the published results. The Cursor agent MUST implement them and MUST NOT weaken them while experimenting.

- **I1 Scorers are untouchable.** Scoring is programmatic and comes from the benchmark. The loop, proposers, and diagnosers cannot read, modify, or influence scorer logic.
- **I2 Splits are fixed by manifest.** Task splits (`opt`, `val`, `test`) are generated once from a seeded manifest, committed to the repo, and hashed. Nothing changes them afterward.
- **I3 The loop never sees `test`.** No `test` task, trace, score, or aggregate may be passed to any proposer, diagnoser, gate, or logger accessible during optimization. Enforce this in code (separate access path) and with tests.
- **I4 Declared evolvable surface only.** The adapter declares which artifacts are editable. Everything else (benchmark policy, tools' behavior, scorer, environment) is **protected**. An edit outside the surface MUST be rejected by the harness manager, not by convention.
- **I5 All LLM calls go through one metered, cached client.** It enforces hard budget caps and logs every call. Direct SDK calls elsewhere are a defect.
- **I6 Every accepted version has an evidence package** (diff, motivating traces, validation results, cost, parent). See Appendix C.
- **I7 The core is benchmark-blind.** `core/` MUST NOT import from `adapters/`. Benchmark-specific logic lives only in adapters. Add a test that fails if this is violated.
- **I8 Matched comparisons.** Baselines and the framework use the same model, same task sets, same seeds, and the same optimization budget (or are reported at several budgets).
- **I9 Final test evaluation is append-only.** Final `test` results are written to an immutable results ledger. Re-running after seeing test results is labeled **post-hoc** and reported separately.
- **I10 Edits are bounded.** A single candidate may change at most the configured number of artifacts and characters. Large rewrites are allowed only as an explicitly named strategy with its own budget.

---

## 5. Architecture

### 5.1 Data flow

```
 Benchmark Adapter  --run(task, harness, seed)-->  RunResult (score, trace, cost)
        ^                                              |
        |                                              v
   HarnessSpec <--accept/reject-- Gate <-- paired evidence <-- Validator
        ^                                                          ^
        |                                                          |
   Proposer <-- Diagnosis <-- Diagnoser <-- failures/successes (opt split only)
        ^
   SearchPolicy (greedy | beam | population | ...)   Budget meter wraps everything
```

### 5.2 Components

1. **Benchmark Adapter** (YELLOW): thin wrapper around an external benchmark. Exposes tasks per split, runs one task with a given harness and seed, declares the editable surface, returns a programmatic score and a trace. No optimization logic.
2. **HarnessSpec** (YELLOW): an immutable, content-addressed bundle of named text artifacts (e.g. `system_prompt`, `tool:<name>.description`, `notes/<topic>.md`, `routing_hints`). Has `id` (hash) and `parent_id` (lineage).
3. **HarnessManager** (RED for validation, GREEN for storage format): applies typed edits, enforces I4 and I10, stores versions as a lineage DAG, supports rollback to any ancestor.
4. **LLMClient** (RED): one wrapper with disk cache, cost metering, hard caps, retries, seeded sampling. Cache key MUST include model, messages, parameters, and a `sample_index` so different seeds still produce different samples.
5. **TraceStore** (YELLOW): SQLite plus JSONL. Stores traces, scores, costs, per task, per version, per seed.
6. **Diagnoser** (GREEN): turns failures (and optionally successes) into a structured diagnosis for the proposer.
7. **Proposer** (GREEN): generates candidate edits (typed patches) given the current harness, diagnosis, and lineage memory.
8. **Validator** (YELLOW): runs current vs candidate on the same `val` tasks and seeds, producing **paired evidence**.
9. **Gate** (GREEN in dev, **frozen** for final): decides accept/reject from paired evidence plus constraints (section 7.4).
10. **SearchPolicy** (GREEN): controls which versions are explored and how budget is spent (greedy, beam, population, successive halving).
11. **Orchestrator** (YELLOW): the round loop that wires the above together. Resumable.
12. **Experiment Runner and Reporter** (YELLOW): runs configs, writes ledgers, produces tables and plots.

### 5.3 The loop (reference version)

```
state = load_or_init(config)            # resumable
while not budget_exhausted(state) and not patience_exhausted(state):
    batch    = sample(opt_tasks, state.batch_size)
    results  = run(current, batch)                      # traces stored
    diag     = diagnoser.diagnose(results)              # opt split only
    cands    = proposer.propose(current, diag, lineage_memory)   # <= K candidates
    for c in cands:
        ev   = validator.compare(current, c, val_tasks, seeds)   # paired
        dec  = gate.decide(current, c, ev)
        log(c, ev, dec)
    current  = search_policy.select(current, accepted_candidates)
    checkpoint(state)
```

---

## 6. Data splits and freeze protocol (RED)

### 6.1 Splits

- Each benchmark's tasks are partitioned into `opt` (loop learns from), `val` (gate decides), `test` (final report only).
- Suggested default: 40% / 20% / 40%, stratified by any available difficulty or category label. Owner may change sizes before the freeze.
- Manifest: `data/splits/<benchmark>.json` with task ids, seed, generation script hash. Commit it, then never touch it.
- Also keep a small **guard set** drawn from `val`: tasks the current version already passes. The gate uses it to detect regressions.

### 6.2 Two phases

**Phase A: Development (allowed to iterate)**
- Use the **dev benchmark** only (a small, chosen slice, see section 10). Use `opt` and `val` only. Compare variants here. Select a single finalist configuration using dev `val` scores only.

**Phase B: Freeze**
- Create a git tag `freeze-<date>`. Write `docs/PROTOCOL.md` containing: final config hash, model names and versions, budgets, seeds, benchmark versions, split manifest hashes, hypotheses, and the exact report template.
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
- S3: S2 + persistent notes/skills files (agent-readable guidance).
- S4: S3 + simple routing/workflow hints (e.g. when to ask a clarifying question, when to call which tool first).

Hypothesis to test: more surface helps up to a point and then overfits.

### 7.2 Diagnoser variants

- D0: none (proposer sees raw failed traces).
- D1: per-trace critique, then merge.
- D2: cluster failures by cause, then diagnose each cluster.
- D3: contrastive: pair a failure with a similar success on the same task family and ask what differed.
- D4: counterfactual probing (re-run a failed task with a candidate hint and observe).
- D5: your own.

### 7.3 Proposer and search variants

- P1: single-shot rewrite from failure summary (naive baseline).
- P2: reflective, per-cause targeted edits, small patches only.
- P3: population with Pareto selection across tasks (GEPA-style; use the `gepa` package or DSPy's GEPA as a **baseline**, and implement your own variant as the framework).
- P4: beam or tree search over versions in the lineage DAG.
- P5: multi-proposer ensemble (different prompts/temperatures) with deduplication.
- P6: lineage-aware proposer (sees previously rejected edits and why, avoids repeats, can combine two accepted ancestors).
- P7: successive halving across candidates to save budget (cheap screen on few `val` tasks, expand only promising ones).
- P8: your own.

### 7.4 Gate and regularization variants

The gate decides acceptance. Variants to compare:
- G1: greedy: accept if mean paired delta > margin.
- G2: paired bootstrap: accept if lower bound of the delta CI > 0.
- G3: G2 plus a **guard set** rule: reject if more than X% of previously passing guard tasks now fail.
- G4: G3 plus an **edit-size penalty** (prefer small diffs; require larger gains for larger edits).
- G5: sequential testing (stop early on clear win or loss to save budget).
- G6: Pareto acceptance (must not worsen any task category beyond tolerance).
- G7: your own.

Regularizers to ablate: edit-size cap, artifact-length cap, rollback on later regression, replay of old failures, diversity pressure, "simplicity" preference.

### 7.5 Second-order improvement (EXPERIMENTAL track, clearly labeled)

You MAY test letting the framework improve **its own proposer/diagnoser prompts**, using the same gate and a separate dev-only evaluation. This track:
- MUST be tagged `experimental-second-order` in all logs.
- MUST NOT touch invariants, scorers, splits, or the gate's final-test procedure.
- MUST have its own budget cap.
- Only enters the finalist if it beats first-order variants on dev `val` and passes review (record in `docs/DECISIONS.md`).

### 7.6 How to run experiments (MUST)

For each experiment:
1. Write a hypothesis in `experiments/EXPERIMENTS.md` (template in Appendix D).
2. Define it as a config file under `configs/experiments/` (config hash recorded).
3. Run on **dev `opt`/`val` only**.
4. Record results, cost, and a verdict (adopt / drop / revisit) in the log.
5. Keep the code for dropped variants in `strategies/archive/` with a one-line reason. Do not delete negative results.

Promotion to finalist requires: wins on dev `val` over the current best, at comparable cost, across at least 2 seeds (or paired bootstrap if only 1), and no weakening of any invariant.

### 7.7 Autonomy levels for the agent

- **Level 1:** implement the baseline architecture and reference variants exactly as specified.
- **Level 2:** explore the variants in 7.1 to 7.5 within the dev benchmark.
- **Level 3:** propose new components or interfaces. Write the rationale in `docs/IDEAS.md` and note the change in `docs/DECISIONS.md` if it touches YELLOW code.

Go to Level 3 only after Level 1 is green and at least a few Level 2 experiments are logged.

---

## 8. Baselines and ablations

Baselines (all use the same model, tasks, seeds, and budget):

- **B0:** untouched agent, default harness.
- **B1:** off-the-shelf optimizer (GEPA, via its package or DSPy; **verify** current API). Use its default recommended settings, document them, and give it the same token budget.
- **B2:** naive loop: one LLM rewrite of the system prompt from failure summaries, no gate (accept always).
- **B3:** naive loop with a simple greedy gate (G1).

Ablations on the finalist:
- Remove the gate (always accept).
- Remove the diagnoser.
- Remove the guard set.
- Remove edit-size regularization.
- Vary optimization budget (e.g. 25%, 50%, 100%) to produce a performance-versus-budget curve.
- Swap the model (H4), if budget allows.

---

## 9. Statistics and reporting

- **Primary metric:** pass rate (or the benchmark's native programmatic metric) on `test`.
- **Paired design:** same tasks and seeds before and after. Report mean delta with a 95% **paired bootstrap** CI over tasks (and over seeds if there are at least 3).
- For pass/fail outcomes also report a paired test (e.g. McNemar) and the raw counts of tasks flipped in each direction.
- **Seeds:** at least 3 per final condition if the budget allows. If not, say so and report the weaker evidence honestly.
- **Also report:**
  - generalization gap (opt gain minus test gain),
  - accept rate and rejection reasons,
  - regressions introduced and later rolled back,
  - cost: tokens, dollars, wall time per benchmark,
  - cost per +1 percentage point,
  - lineage depth and number of accepted edits,
  - failures of the framework (benchmarks where it did not help).
- **Multiple comparisons:** many variants were tried in dev. Only the finalist is evaluated on test, so no test-set variant selection. State this in the write-up.
- **Claims discipline:** results hold for the stated model(s), benchmark versions, and budgets. Do not generalize beyond them. A gain on a cheap or small model does not imply a gain on frontier models.

Output artifacts: `results/ledger.jsonl` (append-only), `results/tables/*.md`, `results/plots/*.png`, `results/REPORT.md`, plus a `REPRODUCE.md` with exact commands.

---

## 10. Benchmarks and adapters

**Verify everything in this section against the current upstream repos before coding.** Names, install steps, task counts, and licenses may differ from what is assumed here.

### 10.1 Suggested suite

| Role | Benchmark | Why | Notes |
|---|---|---|---|
| Dev | `toy-bench` (synthetic) | Unit tests of loop mechanics at zero cost | Deterministic mock agent whose behavior depends on harness text. Build first. |
| Dev | Small slice of **τ²-bench** (one domain) | Realistic conversational, policy-bound tool use | Use only the dev slice for design decisions. |
| Eval 1 | **τ²-bench**, remaining domain(s)/tasks | Customer support style agent; programmatic outcome checks | Protect the benchmark's domain policy: only an *additive* guidance artifact is editable. |
| Eval 2 | **ITBench** (offline / snapshot variant if available) | Operational diagnosis (incident-response style) | Live variants may need Kubernetes: skip if so. Verify the offline path is reproducible. |
| Optional | A coding or finance benchmark | Third agent type | Skip if it needs Docker or heavy infra. Check licenses. |

The owner may change this before the freeze. The framework MUST NOT assume any particular benchmark.

### 10.2 Adapter requirements

- Implement `BenchmarkAdapter` (Appendix A).
- Declare the editable surface and protected parts explicitly. **Never expose the benchmark's ground-truth rules, scorer, or hidden state to the loop.**
- Expose the agent's harness inputs (system prompt addition, tool descriptions, notes) via `HarnessSpec` artifacts. If the benchmark's agent cannot accept a given artifact type, do not declare it.
- Return a score in [0, 1] from the benchmark's own programmatic checks, plus a trace (messages, tool calls, outcomes) and cost.
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
- **Optional open-model path:** an adapter-independent `LLMClient` backend for a locally served open model (e.g. via an OpenAI-compatible server). Never required for the main results.

---

## 12. Repo layout, stack, and standards

```
rsi-harness/
  DESIGN.md
  README.md
  docs/            PROTOCOL.md  DECISIONS.md  QUESTIONS.md  IDEAS.md  LICENSES.md
  core/            types.py  harness.py  llm.py  budget.py  trace_store.py
                   validator.py  orchestrator.py  stats.py        # RED/YELLOW
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
- SQLite for the trace store. JSONL for logs and ledger.
- Every module has docstrings stating its invariants. Keep functions small and pure where possible.
- Tests: `tests/invariants/` MUST include checks for I3 (no test leakage), I4 (edits outside surface rejected), I5 (no direct LLM calls outside the client), I7 (core does not import adapters), and budget-cap enforcement.
- CI (simple): lint, type check, unit tests with the mock LLM. No paid API calls in CI.

---

## 13. Milestones and acceptance criteria

| # | Milestone | Acceptance |
|---|---|---|
| M0 | Scaffold, config system, CLI, CI | `rsi-harness --help` works; CI green |
| M1 | `LLMClient` with cache, meter, caps; `TraceStore` | Replaying a run costs $0; hitting the cap stops and checkpoints |
| M2 | `HarnessSpec` and `HarnessManager` with lineage, edit validation, rollback | Out-of-surface edit rejected; rollback restores exact hash |
| M3 | `toy-bench` and mock agent | Reference loop provably improves toy score in tests |
| M4 | Reference loop (P1 + G1) end to end, resumable | Interrupt and resume yields identical final state |
| M5 | Splits manifest generator, split-leakage tests, stats module | I2/I3 tests pass; bootstrap and McNemar unit-tested on synthetic data |
| M6 | τ²-bench adapter + baselines B0 to B3 on dev slice | Baseline numbers reproduced and logged; cost recorded |
| M7 | GEPA baseline (B1) integrated | Runs under the same budget and logging |
| M8 | Strategy plugins + experiment runner; at least 6 logged experiments | Entries in `EXPERIMENTS.md` with verdicts |
| M9 | Ablations and finalist selection on dev `val` | Finalist config file chosen; selection rationale documented |
| M10 | **Freeze** (tag, `PROTOCOL.md`) | Owner sign-off |
| M11 | ITBench (offline) adapter; final runs on all evaluation benchmarks | Ledger entries; REPRODUCE.md verified |
| M12 | Report, plots, write-up draft, release checklist | `REPORT.md` complete; license check done |

Stop and ask (via `QUESTIONS.md`) if a milestone's acceptance cannot be met within budget.

---

## 14. Change governance and zones

| Zone | What | Rule |
|---|---|---|
| **RED** | Invariants I1 to I10, `LLMClient` caps, split manifests, scorer access, final-test procedure, results ledger | No change without owner approval |
| **YELLOW** | Adapters, `HarnessSpec`, validator, orchestrator, trace store, stats | Change allowed with an entry in `docs/DECISIONS.md` (what, why, impact on past results) |
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
| Overfitting to `val` or the dev benchmark | Fixed splits, guard set, freeze protocol, untouched `test`, generalization-gap reporting |
| Reward hacking of the proxy | Programmatic scorers only, protected benchmark internals, review accepted diffs by hand for a sample |
| Noisy results from small samples | Paired design, bootstrap CIs, multiple seeds, honest "inconclusive" label |
| Budget overruns | Caching, hard caps, cheap-first development, successive halving |
| Benchmark changes upstream | Pin versions and commits; record in the ledger |
| Weak proposer (cheap model) | Treat a stronger proposer as a logged experiment; report the model dependence |
| Leakage via logs or caches | I3 tests; separate cache namespaces for `test` runs |
| Scope creep | Non-goals list; Level 3 work only after Level 1 and 2 are done |
| License problems blocking publication or later commercial use | `docs/LICENSES.md` early; avoid non-commercial data in headline results if unclear |

---

## 16. Open questions for the owner (the agent should confirm before M6)

1. Which model(s) and API provider, and what total budget (per round and overall)?
2. Final benchmark list and the dev slice.
3. Split ratios and the number of seeds affordable.
4. Whether to include the optional second-model experiment (H4).
5. Which license the released code should use, after checking dependency licenses.

---

## Appendix A: Interface sketches (Python, illustrative; adapt freely, keep the contracts)

```python
from dataclasses import dataclass, field
from typing import Protocol, Literal, Any

Split = Literal["opt", "val", "test"]

@dataclass(frozen=True)
class Task:
    id: str
    benchmark: str
    payload: dict[str, Any]          # opaque to core

@dataclass(frozen=True)
class HarnessSpec:
    id: str                          # content hash of artifacts
    parent_id: str | None
    artifacts: dict[str, str]        # e.g. "system_prompt", "tool:search.description", "notes/tips.md"

@dataclass(frozen=True)
class Edit:
    artifact: str
    op: Literal["replace", "append", "insert", "delete"]
    text: str = ""
    anchor: str | None = None        # for insert/replace-within

@dataclass
class Cost:
    prompt_tokens: int
    completion_tokens: int
    dollars: float
    seconds: float

@dataclass
class RunResult:
    task_id: str
    harness_id: str
    seed: int
    score: float                     # [0,1], programmatic
    passed: bool
    trace: list[dict[str, Any]]
    cost: Cost
    error: str | None = None

@dataclass(frozen=True)
class SurfaceDecl:
    editable: dict[str, dict]        # artifact name -> {max_chars, description}
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
    guard_regressions: int
    edit_chars: int
    cost: Cost

class Gate(Protocol):
    def decide(self, current: HarnessSpec, candidate: HarnessSpec,
               evidence: PairedEvidence) -> "Decision": ...

class SearchPolicy(Protocol):
    def select(self, current: HarnessSpec, accepted: list[HarnessSpec],
               lineage: "Lineage") -> HarnessSpec: ...
```

## Appendix B: Example config

```yaml
run_id: dev-tau2-p2-g3-001
workdir: ./runs            # /kaggle/working on Kaggle
seed: 7
benchmark:
  name: tau2
  domain: airline          # dev slice
  splits_manifest: data/splits/tau2_airline.json
models:
  agent:      {name: <cheap-model>, temperature: 0.0}
  user_sim:   {name: <cheap-model>, temperature: 0.0}
  proposer:   {name: <cheap-model>, temperature: 0.7}
budget:
  total_dollars: 20.0
  per_round_dollars: 1.0
  per_candidate_dollars: 0.25
loop:
  rounds: 15
  opt_batch: 12
  candidates_per_round: 3
  val_tasks: 20
  seeds: [0, 1]
  patience: 4
strategies:
  surface: S3
  diagnoser: {name: d2_cluster}
  proposer:  {name: p2_reflective, max_edit_chars: 800}
  gate:      {name: g3_guard, alpha: 0.05, guard_tolerance: 0.05}
  search:    {name: greedy}
```

## Appendix C: Evidence package (one per accepted version)

```json
{
  "version_id": "h_9f3a...",
  "parent_id": "h_41bc...",
  "diff": [{"artifact": "system_prompt", "op": "append", "text": "..."}],
  "motivating_task_ids": ["..."],
  "diagnosis_summary": "...",
  "validation": {
    "task_ids": ["..."], "seeds": [0,1],
    "mean_delta": 0.06, "ci95": [0.01, 0.11],
    "flipped_to_pass": 5, "flipped_to_fail": 1,
    "guard_regressions": 0
  },
  "gate": {"name": "g3_guard", "decision": "accept", "reason": "..."},
  "cost": {"dollars": 0.31, "prompt_tokens": 0, "completion_tokens": 0},
  "created_at": "..."
}
```

## Appendix D: Experiment log entry template

```
### EXP-<nnn>: <short name>
- Date / config hash / git commit:
- Hypothesis:
- Variant(s) vs baseline (what changed):
- Benchmark / split / seeds / budget:
- Results (opt, val; never test): table
- Cost:
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
Split manifests (hashes):
Budgets and seeds:
Hypotheses H1 to H4 (as written before final runs):
Baselines and ablations to be run:
Primary and secondary metrics:
Statistical procedures:
Report template location:
Deviations allowed: none. Anything else is labeled post-hoc.
```

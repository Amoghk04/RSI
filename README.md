# rsi-harness

Working name. A **benchmark-agnostic** loop that improves an LLM agent's *harness* (prompts, tool descriptions, notes/skills, routing hints) with **model weights frozen**. Every accepted change is versioned, evidenced, validated on held-out tasks, and reversible.

This repository is the v1 research proof, not a product. Read `DESIGN.md` before writing code. Zones: **RED** (do not change), **YELLOW** (`docs/DECISIONS.md`), **GREEN** (log the experiment).

Nothing here is a published result. There is no `test` number until freeze + Phase C.

## Status

**M4** Resumable orchestrator (P2 + G7), validator, champion audit stub — `configs/toy-m4.yaml`.

**M3** `toy_bench` adapter + reference loop (proves score improves in tests).

**M2** `HarnessManager`: surface (I4), playbook bullets, bounds (I10), leakage (I11), lineage + rollback.

**M1** `LLMClient` (mock + OpenRouter), disk cache, budget meter, `TraceStore` with split views.

**M0** scaffold: install, CLI, config validation, CI.

```bash
uv sync --all-extras --dev
uv run rsi-harness --help
uv run rsi-harness validate-config configs/base.yaml
uv run rsi-harness run -c configs/ci-mock.yaml --dry-run
uv run pytest
```

## Prototype config

- OpenRouter, **$50** hard cap — `configs/base.yaml`, `OPENROUTER_API_KEY` in `.env.example`
- License intent: **AGPL-3.0** + commercial license for non-AGPL use — `docs/COMMERCIAL.md`

## Docs

- `DESIGN.md` — contract
- `docs/DECISIONS.md` — approved changes
- `docs/QUESTIONS.md` — open questions (ITBench variant Q-003; H4 Q-005)
- `docs/PROTOCOL.md` — filled at freeze
- `docs/LICENSES.md` — fill before any public post

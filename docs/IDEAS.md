# Ideas (GREEN)

Speculative. Nothing here is a requirement. If an idea is adopted into YELLOW or RED, log it in `DECISIONS.md`.

---

## Product trajectory (not part of the v1 scientific claim)

Intent, recorded so the benchmark work stays a **proof** of a later product rather than becoming the product.

1. **Now (this repo):** governed, frozen-weight, text/config RSI on public agent benchmarks. Artifact: code, configs, seeds, evidence packages, append-only ledger, write-up.
2. **Public proof:** 2–4 posts that show a *governed* improvement (diff + why + val evidence + rollback), not a leaderboard screenshot. Audience: researchers and operators, not "we invented RSI."
3. **OSS core:** adapter protocol + `LLMClient` + harness manager + gate + ledger. This is the trust surface. Keep enterprise adapters, policy packs, and hosted metering closed later if needed (depends on Q-006).
4. **Design partners (B2B):** customer-support and incident-response teams whose agents already look like τ² / ITBench. Sell *governance* (every change evidenced, reversible, budget-capped), not "we beat GEPA."
5. **Later, not now:** the same gate and ledger around **weight** updates (LoRA / continued pretrain / online RL). New invariants: canary traffic, eval gates on production traces, rollback of weights, separate budget. Do not advertise this until (1) is real.

Deliberately out of v1: UI, hosted service, domain packs, live weight updates, second-order self-modification of the improver as a product feature.

---

## Method ideas to try only after Level 1 is green

- Bullet-level credit: keep usefulness / harm counters per playbook bullet (ACE).
- Proposer browses opt-only trace files (Meta-Harness filesystem) with a cheap model — likely too weak; try only as a logged experiment with a stronger proposer.
- Component-wise tracks then merge (HarnessCompass): tool descriptions vs notes vs routing, separate candidates, then a combine step.
- CHASE-style protocol perturbations as a *diagnostic* that a shortcut exists, not as a scorer. Must not invent new τ² tasks that peek at hidden policy.
- Successive halving (P7) as default if val rollouts dominate cost.

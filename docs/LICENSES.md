# License findings

Check each benchmark and each dependency for the intended use: research publication now, possible commercial use later. Fill this **before** any public post or OSS drop (Q-006).

Do not put proprietary, employer, or confidential data in this repo.

| Component | Version / commit | License | Research OK? | Later commercial OK? | Notes |
|---|---|---|---|---|---|
| this repo | unreleased | **AGPL-3.0** (+ commercial — D-010) | yes | via commercial license | Full AGPL text + dep audit before public launch |
| τ² / τ³-bench | pin before M6 | MIT (verify at pin) | yes | yes | `tasks.json` 2285 telecom; our `test` = upstream `base` 114 |
| ITBench-Lite | *verify* | reported Apache-2.0; confirm | | | Headline scorer is ours (D-003), not the judge toolkit |
| ITBench-AA | *verify* | *verify* | | | |
| GEPA / `optimize_anything` | *verify* | *verify* | | | B1 only |
| ACE | *verify* | *verify* | | | B4 only |
| litellm (if used) | *verify* | *verify* | | | Inside `LLMClient` only |

Update this table when adding a dependency. Pin versions in the ledger.

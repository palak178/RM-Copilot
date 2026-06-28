# config/

Runtime configuration **data** (not code).

## `scoring.yaml` (authored in M2)
The transparent, tunable scoring configuration designed in
[`../docs/data-model.md` §6](../docs/data-model.md): Value-score factors,
Propensity-score factors, temporal **trigger** rules, weights, thresholds,
confidence bands, the ranking composite, reason-code templates, and compliance
rules.

Editing weights/factors/triggers here changes scoring behaviour **without code
changes** — this is the project's main extensibility lever for the analytics core.

Validated at load time by the typed loader in `src/rm_copilot/config/scoring.py`.

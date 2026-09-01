# Roadmap

## v14.4

### Rider-first mechanical model

Inventory and then standardize ability representation around one rider per Manifested Strike while preserving every current rule outcome and the existing action economy. The accepted Phase 1 [rider-first model inventory](rider-model-inventory.md) covers every concrete ability, and the [neutral mechanical primitives design](mechanical-primitives-design.md) classifies the existing Calculator/harness fields and defines the gated migration sequence.

The schema 2.5.0 migration now models every machine-consumed ability through neutral per-entity mechanics. All 30 Calculator entries and all 27 harness feature rules are ordered derivation references rather than duplicated mechanical rows; the loader materializes the unchanged legacy-shaped contracts, and aggregate plus sentinel compatibility snapshots fail closed on output drift. Utility-only abilities remain canonical prose until a real consumer demonstrates a structured-data need.

Area delivery has two patterns: an area rider delivered by a Manifested Strike hit and a standalone area delivered through its existing independent activation. Neither pattern introduces a composite-rider category.

Tracking: [#132](https://github.com/kmart01123/kinetic-vanguard/issues/132).

### Gravitic Press disposition

After the rider-model migration boundary is secure, make an explicit keep, rework, or retire decision for Gravitic Press. Do not change its mechanics as part of the representation refactor.

Tracking: [#133](https://github.com/kmart01123/kinetic-vanguard/issues/133).

### Fighter 20 damage scaling

Diagnose the level-20 comparator crossover and subclass scaling by discipline before proposing mechanics. Keep single-target damage findings separate from discipline control tradeoffs, and prefer surgical late-game maturation if a rules change is justified.

Tracking: [#122](https://github.com/kmart01123/kinetic-vanguard/issues/122).

### External-review diagnostics

Make doctor and provider failures actionable while preserving exact-head validation, atomic posting, isolation, redaction, and fail-closed behavior. This tooling work is independent of subclass mechanics.

Tracking: [#119](https://github.com/kmart01123/kinetic-vanguard/issues/119).

## Completed parking-lot item

Forked Lightning's independent primary and secondary saving throws were resolved in v13.1.0. The old v13.1 parking-lot entry was removed because it no longer described an open rules issue.

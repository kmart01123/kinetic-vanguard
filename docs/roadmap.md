# Roadmap

## v15.0 development (continuing the v14.4 roadmap)

### Rider-first mechanical model

Inventory and then standardize ability representation around one rider per Manifested Strike while preserving every current rule outcome and the existing action economy. The accepted Phase 1 [rider-first model inventory](rider-model-inventory.md) covers every concrete ability, and the [neutral mechanical primitives design](mechanical-primitives-design.md) classifies the existing Calculator/harness fields and defines the gated migration sequence.

The schema 2.7.0 migration models every machine-consumed ability through neutral per-entity mechanics and colocates every machine-consumed shared progression/core field with one canonical rules entity. Delivery and targeting are orthogonal axes, and concrete D&D damage/save facts live with each feature. The obsolete 30-entry Calculator registry, 27-entry harness registry, and ten shared-field reference slots have been removed. The browser publication and Python harness adapter now derive deterministic consumer views directly from canonical entity order, with focused semantic equivalence checks failing closed on output drift. Player-facing procedures and utility-only abilities remain canonical prose until a real consumer demonstrates a structured-data need.

An area effect combines `targeting.topology: area` with its independently authored delivery. A rider-delivered area and a standalone area share the same targeting concept without creating combined schema types or a composite-rider category.

Completed in PR #134; issue [#132](https://github.com/kmart01123/kinetic-vanguard/issues/132) is closed. The separate Phase Step family force/Strength correction landed in PR #137 and issue #136 is also closed.

### Completed resolution simplification

Implemented the approved rules in [PR #140](https://github.com/kmart01123/kinetic-vanguard/pull/140): normal Action Surge access for standalone psionic Actions, Electron Burst target parity, Static Discharge's 1/3/5 additional-target ladder, class-wide Tier-2 feature/rider resistance penetration, and explicit partial-on-success control. Fresh damage/control evidence validated this baseline before the Apex work.

Completed: [#135](https://github.com/kmart01123/kinetic-vanguard/issues/135).

### Gravitic Press retirement

The approved retirement in [PR #141](https://github.com/kmart01123/kinetic-vanguard/pull/141) removes Gravitic Press from the Advanced Training pool, rules publication, and consumer projections. Removing this published option begins the unreleased v15.0.0 development line under the versioning policy. All retained feature mechanics remain unchanged.

Completed: [#133](https://github.com/kmart01123/kinetic-vanguard/issues/133).

### Fighter 20 damage scaling

The adopted Apex maturation is implemented in [PR #143](https://github.com/kmart01123/kinetic-vanguard/pull/143). The broader level-20 comparator diagnosis remains open: single-target damage still sits below the comparator interval for some disciplines, and those findings must be considered alongside discipline control tradeoffs.

The maintainer adopted 3d8 Apex for all four disciplines at Fighter 18: cold, fire, force, and lightning respectively. One shared Discipline Maturation procedure preserves normal defenses, no critical doubling, no resource cost, and one use per Attack action. The [historical evaluation](discipline-apex-evaluation.md) records the original first-hit results. The current correction requires declaring maturation before rolling and spends the use even on a miss; the [declaration baseline evaluation](maturation-declaration-evaluation.md) measures that procedure and verifies that earlier levels, comparators, and control results are unchanged. Refined Holdout remains available to every discipline.

Integrated follow-up: Absolute Zero uses 6d10 + 45/55/65 cold damage, and Telekinetic Shove increases to 4 force damage at every tier from Fighter 18. Branching Bolt now allocates 3/4/5 rider dice from Fighter 7, with Tier 2 still requiring Fighter 10. Every use requires the primary plus at least two distinct hostile secondaries, with at least one die per target. Declare the allocation before the original strike; its hit delivers every packet without additional attack rolls. This supersedes the earlier Fighter-18 two-die Focused Bolt option. Canonical mechanics drive the Calculator and native harness. Pyrokinesis is unchanged, and Cryokinesis stays cold. The [current Branching Bolt integration](branching-bolt-integration.md) records the crowd rule and benchmark; the [earlier surgical integration](surgical-damage-integration.md) preserves the superseded snapshot, and the [candidate report](surgical-damage-candidates.md) retains the earlier experiments.

Tracking: [#122](https://github.com/kmart01123/kinetic-vanguard/issues/122).

### External-review diagnostics

Completed the review-tool changes in [PR #142](https://github.com/kmart01123/kinetic-vanguard/pull/142): actionable diagnostics, independent collection, private resumable checkpoints, native Grok tool IDs, and rejection of explicit CLI errors or interrupted output. Exact-head validation, isolation, and redaction remain enforced. The corrected Grok invocation passed configuration checks; its full live review behavior has not been rerun.

Completed: [#119](https://github.com/kmart01123/kinetic-vanguard/issues/119).

## Completed parking-lot item

Forked Lightning's independent primary and secondary saving throws were resolved in v13.1.0. The old v13.1 parking-lot entry was removed because it no longer described an open rules issue.

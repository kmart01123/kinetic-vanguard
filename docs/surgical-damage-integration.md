# Surgical damage integration

> Historical integration snapshot: unreleased **v15.0.0**, authority schema **2.13.0**, harness projection **1.9.0**. Absolute Zero and Telekinetic Shove retain the changes below. Branching Bolt's adopted two-die Focused Bolt option was later **superseded** by the [current crowd allocation](branching-bolt-integration.md); it is no longer playable. The benchmark numbers and validation results below describe this earlier snapshot.

The following changes were adopted for this snapshot. The original two-die Focused Bolt is distinct from the later [three-die focused T1 trial and its 3-Psi alternative](focused-bolt-t1-benchmark.md), which were discarded without adoption.

| Feature | Behavior adopted in this snapshot |
|---|---|
| Absolute Zero | At Fighter 20, 6d10 + 45/55/65 cold damage at T0/T1/T2. A successful Constitution save halves the entire packet, rounding down. |
| Telekinetic Shove | From Fighter 18, 4 additional force damage at every tier. Earlier levels retain 2. |
| Branching Bolt | **Superseded:** from Fighter 18, declare Focused Bolt before rolling: forgo all additional targets and deal two Manifested Strike dice of lightning rider damage to the struck target. The option was identical at every tier. |

In this snapshot, Pyrokinesis and the shared pre-roll 3d8 Discipline Maturation procedure were unchanged. Costs, tier availability, action economy, native damage types, and control effects were preserved. Focused Bolt was a choice even when additional enemies were available; it could not stack with ordinary branching on the same strike. Unused branches provided no further damage.

The Calculator in this snapshot derived the new formulas and optional rider mode directly from canonical mechanics. It showed Shove's damage at the selected Fighter level and offered both normal and focused damage calculations from Fighter 18. Its established display policy rounded expected averages upward; the benchmark retained exact probability-weighted values and integer damage rounding.

## Full native benchmark

The full native run used **12 workers**, covered all **47 headline creature profiles** at Fighter levels **7/11/15/20** and cluster sizes **1/3/6**, and completed in 20.1 minutes. Each case reoptimized the legal action policy and Action Surge schedule. It produced **564 damage detail rows**, **96 damage matrix rows**, and all five control publication arrays.

| Discipline | Previous single-target DPR | Integrated DPR | Gain | Snapshot comparator band |
|---|---:|---:|---:|---|
| Pyrokinesis | 126.818 | 126.818 | +0.000 (+0.00%) | COLD (-1.31%) |
| Cryokinesis | 87.100 | 94.934 | +7.833 (+8.99%) | COLD (-26.12%) |
| Psychokinesis | 108.782 | 120.751 | +11.969 (+11.00%) | COLD (-6.03%) |
| Electrokinesis | 106.497 | 116.064 | +9.567 (+8.98%) | COLD (-9.68%) |

All three selected disciplines gain single-target damage. Their means remain below the lower comparator boundary; these changes improve the maintained damage results without establishing universal balance. The single-target comparator means remain **128.502 DPR** for Eldritch Knight and **164.824 DPR** for Battle Master.

| Discipline | Three-target aggregate, before → after | Six-target aggregate, before → after |
|---|---:|---:|
| Pyrokinesis | 126.818 → 126.818 | 126.818 → 126.818 |
| Cryokinesis | 151.308 → 151.308 | 151.308 → 151.308 |
| Psychokinesis | 113.939 → 124.035 | 122.050 → 132.062 |
| Electrokinesis | 146.306 → 146.318 | 208.723 → 208.723 |

Verification matched all **72 accepted experimental cases** to native results within 1e-9 DPR. All **456 earlier-level/Pyrokinesis damage rows**, including their selected policies, are unchanged. Every comparator value and schedule is unchanged. All five control arrays are identical except for authority provenance. Costs, control projections, shared core mechanics, and all other feature projections are unchanged.

Authority SHA-256: `a7720742b9c857721d40175c8fdc17585b7f8184d89e6d6a893b46efd5239889`.

## Validation

Passed: 81 Node tests; 285 harness tests and 157 developer-tool tests across eight concurrent processes; 12 Chromium/Firefox layout tests, including focused-mode containment on mobile and desktop; type checking; canonical and harness validation; toolchain consistency; deterministic prototype build; publication write/check; and whitespace validation.

## Evidence

The retained run is in `artifacts/surgical-integration/`. `benchmark.py generate` freezes input hashes, runs the native damage and control evaluators, and retains all six publication arrays. `verify.py` compares every earlier-level/Pyrokinesis row and all comparator/control evidence against the declaration baseline, and checks all 72 accepted experimental single/six-target cases. `benchmark.py --write` and `--check` use the standard publication validator with those freshly generated arrays after checking that inputs still match.

Historical design evidence remains in the [surgical candidate evaluation](surgical-damage-candidates.md), [Absolute Zero lower-dice evaluation](absolute-zero-low-dice.md), and [pre-surgical declaration baseline](maturation-declaration-evaluation.md).

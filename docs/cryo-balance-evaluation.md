# Cryokinesis damage and control disposition

## Scope

The maintainer accepts Pyrokinesis, Psychokinesis, and crowd-focused Electrokinesis after PR #145. Cryokinesis receives a modest Fighter-20 damage correction while remaining below Pyrokinesis in the maintained single-target benchmark. The objective is to ease a disproportionate deficit, not make every discipline match a damage comparator or maximize damage and control simultaneously.

The baseline is main commit `f0913257014ffcef65fd14b5c9e5194fcc32df87`, after PR #145. All 33 frozen authority, consumer, evaluator, comparator, roster, and configuration hashes match the retained Branching Bolt integration evidence.

## Why a tradeoff remains appropriate

Before this change, Cryokinesis averages 94.934 single-target DPR at Fighter 20 against 128.502 Eldritch Knight and 164.824 Battle Master DPR. Three cold-immune headline targets average 54.818; the other nine average 108.305 against an Eldritch Knight mean of 127.451 for those same nine targets. Cold immunity explains part, but not all, of the damage shortfall.

Cryokinesis also provides strong and reliable control. Its Fighter-20 Control Value is 1.204 CU with 99.97% initial delivery, compared with Pyrokinesis's 0.555 CU / 85.45%, Psychokinesis's 1.672 CU / 87.35%, and Electrokinesis's 0.469 CU / 57.19%. These are the current [control benchmark](../CONTROL_BENCHMARK_DETAIL.md) results. Initial delivery means some modeled control establishes; it is not a guaranteed stun or a three-round lock.

Absolute Zero T2 makes Speed 0 even on a successful save and adds Stunned on failure. Cold immunity does not itself remove that control. Snow Chains offers another reliable control package. These benefits justify retaining a damage tradeoff. Psychokinesis's higher scalar Control Value does not establish dominance: Cryokinesis's higher reliability, individual effect packages, encounter geometry, and the scoring model's contextual limits matter.

Damage and control use separate selection objectives and opportunity windows. Their independently optimized headline values cannot be added, converted through an invented CU-to-DPR exchange rate, or claimed as simultaneous performance by one rotation. The damage benchmark excludes most control feedback and ally-turn benefits; the control benchmark does not monetize all effects into damage prevented or added.

## Candidate selection

A bounded native-planner experiment evaluated every Fighter-20 headline target at cluster size 1 with larger Absolute Zero flat bonuses. The shared rules, control, resource accounting, immunity, comparators, and target weighting remained fixed.

| Extra damage at each tier | Mean single-target DPR | Disposition |
|---|---:|---|
| 0 | 94.934 | Existing baseline |
| 30 | 110.469 | First modest candidate |
| **40** | **115.736** | **Final requested candidate: 10 more per tier than the first modest candidate** |
| 50 | 121.004 | Closer to Pyrokinesis than needed for a modest correction |
| 100 | 147.343 | Too large for the selected direction |
| 150 | 173.681 | Too large for the selected direction |

After considering control, the maintainer chose a modest buff that keeps Cryokinesis below Pyrokinesis. The first +30-per-tier candidate produced 110.469 single-target DPR and unchanged three/six-target aggregate DPR of 151.308. The maintainer then requested 10 more damage at every Absolute Zero tier; the final packet below adds 40 per tier to the merged baseline. The final packet is **6d10 + 85/95/105 cold damage** at T0/T1/T2. It retains six dice, 5 Psi, normal Blood Tax, Constitution saving throws, whole-packet half damage on success, all control effects, native damage type, immunity, and Fighter-20 availability. Shared Discipline Maturation remains a separate pre-roll gamble and is not triggered by this standalone action.

Rules stay on the unreleased 15.0.0 line. No schema or projection shape changes, so schema 2.15.0 and projection 1.11.0 remain unchanged. Published v14.3.0 is unaffected.

## Measured candidate comparison

The +30 and +40 candidates were each independently evaluated against all 12 Fighter-20 headline targets at cluster sizes 1, 3, and 6 with reoptimized native action policies and Action Surge schedules. These focused runs do not substitute for the final full-roster integration run.

| Packet | Single-target DPR | Three-target aggregate DPR | Six-target aggregate DPR |
|---|---:|---:|---:|
| Merged baseline: 6d10 + 45/55/65 | 94.934 | 151.308 | 151.308 |
| First modest candidate: 6d10 + 75/85/95 | 110.469 | 151.308 | 151.308 |
| Final requested candidate: 6d10 + 85/95/105 | 115.736 | 151.308 | 151.308 |

The additional 10 per tier adds 5.268 roster-mean DPR over the first modest candidate. The final candidate is 21.91% above the merged Cryokinesis baseline, 8.74% below Pyrokinesis's 126.818 DPR, and 9.93% below the lower Fighter comparator. Cryokinesis retains a damage tradeoff rather than matching Pyrokinesis. Crowd results and cold-immune fallback results are unchanged in the focused comparisons.

## Verification status

Local validation passed: 83 TypeScript tests, 290 maintained Python harness tests, and 157 developer-tool tests; typechecking; canonical validation of 43 entities; prototype determinism; harness authority/roster validation; and whitespace checks. The Calculator feature snapshot was updated only after verifying that all other features were identical and the entire control/shared-mechanics projection was unchanged. Existing packet-defense and publication regressions verify the new formulas, whole-packet save halving, Resistance, Immunity, and displayed averages.

The full native run completed with 12 workers in 902 seconds: all 47 headline profiles at Fighter levels 7/11/15/20 and clusters 1/3/6, producing 564 damage-detail rows, 96 damage-matrix rows, and all five control publication arrays. Full integration reproduces the focused +40 candidate exactly.

- Only nine Cryokinesis Fighter-20 single-target rows change: Balor, Ancient Blue/Brass/Copper/Gold/Green Dragon, Lich, Pit Fiend, and Solar.
- All 528 rows outside Fighter-20 Cryokinesis retain their numerical values and selected policies.
- All comparator values and schedules are identical.
- Cryokinesis's three/six-target damage and the three cold-immune targets' damage and policies are identical.
- All five control arrays are identical except the expected canonical-authority provenance update. The rendered control publication is unchanged.
- The standard publication writer and checker pass using the frozen native arrays. README now reports Cryokinesis as COLD (-9.93%) at Fighter 20.

Canonical authority SHA-256: `f2f6effd0c6522c1335e63b5be10936c0e12e5ce84af09cd5a2d26d8f2d54853`. Retained evidence is in the implementation checkout's ignored `artifacts/cryo-balance/`: candidate runs, frozen inputs and projection, resumable native checkpoints, damage/control outputs, publication arrays, and scope verification. The interrupted full run for the superseded +30 candidate is historical only and is not counted as completed validation.

Reproduce the maintained full publication evaluation with `python3 -m harness.readme_matrices --check --workers 12`. The implementation run used the same native evaluators and standard publication validator, retaining the generated arrays to avoid a duplicate analytical run during write/check. Browser layouts and the pinned toolchain are checked separately by GitHub CI.

## Final disposition

Cryokinesis retains a real damage cost for its reliable control, but its Fighter-20 single-target shortfall is reduced from 26.12% to 9.93% below the lower comparator. Pyrokinesis, Psychokinesis, and crowd-focused Electrokinesis are accepted unchanged. This closes the remaining development balance scope of #122 upon merge; it does not claim universal encounter balance or publish v15.0.0.

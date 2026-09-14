# Branching Bolt integration into unreleased v15

Branching Bolt uses **3/4/5 Manifested Strike rider dice**, requires **the primary plus at least two distinct hostile secondary targets**, and makes **no additional attack rolls**. This supersedes both the Fighter-18 Focused Bolt option and the experimental two-die threshold rule. The rules version remains **15.0.0**; schema is **2.15.0** and harness projection **1.11.0**.

## Playable rule

Declare the original strike, rider tier, all targets, and the exact allocation before the original attack roll. Every selected target, including the primary, must receive at least one rider die. Each secondary must be a distinct creature hostile to you within 15 feet of the primary. Friendly or neutral creatures cannot be secondary targets, and branches do not continue from secondary targets. A use requires at least three targets, even at Tier 0. Unused branches beyond the two required secondaries can contribute their dice to any selected target, including the primary.

| Tier | Rider dice | Required hostile secondaries | Maximum hostile secondaries | Earliest Fighter level |
|---|---:|---:|---:|---:|
| 0 | 3 | 2 | 2 | 7 |
| 1 | 4 | 2 | 3 | 7 |
| 2 | 5 | 2 | 4 | 10 |

Total targets can be **3 at T0, 3–4 at T1, and 3–5 at T2**. Five targets at T2 means one rider die on the primary and one on each of four secondaries.

An original miss cancels the entire rider, with costs spent. An original hit delivers all allocated rider dice to every declared target, with no saving throw or additional attack roll. Combat Prowess can convert the original miss under its normal rules. There is no threshold, extra-roll critical bonus, or secondary attack state. The original natural 20 doubles only its own base strike dice, never rider dice.

| Tier | Example allocation: primary first | Result after original hit |
|---|---|---|
| 0 | 1 + 1 + 1 | One rider die per target |
| 1 | 2 + 1 + 1 | Two on primary, one on each secondary |
| 1 | 1 + 2 + 1 | One on primary, two on one secondary, one on another |
| 2 | 3 + 1 + 1 | Three on primary, one on each secondary |
| 2 | 1 + 3 + 1 | Three on one secondary, one on each other target |
| 2 | 2 + 2 + 1 | Two on each of two targets, one on the third |
| 2 | 1 + 1 + 1 + 1 + 1 | One die each on five targets |

A single target or a two-target encounter cannot support Branching Bolt. Five dice on one target, four plus one, and zero-die placeholder targets are illegal. Allocations cannot change after the original roll.

Roll each target's complete allocated rider packet and apply that target's defenses once. Tier 2 bypasses lightning resistance, never immunity. The base strike and any Discipline Maturation damage remain separate packets. Normal Psi/Blood costs, one rider per strike, and Tier-2 limits per Attack action remain in force.

## Implementation

The canonical YAML authors a neutral `damage_allocation` rule with `minimum_targets: 3`, `secondary_target_eligibility: hostile`, and one minimum die per target. Fixed tier target capacity derives the dice budget and maximum targets. Both Calculator and native planner consume that projection. Schema validation rejects the superseded excess-attack fields and capacities smaller than the required minimum.

The Calculator offers every ordered legal allocation: one at Tier 0, four at Tier 1, and eleven at Tier 2. It shows each recipient's unconditional rider packet after an original hit, primary combined damage, and level-appropriate averages. Target order is primary first, followed by distinct hostile secondaries. The instruction reads its minimum from the projection instead of hardcoding three.

The native planner excludes the rider from clusters smaller than three. Within homogeneous clusters it enumerates the same legal distributions, consolidating equivalent secondary permutations. Each declared packet uses the existing original-strike resolution, with no secondary d20 or secondary Studied Attacks state. Primary rolls retain their normal Studied Attacks and Combat Prowess behavior. Representative policy labels show allocations, such as `branching_bolt@3+1+1:T2`.

## Validation and benchmark

The full native benchmark completed with **12 workers**, producing **564 damage-detail rows** and **96 matrix rows** across 47 creature profiles, four sampled levels, and clusters of 1/3/6. Elapsed time for the hostile-secondary revision: 20.4 minutes. All **47 single-target Electrokinesis policies exclude Branching Bolt**. All **423 other-discipline rows**, comparator results, shared core/progressions, and other feature projections match the prior integrated run. Control publication arrays are unchanged except for authority provenance.

The fresh 12-worker run after the review fixes reproduced **all 564 damage rows and policy selections exactly**, excluding authority provenance, against the completed `artifacts/branching-bolt-crowd-only/` run. All six damage/control publication arrays likewise match except for provenance. This is expected because the maintained benchmark already uses hostile recipients. The hostility restriction closes friendly-secondary routing without changing modeled damage; it does not add a damage boost. Both review findings are addressed; see the [review and disposition](branching-bolt-crowd-review.md).

### Single-target discipline comparison

These are equally weighted roster means of optimized discipline policies, not isolated rider damage. Previous Electro numbers belong to the superseded threshold rule.

| Fighter level | Previous Electro single-target DPR | Current Electro | Pyrokinesis |
|---|---:|---:|---:|
| 7 | 33.193 | 24.614 | 27.708 |
| 11 | 55.525 | 44.787 | 52.737 |
| 15 | 57.714 | 46.455 | 74.335 |
| 20 | 133.124 | 105.318 | 126.818 |

### Crowd aggregate damage

| Fighter level | Creatures | Previous Electro aggregate DPR | Current Electro aggregate DPR |
|---|---:|---:|---:|
| 7 | 3 | 37.278 | 40.793 |
| 7 | 6 | 38.325 | 41.840 |
| 11 | 3 | 65.901 | 68.940 |
| 11 | 6 | 90.935 | 91.154 |
| 15 | 3 | 83.034 | 84.671 |
| 15 | 6 | 134.850 | 135.217 |
| 20 | 3 | 146.704 | 154.768 |
| 20 | 6 | 208.796 | 208.766 |

Native authority SHA-256: `0995cdef0cfa6a4a10d07d5bdfa51649027f80acc2d0a80dd7b7ff39c902a761`. Evidence is retained in `artifacts/branching-bolt-hostile-review-fixes/`: frozen inputs/projection, resumable case checkpoints, damage/control output, full publication rows, run report, and verification report. The standard publication write and check passed; the generated tables were already numerically current. All eight final README contract tests passed. Retained rows are accepted only while all frozen mechanical inputs match.

**542 distinct local tests passed:** 83 TypeScript, 290 Python harness, 157 developer-tool, and 12 Chromium/Firefox browser tests. Applicable test processes used eight workers. Type checking, canonical/harness validation, deterministic generation, and whitespace checks passed. Targeted reruns verified the updated worked example, all Calculator permutations, provenance checks, and the changed level-20 damage regression.

Tests reject non-hostile secondary declarations and verify the Calculator instruction with a synthetic minimum of two. They independently enumerate legal named-target allocations, reject one- and two-target Branching Bolt declarations, check original misses/hits/criticals and Prowess conversions, and verify packet-level resistance/immunity/vulnerability rounding. Following adversarial review, the independent finite-horizon oracle now covers clusters of 3/4/5 targets across all eight combinations of Studied Attacks, Combat Prowess, and Discipline Maturation: 24 cases run with eight workers, extending the original eight cluster-three cases. Calculator and browser tests cover legal choices, die-size progression, grant/tier gates, and mobile/desktop rendering.

The previous completed run in `artifacts/branching-bolt-integration/` belongs to the superseded 2/3/4-die threshold design. Its 14.7–25.0% single-target gains and additional-roll review evidence do not describe this revision. The [threshold experiment](branching-bolt-threshold-benchmark.md) remains historical evidence only.

## Scope

The subsequent level-18 focused T1 fallback experiment and its 3-Psi follow-up were discarded by the maintainer. Neither changed the integrated rules: Branching Bolt remains a 2-Psi crowd rider with no focused single-target option. Static Discharge at T0 remains the resource-free single-target default. See the [discarded experiment](focused-bolt-t1-benchmark.md) for historical evidence.

This change makes Branching Bolt unavailable against a lone enemy. It still allows concentrated damage on one recipient when at least two hostile secondary creatures receive dice; it does not impose a primary-only allocation cap. Pyrokinesis now leads the single-target roster mean at all four sampled levels. That supports the intended separation; individual defense matchups can still favor Electrokinesis. Against the maintained Fighter comparison envelope, Electrokinesis is now COLD at levels 7, 15, and 20 and IDEAL at level 11. Crowd aggregate means rise at every sampled level/cluster combination except level 20 with six creatures, which falls slightly from 208.796 to 208.766. The removed extra-roll interactions and newly illegal two-target allocations mean this revision is not an across-the-board damage increase.

The maintained benchmark uses a fixed primary and homogeneous hostile clusters of 1/3/6 creatures. The primary has no new allegiance restriction; the planner does not model a friendly primary or mixed-allegiance groups. Hostile lightning-immune creatures remain eligible; immunity still prevents their damage. It does not quantify mixed AC/defenses, deliberate weak-primary targeting, overkill, deaths, or unmodeled multiclass/equipment triggers. Earlier Grok/Claude reviews concern superseded proposals and are not approval of this implementation.

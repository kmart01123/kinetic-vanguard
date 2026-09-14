# Branching Bolt: benchmark of grouped excess-damage rolls

> Historical proposal evidence. The current [integration](branching-bolt-integration.md) uses 3/4/5 dice, requires at least three targets, and has no additional attack rolls. Results and reviews below apply to the earlier design.

This records the completed experiment before canonical integration (see the subsequent [integration report](branching-bolt-integration.md)): 2/3/4 allocated rider dice from Fighter 7, with T2 available from Fighter 10; up to two dice per target land on the triggering strike's hit; one additional attack roll gates excess dice on either the primary or a secondary; an additional natural 20 adds one rider die. Primary miss negates the rider. Declared targets and allocations are locked, required extra rolls resolve before rider damage, and eligible Studied Attacks / Combat Prowess state and uses are shared.

## Single-target DPR

Equal-weight means over each level's full maintained headline roster. The previous automatic exchange is a historical alternative, not the merged rules.

| Fighter level | Merged rules | Earlier automatic exchange | Current proposal | Change from merged | EK–BM reference | Band |
|---|---:|---:|---:|---:|---|---|
| 7 | 26.560 | 33.628 | 33.193 | +24.97% | 26.464–48.493 | IDEAL |
| 11 | 45.792 | 56.492 | 55.525 | +21.26% | 43.442–81.101 | IDEAL |
| 15 | 47.661 | 58.077 | 57.714 | +21.09% | 52.247–92.807 | IDEAL |
| 20 | 116.064 | 134.416 | 133.124 | +14.70% | 128.502–164.824 | IDEAL |

`IDEAL` means inside this comparator interval; it is not proof of universal balance. Only levels 7, 11, 15, and 20 were benchmarked.

## Cluster aggregate DPR

| Fighter level | Creatures | Merged rules | Earlier automatic exchange | Current proposal |
|---|---:|---:|---:|---:|
| 7 | 3 | 37.258 | 37.294 | 37.278 |
| 7 | 6 | 38.306 | 38.341 | 38.325 |
| 11 | 3 | 65.901 | 65.901 | 65.901 |
| 11 | 6 | 90.935 | 90.935 | 90.935 |
| 15 | 3 | 82.969 | 82.991 | 83.034 |
| 15 | 6 | 134.807 | 134.807 | 134.850 |
| 20 | 3 | 146.318 | 146.608 | 146.704 |
| 20 | 6 | 208.723 | 208.723 | 208.796 |

These are optimized Electrokinesis policies, including other available riders and standalone abilities. Small aggregate changes do not imply that all Branching Bolt allocations perform equally. Primary and aggregate damage, selected schedules, and representative allocations are retained per profile in the results.

## What the accuracy rule changes

The proposal retains most of the earlier exchange's single-target improvement. Its single-target means are approximately 0.6–1.7% below the automatic exchange, while remaining 14.7–25.0% above merged rules. The extra accuracy requirement is a modest constraint on the resulting optimized damage output.

Studied Attacks matters even when lightning damage is prevented: against the lightning-immune level-20 Ancient Blue Dragon, primary DPR rises from 51.841 to 52.681. The optimizer can spend a concentrated rider to obtain an extra roll whose miss primes advantage for a later force-damage Holdout strike. This is a consequence of the approved shared Fighter interactions, not lightning bypassing immunity. Two independent oracle cases also cover immune rider damage.

## Method and validation

The run computed all 141 profile/cluster cases with **12 workers**, reoptimizing the action policy and Action Surge schedule over the maintained three-round horizon. Elapsed compute-run time: **32 minutes 7 seconds**. Baseline and comparator evidence were reused only after verifying all canonical, evaluator, configuration, roster and comparator input hashes against the merged benchmark.

The experimental planner retains native costs, Blood Tax payment choices, tier gates, the one-T2-per-Attack-action limit, Holdout, Maturation declarations, saves, defenses, and action economy. It enumerates every full-budget allocation permitted by each cluster, including 2+2 and secondary concentration. Extra-roll outcomes distinguish miss, normal hit, and natural 20; converted misses deliver ordinary excess damage without a bonus die. Dice that land against a target, including the natural 20 bonus, form one defended rider packet.

Pre-roll allocation choices use only observed state. Combat Prowess decisions occur only after the relevant miss. Studied Attacks for the primary is tracked separately from secondary targets; homogeneous secondary identities are represented by counts of effects expiring this turn or next turn, with explicit choices to reuse an existing advantage or select a fresh target. One creature's miss never grants another creature's advantage. Original primary advantage is not copied to the extra roll.

Verification passed: **168** packet/defense checks, **24** conditional-roll checks, **10** independent short-fight oracle comparisons using individually identified secondaries and absolute expiries, and **8** native baseline regressions. Verification used eight worker processes. Every proposal case preserved or increased aggregate damage versus merged rules.

A representative-trace expiry-label correction was also checked with a forced secondary-miss example. It changes only how the diagnostic path advances secondary expiry between rounds; the scored optimizer already handled that transition correctly. None of the 141 retained modal paths selected a gated secondary, so the retained paths and DPR values are unaffected. The exact executed source is preserved as `experiment-run.py`; the corrected source and audit are `experiment.py` and `trace-verification.json`.

## Limits and retained evidence

The maintained roster uses homogeneous clusters and a fixed primary target. It does not quantify choosing a low-AC primary to reach a high-AC secondary, differing target defenses/HP, target switching by later base strikes, overkill, or death. Damage-control feedback and ally effects remain outside the maintained model. Unmodeled multiclass or equipment on-hit/critical triggers are not implicitly included. No blanket ban on those effects is established by this experiment.

During this experiment, canonical rules, production evaluators, README publication, comparators, controls, and other disciplines were not changed or republished. Rules version remains 15.0.0. The experimental feature clones are alternatives for benchmarking, not a proposed production schema or implementation.

Authority SHA-256: `a7720742b9c857721d40175c8fdc17585b7f8184d89e6d6a893b46efd5239889`. Frozen proposal SHA-256: `5c0212103ed479277fca0d5edf814675df29d5fbd6a54fa1914204279048a9cb`.

Evidence: `artifacts/branching-bolt-threshold/` contains frozen `proposal.md`, `projection.json`, `inputs.json`, experimental source, `verify.py`, `verification-preflight.json`, `results.json`, `run.json`, `run.log`, and `verification.json`.

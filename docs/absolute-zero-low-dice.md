# Absolute Zero with fewer dice

> Historical integration snapshot: the 6d10 + 45/55/65 packet below was later increased by the [modest Cryokinesis correction](cryo-balance-evaluation.md). These historical candidate results are preserved unchanged.

**Adopted in an earlier unreleased v15.0.0 snapshot:** Absolute Zero used **6d10 + 45 / 55 / 65 cold damage** at tiers 0/1/2. Roll the same six dice at every tier, then add the tier's bonus. On a successful Constitution save, halve the combined dice-plus-bonus total, rounding down. All current costs, targeting, control effects, defenses, and Fighter-20 availability remain unchanged.

This replaces the earlier 14/16/18d10 proposal. The accompanying Telekinetic Shove and focused Branching Bolt changes are recorded in the [historical surgical damage candidates](surgical-damage-candidates.md). Branching Bolt's focused option was subsequently superseded by [crowd allocation](branching-bolt-integration.md). The six-die revision and both rider changes are integrated into canonical mechanics, the Calculator, and the native harness. See the [integration evaluation](surgical-damage-integration.md) for the full publication run.

| Tier | Earlier proposal | Adopted revision | Earlier average | Revised average |
|---|---|---|---:|---:|
| T0 | 14d10 | 6d10 + 45 | 77 | 78 |
| T1 | 16d10 | 6d10 + 55 | 88 | 88 |
| T2 | 18d10 | 6d10 + 65 | 99 | 98 |

The large flat component makes the damage roll less variable. Discipline Maturation's separate pre-roll gamble is unchanged; Absolute Zero remains a standalone action and does not trigger it.

## Level-20 comparison

Both lower-dice candidates were evaluated on all 12 maintained Fighter-20 profiles at cluster sizes 1 and 6, with reoptimized policies and Action Surge schedules and 12 workers. These are the original focused candidate results; the full native integration run is documented separately.

| Version | Single-target DPR | Gain over pre-integration rules | Six-target aggregate DPR |
|---|---:|---:|---:|
| Pre-integration 10/12/14d10 | 87.100 | — | 151.308 |
| Earlier 14/16/18d10 proposal | 95.429 | +8.328 | 151.308 |
| 8d10 + 30/40/50 | 92.961 | +5.861 | 151.308 |
| **6d10 + 45/55/65** | **94.934** | **+7.833** | **151.308** |

The six-die revision differs from the earlier large-pool proposal by -0.495 single-target DPR. Every six-target result is unchanged from the current baseline. Cold immunity remains effective; this revision adds no alternative damage type.

## Evidence and scope

The isolated experiment adds a local exact distribution for a dice-plus-fixed damage packet and delegates save halving, Resistance, Immunity, Tier-2 resistance treatment, action selection, and resource accounting to the maintained native evaluator. Distribution checks covered expected means, whole-packet save halving, Resistance, Immunity, and Tier-2 resistance handling.

The isolated experiment preserved its baseline authority, evaluator, roster, comparator, and configuration hashes. Production integration now uses the canonical `dice_plus_fixed` primitive shared by the Calculator and harness; the historical evidence below remains tied to its original baseline.

Evidence is retained in `artifacts/absolute-zero-low-dice/`: `experiment.py`, `variants.json`, the frozen projection, `results.json`, `verification.json`, and `run.log`. Run the experiment with `python3 artifacts/absolute-zero-low-dice/experiment.py` and the comparison with `python3 artifacts/absolute-zero-low-dice/summarize.py`.

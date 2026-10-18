# Branching Bolt: early focus and branch exchange

> Historical proposal evidence. The current [integration](branching-bolt-integration.md) uses 3/4/5 dice, requires at least three targets, and has no additional attack rolls. Results and reviews below apply to the earlier design.

This is the follow-up design after PR #144, which has already merged. The maintainer chose branch exchange from Fighter 7 onward, allowed full concentration, and standardized the accuracy threshold across all targets, including the primary: up to two assigned rider dice land on the triggering strike's hit; dice beyond two require one additional attack roll against that target. Required additional rolls resolve together before rider damage, and a natural 20 on an additional roll adds one Manifested Strike damage die to that target's rider packet. The maintainer subsequently authorized integration; the [integration report](branching-bolt-integration.md) tracks the canonical implementation.

**Benchmark status:** the current proposal has now been [evaluated across all 141 headline profile/cluster cases with 12 workers](branching-bolt-threshold-benchmark.md), including excess-damage rolls, shared Fighter interactions, and the natural-20 bonus. The tables below remain historical evidence for the earlier automatic-damage version; use the linked report for current results.

## Design decision

- **Earlier Focused Bolt (comparison only):** move the existing Fighter-18 option to Branching Bolt’s Fighter-7 grant. It remains two Manifested Strike damage dice at every tier.
- **Branch exchange (selected design):** at Fighter 7, each additional target you forgo contributes one Manifested Strike damage die to a remaining target of your choice. Dice may be concentrated freely. The struck target remains included. Declare targets and the complete allocation before the primary attack roll; all dice that land on a creature form its rider damage packet. This replaces the separate Fighter-18 Focused Bolt unlock.

Each remaining target starts with one die. Retain **1/2/3 additional targets**, giving **2/3/4 total targets** at T0/T1/T2; the proposed 0/2/4 additional-target progression was dropped. The tier supplies a fixed allocation budget, before any natural-20 bonus:

| Tier | Rider dice to allocate | Maximum allocation on one target | Earliest availability |
|---|---:|---:|---|
| T0 | 2 | 2 | Fighter 7: 2d8 |
| T1 | 3 | 3 | Fighter 7: 3d8 |
| T2 | 4 | 4 | Fighter 10: 4d8 |

The T2 pool grows to 4d10 at Fighter 11 and 4d12 at Fighter 17. At T2, example allocations are **4**, **3+1**, **2+2**, **2+1+1**, or **1+1+1+1**. The first number belongs to the struck target; additional targets retain the existing 15-foot range from it. The exchange remains available at every level after grant, subject to the normal tier gates. Costs, Blood Tax, the one-T2-rider-per-Attack-action limit, native lightning damage, and defenses remain as in the merged rules. Rider dice still do not double on a critical hit; the additional roll's natural-20 bonus is a new, separate one-die benefit.

## Revised attack resolution

1. Declare the full attack package before rolling the triggering Manifested Strike: name the primary target, every additional target, the rider tier, and the exact number of rider dice assigned to each. Each chosen creature receives at least one die, and each additional creature may be chosen only once. This declaration determines which targets, if any, require additional rolls; allocations of one or two dice require none. Lock all choices and pay the declaration costs.
2. Resolve the triggering Manifested Strike against the primary target's AC. If it misses after any applicable hit-conversion effects, the rider deals no damage and no branches launch. Its declaration costs remain spent.
3. If the triggering attack hits, the primary takes its normal Manifested Strike damage. For **each chosen target, including the primary**, up to the first two assigned Branching Bolt damage dice land without another attack roll or saving throw.
4. For each target assigned **three or more Branching Bolt damage dice**, make one additional ranged attack roll using your Manifested Strike attack bonus against that target's AC. Handle **all required additional rolls together as one group**, immediately within this attack package and before any rider damage rolls. Do not insert another normal attack or action between the triggering strike and these rolls. Apply advantage or disadvantage separately as applicable to each target, and resolve eligible hit-conversion effects and shared uses as part of this group.
5. Each additional roll determines whether that target's dice **beyond the first two** land. On a hit, all assigned rider dice land; on a miss, only the first two land. A natural 1 misses, subject to an applicable hit-conversion effect. A **natural 20 hits and adds one bonus Manifested Strike damage die to that target's rider damage**. Roll once for all excess dice assigned to that target, not once per excess die. The bonus die needs no additional attack roll and cannot trigger another bonus die or create another target. A converted miss is not a natural 20 and grants no bonus die.
6. Once the entire additional-roll group is resolved, roll all rider dice that land on each target, including any natural-20 bonus, together as one lightning damage packet per target. Apply each creature's defenses to its own packet. The primary's base Manifested Strike damage remains separate. No saving throw is added.
7. Excess dice lost on a miss cannot be redirected. You cannot change targets or revise allocations after rolling. An additional-roll miss does not undo the triggering strike's hit, its base damage, or the first two rider dice. No branch continues from its secondary target. Finish resolving the whole package before moving to another normal attack.

The threshold counts the total Branching Bolt rider dice assigned to each individual target at declaration, including its initial one die and any dice gained from forfeited branches. It does not count the tier's total budget, die size, the base Manifested Strike damage dice, Discipline Maturation dice, or the later natural-20 bonus. A creature cannot be chosen twice to split a larger assignment into smaller automatic packets.

Any required additional attack resolves the existing rider; it does not deal another Manifested Strike's base damage, consume another attack from the Attack action, or provide a new Manifested Strike on which to declare a rider or Discipline Maturation. Its damage remains rider damage and does not double on a critical hit. Ordinary attack-roll features must be evaluated according to their own eligibility and remaining uses; the new roll does not create extra uses of those features. Automatic rider damage creates no additional attack-roll triggers.

**Fighter interactions:** an additional-roll miss that remains a miss triggers Studied Attacks against that target. Apply and consume any eligible existing same-target Studied Attacks advantage on the additional roll; advantage used by the triggering strike is not copied to it. Combat Prowess can convert an additional-roll miss into a hit, consuming its normal shared once-per-turn use. A converted miss does not trigger Studied Attacks. Track both features across the triggering strike, additional roll, and later attacks; resolving this group grants no refresh or extra use.

**Natural-20 scope:** the bonus applies to a natural 20 on a required additional roll. A natural 20 on the triggering Manifested Strike keeps its normal critical treatment and does not itself award this extra rider die. The one-die bonus uses the current Manifested Strike die size and the rider's lightning damage type and defenses. It may exceed the original allocation budget but never changes the declared allocation or target count. There is no optional additional roll for a target assigned two or fewer dice merely to seek this bonus.

T0's two-die budget never requires an additional roll. At T1, concentrating all three dice on the primary requires an additional roll for the third die. At T2, concentrating three or four dice on any one target requires an additional roll for its excess dice. Under these budgets at most one target can receive more than two allocated dice, so the additional-roll group currently contains zero or one roll. The first number below is always the primary's rider allocation; all outcomes assume the triggering strike hit, with a natural 20 adding one further die to the target of an additional roll:

| T2 allocation | Rider resolution after a primary hit |
|---|---|
| 4 | Two dice land on the primary; one additional attack roll against it determines whether the other two land |
| 3+1 | Two dice land on the primary and one on the secondary; one additional roll against the primary determines whether its third die lands |
| 2+2 | Two dice land on each target; no additional roll |
| 1+3 | One die lands on the primary and two on the secondary; one additional roll against the secondary determines whether its third die lands |
| 2+1+1 | All assigned dice land; no additional roll |
| 1+2+1 | All assigned dice land; no additional roll |
| 1+1+1+1 | All assigned dice land; no additional roll |

For example, concentrate all four T2 rider dice on the primary. If the triggering strike hits but the additional attack remains a miss, the primary takes its normal strike damage plus two rider dice. If the additional attack hits without a natural 20, it takes its normal strike damage plus four rider dice. A natural 20 on that additional roll gives five rider dice. With **1+3**, the secondary receives two rider dice on an additional miss, three on an ordinary additional hit, or four on an additional natural 20. With **2+2**, both targets receive their full assigned rider damage without a second roll or a chance for the natural-20 bonus.

The maintainer intends to reward using an easier primary target to reach a high-AC secondary with up to two rider dice. Damage beyond two rider dice must overcome the receiving target's AC, whether that target is primary or secondary. Full concentration remains legal, but its excess damage now has an accuracy requirement.

## Historical full-roster single-target results

| Fighter level | Current rules | Focused Bolt at 7 | Branch exchange at 7 | EK–BM comparator interval |
|---|---:|---:|---:|---|
| 7 | 26.560 | 30.094 (IDEAL) | 33.628 (IDEAL) | 26.464–48.493 |
| 11 | 45.792 | 49.252 (IDEAL) | 56.492 (IDEAL) | 43.442–81.101 |
| 15 | 47.661 | 51.386 (COLD) | 58.077 (IDEAL) | 52.247–92.807 |
| 20 | 116.064 | 116.064 (COLD) | 134.416 (IDEAL) | 128.502–164.824 |

DPR means are equally weighted across each level’s maintained roster. `IDEAL` means inside the comparator interval, not proof of universal balance. Moving flat focus earlier cannot change level-20 results because the current rules already grant it at Fighter 18.

## Historical cluster results — automatic secondary hits

| Fighter level | Cluster | Current aggregate DPR | Focused Bolt at 7 | Branch exchange at 7 |
|---|---|---:|---:|---:|
| 7 | 3 | 37.258 | 37.258 | 37.294 |
| 7 | 6 | 38.306 | 38.323 | 38.341 |
| 11 | 3 | 65.901 | 65.901 | 65.901 |
| 11 | 6 | 90.935 | 90.935 | 90.935 |
| 15 | 3 | 82.969 | 82.984 | 82.991 |
| 15 | 6 | 134.807 | 134.807 | 134.807 |
| 20 | 3 | 146.318 | 146.318 | 146.608 |
| 20 | 6 | 208.723 | 208.723 | 208.723 |

The exchange adds flexibility and concentrated damage with a fixed tier allocation budget, plus a possible one-die reward from an additional natural 20. It makes higher-tier Overloads useful for focused damage and increases single-target burst at the original grant. Its extra choice is allocation: the table must specify it before rolling, rather than redistribute after seeing a hit or damage result. The threshold preserves the first two rider dice per target while adding an accuracy cost to excess damage, including concentrated primary damage. Neither the historical single-target nor cluster results establish this rule's performance, attack-roll feature interactions, or natural-20 reward.

## Method and limits

The experiment used 12 workers and the native exact planner on all 47 headline profiles at levels 7/11/15/20 and cluster sizes 1/3/6. It computed 246 cases and reused 36 mechanically identical level-20 early-focus cases from the merged benchmark. Every computed case reoptimized the action policy and Action Surge schedule. That experiment left other disciplines, comparator inputs, control, and all canonical/evaluator files unchanged.

The historical experimental exchange modes used temporary in-memory feature clones with the original tier costs and defenses. They were alternative rider choices, so no clone could stack with another on the same strike. For each number of remaining targets, the experiment put all bonus dice on the primary target. Under the old automatic-hit rule, homogeneous benchmark clusters allowed this to represent the maximum aggregate outcome and maximize primary damage among equivalent allocations. Allocations such as 2+2 remain legal in the revised proposal. The new threshold changes this equivalence: spreading 2+2 avoids the additional roll required by 3+1 or 4. Evaluation must represent the retained first two dice, attack-gated excess dice, and attack-roll feature interactions for either primary or secondary targets. Target death and overkill were not modeled.

This report preserves the design evaluation. The subsequent [integration report](branching-bolt-integration.md) records implementation and its verification. The original integration checklist required extending the current single-target-only option schema and projections to express allocation, grouped excess-damage attack resolution for all targets, and the additional-roll natural-20 bonus, with consumer and pre-roll allocation tests. The damage model needed to resolve the triggering primary-hit gate, retain up to two rider dice per target, and resolve any additional attack for excess dice, preserving target-specific Studied Attacks state and shared Combat Prowess usage. The checklist covered the two/three-die boundary on both primary and secondary, four-die primary concentration, a triggering miss negating everything, an additional miss losing only excess dice, one bonus die on an additional natural 20 without recursion or doubling, no bonus on a converted miss or the triggering strike's critical, no optional rolls below the threshold, grouped resolution before rider damage, single-packet defenses, different target ACs, one selection per creature, and allocation lock-in before rerunning the benchmark with at least eight workers.

Evidence: `artifacts/branching-bolt-exchange/experiment.py`, frozen `projection.json` and `inputs.json`, `results.json`, `verification.json`, `run.json`, and `run.log`. Baseline: `artifacts/surgical-integration/`.

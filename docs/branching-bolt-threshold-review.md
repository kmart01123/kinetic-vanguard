# Branching Bolt universal excess-damage rule: external design review

> Historical proposal evidence. The current [integration](branching-bolt-integration.md) uses 3/4/5 dice, requires at least three targets, and has no additional attack rolls. Results and reviews below apply to the earlier design.

Date: 2026-09-10. Both providers completed independent reviews of the same frozen proposal. The rule keeps up to two rider dice per target on a triggering primary hit, with one additional attack roll gating only excess dice, including on the primary. The reviewed tier budgets are **2/3/4 dice**, with **1/2/3 additional targets**. The later question about 0/2/4 additional targets (1/3/5 total targets and dice) was not part of either review.

Both recommendations are **REVISE**, with medium confidence. Both support the core mechanism and request explicit attack-feature treatment and new evaluation. These are design reviews, not code-review approvals. No rules, target counts, PRs, or merges were changed by this consultation.

**Subsequent maintainer decisions:** retain 1/2/3 additional targets; lock the full package, named targets, and dice at declaration; finish the package immediately; retain the stated Studied Attacks and shared Combat Prowess interactions; resolve all required additional rolls as one group before rider damage; and award one extra Manifested Strike damage die to the receiving target on an additional-roll natural 20. The [current proposal](branching-bolt-exchange-evaluation.md#revised-attack-resolution) records these revisions. The providers did not review the new natural-20 reward. Their suggested blanket exclusions of other on-hit or on-critical effects were not explicitly adopted.

**Benchmark follow-through:** the revised proposal, including the natural-20 reward, has now completed a [141-case experimental benchmark](branching-bolt-threshold-benchmark.md). All four sampled single-target means fall inside the EK–BM reference interval. The report also identifies the damage benefit from extra misses priming Studied Attacks, including when the rider's lightning damage is prevented. This supplies new evaluation evidence; it does not convert these historical design reviews into approval of canonical implementation.

## Assessment of the feedback

- Clarify how the extra roll shares Studied Attacks target state and the once-per-turn Combat Prowess use. The current proposal already says ordinary eligible attack-roll features apply; explicit examples would make this easier to run.
- Resolve the rider as part of the triggering strike before proceeding to another normal attack. Claude's sequencing suggestion should not be read as permission to suspend this rider and insert attacks to build advantage. Any such permission would need a separate rule.
- Decide and state the treatment of other on-hit/on-critical effects. The reviewers' suggested exclusions are optional new restrictions, not existing maintainer decisions.
- Resolve the additional roll before the affected rider packet and clarify the order across targets. Preserve one rider damage packet per receiving creature.
- Rerun the damage model for the actual proposal. The old automatic-damage benchmark is not validation. Both reviewers suggest the old results overstate damage or form an upper bound; that is not established for the full system because the new attack can also change Studied Attacks state and other eligible triggers. A pure extra accuracy gate reduces excess damage with all other effects held fixed, but the complete policy must be evaluated.

## Completed provider reviews

### Claude

Recommendation: **REVISE**. Confidence: medium. Provider-reported model: `claude-sonnet-5`. CLI: `2.1.260 (Claude Code)`.

The universal two-die-free/excess-roll rule is internally consistent and clearly achieves the maintainer's stated intent: up to two rider dice reach any target (including a hard-to-hit secondary) for free off the primary's hit, while concentrating a third+ die anywhere, including the primary, now costs a real attack roll. The gate is meaningful (2+2 skips the roll entirely; 3+1/4/1+3 do not) and action-economy-light (at most one extra roll per use). However, the design is not yet safe to canonize: the attached benchmark numbers still assume the old automatic-hit rule and therefore overstate concentrated allocations, and several attack-roll feature interactions (crit-adjacent triggers, Studied Attacks priming, Combat Prowess reservation) are left implicit rather than ruled.

Strengths:

- Uniform primary/secondary threshold removes the old asymmetry and directly rewards routing 1-2 dice through an easy primary into a hard secondary, exactly as intended.
- Resolution order (allocate pre-roll -> primary hit gate -> per-target 2-die floor -> single excess roll -> one damage packet) is unambiguous and table-fast, since budget math guarantees at most one target can ever need the extra roll.
- Miss handling is coherent and clearly stated at every layer: primary miss zeroes everything, excess-roll miss only strips the dice beyond two, non-reproducible by Maturation or extra Attack-action uses.

**HIGH: Historical benchmark does not reflect the new gate for concentrated allocations**

The DPR tables (e.g., 33.628-134.416 for Branch exchange) were computed under automatic secondary hits. Under the new rule, 4- and 3+1-style concentration now fails its excess roll roughly (1-hit chance) of the time, so those DPR figures are inflated versus 2+2/1+1+1+1 spreads that need no roll. The document itself acknowledges this, but no corrected numbers exist yet.

Suggested action: Rerun the planner modeling the excess-roll gate before treating any DPR comparator interval as satisfied for concentrated allocations.

**MEDIUM: Nat-20 on the excess roll is not ruled for non-damage crit triggers**

Rider dice explicitly never double on a crit, but the text is silent on whether a natural 20 on the excess roll otherwise counts as a 'critical hit' for unrelated triggered features (e.g., anything that fires 'on landing a critical hit').

Suggested action: Add an explicit ruling: the excess roll's natural 20 only satisfies the rider's hit gate and does not constitute a critical hit for any other feature.

**MEDIUM: Studied Attacks/Combat Prowess interactions with the excess roll are underspecified**

Ordinary attack-roll features apply to the excess roll with shared state, but the doc never confirms whether an excess-roll miss 'primes' Studied Attacks against that target, nor addresses that a player can deliberately bank the once-per-turn Combat Prowess conversion specifically for the excess roll, which could make full concentration near-deterministic at level 20 and undercut the intended accuracy cost right when T2 dice are largest (4d12).

Suggested action: Rule explicitly that an excess-roll miss primes Studied Attacks like any resolved miss, and validate via benchmark whether Combat-Prowess-reserved concentration meaningfully erodes the gate at level 20; this may be acceptable as a resource trade-off but should be confirmed, not assumed.

**LOW: Turn-order interaction with the excess roll is implied, not stated**

When a player has multiple attacks (Extra Attack, Action Surge) in the same turn, whether they can sequence other attacks to first generate Studied Attacks advantage before taking the excess roll is left to normal turn order without an explicit note.

Suggested action: State that the player controls action/attack sequencing as normal; no rule change needed, just an explicit callout to avoid table disputes.

Proposed wording (provider recommendation; not adopted):

Keep the rule as written in the proposal (declare targets/allocation before the primary roll; primary hit required or all rider damage fails; each chosen target keeps its first two assigned rider dice automatically; a target with 3+ assigned dice requires one extra Manifested-Strike-bonus attack roll, resolved before damage, gating only the excess dice; one packet per target; excess roll never grants a new Manifested Strike, rider, or Maturation). [Suggested, not currently in the text] Add: 'A natural 20 on this extra roll resolves only this rider's hit gate and does not constitute a critical hit for any other feature; a miss on it is a resolved miss for effects like Studied Attacks.'

Requested validation:

- Rerun the DPR planner modeling the excess-roll gate (not automatic hits) for 4/3+1/1+3 vs 2+2/2+1+1/1+1+1+1 at each tier and level.
- Confirm whether an excess-roll natural 20 should trigger unrelated on-crit features.
- Confirm whether an excess-roll miss primes Studied Attacks advantage against that target.
- Model level-20 outcomes where Combat Prowess is deliberately reserved for the excess roll to see how often it neutralizes the accuracy cost of full concentration.
- Verify Studied Attacks/Combat Prowess use-tracking is correctly shared across the primary strike, the excess roll, and any Action-Surge-driven second Branching Bolt use.

### Grok

Recommendation: **REVISE**. Confidence: medium. Provider-reported model: `grok-4.6-build`. CLI: `grok 1.0.13 (5e9a58528b76)`.

The 2-die retain plus extra-roll-for-excess gate matches the stated intent: an easier primary hit can deliver up to two rider dice to a harder secondary with no second check, while 3–4 dice on any one creature pay that creature’s AC only for the excess. This is not an AC-bypass ban. Canonical text still needs an explicit extra-roll feature ruling; historical auto-hit tables are not this rule.

Strengths:

- After a triggering hit, 2+2 and 1+2+1 land in full with no extra roll; 1+3 still guarantees primary 1 plus secondary 2, so routing two dice through an easier primary is the reliable tactic.
- Concentration 3 or 4 stays legal; one extra roll against the receiving target gates only dice beyond two, and an extra miss keeps two dice rather than wiping the packet.
- The same per-target threshold applies to the primary and secondaries, ignores base strike and Maturation, and with a 4-die budget and min 1 per target yields at most one extra roll.
- Lock-in before the primary roll, extra roll before that target’s rider dice, one lightning packet, extra rolls not consuming Attack-action strikes, and Maturation not copied are specified.

**MEDIUM: Extra roll needs an attack-roll vs on-hit ruling**

The extra roll is a ranged attack roll but not a Manifested Strike. Studied Attacks (extra miss primes same-target advantage; a bonus roll consumes existing same-target advantage) and Combat Prowess (shared once-per-turn conversion; converted miss does not prime Studied Attacks) follow from the contract and are not exploits. Unspecified on-hit damage or ‘when you hit/miss with an attack’ riders could inflate concentrated packets or add extra triggers. A blanket Fighter-feature ban is not in the proposal; adding one is a new design choice.

Suggested action: State that the extra roll is an attack roll for accuracy, cover, advantage/disadvantage, natural 1/20, Studied Attacks, and Combat Prowess, sharing uses and target state with normal attacks. Optionally, and labeled as a new restriction, say it deals no separate strike damage and grants no extra on-hit damage or feature uses.

**MEDIUM: Historical IDEAL figures are not this rule**

Deduction, not a new sim: single-target IDEAL (7: 33.628, 11: 56.492, 15: 58.077, 20: 134.416) assumed every assigned die landed after the primary hit, including full concentration. Under this gate, T1 3 and T2 3–4 require a second hit for excess, so those means are upper bounds. Homogeneous cluster tables also used automatic secondaries and often other riders; they do not measure mixed AC, 2+2 vs 4, overkill, or death.

Suggested action: Do not treat the attached roster or cluster numbers as validation. Re-run with retained-two plus gated excess on both primary and secondary before citing balance.

**LOW: Cross-target packet order is implicit**

The extra roll is before that target’s rider packet, and at most one target can have 3+ dice, but order versus the other target’s automatic packet is unstated. Harmless if packets stay per-creature.

Suggested action: Resolve any extra roll, then each selected target’s rider as one packet; primary base damage stays separate.

Proposed wording (provider recommendation; not adopted):

Declare primary, distinct secondaries within 15 feet, and the full Branching Bolt allocation before the triggering Manifested Strike; min 1 die per selected creature, no creature twice. Costs are paid on declaration. If that strike misses after hit-conversion, no rider damage. If it hits, the primary takes normal Manifested Strike damage separately. For each selected target including the primary, up to two assigned Branching Bolt dice land with no further attack or save. A target assigned 3+ rider dice requires one extra ranged attack roll using the Manifested Strike bonus against that target, made before its rider damage, gating only dice beyond two: hit lands all assigned rider dice; miss keeps two and drops the rest with no redirect. Natural 1 misses; natural 20 hits. Rider dice do not double on a critical; Maturation is not reproduced. Landed rider dice against a creature are one lightning packet. Extra rolls are not Manifested Strikes, do not consume Attack-action attacks, and cannot declare riders or Maturation. They are attack rolls: apply advantage/disadvantage separately; share Studied Attacks state and Combat Prowess uses with other attacks. [Introduced restriction, optional:] the extra roll deals no extra on-hit damage and creates no extra feature uses.

Requested validation:

- Primary miss: zero rider damage despite locked 2+2, 1+3, or 4.
- After a hit: 2+2 and 1+2+1 no extra roll; 4 and 3+1 extra vs primary (miss keeps 2); 1+3 extra vs secondary (miss keeps primary 1 + secondary 2).
- T0 never extra-rolls; T1 only on 3; T2 at most one extra roll.
- One packet vs resistance; mixed AC routing; lock-in; no double-select; lost excess not moved.
- Studied Attacks prime from an extra miss and are consumed if already up on that extra roll; Combat Prowess converts an extra miss once per turn and then does not prime Studied Attacks.
- Crit: only base strike dice double; extra-roll 20 hits excess without doubling rider or copying Maturation.
- Re-benchmark this gate, not auto-all, including mixed AC and 2+2 vs 4.

## Evidence

Common prompt SHA-256: `2e9556d7b593b9aa2ef7cd8d25a52937f6dad6d1c9aa3da4c291b70fb37b7a7e`.

Frozen proposal, common prompt, invocation script, and validated provider responses are retained in `artifacts/branching-bolt-threshold-review/`. The providers received the same context without each other's recommendations or their prior votes. Completion metadata was validated; raw provider logs were not retained.

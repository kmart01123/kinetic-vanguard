# Branching Bolt secondary attack rolls: design vote

> Historical proposal evidence. The current [integration](branching-bolt-integration.md) uses 3/4/5 dice, requires at least three targets, and has no additional attack rolls. Results and reviews below apply to the earlier design.

On 2026-09-10, the maintainer requested a three-way vote and abstained. The result was **2–1 to revert the additional attack rolls**. This is a majority recommendation, not unanimous consensus or an implemented rule change. The primary-hit prerequisite was held fixed: a triggering Manifested Strike miss, after applicable hit conversion, still negates all rider damage and branches, with costs spent.

**Subsequent maintainer decision:** reward routing damage through an easier primary, while applying one rule to every target, including the primary: after the triggering strike hits, up to two assigned rider dice land automatically; dice beyond two require one additional attack roll against the receiving target. An additional-roll miss loses only the excess dice. See the [current proposal](branching-bolt-exchange-evaluation.md#revised-attack-resolution). The votes below concerned the earlier all-or-none choice and do not constitute external review of this compromise.

| Voter | Vote | Main reason |
|---|---|---|
| Codex | Revert secondary rolls | A second accuracy gate penalizes spreading the fixed dice budget while leaving full concentration unchanged. |
| Grok | Revert secondary rolls | The primary-hit gate and prepaid costs already constrain the rider; extra rolls discourage branching and add Fighter-feature interactions. |
| Claude | Keep secondary rolls | Each secondary's own AC should protect it from damage routed through an easier primary. |

All three expressed medium confidence. Codex declared its vote before either external result arrived. Claude and Grok received the same self-contained prompt, independently, without the maintainer's preference or the other voters' opinions. Both returned completed votes through their authenticated provider CLIs. Provider-reported model metadata was `claude-sonnet-5` and `grok-4.6-build`. No GitHub comments were posted and no merge occurred.

## Majority recommendation

Keep targets and dice allocation declared before the primary attack roll. If that attack hits, each declared target takes its assigned lightning rider damage, applying its own defenses, without another attack roll or saving throw. If it misses, the entire rider fails. Retain the fixed 2/3/4-die tier budgets, full concentration, and 15-foot secondary range.

As an arithmetic illustration, with independent 65% hit chances and no hit conversion or advantage, a given secondary receives damage 65% of the time without a second roll, versus 42.25% with one. At T2, concentrating all four dice on the primary yields 2.6 expected rider-die units; spreading one die to each of four targets with secondary rolls yields 1.9175. This isolates the accuracy cost; it is not a benchmark and excludes target defenses and Fighter-feature feedback.

## Dissent and limits

Claude's strongest point is shared by both other voters: a low-AC primary can route up to three T2 rider dice into a high-AC secondary. Free allocation strengthens that existing automatic-arc behavior, and the homogeneous benchmark did not measure it. T2 resistance bypass also matters. The majority regards heterogeneous encounters and playtesting as the next useful evidence if this tactic proves dominant.

Claude also proposed excluding secondary rolls from Studied Attacks and Combat Prowess. That exclusion would be a further rule change, not an agreed property of the current draft. Claude acknowledged that the secondary-roll version has no benchmark evidence and could make branching unattractive. Grok likewise identified these attack-roll interactions as a complication. The majority recommendation does not add that exclusion or any other compromise rule.

The historical automatic-hit exchange benchmark informs this discussion but does not establish universal balance. Optimized cluster policies may choose other riders and mask Branching Bolt's individual behavior. The version with secondary rolls has not been benchmarked.

Evidence retained locally in `artifacts/branching-bolt-vote/`: common `prompt.md`, invocation script `run.py`, completed `claude.json` and `grok.json`, and `codex.json`. Both external results record common prompt SHA-256 `b9495dbecb4b14b8601692abe28811b6de1019953957c0a94d276331f74197d9`. These are design opinions, not code-review approvals.

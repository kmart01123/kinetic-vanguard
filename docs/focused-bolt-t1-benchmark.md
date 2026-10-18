# Focused Bolt: level-18 T1 fallback experiment

**Disposition: discarded by the maintainer.** Retained as historical benchmark evidence only. The single-target option and its 3-Psi follow-up will not be integrated: Electro retains its crowd-focused identity and Branching Bolt stays at 2 Psi. The follow-up run finished, but its result was not adopted or needed to revisit that decision.

This is an isolated candidate benchmark, not an integrated rule. The proposed unlock remains Fighter 18. At the maintainer's direction, damage was evaluated at the maintained **Fighter-20** benchmark point rather than constructing a supplemental Fighter-18 roster. Grant availability was checked at levels 17/18/20; this report does not measure level-18 DPR.

## Candidate

When declaring Branching Bolt at Tier 1 from Fighter 18, optionally forgo all secondary targets and deal three Manifested Strike rider dice as one lightning packet to the primary on an original-strike hit. Pay the normal 2 Psi and T1 Blood Tax for each declaration. The rider uses the normal one-rider-per-strike slot and can be declared on successive strikes, including within the same Attack action. It has no T2 usage limit, no additional roll, no rider critical doubling, and no resistance or immunity bypass. There is no focused T0 or T2 option. Existing crowd allocation remains available, and the focused option may be chosen even when a crowd is present.

Normal Overload Mastery, Psi capacity, the maintained 25%-HP Blood Tax budget, three-round horizon, pre-roll Discipline Maturation, original-roll Studied Attacks/Combat Prowess, and native Action Surge optimization remain in force.

## Results

Equal-weight means across all 12 maintained level-20 creature profiles:

| Targets | Current Electro total DPR | Candidate Electro total DPR | Change | Pyro total DPR |
|---|---:|---:|---:|---:|
| 1 | 105.318 | 127.701 | +21.25% | 126.818 |
| 3 | 154.768 | 154.768 | +0.00% | 126.818 |
| 6 | 208.766 | 208.766 | +0.00% | 126.818 |

The candidate raises single-target mean damage by **22.383 DPR (+21.25%)**, to **127.701**, versus Pyro's **126.818**: **0.883 DPR / 0.70% above Pyro**. Both primary and aggregate damage in every three- and six-target case match the baseline within numerical tolerance. The focused mode appears in 10 of 12 single-target representative policies and none of the crowd policies. Lightning-immune Ancient Blue Dragon and Kraken gain nothing.

Electro remains ahead of Pyro in the same four individual single-target profiles as before: Ancient Brass Dragon, Ancient Gold Dragon, Balor, and Pit Fiend. Pyro remains ahead in the other eight. The roster-average reversal reflects changes in the size of those advantages and deficits, not a reversal of any individual matchup winner. For example, Ancient Copper Dragon rises from 124.079 to 153.789 Electro DPR while Pyro remains 160.912. These defense-dependent results do not establish universal superiority.

## Multiple-strike behavior

The native optimizer actually selects up to **four focused T1 declarations in one Attack action**. Most eligible single-target representative paths select eight focused uses over the three-round encounter; Lich selects five. Those are locally modal representative paths, not expected use counts across all stochastic outcomes. A Balor policy combines three focused T1 declarations with one Static Discharge T2 in the same Attack action, demonstrating that focused declarations do not consume the T2 allowance.

## Per-profile single-target results

| Target | Current Electro | Candidate Electro | Pyro | Maximum focused uses in one action, representative path |
|---|---:|---:|---:|---:|
| Ancient Blue Dragon | 51.841 | 51.841 | 158.970 | 0 |
| Ancient Brass Dragon | 126.933 | 156.604 | 57.602 | 4 |
| Ancient Copper Dragon | 124.079 | 153.789 | 160.912 | 4 |
| Ancient Gold Dragon | 118.799 | 150.637 | 57.098 | 4 |
| Ancient Green Dragon | 124.079 | 153.789 | 160.912 | 4 |
| Ancient Silver Dragon | 119.516 | 150.637 | 158.970 | 4 |
| Ancient White Dragon | 128.398 | 156.604 | 162.810 | 4 |
| Balor | 86.125 | 96.865 | 57.642 | 3 |
| Kraken | 57.454 | 57.454 | 165.615 | 0 |
| Lich | 89.119 | 96.610 | 162.810 | 3 |
| Pit Fiend | 119.766 | 153.789 | 57.563 | 4 |
| Solar | 117.700 | 153.789 | 160.912 | 4 |

## Validation and scope

**Seven focused tests pass:** unchanged baseline projection plus one candidate option; unlock/tier/cost checks at 17/18/20 and clusters 1/2/3/6; one-packet resistance/immunity/vulnerability; three T1 uses within one action; independent Psi/Blood limits; T1 sharing an action with a T2 while retaining the T2 limit; and original miss/hit/critical handling.

The native experiment completed **36 candidate cases with 12 workers in 391.78 seconds**. Each case uses the unchanged native damage planner and reoptimizes the legal policy and Action Surge schedule. Baseline Electro/Pyro rows come from the completed `artifacts/branching-bolt-hostile-review-fixes/` native run; its source/config hashes were verified unchanged before reuse, and its detail CSV was copied and hashed in this experiment's manifest. All candidate cases retain or improve their optimized aggregate objective. Frozen source and projection hashes were checked after evaluation.

The experimental projection appends a separate rider package solely to represent the mutually exclusive focused mode. The normal shared rider slot prevents stacking it with another rider on the same strike. This does not establish production schema, Calculator, or prose integration for a mode alongside allocation. No canonical rules, production harness, schema, official README benchmark tables, or Pyrokinesis mechanics were changed.

Baseline authority SHA-256: `0995cdef0cfa6a4a10d07d5bdfa51649027f80acc2d0a80dd7b7ff39c902a761`. Experiment identity: `a984f895d06c96ce1b331fb8e3dae270508efb393f4c338271fe4d26274039f4`. Artifacts: `artifacts/focused-bolt-t1-level18/` contains the runner, seven tests, frozen baseline/candidate projections, configuration, manifest, per-case checkpoints, native policy selections, aggregate summary, and run log.

## Assessment

This is a substantive single-target upgrade while preserving the existing crowd performance. It also largely removes the roster-mean single-target separation from Pyro that the crowd requirement created. A strict requirement that Electro remain clearly below Pyro in the maintained single-target mean is not met by this candidate. Pyro still leads in the same eight individual profiles, including the ordinary lightning-susceptible comparisons illustrated above. The maintainer rejected this tradeoff to preserve Electro's crowd identity and Pyro's single-target role. The experiment is discarded, not pending adoption.

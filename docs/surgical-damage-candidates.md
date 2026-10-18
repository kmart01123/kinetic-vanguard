# Surgical late-game damage candidates

Status: **historical candidate evaluation**. The two rider proposals and the revised six-die Absolute Zero were [integrated into an earlier unreleased v15.0.0 snapshot](surgical-damage-integration.md). Branching Bolt's focused option was subsequently replaced by [crowd allocation](branching-bolt-integration.md). Pyrokinesis remains unchanged. This review uses the corrected pre-roll Discipline Maturation baseline, preserves that gamble, and examines Cryokinesis, Psychokinesis, and Electrokinesis separately.

**Absolute Zero revision:** the [lower-dice evaluation](absolute-zero-low-dice.md) replaces the 14/16/18d10 proposal below with 6d10 + 45/55/65. The original large-pool results are retained here for comparison; the rider numbers below describe that historical candidate snapshot.

## Recommended shortlist

| Discipline | Proposed change | Fighter-20 single-target DPR | Gain | Six-target aggregate DPR |
|---|---|---:|---:|---:|
| Cryokinesis | Absolute Zero: 14/16/18d10 | 87.100 → 95.429 | +8.328 (+9.56%) | 151.308 → 151.308 |
| Psychokinesis | Telekinetic Shove: 4 damage from Fighter 18 | 108.782 → 120.751 | +11.969 (+11.00%) | 122.050 → 132.062 |
| Electrokinesis | Branching Bolt: optional focused mode from Fighter 18 | 106.497 → 116.064 | +9.567 (+8.98%) | 208.723 → 208.723 |

These are equal-weight means over all 12 maintained Fighter-20 profiles. Each candidate was reoptimized separately at cluster sizes 1 and 6, including the Action Surge schedule. They are not full level-7/11/15/20 publication results. No target-parity threshold was used to select the candidates.

### Cryokinesis: improve Absolute Zero's single-target payoff

**Proposed rules change:** At Fighter level 20, Absolute Zero deals **14d10 / 16d10 / 18d10 cold damage** at tiers 0/1/2, replacing 10d10 / 12d10 / 14d10. Its 5-Psi cost, Blood Tax, Constitution save, half damage on success, targeting, control effects, and action requirement remain as currently authored. It remains a standalone action and cannot trigger Attack-action maturation.

The existing policy often prefers repeated Manifested Strikes over this capstone. Raising only this single-target feature provides a stronger competing action without increasing Arctic Tempest's area packet or granting additional control resources.

This deliberately retains cold immunity. The retained baseline's three cold-immune profiles average 54.818 single-target DPR, compared with 97.861 for the other nine profiles. Stronger cold damage cannot repair that fallback. Cryokinesis remains strictly cold at the maintainer's direction; the bludgeoning alternative is excluded from the recommendation.

### Psychokinesis: mature the basic damaging rider

**Proposed rules addition:** At Fighter level 18, Telekinetic Shove's fixed damage becomes **4 force damage instead of 2**, at every Overload tier. Its existing saving throws, movement, control effects, Psi cost, and Blood Tax remain unchanged. The shared 3d8 maturation packet remains unchanged.

The current optimized damage policies rely heavily on the free rider. This improves that ordinary attack sequence rather than adding damage to Mass Levitation or increasing control frequency. The alternative 4d8 Apex experiment gave a smaller improvement on the initial sentinels and would change the shared 3d8 procedure.

### Electrokinesis: trade branches for concentrated damage

**Proposed rules addition:** At Fighter level 18, when declaring Branching Bolt, you may choose a focused mode. In this mode, the struck creature is the only target, and the rider deals **two Manifested Strike dice instead of one**. This option applies at every tier; unused branches grant no further damage. The normal branching mode remains available. Psi/Blood Tax costs, existing resistance treatment, and declaration/hit requirements remain unchanged.

The choice is available whenever the rider is declared, including encounters with several enemies; it is not gated on the benchmark cluster size. The experimental planner chooses between the focused and normal modes using the same observed-state rules as existing riders.

This offers concentrated damage without increasing Electron Burst, Ball Lightning, or any secondary damage packet. Focused Static Discharge was also tested, but its free concentrated damage raised six-target aggregate results on the initial sentinels. Branching Bolt is the narrower candidate.

## Initial alternatives and sentinels

The first pass compared six alternatives across Ancient Copper Dragon, Ancient White Dragon, and Balor at clusters 1 and 6. Electrokinesis also used lightning-immune Ancient Blue Dragon, for 40 initial cases. The selected candidates were then extended to all 12 Fighter-20 profiles, for 72 complete shortlist cases. Retained results were reused rather than recomputed.

| Alternative | Single-target gain on initial three sentinels | Six-target aggregate gain on those sentinels |
|---|---:|---:|
| `absolute_zero_plus4` | +0.000 to +12.879 DPR | +0.000 to +0.000 DPR |
| `cryogenic_impact` | +0.000 to +22.107 DPR | +0.000 to +22.107 DPR |
| `shove4` | +11.652 to +13.013 DPR | +9.667 to +10.350 DPR |
| `apex4d8` | +7.307 to +7.427 DPR | +7.308 to +7.427 DPR |
| `focused_static6` | +7.685 to +14.883 DPR | +0.982 to +3.812 DPR |
| `focused_branch2dice` | +9.628 to +11.303 DPR | +0.000 to +0.000 DPR |

`cryogenic_impact` permits declaring cold or bludgeoning for the existing 3d8 Cryokinesis maturation packet; normal defenses apply to the chosen type. It improves the cold-immune Ancient White Dragon by 22.107 DPR without changing its cold immunity. `apex4d8` changes only Psychokinesis's packet to 4d8. `focused_static6` permits a single-target Static Discharge mode dealing 6 lightning damage, with its additional targets forfeited. The two focused Electrokinesis candidates give no damage increase against lightning-immune Ancient Blue Dragon.

## Boundaries and outstanding validation

- Pyrokinesis's projection and shared core mechanics are identical to the baseline in every shortlisted prototype.
- Absolute Zero's change is confined to its existing Fighter-20 feature. The rider additions are gated at Fighter 18; projections below their gates are unchanged.
- Existing control effects, costs, saves, action inventory, and comparator inputs are preserved. Damage and control remain separate objectives; this does not claim simultaneous best-damage/best-control performance.
- The focused Branching Bolt packet was checked as primary-only against normal defenses, Resistance, and Immunity. All shortlist cases retain or increase the optimized damage objective over their matching baseline.
- These prototypes alter isolated in-memory harness projections, with a local packet override for the two alternative Apex experiments. They do not establish production schema, Calculator, renderer, or control-catalog integration. No canonical rules or official benchmark tables were changed by this experiment.
- Three-target candidate results, playable level-18/19 outcomes, and table feel have not been evaluated here. Adoption requires canonical authoring, consumer parity and boundary tests, then a fresh publication benchmark for the frozen candidate.

Mass Levitation's recurring damage is excluded from the current damage evaluator because its timing requires additional state; its absence from damage-selected policies is not evidence that it is useless. Ball Lightning is a persistent effect whose value depends on uptime and encounter geometry. Neither feature needs a damage rewrite solely to improve this short-horizon table.

## Evidence

Baseline authority SHA-256: `63e34d17bce2dc410c8eb21ad508d9de2bacfec8ff0d11d0851ced4dce06b703`. All baseline authority, evaluator, roster, comparator, and configuration hashes still match the preceding published benchmark.

Ignored evidence is retained in `artifacts/surgical-damage/`: candidate definitions, the frozen projection, `results.json` (initial sentinels), `roster-results.json` (complete shortlist), `verification.json`, and progress logs. Both passes used 12 workers. `experiment.py` reproduces the six initial alternatives; `roster.py` fills out the three-candidate shortlist; `summarize.py` verifies scope and calculates these comparisons.

The original baseline is documented in [the declaration evaluation](maturation-declaration-evaluation.md); it is historical, not the current adopted rules or benchmark. These historical candidates informed [level-20 balance review #122](https://github.com/kmart01123/kinetic-vanguard/issues/122); the [final Cryokinesis evaluation](cryo-balance-evaluation.md) records its disposition.

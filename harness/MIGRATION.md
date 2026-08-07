# Legacy v12.1.0 to maintained v14.1 migration map

The immutable import was verified before use. Historical files retain their old labels only in provenance; maintained executable names and reports derive their version from YAML.

| Legacy input or function | Current location | Classification |
|---|---|---|
| `CFG` Proficiency Bonus, Psi, Psionic Focus | `KineticVanguard.yaml#/calculator/*_bands` | Canonical YAML mechanics |
| `BASE_MS` | `KineticVanguard.yaml#/calculator/manifested_strike_die_bands` | Canonical YAML mechanics |
| `DAMAGE_TYPE`, signature-save maps | `KineticVanguard.yaml#/calculator/harness_mechanics/disciplines` | Canonical YAML mechanics |
| `overload_tax` and Tier 2 declaration limit | `KineticVanguard.yaml#/calculator/harness_mechanics/overload` | Canonical YAML mechanics |
| `kv_dc`, `kv_attack_bonus` KV components | YAML progressions and discipline data projected by `src/harness-authority.ts`; SRD/configured Archery input remains in benchmark config | Shared canonical mechanics plus non-KV config |
| `rider_dice` and standalone/rider damage tables | Existing `KineticVanguard.yaml#/calculator/features/*/tiers/*/damage` | Shared Calculator/YAML mechanics |
| `rider_names`, feature availability | Stable entity IDs plus entity `level`, `activation`, and classifications projected from YAML | Canonical YAML mechanics |
| `rider_psi_cost` | Entity `psi_cost` projected from YAML | Canonical YAML mechanics |
| `relevant_rider_tiers` | YAML tier arrays plus `tier_minimum_levels` | Canonical YAML mechanics |
| damage type, resistance bypass, secondary targeting | `calculator.harness_mechanics/feature_rules` | Canonical YAML mechanics |
| control `scenarios()` KV rows and `CONDITION_RULES` | `calculator.harness_mechanics/feature_rules/control_tiers` | Canonical YAML mechanics |
| mastery-control behavior | `calculator.harness_mechanics/disciplines/*/mastery` and per-feature `replaces_mastery` | Canonical YAML mechanics |
| BM/EK damage builds and numerical assumptions | `harness/comparators/fighter-subclasses.json#/damage` | Minimal frozen third-party comparator parameters |
| BM/EK control scenarios | `harness/comparators/fighter-subclasses.json#/control` | Minimal frozen third-party comparator parameters |
| levels, rounds, base Fighter action-slot/feature progression plus Studied Attacks and Combat Prowess semantics, seeds, trials, cluster sizes, Blood Tax profile, all-Manifested-Strike/AT policy and optimizer information timing | `harness/config/benchmark.json` | Mixed configuration: project-authored methodology/profile structure plus SRD 5.2.1-derived Fighter mechanics |
| compact control scenario selection | `harness/config/benchmark.json#/control_matrix` | Matrix profile selection, not rules authority |
| SRD targets, HP, defenses, immunities, pages, URL | `harness/data/srd_targets.csv` | Pinned SRD data/provenance |
| attack/save enumeration, exact damage-defense application, equal weighting, and finite-horizon observed-state policy choice | `harness/model.py`, `damage_harness.py`, `control_harness.py` | Simulation/aggregation algorithm |
| `action_configurations`, `standalone_choices`, `turn_options` | Legal projected feature candidates and exact resource-aware Bellman policy in `damage_harness.py` | Reimplemented algorithm; no KV table |
| legacy CSV/Markdown/plot code | `comparison_report.py` and detailed CSV writers | Reporting algorithm |

## Preserved methodology

- levels 7, 11, 15, and 20;
- three rounds and historical action-slot counts (each slot is an Attack action for comparators; KV can replace one slot with its capped standalone Action);
- equal weighting of the pinned roster;
- cluster sizes 1, 3, and 6 with legal positioning assumed;
- no target death, ally turns, concentration loss, or Legendary Resistance spending;
- SRD resistance, immunity, vulnerability, Magic Resistance, size, type, and condition-immunity handling;
- 25% HP voluntary Blood Tax default and Advanced Training disabled;
- conventional GWM Battle Master and sword-and-board Eldritch Knight headline identities;
- control remains reliability only and is never converted to DPR; rider conditions/save outcomes and ally-turn feedback are excluded from damage, with Thermal Fracture’s self-attack Armor Class reduction as the explicit exception.

## Intentional differences

- Current rows use exact d20/save/die enumeration instead of NumPy/Pandas Monte Carlo sampling. Seed/trial settings remain compatibility metadata. Independent review completed with status `REVIEWED_WITH_DOCUMENTED_DIFFERENCES`; this is not a fresh Monte Carlo certification.
- All 336 preserved policies were reevaluated exactly. Historical Monte Carlo differences are sampling-scale (primary mean absolute `0.0323169` DPR, maximum `0.176034`; aggregate mean absolute `0.0374951`, maximum `0.340120`). The maintained adaptive policy improves 123 aggregate rows and ties 213, with no lexicographic regressions.
- Damage differences are retained and explained rather than normalized away: struck-target parity makes Branching Bolt and Electron Burst legal at cluster 1; Thermal Fracture's future Armor Class state survives exact frontier evaluation; and declaration, Studied Attacks, Combat Prowess, and Overload Mastery choices use only legally observed state. Nine primary-target decreases each buy an aggregate increase under the declared objective.
- Comparator tactics are now solved exactly within the declared three-round policy instead of preserving the historical evaluator's hard-coded True Strike order and greedy maneuver-die spending. Against the 28-target roster, Eldritch Knight changes materially on 13 targets with a `+0.345503015604` all-target mean DPR delta and a maximum `+2.211600949267` on the level-20 Tarrasque (`+4.404797%`). Battle Master changes on all 28 targets with a `+2.606555720195` mean DPR delta and a maximum `+5.961162905560` on the level-20 Ancient Black Dragon; its largest relative change is `+5.651049%` on the level-20 Tarrasque. No target has a material decrease. These are reviewed policy corrections, not Monte Carlo drift or historical-output normalization.
- CSV, Markdown, and self-contained HTML compact matrices are new. Headline ratios derive from displayed aggregate raw roster means.
- Control adds an explicit per-target best-legal-scenario envelope and selection-audit CSV. Ineligible targets contribute zero. Review accounted for all 1,212 historical rows: 1,181 like-for-like rows remain within historical sampling noise, three Kraken rows are canonical corrections, and 28 Beguile rows are retired because suggestion effects do not impose Charmed. All 168 winners and 16 matrix aggregates were recomputed. Four level-7 rows deliberately remain `ORDER CHECK` diagnostics.
- PNG plots are no longer a maintained primary output; generated data can be plotted externally without becoming source authority.

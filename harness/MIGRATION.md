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
| levels, rounds, action counts, seeds, trials, cluster sizes, Blood Tax profile, AT policy | `harness/config/benchmark.json` | Benchmark methodology/profile configuration |
| compact control scenario selection | `harness/config/benchmark.json#/control_matrix` | Matrix profile selection, not rules authority |
| SRD targets, HP, defenses, immunities, pages, URL | `harness/data/srd_targets.csv` | Pinned SRD data/provenance |
| attack/save enumeration, damage-defense application, equal weighting, Pareto-like package choice | `harness/model.py`, `damage_harness.py`, `control_harness.py` | Simulation/aggregation algorithm |
| `action_configurations`, `standalone_choices`, `turn_options` | Legal projected feature candidates and deterministic resource-aware choice in `damage_harness.py` | Ported algorithm; no KV table |
| legacy CSV/Markdown/plot code | `comparison_report.py` and detailed CSV writers | Reporting algorithm |

## Preserved methodology

- levels 7, 11, 15, and 20;
- three rounds and historical Attack-action counts;
- equal weighting of the pinned roster;
- cluster sizes 1, 3, and 6 with legal positioning assumed;
- no target death, ally turns, concentration loss, or Legendary Resistance spending;
- SRD resistance, immunity, vulnerability, Magic Resistance, size, type, and condition-immunity handling;
- 25% HP voluntary Blood Tax default and Advanced Training disabled;
- conventional GWM Battle Master and sword-and-board Eldritch Knight headline identities;
- control remains reliability only and is never converted to DPR.

## Intentional differences

- Current rows use exact d20/save/die expectation instead of NumPy/Pandas Monte Carlo sampling. Seed/trial settings remain provenance-compatible, but the new port is explicitly `PORTED_UNDER_REVIEW`, not certified.
- CSV, Markdown, and self-contained HTML compact matrices are new. Headline ratios derive from displayed aggregate raw roster means.
- Control adds an explicit per-target best-legal-scenario envelope and selection-audit CSV. Ineligible targets contribute zero.
- PNG plots are no longer a maintained primary output; generated data can be plotted externally without becoming source authority.

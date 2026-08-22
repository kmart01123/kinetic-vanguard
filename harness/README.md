# Kinetic Vanguard maintained benchmark harnesses

The damage, Control Value, and Control Reliability evaluators use exact analytical enumeration. `KineticVanguard.yaml` is the sole Kinetic Vanguard rules authority; Python receives a schema- and semantics-validated projection keyed by stable entity ID and does not maintain a second copy of Kinetic Vanguard rules.

## Authority and input boundaries

The harness keeps five input layers separate:

1. Root `KineticVanguard.yaml` supplies Kinetic Vanguard mechanics through `src/harness-authority.ts`.
2. `config/benchmark.json` supplies current benchmark levels, horizon, aggregation, target clustering, scenario policy, and SRD-derived base Fighter progression.
3. `config/control-value.json` supplies the frozen Control Unit and explicit per-primitive Slice-2 scalar transforms. It has no family fallback.
4. `data/srd_creatures.json` supplies the 330-creature SRD 5.2.1 source-fact catalog; `data/srd_creature_rosters.json` supplies the `headline` and `eligible_census` memberships; and `data/control_primitives.json` keeps SRD condition definitions separate from project-authored generic analytical primitives.
5. `comparators/fighter-subclasses.json` supplies the minimal Battle Master and Eldritch Knight packages used by the comparators. Their current-PHB packages are independently expressed mechanical abstractions from the sanitized Issue #96 and #92 rulings respectively; they are not labeled as SRD or CC content.

The CLIs default to the maintained 47-target `headline` profile. The 93-target `eligible_census` is the validation and sensitivity inventory and should not be run analytically without explicit authorization. Both profiles contain only SRD 5.2.1 creatures, and both damage and control consume the same `Target` projection.

Catalog rows contain static source facts only: identity, CR, AC, HP, ability modifiers, source-explicit save and skill bonuses, defenses, Magic and Legendary Resistance, size/type, movement, senses, passive Perception, and source locators. Encounter state such as current HP, position, conditions, visibility, concentration, target choice, and Advantage or Disadvantage belongs to evaluator code.

## Commands

Install the existing Node dependencies before running Python because the authority adapter invokes the TypeScript projection:

```text
npm ci
npm run harness:validate
npm run test:harness
```

Focused one-level, one-target output smokes:

```text
python3 -m harness.damage_harness --output-dir /tmp/kv-damage-smoke --profile headline --levels 7 --target-limit 1
python3 -m harness.control_harness --output-dir /tmp/kv-control-smoke --profile headline --levels 7 --target-limit 1
```

Full configured headline runs:

```text
npm run harness:damage -- --output-dir harness/results/damage
npm run harness:control -- --output-dir harness/results/control
python3 -m harness.damage_harness --profile headline --output-dir /tmp/kv-headline-damage --workers 4
python3 -m harness.control_harness --profile headline --output-dir /tmp/kv-headline-control
```

Use `--matrix-only` to omit detail CSVs or `--no-matrix` to omit the comparison matrix. Both CLIs accept `--authority` for authority mutation tests, write only below the required `--output-dir`, and perform no network access.

README benchmark synchronization performs full headline evaluations and is intentionally separate from ordinary unit validation:

```text
npm run readme:benchmarks
npm run readme:benchmarks:check
```

When only control publication inputs or copy changed, the control-only mode preserves the current Single-Target Damage subsection byte-for-byte and obtains fresh Control Value and Reliability evidence from one control run without executing the damage harness:

```text
npm run readme:control
npm run readme:control:check
```

The writer atomically replaces only the delimited balance region and refuses to overwrite a concurrently changed README. Use it only after an intentional authority, methodology, roster, comparator, or release-state change and review the numerical diff.

## Damage methodology

The maintained profile uses 25% of the fixed-HP budget for voluntary Blood Tax, disables Advanced Training, and replaces each configured attack with Manifested Strike. It evaluates levels 7, 11, 15, and 20 across three rounds, equal target weighting, cluster sizes 1, 3, and 6, no target death, no ally turns, legal configured positioning, and source-backed damage defenses.

The planner optimizes each target, discipline, and cluster independently, then averages target results within each level. Fighter progression declares attacks per Attack action, Action Surge uses over the three-round horizon, and the maximum of one Action Surge per turn. One shared enumerator spends every available use and exposes exactly `[2,1,1]`, `[1,2,1]`, and `[1,1,2]` at levels 7, 11, and 15, and `[2,2,1]`, `[2,1,2]`, and `[1,2,2]` at level 20. Every damage model evaluates that same inventory before outcome resolution; schedule choice therefore cannot see unobserved rolls or saves.

Kinetic Vanguard selects the schedule using aggregate damage followed by primary-target damage. Battle Master maximizes its maintained DPR objective. Eldritch Knight preserves independent primary and aggregate optimization, including independently selected schedules when those objectives differ. Pre-roll declarations use only legally observed state; Combat Prowess is the only modeled post-roll Kinetic Vanguard decision. Thermal Fracture's Armor Class reduction is the only control-to-damage feedback modeled.

On-hit riders follow the canonical `per_manifested_strike` repeatability contract. A paid rider may be selected again on later Manifested Strikes while resources remain; a 0-Psi Signature Rider still pays Blood Tax when Overloaded; and Tier 2 remains limited to one declaration per Attack action.

Holdout uses its canonical level-banded strike formula: levels 3–17 halve the complete strike packet and Fighter 18+ uses the Refined Holdout 1d6 + Psionic Ability modifier packet. At Fighter 18+, Psychokinesis also tracks its canonical 3d8 force maturation as availability local to each Attack action; the first qualifying hit consumes it, and a new Attack action from Action Surge starts with fresh availability.

Battle Master and Eldritch Knight consume only their declared comparator configuration. Battle Master uses a fixed damage-forward maneuver-known profile with exactly 5/7/9/9 entries at Fighter 7/11/15/20; it never swaps that profile by target, cluster, or observed result. Feinting Attack is an exact pre-roll option that commits its maneuver resource and the turn's Bonus Action before the attack roll, grants Advantage to that attack, and adds the committed die only if the attack ultimately hits. Feint and Great Weapon Master's Hew therefore share one Bonus Action opportunity. Precision Attack and ordinary on-hit maneuver damage retain their distinct observed-result paths and the one-maneuver-per-attack limit. The benchmark does not invent incoming misses for Riposte, adjacent-target geometry for Sweeping Attack, or movement value for Lunging Attack.

Fighter attack progression, Studied Attacks, Combat Prowess, Relentless, True Strike, weapon packages, and source-backed resistance handling are evaluated analytically from current code and configuration. An Action Surge slot can supply another Attack action but never an Eldritch Knight Magic action, and it does not relax the standalone Kinetic Vanguard psionic-action limit.

Damage matrices retain primary-target and aggregate-cluster DPR. For each row, Battle Master and Eldritch Knight define a dynamic min/max envelope: COLD is below both, IDEAL includes both boundaries, HOT is above both, and N/A represents an unavailable comparison. `Boundary Delta %` measures signed distance outside the nearest boundary.

## Control Reliability methodology

Control Reliability measures how often the configured control package takes effect; it does not compare condition severity, duration, area, or strategic value. For each level and target, the harness selects the highest legal named-feature-plus-mastery reliability for each configured build. An ineligible scenario contributes zero, and the selection audit records the per-target winner.

Eldritch Knight's published Control Reliability winner selection is restricted to its configured `reliability_scenario_ids`; its broader scenario inventory may still feed optional Control Value shadow detail without entering the published winner set. Battle Master uses a separate fixed control-forward 5/7/9/9 maneuver-known profile. Menacing Attack, Pushing Attack, and Trip Attack are its direct modeled scenarios; Pushing preserves 15-foot directly-away displacement, while Trip records target-turn standing recovery at half-Speed cost rather than assuming full-round persistence. Goading Attack and Disarming Attack remain visible diagnostics but fail closed to zero without alternate-target and held-object context. The remaining known maneuvers receive no hostile-control credit merely for occupying a legal loadout slot.

Kinetic Vanguard and Battle Master use legal repeated attack-delivered opportunities within one ordinary Attack action when their configured packages permit them. Eldritch Knight retains one configured cast; an Eldritch Strike package uses every ordinary primer attack to determine whether at least one hit established Disadvantage. Action Surge and repeated spell casts are not credited to Control Reliability.

Control Reliability uses the same dynamic comparator envelope as damage and keeps raw comparator values and boundary identities in generated matrices.

## Control Value methodology and detail

Control Value is the primary public control-balance metric; Control Reliability remains a separate public delivery diagnostic and keeps its own winner selection unchanged. `1.0 CU` is denial of one target's normal Action + Bonus Action for one scored target-turn window.

The frozen nominal rules are:

| Mechanical primitive | Frozen scalar rule |
| --- | --- |
| `active_turn_denial` | `1.00 × exposure` |
| `reaction_denial` | `0.20 × exposure` |
| `offensive_impairment_next_attack` | `0.15 × exposure` |
| `offensive_impairment_all_attacks` | `0.40 × exposure` |
| `mobility_loss_feet` | `0.30 × min(flat feet / benchmark locomotion speed, 1) × summed active target-turn probability` |
| `forced_displacement` | `0.02 × expected displaced feet` |
| `defensive_attack_advantage` | `0.25 × exposure` |
| `save_disadvantage` | `0.20 × exposure` |
| `save_auto_failure` | `0.40 × exposure` |
| `specified_action_requirement` | `0.75 × exposure` |
| `action_bonus_exclusivity` | `0.25 × exposure` |
| `attack_action_cap` | zero; diagnostic/context-required pending an authoritative baseline attack count |
| `bonus_action_denial` | `0.25 × exposure` |
| `turn_movement_denial` | `0.30 × exposure` |
| `flat_armor_class_penalty` | `0.05 × points × placed incoming-attack opportunities` |
| `flat_save_roll_penalty` | `0.05 × points × placed save opportunities` |
| `speed_multiplier` | `0.30 × (1 - remaining multiplier) × summed active target-turn probability` |
| `standing_movement_cost` | `0.15 × exposure` |
| `finite_next_save_roll_penalty` | zero in the current scalar because established Mind Sliver packages already modify downstream delivery probability |

`benchmark_locomotion_speed` is the maximum positive unconditional, nonchoice movement-mode speed in the maintained SRD target facts. It is a normalization denominator, not an encounter movement assumption. Bare Speed 0 and condition-level Speed 0 decompose to `turn_movement_denial`; only quantified flat reductions use `mobility_loss_feet`. A target without trustworthy benchmark locomotion speed downgrades flat mobility to `context_required` and contributes zero.

Scalar eligibility uses the final resolved `PrimitiveExposure.pricing_status` after placement and target-context downgrades. A resolved `candidate` scores only through its explicit frozen transform; a candidate without one fails closed. Resolved `context_required` and `unsupported` rows contribute zero while retaining their source, magnitude, probability, exposure, normalization, suppressor, qualifier, and reason diagnostics.

Repeatable accumulating instantaneous effects use expected successful occurrences: independent legal declaration probabilities sum, and displacement multiplies each success probability by its feet. Boolean or refresh-only conditions, Advantage/Disadvantage, Speed 0, and other nonstacking states retain union probability and ordinary normalization. This remains closed-form analysis, not mutable combat-state or timeline simulation.

Normalization keeps the landed duplicate, condition-inclusion, Mastery, and explicitly correlated all-attacks-over-next-attack rules. It also applies generic dominance for active-turn denial over lesser overlapping action/offense entries, Bonus Action denial over Action/Bonus exclusivity, same-ability automatic save failure over weaker save impairments, and complete turn movement denial over flat/multiplier/standing mobility. Multiple flat reductions share the `0.30 CU` complete-movement ceiling only when a component explicitly names their same-window correlation; independent sources remain independent and retain separate diagnostics. Glacial Spike still replaces Slow, Telekinetic Shove still replaces Push where canonically projected, Electron Burst leaves Sap's successful-save residual, and Graze contributes no Control Value.

`--shadow-detail` adds primitive detail, scenario detail, independent Value selection audit, and the 16-cell level/discipline Value matrix used for public classification. Value winner selection first excludes every ineligible scenario, then maximizes CU with lexicographically greatest scenario ID as the deterministic equal-CU tie-break; a set with no eligible scenario fails closed. Audit rows distinguish nonzero priced winners, legitimate eligible zeroes, and zeroes whose package is entirely context-required or unsupported. Primitive rows report application and active probabilities, expected occurrences and exposure, relevant benchmark locomotion speed, nominal weight, transform ID, scalar CU, resolved status, and normalization disposition.

The shadow layer preserves current condition decomposition, repeat-save timing, dependencies, and fail-closed behavior. Recoverable Prone generically exposes one target-turn `standing_movement_cost` at half Speed, regardless of comparator source. That recovery cost is suppressed while own-turn standing is explicitly unavailable; Prone's attack-facing consequences remain separate and context-sensitive. Unknown timing, magnitude, scope, or battlefield context remains contextual or unsupported.

The Eldritch Knight shadow inventory accounts for the 41 retained audited spells without duplicating the 110 exclusions in runtime data. Exact finite save penalties and deterministic turn branches are analytically enumerated. Reusable production composition evaluates legal prior-Attack-action Eldritch Strike and cross-turn Mind Sliver primers without changing the published Reliability IDs; only the initial qualifying save consumes either primer. Web and Evard's Black Tentacles use a three-window closed-form adversarial escape convention from explicit target Athletics facts with Strength fallback, preserving each escape Action and immediate legal exit without a combat timeline or pathfinding. Other area occupancy, two-sided visibility or isolation, transformations, and context-dependent packages remain explicitly unpriced where the maintained benchmark lacks the required geometry, opportunity, environment, behavior, or replacement-form data.

A focused shadow inspection is:

```text
python3 -m harness.control_harness --output-dir /tmp/kv-control-shadow --profile headline --levels 20 --target-limit 1 --no-matrix --shadow-detail
```

## Output and provenance

Filenames derive from the canonical `rules_version`. Each comparison matrix is emitted as CSV, Markdown, and self-contained HTML from one row model. Matrix provenance identifies the rules, authority, SRD catalog, roster, selected target profile, benchmark config, comparator config, exact analytical evaluator, and aggregation policy. Detail and selection-audit CSVs carry the same current source identities.

Generated rows also carry the project component boundary, SRD 5.2.1 attribution and modification notice, CC BY 4.0 Section 5 disclaimer reference, and unofficial comparator notice. Generated outputs, caches, and virtual environments are not official source.

## Licensing boundaries

Project-authored Python software, report structure, and technical configuration structure are BSD-3-Clause. SRD-derived catalog, roster, condition, and base-Fighter material remains CC BY 4.0. Original Kinetic Vanguard rules, examples, explanatory prose, documentation, and approved interface text remain CC BY-NC-SA 4.0. Battle Master and Eldritch Knight are unofficial comparator identifiers; the project does not grant rights in non-SRD Wizards-owned material. See `LICENSE.md` and `NOTICE.md` for complete terms and attribution.

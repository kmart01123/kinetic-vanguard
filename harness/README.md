# Kinetic Vanguard maintained benchmark harnesses

Status: **REVIEWED_WITH_DOCUMENTED_DIFFERENCES for v14.1**. Independent damage, control, and comparator review completed on 2026-08-07. This is not a fresh Monte Carlo certification; the historical v12.0.0 certification remains provenance only.

`KineticVanguard.yaml` is the sole Kinetic Vanguard rules authority. Python never parses feature prose and contains no parallel KV progression, Psi, save, damage, condition, tier, or targeting tables. `src/harness-authority.ts` uses the repository's restricted YAML loader plus canonical schema and semantic validation, then projects the real authority to Python by stable entity ID. Missing, duplicate, unavailable, or inconsistent mechanics stop the run.

## Authority and input boundaries

The benchmark keeps four distinct input layers:

1. **Kinetic Vanguard authority:** root `KineticVanguard.yaml`, projected by stable entity ID only after canonical schema and semantic validation.
2. **Benchmark configuration:** project-authored seeds, profiles, aggregation, target clustering, and scenario policy, together with SRD-derived base Fighter progression/mechanics, in `config/benchmark.json`, plus the project-authored Python simulation/reporting code.
3. **SRD data:** one 330-creature SRD 5.2.1 target catalog in `data/srd_creatures.json`, explicit ordered membership for `legacy_v14_1` (28), `headline` (47), and `eligible_census` (93) in `data/srd_creature_rosters.json`, and the condition-to-mechanical-primitive shadow catalog in `data/control_primitives.json`.
4. **Third-party comparator assumptions:** minimal independently expressed Battle Master and Eldritch Knight numerical packages in `comparators/fighter-subclasses.json`.

The runtime loads and hashes methodology and comparator assumptions separately. Neither file is Kinetic Vanguard rules authority.

### Licensing boundaries

Licensing follows the distinguishable components rather than assigning one blanket license to every harness file:

- project-authored Python software, report structure, and technical configuration structure are licensed under BSD-3-Clause;
- the project-authored methodology and structure in `config/benchmark.json` are BSD-3-Clause, while its SRD-derived base Fighter mechanics remain separately available under CC BY 4.0;
- the project-authored structure, benchmark selection, and independently authored analytical/policy expression in `comparators/fighter-subclasses.json` are BSD-3-Clause; individual parameters retain SRD or third-party status as applicable, and Battle Master/Eldritch Knight identifiers and underlying third-party mechanics are not licensed by the project;
- `data/srd_creatures.json`, `data/srd_creature_rosters.json`, and the condition semantics in `data/control_primitives.json` are SRD 5.2.1-derived material under CC BY 4.0; and
- original Kinetic Vanguard rules, examples, explanatory and editorial prose, documentation, approved interface text, and project-authored benchmark explanation remain under CC BY-NC-SA 4.0.

No configuration file or generated report relicenses SRD or third-party material. See the repository `LICENSE.md` and `NOTICE.md` for the complete component boundaries and attribution.

## Commands

Install the existing Node dependencies before running Python because the authority adapter invokes the checked-in TypeScript projection:

```text
npm ci
npm run harness:validate
npm run test:harness
```

Tiny fixed-input smoke runs:

```text
python3 -m harness.damage_harness --output-dir /tmp/kv-damage-smoke --levels 7 --target-limit 1 --trials 32 --seed 1151001
python3 -m harness.control_harness --output-dir /tmp/kv-control-smoke --levels 7 --target-limit 1 --trials 32 --seed 1000001
```

Full configured roster runs:

```text
npm run harness:damage -- --output-dir harness/results/damage
npm run harness:control -- --output-dir harness/results/control
python3 -m harness.damage_harness --profile headline --output-dir /tmp/kv-headline-damage --workers 4
python3 -m harness.control_harness --profile headline --output-dir /tmp/kv-headline-control
```

Both CLIs share the same catalog/profile loader and default to `legacy_v14_1` pending expanded-roster review. `headline` is the frozen source-only 47-target sensitivity profile. `eligible_census` is validation inventory only and must not be run analytically without explicit authorization. Use `--matrix-only` to omit detailed CSVs or `--no-matrix` to omit the compact matrix. Both CLIs default to the repository-root authority and accept `--authority` for mutation tests. They write only below the explicit `--output-dir` and perform no network access.

The catalog contains static SRD source facts only: identity, CR, AC, HP, ability and source-explicit save/skill bonuses, defenses, MR/LR, size/type, movement, hover, senses, passive Perception, and source locators. Missing skills remain absent rather than becoming explicit +0 facts. Position, current HP or conditions, visibility, concentration, routes, target choice, Advantage/Disadvantage, and other encounter state belong to scenario/runtime code and are not catalog data. No non-SRD creature source is accepted.

Synchronize the generated balance snapshot near the top of the repository README:

```text
npm run readme:benchmarks
npm run readme:benchmarks:check
```

Both commands run fresh full-roster damage and control evaluations directly from the canonical authority and maintained harness inputs. The writer atomically replaces only the delimited balance-matrix region and refuses to overwrite a concurrent README edit; both modes abort if any maintained build input changes during evaluation. The check recomputes that region and fails if the committed README differs. This path uses exact analytical enumeration, not Monte Carlo sampling, and does not compare against or update a tracked golden result. Run the writer after an intentional authority, methodology, roster, comparator, or release-status change, review the numerical diff, and then run the check. The snapshot's published or unreleased label is derived from the README release lines and must agree with canonical `rules_version`.

## Damage method

The headline profile is `official_default_25_percent_hp`: 25% of fixed-HP budget for voluntary Blood Tax, Advanced Training disabled, and every configured attack replaced by Manifested Strike, matching the historical default policy. Because the profile supplies no Kinetic Vanguard weapon packet, this is not a global optimization of every legal Fighter weapon/Manifested Strike mix. The harness retains levels 7, 11, 15, and 20; three rounds; the historical action-slot counts; equal target weighting; cluster sizes 1, 3, and 6; no target death; legal configured positioning; and SRD defense handling.

For comparators, every configured action slot is an Attack action. Kinetic Vanguard can instead spend one slot on its canonically capped standalone psionic Action; the slot count is therefore not an unconditional Attack-action count. Studied Attacks is granted only by a resolved miss after hit-instead effects and expires at the end of the next turn if unused. At level 20, Combat Prowess is an optimal decision after an observed attack-roll miss; using it resolves that miss as a hit, prevents that miss from establishing Studied Attacks, and the once-per-turn use resets at the start of the next turn. If an attack-roll bonus such as Precision Attack or Relentless is applied first but the modified roll still misses, Combat Prowess remains eligible.

The planner optimizes each target, discipline, and cluster independently using that scenario’s known defenses, then averages those per-target envelopes across the roster. Its lexicographic objective is aggregate damage followed by primary-target damage. Pre-roll declarations can use only legally observed state; the planner has no lookahead into unobserved outcomes, and Combat Prowess is the only modeled post-roll Kinetic Vanguard decision. General rider conditions and save outcomes do not feed back into damage, and ally-turn accuracy and damage are excluded. Thermal Fracture’s Armor Class reduction is the one explicit self-attack feedback exception modeled by the damage planner. The `Selection` field ends with `representative=locally-modal-path|policy=observed-state-adaptive`: its listed declarations follow the locally most-probable resolution at each branch only to make the adaptive result inspectable. It is neither the complete policy nor a claim that the displayed path is the globally most-probable complete path.

On-hit riders use the canonical `per_manifested_strike` repeatability contract. Ember Bolt, Glacial Spike, Telekinetic Shove, and Static Discharge were already 0-Psi repeatable Signature Riders before issue #58; issue #58 newly extends per-strike repeatability to paid on-hit riders. The damage planner can select the same rider again on later strikes, and the Control Reliability harness can retry a fixed Tier 0 or Tier 1 rider after an observed miss or failed control attempt while attacks, Psi, and Blood Tax budget remain. A 0-Psi Signature Rider still pays Blood Tax when Overloaded. Tier 2 remains limited to one declaration per Attack action.

The maintained evaluator analytically enumerates d20, save, and damage-die outcomes. Historical seeds and trial counts remain compatibility metadata, while generated provenance identifies `exact_analytical_enumeration` as the evaluator. Current output is `REVIEWED_WITH_DOCUMENTED_DIFFERENCES`, not freshly Monte Carlo-certified.

### Numerical review evidence

- Exact reevaluation of all 336 preserved historical policies agrees with the 25,000-trial rows at sampling scale: primary DPR mean absolute delta `0.0323169` and maximum `0.176034` (`0.289663%`); aggregate DPR mean absolute delta `0.0374951` and maximum `0.340120` (`0.281098%`).
- The clean observed-state policy improves aggregate damage in 123 rows, ties 213, and regresses in none. Nine rows trade lower primary-target damage for higher aggregate damage under the declared aggregate-first objective; the largest is level-20 Lich Psychokinesis, cluster 3 (primary `-6.26215`, aggregate `+2.06485`).
- Reviewed differences come from corrected struck-target parity for Branching Bolt and Electron Burst, state-aware Thermal Fracture decisions, and optimal observed-state Studied Attacks, Combat Prowess, and Overload Mastery timing. Historical outputs were not normalized back into the implementation.
- The default `legacy_v14_1` limits still apply: 28 equally weighted SRD targets, three rounds, legal configured positioning, no target death or ally damage, Advanced Training disabled, and delayed Mass Levitation target-turn damage excluded. Expanded profiles use the same loader and mechanics.

Damage produces separate primary-target and aggregate-cluster DPR rows. Headline percentages use displayed equal-weight roster aggregate values:

```text
KV as % of comparator = 100 × KV aggregate / comparator aggregate
```

For every displayed aggregate, `lower_bound = min(Battle Master, Eldritch Knight)` and `upper_bound = max(Battle Master, Eldritch Knight)`. COLD is below the lower boundary, IDEAL includes both boundaries, and HOT is above the upper boundary. `Boundary Delta %` is negative relative to the lower boundary for COLD, positive relative to the upper boundary for HOT, and `0.00` inside IDEAL. `N/A` is reserved for an unavailable comparison, including a required zero denominator.

The matrix CSV, Markdown, and HTML retain both named raw comparator aggregates and ordinary KV/comparator ratios, plus `Lower Comparator`, `Upper Comparator`, `Lower Boundary`, and `Upper Boundary` audit fields. Comparator crossover is ordinary evidence, not a separate balance state.

## Control method

The control headline metric is `roster-adjusted whole-package control stick %`. At each level and target, the harness selects the highest legal named-feature-plus-mastery reliability for each configured build. An ineligible scenario contributes zero; it is never dropped. The selection audit identifies the exact per-target winner. The detailed report retains reach, named control, mastery floor, whole-package reliability, and configured repeat-save survival.

Control Reliability evaluates legal repeated attack-delivered opportunities within one ordinary Attack action when the configured package permits them. Kinetic Vanguard retries a fixed Tier 0 or Tier 1 on-hit rider only while Manifested Strikes, Psi, Blood Tax budget, and Overload Mastery permit; observed misses or failed control attempts can lead to another declaration, while success completes the per-target reliability question. Battle Master retries one fixed configured on-hit maneuver after later observed hits while attacks and superiority dice remain: misses spend attacks but not dice, hit attempts spend one die, and no attack can spend more than one die. Relentless is not part of the configured control package. Eldritch Knight retains one Blindness/Deafness cast and one save, but an Eldritch Strike package uses every weapon attack in one ordinary primer Attack action to determine whether at least one hit established Disadvantage. Action Surge and repeated spell casts are not credited.

Published v14.1 Control Reliability used simpler one-shot scenario approximations. The v14.2-to-v14.1 control movement can therefore combine four sources: paid-rider repeatability from issue #58, correction of historical one-shot treatment for already-repeatable Signature Riders, Battle Master maneuver-retry fairness, and Eldritch Strike primer fairness. These effects interact, so the evidence does not claim an exact additive decomposition. The first PR #73 control output at `/tmp/kv-issue-58-final/control` has disposition `invalidated_comparator_retry_asymmetry`; it remains the historical record that exposed Signature Rider, Battle Master, and Eldritch Strike one-shot or one-primer under-modeling. The accepted damage output at `/tmp/kv-issue-58-final/damage` remains valid and was not rerun for this correction.

The public headline is **Control Reliability**; the configured numerical metric remains `roster-adjusted whole-package control stick %`.

### Control Value Slice-1 shadow detail

The optional `--shadow-detail` path adds `kv-<version>-control-value-shadow-detail.csv` beside the ordinary Control Reliability outputs. It reuses the runner's existing target eligibility, hit/save, paid-rider retry, Battle Master retry, Eldritch Strike primer, and repeat-save probabilities, then expands each condition or bare outcome into inspectable mechanical primitives. The shadow rows report their exposure basis, feet magnitude where canonical structure supplies one, active probabilities, expected exposure, normalization or suppression disposition, and `candidate`, `context_required`, or `unsupported` status.

For a repeat save at the start of the affected target's turn, a target-turn exposure window is scored after that save: with initial application probability `p` and repeat-save survival probability `q`, windows 1 through 3 are `p*q`, `p*q^2`, and `p*q^3`. Exposure bases whose event could occur on either side of that checkpoint remain `context_required`. Duplicate boolean primitives do not stack; measured speed reductions deduplicate only within the same source, so canonical reductions from distinct sources can stack until an overlapping Speed 0 effect dominates them.

For a repeat save at the end of the affected target's turn, that target experiences its first target-turn window before the first repeat save. The three target-turn windows are therefore `p`, `p*q`, and `p*q^2`. Reaction, incoming-attack, save, and other opportunities whose placement relative to that checkpoint is not established remain `context_required`; this convention does not create a timeline.

The Stage-A Eldritch Knight shadow inventory adds the SRD 5.2.1 mechanics for Ray of Frost, Color Spray, Ray of Sickness, Thunderwave, Hold Person, and complete Blindness/Deafness timing. Poisoned and Paralyzed decompose through the same primitive catalog, including a diagnostic/context-required melee-hit automatic-critical primitive. Spell attacks use proficiency plus the maintained EK spellcasting ability modifier and never inherit weapon magic bonuses. Hold Person uses catalog creature type and condition immunity, and the save-based spells expose their existing prior-Attack-action Eldritch Strike variants. Ray of Frost records War Magic cantrip delivery; leveled spells record ordinary action-spell delivery and Improved War Magic eligibility without optimizing action sequencing.

Stage B1 promotes every Eldritch Knight consequence, including the Stage-A inventory, into one small effect-package structure and adds Hideous Laughter, Sleep, and Hypnotic Pattern. Scenario metadata now separates delivery, spell access, targeting, automatic-success rules, and inactive break opportunities from effect-local gates, durations, repeat checkpoints, dependencies, and closed-form stages. Hideous Laughter uses the ordinary end-of-target-turn survival vector and retains its damage-triggered Advantage save without firing it under the controller-preserves-control policy; its effect also suppresses the target's own Prone-ending option. Sleep uses disjoint target-turn stages `[p, 0, 0]` and `[0, p*q, p*q]`, so its normalized Incapacitated exposure is `[p, p*q, p*q]` without a mutable timeline or probability-union model. Only the initial save in a prior-Attack-action Eldritch Strike package receives the primer blend; later saves use the ordinary probability `q`.

Hypnotic Pattern's Incapacitated and Speed-0 package has a generic dependency on an effective Charmed condition, so Charmed immunity suppresses the entire dependent package. With no repeat save and with controller damage and ally rescue excluded, its target-turn vector is `[p, p, p]`. Damage and external wake/break actions for all three spells remain structured diagnostics and are inactive in the maintained one-controller/no-ally-turn benchmark. Unconscious includes Incapacitated and Prone once, Speed 0, incoming attack Advantage, automatic Strength/Dexterity save failure, the same within-5-feet automatic-critical diagnostic used by Paralyzed, and context-required awareness denial.

The single maintained EK access progression supplies both spell availability and the highest legal upcast slot at Fighter levels 7, 11, 15, and 20. Targeting metadata records selectable-target caps and higher-slot increments, Sleep's 5-foot-radius sphere and caster choice, and Hypnotic Pattern's 30-foot cube plus ordinary-visual-access predicate. It does not calculate breadth or cluster value. The maintained SRD creature catalog contains no explicit no-sleep stat-block fact, so it intentionally has no all-false `does_not_sleep` field; Sleep can consume a source-explicit capability when one exists, never a name, type, subtype, or lore inference. Exhaustion immunity instead causes automatic save success for the whole package, while Incapacitated and Unconscious immunities suppress only their respective staged consequences.

This expanded inventory is available only to optional Control Value shadow detail. `reliability_scenario_ids` keeps the default/published Control Reliability selection on the two pre-Stage-A Blindness/Deafness packages, so new candidates cannot change its winner set. Shocking Grasp remains tracked on issue #92 and unsupported here until its Opportunity-Attack-only denial can be represented without claiming generic reaction denial.

The primitive layer has no weights and produces no Control Value scalar, winner selection, matrix cell, or README classification. `while_in_area` persistence and comparator timing, magnitude, or scope absent from the maintained comparator configuration fail closed as contextual or unsupported instead of invoking a battlefield or timeline model. Until a later reviewed slice authorizes analytical evidence, inspect this path only with focused sentinels such as:

```text
python3 -m harness.control_harness --output-dir /tmp/kv-control-shadow --levels 20 --target-limit 1 --trials 1 --no-matrix --shadow-detail
```

Control Reliability measures how often the configured control package takes effect. It does not measure the relative severity, duration, area, or strategic value of different control effects. A HOT result is a balance-review signal, not an automatic finding that the feature is overpowered.

Control Reliability uses the same dynamic min/max comparator envelope as damage. Percentages remain ordinary KV/BM and KV/EK ratios. No severity weights are assigned to conditions, and control is never converted into DPR.

The published v14.1 independent review accounted for all 1,212 historical control rows: 1,181 like-for-like analytical rows differ from the 250,000-trial results by `0.0532515` percentage points on average and at most `0.3128`; three Kraken rows are documented canonical corrections, and 28 Beguile rows were retired because suggestion and mass suggestion do not impose Charmed. All 168 selected winners and all 16 matrix aggregates were recomputed independently. That review predates the v14.2 repeated-opportunity corrections described above.

At level 7, Battle Master (`48.65625`) and Eldritch Knight (`41.25`) cross relative to the earlier assumed control ordering. Four rows previously surfaced that historical assumption as `ORDER CHECK`. The finalized min/max envelope treats this as an ordinary comparator crossover and classifies Kinetic Vanguard normally; the raw comparator values and boundary identities remain visible in detailed evidence.

## Primary comparators

- Battle Master damage consumes only the declared ability, weapon, magic-bonus, Great Weapon Fighting, Great Weapon Master, Graze, superiority-die, Relentless, Hew, and tactical-policy inputs. Within the frozen three-round horizon, it maximizes expected damage from legally observed state: after an observed attack roll it may retain its resources or use at most one superiority/Relentless die; that die adds damage on a hit or modifies the attack roll on a miss and is consumed before its outcome is known. A failed attack-roll bonus can still be followed by Combat Prowess. Relentless is one zero-pool-cost d8 per turn, Hew is an optional once-per-round bonus attack after an observed critical, and the Great Weapon Master proficiency bonus applies to every hit made as part of an Attack action but not to Hew's bonus attack.
- Battle Master control consumes only the maintained fighter attacks-per-action progression, the existing superiority pool, minimum level, attack/save numbers, Magic Resistance policy, and the selected scenario IDs with probability-relevant save, hit gate, size limit, condition, or outcome fields. It retries the same configured maneuver after legally observed hits, spends no die on a miss, spends one die on a hit attempt, and never uses more than one maneuver die per attack. It does not import Relentless from the damage package.
- Eldritch Knight damage consumes only the declared regular/True Strike ability modifiers, weapon and magic-bonus inputs, Dueling bonus, True Strike damage, and tactical policy. It uses exactly the configured number of True Strikes in each Attack action and chooses their positions before the current attack roll from observed state only; Studied Attacks and optional post-miss Combat Prowess can therefore change later choices, but no choice sees an unrolled attack or damage die.
- Eldritch Knight control keeps one structured SRD-only scenario inventory. The legacy/default Control Reliability selection consumes only `reliability_scenario_ids`, which remain plain Blindness/Deafness and Blindness after Eldritch Strike. Optional shadow packages consume the maintained spell-access progression, delivery, spell-attack or save math, generic effect packages, duration/repeat timing, condition dependencies, closed-form stages, inactive breaks, condition/outcome, creature-type eligibility, targeting, and magnitude metadata. Spell attacks use proficiency plus the single maintained spellcasting-ability progression; weapon ability and magic bonuses apply only to weapon attacks and the prior-Attack-action Eldritch Strike primer. Primer success remains at least one hit, repeated hits do not stack beyond Disadvantage, and neither Action Surge, same-turn Improved War Magic primers, repeated casts, a breadth score, nor a spell-resource optimizer is modeled.

The comparator model identifies the 2024 fifth-edition ruleset. Scenario IDs identify only the frozen packages actually evaluated; they are not comprehensive maneuver, spell, or subclass inventories. No subclass descriptions, feature prose, maneuver descriptions, spell descriptions, sourcebook tables, flavor, or copied character-building instructions are retained.

Any later public README table or classification derived from these optional SRD-only candidates must state that the candidate inventory is SRD-only and is not a complete Wizard spell-list or subclass assessment. Stage B1 does not publish such a table or regenerate the root README benchmark snapshot.

> Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document.

Hunter Ranger and Open Hand Monk are excluded from primary matrices.

## Output and provenance

Filenames derive from YAML `rules_version`, for example `kv-14-1-0-damage-comparison-matrix.csv`. Every matrix is emitted as CSV, Markdown, and self-contained HTML from one numerical row model. Raw KV, Battle Master, and Eldritch Knight aggregates; both ordinary ratios; dynamic boundary values and identities; band text; and signed `Boundary Delta %` remain visible in every detailed format. HTML color is supplemental. Provenance includes rules version, authority digest, roster digest, methodology-config digest, comparator-config digest, evaluator, compatibility-only seed/trial settings, aggregation, and review status.

The repository README snapshot is another rendering of freshly evaluated matrix rows, not a separate source of numerical truth. It uses level rows, discipline columns, and result-only cells for exactly two front-door views: primary-target DPR at cluster size 1 and single-target Control Reliability. All other primary-target and aggregate-cluster results remain in the detailed CSV, Markdown, and HTML release evidence. Synchronization validates the complete matrices, provenance, notices, raw values, ratios, dynamic boundaries, bands, comparator scope, and release state before selecting the two README views.

Every generated detail, selection-audit, and matrix CSV row also carries semantic `Notice ...` columns for the component boundary, the exact SRD 5.2.1 attribution, the SRD modification marker, the official CC-BY-4.0 Section 5 disclaimer reference, and the unofficial BM/EK comparator notice. Matrix Markdown and HTML display the same notices once in a visible **Licensing and notices** section so copied reports retain their attribution and component boundaries without repeating long notice text in the human-facing table.

Generated outputs, caches, virtual environments, and `.codex-import/` are ignored and are not official source.

See `MIGRATION.md` for the legacy-to-current mapping and `provenance/legacy-import.json` for verified hashes.

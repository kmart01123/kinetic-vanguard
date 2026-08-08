# Kinetic Vanguard maintained damage harness

Status: **REVIEWED_WITH_DOCUMENTED_DIFFERENCES for the v14.2 development line**. The maintained evaluator is damage-only. The Control Reliability implementation and its report pipeline were retired from current `main`; the frozen v14.1 release remains the historical source for those results.

`KineticVanguard.yaml` is the sole Kinetic Vanguard rules authority. Python does not parse feature prose or carry parallel Kinetic Vanguard progression, Psi, save, damage, tier, or targeting tables. The TypeScript loader validates the canonical YAML and emits `DamageHarnessProjection`; Python's `DamageAuthorityModel` loads that projection by stable entity ID and fails closed on missing, duplicate, unavailable, or inconsistent mechanics.

## Authority and input boundaries

The damage benchmark keeps four distinct input layers:

1. **Kinetic Vanguard authority:** root `KineticVanguard.yaml`, projected only after canonical schema and semantic validation.
2. **Damage methodology:** profiles, aggregation, target clustering, the explicit `damage_matrix.non_damage_effect_boundary`, historical seed/trial metadata, and SRD-derived Fighter progression/mechanics in `config/benchmark.json`, plus project-authored Python evaluation and reporting code.
3. **SRD target data:** the pinned 28-row SRD 5.2.1 roster and provenance in `data/srd_targets.csv`.
4. **Third-party damage comparator assumptions:** minimal independently expressed Battle Master and Eldritch Knight numerical packages in `comparators/fighter-subclasses.json`.

The runtime hashes canonical authority, methodology, comparator assumptions, and roster separately. Neither configuration file is Kinetic Vanguard rules authority.

### Control Authority v2 is separate

Control Authority v2 remains a structured, fail-closed contract for the control-methodology redesign. Its schema validation and shared TypeScript/Python parity corpus remain maintained. It is not part of `DamageHarnessProjection`, is not consumed by the damage benchmark, and does not evaluate, classify, or publish a v14.2 control result.

## Commands

Install the checked-in Node dependencies before running Python because the authority adapter invokes the TypeScript projection:

```text
npm ci
npm run harness:validate
npm run test:harness
```

Tiny fixed-input damage smoke run:

```text
python3 -m harness.damage_harness --output-dir /tmp/kv-damage-smoke --levels 7 --target-limit 1 --trials 32 --seed 1151001
```

Full configured roster run:

```text
npm run harness:damage -- --output-dir harness/results/damage
```

Use `--matrix-only` to omit the detailed CSV or `--no-matrix` to omit the compact damage matrix. The CLI defaults to the repository-root authority, accepts `--authority` for mutation tests, writes only below the explicit `--output-dir`, and performs no network access.

Synchronize the generated damage snapshot near the top of the repository README:

```text
npm run readme:damage
npm run readme:damage:check
```

Both commands run a fresh full-roster damage evaluation from canonical authority and maintained damage inputs. The writer atomically replaces only the `BEGIN/END GENERATED DAMAGE MATRIX` region and refuses to overwrite a concurrent README edit. Both modes fingerprint all maintained build inputs before evaluation and abort if any input changes. The check recomputes the region and fails if the committed README differs. This path uses exact analytical enumeration and does not compare against or update a tracked golden output.

Run the writer after an intentional authority, methodology, roster, damage-comparator, classification, reporting, or release-status change. Review the numerical diff before running the check. The snapshot's published or unreleased label derives from the README release lines and must agree with canonical `rules_version`.

## Damage method

The headline profile is `official_default_25_percent_hp`: 25% of fixed-HP budget for voluntary Blood Tax, Advanced Training disabled, and every configured attack replaced by Manifested Strike. Because the profile supplies no Kinetic Vanguard weapon packet, this is not a global optimization of every legal Fighter weapon/Manifested Strike mix. The benchmark covers levels 7, 11, 15, and 20; three rounds; equal target weighting; cluster sizes 1, 3, and 6; no target death; legal configured positioning; and SRD defense handling.

Every comparator action slot is an Attack action. Kinetic Vanguard may instead spend one slot on its canonically capped standalone psionic Action. The planner optimizes each target, discipline, and cluster independently from legally observable state, then averages target results across the roster. Its lexicographic objective is aggregate damage followed by primary-target damage. It cannot look ahead into unresolved outcomes. Thermal Fracture's Armor Class reduction is the one explicit non-damage effect allowed to feed back into self-attack damage; the configured boundary rejects other condition, control, outcome, and ally-turn feedback.

The evaluator analytically enumerates d20, saving-throw, and damage-die outcomes. Seeds and trial counts remain historical compatibility metadata; generated provenance identifies `exact_analytical_enumeration` as the evaluator. The current review status is `REVIEWED_WITH_DOCUMENTED_DIFFERENCES`, not a fresh Monte Carlo certification.

Damage produces separate primary-target and aggregate-cluster DPR rows. Headline percentages use displayed equal-weight roster aggregates:

```text
KV as % of comparator = 100 × KV aggregate / comparator aggregate
```

For each row, the lower boundary is the smaller Battle Master/Eldritch Knight result and the upper boundary is the larger. COLD is below the lower boundary, IDEAL includes both boundaries, and HOT is above the upper boundary. `Boundary Delta %` is signed against the nearest crossed boundary; `N/A` is reserved for an unavailable comparison, including a required zero denominator. Comparator crossover is ordinary evidence, not a separate state.

### Numerical review evidence

- Exact reevaluation of all 336 preserved historical damage policies agrees with the 25,000-trial rows at sampling scale: primary DPR mean absolute delta `0.0323169` and maximum `0.176034`; aggregate DPR mean absolute delta `0.0374951` and maximum `0.340120`.
- The observed-state policy improves aggregate damage in 123 rows, ties 213, and regresses in none. Nine rows trade lower primary-target damage for higher aggregate damage under the declared aggregate-first objective.
- Reviewed differences come from corrected struck-target parity for Branching Bolt and Electron Burst, state-aware Thermal Fracture decisions, and optimal observed-state Studied Attacks, Combat Prowess, and Overload Mastery timing. Historical outputs were not normalized into the maintained implementation.

## Damage comparators

- Battle Master consumes only the declared damage parameters and tactical-policy inputs. Within the frozen three-round horizon it maximizes expected damage from legally observed state.
- Eldritch Knight consumes only the declared damage parameters and tactical policy, including the configured True Strike positions and observed-state follow-up choices.

The comparator model identifies the 2024 fifth-edition ruleset. It is not a comprehensive maneuver, spell, or subclass inventory. No subclass descriptions, feature prose, spell descriptions, sourcebook tables, flavor, or copied character-building instructions are retained.

> Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document.

## Output and provenance

Filenames derive from YAML `rules_version`, for example `kv-14-2-0-damage-comparison-matrix.csv`. The damage matrix is emitted as CSV, Markdown, and self-contained HTML from one numerical row model. Every format retains raw Kinetic Vanguard, Battle Master, and Eldritch Knight aggregates; ordinary ratios; lower and upper comparator identities and values; classification; signed boundary delta; and provenance.

Provenance includes rules version, authority digest, roster digest, methodology-config digest, comparator-config digest, evaluator, compatibility-only seed/trial settings, aggregation, and review status. CSV rows carry structured component, SRD, and comparator notices; Markdown and HTML display the same notices in a visible licensing section.

The README generator validates the complete authoritative damage matrix, all raw and derived result fields, all provenance and notice fields, comparator scope, and release state before selecting primary-target cluster-size-1 rows for its single public heat table. Generated outputs, caches, virtual environments, and `.codex-import/` are ignored and are not official source.

The v14.1 restoration and review record is historical. See `MIGRATION.md` and `provenance/damage-review.json` for its retained review context; use the current commands and files above for maintained work.

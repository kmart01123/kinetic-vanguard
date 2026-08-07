# Kinetic Vanguard maintained benchmark harnesses

Status: **ported for v14.1 and awaiting current-output certification review**. The historical v12.0.0 certification is provenance, not a certification of current 14.1 results.

`KineticVanguard.yaml` is the sole Kinetic Vanguard rules authority. Python never parses feature prose and contains no parallel KV progression, Psi, save, damage, condition, tier, or targeting tables. `src/harness-authority.ts` uses the repository's restricted YAML loader plus canonical schema and semantic validation, then projects the real authority to Python by stable entity ID. Missing, duplicate, unavailable, or inconsistent mechanics stop the run.

## Authority and input boundaries

The benchmark keeps four distinct input layers:

1. **Kinetic Vanguard authority:** root `KineticVanguard.yaml`, projected by stable entity ID only after canonical schema and semantic validation.
2. **Benchmark methodology:** project-authored seeds, profiles, aggregation, target clustering, and scenario policy in `config/benchmark.json`, plus the Python simulation/reporting code.
3. **SRD target data:** the pinned 28-row SRD 5.2.1 roster and provenance in `data/srd_targets.csv`.
4. **Third-party comparator assumptions:** minimal independently expressed Battle Master and Eldritch Knight numerical packages in `comparators/fighter-subclasses.json`.

The runtime loads and hashes methodology and comparator assumptions separately. Neither file is Kinetic Vanguard rules authority.

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
```

Use `--matrix-only` to omit detailed CSVs or `--no-matrix` to omit the compact matrix. Both CLIs default to the repository-root authority and accept `--authority` for mutation tests. They write only below the explicit `--output-dir` and perform no network access.

## Damage method

The headline profile is `official_default_25_percent_hp`: 25% of fixed-HP budget for voluntary Blood Tax and Advanced Training disabled, matching the historical default policy. The harness retains levels 7, 11, 15, and 20; three rounds; the historical Attack-action counts; equal target weighting; cluster sizes 1, 3, and 6; no target death; legal configured positioning; and SRD defense handling.

The maintained port analytically enumerates d20, save, and expected-die outcomes after selecting legal packages from YAML. The historical seeds and trial counts remain in provenance for reproducibility and comparison tooling, but current analytical rows do not claim fresh Monte Carlo certification. This intentional implementation change removes sampling noise from fast gates; independent numerical review against the historical simulator remains required before certification.

Damage produces separate primary-target and aggregate-cluster DPR rows. Headline percentages use displayed equal-weight roster aggregate values:

```text
KV as % of comparator = 100 × KV aggregate / comparator aggregate
```

Expected order is Eldritch Knight ≤ Battle Master. COLD is below EK, IDEAL includes both boundaries, HOT is above BM, reversed order is ORDER CHECK, and a zero denominator is N/A. `Boundary Delta %` is the signed percentage from the violated boundary: negative below EK for COLD, positive above BM for HOT, and `0.00` inside IDEAL.

## Control method

The control headline metric is `roster-adjusted whole-package control stick %`. At each level and target, the harness selects the highest legal named-feature-plus-mastery reliability for each configured build. An ineligible scenario contributes zero; it is never dropped. The selection audit identifies the exact per-target winner. The detailed report retains reach, named control, mastery floor, whole-package reliability, and configured repeat-save survival.

This is a best-available reliability envelope, not a condition-value or severity score. It does not assert that different conditions are equal and never converts control into DPR.

Expected order is Battle Master ≤ Eldritch Knight. COLD is below BM, IDEAL includes both boundaries, HOT is above EK, reversed order is ORDER CHECK, and a zero denominator is N/A. Percentages remain ordinary KV/BM and KV/EK ratios. `Boundary Delta %` is negative below BM for COLD, positive above EK for HOT, and `0.00` inside IDEAL.

## Primary comparators

- Battle Master damage consumes only an ability modifier, weapon dice/type, Great Weapon Fighting flag, attack adjustment, configured Great Weapon Master bonus allowance, superiority-die size by level, and three-round use budget.
- Battle Master control consumes only minimum level, attack/save numbers, Magic Resistance policy, and the selected scenario IDs with probability-relevant save, hit gate, size limit, condition, or outcome fields.
- Eldritch Knight damage consumes only an ability modifier, weapon dice/type, attack adjustment, configured True Strike extra-damage dice/type, and three-round use count.
- Eldritch Knight control consumes only minimum level, attack/save numbers, Magic Resistance policy, and the selected scenario IDs with probability-relevant save, condition, and primer-hit fields.

The comparator model identifies the 2024 fifth-edition ruleset. Scenario IDs identify only the frozen packages actually evaluated; they are not comprehensive maneuver, spell, or subclass inventories. No subclass descriptions, feature prose, maneuver descriptions, spell descriptions, sourcebook tables, flavor, or copied character-building instructions are retained.

> Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document.

Hunter Ranger and Open Hand Monk are excluded from primary matrices.

## Output and provenance

Filenames derive from YAML `rules_version`, for example `kv-14-1-0-damage-comparison-matrix.csv`. Every matrix is emitted as CSV, Markdown, and self-contained HTML from one row model. Band text and the signed `Boundary Delta %` tuning distance are visible in every format; HTML color is supplemental. Provenance includes rules version, authority digest, roster digest, methodology-config digest, comparator-config digest, seed, trial setting, aggregation, and review status.

Generated outputs, caches, virtual environments, and `.codex-import/` are ignored and are not official source.

See `MIGRATION.md` for the legacy-to-current mapping and `provenance/legacy-import.json` for verified hashes.

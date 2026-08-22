# Kinetic Vanguard rules reference

Kinetic Vanguard is a schema-first, deterministic rules publication for a Fighter subclass based on System Reference Document 5.2.1 material. The complete player-facing publication is generated as one self-contained, offline-capable HTML file.

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, mechanics, metadata, tables, examples, and onboarding content are authored there and validated before publication. The README summarizes the project and contributor workflow; it is not a second rules source.

## Release status

- Current published release: **v14.2.0**
- Current development line: **v14.3.0**
- Implementation status: Active v14.3 development
- Canonical rules authority: `KineticVanguard.yaml`

Published releases use frozen `release/X.Y.Z` branches and annotated `vX.Y.Z` tags. The current published release is available from the [v14.2.0 GitHub Release](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.2.0).

Version 14.0.0 introduced the deterministic offline Calculator, advanced the authority schema to 2.0.0 for semantic rule and example structure, made Barrier require Concentration at Tier 0 and Tier 1, aligned Explosion/Implosion Tier 1 geometry, and made the canonical rules version the publication’s sole product version. Detailed changes belong in `CHANGELOG.md` and the generated publication rather than being duplicated here.

Version 14.1.0 restores maintained damage and control benchmark harness source. The harnesses use the same validated canonical mechanics as the Calculator where their needs overlap, retain Battle Master and Eldritch Knight as the primary comparators, and produce versioned CSV, Markdown, and self-contained HTML matrices. Benchmark tooling remains developer-only and is not part of the player-facing Calculator.

<!-- BEGIN GENERATED BALANCE MATRICES -->
## Balance benchmark snapshot

**Unreleased development snapshot** — canonical rules **v14.3.0**; current published release **v14.2.0**.

Target profile: `headline`. The maintained headline benchmark uses 47 creature profiles from SRD 5.2.1 at levels 7, 11, 15, and 20. These are exact analytical full-roster results, with creatures weighted equally within their level.

Battle Master and Eldritch Knight define the comparison envelope for each benchmark result. `IDEAL` means Kinetic Vanguard falls between the two comparator values, inclusive. `COLD` is below both; `HOT` is above both. The percentage on COLD and HOT cells shows the signed distance outside the nearest comparator boundary. `N/A` is reserved for a comparison that cannot be evaluated. This is a comparator-envelope benchmark, not a universal real-play balance tolerance, and `IDEAL` is not proof of balance in every game.

README cells intentionally contain only the public balance result: `IDEAL`, `COLD (-X%)`, `HOT (+X%)`, or `N/A`. Detailed evidence retains raw Kinetic Vanguard and comparator aggregates, dynamic boundaries, and the comparator identity supplying each boundary.

The front-door damage view is the single-target benchmark: primary-target DPR at cluster size 1. All other primary-target and aggregate-cluster results remain in the generated detailed release reports and are not collapsed into this table.

### Single-Target Damage

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | COLD (-6.99%) | IDEAL | COLD (-2.61%) | IDEAL |
| 11 | COLD (-19.47%) | IDEAL | COLD (-0.20%) | IDEAL |
| 15 | COLD (-18.10%) | IDEAL | IDEAL | COLD (-6.75%) |
| 20 | COLD (-41.52%) | COLD (-12.76%) | COLD (-14.95%) | COLD (-26.58%) |

### Control Value

**Primary control-balance metric:** how much mechanically useful control the selected package delivers. A Control Unit is a project analytical benchmark unit, **not a D&D rules quantity**.

For each target, build, and discipline, the benchmark filters out ineligible packages and selects the legal package with the highest Control Value. An exact CU tie is resolved by higher whole-package Control Reliability, then by ascending stable scenario ID. Control Value reports what that selected package delivers mechanically; CU is the common package-selection methodology for both readouts.

The band table compares Kinetic Vanguard against the Battle Master / Eldritch Knight Control Value envelope.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | IDEAL | COLD (-100.00%) | IDEAL | COLD (-34.91%) |
| 11 | IDEAL | COLD (-100.00%) | IDEAL | IDEAL |
| 15 | IDEAL | IDEAL | IDEAL | IDEAL |
| 20 | IDEAL | IDEAL | IDEAL | IDEAL |

### Kinetic Vanguard mean Control Value

This companion table shows the raw Kinetic Vanguard equal-weight roster mean for the same CU-selected packages represented by the band table.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | 0.943 CU | 0.000 CU | 0.324 CU | 0.144 CU |
| 11 | 1.074 CU | 0.000 CU | 1.407 CU | 0.311 CU |
| 15 | 1.064 CU | 0.524 CU | 1.462 CU | 0.473 CU |
| 20 | 1.204 CU | 0.555 CU | 1.672 CU | 0.469 CU |

### Kinetic Vanguard control catalog

This authority-driven catalog is a decomposition view: Kinetic Mastery and every exact rider tier are separate control sources. Each Kinetic Mastery row reports only that Mastery's control; each rider/tier/role row reports only control produced by that exact rider form. Mastery that may legally coexist during actual play is excluded from rider CU and delivery. The headline discipline benchmark above remains a separate whole-legal-package view.

Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20. Each column uses the complete maintained roster for that level.

**Cell format:** `CU · delivery · effective/roster`

Example: `0.143 CU · 95.00% · 12/12` means `0.143 CU` average Control Value and `95.00%` average initial control-delivery probability across the full benchmark roster at that fighter level. `effective/roster` is **targets against which at least one modeled control consequence from that exact source survives maintained structural restrictions, immunities, and effect dependencies / total roster targets**.

`12/12 effective` does **not** mean 100% delivery or that every consequence works; it means every roster target can receive at least one modeled consequence from that exact source. `10/11 effective` means one of the 11 creatures cannot receive any modeled control from that source. A target can remain counted in `12/12 effective` while appearing in a partial-effect exception because another modeled consequence survives. Coverage is not a save result, hit count, successful application count, CU threshold, pricing state, or delivery probability.

`Partial` means retained priced and retained context-required or unsupported consequences coexist; suppressed duplicate or weaker primitives do not create that label. `Unpriced` retains measurable delivery and effectiveness coverage without reporting zero CU. `No modeled control` means `0.000 CU` and no control delivery (`—`). `N/A` means the exact form is unavailable at that level.

Full denominator and state methodology: [Benchmark roster, effectiveness, and coverage](#benchmark-roster-effectiveness-and-coverage)

#### Cryokinesis

| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|
| Kinetic Mastery | 0.076 CU · 96.23% · 12/12 | 0.060 CU · 99.51% · 12/12 | 0.051 CU · 99.50% · 11/11 | 0.041 CU · 99.84% · 12/12 |
| Glacial Spike — T0 | 0.076 CU · 96.23% · 12/12 | 0.060 CU · 99.51% · 12/12 | 0.051 CU · 99.50% · 11/11 | 0.041 CU · 99.84% · 12/12 |
| Glacial Spike — T1 | 0.226 CU · 96.23% · 12/12 | 0.226 CU · 99.51% · 12/12 | 0.216 CU · 99.50% · 11/11 | 0.232 CU · 99.84% · 12/12 |
| Glacial Spike — T2 | N/A | 0.397 CU · 83.75% · 12/12 | 0.422 CU · 84.09% · 11/11 | 0.374 CU · 82.08% · 12/12 |
| Snow Chains — T0 | 0.807 CU · 96.23% · 12/12 | 0.836 CU · 99.51% · 12/12 | 0.861 CU · 99.50% · 11/11 | 0.897 CU · 99.84% · 12/12 |
| Snow Chains — T1 | 0.943 CU · 96.23% · 12/12 | 0.975 CU · 99.51% · 12/12 | 0.993 CU · 99.50% · 11/11 | 1.045 CU · 99.84% · 12/12 |
| Snow Chains — T2 | N/A | 1.033 CU (partial) · 83.75% · 12/12 | 1.025 CU (partial) · 84.09% · 11/11 | 0.964 CU (partial) · 82.08% · 12/12 |
| Frozen Ground — T0 | N/A | 0.125 CU · 41.54% · 12/12 | 0.124 CU · 41.23% · 11/11 | 0.119 CU · 39.52% · 12/12 |
| Frozen Ground — T1 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Frozen Ground — T2 | N/A | 0.435 CU · 37.79% · 11/12 | 0.474 CU · 41.23% · 11/11 | 0.440 CU · 38.27% · 11/12 |
| Arctic Tempest — T0 | N/A | N/A | 0.474 CU · 41.23% · 11/11 | 0.440 CU · 38.27% · 11/12 |
| Arctic Tempest — T1 | N/A | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Arctic Tempest — T2 | N/A | N/A | 0.928 CU (partial) · 41.23% · 11/11 | 0.889 CU (partial) · 39.52% · 12/12 |
| Absolute Zero — T0 | N/A | N/A | N/A | 0.119 CU · 39.52% · 12/12 |
| Absolute Zero — T1 | N/A | N/A | N/A | 0.444 CU · 39.52% · 12/12 |
| Absolute Zero — T2 | N/A | N/A | N/A | 1.189 CU (partial) · 100.00% · 12/12 |

#### Pyrokinesis

| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|
| Kinetic Mastery | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Ember Bolt — T0 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Ember Bolt — T1 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Ember Bolt — T2 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Thermal Fracture — T0 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Thermal Fracture — T1 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Thermal Fracture — T2 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Cinder Lance — T0 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Cinder Lance — T1 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Cinder Lance — T2 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Flare — T0 | N/A | N/A | 0.524 CU (partial) · 80.68% · 11/11 | 0.555 CU (partial) · 85.45% · 12/12 |
| Flare — T1 | N/A | N/A | 0.524 CU (partial) · 80.68% · 11/11 | 0.555 CU (partial) · 85.45% · 12/12 |
| Flare — T2 | N/A | N/A | 0.300 CU (partial) · 46.16% · 11/11 | 0.266 CU (partial) · 40.91% · 12/12 |
| Furnace Strike — T0 | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Furnace Strike — T1 | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Furnace Strike — T2 | N/A | N/A | N/A | 0.000 CU · — · no modeled control |

#### Psychokinesis

| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|
| Kinetic Mastery | 0.297 CU · 87.92% · 11/12 | 0.375 CU · 74.61% · 9/12 | 0.191 CU · 36.25% · 4/11 | 0.163 CU · 24.97% · 3/12 |
| Telekinetic Shove — T0 | 0.167 CU · 64.53% · 12/12 | 0.220 CU · 70.93% · 12/12 | 0.205 CU · 68.21% · 11/11 | 0.268 CU · 73.69% · 12/12 |
| Telekinetic Shove — T1 | 0.250 CU · 64.53% · 12/12 | 0.330 CU · 70.93% · 12/12 | 0.308 CU · 68.21% · 11/11 | 0.403 CU · 73.69% · 12/12 |
| Telekinetic Shove — T2 | N/A | 0.257 CU · 36.65% · 12/12 | 0.239 CU · 34.19% · 11/11 | 0.235 CU · 33.54% · 12/12 |
| Vectored Thrust — T0 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Vectored Thrust — T1 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Vectored Thrust — T2 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Explosion/Implosion — T0 — primary | N/A | 0.733 CU · 63.77% · 11/12 | 0.784 CU · 68.21% · 11/11 | 0.831 CU · 72.22% · 11/12 |
| Explosion/Implosion — T0 — secondary | N/A | 1.063 CU · 70.93% · 12/12 | 1.092 CU · 68.21% · 11/11 | 1.233 CU · 73.69% · 12/12 |
| Explosion/Implosion — T1 — primary | N/A | 0.733 CU · 63.77% · 11/12 | 0.784 CU · 68.21% · 11/11 | 0.831 CU · 72.22% · 11/12 |
| Explosion/Implosion — T1 — secondary | N/A | 1.393 CU · 70.93% · 12/12 | 1.400 CU · 68.21% · 11/11 | 1.636 CU · 73.69% · 12/12 |
| Explosion/Implosion — T2 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Telekinetic Slam — T0 | N/A | N/A | 0.082 CU · 40.95% · 11/11 | 0.083 CU · 41.25% · 12/12 |
| Telekinetic Slam — T1 | N/A | N/A | 0.164 CU · 40.95% · 11/11 | 0.165 CU · 41.25% · 12/12 |
| Telekinetic Slam — T2 | N/A | N/A | 0.487 CU · 100.00% · 11/11 | 0.489 CU · 100.00% · 12/12 |
| Mass Levitation — T0 | N/A | N/A | N/A | 0.138 CU (partial) · 11.67% · 3/12 |
| Mass Levitation — T1 | N/A | N/A | N/A | 0.180 CU (partial) · 11.67% · 3/12 |
| Mass Levitation — T2 | N/A | N/A | N/A | 0.000 CU · — · no modeled control |

#### Electrokinesis

| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|
| Kinetic Mastery | 0.144 CU · 96.23% · 12/12 | 0.149 CU · 99.51% · 12/12 | 0.149 CU · 99.50% · 11/11 | 0.150 CU · 99.84% · 12/12 |
| Static Discharge — T0 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Static Discharge — T1 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Static Discharge — T2 | N/A | 0.083 CU · 41.30% · 12/12 | 0.084 CU · 41.96% · 11/11 | 0.086 CU · 42.82% · 12/12 |
| Branching Bolt — T0 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Branching Bolt — T1 | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Branching Bolt — T2 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Electron Burst — T0 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Electron Burst — T1 | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Electron Burst — T2 | N/A | 0.248 CU · 41.30% · 12/12 | 0.252 CU · 41.96% · 11/11 | 0.257 CU · 42.82% · 12/12 |
| Forked Lightning — T0 | N/A | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Forked Lightning — T1 | N/A | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Forked Lightning — T2 — primary | N/A | N/A | 0.453 CU · 50.32% · 11/11 | 0.467 CU · 51.85% · 12/12 |
| Forked Lightning — T2 — secondary | N/A | N/A | 0.302 CU · 50.32% · 11/11 | 0.311 CU · 51.85% · 12/12 |
| Ball Lightning — T0 | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Ball Lightning — T1 | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Ball Lightning — T2 | N/A | N/A | N/A | Unpriced · 51.85% delivery · 12/12 |

### Control coverage exceptions

These generated rows expose structural exclusions, complete effect nullification, and partial losses from the same evidence used by the catalog.

| Discipline / exact form | Level | Affected target(s) | Status | Reason |
|---|---|---|---|---|
| Cryokinesis — Glacial Spike — T2 | Fighter 11 | Guardian Naga | Partial | immune to Restrained; Speed reduction remains effective |
| Cryokinesis — Glacial Spike — T2 | Fighter 20 | Kraken | Partial | immune to Restrained; Speed reduction remains effective |
| Cryokinesis — Snow Chains — T0 | Fighter 7 | Air Elemental | Partial | immune to Restrained; Speed 0 remains effective |
| Cryokinesis — Snow Chains — T0 | Fighter 11 | Guardian Naga | Partial | immune to Restrained; Speed 0 remains effective |
| Cryokinesis — Snow Chains — T0 | Fighter 20 | Kraken | Partial | immune to Restrained; Speed 0 remains effective |
| Cryokinesis — Snow Chains — T1 | Fighter 7 | Air Elemental | Partial | immune to Restrained; Speed 0 and Reaction denial remain effective |
| Cryokinesis — Snow Chains — T1 | Fighter 11 | Guardian Naga | Partial | immune to Restrained; Speed 0 and Reaction denial remain effective |
| Cryokinesis — Snow Chains — T1 | Fighter 20 | Kraken | Partial | immune to Restrained; Speed 0 and Reaction denial remain effective |
| Cryokinesis — Frozen Ground — T2 | Fighter 11 | Guardian Naga | Ineffective | immune to Restrained |
| Cryokinesis — Frozen Ground — T2 | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Cryokinesis — Arctic Tempest — T0 | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Cryokinesis — Absolute Zero — T1 | Fighter 20 | Kraken | Partial | immune to Restrained; Speed 0 remains effective |
| Psychokinesis — Kinetic Mastery | Fighter 7 | Giant Ape | Ineffective | exceeds maximum size Large |
| Psychokinesis — Kinetic Mastery | Fighter 11 | Remorhaz, Storm Giant, Adult White Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Kinetic Mastery | Fighter 15 | Adult Black Dragon, Adult Blue Dragon, Adult Bronze Dragon, Adult Copper Dragon, Adult Green Dragon, Purple Worm, Adult Silver Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Kinetic Mastery | Fighter 20 | Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Ancient Silver Dragon, Ancient White Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Explosion/Implosion — T0 — primary | Fighter 11 | Guardian Naga | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T0 — primary | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T0 — secondary | Fighter 11 | Guardian Naga | Partial | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Explosion/Implosion — T0 — secondary | Fighter 20 | Kraken | Partial | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Explosion/Implosion — T1 — primary | Fighter 11 | Guardian Naga | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T1 — primary | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T1 — secondary | Fighter 11 | Guardian Naga | Partial | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Explosion/Implosion — T1 — secondary | Fighter 20 | Kraken | Partial | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Mass Levitation — T0 | Fighter 20 | Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Ancient Silver Dragon, Ancient White Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Mass Levitation — T1 | Fighter 20 | Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Ancient Silver Dragon, Ancient White Dragon | Ineffective | exceeds maximum size Large |

### Benchmark roster, effectiveness, and coverage

Every Fighter level uses the complete maintained headline roster for that level. Structural legality remains an internal prerequisite evaluated by `target_is_eligible()` from maintained maximum-size and required-creature-type restrictions. Public `effective/roster` coverage asks a different question: for how many roster targets does at least one modeled control consequence from this exact Mastery or rider survive structural restrictions, maintained immunities, and effect dependencies?

A structural restriction makes a target ineffective for that exact source. Maintained immunity can instead remove one or more consequences after the structural check. If another consequence survives, the target is partially effective and remains in the coverage numerator; if every modeled consequence is nullified, the target is ineffective. Thus `12/12 effective` does not mean 100% delivery, 12 successful saves or attacks, 12 successful applications, or that every consequence works against every target.

Effective coverage is descriptive metadata, not a success roll, CU threshold, pricing state, delivery probability, or alternate averaging population. An ineffective target remains in the aggregate denominator at its existing `CU = 0` and `delivery = 0%` contribution. A partially effective target contributes the CU and delivery of the consequences that survive.

`mean CU = sum(per-target CU across the complete roster) / total roster targets`

`mean delivery = sum(per-target initial-delivery probability across the complete roster) / total roster targets`

Do not divide only by effective targets. Effective-only averaging would hide practical restrictions and could make a narrowly applicable control look stronger or more reliable than it is across the maintained benchmark roster.

**Instructional example (not a published scenario):** if a form has 80% delivery against 9 effective targets and 3 ineffective targets contribute 0%, its full-roster delivery mean is `(9 × 0.80 + 3 × 0) / 12 = 0.60 = 60%`. The effective-only 80% is not the roster-wide result.

`Priced` and `Partial` use the complete-roster denominator above. `Unpriced` can still be effectively covered and show independently measurable delivery, but its CU field remains `Unpriced`, not zero. `No modeled control` is `0.000 CU` because that catalog source declares no modeled control, with delivery `—` because no control establishment is measured. `N/A` means the exact form is unavailable at that Fighter level and does not participate in that level's aggregate.

### How Control Value is calculated

1.0 CU = denial of one target's normal Action + Bonus Action for one scored target-turn window.

The calculation pipeline is: condition/outcome → mechanical primitives → expected delivery/persistence/opportunities → overlap normalization → primitive CU contributions → total Control Value.

General arithmetic: `primitive contribution = frozen weight × expected exposure`.

Expected exposure is where delivery probability, persistence, placed attack, save, and reaction opportunities, and repeatable instantaneous occurrences enter the calculation. Overlap normalization then prevents the same mechanical consequence from being counted twice.

#### Worked example: Sap-style next-attack Disadvantage

The maintained next-attack Disadvantage outcome resolves to `offensive_impairment_next_attack`, weighted at 0.15 CU per expected placed attack opportunity.

Illustrative arithmetic: `0.15 × 0.95 = 0.1425 CU`.

The 95% expected exposure is an instructional example, not a published target or roster result. Even at very high delivery, the effect remains low-Control-Value because it impairs only one attack. Repeated legal attack attempts can make this kind of rider highly reliable without making its consequence more severe; Sap is not assumed to be the selected package in every Electrokinesis matrix cell.

#### Worked example: Stunned

This is an **opportunity-normalized synthetic example**. It assumes 1.00 expected exposure independently on every displayed priced basis; it does not treat those different opportunity types as one shared target-turn window.

| Priced piece | Exposure basis | Nominal weight | Example exposure | Contribution |
|---|---|---|---|---|
| active-turn denial | `target_turn_window` | 1.00 CU | 1.00 | 1.00 CU |
| reaction denial | `reaction_window` | 0.20 CU | 1.00 | 0.20 CU |
| Strength save automatic failure | `save_opportunity` | 0.40 CU | 1.00 | 0.40 CU |
| Dexterity save automatic failure | `save_opportunity` | 0.40 CU | 1.00 | 0.40 CU |
| incoming attack Advantage | `incoming_attack_opportunity` | 0.25 CU | 1.00 | 0.25 CU |
| **Total** |  |  |  | **2.25 CU** |

Incapacitated supplies the active-turn and reaction pieces; Stunned adds the two save automatic failures and incoming attack Advantage. Stunned does **not** gain Speed 0. Concentration, speech, fall, and other context-sensitive consequences remain diagnostic rather than receiving invented headline CU. Real Stunned benchmark rows do **not** automatically equal 2.25 CU because target-turn, reaction, save, and incoming-attack opportunity counts and probabilities can differ.

### Control Unit primitive pricing rubric

This is the complete maintained scoring-rule inventory. Primitive basis and default pricing status come from the primitive catalog; nominal weights and transform IDs come from the frozen scoring config.

| Primitive | Exposure basis | Default pricing status | Nominal weight | Scoring rule |
|---|---|---|---|---|
| `active_turn_denial` | `target_turn_window` | `candidate` | 1.00 CU | `linear_expected_exposure` |
| `reaction_denial` | `reaction_window` | `candidate` | 0.20 CU | `linear_expected_exposure` |
| `offensive_impairment_next_attack` | `attack_opportunity` | `candidate` | 0.15 CU | `linear_expected_exposure` |
| `offensive_impairment_all_attacks` | `target_turn_window` | `candidate` | 0.40 CU | `linear_expected_exposure` |
| `mobility_loss_feet` | `target_turn_window` | `candidate` | 0.30 CU | `bounded_fraction_of_benchmark_locomotion` |
| `forced_displacement` | `instantaneous_occurrence` | `candidate` | 0.02 CU | `expected_displaced_feet` |
| `defensive_attack_advantage` | `incoming_attack_opportunity` | `candidate` | 0.25 CU | `linear_expected_exposure` |
| `save_disadvantage` | `save_opportunity` | `candidate` | 0.20 CU | `linear_expected_exposure` |
| `save_auto_failure` | `save_opportunity` | `candidate` | 0.40 CU | `linear_expected_exposure` |
| `specified_action_requirement` | `target_turn_window` | `candidate` | 0.75 CU | `linear_expected_exposure` |
| `action_bonus_exclusivity` | `target_turn_window` | `candidate` | 0.25 CU | `linear_expected_exposure` |
| `attack_action_cap` | `attack_opportunity` | `context_required` | 0.00 CU | `diagnostic_zero` |
| `bonus_action_denial` | `target_turn_window` | `candidate` | 0.25 CU | `linear_expected_exposure` |
| `turn_movement_denial` | `target_turn_window` | `candidate` | 0.30 CU | `linear_expected_exposure` |
| `flat_armor_class_penalty` | `incoming_attack_opportunity` | `candidate` | 0.05 CU | `points_times_placed_opportunities` |
| `flat_save_roll_penalty` | `save_opportunity` | `candidate` | 0.05 CU | `points_times_placed_opportunities` |
| `speed_multiplier` | `target_turn_window` | `candidate` | 0.30 CU | `remaining_speed_fraction` |
| `standing_movement_cost` | `target_turn_window` | `candidate` | 0.15 CU | `linear_expected_exposure` |
| `finite_next_save_roll_penalty` | `save_opportunity` | `context_required` | 0.00 CU | `diagnostic_zero` |

#### Maintained transform definitions

| Transform | Formula | Meaning |
|---|---|---|
| `linear_expected_exposure` | `CU = nominal weight × expected exposure` | Expected exposure is the placed probability/opportunity exposure for the primitive's maintained basis. |
| `bounded_fraction_of_benchmark_locomotion` | `CU = nominal weight × min(expected lost feet / benchmark locomotion Speed, active-window exposure)` | For one fully active window: CU = nominal weight × min(flat feet lost / benchmark locomotion Speed, 1). |
| `expected_displaced_feet` | `CU = nominal weight × expected displaced feet` | Displacement uses expected intrinsic feet only; it does not invent terrain or collision value. |
| `diagnostic_zero` | `CU = 0 headline CU` | This is a deliberate non-scalar/context diagnostic rule, not a claim that the mechanic has zero real-play value. |
| `points_times_placed_opportunities` | `CU = nominal weight × expected penalty-points/opportunities` | The placed exposure already combines the exact penalty magnitude with established attack or save opportunities. |
| `remaining_speed_fraction` | `CU = nominal weight × (1 - remaining Speed fraction) × active-window exposure` | The magnitude is the exact fraction of Speed that remains. |

#### How movement control is normalized

There is **no universal 30-foot target assumption**.

**Complete movement denial.** `turn_movement_denial` (Speed 0) is valued at `0.30 CU × active exposure`, independent of ordinary Speed. A creature with 10, 30, 60, or 80 feet of ordinary benchmark locomotion loses all movement capacity when rooted.

**Flat Speed loss.** `mobility_loss_feet` uses `0.30 CU × min(expected lost feet / benchmark locomotion Speed, active-window exposure)`. For one fully active window this is `weight × min(flat feet lost / benchmark locomotion Speed, 1)`.

**Illustrative calculations (not current aggregate results):**

| Illustrative case | Calculation | Result |
|---|---|---|
| -10 ft against benchmark Speed 10 | 0.30 × min(10 / 10, 1) | 0.30 CU |
| -10 ft against benchmark Speed 30 | 0.30 × min(10 / 30, 1) | 0.10 CU |
| -10 ft against benchmark Speed 60 | 0.30 × min(10 / 60, 1) | 0.05 CU |
| -30 ft against benchmark Speed 60 | 0.30 × min(30 / 60, 1) | 0.15 CU |
| Speed 0 against any ordinary Speed | 0.30 × 1.00 active exposure | 0.30 CU |

**Benchmark locomotion assumption.** `benchmark_locomotion_speed` is the fastest positive movement mode in the maintained SRD target record that is unconditional, unqualified, and not choice-dependent. Qualified or choice-dependent modes are excluded; walking Speed is not privileged. If no trustworthy positive mode exists, flat `mobility_loss_feet` fails closed to `context_required`.

Using the fastest unconditionally available listed mode supplies a neutral, target-specific denominator without inventing encounter geometry. It can conservatively understate a flat reduction in a fight where that fastest mode cannot be used. For example, an unconditional Fly Speed remains the maintained denominator even if a particular room prevents flight; the benchmark does not silently substitute walking Speed for an unmodeled battlefield.

**Correlated flat movement cap.** Multiple flat reductions are capped at complete movement denial only when explicit maintained correlation metadata connects their sources for the same scored windows. The cap never exceeds the target's benchmark locomotion Speed. Sharing a package, a primitive, or the fact that both reduce Speed does not establish correlation; unrelated mobility effects remain independent.

### Context-dependent and unpriced control primitives

Every primitive below defaults to `context_required` or `unsupported`, including entries with no scalar scoring rule. It contributes 0 headline CU when the benchmark cannot establish the required context. That fail-closed zero does **not** mean the mechanic is worthless in actual play.

| Primitive | Exposure basis | Status | Why it is not assigned headline CU |
|---|---|---|---|
| `target_choice_restriction` | `contextual_opportunity` | `context_required` | Value depends on the restricted source and available target choices. |
| `sight_option_denial` | `contextual_opportunity` | `context_required` | Value depends on sight-dependent options and alternative senses. |
| `movement_mode_denial` | `contextual_opportunity` | `context_required` | Value depends on the target's usable movement modes. |
| `geometry_sensitive_approach_restriction` | `contextual_opportunity` | `context_required` | Requires source geometry and a willing movement choice. |
| `ability_check_impairment` | `contextual_opportunity` | `context_required` | Requires a relevant ability-check opportunity and any stated predicate. |
| `speech_denial` | `contextual_opportunity` | `context_required` | Requires a communication-dependent opportunity. |
| `social_interaction_advantage` | `contextual_opportunity` | `context_required` | Requires a social interaction check involving the source. |
| `concentration_break` | `instantaneous_occurrence` | `context_required` | Requires the target to be concentrating. |
| `fall_transition` | `instantaneous_occurrence` | `context_required` | Requires airborne state and lack of hover or fall prevention. |
| `prone_incoming_attack_context` | `incoming_attack_opportunity` | `context_required` | Incoming attack effect depends on attacker distance. |
| `melee_hit_auto_critical_context` | `contextual_opportunity` | `context_required` | Automatic critical hits require a hit from an attacker within 5 feet. |
| `awareness_denial` | `contextual_opportunity` | `context_required` | Value depends on encounter information and awareness-sensitive opportunities. |
| `opportunity_attack_denial` | `contextual_opportunity` | `context_required` | Only a qualifying Opportunity Attack is denied; other Reactions remain available. |
| `terrain_movement_tax` | `target_turn_window` | `context_required` | Movement through the affected terrain costs additional movement without changing the Speed statistic. |
| `directional_movement_tax` | `contextual_opportunity` | `context_required` | The movement cost applies only in a specified direction and requires geometry. |
| `attack_action_cap` | `attack_opportunity` | `context_required` | The target's Attack action is capped, but the maintained target catalog does not establish a baseline attack count. |
| `restricted_attack_choice` | `contextual_opportunity` | `context_required` | The available attack and target depend on creatures within reach. |
| `finite_next_save_roll_penalty` | `save_opportunity` | `context_required` | The next qualifying save uses an exact finite penalty die and requires a downstream save opportunity. |
| `somatic_spell_failure` | `contextual_opportunity` | `context_required` | Value requires a qualifying spell with a Somatic component. |
| `damage_roll_penalty` | `contextual_opportunity` | `context_required` | Damage rolls are reduced without changing attack accuracy; value requires an offensive-output convention. |
| `two_sided_isolation` | `contextual_opportunity` | `context_required` | Interaction is blocked in both directions and cannot be valued as unilateral denial. |
| `target_protection` | `contextual_opportunity` | `context_required` | The controlled target is also protected from outside effects or attacks. |
| `retained_action_option` | `contextual_opportunity` | `context_required` | The target retains a specified Action or movement option that limits net control value. |
| `spellcasting_interruption` | `contextual_opportunity` | `context_required` | Value requires a qualifying observable enemy spellcasting opportunity. |
| `ongoing_spell_removal` | `contextual_opportunity` | `context_required` | Value requires a qualifying ongoing spell state and its established consequence. |
| `hostile_transformation` | `contextual_opportunity` | `context_required` | Value depends on an approved replacement-form inventory and its exact statistics. |
| `attitude_change` | `contextual_opportunity` | `context_required` | Behavioral value depends on encounter choices and is not inferred. |
| `size_change` | `contextual_opportunity` | `context_required` | Size change has value only when another established mechanic depends on size. |
| `open_ended_behavior` | `contextual_opportunity` | `context_required` | Behavioral consequences depend on an encounter-specific choice that the benchmark does not invent. |
| `held_item_loss` | `contextual_opportunity` | `context_required` | Value depends on whether the target holds relevant items and can recover or replace them. |
| `damage_output_change` | `contextual_opportunity` | `context_required` | Damage-output changes remain visible but outside the current Control Value scalar boundary. |
| `hearing_option_denial` | `contextual_opportunity` | `context_required` | Value requires a hearing-dependent option or communication opportunity. |

`unsupported` can also arise dynamically when a known mechanic lacks a trustworthy required magnitude, timing, or placement/exposure basis. Maintained examples of unresolved context include Ball Lightning future area occupancy, Mass Levitation recurring displacement cadence, and condition-context facts such as sight, concentration, speech, fall state, or attacker distance. The benchmark does not manufacture encounter facts to turn these diagnostics into numbers.

### Control Value normalization rules

Normalization prevents double charging while preserving independently established consequences. These statements describe `normalize_exposures()` and the explicit correlated-flat-mobility cap; they are not a second scoring engine.

| Rule | Maintained behavior |
|---|---|
| Duplicates | Identical primitive/basis/qualifier/magnitude consequences do not double count. `mobility_loss_feet` and `forced_displacement` remain source-specific so distinct legitimate sources are not automatically collapsed. |
| Disjoint sequential stages | Explicitly declared disjoint stages combine probabilities instead of becoming duplicate overlap; their combined probability may not exceed 1. |
| Action-economy dominance | Overlapping `active_turn_denial` dominates `bonus_action_denial`, `action_bonus_exclusivity`, `specified_action_requirement`, `attack_action_cap`, and offensive impairment. `bonus_action_denial` also dominates overlapping `action_bonus_exclusivity`. |
| Specified Action interaction | `specified_action_requirement` consumes overlapping all-attacks impairment on the same target-turn exposure instead of charging both at full value. |
| Attack impairment | All-attacks impairment dominates next-attack impairment only when maintained source-overlap metadata identifies the same attack share. An unrelated next-attack effect survives. |
| Save impairment | For the same save ability, `save_auto_failure` dominates `save_disadvantage`, `flat_save_roll_penalty`, and `finite_next_save_roll_penalty`. Impairment of a different save ability survives. |
| Movement dominance | `turn_movement_denial` dominates overlapping `mobility_loss_feet`, `speed_multiplier`, and `standing_movement_cost`. |
| Correlated flat mobility | Only explicit same-window correlation metadata invokes the target-specific complete-movement cap; unrelated flat reductions are not implicitly capped or merged. |
| Partial overlap | When a stronger effect covers only part of the weaker effect's active exposure, the residual weaker exposure is preserved. |
| Unrelated consequences | Unrelated surviving primitives add independently. |

### Control Reliability — delivery diagnostic

**Secondary diagnostic:** how reliably the Value-selected control package lands and, where applicable, persists. Control Reliability asks: “How reliably is that selected package delivered?”

Configured Reliability metric: **roster-adjusted whole-package control stick %**.

Control Reliability measures delivery probability for the same CU-selected package, not effect severity. It includes legal repeatable attack-delivered opportunities within one ordinary Attack action when the rules permit them, excludes Action Surge from the headline control comparison, and applies the maintained repeat-save and persistence treatment where relevant.

A cell such as `HOT (+46.97%)` does **not** mean a 46.97% chance to apply control. The percentage is the signed distance outside the nearest Battle Master / Eldritch Knight Reliability comparator boundary. `IDEAL` means the raw value falls within that comparator envelope. `COLD` and `HOT` describe relative comparator position, not an absolute real-play balance verdict.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | HOT (+46.97%) | COLD (-100.00%) | HOT (+41.81%) | HOT (+46.97%) |
| 11 | HOT (+14.49%) | COLD (-100.00%) | IDEAL | HOT (+5.32%) |
| 15 | HOT (+8.81%) | HOT (+5.71%) | HOT (+6.75%) | COLD (-3.09%) |
| 20 | HOT (+34.32%) | HOT (+14.81%) | HOT (+17.36%) | COLD (-13.92%) |

### Kinetic Vanguard mean Reliability

This companion table shows the raw Kinetic Vanguard whole-package stick probability reconstructed from the same common CU-selected winner audit. The band percentage above is comparator distance, not this raw application probability.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | 96.23% | 0.00% | 92.85% | 96.23% |
| 11 | 91.04% | 0.00% | 78.52% | 83.75% |
| 15 | 83.05% | 80.68% | 81.47% | 72.56% |
| 20 | 99.97% | 85.45% | 87.35% | 57.19% |

### Why Control Value and Reliability can disagree

Control Value asks: “How much mechanically useful control does the selected package deliver?” Reliability asks: “How often does that same selected package land and persist?” Both readouts use the same CU-selected package.

Sap can be very reliable because legal repeated attack opportunities can give a next-attack Disadvantage rider multiple chances to land. Its priced consequence is still only one impaired attack, so its Control Value remains small. Restrained- and Stunned-style control affects much more of a target's turn, movement, attacks, defenses, saves, or reactions, so one successful application can carry substantially more Control Value even when it is less reliable.

**High Reliability + low Value** means soft control that lands consistently. **Lower Reliability + high Value** means harder control that is less dependable but more consequential when it lands. High Reliability alone is not evidence that a feature is too strong, and low Value alone is not evidence that delivery is poor.

### Control methodology

Normalization prevents double counting. Identical boolean consequences do not stack. Complete turn denial suppresses overlapping lesser action or offensive effects; automatic save failure supersedes weaker impairment to the same save; and complete movement denial supersedes overlapping lesser mobility loss. All-attacks Disadvantage suppresses only an explicitly overlapping next-attack Disadvantage share. Correlated flat movement reductions are capped at complete movement denial, while unrelated mechanical consequences remain independently valued.

Some mechanics require battlefield or opportunity facts that this benchmark cannot neutrally establish, such as geometry-dependent restrictions, sight or sense interactions, cliffs or hazards, unspecified ally opportunities, and open-ended behavioral effects. They remain visible in detailed diagnostics but contribute zero CU unless the required context is explicitly established. Zero Control Value from missing context does **not** mean that a mechanic has no value in actual play.

Kinetic Vanguard mechanics come from [`KineticVanguard.yaml`](KineticVanguard.yaml). Full methodology and reproducibility details are in the [maintained harness guide](harness/README.md), [benchmark configuration](harness/config/benchmark.json), [frozen Control Value configuration](harness/config/control-value.json), [control primitive catalog](harness/data/control_primitives.json), and [comparator assumptions](harness/comparators/fighter-subclasses.json).

Creature benchmark data is SRD 5.2.1. Maintained comparator mechanics are independently expressed analytical abstractions under the reviewed comparator source policy; they are not Kinetic Vanguard rules. Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document. See [`LICENSE.md`](LICENSE.md) for component boundaries and [`NOTICE.md`](NOTICE.md) for attribution and notices.
<!-- END GENERATED BALANCE MATRICES -->

## Publication interface

Opening the publication without a deep link shows **Start Here**, which introduces the subclass’s basic loop and directs players to the appropriate canonical surface. The persistent navigation separates the **Calculator / Feature Deck** for individual playable features from the **Rules Reference** for shared subclass systems and chassis material.

The Calculator / Feature Deck provides one compact, rules-area-grouped index of every individual feature. Each selected card shows identity and availability facts plus its complete canonical feature text. Cards with useful level- or modifier-driven values show deterministic calculations; qualitative cards remain complete reference-only cards without fabricated math. Manifested Strike remains the default calculation experience, with dedicated calculated utility cards for its level-aware Holdout Option and for Blood Tax with eligible Overload Mastery reductions and conditional Overload Mastery II context.

The Rules Reference retains shared material such as How to Play, Example Play, progression tables, the Psionic Discipline and signature-save framework, Psi Reservoir, Manifested Strike procedure, Overload, Signature Riders, and Kinetic Mastery. It provides:

- Category and Topic browsing;
- a canonical Name selector;
- global classification filters with stable ordering and history restoration;
- local Show and Level filters in the Subclass Feature Reference;
- responsive desktop, tablet, mobile, and print layouts;
- keyboard, focus, forced-colors, and reduced-motion support.

Deck cards, Name selections, filtered results, Start Here links, and legacy individual-feature fragments converge on deterministic Calculator deep links. Shared-system selections remain in Rules Reference. Fighter Level and Psionic Ability Modifier are native controls, future-level cards remain visible, and every selection updates the displayed calculations immediately. Longform calculations use full term names, parenthesized component values, `+` operators, and an `=` result matching the retained compact total.

The browser application makes no runtime network requests, does not store character state, and does not replace the rules with inferred behavior.

## Commands

Development uses Node.js `24.18.1` and npm `11.16.0`.

```text
npm ci
npm run typecheck
npm run validate
npm test
npm run build
npm run test:determinism
npm run test:layout
npm run harness:validate
npm run test:harness
npm run readme:benchmarks:check
npm run review:ready
```

Optional full-roster commands are `npm run harness:damage -- --output-dir harness/results/damage` and `npm run harness:control -- --output-dir harness/results/control`. Generated results are ignored. See `harness/README.md` for current methodology, provenance, and matrix interpretation.
`npm run review:ready` waits for the current PR's CI gate, revalidates its exact head, then runs Claude and Grok through `tools/external_review.py` and posts their reviews. Finding disposition and merge remain manual.
`npm run build` writes the development publication to `artifacts/KineticVanguard.prototype.html`. It always carries a visible and accessibility-exposed `NON-RELEASE PROTOTYPE` identity.


A release-profile build is run when preparing a release, not on every pull request:

```text
KV_RELEASE_APPROVED=1 npm run build:release
```

It writes `artifacts/KineticVanguard.html` with `release_status: release` and no prototype banner. The generated publication exposes the canonical rules version as its sole product version.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation, classification, authority-coverage, route, text, filtered-search integrity, and release-identity checks, constructs immutable projections, and emits one release or prototype HTML publication. Failed integrity or coverage checks stop the build rather than producing ceremonial report files.

The top-level onboarding authority is canonical and validated but remains outside the 44 publishable rules entities, Name index, classification results, and progression order.

The maintained Python harnesses consume a deterministic runtime projection emitted by the existing TypeScript YAML loader and semantic validator. Kinetic Vanguard mechanics remain exclusively in YAML; project-authored methodology remains in `harness/config/`; minimal BM/EK third-party comparator parameters remain isolated in `harness/comparators/`; and pinned SRD roster data remains in `harness/data/`.

## Licensing

Kinetic Vanguard uses component-based licensing:

- project-authored software and technical implementation: BSD 3-Clause;
- original Kinetic Vanguard rules, examples, explanatory/editorial prose, and documentation: CC BY-NC-SA 4.0;
- SRD 5.2.1-derived material: CC BY 4.0.

The NonCommercial and ShareAlike terms do not restrict or relicense SRD-derived material. Mixed YAML, configuration, test fixtures, generated HTML, and benchmark reports retain their component-level boundaries; they do not receive a misleading single SPDX license. See `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, `NOTICE.md`, and `docs/licensing-audit.md`.

Battle Master and Eldritch Knight are unofficial third-party comparative benchmarks, not project rules content. Project licenses cover the independently authored benchmark code, structure, and selection—not Wizards-owned names or underlying non-SRD material—and do not imply affiliation or endorsement.

## Development and release discipline

Changes reach `main` through pull requests. GitHub requires the single `Main branch gate` check. Full benchmarks and release checks are run when relevant, following `RELEASE_CHECKLIST.md` for actual release and publication work.

Frozen release branches and annotated release tags remain historical records.

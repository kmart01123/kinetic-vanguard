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

**Primary control-balance metric:** how much useful control the configured package delivers. Control Value asks: “How much useful control does the configured package deliver?”

Control Value combines delivery probability, persistence or active windows, established attack/save/reaction opportunities, mechanical consequences, and legal repeatable accumulating instantaneous effects. `1.0 CU` is denial of one target's normal Action + Bonus Action for one scored target-turn window. A Control Unit is a project analytical benchmark unit, **not a D&D rules quantity**.

For each target, build, and discipline, the benchmark filters out ineligible packages and selects the legal package with the highest Control Value. An exact CU tie is resolved by higher whole-package Control Reliability, then by ascending stable scenario ID. Control Value reports what that selected package delivers mechanically; CU is the common package-selection methodology for both readouts.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | IDEAL | COLD (-100.00%) | IDEAL | COLD (-34.91%) |
| 11 | IDEAL | COLD (-100.00%) | IDEAL | IDEAL |
| 15 | IDEAL | IDEAL | IDEAL | IDEAL |
| 20 | IDEAL | IDEAL | IDEAL | IDEAL |

### Control Reliability — delivery diagnostic

**Secondary diagnostic:** how reliably the Value-selected control package lands and, where applicable, persists. Control Reliability asks: “How reliably is that selected package delivered?”

Configured Reliability metric: **roster-adjusted whole-package control stick %**.

Control Reliability measures delivery probability for the same CU-selected package, not effect severity. It includes legal repeatable attack-delivered opportunities within one ordinary Attack action when the rules permit them, excludes Action Surge from the headline control comparison, and applies the maintained repeat-save and persistence treatment where relevant. A Reliability `HOT` result means unusually high delivery relative to the Reliability comparator envelope; it does not by itself mean that the control's mechanical severity is excessive.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | HOT (+46.97%) | COLD (-100.00%) | HOT (+41.81%) | HOT (+46.97%) |
| 11 | HOT (+14.49%) | COLD (-100.00%) | IDEAL | HOT (+5.32%) |
| 15 | HOT (+8.81%) | HOT (+5.71%) | HOT (+6.75%) | COLD (-3.09%) |
| 20 | HOT (+34.32%) | HOT (+14.81%) | HOT (+17.36%) | COLD (-13.92%) |

### Control methodology

Control Value follows a transparent pipeline: canonical condition or outcome → mechanical consequences → expected exposure or opportunities → overlap normalization → weighted Control Units. It prices what an effect mechanically does rather than assigning value only from its name.

For example, Stunned decomposes into active-turn denial through Incapacitated, reaction denial, automatic failure of Strength and Dexterity saves, and Advantage on incoming attacks. Stunned does **not** gain Speed 0. Restrained includes complete movement denial plus its separately scored consequences. Forced movement is valued from expected displaced feet, and repeatable legal displacement can accrue multiple successful occurrences.

Value and Reliability can still receive different public bands because they measure different properties of the same selected package. A consequence-aware Value readout can differ from delivery: a soft effect such as Sap can land very reliably without carrying the same mechanical consequence as Stunned or Restrained. Equal stick probabilities do not imply equal control power.

Normalization prevents double counting. Identical boolean consequences do not stack. Complete turn denial suppresses overlapping lesser action or offensive effects; automatic save failure supersedes weaker impairment to the same save; and complete movement denial supersedes overlapping lesser mobility loss. All-attacks Disadvantage suppresses only an explicitly overlapping next-attack Disadvantage share. Correlated flat movement reductions are capped at complete movement denial, while unrelated mechanical consequences remain independently valued.

Some mechanics require battlefield or opportunity facts that this benchmark cannot neutrally establish, such as geometry-dependent restrictions, sight or sense interactions, cliffs or hazards, unspecified ally opportunities, and open-ended behavioral effects. They remain visible in detailed diagnostics but contribute zero CU unless the required context is explicitly established. Zero Control Value from missing context does **not** mean that a mechanic has no value in actual play.

Speed 0 is complete turn movement denial. Flat Speed reductions normalize against the target's maintained unconditional locomotion Speed; conditional or choice movement modes are not assumed, and missing trustworthy movement data fails closed. Forced displacement uses expected feet moved.

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

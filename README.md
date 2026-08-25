# Kinetic Vanguard rules reference

Kinetic Vanguard is a schema-first, deterministic rules publication for a Fighter subclass based on System Reference Document 5.2.1 material. The complete player-facing publication is generated as one self-contained, offline-capable HTML file.

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, mechanics, metadata, tables, examples, and onboarding content are authored there and validated before publication. The README summarizes the project and contributor workflow; it is not a second rules source.

## Release status

- Published rules: **[v14.2.0](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.2.0)**
- Current development prototype: **[v14.3.0](https://kmart01123.github.io/kinetic-vanguard/)** — **NON-RELEASE development build**
- Canonical rules authority: `KineticVanguard.yaml`

Published releases use frozen `release/X.Y.Z` branches and annotated `vX.Y.Z` tags.

Version 14.0.0 introduced the deterministic offline Calculator, advanced the authority schema to 2.0.0 for semantic rule and example structure, made Barrier require Concentration at Tier 0 and Tier 1, aligned Explosion/Implosion Tier 1 geometry, and made the canonical rules version the publication’s sole product version. Detailed changes belong in `CHANGELOG.md` and the generated publication rather than being duplicated here.

Version 14.1.0 restores maintained damage and control benchmark harness source. The harnesses use the same validated canonical mechanics as the Calculator where their needs overlap, retain Battle Master and Eldritch Knight as the primary comparators, and produce versioned CSV, Markdown, and self-contained HTML matrices. Benchmark tooling remains developer-only and is not part of the player-facing Calculator.

<!-- BEGIN GENERATED BALANCE MATRICES -->
## Balance benchmark snapshot

**Unreleased development snapshot** — canonical rules **v14.3.0**; current published release **v14.2.0**.

Target profile: `headline`. The maintained headline benchmark uses 47 creature profiles from SRD 5.2.1 at levels 7, 11, 15, and 20. These are exact analytical full-roster results, with creatures weighted equally within their level.

Battle Master and Eldritch Knight define the comparison envelope for the front-door Single-Target Damage result. `IDEAL` means Kinetic Vanguard falls between the two comparator values, inclusive. `COLD` is below both; `HOT` is above both. The percentage on COLD and HOT cells shows the signed distance outside the nearest comparator boundary. `N/A` is reserved for a comparison that cannot be evaluated. This is a comparator-envelope benchmark, not a universal real-play balance tolerance, and `IDEAL` is not proof of balance in every game.

Front-door damage comparator-table cells contain only the public balance classification: `IDEAL`, `COLD (-X%)`, `HOT (+X%)`, or `N/A`. Detailed damage evidence retains raw Kinetic Vanguard and comparator aggregates, dynamic boundaries, and the comparator identity supplying each boundary.

The front-door damage view is the single-target benchmark: primary-target DPR at cluster size 1. All other primary-target and aggregate-cluster results remain in the generated detailed release reports and are not collapsed into this table.

### Single-Target Damage

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | COLD (-6.99%) | IDEAL | COLD (-2.61%) | IDEAL |
| 11 | COLD (-19.47%) | IDEAL | COLD (-0.20%) | IDEAL |
| 15 | COLD (-18.10%) | IDEAL | IDEAL | COLD (-6.75%) |
| 20 | COLD (-41.52%) | COLD (-12.76%) | COLD (-14.95%) | COLD (-26.58%) |

**Fighter 20 note:** [Why the current v14.3 snapshot is COLD at level 20](https://github.com/kmart01123/kinetic-vanguard/issues/122#issuecomment-5389467514)

### Control benchmark

Control Value and Control Reliability require more context than the front-door damage check. The exhaustive exact-form results, effective coverage, Control Unit methodology, and Reliability analysis are maintained in:

[Full control benchmark, catalog, and methodology](CONTROL_BENCHMARK_DETAIL.md)

<!-- END GENERATED BALANCE MATRICES -->

## Publication interface

Opening the publication without a deep link shows **Start Here**, which introduces the subclass’s basic loop and directs players to the appropriate canonical surface. The persistent navigation separates the **Calculator / Feature Deck** for individual playable features from the **Rules Reference** for shared subclass systems and chassis material.

The Calculator / Feature Deck provides one compact, rules-area-grouped index of every individual feature. Each selected card shows identity and availability facts plus its complete canonical feature text. Cards with useful level- or modifier-driven values show deterministic calculations; qualitative cards remain complete reference-only cards without fabricated math. Manifested Strike remains the default calculation experience, with dedicated calculated utility cards for its level-aware Holdout Option and for Blood Tax with eligible Overload Mastery reductions and conditional Overload Mastery II context.

The Rules Reference retains shared material such as How to Play, Example Play, progression tables, the Psionic Discipline and signature-save framework, Psi Reservoir, Manifested Strike procedure, Overload, Signature Riders, and Kinetic Mastery. It provides:

- direct Topic navigation for the authority-derived shared/core inventory;
- a canonical Name selector that routes individual features to Calculator and shared/system names to Rules Reference;
- local Show and Level controls for the 34-row Subclass Feature Reference table;
- responsive desktop, tablet, mobile, and print layouts;
- keyboard, focus, forced-colors, and reduced-motion support.

Deck cards, Name selections, Start Here links, and legacy individual-feature fragments converge on deterministic Calculator deep links. Shared-system selections remain in Rules Reference. Legacy `filters=` fragments safely canonicalize without obsolete state. Fighter Level and Psionic Ability Modifier are native controls, future-level cards remain visible, and every selection updates the displayed calculations immediately. Longform calculations use full term names, parenthesized component values, `+` operators, and an `=` result matching the retained compact total.

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

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation, classification, authority-coverage, route, text, Name-navigation integrity, and release-identity checks, constructs immutable projections, and emits one release or prototype HTML publication. Failed integrity or coverage checks stop the build rather than producing ceremonial report files.

The top-level onboarding authority is canonical and validated but remains outside the 44 publishable rules entities, Name index, and Rules Reference topic inventory.

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

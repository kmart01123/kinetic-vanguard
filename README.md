# Kinetic Vanguard rules reference

Kinetic Vanguard is a schema-first, deterministic rules publication for a Fighter subclass based on System Reference Document 5.2.1 material. The complete player-facing publication is generated as one self-contained, offline-capable HTML file.

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, mechanics, metadata, tables, examples, and onboarding content are authored there and validated before publication. The README summarizes the project and contributor workflow; it is not a second rules source.

## Release status

- Current published release: **v14.1.0**
- Current development line: **v14.2.0**
- Development branch: `14.2.0`
- Implementation status: Active v14.2 development
- Canonical rules authority: `KineticVanguard.yaml`

Published releases use frozen `release/X.Y.Z` branches and annotated `vX.Y.Z` tags. The current published release is available from the [v14.1.0 GitHub Release](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.1.0).

Version 14.0.0 introduced the deterministic offline Calculator, advanced the authority schema to 2.0.0 for semantic rule and example structure, made Barrier require Concentration at Tier 0 and Tier 1, aligned Explosion/Implosion Tier 1 geometry, and made the canonical rules version the publication’s sole product version. Detailed changes belong in `CHANGELOG.md` and the generated publication rather than being duplicated here.

Version 14.1.0 restores maintained damage and control benchmark harness source. The harnesses use the same validated canonical mechanics as the Calculator where their needs overlap, retain Battle Master and Eldritch Knight as the primary comparators, and produce versioned CSV, Markdown, and self-contained HTML matrices. Benchmark tooling remains developer-only and is not part of the player-facing Calculator.

<!-- BEGIN GENERATED BALANCE MATRICES -->
## Balance benchmark snapshot

**Unreleased development snapshot** — canonical rules **v14.2.0**; current published release **v14.1.0**.

Profile: `official_default_25_percent_hp`. Numerical review status: `REVIEWED_WITH_DOCUMENTED_DIFFERENCES`. These are exact analytical full-roster results, not Monte Carlo estimates.

Battle Master and Eldritch Knight define the comparison envelope for each benchmark result. `IDEAL` means Kinetic Vanguard falls between the two comparator results, inclusive. `COLD` is below both; `HOT` is above both. The percentage on COLD and HOT cells shows the signed distance outside the nearest envelope boundary. `N/A` is reserved for a comparison that cannot be evaluated.

README cells intentionally contain only the public balance result: `IDEAL`, `COLD (-X%)`, `HOT (+X%)`, or `N/A`. Detailed release CSV, Markdown, and HTML reports retain raw Kinetic Vanguard and comparator aggregates, ordinary KV/comparator ratios, dynamic lower and upper boundaries, and the comparator identity supplying each boundary.

The front-door damage view is the single-target benchmark: primary-target DPR at cluster size 1. All other primary-target and aggregate-cluster results remain in the generated detailed release reports and are not collapsed into this table.

### Single-Target Damage

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | IDEAL | IDEAL | IDEAL | IDEAL |
| 11 | COLD (-9.75%) | IDEAL | IDEAL | IDEAL |
| 15 | IDEAL | IDEAL | IDEAL | IDEAL |
| 20 | COLD (-40.35%) | IDEAL | COLD (-9.30%) | COLD (-12.84%) |

### Control Reliability

This single-target benchmark evaluates each configured control package against one roster target at a time before taking the equal-weight roster mean.

Configured headline metric: **roster-adjusted whole-package control stick %**.

This v14.2 snapshot evaluates legal repeated attack-delivered opportunities within one ordinary Attack action when the configured package permits them. Kinetic Vanguard Signature Riders were already 0-Psi and repeatable before issue #58; issue #58 newly extends that repeatability to paid on-hit riders. Battle Master maneuvers receive legal hit-gated retries, while Eldritch Knight keeps one Blindness/Deafness cast and uses all ordinary primer attacks for Eldritch Strike. Published v14.1 used simpler one-shot approximations, so control deltas can combine the paid-rider rule with historical KV, Battle Master, and Eldritch Knight evaluator corrections. Those effects interact and are not assumed to be additively separable.

Control Reliability measures how often the configured control package takes effect. It does not measure the relative severity, duration, area, or strategic value of different control effects. A HOT result is a balance-review signal, not an automatic finding that the feature is overpowered.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | HOT (+32.13%) | COLD (-100.00%) | HOT (+5.74%) | HOT (+11.29%) |
| 11 | HOT (+17.89%) | COLD (-100.00%) | HOT (+13.79%) | IDEAL |
| 15 | HOT (+21.16%) | HOT (+21.16%) | HOT (+21.89%) | HOT (+10.72%) |
| 20 | HOT (+22.60%) | HOT (+22.08%) | HOT (+22.60%) | IDEAL |

This snapshot is a summary, not the full evidence set. Kinetic Vanguard mechanics come from [`KineticVanguard.yaml`](KineticVanguard.yaml). See the [maintained harness guide](harness/README.md), [methodology configuration](harness/config/benchmark.json), [SRD creature profiles](harness/data/srd_creature_rosters.json), and [comparator assumptions](harness/comparators/fighter-subclasses.json) for the complete methodology, provenance, regeneration commands, and report paths.

Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document. See [`LICENSE.md`](LICENSE.md) for component boundaries and [`NOTICE.md`](NOTICE.md) for attribution and notices.
<!-- END GENERATED BALANCE MATRICES -->

## Publication interface

Opening the publication without a deep link shows **Start Here**, which introduces the subclass’s basic loop and directs players to the appropriate canonical surface. The persistent navigation separates the **Calculator / Feature Deck** for individual playable features from the **Rules Reference** for shared subclass systems and chassis material.

The Calculator / Feature Deck provides one compact, rules-area-grouped index of every individual feature. Each selected card shows identity and availability facts plus its complete canonical feature text. Cards with useful level- or modifier-driven values show deterministic calculations; qualitative cards remain complete reference-only cards without fabricated math. Manifested Strike remains the default calculation experience, and Blood Tax has a dedicated calculated utility card with eligible Overload Mastery reductions and conditional Overload Mastery II context.

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
```

Optional full-roster commands are `npm run harness:damage -- --output-dir harness/results/damage` and `npm run harness:control -- --output-dir harness/results/control`. Generated results are ignored. See `harness/README.md` for methodology, provenance, matrix interpretation, and current numerical-review status.
`npm run build` writes the development publication to `artifacts/KineticVanguard.prototype.html`. It always carries a visible and accessibility-exposed `NON-RELEASE PROTOTYPE` identity.


A release-profile build is run when preparing a release, not on every pull request:

```text
KV_RELEASE_APPROVED=1 npm run build:release
```

It writes `artifacts/KineticVanguard.html` with `release_status: release` and no prototype banner. The generated publication exposes the canonical rules version as its sole product version.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation, classification, authority-coverage, route, text, and release-identity checks, constructs immutable projections, and emits:

- release or prototype HTML;
- a filtered-search integrity report;
- a YAML entity-to-route coverage ledger;
- a deterministic build manifest.

The top-level onboarding authority is canonical and validated but remains outside the 44 publishable rules entities, Name index, classification results, and progression order.

The completed one-time Markdown migration has been retired. Contributors edit `KineticVanguard.yaml` directly; there is no Markdown synchronization step.

The maintained Python harnesses consume a deterministic runtime projection emitted by the existing TypeScript YAML loader and semantic validator. Kinetic Vanguard mechanics remain exclusively in YAML; project-authored methodology remains in `harness/config/`; minimal BM/EK third-party comparator parameters remain isolated in `harness/comparators/`; and pinned SRD roster data remains in `harness/data/`.

## Licensing

Kinetic Vanguard uses component-based licensing:

- project-authored software and technical implementation: BSD 3-Clause;
- original Kinetic Vanguard rules, examples, explanatory/editorial prose, and documentation: CC BY-NC-SA 4.0;
- SRD 5.2.1-derived material: CC BY 4.0.

The NonCommercial and ShareAlike terms do not restrict or relicense SRD-derived material. Mixed YAML, configuration, test fixtures, generated HTML, manifests, and benchmark reports retain their component-level boundaries; they do not receive a misleading single SPDX license. See `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, `NOTICE.md`, and `docs/licensing-audit.md`.

Battle Master and Eldritch Knight are unofficial third-party comparative benchmarks, not project rules content. Project licenses cover the independently authored benchmark code, structure, and selection—not Wizards-owned names or underlying non-SRD material—and do not imply affiliation or endorsement.

## Development and release discipline

Changes reach `main` through pull requests. GitHub requires the single `Main branch gate` check. Full benchmarks and release checks are run when relevant, following `RELEASE_CHECKLIST.md` for actual release and publication work.

Frozen release branches and annotated release tags remain historical records.

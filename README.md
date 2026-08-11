# Kinetic Vanguard rules reference

Kinetic Vanguard is a schema-first, deterministic rules publication for a Fighter subclass based on System Reference Document 5.2.1 material. The complete player-facing publication is generated as one self-contained, offline-capable HTML file.

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, mechanics, metadata, tables, examples, and onboarding content are authored there and validated before publication. The README summarizes the project and contributor workflow; it is not a second rules source.

## Release status

- Current published release: **v14.1.0**
- Current development line: **v14.2.0**
- Canonical rules authority: `KineticVanguard.yaml`

Published releases use frozen `release/X.Y.Z` branches and annotated `vX.Y.Z` tags. The current published release is available from the [v14.1.0 GitHub Release](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.1.0).

Version 14.0.0 introduced the deterministic offline Calculator, advanced the authority schema to 2.0.0 for semantic rule and example structure, made Barrier require Concentration at Tier 0 and Tier 1, aligned Explosion/Implosion Tier 1 geometry, and made the canonical rules version the publication’s sole product version. Detailed changes belong in `CHANGELOG.md` and the generated publication rather than being duplicated here.

Version 14.1.0 restored damage and Control Reliability benchmark evidence. Those frozen results remain reproducible from the release, tag, release branch, evidence assets, and Git history.

Version 14.2.0 development retires the superseded Control Reliability implementation from current `main`. One authoritative SRD 5.2.1 creature catalog now feeds separate source-only roster profiles and thin damage/control projections; the old CSV and control supplement are retired. The maintained damage benchmark has an explicit damage-authority boundary, while Control Authority v2 remains separate infrastructure for the redesign work and does not publish a current control result.

<!-- BEGIN GENERATED DAMAGE MATRIX -->
## Damage benchmark snapshot

**Current canonical damage authority:** rules **v14.2.0**.

Kinetic Vanguard profile: `official_default_25_percent_hp`.

Target profile: `srd521_headline_source_diversity_v1` (47 source-ordered targets).

A fresh exact analytical run for **v14.2.0** used all 47 targets in `srd521_headline_source_diversity_v1`. It replaces the carried-forward snapshot, while the independently reviewed rules **v14.1.0** evidence remains the review basis (`REVIEWED_WITH_DOCUMENTED_DIFFERENCES`). No fresh independent numerical or Monte Carlo certification is claimed. Run-manifest SHA-256: `a6ad2a6ca1b56c08ce95668f0825d2959d7b8f3ea8dd2f10b498d3536a25e1b8`.

Battle Master and Eldritch Knight define the comparison envelope. `IDEAL` means Kinetic Vanguard falls between the two damage results, inclusive. `COLD` is below both; `HOT` is above both. The percentage on COLD and HOT cells is the signed distance outside the nearest envelope boundary. `N/A` is reserved for a comparison that cannot be evaluated.

This single-target view is primary-target DPR at cluster size 1. README cells contain only the public damage result. Generated detailed analytical CSV, Markdown, and HTML reports retain raw aggregates, ratios, boundaries, classifications, and provenance; all other primary-target and aggregate-cluster results remain in those reports.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | IDEAL | IDEAL | IDEAL | IDEAL |
| 11 | COLD (-18.76%) | IDEAL | IDEAL | IDEAL |
| 15 | COLD (-5.70%) | IDEAL | IDEAL | COLD (-6.12%) |
| 20 | COLD (-35.69%) | IDEAL | COLD (-14.10%) | COLD (-15.70%) |

Kinetic Vanguard mechanics come from [`KineticVanguard.yaml`](KineticVanguard.yaml). See the [maintained damage harness guide](harness/README.md), [methodology configuration](harness/config/benchmark.json), [SRD creature catalog audit](docs/srd-creature-catalog-audit.md), and [comparator assumptions](harness/comparators/fighter-subclasses.json).

Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document. See [`LICENSE.md`](LICENSE.md) for component boundaries and [`NOTICE.md`](NOTICE.md) for attribution and notices.
<!-- END GENERATED DAMAGE MATRIX -->

## Control methodology status

The v14.1 **Control Reliability** benchmark is historical release evidence, not maintained current-development methodology. Its reproducible outputs remain permanently available with the [v14.1.0 GitHub Release](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.1.0), frozen release branch and tag, evidence assets, and Git history.

The v14.2 control methodology is being redesigned under [#32](https://github.com/kmart01123/kinetic-vanguard/issues/32) and issues #39–#42: [#39](https://github.com/kmart01123/kinetic-vanguard/issues/39), [#40](https://github.com/kmart01123/kinetic-vanguard/issues/40), [#41](https://github.com/kmart01123/kinetic-vanguard/issues/41), and [#42](https://github.com/kmart01123/kinetic-vanguard/issues/42). No v14.2 control headline, matrix, or HOT/IDEAL/COLD classification is authoritative until #42 promotes the replacement methodology.

## Publication interface

Opening the publication without a deep link shows **Start Here**, which introduces the subclass’s basic loop and links into the canonical rules. Existing category, topic, entity, and filter deep links continue to open the complete Rules Reference directly. The persistent publication navigation also includes a **Calculator** view.

The Rules Reference provides:

- Category and Topic browsing;
- a canonical Name selector;
- global classification filters with stable ordering and history restoration;
- local Show and Level filters in the Subclass Feature Reference;
- responsive desktop, tablet, mobile, and print layouts;
- keyboard, focus, forced-colors, and reduced-motion support.

The Calculator opens on a dedicated Manifested Strike landing card and derives its attack, damage, and save Difficulty Class, along with total Psi Points, Psi costs, on-hit rider tier results, and supported standalone feature tier results, from Feature Group, Skill / Feature, Fighter Level, and Psionic Ability Modifier selections. Feature Group scopes the supported choices to a discipline or Advanced Training without changing any calculations. Longform hit, damage, and saving throw calculations use full term names, parenthesized component values, `+` operators, and an `=` result matching the retained compact total. Every selection updates the displayed calculations immediately.

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
npm run readme:damage:check -- --report-input /path/to/final-run/run-manifest.json
```

The optional full-roster command is `npm run harness:damage -- --output-dir harness/results/damage`. It writes a provenance-bearing run manifest beside generated outputs. Reuse that exact manifest with `npm run readme:damage -- --report-input ...` and the check command; neither README command reruns the evaluator. Generated results are ignored. See `harness/README.md` for methodology, provenance, damage-matrix interpretation, and the distinction between current authority and its durable numerical-review basis.
`npm run build` writes the development publication to `artifacts/KineticVanguard.prototype.html`. It always carries a visible and accessibility-exposed `NON-RELEASE PROTOTYPE` identity.


An authorized release build uses:

```text
KV_RELEASE_APPROVED=1 npm run build:release
```

It writes `artifacts/KineticVanguard.html` with `release_status: release` and no prototype banner. CI derives workflow labels and the `kinetic-vanguard-v<rules_version>` artifact name from the canonical `rules_version`; the generated publication exposes that canonical rules version as its sole product version.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation, classification, authority-coverage, route, text, and release-identity checks, constructs immutable projections, and emits:

- release or prototype HTML;
- a filtered-search integrity report;
- a YAML entity-to-route coverage ledger;
- a deterministic build manifest.

The top-level onboarding authority is canonical and validated but remains outside the 44 publishable rules entities, Name index, classification results, and progression order.

The completed one-time Markdown migration has been retired. Contributors edit `KineticVanguard.yaml` directly; there is no Markdown synchronization step.

The maintained Python damage harness consumes `DamageHarnessProjection`, emitted by the TypeScript YAML loader and semantic validator through `createDamageHarnessProjection`, and loads it through Python's `DamageAuthorityModel`. Kinetic Vanguard mechanics remain exclusively in YAML; project-authored damage methodology remains in `harness/config/`; minimal BM/EK damage comparator parameters remain isolated in `harness/comparators/`; and the shared SRD creature catalog, complete accounting, and roster profiles remain in `harness/data/`. Python owns creature semantics and thin target projections; TypeScript performs only cheap catalog shape/digest/manifest validation.

Control Authority v2 is a separate, fail-closed structured authority contract with shared TypeScript/Python parity coverage. It is preserved for the redesign sequence, but it is not part of the damage projection and does not evaluate or publish a v14.2 control result.

## Licensing

Kinetic Vanguard uses component-based licensing:

- project-authored software and technical implementation: BSD 3-Clause;
- original Kinetic Vanguard rules, examples, explanatory/editorial prose, and documentation: CC BY-NC-SA 4.0;
- SRD 5.2.1-derived material: CC BY 4.0.

The NonCommercial and ShareAlike terms do not restrict or relicense SRD-derived material. Mixed YAML, configuration, test fixtures, generated HTML, manifests, and benchmark reports retain their component-level boundaries; they do not receive a misleading single SPDX license. See `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, `NOTICE.md`, and `docs/licensing-audit.md`.

Battle Master and Eldritch Knight are unofficial third-party comparative benchmarks, not project rules content. Project licenses cover the independently authored benchmark code, structure, and selection—not Wizards-owned names or underlying non-SRD material—and do not imply affiliation or endorsement.

## Development and release discipline

Changes reach `main` through pull requests. The active `Protect main` ruleset requires an up-to-date branch, resolved review conversations, and the stable `Main branch gate`; it blocks force pushes and deletion. Squash merge is the normal merge method.

At the start of every development line, before a release PR leaves draft, and during publication, complete `RELEASE_CHECKLIST.md`. The checklist requires an explicit README review against canonical authority, the changelog, open issues, CI, build outputs, release assets, and current branch-protection settings.

Frozen release branches and annotated release tags are immutable historical references. Publication workflows verify the exact frozen commit before creating or updating a GitHub Release.

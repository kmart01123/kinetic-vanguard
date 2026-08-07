# Kinetic Vanguard rules reference

Kinetic Vanguard is a schema-first, deterministic rules publication for a Fighter subclass based on System Reference Document 5.2.1 material. The complete player-facing publication is generated as one self-contained, offline-capable HTML file.

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, mechanics, metadata, tables, examples, and onboarding content are authored there and validated before publication. The README summarizes the project and contributor workflow; it is not a second rules source.

## Release status

- Current published release: **v14.0.0**
- Current development line: **v14.1.0**
- Development branch: `14.1.0`
- Implementation pull request: [#20 — v14.1: Restore YAML-driven damage and control harnesses](https://github.com/kmart01123/kinetic-vanguard/pull/20), implementing [issue #19](https://github.com/kmart01123/kinetic-vanguard/issues/19)
- Canonical rules authority: `KineticVanguard.yaml`

Published releases use frozen `release/X.Y.Z` branches and annotated `vX.Y.Z` tags. The current published release is available from the [v14.0.0 GitHub Release](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.0.0).

Version 14.0.0 introduced the deterministic offline Calculator, advanced the authority schema to 2.0.0 for semantic rule and example structure, made Barrier require Concentration at Tier 0 and Tier 1, aligned Explosion/Implosion Tier 1 geometry, and made the canonical rules version the publication’s sole product version. Detailed changes belong in `CHANGELOG.md` and the generated publication rather than being duplicated here.

Version 14.1.0 restores maintained damage and control benchmark harness source. The harnesses use the same validated canonical mechanics as the Calculator where their needs overlap, retain Battle Master and Eldritch Knight as the primary comparators, and produce versioned CSV, Markdown, and self-contained HTML matrices. Benchmark tooling remains developer-only and is not part of the player-facing Calculator.

<!-- BEGIN GENERATED BALANCE MATRICES -->
## Balance benchmark snapshot

**Unreleased development snapshot** — canonical rules **v14.1.0**; current published release **v14.0.0**.

Profile: `official_default_25_percent_hp`. Numerical review status: `REVIEWED_WITH_DOCUMENTED_DIFFERENCES`. These are exact analytical full-roster results, not Monte Carlo estimates.

Battle Master and Eldritch Knight are recognizable Fighter-subclass reference points. The comparison asks whether Kinetic Vanguard sits inside a useful martial Fighter balance envelope; it does not predict every table or make unlike control conditions equally valuable.

### Damage benchmark

Values are damage per round (DPR). Slash-separated entries correspond, in order, to cluster sizes **1 / 3 / 6**. Each entry is a separate equal-weight roster mean; the cluster-size results are not averaged together. Comparator DPR is cluster-independent and appears once per row. Primary-target and aggregate-cluster results remain separate.

**Damage band legend** — expected comparator order: Eldritch Knight ≤ Battle Master.

- `COLD`: KV is below Eldritch Knight.
- `IDEAL`: KV is between Eldritch Knight and Battle Master, inclusive.
- `HOT`: KV is above Battle Master.
- `ORDER CHECK`: comparator ordering is reversed for that result.
- `N/A`: a ratio or comparison is not defined.

#### Primary-target DPR

| Fighter level | Discipline | KV DPR (C1 / C3 / C6) | Eldritch Knight DPR | Battle Master DPR | KV as % of EK (C1 / C3 / C6) | KV as % of BM (C1 / C3 / C6) | Band (C1 / C3 / C6) |
|---|---|---|---|---|---|---|---|
| 7 | Cryokinesis | 25.325000 / 25.325000 / 25.325000 | 22.475000 | 46.029865 | 112.68 / 112.68 / 112.68 | 55.02 / 55.02 / 55.02 | IDEAL / IDEAL / IDEAL |
| 7 | Electrokinesis | 25.443750 / 25.443750 / 25.443750 | 22.475000 | 46.029865 | 113.21 / 113.21 / 113.21 | 55.28 / 55.28 / 55.28 | IDEAL / IDEAL / IDEAL |
| 7 | Psychokinesis | 25.325000 / 25.325000 / 25.325000 | 22.475000 | 46.029865 | 112.68 / 112.68 / 112.68 | 55.02 / 55.02 / 55.02 | IDEAL / IDEAL / IDEAL |
| 7 | Pyrokinesis | 30.595833 / 30.595833 / 30.595833 | 22.475000 | 46.029865 | 136.13 / 136.13 / 136.13 | 66.47 / 66.47 / 66.47 | IDEAL / IDEAL / IDEAL |
| 11 | Cryokinesis | 39.091667 / 39.091667 / 39.091667 | 43.313889 | 80.659913 | 90.25 / 90.25 / 90.25 | 48.46 / 48.46 / 48.46 | COLD / COLD / COLD |
| 11 | Electrokinesis | 55.363113 / 55.331563 / 55.331563 | 43.313889 | 80.659913 | 127.82 / 127.75 / 127.75 | 68.64 / 68.60 / 68.60 | IDEAL / IDEAL / IDEAL |
| 11 | Psychokinesis | 43.676250 / 43.547917 / 43.547917 | 43.313889 | 80.659913 | 100.84 / 100.54 / 100.54 | 54.15 / 53.99 / 53.99 | IDEAL / IDEAL / IDEAL |
| 11 | Pyrokinesis | 63.709375 / 63.709375 / 63.709375 | 43.313889 | 80.659913 | 147.09 / 147.09 / 147.09 | 78.99 / 78.99 / 78.99 | IDEAL / IDEAL / IDEAL |
| 15 | Cryokinesis | 53.289207 / 53.289207 / 53.289207 | 51.828005 | 91.953645 | 102.82 / 102.82 / 102.82 | 57.95 / 57.95 / 57.95 | IDEAL / IDEAL / IDEAL |
| 15 | Electrokinesis | 56.575998 / 55.398506 / 54.267062 | 51.828005 | 91.953645 | 109.16 / 106.89 / 104.71 | 61.53 / 60.25 / 59.02 | IDEAL / IDEAL / IDEAL |
| 15 | Psychokinesis | 56.678101 / 56.678101 / 56.236863 | 51.828005 | 91.953645 | 109.36 / 109.36 / 108.51 | 61.64 / 61.64 / 61.16 | IDEAL / IDEAL / IDEAL |
| 15 | Pyrokinesis | 74.093041 / 74.093041 / 74.093041 | 51.828005 | 91.953645 | 142.96 / 142.96 / 142.96 | 80.58 / 80.58 / 80.58 | IDEAL / IDEAL / IDEAL |
| 20 | Cryokinesis | 57.519902 / 52.253227 / 52.253227 | 96.427430 | 153.865850 | 59.65 / 54.19 / 54.19 | 37.38 / 33.96 / 33.96 | COLD / COLD / COLD |
| 20 | Electrokinesis | 82.629068 / 82.362284 / 67.399830 | 96.427430 | 153.865850 | 85.69 / 85.41 / 69.90 | 53.70 / 53.53 / 43.80 | COLD / COLD / COLD |
| 20 | Psychokinesis | 87.458430 / 85.895114 / 85.705260 | 96.427430 | 153.865850 | 90.70 / 89.08 / 88.88 | 56.84 / 55.82 / 55.70 | COLD / COLD / COLD |
| 20 | Pyrokinesis | 101.314635 / 101.314635 / 101.314635 | 96.427430 | 153.865850 | 105.07 / 105.07 / 105.07 | 65.85 / 65.85 / 65.85 | IDEAL / IDEAL / IDEAL |

#### Aggregate cluster DPR

| Fighter level | Discipline | KV DPR (C1 / C3 / C6) | Eldritch Knight DPR | Battle Master DPR | KV as % of EK (C1 / C3 / C6) | KV as % of BM (C1 / C3 / C6) | Band (C1 / C3 / C6) |
|---|---|---|---|---|---|---|---|
| 7 | Cryokinesis | 25.325000 / 25.325000 / 25.325000 | 22.475000 | 46.029865 | 112.68 / 112.68 / 112.68 | 55.02 / 55.02 / 55.02 | IDEAL / IDEAL / IDEAL |
| 7 | Electrokinesis | 25.443750 / 35.683333 / 36.687500 | 22.475000 | 46.029865 | 113.21 / 158.77 / 163.24 | 55.28 / 77.52 / 79.70 | IDEAL / IDEAL / IDEAL |
| 7 | Psychokinesis | 25.325000 / 25.325000 / 25.325000 | 22.475000 | 46.029865 | 112.68 / 112.68 / 112.68 | 55.02 / 55.02 / 55.02 | IDEAL / IDEAL / IDEAL |
| 7 | Pyrokinesis | 30.595833 / 30.595833 / 30.595833 | 22.475000 | 46.029865 | 136.13 / 136.13 / 136.13 | 66.47 / 66.47 / 66.47 | IDEAL / IDEAL / IDEAL |
| 11 | Cryokinesis | 39.091667 / 39.091667 / 39.091667 | 43.313889 | 80.659913 | 90.25 / 90.25 / 90.25 | 48.46 / 48.46 / 48.46 | COLD / COLD / COLD |
| 11 | Electrokinesis | 55.363113 / 87.623854 / 127.856042 | 43.313889 | 80.659913 | 127.82 / 202.30 / 295.18 | 68.64 / 108.63 / 158.51 | IDEAL / HOT / HOT |
| 11 | Psychokinesis | 43.676250 / 47.643750 / 53.787500 | 43.313889 | 80.659913 | 100.84 / 110.00 / 124.18 | 54.15 / 59.07 / 66.68 | IDEAL / IDEAL / IDEAL |
| 11 | Pyrokinesis | 63.709375 / 63.709375 / 63.709375 | 43.313889 | 80.659913 | 147.09 / 147.09 / 147.09 | 78.99 / 78.99 / 78.99 | IDEAL / IDEAL / IDEAL |
| 15 | Cryokinesis | 53.289207 / 139.972228 / 139.972228 | 51.828005 | 91.953645 | 102.82 / 270.07 / 270.07 | 57.95 / 152.22 / 152.22 | IDEAL / HOT / HOT |
| 15 | Electrokinesis | 56.575998 / 102.656618 / 170.851108 | 51.828005 | 91.953645 | 109.16 / 198.07 / 329.65 | 61.53 / 111.64 / 185.80 | IDEAL / HOT / HOT |
| 15 | Psychokinesis | 56.678101 / 56.678101 / 56.875675 | 51.828005 | 91.953645 | 109.36 / 109.36 / 109.74 | 61.64 / 61.64 / 61.85 | IDEAL / IDEAL / IDEAL |
| 15 | Pyrokinesis | 74.093041 / 74.093041 / 74.093041 | 51.828005 | 91.953645 | 142.96 / 142.96 / 142.96 | 80.58 / 80.58 / 80.58 | IDEAL / IDEAL / IDEAL |
| 20 | Cryokinesis | 57.519902 / 100.183306 / 100.183306 | 96.427430 | 153.865850 | 59.65 / 103.90 / 103.90 | 37.38 / 65.11 / 65.11 | COLD / IDEAL / IDEAL |
| 20 | Electrokinesis | 82.629068 / 123.163357 / 181.724899 | 96.427430 | 153.865850 | 85.69 / 127.73 / 188.46 | 53.70 / 80.05 / 118.11 | COLD / IDEAL / HOT |
| 20 | Psychokinesis | 87.458430 / 90.396033 / 97.320374 | 96.427430 | 153.865850 | 90.70 / 93.75 / 100.93 | 56.84 / 58.75 / 63.25 | COLD / COLD / IDEAL |
| 20 | Pyrokinesis | 101.314635 / 101.314635 / 101.314635 | 96.427430 | 153.865850 | 105.07 / 105.07 / 105.07 | 65.85 / 65.85 / 65.85 | IDEAL / IDEAL / IDEAL |

### Control benchmark

Metric: **roster-adjusted whole-package control stick %**. This is a best-available reliability envelope, not DPR or a condition-severity score. Ratios remain ordinary KV/comparator percentages and are not mathematically inverted.

**Control band legend** — expected comparator order: Battle Master ≤ Eldritch Knight.

- `COLD`: KV is below Battle Master.
- `IDEAL`: KV is between Battle Master and Eldritch Knight, inclusive.
- `HOT`: KV is above Eldritch Knight.
- `ORDER CHECK`: comparator ordering is reversed for that result.
- `N/A`: a ratio or comparison is not defined.

| Fighter level | Discipline | KV control % | Eldritch Knight control % | Battle Master control % | KV as % of EK | KV as % of BM | Band |
|---|---|---|---|---|---|---|---|
| 7 | Cryokinesis | 80.625000 | 41.250000 | 48.656250 | 195.45 | 165.70 | ORDER CHECK |
| 7 | Electrokinesis | 80.625000 | 41.250000 | 48.656250 | 195.45 | 165.70 | ORDER CHECK |
| 7 | Psychokinesis | 70.156250 | 41.250000 | 48.656250 | 170.08 | 144.19 | ORDER CHECK |
| 7 | Pyrokinesis | 0.000000 | 41.250000 | 48.656250 | 0.00 | 0.00 | ORDER CHECK |
| 11 | Cryokinesis | 84.166667 | 49.239583 | 47.541667 | 170.93 | 177.04 | HOT |
| 11 | Electrokinesis | 84.166667 | 49.239583 | 47.541667 | 170.93 | 177.04 | HOT |
| 11 | Psychokinesis | 77.500000 | 49.239583 | 47.541667 | 157.39 | 163.01 | HOT |
| 11 | Pyrokinesis | 0.000000 | 49.239583 | 47.541667 | 0.00 | 0.00 | COLD |
| 15 | Cryokinesis | 84.166667 | 58.056250 | 44.625000 | 144.97 | 188.61 | HOT |
| 15 | Electrokinesis | 90.833333 | 58.056250 | 44.625000 | 156.46 | 203.55 | HOT |
| 15 | Psychokinesis | 100.000000 | 58.056250 | 44.625000 | 172.25 | 224.09 | HOT |
| 15 | Pyrokinesis | 84.166667 | 58.056250 | 44.625000 | 144.97 | 188.61 | HOT |
| 20 | Cryokinesis | 100.000000 | 45.943750 | 37.468750 | 217.66 | 266.89 | HOT |
| 20 | Electrokinesis | 81.250000 | 45.943750 | 37.468750 | 176.85 | 216.85 | HOT |
| 20 | Psychokinesis | 100.000000 | 45.943750 | 37.468750 | 217.66 | 266.89 | HOT |
| 20 | Pyrokinesis | 81.250000 | 45.943750 | 37.468750 | 176.85 | 216.85 | HOT |

This snapshot is a summary, not the full evidence set. Kinetic Vanguard mechanics come from [`KineticVanguard.yaml`](KineticVanguard.yaml). See the [maintained harness guide](harness/README.md), [methodology configuration](harness/config/benchmark.json), [SRD target roster](harness/data/srd_targets.csv), and [comparator assumptions](harness/comparators/fighter-subclasses.json) for the complete methodology, provenance, regeneration commands, and report paths.

Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document. See [`LICENSE.md`](LICENSE.md) for component boundaries and [`NOTICE.md`](NOTICE.md) for attribution and notices.
<!-- END GENERATED BALANCE MATRICES -->

## Publication interface

Opening the publication without a deep link shows **Start Here**, which introduces the subclass’s basic loop and links into the canonical rules. Existing category, topic, entity, and filter deep links continue to open the complete Rules Reference directly. The persistent publication navigation also includes a **Calculator** view.

The Rules Reference provides:

- Category and Topic browsing;
- a canonical Name selector;
- global classification filters with stable ordering and history restoration;
- local Show and Level filters in the Subclass Feature Reference;
- responsive desktop, tablet, mobile, and print layouts;
- keyboard, focus, forced-colors, and reduced-motion support.

The Calculator opens with Manifested Strike and derives its attack, damage, and save Difficulty Class, along with total Psi Points, Psi costs, on-hit rider tier results, and supported standalone feature tier results, from Skill / Feature, Fighter Level, and Psionic Ability Modifier selections. Longform hit, damage, and saving throw calculations use full term names, parenthesized component values, `+` operators, and an `=` result matching the retained compact total. Every selection updates the displayed calculations immediately.

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

The maintained Python harnesses consume a deterministic runtime projection emitted by the existing TypeScript YAML loader and semantic validator. Kinetic Vanguard mechanics remain exclusively in YAML; project-authored methodology remains in `harness/config/`; minimal BM/EK third-party comparator parameters remain isolated in `harness/comparators/`; and pinned SRD roster data remains in `harness/data/`.

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

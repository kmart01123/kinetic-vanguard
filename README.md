# Kinetic Vanguard rules reference

Kinetic Vanguard is a schema-first, deterministic rules publication for a Fighter subclass based on System Reference Document 5.2.1 material. The complete player-facing publication is generated as one self-contained, offline-capable HTML file.

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, mechanics, metadata, tables, examples, and onboarding content are authored there and validated before publication. The README summarizes the project and contributor workflow; it is not a second rules source.

## Release status

- Current published release: **v13.1.0**
- Current development line: **v13.2.0**
- Development branch: `13.2.0`
- Draft pull request: [#12](https://github.com/kmart01123/kinetic-vanguard/pull/12)
- Canonical rules authority: `KineticVanguard.yaml`

Published releases use frozen `release/X.Y.Z` branches and annotated `vX.Y.Z` tags. The current published release is available from the [v13.1.0 GitHub Release](https://github.com/kmart01123/kinetic-vanguard/releases/tag/v13.1.0).

Version 13.2.0 adds the new-player **Start Here** experience and revises Mass Levitation to use five target slots with normal falling after a successful repeat save. It also establishes the project’s split licensing and a stable required CI gate for the protected `main` branch. Detailed changes belong in `CHANGELOG.md` and the generated publication rather than being duplicated here.

## Publication interface

Opening the publication without a deep link shows **Start Here**, which introduces the subclass’s basic loop and links into the canonical rules. Existing category, topic, entity, and filter deep links continue to open the complete Rules Reference directly.

The Rules Reference provides:

- Category and Topic browsing;
- a canonical Name selector;
- global classification filters with stable ordering and history restoration;
- local Show and Level filters in the Subclass Feature Reference;
- responsive desktop, tablet, mobile, and print layouts;
- keyboard, focus, forced-colors, and reduced-motion support.

The browser application makes no runtime network requests and does not store character state, run calculators, or replace the rules with inferred behavior.

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
```

`npm run build` writes the development publication to `artifacts/KineticVanguard.prototype.html`. It always carries a visible and accessibility-exposed `NON-RELEASE PROTOTYPE` identity.

An authorized release build uses:

```text
KV_RELEASE_APPROVED=1 npm run build:release
```

It writes `artifacts/KineticVanguard.html` with `release_status: release` and no prototype banner. CI derives workflow labels and the `kinetic-vanguard-v<rules_version>` artifact name from the canonical `rules_version`; there is no separately maintained active artifact version.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation, classification, authority-coverage, route, text, and release-identity checks, constructs immutable projections, and emits:

- release or prototype HTML;
- a filtered-search integrity report;
- a YAML entity-to-route coverage ledger;
- a deterministic build manifest.

The top-level onboarding authority is canonical and validated but remains outside the 44 publishable rules entities, Name index, classification results, and progression order.

The completed one-time Markdown migration has been retired. Contributors edit `KineticVanguard.yaml` directly; there is no Markdown synchronization step.

## Licensing

Kinetic Vanguard uses component-based licensing:

- software and technical implementation: BSD 3-Clause;
- original Kinetic Vanguard rules, examples, and editorial content: CC BY-NC-SA 4.0;
- SRD 5.2.1-derived material: CC BY 4.0.

The NonCommercial and ShareAlike terms do not restrict or relicense SRD-derived material. See `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, and `NOTICE.md` for the exact boundaries and required attribution.

## Development and release discipline

Changes reach `main` through pull requests. The active `Protect main` ruleset requires an up-to-date branch, resolved review conversations, and the stable `Main branch gate`; it blocks force pushes and deletion. Squash merge is the normal merge method.

At the start of every development line, before a release PR leaves draft, and during publication, complete `RELEASE_CHECKLIST.md`. The checklist requires an explicit README review against canonical authority, the changelog, open issues, CI, build outputs, release assets, and current branch-protection settings.

Frozen release branches and annotated release tags are immutable historical references. Publication workflows verify the exact frozen commit before creating or updating a GitHub Release.

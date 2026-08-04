# Kinetic Vanguard v13 rules reference

`KineticVanguard.yaml` is the sole canonical rules authority. All rule wording, balance, metadata, tables, examples, and feature changes are authored directly in YAML.

Prototype and authorized release HTML are generated from that YAML after schema and semantic validation. `Kinetic_Vanguard.md` was retired after the completed v12.1.0-to-v13 migration; Git history and tagged releases preserve the legacy source and architecture review record.

## Release status

Kinetic Vanguard **v13.0.1** is the current patch release. The publication is one self-contained, offline-capable file: `KineticVanguard.html`.

The schema, semantic, publication, filter, accessibility, determinism, and Chromium/Firefox layout suites remain release-blocking.

## Commands

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

It writes `artifacts/KineticVanguard.html` with `release_status: release` and no prototype banner. GitHub Actions runs the authorized release build only after all verification steps pass and uploads the publication plus its build manifest and integrity reports as the `kinetic-vanguard-v13.0.1` artifact.

The completed one-time Markdown migration command has been removed and is not part of normal development. Contributors edit `KineticVanguard.yaml` directly; there is no Markdown synchronization step.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation, classification, authority-coverage, and route checks, constructs immutable filter and route projections, and emits:

- release or prototype HTML;
- filtered-search integrity report;
- YAML entity-to-route coverage ledger;
- deterministic build manifest.

The browser application contains only native finite selectors, checkboxes, buttons, and links. It makes no runtime network request and does not use local persistence, free-text search, a rules catch-all view, character state, or calculators.

## Filtering and progression ordering

The Rules area filter is canonical: it matches only an entity’s `presentation_metadata.primary_rules_area`, which is also the source of the visible result suffix. Additional selector-reachable routes recorded in `classifications.rules_area` remain available for browsing but do not broaden filtered results. Different facet groups use AND; selected values within the multi-select Rules area group use OR.

Filtered results use this exact comparator: Rules area vocabulary order, progression section (`foundation`, `levelled`, `reference`), earliest `level`, primary-area topic/source order, feature-role vocabulary order, title codepoint order, then entity-ID codepoint order. The generated Name index preserves Rules area vocabulary order and, within each group, uses progression section, numeric earliest `level`, bare title codepoint order, then entity-ID codepoint order. The browser filters and renders that preordered index, including after classification changes.

`level` is the structured earliest acquisition/availability level. Selectable high-tier Advanced Training entries therefore use level 15, except Overload Mastery II, whose Psionic Apex prerequisite makes its earliest level 18. An entity without a level must declare `progression_section`; foundational or automatically applicable mechanics sort before level-gated entries, while supplemental/reference entries sort after them. Semantic validation rejects missing or conflicting section metadata.

## Known follow-up

Forked Lightning needs explicit failed-save wording for non-primary targets. The issue is tracked separately and does not block the v13.0 publication.

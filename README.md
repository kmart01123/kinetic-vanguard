# Kinetic Vanguard v13 rules reference

This repository implements the schema-first architecture accepted by ADR-0001 revision 22.

`KineticVanguard.yaml` is the only v13 rules authority. The legacy `Kinetic_Vanguard.md` is represented only through the checked-in migration inventory and provenance records and is deliberately absent from `build/inputs.json`.

## Release status

Kinetic Vanguard **v13.0.0** is approved for release. The publication is one self-contained, offline-capable file: `KineticVanguard.html`.

Revision 22 closes the ADR review cycle and authorizes v13.0 to ship behind the automated product gate. The full schema, semantic, architecture, publication, filter, determinism, and Chromium/Firefox layout suites remain release-blocking. Unperformed human migration and evidence work is documented as a v13.0 waiver rather than misrepresented as completed review.

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

It writes `artifacts/KineticVanguard.html` with `release_status: release` and no prototype banner. GitHub Actions runs the authorized release build only after all verification steps pass and uploads the publication plus its build manifest and integrity reports as the `kinetic-vanguard-v13.0.0` artifact.

`npm run migrate` re-enumerates the pinned master and rewrites the provisional YAML plus migration inventory files. It is a migration-development command, not a normal build stage. Do not run it casually after manual provenance work begins.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation/classification/origin checks, constructs immutable filter and route projections, and emits:

- release or prototype HTML;
- effective migration ledger;
- filtered-search integrity report;
- coverage/provenance ledger;
- deterministic build manifest.

The browser application contains only native finite selectors, checkboxes, buttons, and links. It makes no runtime network request and does not use local persistence, free-text search, a rules catch-all view, character state, or calculators.

## Filtering and progression ordering

The Rules area filter is canonical: it matches only an entity’s `presentation_metadata.primary_rules_area`, which is also the source of the visible result suffix. Additional selector-reachable routes recorded in `classifications.rules_area` remain available for browsing but do not broaden filtered results. Different facet groups use AND; selected values within the multi-select Rules area group use OR.

Filtered results use this exact comparator: Rules area vocabulary order, progression section (`foundation`, `levelled`, `reference`), earliest `level`, primary-area topic/source order, feature-role vocabulary order, title codepoint order, then entity-ID codepoint order. The Name selector remains alphabetical within each Rules area.

`level` is the structured earliest acquisition/availability level. Selectable high-tier Advanced Training entries therefore use level 15, except Overload Mastery II, whose Psionic Apex prerequisite makes its earliest level 18. An entity without a level must declare `progression_section`; foundational or automatically applicable mechanics sort before level-gated entries, while supplemental/reference entries sort after them. Semantic validation rejects missing or conflicting section metadata.

## Known v13.0.1 follow-up

Forked Lightning needs explicit failed-save wording for non-primary targets. The issue is tracked separately and does not block the v13.0 publication.

# Kinetic Vanguard schema-first reference

This repository implements the prototype profile authorized by ADR-0001 revision 21.

`KineticVanguard.yaml` is the only v13 rules authority. The legacy `Kinetic_Vanguard.md` is used only by the one-time migration command and is deliberately absent from `build/inputs.json`.

## Development status

The current rules version is **v13**. It is in stabilization, bug-squish, and presentation-polish work, with the current focus on rules clarity, layout integrity, consistency, and validation. The generated publication remains a non-release prototype; v13 is not finalized or released.

## Commands

```text
npm ci
npm run typecheck
npm run validate
npm test
npm run build
npm run test:determinism
```

`npm run build` writes the self-contained, offline-capable prototype to `artifacts/KineticVanguard.prototype.html`. It always carries a visible and accessibility-exposed `NON-RELEASE PROTOTYPE` identity.

`npm run migrate` re-enumerates the pinned master and rewrites the provisional YAML plus migration inventory files. It is a migration-development command, not a normal build stage. Do not run it after humans begin disposition review without following the ADR’s inventory-version and amendment rules.

## Release status

`npm run build:release` intentionally fails closed. A release cannot be generated until maintainers provide all human and environment gates required by the ADR, including:

- dispositions and content-scoped attestations for all 548 source units;
- migration acceptance and entity-origin review;
- independent classification/correctness review;
- accepted content-evidence policy binding;
- pinned accessibility scanner, browser, and assistive-technology versions plus completed reports;
- immutable base-container identity and release evidence.

The deployable directory is never touched by a prototype build.

## Architecture

The build parses restricted YAML 1.2, validates the canonical JSON Schema, performs semantic navigation/classification/origin checks, constructs immutable filter and route projections, and emits:

- the prototype HTML;
- effective migration ledger;
- filtered-search integrity report;
- coverage/provenance ledger;
- deterministic build manifest.

The browser application contains only native finite selectors, checkboxes, buttons, and links. It makes no runtime network request and does not use local persistence, free-text search, a rules catch-all view, character state, or calculators.

## Filtering and progression ordering

The Rules area filter is canonical: it matches only an entity’s `presentation_metadata.primary_rules_area`, which is also the source of the visible result suffix. Additional selector-reachable routes recorded in `classifications.rules_area` remain available for browsing but do not broaden filtered results. Different facet groups use AND; selected values within the multi-select Rules area group use OR.

Filtered results use this exact comparator: Rules area vocabulary order, progression section (`foundation`, `levelled`, `reference`), earliest `level`, primary-area topic/source order, feature-role vocabulary order, title codepoint order, then entity-ID codepoint order. The Name selector remains alphabetical within each Rules area.

`level` is the structured earliest acquisition/availability level. Selectable high-tier Advanced Training entries therefore use level 15, except Overload Mastery II, whose Psionic Apex prerequisite makes its earliest level 18. An entity without a level must declare `progression_section`; foundational or automatically applicable mechanics sort before level-gated entries, while supplemental/reference entries sort after them. Semantic validation rejects missing or conflicting section metadata.

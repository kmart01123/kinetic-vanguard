# Changelog

## 13.0.1 — 2026-08-04

### Fixed

- Standardized mathematical addition notation in tables on the literal ASCII `+` and added source-to-render regression coverage to prevent textual or styled substitutes.
- Ordered the feature Name selector by level progression, with alphabetical ordering among entries at the same level.

## 13.0.0 — 2026-08-03

Kinetic Vanguard v13.0.0 is the first schema-first release and the complete replacement for the legacy multi-document reference workflow.

### Added

- Added the schema-first v13 authority and deterministic static publication pipeline, including migration traceability, schema and semantic validation, filter integrity checks, and release gating.
- Added one self-contained, offline-capable `KineticVanguard.html` publication with finite Browse selectors, controlled filtered search, and explicit known-name activation.
- Added structured activation, Psi-cost, and concentration metadata callouts, including a distinct concentration indicator.
- Added four full worked attack turns plus the focused Glacial Spike Overload example.

### Changed

- Corrected responsive browser layout behavior with shrinkable grid tracks, contained long content, mobile stacking, and cross-browser layout coverage.
- Separated full example turns from normative rules content and rendered examples as a distinct, phase-structured presentation section.
- Consolidated the Overload rules and tier system into one common feature, with tier headings and labels rendered as an explicit visual hierarchy.
- Ordered common and advanced features by progression, using explicit foundation/reference sections for entries without a level and earliest availability for level-gated entries.
- Kept common features out of discipline-specific Browse topics and made each entity's primary rules area authoritative for filtered results and result labels.
- Restored the Manifested Strike die progression prose and table to the Manifested Strike feature instead of Overload.
- Standardized tiered feature wording around `T0 Base` and cumulative `T1`/`T2` changes while retaining the validated mechanics.
- Accepted ADR-0001 revision 22 and replaced the unimplemented human-evidence release gate with an explicit maintainer waiver while retaining all automated product checks.

### Validation coverage

- Architecture and authority-boundary tests.
- Publication and release-identity tests.
- Filter correctness, routing, and history-state tests.
- Deterministic build comparison.
- Chromium and Firefox desktop, tablet, mobile, and print layout checks.

### Known issue planned for 13.0.1

- Forked Lightning needs explicit failed-save wording for non-primary targets.

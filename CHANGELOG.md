# Changelog

## 13.1.0 — Unreleased

### Changed

- Established `KineticVanguard.yaml` as the sole maintained rules-authoring source.
- Completed a full language audit of all 44 publishable rules entities, tightening grammar, terminology, sentence structure, tables, examples, and tier wording without intentionally changing mechanics.
- Consolidated repeated Overload, Manifested Strike, and Advanced Training reminders so shared rules are stated once and feature text focuses on feature-specific outcomes.
- Clarified that every Forked Lightning target makes and resolves its own Charisma saving throw, with Tier 2 disruption limited to targets that fail and Speed 0 limited to a failed save by the primary target.
- Defined fixed concentration durations for Vectored Thrust (up to 10 minutes) and Frozen Ground, Mass Levitation, Ball Lightning, and Gravitic Press (up to 1 minute), including canonical rendered metadata.

### Removed

- Retired the completed v12.1.0 Markdown migration source, migration command, migration-only records, and obsolete ADR revision files from the active repository.
- Removed non-normative design commentary, duplicated activation reminders, and other superfluous text where the same rule is already established by structured metadata or shared rules.

### Rules decisions pending

- Mass Levitation does not state whether Medium-or-smaller and Large targets can be mixed in one activation.

## 13.0.1 — 2026-08-04

### Fixed

- Removed the redundant Name-selector Open button so a committed valid rule selection updates the card and route immediately while preserving history, filter restoration, native focus, and same-rule idempotence.
- Standardized mathematical addition notation in tables on the literal ASCII `+` and added source-to-render regression coverage to prevent textual or styled substitutes.
- Ordered every rules-area group in the Name selector by numeric feature level, bare display name, and canonical ID, including after classification filters rebuild the options.
- Simplified the canonical user-facing names of Deflection Screen and Phase Step while preserving their Advanced Training classification and stable routes.

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

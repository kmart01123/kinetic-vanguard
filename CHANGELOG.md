# Changelog

## 14.3.0 — Unreleased

### Changed

- Modernized the development container on Ubuntu 26.04 with repository-aligned Node, npm, and Python versions, native Playwright browser support, reproducible developer-agent CLI installation, and persistent local authentication state without exposing host container sockets.
- Added an optional local Claude Code and Grok Build bridge that validates provider-bound machine output against an exact pull-request head before posting trusted top-level GitHub review records; ordinary CI only runs mocked bridge tests and never requires provider access.
- Hardened the external-review bridge with wrapper-side provider-content redaction, worktree-confined file tools without provider shell access, real-CLI capability preflights, neutral-prose-safe identity validation, direct trusted-header spoof coverage, and a structured findings contract that rejects empty or verdict-inconsistent review evidence.
- Corrected Grok review integration with camelCase structured-envelope parsing, explicit Build-model selection and verification, strict path-scoped reads, pre-provider symlink confinement, and fine-grained GitHub PAT redaction.
- Restored Grok authentication under strict review isolation with a fail-closed ephemeral sandbox profile and directory-limited runtime auth exception unavailable to model file tools, and made Claude reviews explicitly use the rolling Opus alias.
- Closed final external-review bridge gaps with OAuth-compatible Claude Read-only, setting-source, hook, memory, and MCP confinement; whole-directory Grok credential-tool denies; independent single-line model evidence; GitHub-render-aware wrapper spoof detection; exact whole-token CLI capability checks; and direct atomicity regressions.
- Made Glacial Spike replace Slow mastery for its triggering Manifested Strike instead of stacking both 10-foot Speed reductions on the same hit.
- Expanded the Eldritch Knight benchmark comparator to the 41 control-relevant spells retained by the completed current-PHB audit, using independently expressed mechanical abstractions, reusable analytical primitives, and explicit fail-closed diagnostic packages without changing published Control Reliability selection or Control Value weights.
- Corrected the expanded Eldritch Knight shadow evaluation with production Mind Sliver and Eldritch Strike save composition, closed-form Web and Black Tentacles escape exposure, overlapping Action-denial normalization, and immunity-safe condition dependencies.
- Implemented the audited current-PHB Battle Master comparator with separate fixed 5/7/9/9 damage- and control-forward loadouts, exact pre-roll Feinting Attack and shared Feint/Hew Bonus Action accounting, structured Menacing/Pushing/Trip control, fail-closed Goading/Disarming diagnostics, and comparator-neutral standing-cost semantics for legally recoverable Prone.
- Corrected Control Reliability benchmark methodology so bare Kinetic Mastery receives the same legal retries across one ordinary Attack action as repeatable embedded Mastery; Action Surge remains excluded, with no changes to Kinetic Vanguard or comparator mechanics.

### Removed

- Retired the superseded `legacy_v14_1` benchmark profile; maintained profiles are now `headline` and `eligible_census`.
- Removed the obsolete `--trials` and `--seed` damage and control CLI options now that maintained evaluation uses exact analytical enumeration.
- Removed the `Provenance Trials`, `Provenance Seed`, `Provenance Trial Seed Role`, and `Provenance Status` columns from maintained benchmark matrices.

## 14.2.0 — 2026-08-16

### Changed

- Made Calculator / Feature Deck the complete individual-feature surface: calculated cards expose useful deterministic math, qualitative cards retain their full canonical rules without fake calculations, Blood Tax has a direct calculated card, and Rules Reference now focuses on shared system and chassis rules.
- Revised Vectored Thrust so Tier 1 increases its fly Speed by `5 × Proficiency Bonus` feet instead of preventing Opportunity Attacks, while Tier 2 removes its Concentration requirement and retains the 10-minute duration and Incapacitated end condition.
- Restored the vetted 330-creature SRD 5.2.1 catalog; made the reviewed 47-target `headline` profile the public default; retained `legacy_v14_1` for 28-target longitudinal reproduction and `eligible_census` as the 93-target validation and sensitivity inventory.
- Allowed the same paid on-hit rider to be declared on multiple Manifested Strikes in one Attack action, with independent Psi and Blood Tax payment for every declaration, including misses.
- Allowed rider declarations to retry the same legal target or spread among different legal targets while retaining one rider per Manifested Strike and one Tier 2 rider per Attack action.
- Corrected Control Reliability to distinguish the new paid-rider rule from the pre-existing 0-Psi repeatability of all four Signature Riders, which published v14.1 had approximated as one-shot control scenarios.
- Corrected comparator fairness by allowing configured Battle Master maneuvers to retry after later legal hits while attacks and superiority dice remain, and by using all attacks in one ordinary Eldritch Strike primer Attack action before the single configured Blindness/Deafness cast.

## 14.1.0 — 2026-08-07

### Added

- Restored maintained damage and control benchmark harness source with a shared validated projection from the real root `KineticVanguard.yaml`.
- Added pinned SRD 5.2.1 target data, separately declared frozen Battle Master and Eldritch Knight comparator assumptions, verified legacy provenance, and a legacy-to-current migration map.
- Added versioned CSV, Markdown, and self-contained HTML damage/control matrices with a dynamic Battle Master/Eldritch Knight min/max envelope, COLD/IDEAL/HOT/N/A handling, explicit lower/upper boundary values and identities, signed `Boundary Delta %`, aggregate-derived ratios, and a per-target control selection-audit CSV.
- Added fast authority, mutation, completeness, aggregation, classification, output-consistency, and fixed-input smoke tests to ordinary CI.
- Added a repository-wide licensing audit, build-manifest legal-asset hashes, complete deployable legal bundles, and embedded licensing/attribution notices for standalone publications and benchmark reports.
- Added synchronized near-top level × discipline README heat matrices with result-only COLD/IDEAL/HOT/N/A cells for single-target damage and Control Reliability; full cluster and aggregate evidence remains in generated release reports, with canonical release-state labeling and deterministic full analytical regeneration and CI checking.

### Changed

- Added a Calculator Feature Group filter for the four disciplines and Advanced Training, with a separate unselected Manifested Strike landing card and canonical classification-backed feature grouping. This changes Calculator navigation only, not rules or calculations.
- Advanced the authority schema to 2.1.0 with canonical structured discipline, mastery, targeting, resistance-bypass, restriction, duration, repeat-save, and control-outcome fields under the shared Calculator mechanics area.
- Started the 14.1.0 rules-development line without changing player-facing Calculator scope or exposing benchmark tools in the offline publication.
- Reimplemented damage and comparator selection as deterministic exact observed-state policies and completed independent numerical review with documented differences. Historical seeds and trial settings remain compatibility metadata; the current review does not inherit or claim the v12.0.0 Monte Carlo certification.
- Isolated minimal Battle Master and Eldritch Knight parameters under `harness/comparators/`, removed unused comparator prose, added separate provenance hashing, and clarified that project licenses do not cover Wizards-owned non-SRD material.

## 14.0.0 — 2026-08-06

### Added

- Added an offline Calculator for Manifested Strike and supported rider and standalone feature tiers, with level-aware attack, damage, saving throw, Psi, and Blood Tax results derived from canonical authority.

### Changed

- Made Barrier require Concentration for up to 1 minute at T0 and T1. T2 continues to increase the duration to 10 minutes. Added structured concentration metadata, aligned the feature reference, and separated the five Barrier modes into a bulleted list for readability.
- Made the canonical rules version the publication's sole product version, removing the separate application-version label and identity from the interface, provenance, derived-output registry, and build manifest.
- Broke six dense rules passages—Mass Levitation, Explosion/Implosion, Forked Lightning, Gravitic Press, and Manifested Strike’s Somatic Requirement and Holdout Option—into semantic ordered or bulleted lists while preserving their mechanics and tier scope.
- Completed the readability pass by converting the remaining dense mechanical sequences, alternatives, and conditional outcomes—and every authored example—into semantic ordered or bulleted lists without changing their rules outcomes.
- Migrated each Example Play phase from an inline-node array to an array of paragraph or list blocks so examples can express their steps semantically. This incompatible authority-shape change advances the schema version from 1.0.0 to 2.0.0 while leaving the rules version at 14.0.0.
- Set the Calculator’s default Fighter Level to 20 and removed the always-visible duplicate Manifested Strike summary. Manifested Strike remains selectable directly, and rider results retain their existing Triggering Manifested Strike details.
- Aligned Explosion/Implosion’s Tier 1 Sphere radius and push or pull distance at 30 feet.
- Added level-aware total Psi Points beside each feature’s Psi cost in the Calculator, using the canonical Psi Reservoir progression.
- Made Manifested Strike the Calculator’s initial selection and first displayed result card.
- Expanded and normalized Calculator longform math. Hit, damage, and saving throw calculations now use full term names, parenthesized component values, `+` operators, and an `=` result while retaining their compact totals.

### Compatibility

- Version 14 is a major rules release because Barrier's new Concentration requirement changes playable outcomes and can invalidate concurrent concentration.

## 13.2.0 — 2026-08-06

### Changed

- Adopted component-based licensing: BSD-3-Clause for software and tooling, CC BY-NC-SA 4.0 for original Kinetic Vanguard content, and CC BY 4.0 for SRD 5.2.1-derived material, with exact SRD attribution in repository notices and generated publications.
- Revised Mass Levitation to use five target slots: a Medium or smaller creature costs one slot, a Large creature costs two slots, and any mixed combination costing no more than five slots is legal. Each creature can be chosen only once, unused slots are lost, and Huge or larger creatures remain immune.
- Changed a successful Mass Levitation repeat save to end the effect and make the creature fall normally from its current position. A successful initial save still leaves the target unaffected, and every other Mass Levitation mechanic is preserved.
- Added a new default Start Here experience with three primary paths, four Discipline cards, a basic-turn orientation, a build checklist, a short glossary, and direct canonical destinations into the complete rules.
- Added persistent Start Here and Rules Reference navigation while preserving existing category, topic, entity, and filter deep links, browser-history restoration, keyboard and mobile focus behavior, offline operation, and readable print output.
- Kept onboarding outside the 44 publishable rules entities and made it orientation and navigation only; it does not change subclass mechanics.
- Refreshed the README’s release and development status, added a recurring release checklist and pull-request review step, and added an automated guard against stale development-version and artifact wording.

## 13.1.0 — 2026-08-05

### Changed

- Established `KineticVanguard.yaml` as the sole maintained rules-authoring source.
- Completed a full language audit of all 44 publishable rules entities, tightening grammar, terminology, sentence structure, tables, examples, and tier wording without intentionally changing mechanics.
- Consolidated repeated Overload, Manifested Strike, and Advanced Training reminders so shared rules are stated once and feature text focuses on feature-specific outcomes.
- Clarified that every Forked Lightning target makes and resolves its own Charisma saving throw, with Tier 2 disruption limited to targets that fail and Speed 0 limited to a failed save by the primary target.
- Defined fixed concentration durations for Vectored Thrust (up to 10 minutes) and Frozen Ground, Mass Levitation, Ball Lightning, and Gravitic Press (up to 1 minute), including canonical rendered metadata.
- Clarified Ball Lightning entry triggers for voluntary and forced movement on any turn, including the once-per-turn entry limit and the non-triggering effect of moving the orb onto a stationary creature.
- Led the play procedure with pre-roll rider declaration timing and clarified that Tier 2 Blood Tax replaces the Tier 1 amount rather than adding to it.
- Restated independent Forked Lightning saving throws and damage at every tier, corrected Frozen Ground’s Tier 0 replacement reference, and aligned Telekinetic Slam flavor with horizontal movement.
- Added player-facing activation labels and Beguile’s tier-varying duration metadata while preserving internal activation classifications.
- Made mobile Category, Topic, Name, and filtered-result navigation focus and reveal selected rule headings; no classifications now means every canonical result is available in a compact disclosure.
- Rendered tier labels as semantic level-three headings and expanded the Psi Cost Reference with full-English activation and duration values in a horizontally scrollable mobile table.
- Normalized active authority and approved interface text to full English without contractions, with an automated source-level guard.
- Derived active continuous-integration release labels and artifact naming from the canonical rules version.
- Defined the Fighter level 3 choice of one permanent Kinetic Discipline, distinct from the Psionic Ability choice, and documented every subclass element that choice determines.
- Renamed the Psi Cost Reference’s duration column to Ongoing Duration and normalized all 34 rows against tier-aware ongoing outcomes without changing feature mechanics.
- Added page-local Show and Level filters to the Psi Cost Reference, with live row counts, an accessible no-match state, full-table print output, and readable desktop and print column sizing.

### Removed

- Retired the completed v12.1.0 Markdown migration source, migration command, migration-only records, and obsolete ADR revision files from the active repository.
- Removed non-normative design commentary, duplicated activation reminders, and other superfluous text where the same rule is already established by structured metadata or shared rules.

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

# Changelog

## Unreleased

### Added

- Added a pinned, provenance-checked seven-condition consequence catalog for Blinded, Charmed, Frightened, Incapacitated, Prone, Restrained, and Stunned, plus separate versioned control-engine methodology configuration.
- Added the shared weight-free Python control consequence, reliability, overlap, state, and timeline engine; its compact validation and 72-case hand-calculated fixture commands cover both initiative schedules, both area-response conventions, and all three displacement functions without producing a Control Value scalar, classification, or optimization.

### Changed

- Narrowed the maintained benchmark architecture to an explicit damage authority, projection, configuration, comparator, report, README generator, and command boundary.
- Replaced the generated two-matrix README snapshot with one damage heat table and a static control-methodology status that points v14.1 reproduction to frozen release evidence and identifies the v14.2 redesign sequence.
- Completed Control Authority v2.1 with 35 modeled rows, 14 maintained profile exclusions, zero unsupported rows, typed event/save/choice/movement/area/persistent-state semantics, and shared TypeScript/Python parity coverage; it remains separate from damage and does not publish a v14.2 control result.
- Added a fail-closed 28-row SRD control-target supplement for official movement modes, hover, and relevant nonvisual senses while preserving the maintained damage roster byte-for-byte.
- Advanced the shared control engine, consequence catalog, primitive contract, normalization rules, timeline engine, and engine configuration to `2.0.0`. The successor session replaces unique/self-sourced initial conditions with provenance-bearing condition instances and generic inclusion lineage; makes Prone remain, stand, voluntary drop, and crawl explicit proposals; evaluates Charmed legality and attack/save modes against live source-relative state; and couples Incapacitated to exact concentration cleanup, action/Initiative facts, and sourced current-position falls, including state-derived Fly Speed 0. Control Authority remains `2.1.0`, the canonical schema remains `3.1.0`, Kinetic Vanguard rules remain `14.2.0`, and damage contracts are unchanged.
- Corrected the seven-condition catalog so alternative sight affects Blinded sight and sight-dependent checks without erasing its independent outgoing Disadvantage or incoming Advantage, Charmed names exactly attack, damaging-ability, and damaging-magical-effect prohibitions, and attack modifiers use per-opportunity rather than synthetic per-turn units. Consequence provenance now pins only the accepted public issue #53 and #54 records.
- Replaced the v1 control-engine fixture path with the v2 successor path; the old fixture path is not retained as a compatibility alias.
- Corrected both control-engine initiative schedules so the actor-owned movement and area-response opportunity precedes active-turn and attack windows, and made engine-owned chronological sessions with canonical scenario identity and issued reliability/state records the only supported final-result path.
- Made shortest-route geometry, live area membership, and exact remaining distance session-owned across movement opportunities; typed ordinary and forced entries now perform scenario-bound false-to-true membership and route transitions before their same-event gates, with engine-owned once-per-turn frequency and final replay, while typed moving-area updates apply the compiled entry policy without caller-authored membership or history. Membership drives movement and recurring-area gate eligibility even with no active area component, exits and canonical re-entries update later gates, fixed occupancy creates no nominal exit progress, and raw per-event route replacement remains rejected. Zero-area programs accept either inert area convention, while multiple-area ambiguity fails closed.
- Made activation-cadence ambient area components membership-scoped: activation filters them from nonmembers with typed provenance, entry and re-entry restore still-live components once with activation-derived expiry independently of save frequency without restarting expired duration, exits and effect end remove them, and session invariants reject stale ambient state before movement, normalization, or final assembly under either area convention.
- Phase-locked required normalization to each target's immutable pre-event component and route state: target-affecting branch, displacement, entry, geometry, movement, and concentration-end mutations now reject atomically while normalization is pending, independent targets remain uncoupled, and final replay rejects stale or empty post-mutation normalization records.
- Made failed concentration checks genuinely two-phase: the damage-context event now issues an attested pending failure while the tracker, components, ambient membership, and routes remain active, and only its immediate typed concentration-end event may end the tracker, execute compiled end gates and falls, terminate state, close routes, and clear the pending identity. Normalization blocks the failure path before mutation, and final replay rejects missing, duplicate, foreign, stale, rewritten, or discontinuous check/end pairs. That correction landed before the v2 successor contract and changed no damage inputs or numerical mechanics; no analytical benchmark ran.
- Codified the standing policy for retiring superseded implementations from current development while preserving released history through frozen branches, tags, Releases, evidence assets, and Git history.

### Removed

- Retired the legacy Control Reliability evaluator, scenario/configuration data, report and selection-audit pipeline, README regeneration path, package commands, current-version publication workflow, and output-parity/golden-result burden from maintained `main`.

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

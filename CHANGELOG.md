# Changelog

## Unreleased

### Removed

- Retired Gravitic Press from the Advanced Training pool, feature reference, navigation, Calculator, and harness projection following the maintainer's disposition in #133. Other Advanced Training choices and choice-grant levels remain unchanged. Existing users of this option must select a retained option when adopting the new rules.

### Compatibility

- Began the v15.0.0 development line because removal of a published rule is a breaking change under `policy/rules-versioning.md`. This release carries forward the unreleased v14.4 mechanics work; the published v14.3.0 release remains unchanged. The retirement changes the ability inventory without changing the schema or projection shapes.

### Changed

- Replaced Branching Bolt’s Fighter-18 Focused Bolt option with freely allocated 3/4/5 rider dice from Fighter 7, retaining Tier 2’s Fighter-10 gate. Every use requires the primary plus at least two distinct secondary creatures hostile to you, with at least one die per target and a maximum of 3/4/5 total targets. Declare the complete allocation before the original strike; its miss cancels the rider and its hit delivers every allocated die without additional attack rolls or rider critical bonuses. Canonical `damage_allocation` drives the Calculator and native planner, including hostile-secondary eligibility; the Calculator reads its minimum-target instruction from the projected count. Rules remain 15.0.0; schema advances to 2.15.0 and harness projection to 1.11.0. See `docs/branching-bolt-integration.md`.

- Integrated the approved surgical damage upgrades in unreleased v15.0.0: Absolute Zero now deals 6d10 + 45/55/65 cold damage by tier, with successful saves halving the whole packet; Telekinetic Shove deals 4 force damage at every tier from Fighter 18; and Branching Bolt gains a Fighter-18 Focused Bolt option that forgoes all additional targets for two Manifested Strike dice against the struck target. Pyrokinesis, shared pre-roll Discipline Maturation, costs, control, and native damage types are unchanged. Canonical `dice_plus_fixed`, `fixed_by_level`, and rider `damage_options` drive both the Calculator and native damage planner. Schema advances to 2.13.0 and harness projection to 1.9.0; the rules version remains 15.0.0. See `docs/surgical-damage-integration.md` for full benchmark and validation evidence.

- Corrected Discipline Maturation for all four disciplines to require declaration before the Manifested Strike attack roll and spend the once-per-Attack-action use even on a miss. Only the declared strike can deliver the shared 3d8 native-damage packet; Action Surge grants a fresh use with its new Attack action. The damage planner now chooses declaration or deferral before outcome enumeration instead of automatically applying maturation to the first hit. This restores the intended gamble within the unreleased v15.0.0 rules line, so `rules_version` remains 15.0.0; schema advances to 2.12.0 and harness projection to 1.8.0 for explicit declaration and consumption fields. Regenerated the full 47-target damage/control benchmark with 12 workers; README now reflects the corrected declaration rule. Earlier-level damage, comparators, and control results are unchanged; see `docs/maturation-declaration-evaluation.md`.

- Adopted the tested Fighter-18 3d8 cold Cryokinesis and 3d8 lightning Electrokinesis Apex packets. All four disciplines now use one shared Discipline Maturation procedure with their own damage type, once per Attack action, normal defenses, no critical doubling, and no resource cost. Existing Pyrokinesis/Psychokinesis outcomes and Refined Holdout remain unchanged. This added playable content stays within the unreleased v15.0.0 line; schema advances to 2.11.0 and projection to 1.7.0.

- Added Pyrokinesis Maturation to Fighter-18 Psionic Apex: once per Attack action, a Manifested Strike hit deals a separate 3d8 fire packet to the struck creature, refreshed by a new Attack action. The packet costs no Psi or Blood Tax, does not double on a critical hit, and respects Resistance and Immunity even with a Tier-2 rider or Holdout. This new playable content joins the existing unreleased v15.0.0 line; schema advances to 2.10.0 and harness projection to 1.6.0.

- Completed the approved v14.4 resolution simplification: Action Surge can activate another eligible standalone psionic Action; Electron Burst uses one 1d8/2d8/3d8 packet for every affected creature; Static Discharge targets up to 2/4/6 total creatures by tier; and Tier-2 feature/rider damage ignores Resistance across all disciplines and Advanced Training without bypassing Immunity or changing the triggering Manifested Strike or Blood Tax.
- Expressed Telekinetic Slam and Deflection Screen successful-save movement with an explicit `partial_on_success` primitive tied to their Strength saves, preserving both existing movement outcomes. Moved resistance penetration to shared Overload authority, removed per-feature flags, and updated consumer projections and action planning. Schema advances to 2.9.0 and harness projection to 1.5.0; these approved rules changes continue the existing unreleased v14.4.0 line.
- Corrected Grok review tool selection to native `read_file,grep` IDs while retaining scoped Read/Grep permission rules. Reject explicit CLI error or interrupted-completion metadata before accepting a review payload, and cover structured-final versus progress-text selection with offline regressions.

- Closed the remaining PR #142 review findings: exclude short inferred prompt fragments from substring redaction while preserving explicit secret redaction, reject unfinished review statements after prose lead-ins while retaining quoted-fixture support, and remove the unused review-ready doctor diagnostic helper.

- Fixed live CLI output truncation by capturing stdout/stderr in private temporary regular files rather than pipes; this restores the complete Claude capability surface. Excluded punctuation-only diff markers from prompt-line redaction so diagnostics preserve CLI flags and hyphenated terms while meaningful prompts and explicit secrets remain redacted.

- Made external reviews independently collectible and explicitly resumable: each provider uses a separate clean checkout, validated results survive another provider's failure, and private checkpoints bind reuse to exact PR/prompt/bridge identity. Added collection-only runs, explicit INCOMPLETE outcomes, field-specific finality diagnostics, and posting receipts that prevent automatic duplication after an uncertain write. The CI gate now hands its exact approved SHA to the bridge, while per-adapter checks replace the redundant blanket doctor prerequisite. Required all-provider validation and live head/base revalidation still precede publication.

- Hardened review finality checks for “not yet” and contracted negation while allowing explicitly introduced quoted test fixtures in completed reviews. Preserve diagnostic readability when wrapped prompts contain whitespace-only diff lines without weakening meaningful prompt or secret redaction.

- Reject bare placeholder review fields and explicit unfinished or unperformed review statements, including the two failures observed during PR #143 review. Regressions cover both providers, all review fields, and atomic rejection without suppressing legitimate findings about incomplete product features.

- Made external-review failures identify their component and stage, retain bounded redacted diagnostics, offer known authentication remediation, and report skipped providers plus posting state without changing exact-head validation, isolation, or pre-post all-provider atomicity. `doctor` now preserves safe command-failure reasons and names missing CLI flags.

- Made the external-review bridge reject provider output that explicitly describes its own review as bootstrap, unfinished, or still in progress while preserving concise final results and substantive findings that discuss similar product concepts.
- Completed the behavior-preserving rider-first representation migration for every machine-consumed ability: delivery and targeting topology are independent, all riders share one Manifested Strike rider slot, known selectors replace opaque topology, and canonical mechanics author concrete D&D damage/save facts. All 30 Calculator entries and 27 harness feature rules derive from those neutral per-entity primitives; benchmark scenario and scoring policy remain outside canonical rules mechanics.
- Standardized the Phase Step family on fixed Strength saving throws, and made Improved Phase Step explicitly deal force damage at every tier regardless of Discipline.
- Consolidated the ten shared progression and core-mechanics fields under their canonical rules entities: level bands, Overload access and action economy, Manifested Strike and Holdout math, Discipline masteries, and Psionic Apex.
- Removed the Calculator and harness mechanics registries from YAML. The browser publication and Python harness adapter now build deterministic consumer views directly from entity `mechanics` and `system_mechanics`, and the loader no longer mutates the parsed authority.
- Advanced the authority schema contract from 2.4.0 through 2.7.0 and the harness projection contract to 1.3.0 without changing `rules_version` 14.3.0 or playable mechanics. Projection arrays now follow canonical entity order.
- Began the intentional v14.4 rules line at `rules_version: 14.4.0`, removed the now-unused discipline-save mapping contract in schema 2.8.0, and advanced the harness projection contract to 1.4.0 for fixed concrete saves.

## 14.3.0 — 2026-08-26

### Changed

- Changed Fighter 18 Refined Holdout to deal `1d6 + Psionic Ability modifier` force damage instead of using the earlier fallback calculation.
- Added Psychokinesis's Fighter 18 Psionic Apex maturation: once per Attack action, a Manifested Strike hit deals an additional `3d8` force damage, and a new Attack action from Action Surge refreshes that availability.
- Changed Electron Burst secondary damage to `1d8` / `2d8` / `3d8` while retaining `2d8` / `3d8` / `4d8` primary damage, and changed Arctic Tempest to `8d10` / `9d10` / `10d10`.
- Made Glacial Spike replace Slow mastery on its triggering Manifested Strike instead of stacking both 10-foot Speed reductions.
- Made hostile named conditions consistently require saving throws: Flare retains its Dexterity save at every tier, and Mind Lock uses one Intelligence save for its full condition package.
- Moved Blood Tax under Start Here's Terms to Know, and simplified Rules Reference to direct authority-derived Topic navigation plus canonical Name routing while removing obsolete global classification filtering and preserving useful deep links and browser-history routing.
- Consolidated Calculator / Feature Deck output around one shared Psionic Save DC instead of repeating it per feature, and added a dedicated calculated Holdout Option utility card.
- Published the current non-release development prototype at the stable GitHub Pages development URL, with README links to the prototype and relevant balance context; this remains a development build rather than the v14.3 release artifact.
- Completed reviewed current-PHB Eldritch Knight comparator coverage, including the Mind Sliver / Eldritch Strike save composition and persistent-effect escape and exposure behavior required by the accepted evaluation.
- Implemented the audited current-PHB Battle Master comparator with final level-specific damage- and control-forward loadouts, pre-roll Feinting Attack timing, shared Feint/Hew Bonus Action accounting, and fail-closed control diagnostics.
- Intentionally retained the remaining six-target Electrokinesis and three-target Cryokinesis headline damage outliers as discipline and comparator-envelope results rather than applying further tuning.
- Published Control Value as the primary control-balance metric, using the frozen Control Unit primitive/value model and transforms for final package selection; Control Reliability reports delivery probability for that same CU-selected package rather than selecting independently. Bare Kinetic Mastery receives the same legal retries across one ordinary Attack action as repeatable embedded Mastery, with Action Surge excluded, while keeping README as the concise Single-Target Damage sanity check with one control-detail link; exhaustive methodology and evidence live in `CONTROL_BENCHMARK_DETAIL.md`.
- Advanced the development authority to `rules_version: 14.3.0`, `schema_version: 2.4.0`, and harness projection contract `1.2.0`; the schema advance does not itself change player mechanics.
- Modernized the development container with repository-aligned Node, npm, and Python versions, native Playwright browser support, and persistent local developer-agent authentication without host socket exposure.
- Added an optional local Claude Code and Grok Build exact-head review bridge that validates provider output against the exact pull-request head before trusted GitHub review posting, fails closed on isolation or provider-capability gaps, applies bounded secret-safe redaction and path confinement, requires a structured validated findings/verdict contract, and posts all-provider results atomically; ordinary CI remains provider-free and deterministic.

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

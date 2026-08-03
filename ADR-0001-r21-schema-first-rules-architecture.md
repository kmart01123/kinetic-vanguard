# ADR-0001: Schema-First Rules Authority and Deterministic Static Reference Architecture

- **Status:** Proposed — revision 21
- **Date:** 2026-08-02
- **Repository:** `kmart01123/kinetic-vanguard`
- **Baseline commit:** `9c8d0bfb95b23ff724537acefaacefa01bad9538`
- **Decision owners:** Kinetic Vanguard v13 maintainers
- **Supersedes:** ADR-0001 revision 20 and earlier drafts; no previously accepted ADR
- **Implementation authorization:** Acceptance of this ADR authorizes schema, migration, build-system, and publication implementation. Migration acceptance and release conformance are separate gates defined below.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative within this ADR.

This ADR is authoritative only for architecture, process, and publication constraints. It is **not** authoritative for game-rule meaning. `KineticVanguard.yaml` prevails over this ADR in any rules-content conflict. Named mechanics or features appearing here are non-normative illustrations unless a clause explicitly states a structural requirement without asserting their rules meaning.

## Decision summary

Kinetic Vanguard v13 will use one schema-validated YAML document, `KineticVanguard.yaml`, as the sole authoritative rules source.

The source will be a structured, JSON-compatible data model authored in restricted YAML. It will not be a Markdown document embedded inside YAML block strings. Rules will be represented as typed entities such as definitions, progressions, common features, Advanced Training features, disciplines, costs, durations, level gates, option sets, tables, relationships, and concise ordered rule statements. Stable identifiers and explicit references will replace dependence on Markdown heading order and prose parsing.

A TypeScript/Node.js build system will parse and validate the YAML, normalize it into immutable typed objects, and generate one self-contained official human-readable publication. Revision 21 aligns the implementation baseline with the checked-in VS Code devcontainer: Ubuntu Resolute, Node.js 24.18.1, GitHub CLI 2.97.0, OS-provided Python for auxiliary tooling, and persistent Codex and GitHub CLI configuration volumes. Those development conveniences are not rules authorities or publication runtime dependencies.

`KineticVanguard.yaml` → `KineticVanguard.html`

`KineticVanguard.html` is the sole deployable rules publication. It is an official derived publication, not an authoring surface or independent rules authority.

The publication will provide two complementary lookup mechanisms:

1. cascading finite selectors organized by peer broad categories and topics; and
2. deterministic client-side **filtered search** using schema-defined facets and controlled vocabularies from validated YAML content.

The required broad categories are:

- **Common Features**;
- **Advanced Training**;
- **Cryokinesis**;
- **Pyrokinesis**;
- **Psychokinesis**;
- **Electrokinesis**.

There is no umbrella **Disciplines** category, no catch-all view that renders the complete rules corpus, and no unrestricted text-search field. Filtered search is a secondary route into the same validated topics and entities. It combines finite classifications such as rules area and feature role—for example, **Electrokinesis** plus **Rider**—and includes a finite single-select **Name** identity control generated from authoritative entity IDs and titles. The initial implementation uses a grouped native `<select>` plus an adjacent explicit **Open** button. Selection remains inert until activation, and no editable filtering or autocomplete is permitted. Filtered search is not a second content model.

Only `Kinetic_Vanguard.md` may be used as a migration input. During a one-time human-reviewed migration, every enumerated source unit in the pinned master file will receive an explicit disposition. The derivative Markdown files MUST NOT be used as migration inputs, fallback sources, or completeness evidence.

The browser application requires JavaScript. It will use plain HTML, CSS, and browser JavaScript, make no runtime network requests, and work directly through `file://`. It will not include character-sheet, combat-engine, calculator, account, or backend behavior.

A deterministic SQLite database MAY be generated from the validated normalized model as a non-authoritative derivative artifact for later tools. It MUST NOT be manually edited, used as a build authority, or contain rules content absent from `KineticVanguard.yaml`.

## Definitions

For this ADR:

- **Authority** means `KineticVanguard.yaml`, the sole source that may define Kinetic Vanguard rules meaning, classifications, and publication membership.
- **Entity** means a stable-ID rules object in the authority.
- **Publishable entity** means an entity intended for reader access in the publication. Every publishable entity is also a **filterable entity**; the terms describe the same set from rendering and filtered-search perspectives.
- **Topic** means a selector-reachable navigation container that renders one or more publishable entities.
- **Rule-significant leaf** means the smallest authoritative value, statement, relationship, option, table cell, exception, or projection input whose omission or alteration could change rules meaning.
- **Classification vector** means the complete set of required and applicable user-selectable controlled classification-facet assignments for one publishable entity. Identity-domain values and presentation metadata such as `primary_rules_area` are excluded.
- **Rules-area set** means the complete set of broad areas containing selector-reachable topics that render an entity.
- **Primary rules area** means one authored presentation-metadata member of an entity's rules-area set used only for Name-control grouping, default breadcrumb choice, deterministic ordering, and the default result-activation area when no single active rules-area filter determines another area.
- **Canonical topic map** means the `canonical_topic_by_area` presentation-metadata mapping from each rules area with more than one rendering topic for an entity to exactly one authoritative activation topic in that area.
- **Source unit** means one versioned inventory item produced from the pinned migration master under section 12.
- **Origin record** means the migration-evidence link from a publishable entity to one or more qualifying dispositioned source units or to an explicitly reviewed new-content decision.
- **Source-coverage report** means the committed deterministic partition of the pinned migration source into non-overlapping byte spans, each mapped exactly once to an inventoried source unit or a narrowly defined syntax-only exclusion.
- **Effective ledger view** means the deterministic terminal state produced by applying each valid non-branching amendment chain to the immutable original disposition ledger.
- **New-content decision** means a reviewed content-scoped evidence subject authorizing rules content that does not originate in the pinned migration master and recording its rationale, destination, rules-version effect, and review identity.
- **Human-perceivable string** means visible text or text exposed through accessibility APIs.
- **Derived non-rule output** means a human-perceivable count, application-version value, hash, state summary, or other closed-registry value computed from authoritative or build inputs without expressing game-rule meaning.
- **Provenance-safe composition** means a human-perceivable string assembled from a declared UI-text template whose literal segments come from one approved UI token and whose substitution slots accept only typed `AuthoritativeText` or typed `DerivedOutput` values. Each constituent retains its own provenance and coverage record; composition is not a fourth provenance class.
- **Atomic constituent** means one literal segment from the declared UI-text template, one non-nested `AuthoritativeText` slot value, or one non-nested `DerivedOutput` slot value within a provenance-safe composition.
- **Direct declared input** means a current repository file explicitly admitted by `build/inputs.json` and represented in the canonical declared-input path, role, and SHA-256 inventory.
- **Inherited migration provenance** means transitive provenance copied from accepted migration records, including the pinned Markdown source identity and digest, without making the historical source file a current build input.
- **Staged deterministic artifact** means an artifact produced by the declared build stages whose bytes are required to match across the clean double build.
- **Content-scoped evidence artifact** means a human review, attestation, or reviewed evidence-digest migration whose individual entries are tied to the narrowest stable subject digests they actually reviewed—such as source units and destination entities, new-content decisions and destinations, one entity classification, one correctness case, one deferral decision set, or a whole policy when the whole policy was reviewed. Each entry records both the version and SHA-256 of the content-evidence policy used to compute its subject digests. Unchanged entries remain reusable when unrelated subjects change.
- **Release-scoped evidence artifact** means a human-produced or non-byte-reproducible conformance record tied to one verified build-manifest hash, such as a manual screen-reader report or release-specific approval.
- **Recorded evidence artifact** means either a content-scoped or release-scoped evidence artifact. Recorded evidence is hashed into the release evidence record and excluded from byte comparison.
- **All Rules content view** means a screen or mode that renders the complete rules prose or equivalent full rules content as a catch-all publication. A filtered result list containing only titles, breadcrumbs, and classification metadata is not an All Rules content view, even when a saturated finite selection happens to return every publishable entity.
- Unless a field explicitly names another reviewed algorithm, every digest or hash required by this ADR is a SHA-256 digest over the canonical bytes defined for that artifact or subject.

## 1. Context and problem statement

The current baseline repository retains one active legacy rules document, `Kinetic_Vanguard.md`, imported from Kinetic Vanguard v12.1.0. Earlier working sets also contained five derivative Markdown views that duplicated substantial rules content and added view-specific examples; those derivative filenames remain explicitly prohibited migration and fallback inputs even though they are not present in the current repository baseline. The retained master also contains prose for an older executable combat-sheet workflow that is outside the v13 publication scope.

Earlier architecture drafts retained either multiple Markdown authorities or one Markdown authority with multiple publications. Both approaches preserved unnecessary document-management cost. Once the project no longer requires a long-form Markdown publication, Markdown provides less value as the canonical representation and forces the build to recover entities and relationships from headings, tables, and prose.

The v13 product is a compact interactive rules reference. Its information naturally consists of structured entities and relationships:

- common mechanics such as Blood Tax, Overload, Manifested Strike, Proficiency Bonus bands, and Manifested Strike die bands;
- shared subclass mechanics;
- Advanced Training features whose acquisition modes distinguish granted features from selectable options;
- four discipline-specific feature sets;
- activation types, costs, ranges, durations, targets, saves, damage expressions, tier modifications, and exceptions;
- level and progression bands;
- navigation categories, topics, authoritative titles, and related-topic links.

The project therefore needs an architecture that:

- provides one unambiguous authoring surface;
- represents rules concepts directly instead of inferring them from document formatting;
- produces one focused human-readable publication;
- supports both predictable taxonomy navigation and controlled faceted lookup;
- avoids duplicated prose and duplicated rule constants;
- prevents navigation, filter data, generated HTML, databases, or application code from becoming shadow rules sources;
- makes migration completeness and rendered coverage auditable;
- remains deterministic, testable, offline-capable, accessible, and usable through `file://`;
- excludes character-sheet, calculator, and combat-engine behavior.

## 2. Decision boundaries and lifecycle gates

This ADR separates architectural agreement from empirical implementation evidence and from day-to-day authoring feedback.

### 2.1 ADR acceptance

Moving this ADR from **Proposed** to **Accepted** means maintainers agree to the authority model, migration model, publication model, filtered-search model, accessibility target, and deterministic-release model described here.

Acceptance authorizes implementation and prototyping. It does not claim that implementation already conforms.

### 2.2 Migration acceptance

Migration acceptance occurs after the pinned v12.1 master has been fully dispositioned and transposed. It is governed by section 12.

### 2.3 Release conformance

A generated publication may be released only after the implementation passes the conformance requirements in sections 13 through 15.

Only a conforming release build may emit `KineticVanguard.html` into the deployable directory.

### 2.4 Authoring and prototype profiles

Development tooling MAY provide incremental schema diagnostics, subtree validation, selected-cluster rendering, and vertical-slice browser tests without running every release gate. These tools MUST NOT weaken the requirements applied to migration acceptance or release output.

A prototype build generated before release conformance MUST:

- be written only to the non-deployable artifacts directory;
- use the distinct filename `KineticVanguard.prototype.html`;
- display an unconditional, visually prominent **NON-RELEASE PROTOTYPE** banner;
- expose the same status to assistive technology;
- embed `release_status: prototype` in its provenance metadata;
- record `release_status: prototype` in its build manifest;
- remain distinguishable after being copied outside the repository.

A release build MUST embed and record `release_status: release` and MUST NOT contain the prototype banner.

Authoring tools MAY report incomplete publication coverage as diagnostics while working on an explicitly selected vertical slice. They MUST NOT label such output as a release, emit it to the deployable directory, or suppress the corresponding release failures.

### 2.5 Current repository and development-environment baseline

Revision 21 is grounded in repository `kmart01123/kinetic-vanguard` at commit `9c8d0bfb95b23ff724537acefaacefa01bad9538`.

The checked-in development container currently declares:

- VS Code devcontainer name **Kinetic Vanguard v13**;
- base image `mcr.microsoft.com/devcontainers/base:resolute`;
- Node.js `24.18.1` through `ghcr.io/devcontainers/features/node:1`;
- OS-provided Python through `ghcr.io/devcontainers/features/python:1`, with supplemental Python tools and JupyterLab installation disabled;
- GitHub CLI `2.97.0` through `ghcr.io/devcontainers/features/github-cli:1`;
- remote user `vscode`;
- `CODEX_HOME=/home/vscode/.codex` and `GH_CONFIG_DIR=/home/vscode/.config/gh`;
- named volumes `kinetic-vanguard-codex` and `kinetic-vanguard-gh` so Codex and GitHub CLI authentication/configuration survive container rebuilds;
- VS Code extensions `openai.chatgpt`, `redhat.vscode-yaml`, and `DavidAnson.vscode-markdownlint`;
- a post-create ownership and permissions step that creates the persisted configuration directories with mode `0700`;
- `.devcontainer/devcontainer-lock.json`, which pins the resolved devcontainer feature implementations: GitHub CLI feature `1.1.0` at `sha256:d22f50b70ed75339b4eed1ba9ecde3a1791f90e88d37936517e3bace0bbad671`, Node feature `1.7.1` at `sha256:8c0de46939b61958041700ee89e3493f3b2e4131a06dc46b4d9423427d06e5f6`, and Python feature `1.8.0` at `sha256:fbcad6955caeecc5ad3f7886baf652e25cba5225a6c4c2287c536de2e5607511`.

This is the current **development bootstrap profile**, not proof of release conformance. In particular, the base image is currently selected by the mutable `resolute` tag rather than an immutable image digest, and the repository does not yet contain the complete package-manager, dependency, browser-test, or accessibility-toolchain pins required by section 15. Before a release profile can conform, the selected environment specification MUST pin the base image by immutable digest or provide an explicitly reviewed equivalent reproducible identity, and MUST add every remaining toolchain pin required by the release profile.

Codex state, GitHub CLI credentials, user-specific configuration, and the contents of the two persistent volumes MUST NOT be direct declared build inputs, MUST NOT affect staged artifact bytes, and MUST NOT be copied into build artifacts or evidence. The devcontainer specification and lockfile may be declared environment inputs and therefore record that GitHub CLI and Python are installed, but the tools' mutable configuration, command output, and runtime behavior MUST NOT influence publication stages unless a later reviewed build-profile contract explicitly assigns a deterministic role. The authoritative build and publication architecture remains TypeScript/Node.js and browser-native HTML, CSS, and JavaScript.

## 3. Fixed inputs and outputs

### 3.1 Sole authoritative input

The authority manifest MUST contain exactly one rules authority:

| Role | Authoritative source |
|---|---|
| Complete Kinetic Vanguard rules, structured values, vocabularies, and publication membership | `KineticVanguard.yaml` |

No Markdown file, generated artifact, template, database, application source file, filter index, or external rules file may contain authoritative replacement rules content.

### 3.2 Canonical schema contract

`schema/KineticVanguard.schema.json` is the canonical reviewed structural contract.

- TypeScript types and validators MAY be generated from the JSON Schema.
- Generated TypeScript artifacts MUST NOT be manually edited.
- CI MUST regenerate derived schema/type artifacts and fail when the checked-in generated form differs.
- The schema MAY define application-structural enums such as rendering modes.
- Rules domains that may change with the game rules, such as damage types or activation vocabularies, SHOULD live in `KineticVanguard.yaml` and be referenced by stable IDs rather than independently enumerated in code.
- When the schema necessarily constrains a rules-adjacent domain, that constraint MUST be registered in `schema/rules-adjacent-constraints.yaml` with its schema path, rationale, and authority owner.
- CI MUST fail when the schema introduces or changes a rules-adjacent enum or constant without a matching reviewed register entry.

### 3.3 Restricted YAML profile

Although the authority uses YAML syntax, the canonical model MUST remain JSON-compatible.

The parser and linter MUST enforce:

- YAML 1.2 semantics;
- UTF-8 input;
- duplicate mapping keys are errors;
- anchors, aliases, merge keys, custom tags, and executable tags are prohibited;
- ambiguous scalars are quoted when intended as text;
- mapping order does not carry rules meaning;
- sequence order MAY carry explicit authored order;
- every reusable or independently targetable rules entity has a stable explicit ID;
- unknown schema properties are rejected by default;
- rule-significant numeric values are typed values, not extracted from display strings;
- where a typed representation exists, its visible projection MUST be generated and MUST NOT be separately authored as a duplicate value;
- concise prose MAY be authored as ordered statements or structured rich-text nodes defined by the schema;
- unrestricted embedded Markdown is not part of the authority format.

### 3.4 Allowed build inputs

The normal build MUST use the checked-in positive input manifest `build/inputs.json`. Inputs not listed in that manifest MUST fail the build.

The manifest MAY include:

- `KineticVanguard.yaml`;
- `schema/KineticVanguard.schema.json`;
- `policy/rules-versioning.md`;
- `schema/rules-adjacent-constraints.yaml`;
- the committed migration manifest, source-coverage report, source-unit inventory, disposition ledger, and accepted ledger-amendment files;
- application source files;
- templates;
- styles;
- `ui/approved-ui-text.json`;
- `ui/derived-output-registry.json`;
- `ui/filter-interaction-policy.json`, including the sole filtered-result stable-sort policy, deterministic result-activation-area policy, Name placeholder and reset policy, inactive accessible-name and persistent-description policy, focusable aria-disabled activation policy, composed accessible-name policy, authoritative-heading focus policy, direct-route and history-restoration placeholder policy, the closed `history.state` field and focus-origin allowlist, and deterministic settled-state test hook;
- `review/content-evidence-policy.json`, containing an explicit policy version and defining canonical subject serialization, per-entry digest calculation, attestation scope rules, reviewed digest-migration rules, and current-subject coverage validation;
- `review/content-evidence-policy-registry.json`, the append-only accepted binding of every content-evidence-policy version to exactly one policy SHA-256;
- `tests/filtered-search-correctness.yaml`;
- `tests/accessibility-scanner-config.*`;
- `tests/accessibility-manual-script.md`;
- `tests/accessibility-matrix.yaml`;
- `tests/accessibility-known-issues.yaml`;
- `release/release-evidence-schema.json`;
- `.devcontainer/devcontainer.json` and `.devcontainer/devcontainer-lock.json` when the selected profile uses the checked-in devcontainer as its environment specification;
- package manifests and dependency lockfiles;
- selected build-profile and deterministic-build configuration;
- generated TypeScript/schema artifacts whose regeneration is verified;
- pinned SQLite bindings and generation configuration when SQLite output is enabled;
- browser-test fixtures and test implementations that contain no replacement rules content;
- release-evidence configuration explicitly listed above. Filter integrity corpora are generated evidence; filter correctness corpora are independently reviewed evidence. None is a rules authority or generic rules fixture.

`ui/approved-ui-text.json` is permitted only under the constraints in section 9.4. It is a source of generic interface chrome, not rules content and not filter-index content.

Content-scoped and release-scoped evidence artifacts, including `review/content-evidence-migrations/*.json`, migration or classification attestations, manual reports, and `artifacts/release-evidence.json`, are not normal build inputs. They MUST NOT appear in `build/inputs.json`, affect staged publication bytes, or enter clean-build byte comparison. They are validated and hashed only during the evidence and promotion lifecycle in sections 5.5, 12, 14, 15, and 19.

Markdown rules documents are not permitted normal-build inputs.

### 3.5 Sole migration input

The migration process MUST accept exactly one Markdown rules input:

- `Kinetic_Vanguard.md`.

Before migration begins, the exact input bytes MUST be pinned by SHA-256 in a checked-in migration manifest.

The following files are legacy derivatives and MUST NOT be ingested, imported, parsed, consulted as fallback sources, or used as completeness checks:

- `DM_Quick_Reference.md`;
- `Cryokinesis.md`;
- `Pyrokinesis.md`;
- `Psychokinesis.md`;
- `Electrokinesis.md`.

Missing or ambiguous information MUST be resolved by human review of the pinned master source or explicitly recorded as unresolved. It MUST NOT be filled from a derivative file. Any ledger entry involving ambiguity resolution MUST cite the pinned-master location and include an attestation that no derivative Markdown source was used to supply the resolution.

### 3.6 Deployable and non-deployable outputs

The deployable output directory MUST contain exactly one file:

| Output role | Required file | Source basis |
|---|---|---|
| Complete interactive Kinetic Vanguard reference | `KineticVanguard.html` | `KineticVanguard.yaml` |

Release promotion MUST construct a fresh temporary deployable directory, place exactly `KineticVanguard.html` within it, validate that inventory, and atomically replace the prior deployable directory. Stale or foreign files in the prior directory MUST NOT survive promotion and MUST NOT permanently block remediation. A prototype build MUST NOT write to this directory.

Non-deployable outputs MUST be written to a separate artifacts directory and classified as follows.

**Staged deterministic artifacts** MAY include only the configured members of this closed set:

- `KineticVanguard.prototype.html` or staged release `KineticVanguard.html`;
- the normalized debug JSON when retained;
- the filter-index artifact when retained separately;
- the generated filtered-search integrity report;
- the generated effective-ledger view;
- coverage and provenance ledgers;
- canonical SQLite when enabled;
- deterministic machine-readable validation summaries explicitly configured for retention;
- the deterministic build manifest.

**Content-scoped evidence artifacts** MAY include:

- migration-review reports and migration-review attestations;
- reviewed new-content-decision records and attestations;
- classification second-pass attestations;
- filtered-search correctness-review attestations;
- accepted migration-deferral decisions and aggregate migration-deferral review;
- reviewed content-evidence digest-migration records.

A content-scoped evidence artifact MAY contain multiple independently scoped attestation entries. Each entry MUST conform to `review/content-evidence-policy.json`, record both the policy version and policy SHA-256 used to calculate its subject digests, and identify the narrowest stable subject IDs and canonical subject digests it actually reviewed. Subject scopes MUST be appropriate to the review:

- source-migration entries reference the reviewed source-unit digest, effective qualifying disposition and amendment-chain digest, and destination entity or leaf digests;
- new-content entries reference the reviewed new-content-decision ID and digest and destination entity or leaf digests;
- classification entries reference one publishable entity ID and its canonical classification digest;
- filtered-search correctness entries reference one correctness-case ID and canonical case digest;
- deferral entries reference the exact deferral-decision IDs and canonical aggregate-set digest reviewed;
- policy attestations reference the whole policy digest only when the whole policy is the review subject.

An attestation entry MUST NOT claim validity after one of its declared subject digests changes. A change to an unrelated entity, source unit, case, or policy MUST NOT invalidate otherwise current entries. Every lifecycle gate that consumes content evidence MUST prove the complete current coverage required by that gate using valid entries rather than requiring wholesale re-attestation of unchanged subjects.

`review/content-evidence-policy.json` MUST use canonical formatting and declare an explicit monotonically advancing `policy_version`. `review/content-evidence-policy-registry.json` MUST be append-only and MUST bind every accepted `policy_version` to exactly one immutable policy SHA-256 and acceptance reference. The current policy version and SHA-256 MUST appear in the registry. A version appearing with more than one digest, a current version absent from the registry, or deletion or mutation of an accepted historical binding outside an explicitly governed repository-history correction MUST fail validation. Any byte change to canonical subject serialization, subject formation, digest calculation, attestation scope, migration rules, or coverage semantics MUST increment the version. A policy-version change MUST use exactly one of these paths:

- all affected subjects receive fresh review and new attestation entries computed under the new policy version; or
- a reviewed digest-migration record maps every affected prior subject ID and digest to its replacement digest under the new policy version and attests that the canonical reviewed subject content and review conclusion did not change.

A digest-migration record MUST declare the old and new policy versions and policy hashes, the deterministic migration implementation or procedure, every mapped subject ID and old/new digest pair, reviewer identity, and the assertion basis for semantic equivalence. It MUST NOT preserve an attestation when reviewed subject content, scope, or conclusion changed; those subjects require fresh review. Every lifecycle gate that reuses a prior attestation MUST verify a complete, non-branching migration chain from the entry's recorded policy version and policy SHA-256 to the current policy version and policy SHA-256. An unmapped, ambiguous, or content-changing transition MUST invalidate the affected entry.

**Release-scoped evidence artifacts** MAY include:

- accessibility scanner and browser-run reports that are not configured as deterministic staged outputs;
- the manual screen-reader report;
- release-specific accepted-known-issue approvals;
- the per-release aggregate deferral re-review;
- the release evidence record.

Each release-scoped evidence artifact other than the release evidence record itself MUST reference the verified deterministic build-manifest hash for the publication it evaluates.

All required recorded evidence artifacts other than the release evidence record itself MUST be hashed by the release evidence record. They are release-gating evidence but are excluded from clean-build byte comparison.

These artifacts are not rules publications and MUST NOT be required by the release browser application. Prototype HTML remains subject to the identity requirements in section 2.4.

## 4. Source-authority rules

1. `KineticVanguard.yaml` is the sole authority for v13 rules meaning, typed values, relationships, filter classifications, and publication membership.
2. This ADR governs architecture and process only. It MUST NOT be used as a rules source, and `KineticVanguard.yaml` prevails in any rules-content conflict.
3. The schema defines the reviewed data contract and may constrain registered rules-adjacent domains; it MUST NOT contain replacement feature prose or independent feature values.
4. Generated HTML, SQLite, normalized JSON, filter indexes, test corpora, migration evidence, review documents, and browser state are non-authoritative derived representations or evidence.
5. Every publishable entity MUST belong to at least one selector-reachable topic **and** MUST be included in filtered search under its complete authoritative classification vector. Every publishable topic MUST remain reachable through the selector hierarchy.
6. Navigation and filtered-search definitions MUST reference stable entity, topic, facet, and vocabulary IDs and MUST NOT contain replacement rules prose or independent rule constants.
7. Application code and templates MUST NOT contain feature descriptions, costs, ranges, durations, level gates, progression values, formulas, classifications, or rule exceptions that belong in YAML.
8. A rule-significant value or classification needed by only one topic MUST still be authored in YAML.
9. Reuse occurs by referencing stable IDs, never by copying authored rules into multiple source locations.
10. Normalized objects, display projections, generated tables, facet counts, result sets, coverage indexes, and database rows remain derived data.
11. Missing source data MUST fail validation. The build MUST NOT infer it from derivative Markdown, this ADR, generated HTML, SQLite, browser code, approved UI text, or review evidence.
12. The build MUST NOT automatically rewrite the authoritative YAML.
13. Migration decisions that consolidate, rewrite, correct, remove, defer, or drop content from the pinned master MUST be recorded in the migration ledger or a versioned amendment.
14. Every publishable entity MUST carry an accepted origin record before migration acceptance or release.
15. Approved UI text and derived non-rule outputs MUST remain generic interface or provenance material and MUST never serve as a source for topic content, result labels, facet labels, facet values, rule values, or filter classifications.

## 5. Versioning and provenance

Rules-source version, schema version, migration-source identity, and application version MUST remain distinct.

### 5.1 Rules and schema versions

`KineticVanguard.yaml` MUST contain explicit version fields similar to:

```yaml
schema_version: "1.0.0"
rules_version: "13.0.0"
```

- `rules_version` identifies the represented Kinetic Vanguard rules release.
- `schema_version` identifies the authority contract.
- Rules-meaning changes MUST increment `rules_version` according to `policy/rules-versioning.md`.
- Structural migrations preserving rule meaning MAY change `schema_version` without changing `rules_version`.
- The authoritative YAML SHA-256 MUST be recorded in the build manifest and embedded as provenance metadata in the generated HTML.

### 5.2 Application version

- Browser behavior and the build system MUST have a separate SemVer application version.
- The HTML MUST visibly distinguish **Rules version** from **Application version**.
- Application changes MUST NOT silently alter `rules_version`.
- Rules changes MUST NOT silently alter the application version.

### 5.3 Migration provenance

The checked-in migration manifest MUST record:

- the migration source filename;
- the migration source SHA-256;
- the exact repository commit containing the pinned migration source;
- the source-unit enumeration algorithm version;
- the committed source-coverage report filename and SHA-256;
- the committed source-unit inventory filename and SHA-256;
- the disposition-ledger format version and SHA-256;
- date or reproducible epoch of migration acceptance;
- reviewer identities or review references.

The source-coverage report and enumerated source-unit inventory MUST be committed alongside the disposition ledger. For every unit it MUST retain the unit ID, unit type, source location, content digest, and sufficient normalized source text to verify the disposition without re-running a later algorithm version.

A change to the enumeration algorithm after an inventory has been reviewed MUST either:

- produce a new inventory and complete new disposition ledger; or
- provide an explicit reviewed mapping from every old unit ID to its replacement unit ID or IDs.

The migration source MAY be removed from the active rules tree only after its digest, exact repository commit, committed unit inventory, and complete disposition ledger are recorded and migration acceptance succeeds.

### 5.4 Build provenance

The deterministic build manifest MUST distinguish build identity, direct declared inputs, inherited migration provenance, and generated staged artifacts.

**Build identity** MUST record:

- release status (`prototype` or `release`);
- rules version;
- schema version;
- application version;
- exact repository commit used by the selected build;
- selected build-profile and deterministic-build-configuration identifiers and SHA-256 values;
- locked Node.js, dependency, package-manager, browser-test, and accessibility-tool versions;
- the selected environment-specification path and SHA-256, including `.devcontainer/devcontainer.json` and `.devcontainer/devcontainer-lock.json` when they define the selected profile;
- the resolved base-container image digest or reviewed equivalent reproducible environment identity;
- resolved devcontainer-feature implementation versions and digests when devcontainer features are used;
- pinned SQLite library or binding version when SQLite is generated;
- deterministic environment identity.

**Direct declared inputs** MUST be represented by:

- `build/inputs.json` SHA-256; and
- a canonical `declared_inputs` inventory containing the repository-relative path, role, and SHA-256 of every current file admitted by `build/inputs.json`.

The inventory MUST include, when enabled or required by the selected profile, the migration manifest, source-coverage report, source-unit inventory, immutable disposition ledger, accepted amendment files, authoritative YAML, schema, generated contracts, rules-adjacent constraint register, rules-versioning policy, UI resources, filtered-search policy and correctness corpus, content-evidence policy and append-only policy registry, accessibility configuration and scripts, release-evidence schema, application source, templates, styles, browser tests, fixtures, package manifests, dependency lockfiles, selected environment specifications and environment lockfiles, deterministic-build configuration, selected-profile configuration, and SQLite configuration.

Every explicitly named direct-input hash elsewhere in the manifest MUST equal the corresponding `declared_inputs` entry. A direct admitted input missing from that inventory, a path/hash mismatch, or an inventory entry not authorized by `build/inputs.json` MUST fail the build.

**Inherited migration provenance** MUST be copied from the checked-in migration manifest into a distinct `inherited_provenance` object containing at least:

- migration-source filename;
- migration-source SHA-256;
- exact repository commit containing the pinned migration source;
- source-unit enumeration and coverage-algorithm version.

The original Markdown source file is not a direct declared input and MUST NOT appear in `build/inputs.json` or the canonical `declared_inputs` inventory merely because its inherited digest is recorded. Direct-input inventory equality rules do not apply to inherited migration provenance.

**Generated staged-artifact hashes** MUST include:

- generated effective-ledger-view SHA-256;
- generated HTML SHA-256;
- SHA-256 values of every other configured staged deterministic artifact except the manifest itself.

The retained staged deterministic artifact set is closed by section 3.6 and the selected build profile. A generated staged artifact, including the effective-ledger view, MUST NOT be treated as a fixed input to the invocation that generates it. The manifest MUST NOT hash itself and MUST NOT hash content-scoped or release-scoped evidence artifacts, including reviewed content-evidence digest-migration records.

The HTML MUST NOT embed its own digest. The manifest MUST contain the generated HTML digest. The manifest's own digest, if needed, MUST be recorded by the release evidence record rather than recursively embedded within itself.

Wall-clock timestamps MUST be omitted from deterministic artifacts unless supplied through an explicit reproducible input such as `SOURCE_DATE_EPOCH`.

### 5.5 Release evidence

Content-scoped evidence validation and release binding are separate lifecycle operations.

**Content validity** MUST be checked whenever a lifecycle gate consumes content evidence, including migration acceptance and later release validation. Content-validity checks MUST validate:

- current subject IDs and subject digests;
- the recorded content-evidence-policy version and policy SHA-256;
- the immutable version/hash binding in `review/content-evidence-policy-registry.json`;
- every required non-branching digest-migration chain;
- the semantic-equivalence basis for reused attestations;
- complete current coverage for every subject set required by that gate.

Content validity MUST NOT depend on a deterministic build-manifest hash.

**Release binding** occurs only after the clean double build fixes the verified deterministic build-manifest hash. It binds release-scoped evidence to that build and hashes the already content-valid content-scoped evidence, accepted digest-migration records, subject-coverage maps, and release-scoped evidence into the release evidence record.

`artifacts/release-evidence.json` is a release-scoped evidence artifact created only after:

1. two clean staged builds have produced matching staged deterministic artifacts;
2. the verified deterministic build-manifest hash is fixed;
3. current content-scoped evidence has been revalidated for content validity; and
4. required release-scoped evidence has been produced against the verified staged publication.

It MUST conform to `release/release-evidence-schema.json` and record:

- the deterministic build-manifest SHA-256;
- the authoritative YAML SHA-256;
- hashes of required content-scoped evidence artifacts, every included attestation entry's recorded content-evidence-policy version and SHA-256 plus declared subject IDs and digests, accepted digest-migration chains, and the computed coverage sets for current source-migration, new-content-origin, classification, correctness, and deferral subjects;
- the current content-evidence-policy-registry SHA-256;
- hashes of required release-scoped evidence artifacts other than the release evidence record itself;
- migration and classification-review attestation references;
- manual accessibility report hash;
- release-specific accepted-known-issue approval hashes;
- per-release aggregate deferral-review hash together with the effective-ledger-view, amendment-set, and current deferral-decision-set digests it reviewed;
- release approver identity;
- release decision and date.

The release evidence record is not a build input, is not embedded into the staged publication, and is excluded from byte-identical comparison.

Promotion MUST fail when:

- the release evidence record is missing;
- it references a different build-manifest hash;
- any required content-scoped attestation entry references a stale declared subject digest, records a policy version/hash pair absent from or conflicting with the accepted policy registry, lacks a valid migration chain from its recorded content-evidence-policy version and SHA-256 to the current version and SHA-256, or the current source-migration, new-content-origin, classification, correctness-case, or deferral subject sets lack complete valid attestation coverage;
- a required release-scoped evidence artifact references another build;
- a required evidence hash or approval is absent.

## 6. Authoritative data model

The authority SHOULD contain concepts similar to:

- `metadata`: title, versions, attribution, license, compatibility, and release notes;
- `vocabularies`: stable IDs and labels for rules domains that should not live independently in code;
- `glossary`: stable term IDs, abbreviations, labels, and concise definitions;
- `progressions`: level bands, Proficiency Bonus, Psi progression, Manifested Strike die, and other authored tables;
- `common_features`: shared mechanics, timing interactions, and subclass systems;
- `advanced_training`: granted and selectable feature definitions, acquisition mode, level gates, and prerequisites;
- `disciplines`: one object per discipline with its features and discipline-specific rules;
- `features`: stable entities with typed activation, level, cost, target, range, duration, save, damage, conditions, tier modifications, exceptions, and ordered rule statements;
- `navigation`: category and topic ordering, topic membership, related-topic links, defaults, and fragment keys;
- `facets`: controlled facet definitions, value domains, labels, ordering, cardinality, applicability rules, and the finite entity-name identity facet;
- `classifications`: stable user-selectable facet-value references attached to every publishable entity, including complete `rules_area` membership;
- `presentation_metadata`: non-facet publication metadata such as one `primary_rules_area` used for Name grouping, default breadcrumb choice, and stable ordering, plus `canonical_topic_by_area` for every rules area in which the entity has multiple rendering topics;
- `origins`: links from each publishable entity to qualifying dispositioned source units or reviewed new-content decisions;
- `new_content_decisions`: stable references to reviewed content-scoped decision records for publishable rules content not derived from the pinned migration master;
- `audits`: non-authoritative consistency assertions using source paths or IDs.

`origins`, `new_content_decisions`, and `audits` belong to the closed **provenance and evidence metadata** leaf class defined in section 13.1. They MUST NOT carry playable rules meaning or replacement display prose and MUST NOT be rendered as rules content.

Aliases are not part of the initial authority model. A future alias mechanism requires a named consumer, structural constraints, provenance classification, and a follow-on schema decision.

The exact schema is not frozen by this illustrative list. The implementation schema is reviewed separately through normal repository review.

The normalized TypeScript representation MUST:

- be created only from schema-valid YAML;
- preserve stable IDs and source paths for diagnostics;
- assign a stable provenance path to every rule-significant leaf;
- use typed numbers, references, and enums for rule-significant values;
- make invalid states unrepresentable where practical;
- remain immutable during a build;
- MAY be serialized as deterministic debug JSON;
- MUST NOT be manually edited or checked in as a second authority.

### 6.1 Authoring support

A content-free schema, parser, renderer, and tooling spike MAY occur before the migration source is pinned. No rule text, rule value, classification, or semantic adaptation derived from `Kinetic_Vanguard.md` may enter `KineticVanguard.yaml` until the checked-in migration manifest has pinned the exact source filename, SHA-256, and repository commit.

After that pin exists and before full migration, the schema and authoring tooling MUST prove a vertical slice containing shared mechanics, an exception-heavy feature, a progression table, Advanced Training acquisition modes, one discipline, navigation, and filtered search.

Rules content entered for the vertical slice is provisional migration content. Before migration acceptance:

- every publishable vertical-slice entity MUST receive an origin record linking it to one or more dispositioned source units or to an explicitly reviewed new-content decision;
- provisional entities MUST be reconciled after the committed source-unit inventory exists;
- any entity with neither a dispositioned source-unit origin nor a reviewed new-content decision is an entity-side orphan and MUST fail migration acceptance;
- any provisional wording or classification changed during reconciliation MUST be reviewed under the same migration and rules-version requirements as other authority content.

The schema MUST support readable structured prose through reviewed node types for paragraphs, ordered or unordered lists, term references, emphasis, notes, and tables where needed. It MUST NOT force semantically distinct clauses into lossy flat strings merely to satisfy the schema.

Development tooling SHOULD provide:

- editor schema completion and validation;
- focused entity or cluster validation;
- a generated human-readable review projection;
- diagnostics that report multiple actionable errors in one run;
- deterministic formatting without rewriting rules meaning;
- commands that generate integrity corpora and lint derived-output registry bindings without producing release evidence;
- commands that identify changed content-evidence subjects, preserve still-current attestation entries, generate reviewed digest-migration candidates when only canonical serialization changes, and generate the current subject-coverage report without auto-approving any review or semantic-equivalence claim.

Generated review projections and temporary working notes MUST remain non-authoritative and MUST NOT be accepted as fallback rules sources.

## 7. Cascading navigation

### 7.1 Broad categories

The broad-category selector MUST contain these peer categories:

1. **Common Features**;
2. **Advanced Training**;
3. **Cryokinesis**;
4. **Pyrokinesis**;
5. **Psychokinesis**;
6. **Electrokinesis**.

There is no umbrella **Disciplines** category. Named mechanics in this subsection are illustrative rather than rules-authoritative.

**Common Features** contains shared mechanics and progressions. **Advanced Training** contains the complete Advanced Training system. The data model and publication MUST visibly distinguish granted features from selectable options without this ADR asserting which specific features occupy those classes. Each discipline category contains that discipline's authoritative entities.

### 7.2 Dependent selectors

Selecting a broad category MUST populate a dependent topic selector with only topics valid for that category.

A category MAY define another finite dependent selector when a topic naturally has a second bounded level of organization. Additional selectors MUST derive their options from validated upstream selections and MUST NOT accept arbitrary text or numbers.

Every topic option MUST resolve to at least one publishable entity, and every publishable entity MUST belong to at least one topic.

For every publishable entity, semantic validation MUST derive the set of broad areas containing its selector-reachable topics and require exact equality with the entity's independently authored `rules_area` classification set. This is a deliberate redundancy check between authored classification intent and authored publication composition; a mismatch means the maintainer MUST decide whether the classification or navigation is wrong rather than treating either as automatically derived.

The entity's `primary_rules_area` presentation metadata MUST be exactly one member of that set. Exact equality intentionally means that an entity may be returned by an area filter only when at least one selector-reachable topic in that area renders it. If an entity is intended to be discoverable through area A, publication navigation MUST include at least one selector-reachable topic in area A that renders that entity. An entity that merely pertains to another area but is not rendered there MAY be linked as a related entity, but MUST NOT claim that area in `rules_area`.

Authoring diagnostics for an equality failure SHOULD name the entity, each authored-but-unrendered area, and each rendered-but-unauthored area so the maintainer can decide which side is wrong.

### 7.3 Navigation labels

Navigation labels MUST be derived from one of the following:

- a referenced entity or topic's authoritative `title`;
- an authoritative `short_title` stored with that entity or topic;
- a rule-neutral category label declared in `KineticVanguard.yaml`.

Navigation MUST NOT contain inline arbitrary labels that introduce rule values, formulas, dice expressions, level limits, costs, or exceptions.

### 7.4 Fragment routing

URL fragments MAY retain category, topic, subtopic, active classification-facet selections, and an activated entity route. Activated entity routes are distinct from transient Name-control selection.

Bounded `history.state` MAY retain only fields explicitly allowlisted by `ui/filter-interaction-policy.json`: validated category, topic, subtopic, classification-selection, activated-entity, and result-route IDs plus a finite focus-origin enum. Undeclared keys and free-form string payloads are prohibited. `history.state` MUST NOT contain rules prose, entity descriptions, rendered HTML, arbitrary user text, or durable preferences.

An unactivated Name selection is transient DOM state. It MUST NOT be encoded in the URL fragment, written to `history.state`, or otherwise persisted. Changing an unactivated Name selection MUST NOT invoke `pushState` or `replaceState`. Any route restoration MUST use the Name placeholder unless a new Name value is deliberately selected in the restored page state.

The runtime MUST:

- decode only declared route, facet, value, entity, and topic IDs;
- validate classification facet values against authoritative controlled vocabularies;
- validate Name identity values against the declared entity-identity projection;
- discard well-formed but non-authoritative IDs and selections beyond declared facet cardinality;
- normalize a fragment that contains both an activated Name identity route and classification selections according to the mutually exclusive Name-activation policy in section 8.1;
- issue at most one consolidated accessible notice on initial load, combining fragment correction and resulting route or filter state;
- normalize corrected state back into the URL with `replaceState`;
- use `replaceState` when normalizing the initial route;
- use `pushState` for deliberate user navigation that should be traversable, including activation of the Name control's adjacent navigation button;
- preserve the pre-activation classification state in the prior history entry;
- restore selector, filter, result, topic, and recorded focus-origin state on browser back and forward navigation;
- fall back to a valid configured default when no valid route remains;
- announce fragment-driven topic changes accessibly;
- avoid unexpected focus movement.

The number of fragment selections is bounded by the finite declared facet domains. Category, topic, subtopic, classification-filter, and activated entity-route state may be shareable through the fragment; bounded route snapshots and focus origin may exist in `history.state`. No rules-reference state may be stored in `localStorage`, `sessionStorage`, IndexedDB, cookies, Cache Storage, service workers, a backend, or another durable persistence mechanism.

## 8. Filtered search

### 8.1 Filtered-search role

Filtered search is a deterministic faceted lookup over the same publishable entities and topic routes used by cascading navigation. It MUST NOT index arbitrary prose, accept unrestricted user text, rank natural-language relevance, generate excerpts, or create an alternate rules publication.

Every publishable entity is filterable. The interface MUST expose:

- controlled classification facets; and
- a finite single-select **Name** identity control projected from authoritative publishable-entity IDs and titles.

The Name control is a permanent complete title index grouped by `primary_rules_area`. Publishable titles MUST be unique within each `primary_rules_area` optgroup; a duplicate visible Name label within one optgroup MUST fail semantic validation. The initial implementation MUST use a native `<select>` with `<optgroup>` groups and ordinary `<option>` values. Native first-letter selection behavior is permitted. Editable filtering, autocomplete, substring matching, fuzzy matching, and custom text input are prohibited.

Every entity rendered by more than one selector-reachable topic in any rules area MUST declare one `canonical_topic_by_area` entry for that area. Name activation uses the canonical or sole topic in `primary_rules_area`. Area-scoped filtered-result activation uses the canonical or sole topic in the deterministic result-activation area defined in section 8.4.

Name selection and Name activation are separate operations:

1. the Name `<select>` MUST begin with a non-entity placeholder option whose approved UI-text label is **Select a rule by name**;
2. the placeholder MUST be selected in the default unactivated state and immediately after any Name-state reset; a user MAY subsequently select a Name value while classification facets remain active, but selection alone remains inert until Open activation;
3. an initial direct entity route, a validated shared fragment, browser Back, or browser Forward MUST leave the Name select on the placeholder; arriving at or restoring an entity topic MUST NOT auto-select its identity option;
4. changing the selected Name value MUST NOT navigate, clear classification filters, update the topic route, move focus, or otherwise cause a change of context;
5. an adjacent **Open** button, programmatically associated with the Name control and persistent instruction text, performs activation;
6. while the placeholder is selected or no valid target exists, the Open button MUST remain focusable, expose `aria-disabled="true"`, use the approved static accessible name **Open selected rule**, and reference the approved persistent description **Select a rule name, then choose Open.** through `aria-describedby`;
7. activating Open while it is aria-disabled MUST be inert: it MUST NOT navigate, change route or selection state, move focus, or emit a live-region announcement; the persistent accessible description is the required instruction;
8. when a valid Name value is selected, Open MUST expose `aria-disabled="false"`; the visible button label remains the generic UI verb **Open** and its accessible name MUST be produced by the provenance-safe UI template **Open {entity_title}**, whose slot accepts the selected entity's authoritative title; the persistent description MAY remain associated;
9. activating a valid Open target MUST use `pushState`, preserve the prior classification-filter state in browser history, clear classification facets only in the newly activated route state, render the entity's canonical or sole topic in its primary rules area, reset the destination-state Name control to the placeholder with Open aria-disabled, and move focus under the policy in `ui/filter-interaction-policy.json`;
10. browser Back MUST restore the complete prior route and classification state with the Name placeholder selected and Open aria-disabled; browser Forward to the activated destination MUST restore that destination with the placeholder selected and Open aria-disabled.

The required focus destination after valid Name activation is the rendered authoritative entity heading. The heading MUST be programmatically focusable with `tabindex="-1"` and retain its native heading semantics and authoritative title text. Name activation MUST NOT separately repeat the entity title through the live region. When activation clears classification selections, at most one polite message MAY report that state correction without repeating the title.

Selecting or changing any classification facet resets the Name select to the placeholder and makes Open aria-disabled, regardless of whether the previous Name selection had been activated or merely selected. Name options remain enabled regardless of classification-filter state because a later Name activation establishes a new mutually exclusive route state.

Until at least one classification facet value is selected, the classification-results region MUST display instructions rather than results. This empty-state rule does not hide the separate finite Name title index and is not the definition of the All Rules prohibition. A saturated finite classification selection MAY return every publishable entity as a metadata-only result list. It MUST NOT render the complete rules prose or equivalent catch-all content.

### 8.2 Facets and controlled vocabularies

Every classification facet and every controlled classification value MUST be declared in `KineticVanguard.yaml`. Additional vocabulary files are not permitted.

The only permitted derived facet-value domain is the `entity_name` identity domain, projected deterministically from publishable entity IDs and authoritative titles by a reviewed projection function declared in the schema contract. No other derived facet-value domain is permitted without an ADR amendment.

Each classification facet definition MUST include:

- a stable facet ID;
- an authoritative label path;
- single-select or multi-select cardinality;
- applicability rules;
- requiredness rules;
- deterministic ordering;
- a closed controlled value domain.

The initial classification model MUST include:

- `rules_area`: required and multi-select for every publishable entity;
- `entity_kind`: required and single-select for every publishable entity;
- `feature_role`: required and single-select for every entity whose `entity_kind` is `feature`;
- `acquisition_mode`: required and single-select for every Advanced Training feature.

The initial identity and presentation model additionally MUST include:

- `entity_name`: the sole derived identity domain, single-select and projected from publishable entity IDs and titles;
- `primary_rules_area`: required single-valued presentation metadata for every publishable entity, constrained to one member of `rules_area`, and not a facet or member of the classification vector;
- `canonical_topic_by_area`: a map from rules-area ID to topic ID. For every area in which an entity is rendered by more than one selector-reachable topic, the map MUST contain exactly one entry naming a topic in that area that renders the entity. An area with exactly one rendering topic MAY omit the entry; the sole topic is then canonical by construction.

Other controlled facets MAY include activation type, damage type, level band, resource interaction, or other finite classifications justified by lookup needs. An optional facet MUST have explicit applicability conditions; a classification required by those conditions cannot be omitted.

A representative shape is:

```yaml
classifications:
  rules_area: [common_features, electrokinesis]
  entity_kind: feature
  feature_role: rider
presentation_metadata:
  primary_rules_area: electrokinesis
  canonical_topic_by_area:
    electrokinesis: electrokinesis_riders
```

Entity classifications MUST reference declared facet and value IDs. Unknown facets, unknown values, duplicate single-valued classifications, invalid applicability, missing required classifications, or a feature without `feature_role` MUST fail semantic validation. A missing `primary_rules_area`, a primary area outside `rules_area`, a duplicate Name label within one primary-area group, a missing required canonical-area entry, an entry for an area that does not render the entity, or an entry naming a topic that does not belong to the keyed area or render the entity MUST fail presentation-metadata semantic validation.

Every zero-result classification value MUST remain visible and disabled. Per-facet enable-versus-disable configuration is not permitted.

Arbitrary tags, inferred keywords, aliases, tokenized rules prose, and approved UI text MUST NOT become facet values.

### 8.3 Matching, identity, ordering, and availability semantics

Classification matching is exact and deterministic:

- selections across different classification facets are combined with logical **AND**;
- multiple selected values within a multi-select classification facet are combined with logical **OR**;
- an unselected classification facet imposes no constraint;
- result ordering follows only the stable sort declared in `ui/filter-interaction-policy.json`; navigation order or another authority sequence does not independently alter filtered-result ordering.

The Name identity control is mutually exclusive with classification filtering only after explicit Open-button activation. Changing the Name selection is inert except for updating the Open button's aria-disabled state and composed accessible name. Name options MUST remain enabled regardless of current classification availability. Activating Open clears conflicting filters only in the new route state while browser history retains the prior state. Selecting any classification facet resets the Name control to its placeholder, regardless of whether the previously displayed Name identity had been activated.

The canonical classification case:

```text
rules_area = electrokinesis
feature_role = rider
```

returns the independently reviewed complete set of publishable entities classified as both Electrokinesis and a rider, including entities that also appear in other rules areas.

The classification interface SHOULD display the result count for each currently available facet value. Counts and availability are derived non-rule outputs. A classification value that would produce no matching result MUST remain present but disabled; it MUST NOT be hidden. Focus MUST remain stable. If an upstream change invalidates a selected dependent value, the runtime MUST clear it once and include that correction in the consolidated accessible announcement.

### 8.4 Results

Each classification result MUST resolve to one deterministic selector route and MAY focus a specific entity within its topic.

The result-activation area MUST be selected deterministically:

1. when exactly one `rules_area` value is actively selected and the entity belongs to it, use that area;
2. otherwise use the entity's `primary_rules_area`.

Within the result-activation area, activation uses the entity's `canonical_topic_by_area` entry when the entity has multiple rendering topics in that area, or the sole rendering topic when only one exists.

Every result control's visible identity label and accessible name MUST use the provenance-safe composition:

`{entity_title} — {primary_rules_area_label}`

The template is applied uniformly, even when no title collision exists. Both slot values are authoritative text from the normalized model; the em dash and surrounding spaces are approved generic UI-token literal segments. The composition is presentation-only and MUST NOT create an alias or a second authoritative title.

A result MAY additionally display only:

- authoritative topic and category breadcrumbs;
- authoritative selected facet labels and values;
- a generic derived result status such as the match count.

A **result identity label** is the required composed title-and-primary-area label. A **result status** is generic non-rule state such as “3 matches” or “No matches,” produced under the derived-output registry. These terms are not interchangeable.

Results MUST NOT:

- display rule statements, snippets, excerpts, summaries, formulas, costs, or other rules prose;
- contain a label or classification absent from the normalized model;
- introduce independent ordering or grouping rules not declared by `ui/filter-interaction-policy.json`; authoritative labels and classifications may be displayed but do not create a second result-ordering policy;
- require a network request;
- persist the user's selections or history outside the URL fragment and current DOM state;
- create an All Rules content view.

### 8.5 Filtered-search accessibility

Filtered search MUST include:

- persistent accessible labels and instructions for every facet control;
- persistent instruction text associated with the Name select and Open button explaining that selection alone does not navigate;
- a focusable aria-disabled Open button whose inactive accessible name is **Open selected rule** and whose persistent accessible description is **Select a rule name, then choose Open.**;
- inert aria-disabled activation that produces no navigation, state change, focus movement, or live-region message;
- a composed accessible Open-button name that includes the selected authoritative entity title only when a valid Name value is selected;
- keyboard-operable classification selection, Name selection, explicit Name activation, and result activation;
- visible focus;
- a single polite live region for settled filter-state announcements;
- one consolidated announcement per settled classification interaction covering result-count changes, disabled-value changes, and cleared invalid selections;
- a deterministic settling interval declared in `ui/filter-interaction-policy.json`;
- a deterministic settled-state test hook or flush signal declared in the same policy;
- clear empty-state and no-result behavior;
- no focus trap and no pointer-only requirement.

Changing one facet or the Name selection MUST NOT unexpectedly move focus or change context. Name activation is deliberate navigation: it MUST follow the `pushState`, destination-placeholder, history-restoration, and authoritative-heading focus policy declared in `ui/filter-interaction-policy.json` and constrained by sections 7.4 and 8.1. The authoritative title is announced through the focused entity heading and MUST NOT be duplicated in the live region. The persistent inactive-state description, not the filter-state live region, provides the instruction for aria-disabled Open. Per-value count updates MUST NOT each produce separate live-region announcements. Initial fragment correction and initial state announcement MUST be combined into at most one message.

### 8.6 Filtered-search conformance

Filtered-search evidence is split by purpose.

`artifacts/filtered-search-integrity.json` verifies implementation integrity and MUST be generated deterministically from the normalized model. It MUST include:

- every publishable entity retrieved by its `entity_name` identity value;
- every publishable entity contained by its complete classification vector;
- controlled-vocabulary coverage;
- identity-domain projection coverage;
- stable-sort policy checks;
- semantic equality between each entity's `rules_area` set and its selector-reachable topic-area set.

`tests/filtered-search-correctness.yaml` verifies classification correctness and MUST be independently authored or reviewed rather than generated from the classifications it tests. Each case MUST record:

- the selection vector;
- the exact expected result IDs;
- entities that MUST NOT appear;
- expected disabled classification values where applicable;
- the independent derivation method;
- reviewer identity or second-pass attestation.

The correctness corpus MUST include:

- the exact **Electrokinesis + Rider** case;
- **Advanced Training + Granted** and **Advanced Training + Selectable** cases;
- at least one multi-select OR case;
- at least one cross-area entity case;
- at least one deliberately empty case;
- negative over-inclusion assertions;
- the no-selection state;
- a saturated-selection case proving that a complete metadata result list contains no rules prose and does not become an All Rules content view.

Ordering is tested once against the declared stable-sort policy and is not independently hand-derived for every correctness case. Availability vectors are required only for cases that exercise availability or selection clearing.

For migrated entities, correctness expectations and classification vectors MUST be reviewed against the pinned master and recorded in migration evidence. For later entities, expected sets MUST be authored or reviewed in a distinct pass rather than copied from generated filter output. A single maintainer MAY perform the second pass, but the attestation MUST identify it as separate from the initial classification work.

Changes to facets, controlled values, matching semantics, applicability rules, identity projection, or entity classifications MUST update the appropriate integrity or correctness evidence through normal review.

## 9. Rendering model

The renderer will produce one self-contained JavaScript application from the validated normalized model.

### 9.1 Topic rendering

A rendered topic MAY:

- combine several source entities when they form one coherent reference topic;
- show shared definitions needed to understand the selected entity;
- reuse an entity referenced by more than one topic;
- use generated tables, cards, definition groups, lists, and accordions;
- include direct links to related topics;
- focus an entity reached through filtered search.

A rendered topic MUST NOT:

- introduce new rules prose or constants;
- silently paraphrase authoritative statements;
- read content from a derivative Markdown file;
- display a rule-significant value that does not trace to YAML;
- require a separately generated discipline document.

### 9.2 Browser runtime

The application:

1. requires JavaScript to initialize and operate;
2. MAY render from build-time HTML, embedded structured data, or a combination;
3. MUST keep every rendered rule-significant leaf traceable to YAML;
4. SHOULD include a concise `<noscript>` notice;
5. SHOULD prefer native semantic elements;
6. MUST inline required CSS, JavaScript, icons, structured data, and necessary images;
7. SHOULD use system fonts;
8. MUST work directly through `file://`;
9. MUST make no automatic runtime network requests;
10. MAY contain ordinary user-activated external links;
11. MUST NOT use `eval`, `new Function`, dynamically loaded modules, or executable source data.

### 9.3 UI control and behavior allowlist

The application MAY contain only:

- the native single-select Name `<select>` with `<optgroup>` and `<option>` descendants;
- the adjacent Name **Open** activation button;
- finite classification selectors;
- finite checkbox groups or enumerated toggle groups used by multi-select facets;
- filtered-search result controls;
- the broad-category selector;
- dependent finite selectors;
- buttons;
- binary or enumerated toggles;
- accordions;
- segmented controls;
- bounded steppers used only for finite navigation or filtering;
- ordinary links;
- non-editable output and status elements.

Any other interactive control type requires an ADR amendment or an explicitly accepted follow-on ADR.

Permitted interaction state is limited to:

- current category, topic, and subtopic route;
- current finite filter selections and result focus while the page remains open;
- disclosure state;
- finite display-only preferences that do not alter rules meaning.

No control may:

- mutate a rule-significant value;
- accumulate a character, creature, encounter, or resource value across interactions;
- derive a displayed game value from a sequence of user inputs;
- preserve a mutable game-state value across a topic change;
- calculate attacks, saves, damage, costs, remaining resources, or outcomes.

A bounded stepper MUST select an authored finite navigation or filter value and MUST NOT perform arithmetic over game rules.

The UI MUST NOT include:

- an `input` whose type is `text`, `search`, `number`, or another unrestricted entry type;
- `textarea`;
- `contenteditable`;
- an editable combobox;
- `aria-autocomplete`;
- client-side substring, prefix, token, fuzzy, or natural-language narrowing of the Name options;
- unrestricted numeric-entry fields;
- editable rules prose;
- user-authored notes, names, labels, or arbitrary values;
- an All Rules content view;
- character-state tracking;
- resource tracking;
- attack, save, damage, or combat-resolution execution;
- calculators.

Native non-editable `<select>` first-letter navigation is permitted and is not text search. The Name `<select>` MUST NOT navigate or clear state from its `input` or `change` event. Only activation of the adjacent Open button may perform the Name route change. The Open button MUST remain focusable and MUST express its inactive state with `aria-disabled="true"` rather than the native `disabled` attribute.

### 9.4 Approved static UI text

`ui/approved-ui-text.json` MAY contain only generic interface chrome such as the Name placeholder, inactive Open accessible name, persistent inactive-Open description, filter instructions, empty-state messages, generic navigation instructions, accessibility message templates, release-status notices, version-field labels, and the concise no-JavaScript notice.

The initial UI tokens MUST include the exact strings **Select a rule by name**, **Open selected rule**, and **Select a rule name, then choose Open.**, plus the reviewed result-identity template **{entity_title} — {primary_rules_area_label}**.

Each UI-text entry MUST declare:

- a stable token ID;
- a semantic role;
- permitted element or accessibility-attribute placements;
- exact static text or a typed template;
- permitted typed substitution slots, each declared as `AuthoritativeText` or `DerivedOutput`. Static literal content MUST be part of the approved template's literal segments and MUST NOT be modeled as a substitution slot.

The renderer MUST use the distinct `UiTextToken<TokenId, Placement>` type defined by the three-class renderer boundary. It cannot be passed where authoritative rule text, entity labels, facet labels, or facet values are required.

A typed UI-text template MAY produce `ComposedText<TemplateId, Placement, Slots>` only when:

- every literal segment belongs to the approved UI token;
- each substitution slot is declared in that token's schema;
- each slot accepts only a typed `AuthoritativeText` or typed `DerivedOutput` value permitted for the placement;
- no raw string or UI-text token is passed through a substitution slot;
- constituent provenance and leaf coverage are recorded separately.

`ComposedText` is a provenance-safe container, not a fourth provenance class. The initial required compositions are:

- the Open-button accessible-name template **Open {entity_title}**, where `{entity_title}` is `AuthoritativeText` from the selected entity title; and
- the filtered-result identity template **{entity_title} — {primary_rules_area_label}**, where both slots are `AuthoritativeText` and the separator is an approved literal segment.

The result-identity composition is presentation-only and does not create an alias or replacement title.

Adding or changing a composition template MUST receive explicit UI-text registry review, typed-slot review, placement review, and corresponding renderer and conformance tests. A composition template cannot be introduced solely through application code or an unreviewed resource edit.

Approved UI text MUST NOT contain:

- feature, discipline, option, topic, facet, product-title, or rules-term labels; generic interface nouns and verbs remain permitted;
- dice expressions;
- game-rule numeric values;
- costs, ranges, durations, level gates, progression values, formulas, exceptions, or conditional rule language;
- paraphrased or copied rule statements;
- entity result labels or rules excerpts.

CI MUST lint the resource against authoritative labels, controlled vocabularies, dice and numeric patterns, conditional-rule patterns, and prohibited placements. Its SHA-256 MUST be recorded in the build manifest.

### 9.5 Derived non-rule outputs

`ui/derived-output-registry.json` MUST be a closed registry of permitted human-perceivable values that are neither authoritative strings nor static UI text. Initial permitted classes are:

- aggregate result and facet counts;
- enabled, disabled, empty, and corrected-state summaries;
- application-version values;
- release status;
- source and artifact hashes when displayed;
- templated substitutions of those values into approved UI-text tokens.

Authoritative product title, rules version, and schema version values use normalized source-path provenance and MUST NOT be emitted through the derived-output class. When an authoritative source path exists, authoritative provenance takes precedence and the derived-output class is prohibited for that value.

Each registry entry MUST declare:

- a stable derivation ID;
- input types or source paths;
- a deterministic derivation function or implementation reference;
- permitted placements;
- output type and formatting policy;
- whether it may enter an accessibility announcement.

The implementation MUST expose `AuthoritativeText<SourcePath, Placement>`, `UiTextToken<TokenId, Placement>`, `DerivedOutput<DerivationId, Placement>`, and the non-class `ComposedText<TemplateId, Placement, Slots>` container. `DerivedOutput` values MUST be produced only by registered derivation functions. The renderer MUST accept human-perceivable content only through:

- `AuthoritativeText` values carrying normalized source paths and valid placement;
- `UiTextToken` values valid for the placement;
- `DerivedOutput` values valid for the placement; or
- `ComposedText` values produced from one approved UI-text template and individually typed constituent slots under section 9.4.

A bare string interpolation into a human-perceivable placement, including into a composed template slot, MUST fail type checking or renderer validation.

Derived non-rule outputs MUST NOT express rules meaning, entity labels, facet labels, facet values, or filter classifications. Adding a new class requires review of the registry and corresponding conformance tests.

## 10. Derived SQLite artifact

A deterministic SQLite artifact MAY be generated after schema and semantic validation.

The database:

- MUST derive exclusively from the normalized model;
- MUST preserve stable entity IDs and source provenance paths;
- MUST include schema, rules, and application version metadata;
- MUST record the authoritative YAML hash;
- MUST use a pinned SQLite library or binding;
- MUST set canonical `page_size`, `application_id`, `user_version`, encoding, journal, and schema-creation settings;
- MUST create tables, indexes, and rows in documented deterministic order;
- MUST finalize through a canonical `VACUUM INTO` or equivalently reviewed process;
- MUST be byte-identical only relative to the pinned SQLite toolchain and deterministic environment;
- MUST NOT be a normal build input for `KineticVanguard.html`;
- MUST NOT be manually edited;
- MUST NOT contain replacement rules text or values absent from YAML;
- MUST be written only to the non-deployable artifacts directory.

Future applications MAY consume the database, but they remain derived consumers and must not feed rules changes back into the authority. Relaxing SQLite byte identity in favor of logical-content determinism requires a follow-on ADR.

## 11. Build, conformance, and promotion stages

A single build invocation is a one-way transformation from declared inputs into staged deterministic artifacts. It does not prove determinism by itself.

One invocation performs:

1. **Load and bind the positive input manifest.** Read `build/inputs.json`, hash it and the selected build profile, produce the canonical repository-relative path/role/SHA-256 `declared_inputs` inventory for every direct declared input, and reject undeclared or missing direct inputs.
2. **Verify repository and input state.** For a release profile, require the Git index and worktree to match the exact recorded commit for every direct declared input path, reject untracked admitted inputs, and reject any direct declared-input byte sequence that differs from the recorded commit or canonical input inventory.
3. **Validate migration inputs and resolve the effective ledger.** Verify the migration manifest, source-coverage report, source-unit inventory, immutable original ledger, and amendment files; reject gaps, overlaps, invalid per-unit amendment mappings, branches, cycles, missing predecessors, and multiple terminals; generate the deterministic effective-ledger view. Copy the pinned Markdown source identity from the migration manifest into inherited provenance without reading that Markdown file as a current build input.
4. **Read and fingerprint authority.** Read UTF-8 bytes and calculate the source hash.
5. **Parse restricted YAML.** Reject duplicate keys and prohibited YAML features.
6. **Validate canonical schema.** Reject unknown properties and invalid structures.
7. **Verify generated contracts and rules-adjacent register.** Regenerate TypeScript/schema derivatives, fail on diff, and reject unregistered schema-side rules constraints.
8. **Run semantic validation.** Validate IDs, references, vocabularies, classification requiredness, rules-area/topic redundancy, presentation metadata, Name-label uniqueness, canonical-topic maps, ranges, membership, source-origin qualification against the effective ledger, structural new-content-origin references, closed leaf classifications, and cross-field constraints. External review acceptance for new-content decisions is validated during the content-validity gate.
9. **Normalize immutable objects.** Preserve stable IDs and provenance paths.
10. **Resolve navigation.** Resolve categories, topics, per-area canonical entity routes, defaults, links, and fragments.
11. **Generate display projections.** Produce visible strings from typed values through defined projection functions.
12. **Generate filter index and integrity evidence.** Build deterministic facet maps, availability maps, counts, identity projection, entity-classification indexes, and generated integrity corpus.
13. **Render profile-specific staged publication.** Render the self-contained HTML shell, embedded data, provenance status, and prototype identity when applicable.
14. **Generate coverage and provenance ledgers.** Record direct rule leaves, indirect projection inputs, publication metadata, navigation/filter metadata, non-rules UI metadata, provenance/evidence metadata, UI tokens, derived-output IDs, effective origin records, and rendered destinations.
15. **Optionally generate canonical SQLite.** Produce the non-authoritative database from the same normalized model.
16. **Validate staged runtime and output.** Run structure, source and entity coverage, filtered-search, result-identity, canonical-route, navigation, `history.state` shape, accessibility automation, `file://`, network, persistence, prototype-identity, and prohibited-feature tests required by the selected profile.
17. **Emit deterministic build manifest.** Record direct declared inputs, inherited migration provenance, and the hash of every configured staged deterministic artifact except the manifest itself; write the manifest only after required staged validation succeeds.

Determinism verification is a CI-level obligation over two complete clean invocations of stages 1 through 17 using identical direct declared inputs, inherited provenance records, toolchain, and deterministic environment. CI compares every staged deterministic artifact required by the selected profile. The effective-ledger view is compared as an output and is never presumed as an input.

Content-scoped evidence artifacts and reviewed digest-migration records are excluded from staged build inputs and byte comparison. Their subject, policy-registry, policy-chain, semantic-equivalence, and coverage validity MUST be checked whenever migration acceptance or another lifecycle gate consumes them. This content-validity check may and, at migration acceptance, must occur before any release build-manifest hash exists.

After the clean double-build comparison fixes the verified build-manifest hash, current content validity is rechecked, release-scoped evidence is produced against that staged publication, and release binding hashes the accepted content evidence and release-scoped evidence into the release evidence record. A separate promotion operation then constructs a fresh temporary deployable directory containing only the verified `KineticVanguard.html` and atomically replaces the prior deployable directory. Prototype output is never promoted.

Incremental authoring tools MAY execute a documented subset of stages 1 through 17, but their output cannot satisfy release conformance.

## 12. Migration acceptance

Migration is a human-reviewed semantic transposition, not a blind conversion.

### 12.1 Source-span coverage and source-unit inventory

The pinned `Kinetic_Vanguard.md` MUST be processed by a versioned deterministic parser and coverage algorithm before disposition review.

The source-unit leaf model is **reviewable block-content atoms**. It is part of the versioned enumeration algorithm and MUST be implemented consistently by every conforming enumerator.

Leaf source units include, as applicable:

- heading content together with structural heading level;
- paragraph content;
- the direct content of a list item, while nested block children are separate units;
- blockquote paragraph content;
- every table header cell and data cell, with table, row, and column relationships recorded as metadata;
- fenced and indented code-block content;
- raw HTML or other embedded visible block content;
- footnote-definition content;
- explicit examples and workflow passages;
- malformed or unrecognized block content that remains readable;
- another explicitly versioned block-content type recognized by the migration parser.

Each leaf contains its complete inline source, including emphasis, inline code, links, footnote references, and other inline markup. Inline constructs are within-unit metadata and MUST NOT become overlapping source units. Every link destination MUST be captured unconditionally as metadata on its containing source unit. The enumerator MUST NOT decide whether a destination is meaning-bearing; that judgment belongs to disposition review.

Structural containers such as lists, blockquotes, tables, and table rows MAY be recorded as relationships or metadata, but MUST NOT claim byte spans already assigned to leaf content. A leaf MAY reference more than one exact non-overlapping span when required to represent direct content around nested structural children.

The algorithm MUST produce `migration/source-coverage.json`, an ordered partition of the complete pinned UTF-8 byte sequence. Every byte span MUST be covered exactly once by either:

- one inventoried source unit; or
- a narrowly defined syntax-only exclusion with an explicit exclusion type and reason.

Syntax-only exclusions MAY cover byte-order marks, line endings, inter-unit whitespace, and structural Markdown delimiter characters not already contained within a leaf's complete inline source and carrying no independent human-readable content. They MUST NOT exclude visible prose, labels, table content, raw HTML text, link text or destinations, footnote text, malformed but readable content, or any span whose meaning is uncertain. Gaps, unintended overlaps, out-of-range spans, duplicate coverage, and non-syntax human-readable exclusions MUST fail inventory creation.

Inventory decisions MUST precede normative classification. The inventory MUST include every visible or potentially meaningful construct regardless of whether later review decides it is normative, exemplary, obsolete, duplicated, or irrelevant.

The enumerator MUST NOT decide that a table cell, paragraph, example, destination, or unfamiliar construct is non-rule-significant and omit it. Rule significance and every retained, dropped, removed, deferred, example, and obsolete-workflow judgment belong in the reviewed disposition ledger.

`migration/source-coverage.json` MUST record for every span:

- start and end byte offsets;
- span type;
- source-unit ID or syntax-only exclusion ID;
- content digest;
- exclusion reason when applicable.

It MUST also record the pinned source SHA-256, parser version, enumeration-algorithm version, leaf-model version, total byte count, covered byte count, gap count, and overlap count. A deterministic source-coverage validator MUST prove complete exact partitioning before the inventory can be accepted.

Each source unit MUST have a stable inventory ID derived from its source location and content digest.

The complete source-coverage report and enumerated inventory MUST be committed as immutable migration artifacts before disposition review. Each inventory record MUST include:

- unit ID;
- unit type;
- one or more exact source spans;
- source location;
- content digest;
- normalized source text sufficient for later verification;
- within-unit inline metadata, including all link destinations, where present.

### 12.2 Workflow state and required dispositions

A newly enumerated unit begins in the workflow state `pending_review`. `pending_review` is not an accepted disposition and MUST fail migration acceptance.

Every source unit MUST ultimately receive exactly one reviewed disposition:

- `transposed` — represented without intended meaning change by one or more YAML paths or entity IDs;
- `consolidated` — merged without intended meaning change into a named authoritative entity or field;
- `rewritten_equivalent` — preserved with wording or structure changed but intended meaning unchanged, with rationale and destination;
- `corrected_by_rules_decision` — transposed with an intentional meaning correction, with a reviewed rules-decision reference, before-and-after summary, and destination;
- `removed_by_rules_decision` — intentionally removed from v13 by a reviewed rules decision, with tracking reference and rationale;
- `deferred_to_follow_on_decision` — reviewed content outside the initial authority pending a named follow-on ADR or issue, with scope, tracking reference, and explicit release impact;
- `dropped_non_normative` — intentionally excluded as non-normative example or tutorial material;
- `dropped_obsolete_workflow` — intentionally excluded as legacy executable-sheet behavior.

A deferred unit MAY pass migration acceptance only when its tracking decision explicitly places it outside the initial v13 authority and the unit is not required to understand retained Kinetic Vanguard rules. All other unresolved deferrals are release-blocking.

A unit with `pending_review`, no disposition, multiple contradictory dispositions, a missing destination, a missing required decision reference, or an unresolved review objection MUST fail migration acceptance.

### 12.3 Review requirements

The migration ledger MUST:

- reference the committed inventory unit ID;
- map retained content to stable YAML paths or IDs;
- explain material consolidation, equivalent rewriting, and intentional correction;
- identify explicit rules decisions that correct or remove v12.1 content;
- identify deferred follow-on decisions;
- identify removed executable-sheet and combat-log workflow content;
- distinguish dropped examples from removed or deferred rules;
- record the classification vector assigned to each resulting publishable entity;
- record reviewer approval and review method;
- include a pinned-master citation and no-derivative-source attestation for ambiguity resolutions;
- be committed with the pinned source digest and inventory digest.

Every publishable entity MUST carry an origin record that points to:

- one or more source-unit IDs whose effective disposition is `transposed`, `consolidated`, `rewritten_equivalent`, or `corrected_by_rules_decision`; or
- a reviewed new-content decision with tracking reference, rationale, rules-version effect, and reviewer approval.

A reviewed new-content decision MUST be represented by a content-scoped evidence entry containing:

- `origin_type: new_content_decision`;
- stable `decision_id`;
- canonical `decision_digest`;
- destination entity or leaf IDs and digests;
- rationale and scope;
- rules-version effect and resulting rules version when applicable;
- reviewer identity and approval;
- content-evidence-policy version and SHA-256.

A unit dispositioned `removed_by_rules_decision`, `deferred_to_follow_on_decision`, `dropped_non_normative`, or `dropped_obsolete_workflow` MUST NOT qualify as the sole origin of publishable authority content.

Migration acceptance MUST perform reverse-origin coverage and fail when any publishable entity lacks an accepted origin record, even when every source unit has a disposition. Vertical-slice entities are subject to the same check.

Migration acceptance additionally requires:

- schema-valid `KineticVanguard.yaml`;
- stable IDs for reusable and navigable entities;
- the required broad categories and topics;
- complete exact source-span coverage with no gaps or unintended overlaps;
- complete source-unit disposition coverage;
- complete entity-side origin coverage;
- exact equality between each independently authored rules-area set and selector-reachable topic-area set as a redundancy check;
- independent second-pass review of filter classifications and correctness cases;
- aggregate review of the complete deferred-unit set to confirm that the combined deferral does not remove context required to understand retained rules;
- documented review of the non-normative high-risk cluster checklist: Blood Tax, Overload, Manifested Strike, concentration interactions, granted versus selectable Advanced Training, and each discipline.

A single maintainer MAY perform the second pass, but MUST record that it was a separate review pass using a checklist and MUST NOT programmatically derive correctness expectations from the classifications under review. Independent adversarial review MAY supplement but does not replace maintainer accountability.

Migration, new-content-origin, classification, and correctness-review attestations are content-scoped evidence. Each attestation entry MUST record both the content-evidence-policy version and policy SHA-256 under which its subject digests were computed and MUST use the narrowest subject scope defined in section 3.6:

- source-migration entries identify reviewed source-unit, effective disposition and amendment-chain, and destination entity or leaf digests;
- new-content-origin entries identify one reviewed new-content decision and its destination entity or leaf digests;
- classification entries identify one entity and its canonical classification digest;
- correctness entries identify one correctness case and its canonical case digest.

A batch evidence file MAY carry many independently valid entries. Unchanged entries remain valid when unrelated subjects change. Migration acceptance and release validation MUST compute the current source-migration and new-content-origin subject sets and prove that every current qualifying source migration, reviewed new-content decision, publishable-entity classification, and required correctness case is covered by at least one current valid entry.

The accepted deferral set MUST be reviewed as an aggregate at migration acceptance. A release-scoped aggregate deferral re-review MUST also occur for every release and MUST reference the verified build-manifest hash together with the current effective-ledger-view digest, amendment-set digest, and canonical aggregate deferral-decision-set digest. Promotion MUST fail when a deferral's tracking decision has expired, changed scope, become necessary to understand retained rules, or lacks current aggregate-review coverage.

Prototype and incremental-authoring profiles MAY omit completed second-pass attestations while content is provisional. They MUST surface missing origin, disposition, and correctness review as diagnostics and MUST NOT satisfy migration acceptance or release conformance.

### 12.4 Accepted-ledger amendments and effective state

An accepted inventory record and original disposition MUST NOT be silently rewritten.

A discovered migration error requires a versioned amendment containing:

- stable `amendment_id`;
- affected entity IDs, when any;
- a non-empty `changes` array;
- reason and evidence;
- rules-version impact;
- reviewer approval;
- required regeneration and conformance results.

Each `changes` entry MUST contain:

- `source_unit_id`;
- `supersedes`, naming that source unit's current terminal ledger-entry ID or amendment ID;
- monotonic sequence or version within that source unit's chain;
- prior effective disposition and destination;
- new effective disposition and destination.

The amendment's declared affected-source-unit set MUST equal the set of `source_unit_id` values in `changes` exactly. A source unit MUST NOT appear more than once in one amendment.

For each source unit, the original ledger entry is the chain root. Every change entry participates only in the chain for its declared source unit. The validator MUST prove independently for every source unit that:

- `supersedes` names that unit's current terminal predecessor;
- sequence values are monotonic and unique within the unit's chain;
- the chain is non-branching and acyclic;
- the chain has exactly one terminal state.

Missing predecessors, duplicate source-unit entries within an amendment, duplicate sequence values, branches, cycles, multiple terminals, changes that supersede another unit's chain, an affected-unit/change-set mismatch, or ambiguous ordering MUST fail migration acceptance and every release build.

One amendment MAY therefore record one atomic reviewed correction across multiple source units while preserving independent predecessor semantics for every unit.

The migration validator MUST deterministically produce an **effective ledger view** containing exactly one terminal effective disposition and destination per source unit plus the complete amendment chain that produced it. Origin qualification, deferred-set computation, source-migration evidence, classification review, and release validation MUST use this effective view rather than the immutable original disposition alone.

The disposition-ledger format contract MUST define canonical serialization for amendment files, per-unit ordered amendment chains, the complete amendment set, and the generated effective-ledger view. The deterministic build manifest MUST record every amendment-file SHA-256 as a direct declared input and the effective-ledger-view SHA-256 as a generated staged artifact. Content evidence MUST attest the effective disposition and the canonical per-unit amendment-chain digest that produced it.

An amendment whose correction changes published rules meaning MUST increment `rules_version` under `policy/rules-versioning.md`, and the amendment MUST record the resulting version. An amendment claiming no rules-version change MUST state why published meaning is unchanged and receive reviewer approval.

After migration acceptance, the pinned master and derivative Markdown files SHOULD be removed from the active rules tree and retained through the exact recorded Git commit and committed migration evidence.

## 13. Coverage, classification, and provenance validation

### 13.1 Rule-significant leaves

Every normalized authority leaf MUST belong to exactly one member of this closed classification:

- **directly published rule leaf** — visibly rendered as authoritative rule content;
- **indirectly published projection input** — not displayed independently, but consumed by at least one covered visible projection whose provenance records the input source path;
- **publication metadata** — authoritative document identity, attribution, version, or release metadata with declared publication placement;
- **navigation or filter metadata** — authoritative IDs, labels, memberships, classifications, and presentation routing used by selector or filtered-search behavior;
- **non-rules UI metadata** — schema-declared finite application metadata that carries no game-rule meaning;
- **provenance and evidence metadata** — schema-declared `origins`, `new_content_decisions`, `audits`, and any other explicitly enumerated provenance-only structures.

The provenance-and-evidence metadata class is closed. Its members MUST NOT carry playable rules meaning, replacement display prose, rule constants, or classifications used as shadow rules. They MUST NOT be rendered as rules content and MAY be consumed only by migration, provenance, audit, coverage, and release validation.

Every retained rule-significant leaf MUST be either directly published or indirectly published through a visible covered projection. The authority MUST NOT contain an open-ended “rule-significant but intentionally non-publishable” category. Content removed or deferred through a qualifying rules decision is outside the active authority rather than retained as an unpublished playable rule.

Every retained rules entity MUST:

- have at least one selector-reachable rendered topic;
- contain or reference at least one directly published rule leaf or indirectly published projection input;
- have every rule-significant leaf represented directly or indirectly in the publication.

Coverage MUST include:

- typed values;
- ordered rule statements and structured prose nodes;
- table headers and cells;
- prerequisites;
- relationships;
- options;
- exceptions;
- progression bands;
- generated display projections and every authoritative input consumed by them.

Entity-level presence alone is insufficient. An entity with no represented rule-significant leaves, an indirect projection input with no covered visible consumer, or a retained leaf with no member of the closed classification MUST fail coverage validation.

### 13.2 Emission provenance

Every atomic constituent of a human-perceivable string emitted by the publication MUST consume exactly one provenance class. An atomic constituent is one literal segment from the declared UI-text template, one non-nested `AuthoritativeText` value, or one non-nested `DerivedOutput` value:

1. one or more normalized authoritative source paths;
2. an approved static UI-text token valid for that placement; or
3. a registered derived non-rule output valid for that placement.

A human-perceivable string MAY combine constituents only through a declared provenance-safe composition under sections 9.4 and 9.5. Each constituent retains its own class, source identity, placement permission, and coverage record. Composition does not permit a constituent to bypass the precedence or placement rules.

When an authoritative source path exists for a constituent, class 1 takes precedence and classes 2 and 3 MUST NOT be used for that constituent.

This includes visible text nodes, document titles, alternative text, form labels, status messages, `title` attributes, accessible names, accessible descriptions, and CSS-generated human-readable content.

Machine-only identifiers, class names, stable IDs, serialized field names, and executable source code are not human-perceivable strings. Any other exemption MUST be enumerated by exact element and attribute in a checked-in conformance specification; undefined regions and heuristic classification are prohibited.

Renderer APIs MUST enforce the disjoint `AuthoritativeText`, `UiTextToken`, and `DerivedOutput` base types plus the provenance-safe `ComposedText` container defined in section 9. Bare human-perceivable string emission or raw-string template substitution is prohibited.

The build MUST fail when:

- a retained rule-significant leaf is neither directly rendered nor consumed by a covered visible projection;
- a retained rules entity has no directly or indirectly represented rule-significant leaf;
- rendered rule content has no normalized source path;
- a human-perceivable static string has no valid UI token;
- a human-perceivable computed value lacks a typed registered derivation ID and placement;
- a composed human-perceivable value uses an undeclared or unreviewed template, an undeclared slot, a raw-string slot value, an invalid placement, lacks the required conformance tests, or fails to record each constituent's provenance;
- a rule string, product title, version value with an authoritative path, entity label, facet label, or facet value is emitted through a UI-text or derived-output escape path, other than as typed authoritative input to a declared provenance-safe composition slot;
- two topics generate contradictory projections from the same source leaf;
- a renderer silently ignores an unknown rule-significant field;
- filtered search displays an untraceable title, breadcrumb, facet label, facet value, or result status;
- a topic or entity lacks a selector route;
- a publishable entity lacks required or applicable classifications;
- an entity's authored `rules_area` set differs from the set of selector-reachable topic areas containing it;
- `primary_rules_area` is not a member of `rules_area`;
- a publishable entity is absent from the result set produced by its complete classification vector;
- a publishable entity lacks an accepted origin record at migration acceptance or release;
- the independently reviewed correctness corpus disagrees with generated results or availability.

### 13.3 Navigation and filtered-search coverage

Automated JavaScript-enabled browser and structure tests MUST confirm:

- every category and configured topic is selector-reachable;
- every publishable entity belongs to at least one selector-reachable topic;
- dependent selectors contain only valid options;
- every publishable topic and entity can be reached without filtered search;
- every classification result resolves to exactly one valid selector route under the deterministic result-activation-area rule;
- every area in which an entity has multiple rendering topics has exactly one valid `canonical_topic_by_area` entry, and every canonical entry names a topic in the keyed area that renders the entity;
- every classification facet and value is backed by a controlled vocabulary declared in `KineticVanguard.yaml`;
- the `entity_name` domain is exactly the reviewed projection of publishable entity IDs and authoritative titles;
- no other derived facet-value domain exists;
- result sets exactly follow the classification AND/OR semantics in section 8.3;
- required and conditional classifications are present;
- each entity's `rules_area` set exactly equals its selector-reachable topic-area set;
- `primary_rules_area` is one member of that set;
- every filtered-result visible label and accessible name equals the required authoritative composition `{entity_title} — {primary_rules_area_label}` and introduces no alias;
- the generated integrity corpus succeeds;
- the independently reviewed correctness corpus succeeds;
- expected disabled availability and selection-clearing behavior succeed;
- the canonical classification and Advanced Training acquisition-mode cases return their exact expected sets;
- the Name control's default unactivated state selects the approved non-entity placeholder **Select a rule by name**; Open is focusable with `aria-disabled="true"`, exposes the static accessible name **Open selected rule**, and references the persistent description **Select a rule name, then choose Open.**;
- activating aria-disabled Open is inert and produces no navigation, route or selection change, focus movement, or live-region message;
- every Name value can be selected without navigation or state clearing, and explicit Open-button activation routes to exactly its entity, clears conflicting classification selections only in the new history state, and uses `pushState`;
- the Name control uses a native non-editable `<select>` plus an adjacent focusable Open button and contains no native-disabled Open state, text/search input, `textarea`, `contenteditable`, editable combobox, `aria-autocomplete`, or client-side option-narrowing code;
- Name `input` and `change` events do not navigate, clear classification state, move focus, mutate the fragment, or write browser-history state;
- unactivated Name choices are transient DOM state, are not restored by Back or Forward, and every restored route presents the Name placeholder;
- selecting any classification facet resets the Name select to its placeholder and makes Open aria-disabled, including after a prior Name activation or unactivated Name selection;
- a valid Open target exposes the composed accessible name **Open {entity_title}** with separately traceable UI-template and authoritative-title constituents;
- every composition template has reviewed registry metadata, typed slots, placement authorization, and corresponding conformance tests;
- Name activation focuses the rendered authoritative entity heading defined by `ui/filter-interaction-policy.json`;
- the activated destination resets Name to the placeholder and Open to aria-disabled; browser Back restores the complete prior state and browser Forward restores the destination with the placeholder and aria-disabled Open;
- initial direct entity routes and validated shared fragments leave Name on the placeholder rather than auto-selecting the routed entity;
- no-selection, empty, no-result, negative, multi-select OR, cross-area, and saturated-selection behavior work;
- saturated results expose metadata only and no All Rules content view;
- direct links and fragments restore valid selector and filter state;
- back and forward navigation restore selections;
- every `history.state` entry contains only allowlisted finite route fields and focus-origin enums and contains no rules prose, entity descriptions, rendered HTML, arbitrary text, durable preferences, or undeclared keys;
- malformed fragments and well-formed non-authoritative IDs are corrected safely, announced at most once on initial load, and normalized with `replaceState`;
- live-region tests wait on the declared settled-state signal rather than a timing sleep.

## 14. Accessibility conformance

The publication targets **WCAG 2.2 Level AA**.

Release validation MUST include:

- the pinned automated scanner results required by `tests/accessibility-scanner-config.*`, with no unresolved findings in the configured release-blocking classes;
- a checked-in `tests/accessibility-known-issues.yaml` containing any accepted non-blocking finding, rationale, scope, owner, and tracking reference;
- complete keyboard-only operation of selectors, filtered-search facets, results, topic controls, and links;
- visible focus for every interactive element;
- programmatic labels and instructions;
- accessible announcement of dependent-selector updates;
- one consolidated polite announcement per settled filtered-search or fragment-correction interaction;
- no per-value live-region storm;
- no unexpected focus movement or destruction when availability changes;
- correct heading and landmark structure;
- sufficient contrast;
- reduced-motion support where motion exists;
- high-contrast compatibility where supported;
- execution of the checked-in manual screen-reader script.

`tests/accessibility-manual-script.md` MUST tag every step as `prototype`, `release`, or `both` and define the actions, expected focus state, expected announcements, and pass criteria for selector navigation, facet changes, disabled-value behavior, consolidated counts, result activation, fragment correction, history restoration, related-topic links, and artifact-status presentation.

Every step MUST have a stable ID and MAY declare `allow_not_applicable: true`. A recorded `not_applicable` result is permitted only for a step that declares that flag and MUST include a non-empty rationale. The validator MUST reject `not_applicable` for every other step. Prototype-tagged steps MUST verify the visible and accessibility-exposed prototype banner; release-tagged steps MUST verify that the prototype banner is absent.

The script MUST begin by confirming that the Name select exposes the approved placeholder; that Open remains in the tab order with `aria-disabled="true"`; that its inactive accessible name is **Open selected rule**; that `aria-describedby` exposes **Select a rule name, then choose Open.**; and that inert activation causes no navigation, state change, focus movement, or live-region announcement. It MUST exercise keyboard traversal and value changes within the Name select while classification filters are active and confirm that no navigation, clearing, or focus movement occurs before valid Open activation. It MUST confirm the composed accessible name **Open {entity_title}**, activate Open, and verify `pushState`, focus on the rendered authoritative entity heading, destination reset to the placeholder, and non-duplicated live-region behavior. It MUST verify that changing an unactivated Name value does not change the URL or browser-history state. It MUST verify that Back restores the prior route and classification state with the Name placeholder and aria-disabled Open, and that Forward restores the destination with the placeholder and aria-disabled Open. It MUST test an initial validated entity fragment and confirm that it also leaves Name on the placeholder. It MUST then activate a classification facet after a Name route and confirm that the Name control remains or resets to the placeholder and Open becomes aria-disabled.

The script MUST also exercise at least one filtered result whose title is duplicated in another primary area or a fixture equivalent and confirm that the visible label and accessible name expose the required authoritative primary-area disambiguator.

The manual screen-reader release report is a release-scoped evidence artifact produced against the verified staged publication and MUST record:

- the verified build-manifest SHA-256;
- tester identity;
- browser and assistive-technology versions;
- script version and hash;
- result for every scripted step;
- deviations and accepted-known-issue references.

The selected scanner, its version, and severity mapping MUST be named in checked-in configuration. The supported browser and assistive-technology matrix MUST be checked in, versioned, hashed in the build manifest, and used by the release report. Machine reports that contain uncontrolled timings, host metadata, or tester metadata are release-scoped evidence artifacts unless a profile explicitly canonicalizes them as staged deterministic artifacts.

## 15. Deterministic release conformance

Given the identical exact repository commit, positive input manifest, canonical direct declared-input inventory, inherited migration provenance recorded in the migration manifest, migration manifest, source-coverage report, source-unit inventory, immutable disposition ledger, amendment files, authority, schema, generated contracts, rules-adjacent constraint register, policy resources and policy registry, UI resources, derived-output registry, interaction policy, independently reviewed correctness corpus, integrity-generation implementation, accessibility configuration, application inputs, lockfile, toolchain, application version, selected build profile and configuration, and declared environment, two clean build invocations MUST produce byte-identical staged deterministic artifacts.

The generated effective-ledger view is a staged deterministic output. It is not part of the fixed-input premise. Its bytes, along with every other configured staged deterministic artifact, MUST match across the two clean builds.

Reviewed content-evidence digest-migration records and all other content-scoped or release-scoped evidence are excluded from staged build inputs and byte comparison. Content validity—including subject digests, accepted policy-version/hash bindings, digest-migration chains, semantic-equivalence claims, and required subject coverage—MUST be checked at every lifecycle gate that consumes content evidence, including migration acceptance. Only release binding to the verified build-manifest hash waits until after deterministic build verification.

For a release profile, a **clean build** requires:

- the Git index and worktree to match the exact recorded commit for every direct declared input path;
- every direct declared input to be tracked and byte-identical to the canonical `declared_inputs` inventory;
- no untracked file to be admitted as a direct input;
- no dirty or alternate direct-input bytes to influence build or test behavior.

The historical Markdown migration source is inherited provenance, not a direct declared input. Its absence from the active worktree does not violate clean-build requirements when the accepted migration manifest and committed migration artifacts remain valid.

The build environment MUST pin:

- Node.js version;
- package-manifest and dependency-lockfile bytes and SHA-256;
- package-manager version;
- selected environment-specification and environment-lockfile bytes and SHA-256;
- every devcontainer-feature implementation version and digest when devcontainer features are used;
- SQLite library or binding version when SQLite is generated;
- `TZ=UTC`;
- `LC_ALL=C` or another explicitly fixed locale;
- newline and text-encoding policy;
- container image by immutable digest or an equivalently reproducible environment specification;
- versions of schema, browser, accessibility, and test tooling used for staged conformance.

For the revision-21 bootstrap baseline, Node.js is `24.18.1`; GitHub CLI is `2.97.0`; Python is supplied by the base operating system with optional Python tooling and JupyterLab disabled; and the devcontainer feature implementations are pinned in `.devcontainer/devcontainer-lock.json`. The environment specification may record those installed tools, but GitHub CLI and Python MUST NOT become build-execution dependencies without an explicit deterministic profile assignment. The Codex volume, GitHub CLI configuration volume, credentials, and other user state are always excluded from publication inputs. The current `mcr.microsoft.com/devcontainers/base:resolute` tag is sufficient for development onboarding but does not satisfy the immutable release-environment requirement until it is resolved and committed as an immutable digest or replaced by an accepted equivalent reproducible specification.

The build MUST NOT embed:

- uncontrolled timestamps;
- absolute paths;
- random values;
- process IDs;
- hostnames;
- environment-specific ordering;
- its own output digest.

Serialization order, generated IDs, filter-index ordering, facet-value ordering, UI-resource ordering, integrity-corpus ordering, effective-ledger ordering, SQLite schema creation and row insertion order, whitespace, and locale-sensitive formatting MUST be stable.

CI MUST perform a clean double-build comparison or equivalent content-hash comparison for every staged deterministic artifact required by the selected profile. Recorded evidence artifacts are excluded from byte comparison. After comparison fixes the build-manifest hash, the release validator MUST revalidate current content validity, produce or validate build-specific release-scoped evidence, and hash the accepted content-scoped evidence, digest-migration records, subject-coverage maps, and release-scoped evidence into the release evidence record under section 5.5. A failed invocation, comparison, dirty direct declared input, stale content-evidence subject digest, policy-registry conflict, incomplete or ambiguous evidence-policy migration chain, evidence gate, or manifest/evidence mismatch MUST not replace the last valid release artifact.

## 16. Alternatives considered

### 16.1 Continue using Markdown plus a Markdown AST

**Rejected.** The product no longer requires Markdown as the canonical publication format. Recovering entities, relationships, navigation membership, and typed domains from prose weakens validation.

### 16.2 Store Markdown inside YAML block scalars

**Rejected.** This preserves Markdown parsing and duplication problems while adding YAML indentation and escaping concerns. Structured rich-text nodes may be added when justified, but unrestricted embedded Markdown is not the authority model.

### 16.3 Use JSON as the authoritative source

**Not selected.** JSON offers similar validation but is less comfortable for human editing of ordered rules statements. The project will use a restricted JSON-compatible YAML profile.

### 16.4 Six independently authoritative sources

**Rejected.** This recreates duplicated authorship and continuous drift management.

### 16.5 Keep legacy files as secondary authorities

**Rejected.** A fallback authority preserves ambiguity. Missing YAML content must fail visibly.

### 16.6 Use derivative Markdown files as completeness checks

**Rejected.** They contain duplicated and view-specific material and cannot prove the master was transposed faithfully. Completeness is established by the pinned master-source unit ledger.

### 16.7 SQLite as the authority

**Rejected.** A database creates a second durable authoring surface and obscures review diffs. SQLite is permitted only as a deterministic derivative.

### 16.8 Generate separate discipline documents

**Rejected.** Separate publications duplicate packaging and validation without adding an independent product need.

### 16.9 Selector-only lookup

**Rejected.** Taxonomy navigation alone makes reachability provable but does not make findability reliable for users who know a feature's classifications but not its exact topic location.

### 16.10 Add deterministic filtered search

**Selected.** Finite schema-defined facets let users combine known classifications—for example, Electrokinesis and Rider—while remaining offline, derived, deterministic, accessible, and subordinate to the same topic routes. A grouped native Name `<select>` projected from authoritative entity IDs and titles, paired with an explicit Open button, provides finite known-name navigation without change-on-input or unrestricted text entry.

### 16.11 Add unrestricted text or fuzzy search

**Rejected for the initial implementation.** Open text search would add tokenization, typo tolerance, ranking, highlighting, snippet safety, natural-language recall expectations, and text-input accessibility behavior. Known-name lookup is served by a grouped native Name `<select>` with ordinary first-letter selection and an explicit Open button; classification lookup is served by controlled facets. Editable comboboxes, autocomplete, substring filtering, custom type-ahead, and change-on-input navigation are excluded. A future need for natural-language or fuzzy search requires a follow-on ADR supported by observed failed lookup cases.

### 16.12 Add an All Rules screen

**Rejected.** The publication will not provide a catch-all mode that renders the complete rules prose or equivalent full rules content. A saturated filtered result set containing titles, breadcrumbs, and classifications is permitted because it remains an index into ordinary topics rather than a second rules publication.

### 16.13 Persist reference state locally

**Rejected.** URL fragments provide reload-safe and shareable route and filter state without hidden stale storage. Disclosure and display-only preferences may reset on reload; system-level color, contrast, and motion preferences SHOULD be respected through CSS media queries. If durable non-rules UI preferences later become a demonstrated requirement, they require a follow-on ADR defining scope, privacy, reset behavior, and version invalidation.

### 16.14 Allow YAML anchors and aliases

**Rejected.** Stable domain IDs and references provide explicit reuse at the rules-model layer. Shared saving-throw clauses, costs, progressions, and other repeated mechanics SHOULD become reusable domain entities or typed structures rather than copied blocks. Serialization-layer reuse would obscure those relationships and complicate provenance, canonicalization, diagnostics, and review.

### 16.15 Use a frontend framework

**Rejected for the initial implementation.** Selectors, finite facets, accordions, and stateless topic rendering remain manageable with semantic HTML, CSS, and small plain-JavaScript modules. A future framework change would require preserving all authority and conformance constraints.

### 16.16 Include SRD 5.2.1 content in the initial v13 authority

**Deferred to a separate decision.** ADR-0001 governs Kinetic Vanguard-specific rules and the publication architecture. SRD-derived fighter chassis, species, backgrounds, equipment, spells, or other general rules data may be added later only under explicit source, license, attribution, versioning, and provenance requirements. Such data MUST NOT be silently inferred, copied into UI text, or treated as Kinetic Vanguard-authored content.

### 16.17 Relax migration and provenance checks for release

**Rejected.** Exhaustive migration disposition and leaf-level publication provenance protect different failure boundaries and remain release requirements. Incremental authoring and vertical-slice prototype profiles are selected instead, as defined in section 2.4, so daily work need not run every whole-publication gate.

## 17. Consequences

### Positive consequences

- One explicit source of truth.
- Auditable migration completeness against the exact pinned master.
- Typed rules concepts rather than inferred prose structure.
- One official human-readable publication.
- Selector navigation for predictable browsing.
- Filtered search for classification-based discovery.
- A grouped native Name control provides a permanent complete title index with explicit activation and no change-on-input navigation or unrestricted text search.
- Stable IDs for links, tests, databases, and future applications.
- Leaf-level coverage catches partially rendered entities.
- Three-class provenance covers authoritative strings, static UI text, and closed-registry derived outputs.
- Independently reviewed classifications and result corpora test disagreement rather than only internal consistency.
- Deterministic outputs support trustworthy diffs and releases.
- The checked-in devcontainer gives contributors a concrete Node.js, GitHub CLI, editor-extension, and authentication-persistence baseline while keeping personal Codex and GitHub state outside the build graph.
- A generated SQLite artifact can support later reference-sheet work without becoming authoritative.
- The publication remains offline-capable and directly usable through `file://`.

### Negative consequences and costs

- Migration is a reviewed semantic rewrite rather than a mechanical conversion.
- Source-unit disposition, classification review, and leaf-level provenance require implementation effort.
- A schema, semantic validator, controlled-facet model, grouped Name control, filtered-search implementation, and coverage system must be maintained.
- YAML is less pleasant than Markdown for long narrative prose, so authoring support and a review projection are mandatory safeguards against parallel shadow documents.
- Filtered search introduces controlled-vocabulary maintenance, multi-area classification validation, finite-state accessibility behavior, independent correctness review, and availability tests.
- Exact equality between `rules_area` and rendering-topic areas deliberately forecloses classifying an entity under an area where no topic renders it; related-but-not-rendered relationships must use links rather than area-filter membership.
- Navigation and filter metadata must remain ID-based and authoritative classifications must remain in YAML.
- Universal human-perceivable-string provenance requires typed renderer boundaries and a maintained derived-output registry.
- The project must maintain deterministic build and test environments.
- The current Ubuntu Resolute image tag is intentionally treated as a development bootstrap only; release work must add an immutable image identity and remaining package-manager, browser, and accessibility-tool pins.
- Persistent Codex and GitHub CLI volumes improve rebuild ergonomics but create user-specific mutable state that must remain isolated from build inputs, logs, artifacts, and release evidence.
- Deterministic staged artifacts, content-scoped evidence, and release-scoped evidence require separate retention, subject-digest validation, and release-record handling.
- Fine-grained content attestations require canonical per-unit, per-entity, and per-case digests plus a release validator that proves complete current coverage, but avoid wholesale re-attestation after unrelated edits.
- Repository commit identity is a declared deterministic input, so semantically unrelated commits intentionally change the manifest.
- SQLite byte identity is reproducible relative to the pinned toolchain and container, not across arbitrary SQLite versions.
- This process weight is being accepted for a small, primarily single-maintainer rules project in exchange for long-term migration fidelity and publication integrity.
- Several controls depend on human judgment; the compensating control is checklist-driven separate-pass review with recorded attestation and continued adversarial review.
- Incremental authoring tools and vertical-slice prototypes must be maintained so release rigor does not become the only feedback loop.
- JavaScript-disabled browsers are unsupported beyond a notice.
- The architecture deliberately excludes character-state, calculator, and combat-execution behavior from the publication.

These costs are accepted because they directly protect rules authority, migration fidelity, findability, and reproducible publication.

## 18. ADR acceptance criteria

ADR-0001 is ready to move from **Proposed** to **Accepted** when maintainers agree that:

- [ ] This ADR governs architecture and process only; `KineticVanguard.yaml` is the sole authoritative v13 rules source and prevails on rules meaning.
- [ ] `schema/KineticVanguard.schema.json` is the canonical reviewed structural contract, and schema-side rules-adjacent constraints are registered.
- [ ] `policy/rules-versioning.md` governs rules-version increments and is a required build input.
- [ ] The repository identity is `kmart01123/kinetic-vanguard`, and the revision-21 development bootstrap is the checked-in Ubuntu Resolute devcontainer with Node.js 24.18.1, GitHub CLI 2.97.0, OS-provided Python, locked devcontainer features, and isolated persistent Codex/GitHub CLI configuration volumes; release conformance still requires an immutable base-image identity and the remaining toolchain pins.
- [ ] Migration uses only the SHA-256-pinned `Kinetic_Vanguard.md` master; source units use the versioned reviewable-block-content leaf model with unconditional link-destination metadata; and migration commits a gap-free source-coverage report, complete source-unit inventory, immutable disposition ledger, valid per-unit amendment chains, generated effective-ledger view, and any reviewed new-content decisions.
- [ ] Derivative Markdown files are never migration inputs, fallback sources, or completeness evidence; ambiguity resolutions carry master citations and attestations.
- [ ] The official human-readable publication is one generated release file, `KineticVanguard.html`.
- [ ] Non-release HTML uses `KineticVanguard.prototype.html`, an accessible visible prototype banner, and prototype provenance status.
- [ ] Cascading selectors and deterministic filtered search are complementary routes into the same entities and topics.
- [ ] Every publishable entity is filterable, selector-reachable, carries an accepted origin record, is classified with a complete multi-valued `rules_area` set, `entity_kind`, and applicable conditional facets, carries one non-facet `primary_rules_area`, and declares `canonical_topic_by_area` for every ambiguous rendering area.
- [ ] Classification search uses only facets and controlled values declared in `KineticVanguard.yaml`, with AND across facets and OR within multi-select facets; the sole derived value domain is the reviewed entity-identity projection.
- [ ] A grouped native single-select Name control generated from authoritative entity IDs and titles begins at an approved non-entity placeholder and uses an adjacent focusable aria-disabled Open button; selection alone does not navigate, clear filters, or move focus, valid activation uses a composed authoritative accessible name and heading focus, and no editable combobox, autocomplete, or text narrowing is present.
- [ ] The controlled facets support the canonical **Electrokinesis + Rider**, **Advanced Training + Granted**, and **Advanced Training + Selectable** cases.
- [ ] The publication has no unrestricted text-search field and no All Rules content view; saturated metadata-only result lists are permitted.
- [ ] The data model and UI distinguish granted from selectable Advanced Training without this ADR naming rules-authoritative feature assignments.
- [ ] Navigation, filter indexes, application code, templates, UI text, derived-output registries, conformance corpora, HTML, SQLite, review documents, and debug artifacts remain non-authoritative.
- [ ] Approved UI text is placement-constrained generic chrome, computed human-perceivable values use a closed derived-output registry, and every filtered-result label and accessible name uses the authoritative `{entity_title} — {primary_rules_area_label}` composition.
- [ ] Every authority leaf belongs to exactly one closed leaf class, including provenance-and-evidence metadata; every retained rule-significant leaf is directly rendered or consumed by a covered visible projection; every atomic constituent of every human-perceivable string is covered by exactly one enforced base provenance class; and multi-constituent strings are permitted only through a declared typed provenance-safe `ComposedText` template.
- [ ] Generated integrity cases are distinguished from independently reviewed correctness cases, and classification correctness receives a separate review pass rather than being checked only against itself.
- [ ] WCAG 2.2 AA is the accessibility target, with pinned automation and a scripted recorded manual screen-reader gate.
- [ ] URL fragments provide validated, bounded, shareable navigation and filter state; `history.state` is structurally restricted to allowlisted route fields and focus-origin enums; hidden local persistence is excluded.
- [ ] Deterministic release conformance separates direct declared inputs from inherited migration provenance, treats the effective-ledger view solely as a generated output, binds direct inputs through `build/inputs.json` and a canonical path/SHA-256 inventory, validates content evidence whenever consumed using an append-only evidence-policy version/hash registry, compares staged deterministic artifacts from two clean builds, and performs release binding only after the verified build-manifest hash is fixed.
- [ ] A generated SQLite database is permitted only as a pinned, canonical, deterministic non-authoritative artifact.
- [ ] SRD 5.2.1-derived general rules data is outside this ADR's initial authority and requires a separate provenance and licensing decision.
- [ ] Character-sheet, calculator, resource-tracking, and combat-execution behavior remain outside the publication scope.

## 19. Post-acceptance implementation gates

Acceptance of this ADR authorizes implementation. It does not authorize release.

Release requires, in order:

1. `policy/rules-versioning.md`, `schema/rules-adjacent-constraints.yaml`, `build/inputs.json`, `review/content-evidence-policy.json`, the append-only `review/content-evidence-policy-registry.json`, the selected build-profile contract, canonical digest conventions, and the selected deterministic environment contract committed and reviewed; when the checked-in devcontainer is used, this includes `.devcontainer/devcontainer.json`, `.devcontainer/devcontainer-lock.json`, an immutable base-image identity, and explicit exclusion of persistent Codex and GitHub CLI state from build inputs;
2. pinned migration-source manifest with exact filename, SHA-256, repository commit, and inherited-provenance contract;
3. canonical schema and provisional authoring vertical-slice review; a content-free tooling spike may precede step 2, but no migrated rule content may;
4. committed source-coverage report proving exact source partition under the versioned reviewable-block-content leaf model, unconditional link-destination metadata, and a complete source-unit inventory;
5. complete immutable disposition ledger, valid per-unit amendment change mappings and chains, generated effective-ledger view, qualifying entity origin records, and reviewed new-content decisions;
6. migration acceptance, including gap-free source-span coverage, source-unit disposition coverage, entity-side orphan detection, new-content-origin evidence, classification review, aggregate deferral-set review, ambiguity-resolution attestations, and content-validity verification of every consumed evidence subject, policy binding, and digest-migration chain without requiring a release build-manifest hash;
7. direct-or-indirect coverage of every retained rule-significant leaf, closed classification of every authority leaf including provenance-and-evidence metadata, and enforced three-class atomic-constituent provenance validation;
8. selector reachability, rules-area/topic redundancy validation, Name-label uniqueness, per-area canonical-route validation, deterministic result-activation-area validation, authoritative result-label disambiguation, generated filtered-search integrity checks, globally disabled zero-result values, and independently reviewed correctness conformance;
9. native non-editable Name-select plus explicit Open-button validation, including placeholder initial, direct-route, destination, and reset states; focusable aria-disabled behavior; static inactive accessible naming and persistent description; inert activation without live-region output; reviewed composed accessible naming; no change on selection; `pushState`; authoritative-heading focus placement; Back/Forward restoration; and structural rejection of unauthorized `history.state` content;
10. prototype identity and deployable-directory isolation tests, with profile-tagged accessibility-script steps proving prototype-banner presence and release-banner absence as applicable and validating `not_applicable` only for steps that explicitly authorize it with a rationale;
11. two complete clean staged builds through manifest emission, each proving a clean direct-declared-input Git state and identical canonical path/SHA-256 direct-input inventory, with inherited migration provenance recorded separately and byte-identical staged deterministic artifacts—including the generated effective-ledger view and canonical SQLite when retained—and pinned automated accessibility assertions required by the staged profile;
12. successful deterministic build-manifest comparison and selection of the verified staged publication and manifest hash;
13. revalidation of current content validity against narrow declared subject digests, the append-only policy-version/hash registry, every required reviewed digest-migration chain, and complete source-migration, new-content-origin, classification, correctness-case, and deferral evidence coverage;
14. production of release-scoped evidence against that verified staged publication, including any non-deterministic scanner or browser reports as classified under section 14, the profile-tagged recorded manual screen-reader script report, release-specific accepted-known-issue approvals, and the per-release aggregate deferral re-review carrying current effective-ledger, amendment-set, and deferral-set digests;
15. completed release evidence record bound to the verified build-manifest hash and hashing all required current content-scoped evidence, accepted digest-migration records, subject-coverage maps, policy-registry identity, and release-scoped evidence;
16. atomic promotion of the verified `KineticVanguard.html` into a freshly constructed one-file deployable directory with `release_status: release`.


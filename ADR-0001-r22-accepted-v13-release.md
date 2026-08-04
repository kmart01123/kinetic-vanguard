# ADR-0001 revision 22: Acceptance and v13.0 release decision

- **Status:** Accepted
- **Date:** 2026-08-03
- **Repository:** `kmart01123/kinetic-vanguard`
- **Decision owner:** Kyle Martin, Kinetic Vanguard maintainer
- **Supersedes:** ADR-0001 revision 21 and all earlier drafts
- **Incorporates by reference:** `ADR-0001-r21-schema-first-rules-architecture.md`

## Decision

ADR-0001 revision 21 is accepted as the architecture for Kinetic Vanguard v13. Its schema-first authority, deterministic static publication, finite selector and filtered-search model, offline behavior, accessibility target, and prohibition on shadow rules authorities remain in force.

The repeated adversarial-review cycle is closed. Later reviews found no unresolved architectural blocker; the remaining material risk was the process cost of the full evidence regime for a primarily single-maintainer rules project. Further paper review has lower value than shipping and testing the implemented product.

## v13.0 release ruling

Kinetic Vanguard v13.0 may ship from the current schema-first authority when all automated release checks pass:

- schema and semantic validation;
- architecture and publication tests;
- filter and route integrity tests;
- deterministic build comparison;
- Chromium and Firefox desktop/mobile layout checks;
- release identity checks proving the publication is not marked as a prototype.

For v13.0 only, the following revision-21 release gates are waived as release blockers rather than falsely recorded as completed:

- reviewed dispositions and attestations for every legacy migration source unit;
- independent second-pass evidence for the filtered-search correctness corpus;
- a build-bound manual screen-reader report and full release-evidence record;
- an immutable digest for the development-container base image.

The migration inventory, source coverage, origins, correctness corpus, and evidence-policy files remain checked-in provenance and validation inputs. Their incomplete human-review state must remain visible in diagnostics and must not be rewritten as completed evidence.

This waiver does not weaken the sole-authority rule: `KineticVanguard.yaml` is the complete and controlling v13 rules source. It also does not permit release builds with schema, semantic, test, deterministic-output, layout, or release-identity failures.

## Release disposition

- **Rules version:** 13.0.0
- **Release status:** Approved for release after green CI
- **Publication:** `KineticVanguard.html`
- **Known follow-up:** Forked Lightning needs explicit failed-save wording for non-primary targets; track for v13.0.1.

## Consequences

The project ships a usable, tested product now instead of manufacturing evidence that was not actually reviewed. The stricter evidence system remains available for future releases if its value justifies its maintenance cost. v13.0.1 may focus on concrete rules and presentation defects found in use.

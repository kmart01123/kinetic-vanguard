# Kinetic Vanguard release checklist

Use this checklist for every development line and release. The README is a maintained public entry point: review its release and orientation prose deliberately, and regenerate its delimited damage-matrix region only when fresh analytical evidence is required. Keep mutable branch and pull-request pointers in GitHub rather than copying them into README status, so merged or superseded work cannot leave stale public metadata behind.

## Branch and release-reference hygiene

- `main` is permanent.
- Frozen `release/*` branches are permanent and immutable. Never delete or rewrite them.
- Annotated release tags and GitHub Releases are permanent. Never delete or repoint them as part of branch cleanup.
- Temporary development branches are deleted after their pull requests merge. GitHub's automatic head-branch deletion setting is the normal cleanup mechanism.
- A branch associated with open or otherwise unmerged work must not be deleted.
- The weekly branch-hygiene audit flags non-release branches that have no open pull request and whose head commit is older than 14 days. The audit reports candidates but never deletes them; verify each candidate before manual cleanup.
- Treat branch hygiene as normal post-merge and post-release housekeeping.

## Start of a development line

- [ ] Branch from the current `main` after the previous release and publication work is complete.
- [ ] Set canonical `rules_version` in `KineticVanguard.yaml`.
- [ ] Update `README.md`:
  - current published release and tag;
  - current development line;
  - current development goals and interface capabilities;
  - supported Node.js and npm versions;
  - known follow-ups, removing completed work.
- [ ] Do not add active branch names, release-candidate branch names, implementation pull-request numbers, or other mutable work-in-progress pointers to README release status. Track those in GitHub issues and pull requests instead.
- [ ] Decide whether the development-line changes require fresh analytical evidence under the benchmark-evidence rule below. A rules-version or README release-status change alone does not require recomputation.
- [ ] Open or update the shared development issue and draft pull request in GitHub.

## Before marking a release pull request ready

- [ ] Compare `README.md` with:
  - `KineticVanguard.yaml` and canonical `rules_version`;
  - `CHANGELOG.md`;
  - the release pull request description;
  - current open issues;
  - `.github/workflows/ci.yml` and artifact naming;
  - actual build commands and output paths;
  - current interface, browser, accessibility, offline, and print guarantees;
  - `LICENSE.md` and `NOTICE.md`;
  - `docs/licensing-audit.md` and any documented unresolved maintainer/legal questions.
- [ ] Confirm the README does not describe an older active release, obsolete artifact name, resolved follow-up, or mutable branch/pull-request pointer.
- [ ] Confirm the README summarizes the project without duplicating canonical rules text.
- [ ] Decide whether a fresh full-roster analytical benchmark run is required. It is required only when:
  - benchmark inputs changed;
  - evaluator or planner logic changed;
  - methodology changed;
  - comparator or roster data changed; or
  - the specific release gate explicitly requires fresh evidence.
- [ ] When one of those triggers applies, record the trigger and run `npm run harness:damage -- --output-dir <private-output>` exactly once. Then reuse and validate that run with `npm run readme:damage -- --report-input <private-output>/run-manifest.json` and `npm run readme:damage:check -- --report-input <private-output>/run-manifest.json`; both synchronization commands must read the same manifest and must not evaluate the analytical universe again. Investigate and commit the synchronized numerical diff. Otherwise, do not recompute an unchanged analytical universe or rewrite its evidence merely for release metadata.
- [ ] Run the focused current-methodology validation commands `npm run harness:validate` and `npm run test:harness`; they protect the fail-closed damage and Control Authority v2 projections and maintained evaluator/report contracts without running the full analytical universe.
- [ ] Confirm harness outputs derive filenames and provenance from canonical `rules_version` and authority digest.
- [ ] Confirm every damage CSV carries structured component/SRD/comparator notices and damage-matrix Markdown/HTML exposes the same licensing-and-notices section.
- [ ] Confirm damage-matrix CSVs retain benchmark type/scope, raw KV/Battle Master/Eldritch Knight aggregates, both ordinary ratios, explicit lower/upper comparator identities and boundary values, classification, signed `Boundary Delta %`, and provenance.
- [ ] Keep the generated README region limited to one single-target damage heat table. A release may intentionally carry no authoritative current control headline while #32 and #39–#42 remain in progress. Keep the following control-methodology section static, historical/transitional, and free of a current control table or classification; this temporary gap is not by itself a release blocker.
- [ ] Confirm `.codex-import/`, generated benchmark results, caches, virtual environments, and downloaded archives are absent from tracked files and `build/inputs.json`.
- [ ] Confirm BM/EK assumptions remain minimal and isolated under `harness/comparators/`, absent from canonical YAML, separately hashed in report provenance, and covered by the third-party notice.
- [ ] Record current harness certification/review status honestly; historical certification does not automatically carry forward.
- [ ] Review `policy/superseded-implementations.md` and confirm superseded commands, runtimes, schemas, reports, assets, compatibility aliases, parity gates, and golden outputs were removed unless an approved exception names a reason, owner, and sunset.
- [ ] Scan every package script and every CI/release workflow. Confirm none invokes the retired Control Reliability stack or expects its report assets, and confirm no current-version publication workflow was carried forward as maintained release wiring.
- [ ] Confirm frozen release branches, tags, GitHub Releases, published evidence assets, and Git history remain intact as the historical reproduction path.
- [ ] Confirm the build manifest declares and hashes `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, and `NOTICE.md`.
- [ ] Confirm generated HTML retains scoped copyright, exact SRD attribution, the SRD modification/disclaimer notices, canonical license URLs, and no blanket license claim.
- [ ] Confirm the exact release-candidate commit passed the complete required validation suite through `Main branch gate`, and run `git diff --check`. Do not repeat the same complete suite during publication; any post-gate code or artifact change requires a new exact-head gate.
- [ ] Confirm all review conversations are resolved.
- [ ] Confirm the branch is up to date with `main`.
- [ ] Confirm the `Protect main` ruleset is active and still requires the stable gate.

## Publication

Generalized publication-workflow and shared-verifier design is intentionally deferred to focused follow-up work. The checks below state the irreversible publication invariants without prescribing or adding another version-specific workflow.

- [ ] Squash-merge the verified release pull request into `main`.
- [ ] Confirm the merged temporary development branch was deleted, while preserving `main`, every frozen `release/*` branch, release tags, GitHub Releases, and all heads associated with open or unmerged work.
- [ ] Record the exact merged release commit.
- [ ] Create and freeze `release/X.Y.Z` at that exact commit.
- [ ] Create or verify the annotated `vX.Y.Z` tag at the approved release SHA.
- [ ] Before an authorized release-profile build or upload, verify that `release/X.Y.Z` resolves to the approved SHA, the checked-out `HEAD` is that exact SHA, and annotated `vX.Y.Z` peels to the same SHA.
- [ ] Confirm that exact frozen commit already passed the required release gate. Do not run the complete suite again during publication unless the snapshot changed; a changed snapshot requires a new approved SHA and exact-head gate.
- [ ] Require explicit authorization for the release-profile build and confirm `npm run build:release` succeeds.
- [ ] Verify in one cohesive release-artifact check that the deployable has release status and canonical rules-version identity; contains no prototype marker or application-version leakage; and includes a build manifest, filtered-search integrity report, coverage ledger, and all required legal assets. Reuse a maintained command or script when available instead of copying identical assertions into version-specific workflows.
- [ ] Publish or update the GitHub Release and upload all required assets.
- [ ] If `npm run promote` is used, confirm the deployable contains the HTML plus all four legal assets and no stale files.
- [ ] Update `README.md`:
  - promote the new version to current published release;
  - link the permanent tag and GitHub Release;
  - set the current development line to **None** unless the next line already exists;
  - verify downloadable asset naming;
  - keep live branch, issue, and pull-request tracking in GitHub rather than README.
- [ ] Review the README publication-status and permanent-link diff. Release metadata or status alone does not require `npm run readme:damage` or `npm run readme:damage:check`; run them only when a benchmark-evidence trigger above applies.
- [ ] Close completed release issues and record final validation.

## Required release assets

- `KineticVanguard.html`
- `build-manifest.json`
- `filtered-search-integrity.json`
- `coverage-ledger.json`
- `LICENSE.md`
- `LICENSE-CODE`
- `LICENSE-CONTENT`
- `NOTICE.md`

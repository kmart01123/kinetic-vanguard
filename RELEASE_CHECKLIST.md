# Kinetic Vanguard release checklist

Use this checklist for every development line and release. The README is a maintained public entry point: its release and orientation prose is reviewed deliberately, while its delimited damage-matrix region is regenerated from the exact analytical harness. Keep mutable branch and pull-request pointers in GitHub rather than copying them into README status, so merged or superseded work cannot leave stale public metadata behind.

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
- [ ] Run `npm run readme:damage` after the canonical version and README release lines agree, review the generated numerical and release-label diff, and run `npm run readme:damage:check`.
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
- [ ] After any intentional damage-authority, methodology, roster, damage-comparator, classification, or reporting change, run `npm run readme:damage`, investigate the numerical diff, and commit the synchronized README region; never normalize a difference merely to match an old snapshot.
- [ ] Run `npm run readme:damage:check` and confirm it completes fresh full-roster exact analytical damage evaluation without relying on a tracked golden result or Monte Carlo sampling.
- [ ] Run `npm run harness:validate` and `npm run test:harness`.
- [ ] Confirm harness outputs derive filenames and provenance from canonical `rules_version` and authority digest.
- [ ] Confirm every damage CSV carries structured component/SRD/comparator notices and damage-matrix Markdown/HTML exposes the same licensing-and-notices section.
- [ ] Confirm damage-matrix CSVs retain benchmark type/scope, raw KV/Battle Master/Eldritch Knight aggregates, both ordinary ratios, explicit lower/upper comparator identities and boundary values, classification, signed `Boundary Delta %`, and provenance.
- [ ] Keep the generated README region limited to one single-target damage heat table. Keep the following control-methodology section static, historical/transitional, and free of a current control table or classification.
- [ ] Confirm `.codex-import/`, generated benchmark results, caches, virtual environments, and downloaded archives are absent from tracked files and `build/inputs.json`.
- [ ] Confirm BM/EK assumptions remain minimal and isolated under `harness/comparators/`, absent from canonical YAML, separately hashed in report provenance, and covered by the third-party notice.
- [ ] Record current harness certification/review status honestly; historical certification does not automatically carry forward.
- [ ] Review `policy/superseded-implementations.md` and confirm superseded commands, runtimes, schemas, reports, assets, compatibility aliases, parity gates, and golden outputs were removed unless an approved exception names a reason, owner, and sunset.
- [ ] Scan every package script and every CI/release workflow. Confirm none invokes the retired Control Reliability stack or expects its report assets, and confirm no current-version publication workflow was carried forward as maintained release wiring.
- [ ] Confirm frozen release branches, tags, GitHub Releases, published evidence assets, and Git history remain intact as the historical reproduction path.
- [ ] Confirm the build manifest declares and hashes `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, and `NOTICE.md`.
- [ ] Confirm generated HTML retains scoped copyright, exact SRD attribution, the SRD modification/disclaimer notices, canonical license URLs, and no blanket license claim.
- [ ] Run the complete validation suite and `git diff --check`.
- [ ] Confirm all review conversations are resolved.
- [ ] Confirm the branch is up to date with `main`.
- [ ] Confirm `Main branch gate` passes.
- [ ] Confirm the `Protect main` ruleset is active and still requires the stable gate.

## Publication

- [ ] Squash-merge the verified release pull request into `main`.
- [ ] Confirm the merged temporary development branch was deleted, while preserving `main`, every frozen `release/*` branch, release tags, GitHub Releases, and all heads associated with open or unmerged work.
- [ ] Record the exact merged release commit.
- [ ] Create and freeze `release/X.Y.Z` at that exact commit.
- [ ] Add an idempotent publication workflow that verifies the frozen commit.
- [ ] Create or verify the annotated `vX.Y.Z` tag.
- [ ] Publish or update the GitHub Release and upload all required assets.
- [ ] If `npm run promote` is used, confirm the deployable contains the HTML plus all four legal assets and no stale files.
- [ ] Update `README.md`:
  - promote the new version to current published release;
  - link the permanent tag and GitHub Release;
  - set the current development line to **None** unless the next line already exists;
  - verify downloadable asset naming;
  - keep live branch, issue, and pull-request tracking in GitHub rather than README.
- [ ] Run `npm run readme:damage` after the publication-status edit so the generated damage snapshot says **Published** for canonical `rules_version`, then run `npm run readme:damage:check` and review the resulting diff.
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

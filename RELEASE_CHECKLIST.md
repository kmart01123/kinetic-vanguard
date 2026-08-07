# Kinetic Vanguard release checklist

Use this checklist for every development line and release. The README is a maintained public entry point, not generated output, so its status must be reviewed deliberately.

## Start of a development line

- [ ] Branch from the current `main` after the previous release and publication work is complete.
- [ ] Set canonical `rules_version` in `KineticVanguard.yaml`.
- [ ] Update `README.md`:
  - current published release and tag;
  - current development line and branch;
  - active draft pull request;
  - current development goals and interface capabilities;
  - supported Node.js and npm versions;
  - known follow-ups, removing completed work.
- [ ] Open or update the shared development issue and draft pull request.

## Before marking a release pull request ready

- [ ] Compare `README.md` with:
  - `KineticVanguard.yaml` and canonical `rules_version`;
  - `CHANGELOG.md`;
  - the release pull request description;
  - current open issues;
  - `.github/workflows/ci.yml` and artifact naming;
  - actual build commands and output paths;
  - current interface, browser, accessibility, offline, and print guarantees;
  - `LICENSE.md` and `NOTICE.md`.
- [ ] Confirm the README does not describe an older active release, obsolete artifact name, or resolved follow-up.
- [ ] Confirm the README summarizes the project without duplicating canonical rules text.
- [ ] Run `npm run harness:validate` and `npm run test:harness`.
- [ ] Confirm harness outputs derive filenames and provenance from canonical `rules_version` and authority digest.
- [ ] Confirm `.codex-import/`, generated benchmark results, caches, virtual environments, and downloaded archives are absent from tracked files and `build/inputs.json`.
- [ ] Confirm BM/EK assumptions remain minimal and isolated under `harness/comparators/`, absent from canonical YAML, separately hashed in report provenance, and covered by the third-party notice.
- [ ] Record current harness certification/review status honestly; historical certification does not automatically carry forward.
- [ ] Run the complete validation suite and `git diff --check`.
- [ ] Confirm all review conversations are resolved.
- [ ] Confirm the branch is up to date with `main`.
- [ ] Confirm `Main branch gate` passes.
- [ ] Confirm the `Protect main` ruleset is active and still requires the stable gate.

## Publication

- [ ] Squash-merge the verified release pull request into `main`.
- [ ] Record the exact merged release commit.
- [ ] Create and freeze `release/X.Y.Z` at that exact commit.
- [ ] Add an idempotent publication workflow that verifies the frozen commit.
- [ ] Create or verify the annotated `vX.Y.Z` tag.
- [ ] Publish or update the GitHub Release and upload all required assets.
- [ ] Update `README.md`:
  - promote the new version to current published release;
  - link the permanent tag and GitHub Release;
  - remove obsolete development-branch and draft-PR wording;
  - set the current development line to **None** unless the next line already exists;
  - verify downloadable asset naming.
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

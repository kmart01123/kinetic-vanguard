# Kinetic Vanguard release checklist

Use this checklist for actual release and publication work.

## Before release

- [ ] Set and verify the canonical `rules_version`.
- [ ] Update `README.md` and `CHANGELOG.md`.
- [ ] Run `npm run typecheck`, `npm run validate`, `npm test`, `npm run harness:validate`, `npm run test:harness`, `npm run build`, `npm run test:determinism`, `npm run test:layout`, and the authorized `npm run build:release`.
- [ ] Run the damage and control benchmarks once when rules, comparator behavior, roster, methodology, or benchmark code changed.
- [ ] Review and synchronize the README benchmark results.
- [ ] Verify the legal files and generated release identity.
- [ ] Confirm GitHub CI passes.

## Publication

- [ ] Squash-merge the release pull request.
- [ ] Record the exact merged release commit.
- [ ] Create and freeze the `release/X.Y.Z` branch and annotated `vX.Y.Z` tag at that commit.
- [ ] Publish the GitHub Release and required assets.
- [ ] Update the README published status.

## Required release assets

- `KineticVanguard.html`
- `build-manifest.json`
- `filtered-search-integrity.json`
- `coverage-ledger.json`
- `LICENSE.md`
- `LICENSE-CODE`
- `LICENSE-CONTENT`
- `NOTICE.md`

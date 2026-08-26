# Kinetic Vanguard release checklist

Use this checklist for an actual release. Frozen release refs and published GitHub Releases are immutable records. An unexpected pre-existing release branch, tag, or GitHub Release is a STOP condition; do not recover by editing, clobbering, or force-moving it.

## Prepare and freeze the candidate

- [ ] Finish and independently review the release-prep pull request.
- [ ] Reconcile `CHANGELOG.md` from development history into concise final release outcomes; remove stale intermediate wording and implementation-diary detail before freezing the candidate.
- [ ] Set the canonical `rules_version`, release notes, and `CHANGELOG.md` for `X.Y.Z`.
- [ ] Confirm whether rules, comparators, roster, methodology, or benchmark code changed. Run fresh analytical evidence only when that input-aware policy requires it.
- [ ] Squash-merge the exact candidate and record the merged commit SHA.
- [ ] Confirm the ordinary `Main branch gate` succeeds naturally for that exact SHA.
- [ ] Confirm `release/X.Y.Z`, annotated `vX.Y.Z`, and the GitHub Release do not already exist unexpectedly.
- [ ] Create and push `release/X.Y.Z` and annotated `vX.Y.Z` at the same approved SHA, then treat both refs as frozen.

## Verify on GitHub

- [ ] Manually dispatch `.github/workflows/release-verify.yml` against `release/X.Y.Z` with only `version=X.Y.Z` and the full `approved_sha`.
- [ ] Confirm the run verifies the selected release ref, exact SHA, annotated tag peel, and successful exact-SHA ordinary CI before building.
- [ ] Confirm the authorized release build succeeds and the generated HTML has canonical `rules_version` and release identity, no prototype marker, and no application/package version leakage.
- [ ] Confirm the run uploads one `kinetic-vanguard-X.Y.Z-candidate` artifact containing exactly:
  - `KineticVanguard.html`
  - `LICENSE.md`
  - `LICENSE-CODE`
  - `LICENSE-CONTENT`
  - `NOTICE.md`
  - `SHA256SUMS`

## Independent review

- [ ] Give Claude or another independent reviewer the exact artifact from the successful release-verification run.
- [ ] Record the review on the release issue with the version, approved SHA, workflow run ID, artifact name, GitHub artifact digest, reviewer, and `PASS` or findings.
- [ ] Record the maintainer disposition for every finding. A changed SHA or artifact digest makes the review stale and requires a new review.

## Publish deliberately

- [ ] Download the artifact from the exact reviewed run and run `sha256sum -c SHA256SUMS` in its directory.
- [ ] Confirm again that no GitHub Release unexpectedly exists for `vX.Y.Z`.
- [ ] Use one deliberate `gh release create` command to publish the exact five checksummed assets plus `SHA256SUMS`. Do not use `gh release edit`, upload `--clobber`, or force-update a ref.
- [ ] Download all published assets into a fresh directory and run `sha256sum -c SHA256SUMS` again.
- [ ] Update README published status separately on `main`; never rewrite the frozen release ref.

Local release builds remain available for focused verification and require the single explicit authorization boundary:

```text
KV_RELEASE_APPROVED=1 npm run build:release
```

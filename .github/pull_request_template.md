## Summary

Describe the change, why it is needed, and any user-facing or rules impact.

## Validation

- [ ] Relevant focused checks passed.
- [ ] `npm run typecheck`
- [ ] `npm run validate`
- [ ] `npm test`
- [ ] `npm run build`
- [ ] `npm run test:determinism`
- [ ] `npm run test:layout`
- [ ] Authorized release build, when applicable.
- [ ] `git diff --check`

## Release readiness

For development-line, release, or publication pull requests, complete `RELEASE_CHECKLIST.md`.

- [ ] `README.md` was reviewed and updated, or this PR explains why it is not applicable.
- [ ] `CHANGELOG.md` was updated when the change is user-facing.
- [ ] Canonical authority and generated outputs remain correctly separated.
- [ ] Review conversations are resolved before merge.
- [ ] `Main branch gate` passes before merge.

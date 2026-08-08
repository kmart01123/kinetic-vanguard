# Superseded implementation retirement policy

## Purpose

Current `main` should describe and execute the project's maintained architecture. Once a successor is viable, the implementation it supersedes must be retired from `main`; historical reproducibility alone is not a reason to keep obsolete runtime code maintained.

## Required disposition

- Preserve released history through frozen release branches, annotated tags, GitHub Releases, published evidence assets, and Git history. Do not move an obsolete executable stack into a maintained `legacy`, `archive`, or compatibility directory merely to reproduce an old release.
- Carry forward principles and invariants that remain valuable—such as canonical authority, deterministic evaluation, fail-closed validation, provenance, exact policy reasoning, comparator neutrality, and independent review—without carrying forward obsolete code structure, labels, scenarios, schemas, or outputs.
- Remove superseded commands, runtime paths, data, reports, assets, release wiring, tests, and documentation from current development when they no longer serve the successor.
- Prefer a clearly documented temporary capability gap over publishing a result known to come from a superseded or misleading methodology.

## No indefinite dual stacks

Do not retain parallel old and new implementations, output-parity gates, golden outputs, compatibility aliases, duplicate schemas, or ongoing runtime and CI burden by default. A temporary exception requires all of the following in an approved issue or decision record:

1. a concrete reason the retained implementation is still necessary;
2. a named owner responsible for its removal; and
3. a specific sunset date or release milestone.

The owner must remove the exception when the approved condition ends. An exception must not silently become permanent because downstream callers or tests were left unchanged.

## Release and review check

Every architecture replacement and release review must verify that maintained commands, CI, release workflows, build manifests, public documentation, report expectations, and test suites no longer execute or present the superseded stack. Historical references must be labeled as historical and point to frozen evidence rather than acting as current instructions.

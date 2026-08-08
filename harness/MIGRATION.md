# Historical v14.1 harness restoration record

This file records the one-time v14.1 restoration and independent review of benchmark source descended from the v12-era harness. It is historical evidence, not current migration guidance and not a supported route for reintroducing retired code into `main`.

Version 14.1 moved Kinetic Vanguard mechanics into a validated projection of the canonical root `KineticVanguard.yaml`, isolated methodology, SRD roster data, and third-party comparator assumptions, and replaced sampling execution with exact analytical evaluation. The damage review retained documented numerical differences instead of normalizing current results to old output.

The v14.1 Control Reliability evaluator, flattened control mechanics, comparator scenarios, configuration, reports, selection audit, README matrix, and publication workflow were retired from current development in v14.2. Their reproducibility remains permanently available through frozen `release/14.1.0`, tag `v14.1.0`, the v14.1 GitHub Release and evidence assets, and Git history.

Maintained work now uses the damage-only commands and architecture documented in `README.md`. Control Authority v2 is a separate structured redesign contract and must not be populated from this historical mapping.

The surviving damage review provenance is recorded in `provenance/damage-review.json`. No legacy import, compatibility alias, parity gate, or golden output is a maintained migration path.

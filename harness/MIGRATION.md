# Historical v14.1 harness restoration record

This file records the one-time v14.1 restoration and independent review of benchmark source descended from the v12-era harness. It is historical evidence, not current migration guidance and not a supported route for reintroducing retired code into `main`.

Version 14.1 moved Kinetic Vanguard mechanics into a validated projection of the canonical root `KineticVanguard.yaml`, isolated methodology, SRD roster data, and third-party comparator assumptions, and replaced sampling execution with exact analytical evaluation. The damage review retained documented numerical differences instead of normalizing current results to old output.

The v14.1 Control Reliability evaluator, flattened control mechanics, comparator scenarios, configuration, reports, selection audit, README matrix, and publication workflow were retired from current development in v14.2. Their reproducibility remains permanently available through frozen `release/14.1.0`, tag `v14.1.0`, the v14.1 GitHub Release and evidence assets, and Git history.

Maintained work now uses the damage-only commands and architecture documented in `README.md`. Control Authority v2 and `ControlTarget` survive only as static input contracts for separately approved future design and must not be populated from this historical mapping.

The surviving damage review provenance is recorded in `provenance/damage-review.json`. No legacy import, compatibility alias, parity gate, or golden output is a maintained migration path.

## Current v14.2 control boundary

The superseded current-development control execution runtime is retired. No maintained v14.2 control evaluator or current v14.2 control result exists, and no compatibility or fallback runtime is retained. Future replacement work must begin from a separately approved minimum execution contract; the simpler named-condition runner is also future work and remains unimplemented.

## v14.2 creature-input retirement boundary

Issue #55 replaced the current-development `data/srd_targets.csv`, `data/srd_control_targets.json`, their exact level/name join, and `control_targets.py`/TypeScript twin with one 330-record catalog, separate deterministic roster profiles, consumer requirements, and sibling thin projections. Before deletion, a private machine comparison against base commit `279bb4edfe0e6a52a7ecae60d39957e3bde56b0f` joined 28/28 historical rows in order and matched 812/812 required consumed fields plus 28/28 CR facts after documented structural normalization.

The old files remain historical evidence through Git and frozen v14.1 refs. They are not copied, aliased, dual-read, or retained as a golden. Maintained work uses common catalog/roster logic in `creature_catalog.py`, sibling projections in `creature_damage_projection.py` and `creature_control_projection.py`, `data/srd_creatures.json`, `data/srd_creature_rosters.json`, `config/creature-consumers.json`, and `provenance/srd-creatures.json`. Neither sibling restores or aliases the retired v14.1 control supplement, and live scenario state stays outside these static records and projections.

# SRD 5.2.1 creature catalog audit

The maintained catalog contains 330 unique stat blocks from the official SRD 5.2.1 PDF (SHA-256 `8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87`). It was recovered from the vetted issue #55 / PR #59 source at `dcd7c3e6b0b1f497ac530b2f425e8bbc7953f596`; the source was not re-scraped.

`harness/data/srd_creatures.json` is the one static source-fact catalog. It retains stable IDs, display names, CR, AC, HP, six raw ability modifiers, sparse source-explicit saves and skills, Magic and Legendary Resistance, size/type, condition and damage defenses, movement/hover, senses, passive Perception, and page/order anchors. An absent skill is not an explicit +0. Live encounter state is excluded.

`harness/data/srd_creature_rosters.json` is the one ordered membership source:

| Profile | Level 7 | Level 11 | Level 15 | Level 20 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `legacy_v14_1` | 8 | 6 | 6 | 8 | 28 |
| `headline` | 12 | 12 | 11 | 12 | 47 |
| `eligible_census` | 47 | 20 | 11 | 15 | 93 |

The historical candidate bands contained 101 creatures; eight creatures with unsupported or unresolved material mechanics were excluded before the 93-creature feasible census was frozen. The 47-creature headline was then selected for bounded source-mechanical diversity using only source facts, with deterministic source-order tie-breaking. No Kinetic Vanguard, Battle Master, Eldritch Knight, scenario, result, envelope, or HOT/IDEAL/COLD value participated.

Both damage and control use the same `Target` projection and the same `load_targets(profile=...)` path. The legacy profile reproduces all 28 prior ordered target inputs exactly. Historical control engines, replay/provenance runtimes, separate consumer databases, result contracts, passive-trait registries, selection traces, compatibility loaders, and CI benchmark machinery were intentionally not restored.

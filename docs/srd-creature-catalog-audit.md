# SRD 5.2.1 creature catalog audit

The maintained catalog contains 330 unique stat blocks from the official SRD 5.2.1 PDF (SHA-256 `8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87`).

`harness/data/srd_creatures.json` is the one static source-fact catalog. It retains stable IDs, display names, CR, AC, HP, six raw ability modifiers, sparse source-explicit saves and skills, Magic and Legendary Resistance, size/type, condition and damage defenses, movement/hover, senses, passive Perception, and page/order anchors. An absent skill is not an explicit +0. Live encounter state is excluded.

`harness/data/srd_creature_rosters.json` is the one ordered membership source:

| Profile | Level 7 | Level 11 | Level 15 | Level 20 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `headline` | 12 | 12 | 11 | 12 | 47 |
| `eligible_census` | 47 | 20 | 11 | 15 | 93 |

The eligible census applies the closed level/CR bands and excludes eight creatures with unsupported or unresolved material mechanics. The 47-creature headline is selected for bounded source-mechanical diversity using only source facts, with deterministic source-order tie-breaking. No Kinetic Vanguard, Battle Master, Eldritch Knight, scenario, result, envelope, or HOT/IDEAL/COLD value participates.

Both damage and control use the same `Target` projection and the same `load_targets(profile=...)` path.

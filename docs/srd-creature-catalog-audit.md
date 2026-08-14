# SRD 5.2.1 creature catalog and roster audit

Status: implemented; the source catalog and source-only roster were frozen in issue #55 comment `5252064760`. The pre-correction v14.2 expanded-roster run is permanently marked `invalidated_premerge_provenance_boundary_correction` and retained only as comparison evidence. One completed corrected-contract replacement now binds the consumer-scoped damage provenance and exactly matches every numerical and classification field in the invalidated run. No numerical defect was demonstrated, and no independent numerical or Monte Carlo certification is claimed.

## Authority and extraction

The maintained authority is the official D&D SRD 5.2.1 PDF at `https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf`. The verified file is 6,031,375 bytes, has 364 pages, and has SHA-256 `8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87`.

One whole-document text layer and coordinate/font metadata were extracted with Poppler 26.01.0. No OCR, private PHB material, or fallback creature source was used. Pages 258–364 contain 330 actual stat blocks: 235 Monsters A–Z blocks and 95 Animals blocks. Every accepted block has one source page/order identity, one size/type line, the ordered AC/HP/Speed headers, six ability cells, senses/passive Perception, CR/XP/PB, and a deterministic canonical ID. The first identity is Aboleth at `p258-o001`; the last is Wolf at `p364-o330`.

The extraction provenance, tool options, intermediate digests, visual-check pages, modification notice, and the two source-printed exceptions are recorded in [`harness/provenance/srd-creatures.json`](../harness/provenance/srd-creatures.json). Extraction inputs remain private scratch artifacts and are not repository authorities.

## Maintained contracts

| Contract | ID | Version |
| --- | --- | --- |
| Creature catalog | `srd521_creature_catalog` | 1.0.0 |
| Roster/profile document | `srd521_creature_rosters` | 1.0.0 |
| Passive-trait registry | `srd521_passive_trait_registry` | 1.0.0 |
| Consumer requirements | `srd521_creature_consumer_requirements` | 1.0.0 |
| DamageTarget projection | `srd521_damage_target` | 1.0.0 |
| ControlTarget projection | `srd521_control_target` | 1.0.0 |
| Future planner static projection | `srd521_planner_static_target` | 1.0.0, declared but not implemented |

The current whole consumer-requirements registry SHA-256 is `5ceaae5dd15bc1dd1fe7dc04d57033fd6d7514fa30b066183162daf12f21d58e`; it is repository-integrity metadata. The current damage-consumer requirements SHA-256 is `a394e60b24aa2901369b12877adb6fad5e2b1be8180c416c3441361be6dd1ac1`, and the current control-consumer requirements SHA-256 is `2549ae2884aeb11bf53e3f079afc094172f5288276cd036ea86181381c4fd3d5`. Future evidence must bind its precise consumer-scoped field rather than the coarse whole-registry digest. The invalidated comparison manifest permanently retains its original coarse digest as historical evidence.

[`harness/data/srd_creatures.json`](../harness/data/srd_creatures.json) is the sole maintained source-fact catalog. [`harness/data/srd_creature_rosters.json`](../harness/data/srd_creature_rosters.json) separately owns eligibility, complete candidate accounting, profile membership, exact rational weights, greedy traces, numeric bucket maps, token universes, coverage, and family audits. Python is the semantic owner; TypeScript performs only inexpensive shape, digest, ordering, and manifest checks.

Catalog facts, roster facts, and live scenario state are separate. `DamageTarget` and `ControlTarget` are sibling projections. `ControlTarget` includes passive Perception and a canonically sorted tuple of sparse, source-explicit skill facts. Each fact retains the canonical skill ID, its canonical associated ability ID, the final source-authored bonus, and source-explicit status. An unlisted skill has no fabricated row and later check resolution falls back to the associated raw ability modifier; absence is not an explicit +0. Live Advantage, Disadvantage, roll mode, condition or equipment effects, and all other check circumstances remain scenario/event state. Neither projection owns benchmark level or weight, and neither contains current position, visibility relation, airborne state, route, concentration, Reaction availability, current conditions, held/wielded/dropped state, or intent. A roster entry supplies level and exact weight at the benchmark boundary.

## Source population audit

The catalog contains 330 unique canonical IDs and source identities, 1,980 independently validated ability cells, passive Perception for all 330 creatures, 429 source-explicit skill facts across 216 creatures, 45 static-Gear blocks, 36 multi-size blocks, seven swarms, 16 hover facts, 25 telepathy facts, and 27 alternate in-lair XP facts. The 47-target headline retains all 47 passive-Perception facts and 105 explicit skill facts across 40 targets; the 93-target census retains all 93 passive-Perception facts and 165 explicit skill facts across 71 targets. Special-sense occurrences are Darkvision 201, Blindsight 80, Tremorsense 6, and Truesight 16.

All 337 passive-trait heading occurrences are closed over 115 source headings: 329 top-level headings plus eight ordered Vampire Weakness child clauses. Every occurrence is modeled through a typed ID, retained with a closed non-consumption reason, or declared irrelevant to the maintained consumer boundary. Static Gear is transcribed only from the source Gear field; attack/action prose is not used to reconstruct equipment.

Two printed-source exceptions are retained, not silently repaired:

- Archmage prints CR 12 with XP 8,000 rather than the CR-table value 8,400.
- Young White Dragon prints Intelligence modifier −2 and final save +2; the unsigned positive save is preserved.

Gray Ooze and Invisible Stalker preserve source Initiative Advantage and the corresponding printed Initiative score. Structured sentinels also cover were-form movement/speech, Otyugh and Dretch telepathy restrictions, Archmage and Vampire Familiar qualified Charmed immunity, Rakshasa's qualified vulnerability, Half-Dragon's unresolved origin choice, and Swarm of Insects' movement choice.

## Approved eligibility and source-only selection

Eligibility policy `srd521_level_cr_closed_ranges_v1` uses closed exact-rational bands: level 7 CR 5–8, level 11 CR 10–13, level 15 CR 14–16, and level 20 CR 19–30. CR 9, 17, and 18 are intentionally outside this profile. These are approved continuity-oriented bands, not a recovered historical algorithm.

The eligible census is `srd521_eligible_census_v1`. Every projection-feasible eligible creature is included with weight `1/N` at its level. The bounded source-mechanical-diversity headline is `srd521_headline_source_diversity_v1`; it selects `min(12, N)` independently per level and gives every selected entry exact weight `1/k`. It is not a random sample, encounter-frequency population, campaign estimate, or comprehensive performance distribution.

Selection algorithm `srd521_source_diversity_greedy_v1` constructs source-only token universes after exclusions are frozen. Each dimension has total weight one and each token within a dimension has exact weight `1/|V|`. Numeric fields use the approved deterministic distinct-value rank buckets. Greedy picks maximize exact uncovered weight and break ties by source page, source order, then canonical ID. Final profiles serialize in source order. No KV, Battle Master, Eldritch Knight, Control Value, comparator, old-roster, classification, or other analytical result is an input.

## Accounting, exclusions, and membership

There are 101 band-eligible source blocks, 93 projection-feasible census entries, eight closed exclusions, and 47 headline entries.

| Level | Eligible | Feasible census | Excluded | Headline |
| ---: | ---: | ---: | ---: | ---: |
| 7 | 52 | 47 | 5 | 12 |
| 11 | 21 | 20 | 1 | 12 |
| 15 | 12 | 11 | 1 | 11 |
| 20 | 16 | 15 | 1 | 12 |

Closed exclusions are Assassin (`unsupported_evasion_result_conversion`); Flesh Golem, Iron Golem, and Shambling Mound (`unsupported_damage_absorption`); Half-Dragon (`unresolved_draconic_origin_choice`); Invisible Stalker (`unsupported_static_invisibility`); Rakshasa (`unsupported_greater_magic_resistance`); and Tarrasque (`unsupported_reflective_carapace`). Excluded rows remain in complete source accounting and cannot affect universes, buckets, scores, or tie-breaking.

Headline membership in stable source order:

- Level 7: Air Elemental, Barbed Devil, Young Brass Dragon, Earth Elemental, Gladiator, Young Green Dragon, Mage, Pirate Captain, Unicorn, Vampire Spawn, Werebear, Giant Ape.
- Level 11: Deva, Djinni, Erinyes, Young Gold Dragon, Guardian Naga, Archmage, Remorhaz, Sphinx of Lore, Stone Golem, Storm Giant, Vampire, Adult White Dragon.
- Level 15: Adult Black Dragon, Adult Blue Dragon, Adult Bronze Dragon, Adult Copper Dragon, Adult Green Dragon, Ice Devil, Marilith, Mummy Lord, Planetar, Purple Worm, Adult Silver Dragon.
- Level 20: Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Lich, Pit Fiend, Ancient Silver Dragon, Solar, Ancient White Dragon.

## Coverage audit

| Level | Dimensions | Covered / available weight | Coverage | Uncovered tokens |
| ---: | ---: | ---: | ---: | ---: |
| 7 | 53 | `64093/1386` / `53` | `64093/73458` (87.251218%) | 54 |
| 11 | 50 | `2879/60` / `50` | `2879/3000` (95.966667%) | 13 |
| 15 | 49 | `49` / `49` | 100% | 0 |
| 20 | 49 | `49` / `49` | 100% | 0 |

Every major family present in a feasible level pool is represented in that level's headline: Magic Resistance, Legendary Resistance, qualified damage defense, condition immunity, special movement, hover, each present special-sense kind, material typed passive traits, static Gear, and source-authored targeting restrictions. Distinct sense kind, range, and limitation facts are atomic tokens within each sense-kind dimension; this preserves Tremorsense representation at level 7 without hand-editing membership.

The complete per-dimension exact coverage, every uncovered token, every numeric value-to-bucket map, candidate-only token universe, greedy pick trace, and family member lists are the machine-auditable `selection_audit.levels` records in [`harness/data/srd_creature_rosters.json`](../harness/data/srd_creature_rosters.json). That maintained JSON is the publication of the exact maps; this document does not duplicate thousands of deterministic entries into a second authority.

## Migration and result boundary

A private machine comparison against the exact base commit joined all old 28 rows in order and reproduced all 812 required consumed-field comparisons plus 28 CR checks. Intentional representation changes are canonical ID plus display name, integer source pages, structured qualified atoms, separate final saves, richer Legendary Resistance policies, and retained Darkvision/Truesight facts. No old-28 golden, alias, fallback, or compatibility runtime is retained.

The maintained damage benchmark consumes the headline profile through `DamageTarget`. The headline profile remains a separate static roster input, while `ControlTarget` is retained as a static per-creature input for future control design that requires separate approval; no maintained evaluator consumes either to publish a current v14.2 control result. The catalog and profiles do not alter Kinetic Vanguard rules, comparator mechanics/packages, the Control Authority contract, primitive weights, or Control Value. The catalog and roster were frozen before the full expanded damage run; the then-current projection and report-input boundaries passed their complete non-analytical gate, but their later pre-merge provenance correction is why that run is now comparison-only.

## Invalidated pre-merge v14.2 comparison-run record

Issue #55 comment `5252064760` records the pre-run source-only freeze. An attempted `/usr/bin/time` wrapper failed before `npm` started, so it did not invoke the evaluator and is not counted as a run. The evaluator was then invoked exactly once with:

```text
npm run harness:damage -- --output-dir /tmp/kv-issue-55-final-damage.NU1wCZ/damage --workers 4
```

That run completed in about 255 seconds across all 47 source-ordered headline targets. Its evaluator implementation SHA-256 is `9838c390ef6c8a05ffcc9f6b67ca4e867da16277f8838a99015ae919e3a18c4d`. Its `run-manifest.json` has SHA-256 `a6ad2a6ca1b56c08ce95668f0825d2959d7b8f3ea8dd2f10b498d3536a25e1b8` and binds these preserved outputs:

| Output | Rows | SHA-256 |
| --- | ---: | --- |
| Detail CSV | 564 | `6147aca22e5881741628dcdc5527175facd1107b98e66eff4660db852103b1b9` |
| Matrix CSV | 96 | `aaa5883bf18ac1ccde6cbb1af21290e5add47c36ec3babba36d95e5101cd1263` |
| Matrix Markdown | 96 | `7d8cd1e4316ee28f589b2ad47a1de1418d0c9b80389f0fb2bac9a82467c3c87c` |
| Matrix HTML | 96 | `963cceba16ac9a1db894e02407d1fa22333215c279425083458af14a92e27639` |

The README writer and checker both consumed that exact manifest and its bound outputs; neither reran the evaluator. The later consumer-scoped requirements and sibling-projection implementation correction made that coarse provenance identity stale. The manifest is not rewritten or re-signed and cannot serve as corrected-contract evidence. Its bytes and numerical outputs remain permanent `comparison_evidence_only`; no numerical defect was demonstrated.

## Corrected-contract v14.2 replacement-run record

Issue #55 comment `5261639551` records the authorized replacement gate, the first attempt that failed before producing output, and the amended freeze used for the retry. The private retry scratch directory was created at `2026-08-12T03:57:30Z`; its manifest completed at `2026-08-12T04:02:32Z`, about five minutes end-to-end, after evaluating all 47 source-ordered headline targets. Its evaluator implementation SHA-256 is `7907904abe5cdcf0a46d8888101a8e8cd4888202a34ba3577870dcb1a11a1f7e`. Its `run-manifest.json` has SHA-256 `3986173ebb182c809e0d977ae4f24124b5fa9ffba37b2332492e496b54cf1b98` and binds these outputs:

| Output | Rows | SHA-256 |
| --- | ---: | --- |
| Detail CSV | 564 | `b8840c398dbb11e6225270cffb7312cb096a9711095d14208393107190652c0b` |
| Matrix CSV | 96 | `109f17a20c9a86b6e55a831ac7292eb4079dc0d5c2cd194d3a1bd5d8c09a6866` |
| Matrix Markdown | 96 | `6ba68dc1dae86d2f534caa5e17c6402c0064dfafd156f2e174c7743b65209340` |
| Matrix HTML | 96 | `2115627df7ec259e5fd5bb40e609d26627fd524f696e06d5abd2e937ce92c94d` |

The invalidated and replacement outputs join in the same order on all 564 detail and 96 matrix identities. All 16,920 comparisons across 30 non-provenance detail fields and all 1,632 comparisons across 17 non-provenance matrix fields are exact, and all notice fields are identical. Differences are confined to the generic-to-damage-scoped consumer-requirements field, DamageTarget projection digest, evaluator implementation digest, and resulting report and manifest digests. The replacement was required by a pre-merge provenance-contract correction, not changed damage mechanics. It is fresh full-roster evidence without fresh independent numerical or Monte Carlo certification.

## Mechanical v14.1 to v14.2 damage delta

The accepted v14.1 release matrix (`e0a9aec2d5c8da9409b8158163d44085001c26686385ddacb7108ff48d2326b4`) and the invalidated pre-merge v14.2 comparison matrix (`aaa5883bf18ac1ccde6cbb1af21290e5add47c36ec3babba36d95e5101cd1263`) join exactly on all 96 unique level, discipline, cluster-size, damage-scope, profile, and benchmark-type identities. No row is missing, new, duplicated, or newly unevaluable. The comparison used exact decimal arithmetic over the existing artifacts and did not invoke the evaluator. Because the corrected-contract replacement is numerically and classificationally identical to that invalidated comparison, the same v14.1-to-v14.2 findings apply without recomputation.

Headline target counts changed from 8, 6, 6, and 8 at levels 7, 11, 15, and 20 to 12, 12, 11, and 12 respectively: 28 to 47 overall. Aggregate-scope mean signed DPR changes (after minus before) by level are:

| Level | Kinetic Vanguard | Eldritch Knight | Battle Master |
| ---: | ---: | ---: | ---: |
| 7 | -0.429604 | +1.291667 | +1.636548 |
| 11 | -7.285145 | -0.252778 | -0.206008 |
| 15 | -9.016264 | -0.453115 | +0.070450 |
| 20 | +6.822441 | +5.945139 | +10.434650 |

The same aggregate-scope KV means by discipline are Cryokinesis -0.764780, Electrokinesis -7.127513, Psychokinesis +0.467239, and Pyrokinesis -2.483518; by cluster size they are -1.277160 at 1, -2.420260 at 3, and -3.734009 at 6. The comparator changes for those groupings are retained separately in the audit.

Comparator identities did not change: Eldritch Knight remains the lower boundary and Battle Master the upper boundary in all 96 rows, although both numeric boundaries changed in every row. Bands changed from 70 IDEAL, 19 COLD, and 7 HOT rows to 63 IDEAL, 28 COLD, and 5 HOT rows. Eleven rows changed classification: nine IDEAL to COLD and two HOT to IDEAL. Across all 288 displayed DPR cells, the mean absolute delta is 3.336333510417 and the maximum is 39.306652, the KV level-15 Electrokinesis cluster-6 aggregate row (170.851108 to 131.544456).

The complete deterministic record—including matrix-wide and aggregate-scope means by level, discipline, and cluster; primary-target means across cluster sizes by level and discipline; all 48 aggregate-scope row deltas; boundary and classification transitions; exact sums and denominators; both v14.2 manifest/report inventories; and the exact invalidated-to-replacement equality proof—is [`harness/provenance/damage-delta-v14.1-to-v14.2.json`](../harness/provenance/damage-delta-v14.1-to-v14.2.json). It preserves the invalidated comparison separately from the corrected-contract replacement and records that no numerical defect was demonstrated. Roster membership remained frozen after results were inspected.

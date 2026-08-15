# Kinetic Vanguard maintained computational harnesses

Status: current canonical rules **v14.2.0**. The accepted corrected-contract replacement exact analytical run remains the comparison baseline: its 564 detail rows and 96 matrix rows are numerically and classificationally identical to the permanently preserved `invalidated_premerge_provenance_boundary_correction` comparison run. Issue #65 Phase 2 PR1 introduces the separately specified nominal successor, but no complete successor matrix has been authorized or run and no successor output is promoted by this change. The durable numerical-review basis **v14.1.0** (`REVIEWED_WITH_DOCUMENTED_DIFFERENCES`) and accepted 47-target evidence remain intact.

The superseded current-development control execution runtime and the earlier Control Reliability report pipeline are retired from current `main`. No maintained v14.2 control evaluator or current v14.2 control result exists. Historical implementations remain available through Git history and frozen release evidence; no compatibility or fallback runtime is maintained.

`KineticVanguard.yaml` is the sole Kinetic Vanguard rules authority. Python does not parse feature prose or carry parallel Kinetic Vanguard progression, Psi, save, damage, tier, or targeting tables. The TypeScript loader validates the canonical YAML and emits `DamageHarnessProjection`; Python's `DamageAuthorityModel` loads that projection by stable entity ID and fails closed on missing, duplicate, unavailable, or inconsistent mechanics.

## Authority and input boundaries

The damage benchmark keeps four distinct input layers:

1. **Kinetic Vanguard authority:** root `KineticVanguard.yaml`, projected only after canonical schema and semantic validation.
2. **Damage methodology:** profiles, aggregation, target clustering, the explicit `damage_matrix.non_damage_effect_boundary`, historical seed/trial metadata, and SRD-derived Fighter progression/mechanics in `config/benchmark.json`, plus project-authored Python evaluation and reporting code.
3. **SRD creature inputs:** the authoritative 330-record source catalog in `data/srd_creatures.json`, separate source-only headline/census profiles and complete accounting in `data/srd_creature_rosters.json`, consumer requirements in `config/creature-consumers.json`, and extraction provenance in `provenance/srd-creatures.json`.
4. **Third-party damage comparator assumptions:** minimal independently expressed Battle Master and Eldritch Knight numerical packages in `comparators/fighter-subclasses.json`.

The damage evaluator hashes canonical authority bytes, the path-independent damage-authority projection, the Python authority adapter plus nominal semantic kernel, methodology, comparator assumptions, the whole catalog and roster contract, the active profile, the precise consumer-scoped requirements, and the active thin target projection separately. The whole requirements-registry digest is repository-integrity metadata only; damage evidence binds `damage_consumer_requirements_sha256`, so control-only requirement changes cannot invalidate damage evidence. Neither configuration file is Kinetic Vanguard rules authority. Catalog facts, roster level/weight, and live scenario state remain distinct.

### Issue #65 nominal successor boundary

Phase 2 PR1 implements only `nominal_sustained_dpr_v1`: one immutable exact transition/value kernel with closed Kinetic Vanguard, Battle Master, and Eldritch Knight providers. Semantic probabilities, rewards, resource costs, and comparisons use exact fractions. All three providers receive the same `declared_static_target_knowledge_v1` snapshot, while unresolved attack, save, and damage outcomes remain hidden until their resolution stages. The nominal objective maximizes exact aggregate damage, then fixed-primary damage, then minimizes the shared self-damage, horizon-limited, persistent-pool, and refreshable cost classes before the stable canonical action ID.

The independently derived 50-case contract corpus is `data/damage-sentinels-v1.json`; its standard-library-only oracles and integrity checks are in `tests/damage_sentinel_oracles.py` and `tests/test_damage_sentinels.py`, while `tests/test_damage_contract_integration.py` binds applicable nominal facets to the production contract API. Finite cases remain frozen contract records only in PR1 and cannot activate a finite solver.

Finite HP, target death, retargeting, kill-trigger Hew, and the `finite_hp_removed_v1` and `finite_hp_kill_cleave_v1` policies remain unimplemented and fail closed pending separately authorized PR2. The maintainer has approved independent Ball Lightning damage rolls per creature trigger for that future finite model; the ruling does not alter nominal PR1 results. `provenance/damage-model-contract.json` records the frozen contract, exact base commit, implementation boundary, accepted delta classes, and unconsumed evidence gates.

### Control Authority v2 is separate

Control Authority v2.1 is the complete 35-modeled/14-excluded structured static authority retained for future control design that requires separate approval. Its `benchmark_ready` flag is scoped to authority completeness and does not imply evaluator or result readiness. The retained static input set also includes the shared creature catalog, the active source-only profile, consumer requirements, and a `ControlTarget` 1.0.0 projection. `ControlTarget` preserves raw ability modifiers and final saves separately; passive Perception; canonically sorted, source-explicit skill facts with canonical skill and associated-ability IDs plus the final printed bonus; condition facts; movement and hover; Darkvision, Blindsight, Tremorsense, and Truesight; Initiative; communication and telepathy; static Gear; and typed passive facts. An unlisted skill remains absent from the explicit facts; any future check resolution must fall back to its associated raw ability modifier rather than treat absence as an explicit +0. Live Advantage, Disadvantage, roll mode, equipment or condition effects, and other check circumstances remain scenario/event state. `ControlTarget` nonvisual-query adaptation covers only Blindsight and Tremorsense and never reclassifies Truesight. These contracts are static inputs only: they do not constitute a benchmark methodology or evaluator and do not classify or publish a v14.2 control result.

Coverage is source-mechanical rather than fabricated completion: all 330 catalog creatures retain passive Perception and 429 explicit skill facts across 216 creatures; the 47-target headline retains 47 passive-Perception facts and 105 explicit skill facts across 40 targets; the 93-target census retains 93 passive-Perception facts and 165 explicit skill facts across 71 targets.

### Current control capability boundary

The retired runtime is not replaced by another evaluator, compatibility layer, fallback, or dormant command. Control Authority v2 and `ControlTarget` remain static inputs only; neither is a benchmark methodology nor an execution runtime. A minimum execution contract and a simpler named-condition runner are separate future work and remain unimplemented.

## Commands

Install the checked-in Node dependencies before running Python because the authority adapter invokes the TypeScript projection:

```text
npm ci
npm run harness:validate
npm run test:harness
```

`harness:validate` checks the creature catalog, maintained damage inputs, and static Control Authority v2. `test:harness` runs the maintained damage, catalog, projection, and authority contracts. Neither command evaluates control or publishes a control result.

Separately authorized full configured roster run:

```text
npm run harness:damage -- --output-dir harness/results/damage
```

Do not run this complete 47-target command during ordinary PR1 development. It is a separate consumable final gate after the nominal implementation, comparator behavior, target semantics, and sentinels are frozen; there is no automatic retry authorization.

Use `--matrix-only` to omit the detailed CSV or `--no-matrix` to omit the compact damage matrix. The CLI defaults to the repository-root authority, accepts `--authority` for mutation tests, writes only below the explicit `--output-dir`, and performs no network access.

A full run writes a format-2 `run-manifest.json` beside its detail and matrix outputs. That manifest binds the result contract, mode, target-knowledge, numeric-representation, and provider IDs; rules, authority, catalog, whole roster contract, active profile, DamageTarget projection, damage-consumer requirements, benchmark and comparator configuration; the damage-model contract; canonical and byte-level sentinel identities; observation, resource, and optimization policies; semantic, orchestration, evaluator, and reporter implementations; and every output digest. Headline output has no file-order `--target-limit` mode.

Synchronize the generated damage snapshot near the top of the repository README:

```text
npm run readme:damage -- --report-input /path/to/corrected-contract-run/run-manifest.json
npm run readme:damage:check -- --report-input /path/to/corrected-contract-run/run-manifest.json
```

Both commands only validate and read the exact candidate replacement run; neither invokes the evaluator. A stale, foreign, incomplete, rewritten, or digest-mismatched report fails closed. In particular, the invalidated pre-correction manifest is not accepted. The writer atomically replaces only the `BEGIN/END GENERATED DAMAGE MATRIX` region and refuses to overwrite a concurrent README edit. Both modes fingerprint all maintained build inputs before reading and abort if any input changes. The check derives the same region from the same manifest and fails if the committed README differs.

Run the evaluator only when a specific gate explicitly authorizes the exact analytical scope. Reuse that one manifest for the writer, numerical review, and check. A release metadata/status edit or ordinary PR1 development does not authorize an analytical run.

### Invalidated pre-merge v14.2 comparison run

The catalog and roster were frozen before execution in issue #55 comment `5252064760`. An attempted `/usr/bin/time` wrapper failed before `npm` started and therefore did not invoke the evaluator or count as a run. The one evaluator invocation was:

```text
npm run harness:damage -- --output-dir /tmp/kv-issue-55-final-damage.NU1wCZ/damage --workers 4
```

It completed in about 255 seconds over all 47 source-ordered headline targets with evaluator implementation SHA-256 `9838c390ef6c8a05ffcc9f6b67ca4e867da16277f8838a99015ae919e3a18c4d`. Its manifest SHA-256 is `a6ad2a6ca1b56c08ce95668f0825d2959d7b8f3ea8dd2f10b498d3536a25e1b8`; it binds 564 detail rows at `6147aca22e5881741628dcdc5527175facd1107b98e66eff4660db852103b1b9` and 96 matrix rows emitted as CSV `aaa5883bf18ac1ccde6cbb1af21290e5add47c36ec3babba36d95e5101cd1263`, Markdown `7d8cd1e4316ee28f589b2ad47a1de1418d0c9b80389f0fb2bac9a82467c3c87c`, and HTML `963cceba16ac9a1db894e02407d1fa22333215c279425083458af14a92e27639`. The run is permanently marked `invalidated_premerge_provenance_boundary_correction`: its manifest predates the corrected consumer-scoped requirements and sibling-projection implementation identities. Those bytes and numerical outputs remain preserved only as comparison evidence, and no numerical defect was demonstrated. The README writer and checker had reused this same manifest without rerunning the evaluator; the corrected contract rejects it as stale.

### Corrected-contract v14.2 replacement run

Issue #55 comment `5261639551` records the authorized replacement gate, the first attempt that failed before producing output, and the amended freeze used for the retry. The private retry scratch directory was created at `2026-08-12T03:57:30Z`; its manifest completed at `2026-08-12T04:02:32Z`, about five minutes end-to-end, after evaluating all 47 source-ordered headline targets. Its evaluator implementation SHA-256 is `7907904abe5cdcf0a46d8888101a8e8cd4888202a34ba3577870dcb1a11a1f7e`. Its manifest SHA-256 is `3986173ebb182c809e0d977ae4f24124b5fa9ffba37b2332492e496b54cf1b98`; it binds 564 detail rows at `b8840c398dbb11e6225270cffb7312cb096a9711095d14208393107190652c0b` and 96 matrix rows emitted as CSV `109f17a20c9a86b6e55a831ac7292eb4079dc0d5c2cd194d3a1bd5d8c09a6866`, Markdown `6ba68dc1dae86d2f534caa5e17c6402c0064dfafd156f2e174c7743b65209340`, and HTML `2115627df7ec259e5fd5bb40e609d26627fd524f696e06d5abd2e937ce92c94d`.

The invalidated and replacement outputs join in the same order on every row identity. All 16,920 comparisons across 30 non-provenance fields in the 564 detail rows and all 1,632 comparisons across 17 non-provenance fields in the 96 matrix rows are exact; all notice fields are also identical. Differences are confined to the generic-to-damage-scoped consumer-requirements field, DamageTarget projection digest, evaluator implementation digest, and the resulting report and manifest digests. The replacement was required by a pre-merge provenance-contract correction, not changed damage mechanics. It is fresh full-roster evidence without fresh independent numerical or Monte Carlo certification.

The read-only v14.1-to-v14.2 comparison joins all 96 matrix identities exactly, finds no newly unevaluable row, and records all target counts, grouped and row-level signed DPR changes, boundary changes, 11 classification transitions, absolute-delta statistics, and both v14.2 manifest identities in [`provenance/damage-delta-v14.1-to-v14.2.json`](provenance/damage-delta-v14.1-to-v14.2.json). Because the replacement numerical and classification fields exactly equal the invalidated comparison, the compact v14.1 delta remains unchanged. The 288 displayed DPR cells have mean absolute change 3.336333510417 and maximum absolute change 39.306652. The comparison stage did not invoke the evaluator or alter the frozen roster.

The generated damage evidence line is status-neutral and identifies the canonical rules version without duplicating publication state. Its adjacent provenance text distinguishes that current authority from the durable numerical-review basis and records whether fresh current-version evidence exists. Maintain the current published release and development line in the README's separate **Release status** section.

## Damage method

The Kinetic Vanguard profile is `official_default_25_percent_hp`: 25% of fixed-HP budget for voluntary Blood Tax, Advanced Training disabled, and every configured attack replaced by Manifested Strike. Because the profile supplies no Kinetic Vanguard weapon packet, this is not a global optimization of every legal Fighter weapon/Manifested Strike mix. The target profile is `srd521_headline_source_diversity_v1`. It covers levels 7, 11, 15, and 20; three rounds; explicit exact rational weights that sum to one within each level; cluster sizes 1, 3, and 6; no target death; legal configured positioning; and SRD defense handling.

Every comparator action slot is an Attack action. Kinetic Vanguard may instead spend one slot on its canonically capped standalone psionic Action. The successor optimizes each target, discipline, and cluster independently from the shared declared static target snapshot and currently observed state, then aggregates targets with exact rational profile weights. It cannot look ahead into unresolved outcomes. Thermal Fracture's Armor Class reduction is the one explicit non-damage effect allowed to feed back into self-attack damage; the configured boundary rejects other condition, control, outcome, and ally-turn feedback.

The successor analytically enumerates d20, saving-throw, and damage-die outcomes with exact fractions; seeds and trial counts remain historical compatibility metadata. The accepted predecessor bundle is the comparison baseline, not an unquestionable golden: every future joined difference must be classified as `current_evaluator_defect`, `successor_defect`, `approved_methodology_correction`, `representation_or_rounding_only`, or `unresolved_blocker`. That complete joined comparison has not run in PR1 development.

Damage produces separate primary-target and aggregate-cluster DPR rows. Headline percentages use the displayed exact-profile-weight aggregates:

```text
KV as % of comparator = 100 × KV aggregate / comparator aggregate
```

For each row, the lower boundary is the smaller Battle Master/Eldritch Knight result and the upper boundary is the larger. COLD is below the lower boundary, IDEAL includes both boundaries, and HOT is above the upper boundary. `Boundary Delta %` is signed against the nearest crossed boundary; `N/A` is reserved for an unavailable comparison, including a required zero denominator. Comparator crossover is ordinary evidence, not a separate state.

### Durable v14.1 numerical-review basis

The following numerical findings belong to the retained v14.1 review basis. PR #46 carried that basis forward because it intentionally changed neither damage-relevant mechanics nor numerical evaluator semantics. Those findings remain historical review evidence and do not independently certify either the invalidated v14.2 comparison outputs or the corrected-contract replacement run.

- Exact reevaluation of all 336 preserved historical damage policies agrees with the 25,000-trial rows at sampling scale: primary DPR mean absolute delta `0.0323169` and maximum `0.176034`; aggregate DPR mean absolute delta `0.0374951` and maximum `0.340120`.
- The observed-state policy improves aggregate damage in 123 rows, ties 213, and regresses in none. Nine rows trade lower primary-target damage for higher aggregate damage under the declared aggregate-first objective.
- Reviewed differences come from corrected struck-target parity for Branching Bolt and Electron Burst, state-aware Thermal Fracture decisions, and optimal observed-state Studied Attacks, Combat Prowess, and Overload Mastery timing. Historical outputs were not normalized into the maintained implementation.

## Damage comparators

- Battle Master consumes only the declared damage parameters and `generic_on_hit_superiority_damage_v1` package. Nominal Hew is an optional once-per-Fighter-turn reserved-Bonus-Action same-weapon follow-up after a critical; target death is absent.
- Eldritch Knight consumes only the declared damage parameters and tactical policy. True Strike is an optional zero-or-one pre-roll replacement per Attack action, with explicit `radiant_base` and `weapon_normal_base` choices made from declared static target facts and observed state.

The comparator model identifies the 2024 fifth-edition ruleset. It is not a comprehensive maneuver, spell, or subclass inventory. No subclass descriptions, feature prose, spell descriptions, sourcebook tables, flavor, or copied character-building instructions are retained.

> Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document.

## Output and provenance

Filenames derive from YAML `rules_version`, for example `kv-14-2-0-damage-comparison-matrix.csv`. The damage matrix is emitted as CSV, Markdown, and self-contained HTML from one numerical row model. Every format retains raw Kinetic Vanguard, Battle Master, and Eldritch Knight aggregates; ordinary ratios; lower and upper comparator identities and values; classification; signed boundary delta; and provenance.

Generated-run provenance includes the damage result contract; mode and policy identities; rules version; authority digest; catalog and roster contract versions and digests; active target-profile ID, version, and digest; DamageTarget projection ID, version, and digest; consumer-requirement version and precise damage-consumer digest; methodology, comparator, semantic implementation, sentinel, and reporter identities; compatibility-only seed/trial settings; aggregation; and review-basis status. The maintained `provenance/damage-model-contract.json` records the Issue #65 PR1 freeze and pending gates; `provenance/damage-review.json` separately preserves the durable accepted run history. CSV rows carry structured component, SRD, and comparator notices; Markdown and HTML display the same notices in a visible licensing section.

The README generator validates the run manifest, every bound input/output digest, the complete authoritative damage matrix, all raw and derived result fields, all provenance and notice fields, comparator scope, and canonical rules evidence identity before selecting primary-target cluster-size-1 rows for its single public heat table. Generated outputs, caches, virtual environments, and `.codex-import/` are ignored and are not official source.

The v14.1 restoration and numerical-review record remains the durable independent review basis. The pre-correction v14.2 run remains invalidated comparison evidence; the exact-equal corrected-contract replacement now supplies current full-roster evidence without claiming independent numerical or Monte Carlo certification. See `MIGRATION.md` and `provenance/damage-review.json` for both typed run records; use the current commands and files above for maintained work.

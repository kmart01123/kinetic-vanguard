# Kinetic Vanguard maintained computational harnesses

Status: current canonical rules **v14.2.0**; durable numerical-review basis **v14.1.0** (`REVIEWED_WITH_DOCUMENTED_DIFFERENCES`), carried forward because PR #46 intentionally changed neither damage-relevant mechanics nor numerical evaluator semantics. No fresh v14.2 full-roster run, numerical certification, or Monte Carlo certification was performed. The maintained damage evaluator remains damage-only. The shared control engine is comparator-neutral mechanical infrastructure and publishes no v14.2 Control Value result. The Control Reliability implementation and its report pipeline were retired from current `main`; the frozen v14.1 release remains the historical source for those results.

`KineticVanguard.yaml` is the sole Kinetic Vanguard rules authority. Python does not parse feature prose or carry parallel Kinetic Vanguard progression, Psi, save, damage, tier, or targeting tables. The TypeScript loader validates the canonical YAML and emits `DamageHarnessProjection`; Python's `DamageAuthorityModel` loads that projection by stable entity ID and fails closed on missing, duplicate, unavailable, or inconsistent mechanics.

## Authority and input boundaries

The damage benchmark keeps four distinct input layers:

1. **Kinetic Vanguard authority:** root `KineticVanguard.yaml`, projected only after canonical schema and semantic validation.
2. **Damage methodology:** profiles, aggregation, target clustering, the explicit `damage_matrix.non_damage_effect_boundary`, historical seed/trial metadata, and SRD-derived Fighter progression/mechanics in `config/benchmark.json`, plus project-authored Python evaluation and reporting code.
3. **SRD target data:** the pinned 28-row SRD 5.2.1 roster and provenance in `data/srd_targets.csv`.
4. **Third-party damage comparator assumptions:** minimal independently expressed Battle Master and Eldritch Knight numerical packages in `comparators/fighter-subclasses.json`.

The runtime hashes canonical authority, methodology, comparator assumptions, and roster separately. Neither configuration file is Kinetic Vanguard rules authority.

### Control Authority v2 is separate

Control Authority v2.1 is the complete 35-modeled/14-excluded structured authority for the control-methodology redesign. Its `benchmark_ready` flag is scoped to authority completeness. Combined control-input readiness additionally requires the exact 28-row `data/srd_control_targets.json` supplement and `provenance/srd-control-targets.json` to validate against the unchanged `data/srd_targets.csv` roster; `npm run harness:validate` enforces both boundaries. The supplement records only official movement modes, hover, and relevant nonvisual senses and is loaded through `harness.control_targets`; it is not consumed by `DamageHarnessProjection` or the damage benchmark. This contract does not evaluate, classify, or publish a v14.2 control result.

### Shared control mechanics engine

`harness.control_engine` is the narrow public facade over the one maintained computational runtime for control consequences, gates, overlap, state, and timing. That runtime is Python only: `control_catalog.py`, `control_graph.py`, `control_state.py`, `control_timeline.py`, and `control_engine.py`. TypeScript retains cheap architecture, manifest, and input-presence checks, but has no twin semantic evaluator or engine-parity corpus. The facade consumes the validated Control Authority v2.1 projection, the exact control-target supplement, the pinned seven-condition SRD consequence catalog (Blinded, Charmed, Frightened, Incapacitated, Prone, Restrained, and Stunned), and the separate `config/control-engine.json` methodology configuration.

The consequence catalog, primitive contract, normalization rules, timeline engine, and engine configuration are each version `1.0.0`. Engine results retain the authority projection version and digest, target-supplement digest, consequence-catalog version and digest, primitive-contract version, normalization-rules version, timeline-engine version, `engine_config_version` and `engine_config_digest`, selected initiative and area-response convention IDs and versions, and displacement-function ID and version. The catalog and provenance contain compact SRD-derived mechanics under the repository's existing SRD attribution and license boundary; the configuration and runtime are project-authored methodology and software.

The supported mutable boundary is `ControlEngine.execution_session(...)`, and the supported final assembly boundary is `session.result()`. A session binds the compiled effect and authority digest; engine, catalog, primitive, normalization, timeline, configuration, initiative, area, and displacement identities; exact target identities and relevant mechanics; selector membership and context; choices; probability context and kernel provenance; candidate components; the ordered reliability script; the exact timeline schedule; and the `include_initial` policy into a deterministic canonical scenario record and SHA-256 integrity digest. Independent mutable state, chronological helpers, and collection-based result assembly are not public facade operations.

The maintained d20 kernel has a stable ID, version, and deterministic algorithm/parameter record. Accepted custom kernels must likewise provide a stable ID, version, and JSON-safe reproducibility provenance; fixture kernels are explicitly marked test-only. Reliability results retain the complete immutable reliability scenario and receive a unique evaluator-issued attestation, so a hand-built dataclass or a result from another execution cannot serve as final-result provenance.

The two initiative schedules are `fighter_first_v1` and `target_before_fighter_v1`. The two area-response conventions are `shortest_route_v1`, which follows the shortest supplied legal exit route and fails closed when required route context is missing, and `fixed_occupancy_v1`, which preserves membership until the effect ends. A program with no compiled area accepts either convention as mechanically inert and creates no route ledger or geometry-update surface. A program with one compiled area uses the selected convention normally; programs with multiple compiled areas fail closed rather than selecting one implicitly. Every schedule and area convention is version `1.0.0`.

For `shortest_route_v1`, a session validates the initial route alternatives once, includes them in its canonical scenario identity, and owns the route ledger thereafter. Live membership in that ledger—not the presence of an active area-bound component—requires the legal movement response and controls compiled entry and recurring area-gate eligibility. Ordinary and forced false-to-true entries use a typed `AreaEntryTransition` pre-bound to the exact effect, compiled area, target, event and sequence, triggering turn, entry cause, compiled moved-area policy, and complete route geometry. The transition reads membership from engine-owned state, installs the carried exit route, records a continuous pre/post route-state chain, and then makes any same-event entry gate executable; callers cannot author membership or prior-trigger history. Once-per-turn entry frequency is engine-owned by effect, area, target, and turn, so same-turn exit and re-entry cannot farm a second gate while a later-turn entry can trigger normally. Activation-cadence area effects remain dormant for a pre-entry nonmember, and a qualifying false-to-true transition restores any missing canonical ambient component before later movement consumes its authority. The first legal response selects a route and stores its exact remainder, movement mode, environment, movement-cost basis, membership, and update event; later responses consume that remainder without caller restatement. Exit prunes later area-owned gates, while a canonical re-entry restores only later eligible gates and applies the compiled moved-area entry policy without retroactive execution. Speed 0 or mode denial preserves membership and the route, difficult terrain changes movement cost rather than Speed, and standing consumes the same movement budget before route progress. Per-event raw route replacement is rejected. `fixed_occupancy_v1` uses the same authoritative membership ledger and typed transition with empty routes, but creates no selected route, remaining distance, or nominal exit progress. Programs with one compiled area therefore have one membership source under either convention; zero-area programs still create no area state.

Persistent moving-area geometry can change only through a typed `AreaGeometryUpdate` pre-bound to the session, exact schedule event, compiled effect and area, and target. The session accepts it only at a compatible typed event authorized by the compiled area-movement contract, and issues the canonical old/new membership and route transition with entry or exit opportunities, component endings, and pre/post route-state hashes. A false-to-true move whose compiled policy does not count area movement creates no entry gate and consumes no ordinary-entry allowance; a policy that does count it requires the matching bound `AreaEntryTransition` and the same-event entry gate after the geometry update. A true-to-false move continues to end only while-in-area components. This is not a general battlefield-edit or action-planning interface.

For each target turn, both initiative schedules use this chronology: target-turn start and reaction-interval opening; target-start scripts; start-turn area gates and repeat saves; the first and only legal movement/standing/area response; active-turn opportunity; caller-supplied attack opportunities in order; remaining caller-scripted events at their legal timing hooks; target-turn end. Immediate after-movement state changes therefore precede the active and attack windows. Standing spends half current Speed rounded down before route progress, the remainder is the only movement budget available to that response, and the same opportunity owns any displacement-epoch boundary; no post-attack full movement budget is created.

Each session owns a monotonic event cursor. It explicitly advances to known schedule events, preserves caller order for multiple operations at one event, captures pre-event plus per-operation pre/post component and route state, and closes the event before further advancement. Expiry, branches, replacement/refresh, normalization, Prone and area responses, geometry updates, concentration, displacement, and epoch changes issue typed records carrying the session digest and schedule identity. Route transitions form an issuance-ordered continuous hash chain; final results expose those transitions and final membership and route state. Earlier, unknown, future-without-advance, foreign-session, stale, fabricated, rewritten, discontinuous, or inactive-source records are rejected rather than repaired by final sorting.

Each target has an explicit horizon-entry partial reaction interval from round-one start until its first turn start. Its initial availability remains unresolved unless supplied by the caller, and a scripted reaction window inside that partial interval fails closed without that fact. Every target-turn start then creates a known-available interval ending immediately before that target's next turn start (or at the round-three horizon end); targeted scripted reaction windows bind to the interval containing their event. Each round ends before the next round starts, with no implicit event window between those boundaries.

The three version `1.0.0` displacement functions operate on `u = net displacement feet / 5`: `sqrt_5ft_v1` uses `sqrt(u)`, `log2_5ft_v1` uses `log2(1 + u)`, and `banded_10ft_v1` uses `0` at zero feet and otherwise `ceil(distance feet / 10)`. Contributions use only increases in the maximum net displacement within a movement epoch, so reversals and circles cannot farm path length. No function is selected as a permanent headline default.

Outputs remain sparse denial, enablement, and retained/unpriced primitive vectors with deterministic transition and suppression ledgers. The engine assigns no final primitive weights, produces no combined Control Value scalar, applies no HOT/IDEAL/COLD/SENSITIVE classification, and performs no action, tier, target, resource, comparator, ranking, or optimization decision. It neither imports nor participates in the damage planner, evaluator, configuration, comparator packages, reports, or README evidence generation.

## Commands

Install the checked-in Node dependencies before running Python because the authority adapter invokes the TypeScript projection:

```text
npm ci
npm run control:engine:validate
npm run control:engine:fixtures
npm run harness:validate
npm run test:harness
```

`control:engine:validate` validates the catalog, provenance, configuration, authority compilation, and public facade while emitting only a compact summary. `control:engine:fixtures` runs the 72-case reviewed hand-calculated corpus across both initiative schedules, both area conventions, and all three displacement functions without evaluating the complete target roster. `harness:validate` includes the same cheap engine validation alongside the maintained damage, authority, and control-target checks.

Tiny fixed-input damage smoke run:

```text
python3 -m harness.damage_harness --output-dir /tmp/kv-damage-smoke --levels 7 --target-limit 1 --trials 32 --seed 1151001
```

Full configured roster run:

```text
npm run harness:damage -- --output-dir harness/results/damage
```

Use `--matrix-only` to omit the detailed CSV or `--no-matrix` to omit the compact damage matrix. The CLI defaults to the repository-root authority, accepts `--authority` for mutation tests, writes only below the explicit `--output-dir`, and performs no network access.

Synchronize the generated damage snapshot near the top of the repository README:

```text
npm run readme:damage
npm run readme:damage:check
```

Both commands run a fresh full-roster damage evaluation from canonical authority and maintained damage inputs. The writer atomically replaces only the `BEGIN/END GENERATED DAMAGE MATRIX` region and refuses to overwrite a concurrent README edit. Both modes fingerprint all maintained build inputs before evaluation and abort if any input changes. The check recomputes the region and fails if the committed README differs. This path uses exact analytical enumeration and does not compare against or update a tracked golden output.

Run the writer only when fresh full-roster evidence is required because benchmark inputs, evaluator or planner logic, methodology, comparator or roster data changed, or a specific release gate explicitly requires fresh evidence. Review the numerical diff before running the check. A release metadata or status edit alone does not trigger either command.

The generated damage evidence line is status-neutral and identifies the canonical rules version without duplicating publication state. Its adjacent provenance text distinguishes that current authority from the durable numerical-review basis and records whether fresh current-version evidence exists. Maintain the current published release and development line in the README's separate **Release status** section.

## Damage method

The headline profile is `official_default_25_percent_hp`: 25% of fixed-HP budget for voluntary Blood Tax, Advanced Training disabled, and every configured attack replaced by Manifested Strike. Because the profile supplies no Kinetic Vanguard weapon packet, this is not a global optimization of every legal Fighter weapon/Manifested Strike mix. The benchmark covers levels 7, 11, 15, and 20; three rounds; equal target weighting; cluster sizes 1, 3, and 6; no target death; legal configured positioning; and SRD defense handling.

Every comparator action slot is an Attack action. Kinetic Vanguard may instead spend one slot on its canonically capped standalone psionic Action. The planner optimizes each target, discipline, and cluster independently from legally observable state, then averages target results across the roster. Its lexicographic objective is aggregate damage followed by primary-target damage. It cannot look ahead into unresolved outcomes. Thermal Fracture's Armor Class reduction is the one explicit non-damage effect allowed to feed back into self-attack damage; the configured boundary rejects other condition, control, outcome, and ally-turn feedback.

The evaluator analytically enumerates d20, saving-throw, and damage-die outcomes. Seeds and trial counts remain historical compatibility metadata; generated provenance identifies `exact_analytical_enumeration` as the evaluator. The durable v14.1 review-basis status is `REVIEWED_WITH_DOCUMENTED_DIFFERENCES`; it is not a claim of fresh v14.2 numerical or Monte Carlo certification.

Damage produces separate primary-target and aggregate-cluster DPR rows. Headline percentages use displayed equal-weight roster aggregates:

```text
KV as % of comparator = 100 × KV aggregate / comparator aggregate
```

For each row, the lower boundary is the smaller Battle Master/Eldritch Knight result and the upper boundary is the larger. COLD is below the lower boundary, IDEAL includes both boundaries, and HOT is above the upper boundary. `Boundary Delta %` is signed against the nearest crossed boundary; `N/A` is reserved for an unavailable comparison, including a required zero denominator. Comparator crossover is ordinary evidence, not a separate state.

### Durable v14.1 numerical-review basis

The following numerical findings belong to the retained v14.1 review basis. PR #46 carries that basis forward because it intentionally changes neither damage-relevant mechanics nor numerical evaluator semantics; it does not relabel the findings as a fresh v14.2 review.

- Exact reevaluation of all 336 preserved historical damage policies agrees with the 25,000-trial rows at sampling scale: primary DPR mean absolute delta `0.0323169` and maximum `0.176034`; aggregate DPR mean absolute delta `0.0374951` and maximum `0.340120`.
- The observed-state policy improves aggregate damage in 123 rows, ties 213, and regresses in none. Nine rows trade lower primary-target damage for higher aggregate damage under the declared aggregate-first objective.
- Reviewed differences come from corrected struck-target parity for Branching Bolt and Electron Burst, state-aware Thermal Fracture decisions, and optimal observed-state Studied Attacks, Combat Prowess, and Overload Mastery timing. Historical outputs were not normalized into the maintained implementation.

## Damage comparators

- Battle Master consumes only the declared damage parameters and tactical-policy inputs. Within the frozen three-round horizon it maximizes expected damage from legally observed state.
- Eldritch Knight consumes only the declared damage parameters and tactical policy, including the configured True Strike positions and observed-state follow-up choices.

The comparator model identifies the 2024 fifth-edition ruleset. It is not a comprehensive maneuver, spell, or subclass inventory. No subclass descriptions, feature prose, spell descriptions, sourcebook tables, flavor, or copied character-building instructions are retained.

> Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document.

## Output and provenance

Filenames derive from YAML `rules_version`, for example `kv-14-2-0-damage-comparison-matrix.csv`. The damage matrix is emitted as CSV, Markdown, and self-contained HTML from one numerical row model. Every format retains raw Kinetic Vanguard, Battle Master, and Eldritch Knight aggregates; ordinary ratios; lower and upper comparator identities and values; classification; signed boundary delta; and provenance.

Generated-run provenance includes rules version, authority digest, roster digest, methodology-config digest, comparator-config digest, evaluator, compatibility-only seed/trial settings, aggregation, and the review-basis status. The maintained `provenance/damage-review.json` separately records the current authority version, durable review-basis version, and whether fresh full-roster or numerical certification was performed. CSV rows carry structured component, SRD, and comparator notices; Markdown and HTML display the same notices in a visible licensing section.

The README generator validates the complete authoritative damage matrix, all raw and derived result fields, all provenance and notice fields, comparator scope, and canonical rules evidence identity before selecting primary-target cluster-size-1 rows for its single public heat table. Generated outputs, caches, virtual environments, and `.codex-import/` are ignored and are not official source.

The v14.1 restoration and numerical-review record remains the durable basis for the current damage snapshot. See `MIGRATION.md` and `provenance/damage-review.json` for that retained record and PR #46's explicit current-development disposition; use the current commands and files above for maintained work.

# Control Authority v2 population audit

Status: implementation and local validation complete. The final independent 35-row canonical re-audit and test-coverage audit are approved. Exact-head CI evidence is recorded externally in the draft PR and governing issue after push, because embedding a head SHA or run ID in this tracked file would create a new head.

Canonical basis: KineticVanguard.yaml is the sole mechanics authority. The table below records the complete resolved control semantics for the exact 26 rows that replace the pending authority ledger. Damage values are mentioned only when their ordering gates a control effect; they are not Control Value components.

## Version decision

The projection shape changed. The existing 2.0.0 contract cannot faithfully express event ownership, save role and roll mode, declaration-coupled choices, area-wide terrain, persistent elevation and fall transitions, or the required forced-movement distinctions. The coordinated version decision is therefore:

- control contract: 2.1.0
- control projection wrapper: 2.1.0
- canonical schema: 3.1.0

The YAML, JSON Schema, TypeScript types and validator, TypeScript projection wrapper and CLI, Python constants and validator, shared parity corpus, focused tests, and documentation moved together.

## Required semantic extensions

| Extension | Required fail-closed meaning |
| --- | --- |
| event_context | Replace ownerless cadence strings with typed events. Turn-relative events identify controller, affected target, or any creature as owner; start or end as anchor; current or next turn as relation; and declaration, hit, save, entry, exit, and instantaneous resolution as non-turn events. |
| save_semantics | Every saving throw states initial, repeat, or recurring role; normal, Advantage, or Disadvantage roll mode; affected-target ownership; exact timing; and independent-per-target or shared resolution. |
| choice_binding | A choice has an ID, timing, options, and scope. Explosion versus Implosion is chosen once at rider declaration and shared by all affected targets. Phase Step chooses one endpoint, departure or arrival, for the whole burst. |
| target_choice_and_placement | Distinguish creatures chosen by the controller from every creature in an area. Keep primary and secondary roles, uniqueness, weighted slots, size immunity, and area or endpoint placement separate from target range. |
| area_property | Represent persistent difficult terrain as an area-wide movement-cost property, not a target Speed reduction. Exit semantics are per property or component so leaving an area does not erase an independently timed failed-save condition. |
| movement_path | Forced movement states reference point, axis, direction, exact or up-to distance, straight-line status, visibility and occupancy requirements, obstruction rule, blocked-path fallback, and resolution order. A generic legal_destination or controller_choice token is insufficient. |
| persistent_state_transition | Represent elevated and hovering state, its continued Restrained state, current-position dependency, and fall transitions on successful repeat save or concentration end. Active-component guards are evaluated against the pre-event active-state snapshot before the current event applies branch transitions or cadence termination, so concentration end still makes every currently elevated target fall. |
| concentration_startup | Startup occurs after declaration and resource payment have allowed activation to proceed, before target resolution. It records one-slot occupancy, replacement, maximum duration, and all termination causes. Blood Tax that reduces the controller to 0 prevents activation from resolving. |
| gate_inheritance | Resolved inheritance can retain, replace, or remove gates and components. This is required when Flare T1 removes T0's save and when higher tiers replace lower-tier conditions. |
| outcome_ordering | Preserve ordered control-relevant steps even when an intervening damage value is outside Control Value: hit before rider saves, no-save Snow Chains Speed 0 before its save, Static Discharge damage context before its save, and Mass Levitation's repeat save before Tier 2 damage. |

## Common policy used by every row

- A rider is declared immediately before its Manifested Strike attack roll. Its Psi and Blood Tax are paid at declaration and remain spent on a miss. A miss prevents every rider effect from resolving.
- Non-signature riders are limited to once per Attack action. Signature Riders cost 0 Psi and are otherwise repeatable across Manifested Strike attacks; only one rider in an Attack action can be Tier 2.
- A standalone feature is declared and paid for when activated. The maintained action-economy policy permits one standalone psionic action per turn and no additional standalone psionic action from Action Surge.
- Tier 0 has no Blood Tax. Tier 1 costs Blood Tax equal to Proficiency Bonus. Tier 2 costs twice Proficiency Bonus in total, replacing rather than adding to the Tier 1 amount.
- “Controller start-next” means the start of the controller's next turn. “Controller end-next” means the end of the controller's next turn. “Affected current-end” means the end of the affected target's current turn.
- Unless a row states otherwise, a save is rolled by the affected target, uses normal roll mode, and has independent resolution for each selected or exposed target.

## Exact 26-row deterministic audit

| Entity / tier | Activation and delivery | Psi and Blood Tax | Selectors and roles | Declaration or placement choice | Gate, save role, mode, timing, and ownership | Control components, magnitude, and duration | Inheritance | Concentration | Area | Movement and path | Contract extensions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| absolute_zero:T0 | Action; standalone | Psi 5; none | One creature within 60 feet; single primary | Controller selects target on activation | Activation then one initial normal Constitution save by target; failure and success resolve separately | Failure: explicit Speed 0 through controller end-next. Success: no control | None | None | None | None | event_context; save_semantics |
| absolute_zero:T1 | Action; standalone | Psi 5; PB | Same single primary | Same target choice | Same initial normal Constitution save | Failure: explicit Speed 0 plus Restrained, both through controller end-next. Success: no control | Resolved from T0; retains Speed 0 and adds Restrained on failure | None | None | None | event_context; save_semantics; gate_inheritance |
| absolute_zero:T2 | Action; standalone | Psi 5; 2 × PB | Same single primary | Same target choice | Same initial normal Constitution save; success has a positive control branch | Failure: explicit Speed 0 plus Stunned through controller end-next. Success: explicit Speed 0 through controller end-next. Stunned replaces only T1 Restrained and does not erase Speed 0 | Resolved from T1; condition replacement with explicit Speed 0 retained | None | None | None | event_context; save_semantics; gate_inheritance |
| arctic_tempest:T0 | Action; standalone | Psi 3; none | Up to three creatures within 60 feet; controller-chosen peers | One target-set choice on activation | Each chosen target makes its own initial normal Constitution save; independent outcomes | Failure: Restrained through controller end-next. Success: no control | None | None | None | None | event_context; save_semantics; target_choice_and_placement |
| arctic_tempest:T1 | Action; standalone | Psi 3; PB | Same up-to-three chosen targets | Same target-set choice | Same independent initial normal Constitution saves | Complete T0 Restrained package is retained through controller end-next; damage is the only canonical delta | Resolved from T0 with full control retained | None | None | None | event_context; save_semantics; target_choice_and_placement; gate_inheritance |
| arctic_tempest:T2 | Action; standalone | Psi 3; 2 × PB | Same up-to-three chosen targets | Same target-set choice | Same independent initial normal Constitution saves | Failure: Stunned instead of Restrained through controller end-next. Success: no control | Resolved from T1; Stunned replaces Restrained | None | None | None | event_context; save_semantics; target_choice_and_placement; gate_inheritance |
| frozen_ground:T0 | Action; standalone | Psi 2; none | Every creature exposed to the area; no creature choice. Placement point within 60 feet is not a target-range limit | Controller selects one point within 60 feet | After activation and area startup, each creature makes a recurring normal Constitution save independently when it first enters on a turn or starts its own turn there. Entry is anchored to any creature's turn; start-turn is anchored to the affected target | Area-wide difficult terrain for the duration. Failed save: Speed 0 through affected current-end. Leaving does not end that timed Speed 0 | None | Required; startup on successful activation before exposure resolution; one slot; replacement; up to 1 minute; canonical termination list | Persistent stationary cylinder; 15-foot radius; 20-foot height; selected-point origin | Area is stationary; no target forced movement | event_context; save_semantics; target_choice_and_placement; area_property; concentration_startup |
| frozen_ground:T1 | Action; standalone | Psi 2; PB | Same every-creature exposure | Same selected-point placement | Same two recurring independent normal Constitution-save triggers and ownership | Same difficult terrain and failed-save Speed 0 | Resolved from T0 | Same required concentration | Persistent stationary cylinder; radius becomes 25 feet; height remains 20 feet | Stationary | event_context; save_semantics; target_choice_and_placement; area_property; concentration_startup; gate_inheritance |
| frozen_ground:T2 | Action; standalone | Psi 2; 2 × PB | Same every-creature exposure | Same selected-point placement | Same recurring independent normal Constitution saves | Area-wide difficult terrain remains. Failed save: Restrained through controller end-next replaces the retained T0 Speed 0 from that trigger. Exiting does not prematurely cancel timed Restrained | Resolved from T1; failed-save component replacement only | Same required concentration | Persistent stationary 25-foot-radius, 20-foot-high cylinder | Stationary | event_context; save_semantics; target_choice_and_placement; area_property; concentration_startup; gate_inheritance |
| snow_chains:T0 | Pre-roll declaration; on-hit attack rider | Psi 2; none | Struck target; primary | Rider and tier chosen once before roll | Declaration and payment, attack roll, then on hit no-save Speed 0, then one initial normal Constitution save. Miss ends graph after costs. Successful save retains the no-save component | Hit: Speed 0 through controller end-next. Failed save additionally Restrained through controller end-next | None | None | None | None | event_context; save_semantics; outcome_ordering |
| snow_chains:T1 | Pre-roll declaration; on-hit attack rider | Psi 2; PB | Same struck primary | Same rider declaration | Same ordered hit, no-save component, then initial normal Constitution save | Speed 0 always on hit. Failed save: Restrained through controller end-next plus reaction denial through controller start-next | Resolved from T0; adds failed-save reaction denial | None | None | None | event_context; save_semantics; outcome_ordering; gate_inheritance |
| snow_chains:T2 | Pre-roll declaration; on-hit attack rider | Psi 2; 2 × PB | Same struck primary | Same rider declaration | Same ordered hit, no-save component, then initial normal Constitution save | Hit always gives Speed 0 through controller end-next. Failure gives reaction denial through controller start-next and Stunned through controller end-next; Stunned replaces Restrained. Success retains Speed 0 only | Resolved from T1; retains Speed 0 and reaction denial, replaces Restrained with Stunned | None | None | None | event_context; save_semantics; outcome_ordering; gate_inheritance |
| flare:T0 | Pre-roll declaration; on-hit attack rider | Psi 3; none | Struck target; primary | Rider and tier chosen once before roll | Attack hit is prerequisite; then one initial normal Dexterity save. Miss has no rider effect. Success has no control | Failed save: Blinded through controller end-next | None | None | None | None | event_context; save_semantics; outcome_ordering |
| flare:T1 | Pre-roll declaration; on-hit attack rider | Psi 3; PB | Same struck primary | Same rider declaration | Attack hit directly applies control; no saving throw exists at this tier | Hit: Blinded through controller end-next | Resolved from T0, but the T0 save gate is removed and replaced by a no-save hit branch | None | None | None | event_context; gate_inheritance; outcome_ordering |
| flare:T2 | Pre-roll declaration; on-hit attack rider | Psi 3; 2 × PB | Same struck primary | Same rider declaration | Attack hit directly applies control; no saving throw | Hit: Blinded through controller end-next. Damage and resistance changes add no control component | Resolved from T1; no-save control retained | None | None | None | event_context; gate_inheritance; outcome_ordering |
| advanced_phase_step:T2 | Bonus action; granted universal standalone feature | Psi 1; 2 × PB | Teleporting controller plus creatures of the controller's choice within 5 feet of the selected endpoint; chosen creatures are unique peers | Choose a visible unoccupied arrival within inherited 30-foot teleport range; choose exactly one endpoint, departure or arrival, for the whole burst | Activation and legal teleport resolve before the instantaneous burst. Each chosen creature makes an independent initial normal Discipline-signature save | Failed save: reaction denial through controller start-next. Success: no control | Resolved from canonical T1; retains 30-foot teleport and arrival legality. T1 is a non-ledger control source | None | Instantaneous 5-foot-radius burst centered on the one selected endpoint | Teleport is not forced movement; arrival must be visible and unoccupied | event_context; save_semantics; choice_binding; target_choice_and_placement; gate_inheritance |
| explosion_implosion:T0 | Pre-roll declaration; on-hit attack rider; once per Attack action | Psi 2; none | Every creature in the sphere, including struck primary; struck target is primary and center, all others are secondaries | Choose Explosion or Implosion once at declaration; selected mode binds every secondary. Movement resolution order is chosen by controller | Declaration and payment, attack roll, then on hit every affected creature makes its own initial normal Strength save. Miss creates no sphere or saves | Each failed target is Restrained through controller end-next. Failed secondaries also move exactly 15 feet; primary saves and can be Restrained but never moves. Success gives neither component | None | None | Instantaneous 15-foot-radius sphere centered on primary target | Secondary straight-line movement relative to primary: Explosion pushes away; Implosion pulls toward. Occupied destinations prohibited. Controller-selected order. Fully blocked path stops at nearest unoccupied space along line | event_context; save_semantics; choice_binding; target_choice_and_placement; movement_path; outcome_ordering |
| explosion_implosion:T1 | Pre-roll declaration; on-hit attack rider; once per Attack action | Psi 2; PB | Same every-creature primary and secondary roles | Same one shared declaration mode and controller-selected resolution order | Same hit-gated independent initial normal Strength saves | Same Restrained component; failed secondary movement becomes exactly 30 feet | Resolved from T0; radius and movement magnitude replace lower values | None | Instantaneous sphere radius becomes 30 feet | Same reference point, line, occupancy, order, and blocked-path fallback at 30 feet | event_context; save_semantics; choice_binding; target_choice_and_placement; movement_path; gate_inheritance; outcome_ordering |
| explosion_implosion:T2 | Pre-roll declaration; on-hit attack rider; once per Attack action | Psi 2; 2 × PB | Same every-creature roles | Same one shared declaration mode and order choice | Same hit-gated independent initial normal Strength saves. Failed-save damage occurs after the save but does not add a control component | T1 Restrained and exact 30-foot secondary movement are unchanged | Resolved from T1; complete control retained | None | Same instantaneous 30-foot-radius sphere | Same complete T1 movement and path semantics | event_context; save_semantics; choice_binding; target_choice_and_placement; movement_path; gate_inheritance; outcome_ordering |
| mass_levitation:T1 | Action; standalone | Psi 5; PB | Five weighted slots spent on unique visible creatures within 60 feet. Tiny, Small, and Medium cost 1; Large costs 2; Huge or larger is immune | Controller chooses a legal slot combination on activation. At each controller start, controller may choose a new destination for every still-affected target | Each target first makes an independent initial normal Strength save. Each affected target repeats at the start of its own turn with Disadvantage. Controller-start reposition happens only for still-affected targets | Initial failure: exact 30-foot lift, persistent elevated and hovering state, and Restrained. Successful repeat: target state ends and it falls from current position. Failed repeat: state persists. At controller start, each still-affected target may move up to 15 feet and remains elevated, hovering, and Restrained. Concentration end: all affected targets fall from current positions | Resolved from corrected T0 full state model | Required; startup on successful activation before initial saves; one slot; replacement; up to 1 minute; canonical termination list | None | Initial exact vertical 30-foot lift. Recurring reposition is up to 15 feet in any direction to a visible unoccupied space. Fall transition uses current position. No falling-damage valuation | event_context; save_semantics; target_choice_and_placement; movement_path; persistent_state_transition; concentration_startup; gate_inheritance |
| mass_levitation:T2 | Action; standalone | Psi 5; 2 × PB | Same weighted unique visible targets and persistent affected-target set | Same target and controller-start destination choices | Initial saves remain normal. At each affected-target start, its repeat Strength save with Disadvantage resolves first. Success ends state, causes fall, and prevents this tier's damage; failure retains state, then damage context resolves | Complete T1 lift, hover, Restrained, reposition, and fall transitions remain. Failed repeat retains control state; successful repeat ends it and falls from current position | Resolved from T1 | Same required concentration and concentration-end fall transition | None | Same T1 movement and path semantics; explicit repeat-save-before-damage ordering | event_context; save_semantics; target_choice_and_placement; movement_path; persistent_state_transition; concentration_startup; gate_inheritance; outcome_ordering |
| telekinetic_slam:T0 | Action; standalone | Psi 3; none | One creature the controller can see within 60 feet; single primary | Controller chooses target; on failure chooses horizontal direction | One initial normal Strength save | Failure: exact 10-foot horizontal push. Success: no control | None | None | None | Movement originates at affected target and follows controller-selected horizontal direction. Preserve standard forced-movement legality without importing T2's visible-destination gate | event_context; save_semantics; movement_path |
| telekinetic_slam:T1 | Action; standalone | Psi 3; PB | Same visible single primary | Same target and failure-direction choices | Same initial normal Strength save | Failure: exact 20-foot horizontal push. Success: no control | Resolved from T0; distance replaces 10 feet | None | None | Same horizontal movement semantics at 20 feet | event_context; save_semantics; movement_path; gate_inheritance |
| telekinetic_slam:T2 | Action; standalone | Psi 3; 2 × PB | Same visible single primary | Controller chooses branch-legal direction and destination | One initial normal Strength save with distinct success and failure movement branches | Failure: exact 30-foot movement plus Speed 0 through controller end-next. Success: up to 10-foot movement and no Speed 0 | Resolved from T1; failure movement becomes 30 feet and gains Speed 0; success gains a separate up-to movement component | None | None | Both branches are horizontal and controller-directed. Failure requires an unobstructed path to a visible unoccupied destination and has no nearest-space fallback. Success is up to 10 feet and does not inherit the failure-only destination gate | event_context; save_semantics; movement_path; gate_inheritance |
| electron_burst:T2 | Pre-roll declaration; on-hit attack rider; once per Attack action | Psi 2; 2 × PB | Every creature in the sphere, including struck primary; no creature choice | Sphere placement is fixed to struck target | Declaration and payment, attack roll, then on hit every affected creature makes its own initial normal Charisma save | Failure: reaction denial plus Disadvantage on all attack rolls through controller start-next. Success: no control | Resolved from canonical T1; retains 10-foot radius. T1 is a non-ledger control source | None | Instantaneous 10-foot-radius sphere centered on primary | None | event_context; save_semantics; target_choice_and_placement; gate_inheritance; outcome_ordering |
| static_discharge:T2 | Pre-roll declaration; on-hit Signature Rider | Psi 0; 2 × PB | Struck primary is always included; up to PB unique controller-chosen secondary creatures within 5 feet of primary | Additional targets chosen with rider declaration; unused capacity allowed | Shared attack-hit prerequisite. On hit, each affected creature independently makes an initial normal Charisma save after the damage context. Lightning immunity does not suppress the save | Failure: reaction denial through controller start-next. Success: no control | Resolved from canonical T1; PB additional targets retained. T1 is a non-ledger control source | None | Not an area; explicit primary-plus-nearby target set | None | event_context; save_semantics; target_choice_and_placement; gate_inheritance; outcome_ordering |

## Final coverage

| Disposition | Count |
| --- | ---: |
| modeled | 35 |
| excluded_by_profile | 14 |
| unsupported_error | 0 |
| total | 49 |
| authority benchmark_ready | true |

The expected modeled set is derived as canonical 49-row universe minus the maintained exclusion map. It must not be copied as independent 35-row allowlists in TypeScript and Python. No pending_authority_population reason remains.

## Exact maintained exclusions

| Entity / tier | Disposition | Reason |
| --- | --- | --- |
| advanced_beguile:T0 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_beguile:T1 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_beguile:T2 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_deflection_screen:T2 | excluded_by_profile | incoming_enemy_attacks_unmodeled |
| advanced_gravitic_press:T0 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_gravitic_press:T1 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_gravitic_press:T2 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_improved_phase_step:T2 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_mind_lock:T0 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_mind_lock:T1 | excluded_by_profile | selectable_advanced_training_disabled |
| advanced_mind_lock:T2 | excluded_by_profile | selectable_advanced_training_disabled |
| thermal_fracture:T0 | excluded_by_profile | outside_headline_control_value |
| thermal_fracture:T1 | excluded_by_profile | outside_headline_control_value |
| thermal_fracture:T2 | excluded_by_profile | outside_headline_control_value |

## Existing nine representative models: concrete audit findings

These changes correct representational defects; they do not change canonical subclass mechanics. Canonically correct values noted below must be preserved.

| Existing row | Preserve | Concrete defect | Required correction |
| --- | --- | --- | --- |
| ball_lightning:T2 | Action, Psi 5, Tier 2 Blood Tax, 30-foot sphere, entry once per turn, moving the orb onto a stationary creature is not entry, bonus-action orb movement, while-area conditions, and exit termination | Selector range conflates center placement within 60 feet with target range; cluster_remainder does not say every creature. Entry and start_turn are ownerless, save role and normal mode are absent, orb movement omits up-to and controller-turn context, and concentration startup is on_resolution | Separate placement from population; encode every creature; use any-turn entry and affected-target-start contexts with recurring normal independent saves; encode bonus-action-on-controller-turn movement up to 15 feet; start concentration on successful activation before exposure resolution |
| forked_lightning:T2 | Primary visible within 60 feet; up to five secondaries within 30 feet of primary; independent Charisma outcomes; reaction denial, all-attack Disadvantage, and primary-only Speed 0 through controller start-next | Secondary uniqueness and controller-choice semantics are implicit. The combined selector gate does not fail closed against applying a primary-only component when a secondary fails, and cadence/save timing is ownerless | Add explicit unique controller-chosen secondaries and initial normal independent save context; split role-sensitive gates or add per-current-target binding so only a failed primary can receive primary Speed 0 |
| glacial_spike:T0 | Hit applies nonstacking 10-foot Speed reduction through controller end-next | Cadence has no controller-end event even though duration does; event context is incomplete | Use typed hit and controller-end-next events; make cadence agree with duration |
| glacial_spike:T1 | Hit first applies T0 reduction; post-hit Constitution failure replaces it with Speed 0; success retains reduction | Save lacks initial/normal timing. Speed-reduction cadence repeat save and end save conflicts with branch-specific refresh on success and replacement on failure | Encode ordered hit then initial normal save and branch-specific retain/replace transitions; remove contradictory generic cadence |
| glacial_spike:T2 | Hit first applies T0 reduction; failure Restrained replaces Tier 1 Speed 0; success retains T0 reduction | Same untyped save and contradictory cadence problem; controller-end duration is absent from cadence | Preserve the approved replacement graph but use typed branch transitions and controller-end-next termination |
| mass_levitation:T0 | Five weighted visible unique slots, initial Strength saves, 30-foot lift, Restrained, one-minute concentration | Repeat-save gate is incorrectly a root and ownerless, so it is not contingent on initial failure or affected state. Persistent elevation/hover, current-position fall on repeat success, fall on concentration end, and explicit startup are absent | Make repeat saves recurring only for affected targets at their start turns; add persistent elevation/hover state, successful-save and concentration-end fall transitions, current-position reference, normal initial save, and activation-time concentration startup |
| telekinetic_shove:T0 | Exact 10-foot movement on failed Strength save; no movement on success; declaration replaces Push mastery for the hit | controller_choice and legal_destination erase the explicit horizontal direction and do not distinguish canonical path rules; save role/mode is absent | Encode exact 10-foot controller-chosen horizontal forced movement with the controller as the explicit reference point and an initial normal post-hit Strength save; do not invent Slam T2 visibility rules |
| telekinetic_shove:T1 | Exact distance increases to 15 feet; success remains unmoved | Same horizontal/path and save-context defects | Preserve 15 feet while adding explicit horizontal movement and initial normal save semantics |
| telekinetic_shove:T2 | Exact failed-save distance 20 feet and Speed 0 through controller end-next | Same horizontal/path and save-context defects; Speed 0 cadence omits its controller-end event | Preserve 20 feet and failure-only Speed 0; add horizontal movement structure, initial normal save context, and controller-end-next termination |

## Completed foundation generalization

- Removed the TypeScript and Python nine-row modeled-key sets.
- Replaced fixed 9 / 14 / 26 checks with 35 / 14 / 0 results derived from the completed canonical ledger and maintained exclusion map.
- Replaced the five-family MODELED_POLICIES table with expectations derived from canonical entity activation, feature role, Psi cost, signature-rider status, action-economy policy, and Calculator delivery metadata only where it is genuinely authoritative.
- Replaced the two-entity concentration set with canonical entity metadata; Frozen Ground, Mass Levitation, and Ball Lightning are the three modeled concentration families.
- Removed representative-only policy checks and every message that calls the completed state a foundation or pending population.
- No arbitrary unrecognized row is permitted: the exact canonical 49-row universe and exclusion map remain fail closed.
- TypeScript and Python acceptance behavior is equivalent through the one shared mutation corpus.

## Control-target supplement design

Maintained files:

- harness/data/srd_control_targets.json
- harness/provenance/srd-control-targets.json

Final supplement SHA-256: ce79647cc2a6ce4a9c5d5a7b84a21b0106e3cc55da2f1da6c45377d1a91a3683. Final provenance SHA-256: 7be56099c66a64beb34f826997039b6ac8806feb523da879ea657edf0ea57b8b. Provenance pins the official SRD 5.2.1 PDF SHA-256 8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87 and row-auditable source pages. All 28 Speed and relevant Senses entries were independently checked against that source; no movement mode, hover status, or retained nonvisual sense was inferred.

The data supplement joins fail closed to all 28 existing roster rows using the exact typed tuple Level plus Target, with no case folding, whitespace normalization, fuzzy matching, or damage-configuration dependency.

Each supplement row contains only officially sourced control facts:

- walking Speed;
- explicit fly, swim, climb, and burrow modes and speeds, with absence represented explicitly;
- hover status;
- typed relevant nonvisual senses, range, and any material official limitation; ordinary darkvision is excluded.

Validation rejects duplicate, missing, or extra join keys; inferred values; negative, non-integer, or malformed speeds and ranges; hover without a fly mode; unknown movement modes; unknown sense kinds; unknown fields; and nondeterministic row ordering. Serialization is deterministic. The provenance file uses the same pinned official SRD 5.2.1 source and provides row-auditable source identity and location. Both files are added to build/inputs.json.

Readiness remains honestly separated:

- authority readiness is the 35 / 14 / 0 / 49 ledger and authority benchmark_ready flag;
- combined control-input readiness additionally requires exact 28-row supplement validation.

No monster tactics, pathfinding, altitude selection, line-of-sight simulation, or behavioral heuristics enter the supplement or loader.

## Damage roster baseline and boundary

- File: harness/data/srd_targets.csv
- Baseline rows: 28 data rows plus one header row
- Baseline SHA-256: dfbda8f8e51d85b898d406a1b7dff63a40899bdf460fe5bc25d73c61d1d1ca5a
- Final SHA-256: dfbda8f8e51d85b898d406a1b7dff63a40899bdf460fe5bc25d73c61d1d1ca5a (exact baseline match)
- Damage comparator/configuration SHA-256 values remain 03d5da10742ef3bc4f63e57bacd9bc966ee68835e9629e47bab863b53ab5bf7d and d3f953192e29c9b098715e3c5a426b62f680dd097bec3d41a7a0831b7c47046c; both files are unchanged from main
- Damage evaluator and planner proof: no diff from main in harness/model.py, harness/damage_harness.py, harness/damage_report.py, or harness/readme_damage.py
- Structured damage projection proof: exact structural equality after removing only authority_path, authority_sha256, and schema_version; those identities changed from the clean-main path/hash/schema to the current path, 4add4d84eb01832eb69b02cfbaec12ad64360184d6ea0bd60f3bb281ea00193e, and 3.1.0
- Focused damage numerical, comparator, and planner sentinel results: 4/4 passed
- Control-only target data cannot enter damage computation: the new loader is isolated in harness/control_targets.py; the damage roster, model, evaluator, comparator, and report sources are unchanged

The base roster is not modified and no control-only column is added to it.

## Local validation evidence

These are the exact final commands, exit results, and relevant test counts or artifact identities. No analytical benchmark work substitutes for validation.

| Required evidence | Exact final command | Result |
| --- | --- | --- |
| TypeScript typecheck | npm run typecheck | Pass |
| Canonical and semantic validation | npm run validate | Pass; 44 YAML-authored entities |
| Focused TypeScript Control Authority tests | node --import tsx --test tests/harness-authority.test.ts tests/control-targets.test.ts tests/control-authority-v2-population.test.ts | Pass; 64/64, including 51/51 population and branch-exactness cases |
| Complete TypeScript shared parity corpus | node --import tsx --test tests/control-authority-v2-parity.test.ts | Pass; 114/114 Node subtests over 113 unique shared cases, with all original 71 IDs retained |
| Focused Python Control Authority tests | python3 -m unittest harness.tests.test_authority_v2 harness.tests.test_control_targets | Pass; 18/18 |
| Complete Python shared parity corpus | python3 -m unittest harness.tests.test_authority_v2_parity | Pass; 1/1 corpus driver over the same 113 cases |
| Control-target supplement exact-coverage validation | python3 -m harness.control_targets | Pass; 28 exact joins |
| Maintained harness validation | npm run harness:validate | Pass; authority valid and benchmark-ready at 35/14/0/49, plus 28 exact target joins |
| Harness suite | npm run test:harness | Pass; 77/77 |
| Focused damage numerical, comparator, and planner sentinels | python3 -m unittest harness.tests.test_harness.FighterNumericalTests.test_exact_fighter_dpr_sentinels_cover_every_supported_level harness.tests.test_harness.ComparatorLeafContractTests.test_every_damage_comparator_leaf_is_numerically_live harness.tests.test_harness.DamagePlannerTests.test_pre_roll_rider_cost_is_spent_on_a_miss_without_outcome_lookahead harness.tests.test_harness.DamagePlannerTests.test_observed_state_policy_matches_reviewed_l20_sentinel | Pass; 4/4 |
| Complete maintained non-analytical tests | npm test | Pass; 250/250 |
| Prototype build | npm run build | Pass; prototype HTML and manifest written |
| Build determinism | npm run test:determinism | Pass; 4 artifacts identical |
| Layout tests | npm run test:layout | Pass; 11/11 across Chromium and Firefox |
| Authorized release-profile build and release identity | KV_RELEASE_APPROVED=1 npm run build:release, followed by the exact CI test/grep identity block | Pass; release status/rules version present and prototype/application-version markers absent |
| Architecture and build-input tests | node --import tsx --test tests/architecture.test.ts tests/ci-contract.test.ts tests/harness-authority.test.ts | Pass; 35/35 |
| Whitespace and patch integrity | git diff --check | Pass after final audit update |
| Base damage roster byte identity | sha256sum harness/data/srd_targets.csv | Pass; dfbda8f8e51d85b898d406a1b7dff63a40899bdf460fe5bc25d73c61d1d1ca5a |
| Final read-only canonical re-audit of all 35 modeled rows | Separate manual deterministic table review against canonical entity text | Approved; 35/35 modeled rows, 14/14 exact exclusions, all nine representatives, and branch-test coverage |
| ControlAuthorityV2Model.load with require_benchmark_ready true | python3 -m harness.authority --projection-version 2.1.0 --require-benchmark-ready | Pass; valid=true, benchmark_ready=true, 35/14/0/49 |

Prohibited-run confirmation:

- full damage matrix: not run; only the maintained validate-only damage authority command and four focused sentinels ran
- README damage regeneration or check: neither command ran
- legacy control command: none exists or ran
- Control Value scoring, comparator v2, observed-state control planning, sensitivity, and public classification: none ran; only the required focused damage-planner sentinels ran

## Exact-head CI recording

- Branch: agent/issue-39-control-authority-v2-population
- Final head SHA: recorded in the mutable draft PR and issue #39 completion record after push; intentionally external to this self-referential tracked audit
- GitHub Actions run ID and URL: recorded in the draft PR and issue #39 completion record after the exact-head run
- Exact-head match: verified and recorded externally without changing the tested head
- Job inventory: actual metadata, verification, and main_branch_gate jobs recorded externally after the run
- All required job conclusions: recorded externally after exact-head completion
- Analytical benchmark absence: verified from the actual job and step inventory and recorded externally
- Draft PR number and URL: recorded in issue #39 after creation

## Final scope sign-off

- Final separate re-audit found all 35 modeled rows faithful to canonical entity text: approved, 35/35
- All nine representative corrections above are enumerated in the draft PR description and issue completion record
- Exact 14 exclusions remain unchanged: confirmed 14/14, with exact reasons
- No legacy control, Control Value scoring, comparator v2, observed-state control planner, sensitivity, public promotion, or subclass-rule change entered the diff: confirmed
- codex/issues-31-36-discoverability, frozen release refs, tags, Releases, and evidence remain untouched: confirmed
- No checkpoint or stash was created: confirmed; git stash list is empty

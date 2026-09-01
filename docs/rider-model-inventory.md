# Rider-first model inventory

## Status and authority

This is the accepted Phase 1 design inventory for the v14.4 rider-first mechanical-model work. It snapshots canonical rules **v14.3.0** and is intentionally non-normative. `KineticVanguard.yaml` remains the sole rules authority; this document records migration dispositions and behavior-preservation sentinels, not replacement rules text. The approved next-stage architecture is recorded in the [neutral mechanical primitives design](mechanical-primitives-design.md).

No schema, runtime, Calculator, harness, or player-facing mechanic changes are authorized by this inventory. If this inventory and the canonical authority disagree, the canonical authority wins and the inventory must be corrected before implementation proceeds.

## Scope

The Subclass Feature Reference contains 34 rows: 31 concrete ability entities and three Advanced Training choice-grant summary rows. The table below inventories the 31 concrete abilities exactly once. The three choice-grant rows are progression events, not independently resolvable abilities, so they are not separate inventory entries.

Shared chassis and rules-system entities such as Manifested Strike, Signature Rider, Overload, Kinetic Mastery, Psi Reservoir, and Discipline Signature Save define the lifecycle used by these abilities but are not themselves migration candidates in this inventory. In particular, Kinetic Mastery is not a rider: its legal coexistence with one declared rider must survive the migration.

## Delivery dispositions

| Disposition | Model status | Meaning |
|---|---|---|
| `standard_rider` | Standard rider lifecycle | Declared for one Manifested Strike before its attack roll, consumes that swing's one rider allowance, and resolves only if that strike hits. Extra named targets do not make it a composite rider. |
| `area_rider` | Standard rider lifecycle | Uses the same declaration and hit gate as a standard rider, then resolves one area effect from the struck target. The area is the effect of one rider, not a bundle of riders. |
| `standalone_activation` | Justified exception | Uses its existing Action, Bonus Action, or Reaction independently of a Manifested Strike. Converting it to an on-hit rider would change action economy or timing. |
| `standalone_area` | Justified exception | Uses its existing standalone activation to create or resolve an area, persistent zone, or the explicitly carved-out Mass Levitation multi-target effect. “Standalone” describes delivery, not necessarily the Action action type. |
| `passive` | Outside the rider lifecycle | Continuously modifies another resource or feature and has no declaration or hit-resolution lifecycle of its own. |
| `mixed_passive_standalone` | Justified mixed exception | One canonical entity contains both a passive benefit and a separately activated standalone surface. Each surface must retain its own lifecycle. |

The two standardized area patterns are therefore `area_rider` and `standalone_area`. Sphere or Cylinder geometry does not by itself decide whether an ability is a rider; the existing activation and hit gate do.

## Findings that constrain implementation

1. **One rider per swing fits all 14 current on-hit abilities.** Twelve are `standard_rider`; Explosion/Implosion and Electron Burst are `area_rider`. None requires a composite-rider category.
2. **Extra targets are not automatically areas.** Static Discharge and Branching Bolt remain `standard_rider` because one declaration selects a bounded set of additional targets. Their effects do not create geometric zones.
3. **Phase Step adds a previously omitted standalone-area case.** Its Tier 2 form resolves through a burst at the departure or arrival space, so the full feature must support standalone-area behavior without changing its Bonus Action activation.
4. **Improved Phase Step is also a standalone-area case.** Its Sphere originates at one teleport endpoint and is part of the same Bonus Action activation.
5. **Mass Levitation remains an explicit standalone-area exception by ruling.** It is slot-targeted rather than geometric, but its persistent multi-target, repeat-save, concentration, and movement lifecycle should not be forced through the ordinary rider schema.
6. **Empathic Sense has two delivery surfaces.** Its passive Insight benefit and limited Bonus Action Active Scan belong to one canonical feature but cannot share one resolution lifecycle.
7. **Standalone attacks remain standalone.** Arctic Tempest, Telekinetic Slam, Forked Lightning, Beguile, and Absolute Zero could superficially resemble attack riders, but converting them would change their action economy and is outside this behavior-preserving migration.

## Complete ability inventory

“Activation” preserves the current player-facing timing. “Target/save shape” records the resolution topology required by a future declarative model. “Sentinel” is the minimum representative behavior that must remain true after migration; it is verification guidance, not new rules authority.

| Entity | Feature | Level | Activation | Disposition | Target/save shape | Ongoing duration | Behavior-preservation sentinel |
|---|---|---:|---|---|---|---|---|
| `glacial_spike` | Glacial Spike | 3 | Before roll; resolves on hit | `standard_rider` | Struck target; higher tiers add a Constitution save after the hit | Until end of next turn | Declaring it replaces Slow mastery for that hit; a successful higher-tier save retains the Tier 0 Speed reduction. |
| `ember_bolt` | Ember Bolt | 3 | Before roll; resolves on hit | `standard_rider` | Struck target; no save | Instantaneous | The fixed extra damage remains repeatable on separate Manifested Strikes and does not acquire a per-Attack-action limit. |
| `telekinetic_shove` | Telekinetic Shove | 3 | Before roll; resolves on hit | `standard_rider` | Struck target; Strength save after damage | Varies by tier | It replaces Push mastery even on a successful save, and the target is moved only once. |
| `static_discharge` | Static Discharge | 3 | Before roll; resolves on hit | `standard_rider` | Struck target plus selected nearby targets; Tier 2 gives each target an independent Charisma save | Varies by tier | One declaration remains one rider; a lightning-immune target still makes the Tier 2 save even when it takes no lightning damage. |
| `advanced_deflection_screen` | Deflection Screen | 5 | Reaction to non-self damage | `standalone_activation` | Self damage reduction; Tier 2 separately resolves against an originating creature with a Strength save | Varies by tier | Self-inflicted damage and Blood Tax remain ineligible; no-origin damage still receives reduction but creates no push or Prone effect. |
| `common_empathic_sense` | Empathic Sense | 7 | Passive plus limited Bonus Action scan | `mixed_passive_standalone` | Passive self modifier; Active Scan senses eligible creatures in a radius with no save | Continuous passive; instantaneous scan | The passive Insight increase is continuous, while each scan remains a separately limited standalone activation and only returns the canonical snapshot information. |
| `snow_chains` | Snow Chains | 7 | Before roll; resolves on hit | `standard_rider` | Struck target; Speed 0 on hit, then Constitution save for additional conditions | Until end of next turn | The no-save Speed 0 effect remains independent of the failed-save condition package. |
| `thermal_fracture` | Thermal Fracture | 7 | Before roll; resolves on hit | `standard_rider` | Struck target; no save | Until start of next turn | The triggering hit never benefits from the Armor Class reduction; later applications use the strongest reduction or refresh an equal one. |
| `vectored_thrust` | Vectored Thrust | 7 | Bonus Action | `standalone_activation` | Self buff; no attack or save | Up to 10 minutes | Tier 0 and Tier 1 require Concentration, while Tier 2 retains the duration without Concentration. |
| `branching_bolt` | Branching Bolt | 7 | Before roll; resolves on hit | `standard_rider` | Struck target plus preselected nearby targets; no save | Instantaneous | Additional targets are selected when the rider is declared, unused branches are lost, and arcs do not continue from secondary targets. |
| `frozen_ground` | Frozen Ground | 10 | Action; Concentration | `standalone_area` | Persistent Cylinder; entry/start-of-turn Constitution save | Concentration, up to 1 minute | Entry triggers at most through the canonical entry/start timing, and the Tier 2 Restrained result replaces rather than stacks with the lower-tier Speed-0 result. |
| `cinder_lance` | Cinder Lance | 10 | Before roll; resolves on hit | `standard_rider` | Struck target; no save | Instantaneous | Damage continues to use the level-based base Manifested Strike die; Tier 2 alone bypasses fire Resistance. |
| `explosion_implosion` | Explosion/Implosion | 10 | Before roll; resolves on hit | `area_rider` | Hit-centered Sphere; each creature makes its own Strength save | Until end of next turn | One hit-gated rider creates the whole Sphere; the struck target can be Restrained but is never pushed or pulled from the Sphere's center. |
| `electron_burst` | Electron Burst | 10 | Before roll; resolves on hit | `area_rider` | Hit-centered Sphere; each creature makes its own Charisma save and resolves role-specific damage | Varies by tier | One hit-gated rider creates the whole burst; primary and secondary damage remain distinct and Tier 2 conditions remain failed-save gated per creature. |
| `advanced_phase_step` | Phase Step | 10 | Bonus Action | `standalone_area` | Self teleport; Tier 2 adds a chosen-endpoint burst using the Discipline signature save | Varies by tier | Tier 0 and Tier 1 remain teleport-only; Tier 2 adds the burst without changing the Bonus Action activation or provoking Opportunity Attacks. |
| `arctic_tempest` | Arctic Tempest | 15 | Action | `standalone_activation` | Up to three named targets; each makes a Constitution save | Until end of next turn | Each target resolves the same activation independently; Tier 2 replaces Restrained with Stunned rather than stacking both conditions. |
| `flare` | Flare | 15 | Before roll; resolves on hit | `standard_rider` | Struck target; extra damage on hit, then Dexterity save for Blinded | Until end of next turn | The extra damage is not save-gated; only Blinded depends on the target failing its save. |
| `telekinetic_slam` | Telekinetic Slam | 15 | Action | `standalone_activation` | One target; Strength save controls damage and movement outcomes | Varies by tier | Tier 2 still pushes a successful-save target by its smaller amount while reserving Speed 0 for a failed save. |
| `forked_lightning` | Forked Lightning | 15 | Action | `standalone_activation` | Primary target plus bounded secondary targets; independent Charisma saves and role-specific outcomes | Varies by tier | No target's save determines another target's damage or conditions; Tier 2 Speed 0 remains primary-target-only. |
| `advanced_mind_shred` | Mind Shred | 15 | Before roll; resolves on hit | `standard_rider` | Struck target; no save | Instantaneous | It remains a single hit-gated psychic-damage rider, with Resistance bypass only at Tier 2. |
| `advanced_beguile` | Beguile | 15 | Action; Concentration | `standalone_activation` | One target at lower tiers and up to five at Tier 2; Charisma save; tier-selected referenced effect | Varies by tier | Higher tiers replace lower-tier effects, the save always uses Charisma, and the feature remains magical but neither a spell nor a rider. |
| `advanced_mind_lock` | Mind Lock | 15 | Before roll; resolves on hit | `standard_rider` | Struck target; one Intelligence save gates the tier's whole condition package | Until end of next turn | A successful save applies none of the feature's conditions; Tier 2 replaces Incapacitated with Stunned while retaining Blinded. |
| `advanced_gravitic_press` | Gravitic Press | 15 | Action; Concentration | `standalone_area` | Persistent Cylinder; no-save area effects plus entry/start-of-turn Strength save | Concentration, up to 1 minute | Falling and fly denial remain no-save area effects; the save separately gates reaction denial and Tier 2 Speed 0. |
| `advanced_barrier` | Barrier | 15 | Bonus Action; Concentration | `standalone_activation` | Self mode selection; no attack or save | Varies by tier | Tier 1 selects two distinct modes; Tier 2 keeps the longer duration and out-of-Initiative replacement procedure without becoming a rider. |
| `advanced_improved_phase_step` | Improved Phase Step | 15 | Bonus Action | `standalone_area` | Self teleport plus a chosen-endpoint Sphere affecting selected other creatures with the Discipline signature save | Varies by tier | The user remains unaffected by the burst, only selected other creatures resolve it, and teleportation still avoids Opportunity Attacks. |
| `advanced_overload_mastery_ii` | Overload Mastery II | 18 | Passive | `passive` | Modifies Overload Mastery uses; no target, attack, or save | Continuous | The Psionic Apex prerequisite and exactly one additional rest-based use remain intact. |
| `advanced_inner_reserve` | Inner Reserve | 15 | Passive | `passive` | Modifies maximum Psi; no target, attack, or save | Continuous | It continues to increase the maximum pool once and cannot be selected more than once. |
| `absolute_zero` | Absolute Zero | 20 | Action | `standalone_activation` | One target; Constitution save controls damage and most conditions | Until end of next turn | Tier 2 still makes Speed 0 apply on a successful save while its Stunned result remains failed-save gated. |
| `furnace_strike` | Furnace Strike | 20 | Before roll; resolves on hit | `standard_rider` | Struck target; no save | Instantaneous | It remains one hit-gated damage rider, with fire Resistance bypass only at Tier 2. |
| `mass_levitation` | Mass Levitation | 20 | Action; Concentration | `standalone_area` | Slot-budgeted named targets; independent initial and repeat Strength saves; persistent movement/hover state | Concentration, up to 1 minute | Target-size slot costs, independent repeat saves, falling on release, and Tier 2 damage only after a failed repeat save all remain intact. |
| `ball_lightning` | Ball Lightning | 20 | Action; Concentration; later Bonus Action movement | `standalone_area` | Persistent movable Sphere; entry/start-of-turn Charisma save | Concentration, up to 1 minute | Moving the orb onto a stationary creature never triggers immediate damage; entry is limited to once per turn and Tier 2 conditions end on leaving. |

## Implementation gate

Broad schema or runtime implementation may begin only after this inventory is accepted. The first implementation slice should prove the common rider lifecycle against representative sentinels from each rider shape:

- a no-save single-target rider (`ember_bolt`);
- a hit-then-save rider (`glacial_spike` or `flare`);
- a bounded extra-target rider (`static_discharge` or `branching_bolt`);
- an area rider (`explosion_implosion` or `electron_burst`);
- one standalone activation and one standalone area to prove they remain outside the one-rider-per-swing contract.

Only after those equivalence tests pass should the migration expand across the remaining consumers. Any ambiguity or suspected balance problem discovered during implementation must be parked separately without changing v14.3.0 behavior.

# Rider-first model inventory

## Status and authority

This is the accepted v14.4 inventory of canonical rules **v14.3.0**. It is non-normative: `KineticVanguard.yaml` remains the sole rules authority. This document records delivery, targeting topology, activation, and behavior-preservation sentinels for the representation refactor.

Delivery and targeting are orthogonal. An “area rider” in prose means `delivery = rider` plus `targeting topology = area`; it is not a distinct lifecycle. No inventory label combines the two axes, and there is no composite-rider concept.

## Scope

The Subclass Feature Reference contains 34 rows: 31 concrete ability entities and three Advanced Training choice-grant summaries. The table inventories the 31 concrete abilities exactly once. The choice-grant rows are progression events, not independently resolvable abilities.

Shared chassis entities such as Manifested Strike, Signature Rider, Overload, Kinetic Mastery, Psi Reservoir, and Discipline Signature Save define the lifecycle used by these abilities but are not migration candidates. Kinetic Mastery remains separate from the Manifested Strike rider slot.

## Orthogonal axes

Delivery is one of:

- `rider`: declared for one Manifested Strike before the attack roll, consumes that swing's single rider allowance, and resolves on that strike's hit;
- `standalone`: retains its explicitly authored Action, Bonus Action, or Reaction and never consumes a Manifested Strike rider slot;
- `passive`: continuously modifies a resource or feature without a rider declaration;
- `mixed`: one entity owns multiple surfaces with separately declared delivery lifecycles.

Targeting topology is one of:

- `single`: one struck or selected creature;
- `discrete_multi`: multiple individually selected, linked, slot-budgeted, or eligible creatures without area geometry;
- `area`: explicit Sphere or Cylinder geometry and origin;
- `self`: the user, their movement, or their defense;
- `none`: no target selector;
- `mixed`: tiers or surfaces intentionally use more than one topology.

Activation remains independent from both axes.

## Findings that constrain implementation

1. All 14 on-hit abilities use the same `rider` lifecycle and the same single Manifested Strike rider slot. Additional targets or an area never create another rider declaration.
2. Static Discharge and Branching Bolt are `rider + discrete_multi`; they do not invent geometry. Explosion/Implosion and Electron Burst are `rider + area`; their explicit geometry does not create a separate delivery lifecycle.
3. Mass Levitation is `standalone + discrete_multi`. Its five weighted target slots are selection/cardinality mechanics, not an area.
4. Phase Step changes from `self` to `area` at Tier 2 while retaining one standalone Bonus Action lifecycle. Improved Phase Step is standalone with an explicit endpoint Sphere.
5. Empathic Sense owns a passive/no-target surface and a standalone/discrete-multi Active Scan surface.
6. Concrete discipline damage types and ordinary saves are authored on the feature mechanics. Universal signature-save features own a bounded discipline-to-save mapping.
7. Improved Phase Step's damage type is genuinely runtime-dependent because its text follows the current Manifested Strike damage type; it is not a statically knowable discipline alias.

## Complete ability inventory

| Entity | Feature | Level | Delivery | Targeting topology | Activation | Target/save mechanics | Behavior-preservation sentinel |
|---|---|---:|---|---|---|---|---|
| `glacial_spike` | Glacial Spike | 3 | `rider` | `single` | Before roll; resolves on hit | Struck target; higher tiers add Constitution save | Replaces Slow mastery for that hit; successful higher-tier save retains Tier 0 Speed reduction. |
| `ember_bolt` | Ember Bolt | 3 | `rider` | `single` | Before roll; resolves on hit | Struck target; no save | Fixed fire damage remains repeatable on separate Manifested Strikes. |
| `telekinetic_shove` | Telekinetic Shove | 3 | `rider` | `single` | Before roll; resolves on hit | Struck target; Strength save after damage | Replaces Push mastery even on a successful save; target is moved only once. |
| `static_discharge` | Static Discharge | 3 | `rider` | `discrete_multi` | Before roll; resolves on hit | Struck target plus nearby selected targets; independent Tier 2 Charisma saves | Target counts and damage-immunity-independent Tier 2 saves remain unchanged. |
| `advanced_deflection_screen` | Deflection Screen | 5 | `standalone` | `mixed` (`self`, `single`) | Reaction | Self damage reduction; Tier 2 originating creature makes Strength save | No-origin damage still receives reduction but creates no push or Prone effect. |
| `common_empathic_sense` | Empathic Sense | 7 | `mixed` (`passive`, `standalone`) | `mixed` (`none`, `discrete_multi`) | Passive; limited Bonus Action scan | Passive self modifier; scan senses all eligible creatures in range | Passive increase stays continuous; each scan remains separately limited and instantaneous. |
| `snow_chains` | Snow Chains | 7 | `rider` | `single` | Before roll; resolves on hit | Struck target; Constitution save for added conditions | No-save Speed 0 remains independent of the failed-save package. |
| `thermal_fracture` | Thermal Fracture | 7 | `rider` | `single` | Before roll; resolves on hit | Struck target; no save | Triggering hit never benefits from Armor Class reduction. |
| `vectored_thrust` | Vectored Thrust | 7 | `standalone` | `self` | Bonus Action | Self fly Speed; no save | Tier 0/1 Concentration and Tier 2 no-Concentration behavior remain intact. |
| `branching_bolt` | Branching Bolt | 7 | `rider` | `discrete_multi` | Before roll; resolves on hit | Struck target plus preselected creatures within 15 feet; no save | Unused branches are lost and arcs do not continue from secondary targets. |
| `frozen_ground` | Frozen Ground | 10 | `standalone` | `area` | Action; Concentration | Persistent Cylinder; entry/start Constitution save | Trigger timing and Tier 2 replacement behavior remain unchanged. |
| `cinder_lance` | Cinder Lance | 10 | `rider` | `single` | Before roll; resolves on hit | Struck target; no save | Tier 2 alone bypasses fire Resistance. |
| `explosion_implosion` | Explosion/Implosion | 10 | `rider` | `area` | Before roll; resolves on hit | Hit-centered Sphere; independent Strength saves | One rider creates the whole Sphere; struck target is never moved from its center. |
| `electron_burst` | Electron Burst | 10 | `rider` | `area` | Before roll; resolves on hit | Hit-centered Sphere; independent Charisma saves and role-specific damage | Primary/secondary damage and Tier 2 gates remain unchanged. |
| `advanced_phase_step` | Phase Step | 10 | `standalone` | `mixed` (`self`, `area`) | Bonus Action | Self teleport; Tier 2 endpoint Sphere with feature-local discipline save mapping | Tier 2 adds the burst without changing activation or provoking Opportunity Attacks. |
| `arctic_tempest` | Arctic Tempest | 15 | `standalone` | `discrete_multi` | Action | Up to three selected targets; independent Constitution saves | Tier 2 replaces Restrained with Stunned rather than stacking them. |
| `flare` | Flare | 15 | `rider` | `single` | Before roll; resolves on hit | Struck target; Dexterity save gates only Blinded | Fire damage remains unconditional on the save. |
| `telekinetic_slam` | Telekinetic Slam | 15 | `standalone` | `single` | Action | One selected target within 60 feet; Strength save | Tier 2 successful-save push and failed-save Speed 0 remain distinct. |
| `forked_lightning` | Forked Lightning | 15 | `standalone` | `discrete_multi` | Action | Primary plus bounded secondary targets; independent Charisma saves | Primary/secondary damage and Tier 2 primary-only Speed 0 remain unchanged. |
| `advanced_mind_shred` | Mind Shred | 15 | `rider` | `single` | Before roll; resolves on hit | Struck target; no save | Psychic Resistance bypass remains Tier 2 only. |
| `advanced_beguile` | Beguile | 15 | `standalone` | `mixed` (`single`, `discrete_multi`) | Action; Concentration | One lower-tier target; up to five targets within 60 feet at Tier 2; Charisma save | Higher tiers replace lower effects; save remains Charisma regardless of Discipline. |
| `advanced_mind_lock` | Mind Lock | 15 | `rider` | `single` | Before roll; resolves on hit | Struck target; Intelligence save | Tier 2 replaces Incapacitated with Stunned while retaining Blinded. |
| `advanced_gravitic_press` | Gravitic Press | 15 | `standalone` | `area` | Action; Concentration | Persistent 15-foot-radius, 20-foot-high Cylinder within 60 feet; Strength save | No-save area effects and save-gated effects remain separate. |
| `advanced_barrier` | Barrier | 15 | `standalone` | `self` | Bonus Action; Concentration | Self mode selection; no save | Mode count, duration, and replacement procedure remain unchanged. |
| `advanced_improved_phase_step` | Improved Phase Step | 15 | `standalone` | `area` | Bonus Action | Endpoint 5-foot Sphere; up to three other creatures; feature-local discipline save mapping | Damage follows current Manifested Strike type; user remains unaffected. |
| `advanced_overload_mastery_ii` | Overload Mastery II | 18 | `passive` | `none` | Passive | No target | Exactly one additional rest-based use remains intact. |
| `advanced_inner_reserve` | Inner Reserve | 15 | `passive` | `none` | Passive | No target | Maximum Psi increase remains +4 and non-repeatable. |
| `absolute_zero` | Absolute Zero | 20 | `standalone` | `single` | Action | One target within 60 feet; Constitution save | Tier 2 Speed 0 still applies on success; Stunned remains failed-save-only. |
| `furnace_strike` | Furnace Strike | 20 | `rider` | `single` | Before roll; resolves on hit | Struck target; no save | Tier 2 alone bypasses fire Resistance. |
| `mass_levitation` | Mass Levitation | 20 | `standalone` | `discrete_multi` | Action; Concentration | Five weighted target slots within 60 feet; unique targets; independent Strength saves | Slot costs, repeat saves, falling, and Tier 2 post-failed-repeat damage remain intact. |
| `ball_lightning` | Ball Lightning | 20 | `standalone` | `area` | Action; Concentration; later Bonus Action movement | Persistent movable Sphere; entry/start Charisma save | Moving orb onto a stationary creature still does not trigger immediate damage. |

## Implementation result

The canonical schema and semantic validator enforce the two axes, the shared rider slot, selector-specific targeting requirements, concrete discipline facts, and bounded universal mappings. Calculator and harness views remain deterministic projections from entity-owned mechanics. Mechanical ambiguities and simplifications remain follow-up work under #135; this inventory authorizes no playable changes.

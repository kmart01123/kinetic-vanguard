# Neutral mechanical primitives design

## Decision

Kinetic Vanguard will transition machine-consumed ability mechanics to neutral, per-entity structured primitives in `KineticVanguard.yaml`. The project will not promote control-harness terminology wholesale into the rules authority.

The target removes the present three-way representation of the same facts:

1. authored player-facing entity content;
2. Calculator-specific damage, save, delivery, and metric rows;
3. harness-specific damage, targeting, and control rows.

Structured mechanics will become canonical for facts consumed by code. Authored content will remain canonical for complete player-facing wording and procedures that are not machine-modeled. Semantic validation must keep the two surfaces consistent. Generated prose is not a goal.

This document is a behavior-preserving architecture decision for issue [#132](https://github.com/kmart01123/kinetic-vanguard/issues/132). It does not authorize balance changes or reinterpret existing rules.

## Field audit

The exhaustive machine-readable audit is [mechanical-field-dispositions.json](../policy/mechanical-field-dispositions.json). Every currently populated field under `calculator.features` and `calculator.harness_mechanics.feature_rules` has one disposition:

- **Promote:** the field already expresses a neutral rules fact.
- **Generalize:** preserve the fact under a neutral name or structure.
- **Derive:** stop authoring the duplicate and calculate it from entity metadata or structured mechanics.
- **Benchmark-only:** keep the value outside canonical mechanics.

### Promote or generalize into canonical mechanics

- exact activation and rider declaration/resolution timing;
- target selectors, roles, eligibility restrictions, and cardinality formulas;
- area geometry, origin, occupancy, and recurring triggers;
- damage types, formulas, target roles, and Resistance handling;
- saving-throw ability and success/failure branches;
- conditions, forced movement, Speed changes, reaction denial, roll modifiers, and durations;
- repeat saves, repeat-save roll mode, and effect dependencies;
- Kinetic Mastery replacement behavior;
- resource, movement, sensing, mitigation, and other values currently exposed as Calculator metrics.

### Derive rather than author twice

- per-row `entity_id` when mechanics are colocated with the entity;
- discipline applicability when it follows the entity's canonical rules area;
- `hit_gated` from rider delivery;
- `application` from ordered saving-throw branches;
- Calculator labels from typed effects and the approved UI-text registry;
- persistent-zone booleans from the area's duration and event triggers.

### Keep outside canonical mechanics

- `cluster_remainder`, which is a benchmark occupancy assumption rather than a player targeting rule;
- retry recipes, exposure windows, and planner state;
- Control Unit pricing and normalization;
- effectiveness and roster-coverage classifications;
- comparator, target-profile, and benchmark-horizon policy.

The canonical area definition supplies what an ability does. The harness separately decides how many benchmark creatures occupy that area and how long the configured scenario observes it.

## Production source shape

Each mechanically modeled entity receives `mechanics.surfaces`. A surface is one independently activated or continuously applied rules lifecycle. Most abilities have one `main` surface; Empathic Sense demonstrates why the uniform collection is useful by having `passive` and `active_scan` surfaces.

```yaml
mechanics:
  surfaces:
    - id: main
      delivery:
        kind: rider
        declaration: before_attack_roll
        resolution: manifested_strike_hit
      tiers:
        - tier: 0
          targeting: ...
          steps: ...
```

### Delivery

The initial delivery vocabulary is:

- `rider`: declared before a Manifested Strike attack roll and resolved on that strike's hit;
- `standalone`: retains an explicit `action`, `bonus_action`, or `reaction` activation;
- `passive`: continuously modifies another canonical value or rule.

There is no composite-rider delivery. An `area_rider` is represented by `delivery.kind: rider` plus area targeting. “Area rider” remains a useful inventory name, not a separate declaration lifecycle.

The existing one-rider-per-swing rule is a shared Manifested Strike constraint and must be validated across all surfaces with `delivery.kind: rider`. Kinetic Mastery remains a separate strike property rather than consuming the rider allowance.

### Targeting

The production vocabulary includes these neutral selectors:

- `self`;
- `struck_target`;
- `additional_creatures` anchored to another selector, with fixed or Proficiency Bonus cardinality and a distance limit;
- `creatures_in_area`, with role refinement for the struck/primary creature and other/secondary creatures;
- `area`, with shape, origin, dimensions, placement range, and persistence;
- `eligible_creatures_in_range` for Active Scan.

Target roles are selectors, not benchmark roles. Benchmark grouping such as “cluster remainder” is derived later.

### Values

The production model uses bounded typed formulas rather than a general expression language:

- fixed integer;
- dice;
- Manifested Strike dice;
- Psionic Ability modifier with an integer multiplier;
- Proficiency Bonus with an integer multiplier;
- fixed plus a bounded canonical component;
- floor of a bounded canonical component divided by a fixed divisor.

Units remain explicit where relevant. New formula kinds require a real canonical feature need; consumers must not accept arbitrary expressions.

### Ordered steps and branches

A tier contains ordered steps. The step vocabulary is deliberately bounded:

- `damage`;
- `saving_throw`, containing ordered `failure` and `success` branches;
- `condition`;
- `speed_modifier` or `speed_zero`;
- `forced_movement`;
- `reaction_denial`;
- `skill_modifier`;
- `sense_snapshot`;
- `create_area` and an area's event-triggered steps;
- `difficult_terrain`;
- `movement_mode_denial`;
- `uses` for a rest-restored activation limit.

Each effect carries its target selector and duration when they are not inherited from the containing branch. Replacement is explicit through a stable step identifier; it is not inferred from prose or effect severity.

Harness summary labels such as `on_reach` and `application: failed_save` disappear from source mechanics. Ordered placement supplies unconditional effects, while placement inside a saving throw's `failure` branch supplies the failed-save gate.

## Detailed example: Glacial Spike

The following is the production source shape introduced by authority schema 2.5.0:

```yaml
mechanics:
  surfaces:
    - id: main
      delivery:
        kind: rider
        declaration: before_attack_roll
        resolution: manifested_strike_hit
      interactions:
        kinetic_mastery: replace
      targeting:
        kind: struck_target
      tiers:
        - tier: 0
          steps:
            - id: rider_damage
              kind: damage
              damage_type: discipline
              value: {kind: fixed, value: 2}
            - id: speed_effect
              kind: speed_modifier
              feet: -10
              duration: until_end_next_turn
        - tier: 1
          steps:
            - id: rider_damage
              kind: damage
              damage_type: discipline
              value: {kind: fixed, value: 2}
            - id: speed_effect
              kind: speed_modifier
              feet: -10
              duration: until_end_next_turn
            - kind: saving_throw
              ability: constitution
              failure:
                - kind: speed_zero
                  duration: until_end_next_turn
                  replaces: speed_effect
        - tier: 2
          steps:
            - id: rider_damage
              kind: damage
              damage_type: discipline
              value: {kind: fixed, value: 2}
            - id: speed_effect
              kind: speed_modifier
              feet: -10
              duration: until_end_next_turn
            - kind: saving_throw
              ability: constitution
              failure:
                - kind: condition
                  condition: restrained
                  duration: until_end_next_turn
                  replaces: speed_effect
```

This single structure can derive the current Calculator damage/save rows and the current harness control tiers without treating either consumer's shape as canonical.

## Sentinel proof

| Sentinel | Required primitive coverage | Result |
|---|---|---|
| `ember_bolt` | Rider delivery, struck target, unconditional fixed damage, three full tiers | Fits without a feature-specific primitive. |
| `glacial_spike` | Rider delivery, Mastery replacement, ordered damage and Speed effects, save branch, explicit replacement, condition duration | Fits the proposed ordered-step model. |
| `static_discharge` | Rider delivery, primary plus formula-sized additional-target selector, per-target independent save, damage-immunity-independent save resolution | Fits; the last qualification remains an explicit save-step property rather than harness policy. |
| `explosion_implosion` | Rider delivery, hit-centered Sphere, per-creature save, primary/secondary selectors, mode-selected forced-movement direction, blocked-space procedure | Core resolution fits; blocked-space procedure remains authored content until a consumer demonstrates a need to model collision paths. |
| `frozen_ground` | Standalone Action, persistent Cylinder, Concentration, difficult terrain, entry/start triggers, save branch, tier replacement | Fits with area lifecycle and event-triggered steps. |
| `common_empathic_sense` | Passive value modifier plus limited Bonus Action scan, formula-based uses, eligible-creature sensing, snapshot output | Fits through two surfaces; excluded-information prose remains authored content because no current consumer calculates it. |

No sentinel requires a composite rider or a generic opaque “custom effect” primitive. The two retained prose procedures—Explosion/Implosion collision ordering and Active Scan's information exclusions—do not currently drive Calculator or harness behavior and therefore do not justify expanding the machine language.

## Migration sequence

The schema 2.5.0 migration completes the first five steps:

1. **Complete:** add schema/types for `mechanics.surfaces` and the bounded production vocabulary.
2. **Complete:** add the six sentinel mechanics blocks beside their player-facing content.
3. **Complete:** prove exact compatibility with the prior Calculator/harness contracts through locked projection snapshots.
4. **Complete:** replace the sentinel Calculator and harness mechanical rows with ordered `derived_from: entity_mechanics` references; the canonical loader materializes the unchanged consumer contracts.
5. **Complete:** migrate every remaining Calculator/harness ability, expanding primitives only for demonstrated needs. All 30 Calculator rows and all 27 harness feature rules are now ordered derivation references.
6. Change consumers that benefit from richer semantics to read neutral mechanics directly.
7. Remove the Calculator and harness projection registries after complete coverage, if their ordering and membership are derived elsewhere.
8. Remove the temporary legacy-equivalence layer and advance the projection contract as required.

Authority schema 2.5.0 is additive and does not change playable rules, so `rules_version` remains 14.3.0. The harness projection remains 1.2.0 because its emitted contract and values are unchanged. Utility abilities with no Calculator or harness consumer remain fully authoritative in player-facing content; the migration does not invent benchmark data for them.

At every step, canonical rules wording and numerical outcomes remain unchanged. Full damage/control benchmark regeneration is required only if mechanics, methodology, comparator data, roster data, or evaluator behavior changes; structural equivalence should be established with focused sentinel and projection tests first.

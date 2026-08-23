# Kinetic Vanguard Control Benchmark Detail

This is the exhaustive public companion to the README control benchmark. Control Value measures the mechanical consequence of the selected package; Control Reliability measures initial establishment/delivery of that same CU-selected package. Damage analysis is outside this page's scope.

## Current Kinetic Vanguard results

### Kinetic Vanguard mean Control Value

This table shows the raw Kinetic Vanguard equal-weight roster mean for the packages selected by Control Value.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | 0.943 CU | 0.000 CU | 0.324 CU | 0.144 CU |
| 11 | 1.074 CU | 0.000 CU | 1.407 CU | 0.311 CU |
| 15 | 1.064 CU | 0.524 CU | 1.462 CU | 0.473 CU |
| 20 | 1.204 CU | 0.555 CU | 1.672 CU | 0.469 CU |

### Kinetic Vanguard mean Reliability

This table shows the raw initial whole-package establishment/delivery probability for those same CU-selected winners.

| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |
|---|---|---|---|---|
| 7 | 96.23% | 0.00% | 92.85% | 96.23% |
| 11 | 91.04% | 0.00% | 78.52% | 83.75% |
| 15 | 83.05% | 80.68% | 81.47% | 72.56% |
| 20 | 99.97% | 85.45% | 87.35% | 57.19% |

## Exact-form catalog and effective coverage

### Kinetic Vanguard control catalog

This authority-driven catalog is a decomposition view: Kinetic Mastery and every exact rider tier are separate control sources. Each Kinetic Mastery row reports only that Mastery's control; each rider/tier/role row reports only control produced by that exact rider form. Mastery that may legally coexist during actual play is excluded from rider CU and delivery. The headline discipline benchmark above remains a separate whole-legal-package view.

Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20. Each column uses the complete maintained roster for that level.

**Cell format:** `CU · delivery · effective/roster`

Example: `0.143 CU · 95.00% · 12/12` means `0.143 CU` average Control Value and `95.00%` average initial control-delivery probability across the full benchmark roster at that fighter level. `effective/roster` is **targets against which at least one modeled control consequence from that exact source survives maintained structural restrictions, immunities, and effect dependencies / total roster targets**.

`12/12 effective` does **not** mean 100% delivery or that every consequence works; it means every roster target can receive at least one modeled consequence from that exact source. `10/11 effective` means one of the 11 creatures cannot receive any modeled control from that source. A target can remain counted in `12/12 effective` while appearing in a partial-effect exception because another modeled consequence survives. Coverage is not a save result, hit count, successful application count, CU threshold, pricing state, or delivery probability.

`CU (partial)` means the form is partially priced: retained priced and retained context-required or unsupported consequences coexist. Suppressed duplicate or weaker primitives do not create that label. `Unpriced` retains measurable delivery and effectiveness coverage without reporting zero CU. `No modeled control` means `0.000 CU` and no control delivery (`—`). `N/A` means the exact form is unavailable at that level.

Full denominator and state methodology: [Benchmark roster, effectiveness, and coverage](#benchmark-roster-effectiveness-and-coverage)

#### Cryokinesis

| Rider / form | Delivery recipe | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|---|
| Kinetic Mastery | Kinetic Mastery — ordinary Attack-action at least one hit | 0.076 CU · 96.23% · 12/12 | 0.060 CU · 99.51% · 12/12 | 0.051 CU · 99.50% · 11/11 | 0.041 CU · 99.84% · 12/12 |
| Glacial Spike — T0 | KV Attack-action retry — hit | 0.076 CU · 96.23% · 12/12 | 0.060 CU · 99.51% · 12/12 | 0.051 CU · 99.50% · 11/11 | 0.041 CU · 99.84% · 12/12 |
| Glacial Spike — T1 | KV Attack-action retry — hit; failed Constitution save gates additional control | 0.226 CU · 96.23% · 12/12 | 0.226 CU · 99.51% · 12/12 | 0.216 CU · 99.50% · 11/11 | 0.232 CU · 99.84% · 12/12 |
| Glacial Spike — T2 | KV Attack-action retry — hit; failed Constitution save gates additional control | N/A | 0.397 CU · 83.75% · 12/12 | 0.422 CU · 84.09% · 11/11 | 0.374 CU · 82.08% · 12/12 |
| Snow Chains — T0 | KV Attack-action retry — hit; failed Constitution save gates additional control | 0.807 CU · 96.23% · 12/12 | 0.836 CU · 99.51% · 12/12 | 0.861 CU · 99.50% · 11/11 | 0.897 CU · 99.84% · 12/12 |
| Snow Chains — T1 | KV Attack-action retry — hit; failed Constitution save gates additional control | 0.943 CU · 96.23% · 12/12 | 0.975 CU · 99.51% · 12/12 | 0.993 CU · 99.50% · 11/11 | 1.045 CU · 99.84% · 12/12 |
| Snow Chains — T2 | KV Attack-action retry — hit; failed Constitution save gates additional control | N/A | 1.033 CU (partial) · 83.75% · 12/12 | 1.025 CU (partial) · 84.09% · 11/11 | 0.964 CU (partial) · 82.08% · 12/12 |
| Frozen Ground — T0 | Single activation — failed Constitution save | N/A | 0.125 CU · 41.54% · 12/12 | 0.124 CU · 41.23% · 11/11 | 0.119 CU · 39.52% · 12/12 |
| Frozen Ground — T1 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Frozen Ground — T2 | Single activation — failed Constitution save | N/A | 0.435 CU · 37.79% · 11/12 | 0.474 CU · 41.23% · 11/11 | 0.440 CU · 38.27% · 11/12 |
| Arctic Tempest — T0 | Single activation — failed Constitution save | N/A | N/A | 0.474 CU · 41.23% · 11/11 | 0.440 CU · 38.27% · 11/12 |
| Arctic Tempest — T1 | — | N/A | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Arctic Tempest — T2 | Single activation — failed Constitution save | N/A | N/A | 0.928 CU (partial) · 41.23% · 11/11 | 0.889 CU (partial) · 39.52% · 12/12 |
| Absolute Zero — T0 | Single activation — failed Constitution save | N/A | N/A | N/A | 0.119 CU · 39.52% · 12/12 |
| Absolute Zero — T1 | Single activation — failed Constitution save | N/A | N/A | N/A | 0.444 CU · 39.52% · 12/12 |
| Absolute Zero — T2 | Single activation — automatic control; failed Constitution save gates additional control | N/A | N/A | N/A | 1.189 CU (partial) · 100.00% · 12/12 |

#### Pyrokinesis

| Rider / form | Delivery recipe | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|---|
| Kinetic Mastery | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Ember Bolt — T0 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Ember Bolt — T1 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Ember Bolt — T2 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Thermal Fracture — T0 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Thermal Fracture — T1 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Thermal Fracture — T2 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Cinder Lance — T0 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Cinder Lance — T1 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Cinder Lance — T2 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Flare — T0 | KV Attack-action retry — hit × failed Dexterity save | N/A | N/A | 0.524 CU (partial) · 80.68% · 11/11 | 0.555 CU (partial) · 85.45% · 12/12 |
| Flare — T1 | KV Attack-action retry — hit × failed Dexterity save | N/A | N/A | 0.524 CU (partial) · 80.68% · 11/11 | 0.555 CU (partial) · 85.45% · 12/12 |
| Flare — T2 | KV Attack-action retry — hit × failed Dexterity save | N/A | N/A | 0.300 CU (partial) · 46.16% · 11/11 | 0.266 CU (partial) · 40.91% · 12/12 |
| Furnace Strike — T0 | — | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Furnace Strike — T1 | — | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Furnace Strike — T2 | — | N/A | N/A | N/A | 0.000 CU · — · no modeled control |

#### Psychokinesis

| Rider / form | Delivery recipe | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|---|
| Kinetic Mastery | Kinetic Mastery — ordinary Attack-action at least one hit | 0.297 CU · 87.92% · 11/12 | 0.375 CU · 74.61% · 9/12 | 0.191 CU · 36.25% · 4/11 | 0.163 CU · 24.97% · 3/12 |
| Telekinetic Shove — T0 | KV Attack-action retry — hit × failed Strength save | 0.167 CU · 64.53% · 12/12 | 0.220 CU · 70.93% · 12/12 | 0.205 CU · 68.21% · 11/11 | 0.268 CU · 73.69% · 12/12 |
| Telekinetic Shove — T1 | KV Attack-action retry — hit × failed Strength save | 0.250 CU · 64.53% · 12/12 | 0.330 CU · 70.93% · 12/12 | 0.308 CU · 68.21% · 11/11 | 0.403 CU · 73.69% · 12/12 |
| Telekinetic Shove — T2 | KV Attack-action retry — hit × failed Strength save | N/A | 0.257 CU · 36.65% · 12/12 | 0.239 CU · 34.19% · 11/11 | 0.235 CU · 33.54% · 12/12 |
| Vectored Thrust — T0 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Vectored Thrust — T1 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Vectored Thrust — T2 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Explosion/Implosion — T0 — primary | KV Attack-action retry — hit × failed Strength save | N/A | 0.733 CU · 63.77% · 11/12 | 0.784 CU · 68.21% · 11/11 | 0.831 CU · 72.22% · 11/12 |
| Explosion/Implosion — T0 — secondary | KV Attack-action retry — hit × failed Strength save | N/A | 1.063 CU · 70.93% · 12/12 | 1.092 CU · 68.21% · 11/11 | 1.233 CU · 73.69% · 12/12 |
| Explosion/Implosion — T1 — primary | KV Attack-action retry — hit × failed Strength save | N/A | 0.733 CU · 63.77% · 11/12 | 0.784 CU · 68.21% · 11/11 | 0.831 CU · 72.22% · 11/12 |
| Explosion/Implosion — T1 — secondary | KV Attack-action retry — hit × failed Strength save | N/A | 1.393 CU · 70.93% · 12/12 | 1.400 CU · 68.21% · 11/11 | 1.636 CU · 73.69% · 12/12 |
| Explosion/Implosion — T2 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Telekinetic Slam — T0 | Single activation — failed Strength save | N/A | N/A | 0.082 CU · 40.95% · 11/11 | 0.083 CU · 41.25% · 12/12 |
| Telekinetic Slam — T1 | Single activation — failed Strength save | N/A | N/A | 0.164 CU · 40.95% · 11/11 | 0.165 CU · 41.25% · 12/12 |
| Telekinetic Slam — T2 | Single activation — automatic control; failed Strength save gates additional control | N/A | N/A | 0.487 CU · 100.00% · 11/11 | 0.489 CU · 100.00% · 12/12 |
| Mass Levitation — T0 | Single activation — failed Strength save | N/A | N/A | N/A | 0.138 CU (partial) · 11.67% · 3/12 |
| Mass Levitation — T1 | Single activation — failed Strength save | N/A | N/A | N/A | 0.180 CU (partial) · 11.67% · 3/12 |
| Mass Levitation — T2 | — | N/A | N/A | N/A | 0.000 CU · — · no modeled control |

#### Electrokinesis

| Rider / form | Delivery recipe | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|---|
| Kinetic Mastery | Kinetic Mastery — ordinary Attack-action at least one hit | 0.144 CU · 96.23% · 12/12 | 0.149 CU · 99.51% · 12/12 | 0.149 CU · 99.50% · 11/11 | 0.150 CU · 99.84% · 12/12 |
| Static Discharge — T0 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Static Discharge — T1 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Static Discharge — T2 | KV Attack-action retry — hit × failed Charisma save | N/A | 0.083 CU · 41.30% · 12/12 | 0.084 CU · 41.96% · 11/11 | 0.086 CU · 42.82% · 12/12 |
| Branching Bolt — T0 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Branching Bolt — T1 | — | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Branching Bolt — T2 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Electron Burst — T0 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Electron Burst — T1 | — | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Electron Burst — T2 | KV Attack-action retry — hit × failed Charisma save | N/A | 0.248 CU · 41.30% · 12/12 | 0.252 CU · 41.96% · 11/11 | 0.257 CU · 42.82% · 12/12 |
| Forked Lightning — T0 | — | N/A | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Forked Lightning — T1 | — | N/A | N/A | 0.000 CU · — · no modeled control | 0.000 CU · — · no modeled control |
| Forked Lightning — T2 — primary | Single activation — failed Charisma save | N/A | N/A | 0.453 CU · 50.32% · 11/11 | 0.467 CU · 51.85% · 12/12 |
| Forked Lightning — T2 — secondary | Single activation — failed Charisma save | N/A | N/A | 0.302 CU · 50.32% · 11/11 | 0.311 CU · 51.85% · 12/12 |
| Ball Lightning — T0 | — | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Ball Lightning — T1 | — | N/A | N/A | N/A | 0.000 CU · — · no modeled control |
| Ball Lightning — T2 | Single activation — failed Charisma save | N/A | N/A | N/A | Unpriced · 51.85% delivery · 12/12 |

### Catalog delivery recipes

The generated `Delivery recipe` column is diagnostic metadata from each exact source's evaluator path. Its initial gate comes from the canonical control effects applicable to that exact target role: any `on_reach` consequence can establish initial control, while an optional `on_failed_save` gate identifies additional control. It never changes scoring or selection, contains no per-target percentages, and remains present for deliverable `Unpriced` forms. Structural restrictions and effect immunities change target effectiveness, not the underlying source recipe. Unknown recipe IDs fail publication closed.

| Recipe family | Reader-facing format |
|---|---|
| `mastery_attack_action_hit_retry` | Kinetic Mastery — ordinary Attack-action at least one hit |
| `kv_attack_action_hit_retry` | KV Attack-action retry — hit |
| `kv_attack_action_hit_retry` + `additional_control_gate=failed_save` | KV Attack-action retry — hit; failed Constitution save gates additional control |
| `kv_attack_action_hit_failed_save_retry` | KV Attack-action retry — hit × failed Constitution save |
| `single_activation_hit` | Single activation — hit |
| `single_activation_hit` + `additional_control_gate=failed_save` | Single activation — hit; failed Constitution save gates additional control |
| `single_activation_failed_save` | Single activation — failed Constitution save |
| `single_activation_hit_failed_save` | Single activation — hit × failed Constitution save |
| `single_activation_automatic` | Single activation — automatic/no-save modeled control |
| `single_activation_automatic` + `additional_control_gate=failed_save` | Single activation — automatic control; failed Constitution save gates additional control |
| `no_modeled_control` | — |

### Control coverage exceptions

These generated rows expose structural exclusions, complete effect nullification, and partial losses from the same evidence used by the catalog.

| Discipline / exact form | Level | Affected target(s) | Status | Reason |
|---|---|---|---|---|
| Cryokinesis — Glacial Spike — T2 | Fighter 11 | Guardian Naga | Partially effective | immune to Restrained; Speed reduction remains effective |
| Cryokinesis — Glacial Spike — T2 | Fighter 20 | Kraken | Partially effective | immune to Restrained; Speed reduction remains effective |
| Cryokinesis — Snow Chains — T0 | Fighter 7 | Air Elemental | Partially effective | immune to Restrained; Speed 0 remains effective |
| Cryokinesis — Snow Chains — T0 | Fighter 11 | Guardian Naga | Partially effective | immune to Restrained; Speed 0 remains effective |
| Cryokinesis — Snow Chains — T0 | Fighter 20 | Kraken | Partially effective | immune to Restrained; Speed 0 remains effective |
| Cryokinesis — Snow Chains — T1 | Fighter 7 | Air Elemental | Partially effective | immune to Restrained; Speed 0 and Reaction denial remain effective |
| Cryokinesis — Snow Chains — T1 | Fighter 11 | Guardian Naga | Partially effective | immune to Restrained; Speed 0 and Reaction denial remain effective |
| Cryokinesis — Snow Chains — T1 | Fighter 20 | Kraken | Partially effective | immune to Restrained; Speed 0 and Reaction denial remain effective |
| Cryokinesis — Frozen Ground — T2 | Fighter 11 | Guardian Naga | Ineffective | immune to Restrained |
| Cryokinesis — Frozen Ground — T2 | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Cryokinesis — Arctic Tempest — T0 | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Cryokinesis — Absolute Zero — T1 | Fighter 20 | Kraken | Partially effective | immune to Restrained; Speed 0 remains effective |
| Psychokinesis — Kinetic Mastery | Fighter 7 | Giant Ape | Ineffective | exceeds maximum size Large |
| Psychokinesis — Kinetic Mastery | Fighter 11 | Remorhaz, Storm Giant, Adult White Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Kinetic Mastery | Fighter 15 | Adult Black Dragon, Adult Blue Dragon, Adult Bronze Dragon, Adult Copper Dragon, Adult Green Dragon, Purple Worm, Adult Silver Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Kinetic Mastery | Fighter 20 | Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Ancient Silver Dragon, Ancient White Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Explosion/Implosion — T0 — primary | Fighter 11 | Guardian Naga | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T0 — primary | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T0 — secondary | Fighter 11 | Guardian Naga | Partially effective | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Explosion/Implosion — T0 — secondary | Fighter 20 | Kraken | Partially effective | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Explosion/Implosion — T1 — primary | Fighter 11 | Guardian Naga | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T1 — primary | Fighter 20 | Kraken | Ineffective | immune to Restrained |
| Psychokinesis — Explosion/Implosion — T1 — secondary | Fighter 11 | Guardian Naga | Partially effective | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Explosion/Implosion — T1 — secondary | Fighter 20 | Kraken | Partially effective | immune to Restrained; Forced movement remains effective |
| Psychokinesis — Mass Levitation — T0 | Fighter 20 | Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Ancient Silver Dragon, Ancient White Dragon | Ineffective | exceeds maximum size Large |
| Psychokinesis — Mass Levitation — T1 | Fighter 20 | Balor, Ancient Blue Dragon, Ancient Brass Dragon, Ancient Copper Dragon, Ancient Gold Dragon, Ancient Green Dragon, Kraken, Ancient Silver Dragon, Ancient White Dragon | Ineffective | exceeds maximum size Large |

### Benchmark roster, effectiveness, and coverage

Every Fighter level uses the complete maintained headline roster for that level. Structural legality remains an internal prerequisite evaluated by `target_is_eligible()` from maintained maximum-size and required-creature-type restrictions. Public `effective/roster` coverage asks a different question: for how many roster targets does at least one modeled control consequence from this exact Mastery or rider survive structural restrictions, maintained immunities, and effect dependencies?

A structural restriction makes a target ineffective for that exact source. Maintained immunity can instead remove one or more consequences after the structural check. If another consequence survives, the target is partially effective and remains in the coverage numerator; if every modeled consequence is nullified, the target is ineffective. Thus `12/12 effective` does not mean 100% delivery, 12 successful saves or attacks, 12 successful applications, or that every consequence works against every target.

Effective coverage is descriptive metadata, not a success roll, CU threshold, pricing state, delivery probability, or alternate averaging population. An ineffective target remains in the aggregate denominator at its existing `CU = 0` and `delivery = 0%` contribution. A partially effective target contributes the CU and delivery of the consequences that survive.

`mean CU = sum(per-target CU across the complete roster) / total roster targets`

`mean delivery = sum(per-target initial-delivery probability across the complete roster) / total roster targets`

Do not divide only by effective targets. Effective-only averaging would hide practical restrictions and could make a narrowly applicable control look stronger or more reliable than it is across the maintained benchmark roster.

**Instructional example (not a published scenario):** if a form has 80% delivery against 9 effective targets and 3 ineffective targets contribute 0%, its full-roster delivery mean is `(9 × 0.80 + 3 × 0) / 12 = 0.60 = 60%`. The effective-only 80% is not the roster-wide result.

`Priced` and `CU (partial)` use the complete-roster denominator above. `Unpriced` can still be effectively covered and show independently measurable delivery, but its CU field remains `Unpriced`, not zero. `No modeled control` is `0.000 CU` because that catalog source declares no modeled control, with delivery `—` because no control establishment is measured. `N/A` means the exact form is unavailable at that Fighter level and does not participate in that level's aggregate.

## Comparator reference scale

These raw rows provide a familiar Fighter comparison scale beside the exact-form Kinetic Vanguard catalog. They are reference measurements, not Kinetic Vanguard rules.

**Cell format:** `CU · initial delivery · effective/roster`

`CU` is complete-roster mean Control Value. `Initial delivery` is the complete-roster mean initial establishment probability after maintained legal retries and primer logic. `Effective/roster` counts targets for which at least one modeled control consequence survives structural restrictions, maintained immunities, and effect dependencies. Zero and nullified targets remain in both means; coverage is not derived from CU, pricing state, or delivery probability.

### Battle Master reference maneuvers

| Maneuver | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|
| Menacing Attack | 0.000 CU · 68.71% · 12/12 | 0.000 CU · 55.72% · 9/12 | 0.000 CU · 62.57% · 9/11 | 0.000 CU · 50.60% · 8/12 |
| Pushing Attack | 0.222 CU · 58.28% · 11/12 | 0.295 CU · 61.00% · 9/12 | 0.121 CU · 26.13% · 4/11 | 0.137 CU · 21.93% · 3/12 |
| Trip Attack | 0.078 CU · 52.14% · 10/12 | 0.092 CU · 61.00% · 9/12 | 0.039 CU · 26.13% · 4/11 | 0.033 CU · 21.93% · 3/12 |

Goading Attack and Disarming Attack remain maintained context-required diagnostics; they are not scalar reference rows.

Menacing Attack can have nonzero initial delivery with `0.000 CU`: its Frightened consequences remain context-required without source line-of-sight, a relevant ability check, and encounter-geometry assumptions.

### Eldritch Knight reference spell families

**Best maintained legal setup for each spell family per target.** Candidates are grouped by stable `spell_id`; the exact selector orders them by highest CU, then highest initial Reliability on an exact CU tie, then lexicographically ascending stable Scenario ID on an exact tie. Different targets may select different setups.

| Spell family | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |
|---|---|---|---|---|
| Ray of Frost | 0.046 CU · 57.92% · 12/12 | 0.033 CU · 53.75% · 12/12 | 0.033 CU · 64.09% · 11/11 | 0.024 CU · 57.08% · 12/12 |
| Thunderwave | 0.104 CU · 52.02% · 12/12 | 0.118 CU · 59.20% · 12/12 | 0.139 CU · 69.44% · 11/11 | 0.138 CU · 69.21% · 12/12 |
| Blindness/Deafness — Blinded mode | 0.360 CU · 52.02% · 12/12 | 0.352 CU · 59.20% · 12/12 | 0.479 CU · 69.44% · 11/11 | 0.454 CU · 69.21% · 12/12 |
| Hold Person | 0.265 CU · 12.55% · 3/12 | 0.051 CU · 3.30% · 1/12 | 0.000 CU · 0.00% · 0/11 | 0.000 CU · 0.00% · 0/12 |
| Web | 1.201 CU · 48.55% · 12/12 | 1.479 CU · 61.73% · 12/12 | 2.189 CU · 80.32% · 11/11 | 1.915 CU · 71.73% · 12/12 |
| Hypnotic Pattern | N/A | N/A | 2.813 CU · 62.50% · 9/11 | 2.421 CU · 53.80% · 9/12 |
| Slow | N/A | N/A | 0.469 CU · 69.49% · 11/11 | 0.432 CU · 68.90% · 12/12 |

`N/A` means the family is not spell-accessible at that Fighter level. When a family is available, target-specific restrictions such as Hold Person's Humanoid requirement contribute zero and remain in the complete-roster denominator.

### How to interpret comparator references

These rows do not mean Kinetic Vanguard should equal each reference, that every source is equally severe or broadly applicable, that higher Reliability implies greater severity, or that higher CU implies higher delivery. Control Value and Reliability retain the separate meanings documented below.

Creature and roster facts come from SRD 5.2.1. Battle Master and Eldritch Knight mechanics come from reviewed, independently expressed current-PHB-derived analytical abstractions in `harness/comparators/fighter-subclasses.json`. This unofficial comparative scale is not Wizards-endorsed project content, is not Kinetic Vanguard rules, and does not assert that the Eldritch Knight control inventory is SRD-only.

## Control Reliability methodology

### What Reliability measures

`Whole-package control stick %` is the probability that the exact published control source or package establishes at least one modeled control consequence in its legal initial delivery window, after all maintained legal retries and resource constraints are applied. It is initial establishment/delivery probability: it is not a severity score, Control Value, effective coverage, or the probability of remaining controlled for all three benchmark rounds.

The headline discipline benchmark reports the delivery of the same full legal package selected by Control Value. It does not run a separate Reliability winner-selection pass. Persistence is a separate diagnostic and contributes to active exposure and Control Value where the maintained scenario timing calls for it.

### One-attempt probability grammar

**Hit-gated, no save:** `P(control) = P(hit)`.

The maintained attack helper enumerates d20 results exactly. A natural 1 misses, a natural 20 hits as a critical, and every other roll hits when `natural roll + attack bonus >= AC`. `P(hit)` includes ordinary hits plus critical hits. Where a source contract actually grants attack Advantage, the helper enumerates both d20s exactly and keeps the higher result; this publication does not invent Advantage for a control source.

**Save-only:** `P(control) = P(failed save) = 1 - P(successful save)`.

A save succeeds when `d20 + maintained save bonus >= DC`. Saving throws do not use the attack-roll natural-1/natural-20 automatic miss/critical rules. Magic Resistance supplies save Advantage only where the maintained comparator/source contract says it applies. The save helper enumerates Advantage and Disadvantage exactly and cancels them when both apply. Finite penalties such as `d20 - 1d4` are enumerated over every die result, never replaced by an average penalty.

**Hit plus failed save:** for the maintained independent gates, `P(control) = P(hit) × P(failed save)`.

**Automatic / no-save modeled control:** application uses the maintained automatic or reach probability supplied by the evaluator. “Automatic” does not mean universally effective: size/type restrictions, immunities, and effect dependencies are evaluated separately.

### Attack-action retries

For `n` identical unconstrained attempts with one-attempt success probability `p`, `P(at least one success) = 1 - (1 - p)^n`. The maintained generic helper returns this special case when no state-changing legality function is supplied.

That closed form is not the general Kinetic Vanguard or Battle Master rule when resources or legality change. Their recursive shape is `R(attacks remaining, state) = max over legal next states [p + (1 - p) × R(attacks remaining - 1, next state)]`, with terminal `0` when no attacks or legal attempts remain. The exact legal resource state is carried forward.

Every headline control retry window in this section is one ordinary Attack action. Action Surge is excluded.

### Kinetic Vanguard retry resources

A repeatable on-hit rider can be declared again on a later Manifested Strike within the same ordinary Attack action. At each opportunity, the evaluator carries attacks remaining, Psi spent, Blood Tax spent, Tier-2 declarations, Overload Mastery uses remaining, and the selected raw/reduced payment mode. A declaration is legal only if its Psi cost fits the current Psi pool, its canonical Blood Tax payment fits the benchmark budget, the Tier-2-per-Attack-action limit is respected, and the current Overload Mastery payment state offers that option. The recursion then chooses the legal state path with the greatest at-least-one-establishment probability.

The canonical payment options preserve the raw Blood Tax path and, while the maintained Overload Mastery use is available, the exact reduced-tax path. Once a path establishes its payment mode, later declarations carry that mode and remaining-use state forward; the renderer does not approximate or rebuild it.

The table is generated from canonical authority, Fighter progression, and the benchmark profile used by the evaluator. Benchmark HP and its 25% Blood Tax budget are analytical inputs, not subclass rules. `T0/T1/T2 tax` lists the canonical raw Blood Tax before any legal Overload Mastery reduction.

| Fighter level | Attacks / Attack action | Psi pool | Benchmark HP | Blood Tax budget | T0/T1/T2 tax | Overload Mastery availability/uses | Tier-2 declaration limit |
|---|---|---|---|---|---|---|---|
| 7 | 2 | 7 | 67 | 16 | 0/3/6 | unavailable / 0 | 1 |
| 11 | 3 | 10 | 103 | 25 | 0/4/8 | unavailable / 0 | 1 |
| 15 | 3 | 13 | 139 | 34 | 0/5/10 | unavailable / 0 | 1 |
| 20 | 4 | 16 | 184 | 46 | 0/6/12 | available / 1 per rest | 1 |

### Kinetic Mastery retries

For an eligible current Kinetic Mastery, each qualifying Manifested Strike hit in one ordinary Attack action is an opportunity and there is no additional Mastery saving throw. With maintained ordinary attacks/action, `P(Mastery establishes) = 1 - (1 - P(hit))^attacks`. Action Surge is excluded. Mastery delivery and rider delivery remain separate catalog recipes.

### Headline package versus catalog delivery

The explanatory catalog decomposes each exact source: a Kinetic Mastery row shows Mastery delivery only, and a rider row shows rider delivery only. Mastery does not rescue a rider's recipe or target effectiveness. The headline discipline benchmark instead uses the selected full legal package, and its Reliability is the initial delivery probability of that same CU-selected package.

### Battle Master retry recursion

For attacks remaining `a`, superiority dice remaining `d`, hit probability `h`, and failed-save probability `f`, the maintained recursion is:

`R(a,d) = (1-h) × R(a-1,d) + h × [f + (1-f) × R(a-1,d-1)]`

The terminal value is zero when attacks or superiority dice are exhausted. A miss preserves the die; a hit consumes it; hit plus failed save succeeds; and a hit followed by a successful save can recurse when both attacks and dice remain. The headline Control Reliability window excludes Action Surge. The Battle Master reference table above uses this same recursion.

### Eldritch Knight spell attacks and saves

A spell attack uses its exact spell-attack hit probability. A save spell uses its exact failed-save probability. Headline Reliability credits one configured cast in the spell's delivery window, not repeated casting.

### Eldritch Strike primer

A legal prior ordinary Attack action establishes Eldritch Strike with `P(ES established) = 1 - (1 - P(weapon hit))^ordinary primer attacks`. The target spell's initial failure probability is the exact mixture `P(ES) × P(fail with maintained Disadvantage state) + (1 - P(ES)) × P(ordinary fail)`. The save helper preserves Magic Resistance and cancels Advantage against Disadvantage when both apply. Eldritch Strike is never credited below its configured minimum level.

### Mind Sliver primer

Only the approved cross-turn composition is modeled. Mind Sliver must first establish on its Intelligence save; if it does, the next qualifying save enumerates exact `d20 - 1d4` outcomes, with no average `-2.5` substitution. The composition is `P(initial target save fails) = P(Mind Sliver establishes) × P(penalized save fails) + P(Mind Sliver does not establish) × P(unpenalized composed save fails)`. If Eldritch Strike is also present, the finite penalty and probabilistic Disadvantage are combined exactly, including Magic Resistance cancellation. Same-Attack-action Mind Sliver sequencing is not modeled.

### Persistence is separate from delivery

Let initial delivery be `p` and the maintained repeat-save failure probability be `q`. For an effect whose timing supplies repeated survival checkpoints, the active probabilities can conceptually be `p`, `p × q`, and `p × q²` over the frozen three-round horizon. Only initial `p` is `Whole-package control stick %`.

The later terms affect active exposure, Control Value, and the `Still controlled after configured repeats %` persistence diagnostic; they do not redefine initial Reliability as `p × q²`. The evaluator uses each scenario's actual timing metadata rather than applying this pattern universally. Other maintained end or escape mechanisms can likewise change CU exposure without becoming part of initial Reliability.

### Worked Reliability examples

**Illustrative hit × save (not current target data):** `P(hit) = 0.70` and `P(failed save) = 0.60`, so `P(one-attempt control) = 0.70 × 0.60 = 0.42 = 42%`.

**Illustrative identical retries (not current target data):** with `p = 0.42` and `n = 3`, `P(at least one) = 1 - (1 - 0.42)^3 = 0.804888 = 80.49%`. Actual KV and Battle Master retries use exact state recursion when resources or legality change.

**Illustrative persistence (not current target data):** with initial `p = 0.42` and repeat-save failure `q = 0.60`, the active windows are `p = 0.42 (42.00%)`, `p × q = 0.252 (25.20%)`, and `p × q² = 0.1512 (15.12%)`. Only the first `p` is headline Reliability.

## Control Value methodology

### How Control Value is calculated

1.0 CU = denial of one target's normal Action + Bonus Action for one scored target-turn window.

The calculation pipeline is: condition/outcome → mechanical primitives → expected delivery/persistence/opportunities → overlap normalization → primitive CU contributions → total Control Value.

General arithmetic: `primitive contribution = frozen weight × expected exposure`.

Expected exposure is where delivery probability, persistence, placed attack, save, and reaction opportunities, and repeatable instantaneous occurrences enter the calculation. Overlap normalization then prevents the same mechanical consequence from being counted twice.

#### Worked example: Sap-style next-attack Disadvantage

The maintained next-attack Disadvantage outcome resolves to `offensive_impairment_next_attack`, weighted at 0.15 CU per expected placed attack opportunity.

Illustrative arithmetic: `0.15 × 0.95 = 0.1425 CU`.

The 95% expected exposure is an instructional example, not a published target or roster result. Even at very high delivery, the effect remains low-Control-Value because it impairs only one attack. Repeated legal attack attempts can make this kind of rider highly reliable without making its consequence more severe; Sap is not assumed to be the selected package in every Electrokinesis matrix cell.

#### Worked example: Stunned

This is an **opportunity-normalized synthetic example**. It assumes 1.00 expected exposure independently on every displayed priced basis; it does not treat those different opportunity types as one shared target-turn window.

| Priced piece | Exposure basis | Nominal weight | Example exposure | Contribution |
|---|---|---|---|---|
| active-turn denial | `target_turn_window` | 1.00 CU | 1.00 | 1.00 CU |
| reaction denial | `reaction_window` | 0.20 CU | 1.00 | 0.20 CU |
| Strength save automatic failure | `save_opportunity` | 0.40 CU | 1.00 | 0.40 CU |
| Dexterity save automatic failure | `save_opportunity` | 0.40 CU | 1.00 | 0.40 CU |
| incoming attack Advantage | `incoming_attack_opportunity` | 0.25 CU | 1.00 | 0.25 CU |
| **Total** |  |  |  | **2.25 CU** |

Incapacitated supplies the active-turn and reaction pieces; Stunned adds the two save automatic failures and incoming attack Advantage. Stunned does **not** gain Speed 0. Concentration, speech, fall, and other context-sensitive consequences remain diagnostic rather than receiving invented headline CU. Real Stunned benchmark rows do **not** automatically equal 2.25 CU because target-turn, reaction, save, and incoming-attack opportunity counts and probabilities can differ.

### Control Unit primitive pricing rubric

This is the complete maintained scoring-rule inventory. Primitive basis and default pricing status come from the primitive catalog; nominal weights and transform IDs come from the frozen scoring config.

| Primitive | Exposure basis | Default pricing status | Nominal weight | Scoring rule |
|---|---|---|---|---|
| `active_turn_denial` | `target_turn_window` | `candidate` | 1.00 CU | `linear_expected_exposure` |
| `reaction_denial` | `reaction_window` | `candidate` | 0.20 CU | `linear_expected_exposure` |
| `offensive_impairment_next_attack` | `attack_opportunity` | `candidate` | 0.15 CU | `linear_expected_exposure` |
| `offensive_impairment_all_attacks` | `target_turn_window` | `candidate` | 0.40 CU | `linear_expected_exposure` |
| `mobility_loss_feet` | `target_turn_window` | `candidate` | 0.30 CU | `bounded_fraction_of_benchmark_locomotion` |
| `forced_displacement` | `instantaneous_occurrence` | `candidate` | 0.02 CU | `expected_displaced_feet` |
| `defensive_attack_advantage` | `incoming_attack_opportunity` | `candidate` | 0.25 CU | `linear_expected_exposure` |
| `save_disadvantage` | `save_opportunity` | `candidate` | 0.20 CU | `linear_expected_exposure` |
| `save_auto_failure` | `save_opportunity` | `candidate` | 0.40 CU | `linear_expected_exposure` |
| `specified_action_requirement` | `target_turn_window` | `candidate` | 0.75 CU | `linear_expected_exposure` |
| `action_bonus_exclusivity` | `target_turn_window` | `candidate` | 0.25 CU | `linear_expected_exposure` |
| `attack_action_cap` | `attack_opportunity` | `context_required` | 0.00 CU | `diagnostic_zero` |
| `bonus_action_denial` | `target_turn_window` | `candidate` | 0.25 CU | `linear_expected_exposure` |
| `turn_movement_denial` | `target_turn_window` | `candidate` | 0.30 CU | `linear_expected_exposure` |
| `flat_armor_class_penalty` | `incoming_attack_opportunity` | `candidate` | 0.05 CU | `points_times_placed_opportunities` |
| `flat_save_roll_penalty` | `save_opportunity` | `candidate` | 0.05 CU | `points_times_placed_opportunities` |
| `speed_multiplier` | `target_turn_window` | `candidate` | 0.30 CU | `remaining_speed_fraction` |
| `standing_movement_cost` | `target_turn_window` | `candidate` | 0.15 CU | `linear_expected_exposure` |
| `finite_next_save_roll_penalty` | `save_opportunity` | `context_required` | 0.00 CU | `diagnostic_zero` |

#### Maintained transform definitions

| Transform | Formula | Meaning |
|---|---|---|
| `linear_expected_exposure` | `CU = nominal weight × expected exposure` | Expected exposure is the placed probability/opportunity exposure for the primitive's maintained basis. |
| `bounded_fraction_of_benchmark_locomotion` | `CU = nominal weight × min(expected lost feet / benchmark locomotion Speed, active-window exposure)` | For one fully active window: CU = nominal weight × min(flat feet lost / benchmark locomotion Speed, 1). |
| `expected_displaced_feet` | `CU = nominal weight × expected displaced feet` | Displacement uses expected intrinsic feet only; it does not invent terrain or collision value. |
| `diagnostic_zero` | `CU = 0 headline CU` | This is a deliberate non-scalar/context diagnostic rule, not a claim that the mechanic has zero real-play value. |
| `points_times_placed_opportunities` | `CU = nominal weight × expected penalty-points/opportunities` | The placed exposure already combines the exact penalty magnitude with established attack or save opportunities. |
| `remaining_speed_fraction` | `CU = nominal weight × (1 - remaining Speed fraction) × active-window exposure` | The magnitude is the exact fraction of Speed that remains. |

#### How movement control is normalized

There is **no universal 30-foot target assumption**.

**Complete movement denial.** `turn_movement_denial` (Speed 0) is valued at `0.30 CU × active exposure`, independent of ordinary Speed. A creature with 10, 30, 60, or 80 feet of ordinary benchmark locomotion loses all movement capacity when rooted.

**Flat Speed loss.** `mobility_loss_feet` uses `0.30 CU × min(expected lost feet / benchmark locomotion Speed, active-window exposure)`. For one fully active window this is `weight × min(flat feet lost / benchmark locomotion Speed, 1)`.

**Illustrative calculations (not current aggregate results):**

| Illustrative case | Calculation | Result |
|---|---|---|
| -10 ft against benchmark Speed 10 | 0.30 × min(10 / 10, 1) | 0.30 CU |
| -10 ft against benchmark Speed 30 | 0.30 × min(10 / 30, 1) | 0.10 CU |
| -10 ft against benchmark Speed 60 | 0.30 × min(10 / 60, 1) | 0.05 CU |
| -30 ft against benchmark Speed 60 | 0.30 × min(30 / 60, 1) | 0.15 CU |
| Speed 0 against any ordinary Speed | 0.30 × 1.00 active exposure | 0.30 CU |

**Benchmark locomotion assumption.** `benchmark_locomotion_speed` is the fastest positive movement mode in the maintained SRD target record that is unconditional, unqualified, and not choice-dependent. Qualified or choice-dependent modes are excluded; walking Speed is not privileged. If no trustworthy positive mode exists, flat `mobility_loss_feet` fails closed to `context_required`.

Using the fastest unconditionally available listed mode supplies a neutral, target-specific denominator without inventing encounter geometry. It can conservatively understate a flat reduction in a fight where that fastest mode cannot be used. For example, an unconditional Fly Speed remains the maintained denominator even if a particular room prevents flight; the benchmark does not silently substitute walking Speed for an unmodeled battlefield.

**Correlated flat movement cap.** Multiple flat reductions are capped at complete movement denial only when explicit maintained correlation metadata connects their sources for the same scored windows. The cap never exceeds the target's benchmark locomotion Speed. Sharing a package, a primitive, or the fact that both reduce Speed does not establish correlation; unrelated mobility effects remain independent.

### Context-dependent and unpriced control primitives

Every primitive below defaults to `context_required` or `unsupported`, including entries with no scalar scoring rule. It contributes 0 headline CU when the benchmark cannot establish the required context. That fail-closed zero does **not** mean the mechanic is worthless in actual play.

| Primitive | Exposure basis | Status | Why it is not assigned headline CU |
|---|---|---|---|
| `target_choice_restriction` | `contextual_opportunity` | `context_required` | Value depends on the restricted source and available target choices. |
| `sight_option_denial` | `contextual_opportunity` | `context_required` | Value depends on sight-dependent options and alternative senses. |
| `movement_mode_denial` | `contextual_opportunity` | `context_required` | Value depends on the target's usable movement modes. |
| `geometry_sensitive_approach_restriction` | `contextual_opportunity` | `context_required` | Requires source geometry and a willing movement choice. |
| `ability_check_impairment` | `contextual_opportunity` | `context_required` | Requires a relevant ability-check opportunity and any stated predicate. |
| `speech_denial` | `contextual_opportunity` | `context_required` | Requires a communication-dependent opportunity. |
| `social_interaction_advantage` | `contextual_opportunity` | `context_required` | Requires a social interaction check involving the source. |
| `concentration_break` | `instantaneous_occurrence` | `context_required` | Requires the target to be concentrating. |
| `fall_transition` | `instantaneous_occurrence` | `context_required` | Requires airborne state and lack of hover or fall prevention. |
| `prone_incoming_attack_context` | `incoming_attack_opportunity` | `context_required` | Incoming attack effect depends on attacker distance. |
| `melee_hit_auto_critical_context` | `contextual_opportunity` | `context_required` | Automatic critical hits require a hit from an attacker within 5 feet. |
| `awareness_denial` | `contextual_opportunity` | `context_required` | Value depends on encounter information and awareness-sensitive opportunities. |
| `opportunity_attack_denial` | `contextual_opportunity` | `context_required` | Only a qualifying Opportunity Attack is denied; other Reactions remain available. |
| `terrain_movement_tax` | `target_turn_window` | `context_required` | Movement through the affected terrain costs additional movement without changing the Speed statistic. |
| `directional_movement_tax` | `contextual_opportunity` | `context_required` | The movement cost applies only in a specified direction and requires geometry. |
| `attack_action_cap` | `attack_opportunity` | `context_required` | The target's Attack action is capped, but the maintained target catalog does not establish a baseline attack count. |
| `restricted_attack_choice` | `contextual_opportunity` | `context_required` | The available attack and target depend on creatures within reach. |
| `finite_next_save_roll_penalty` | `save_opportunity` | `context_required` | The next qualifying save uses an exact finite penalty die and requires a downstream save opportunity. |
| `somatic_spell_failure` | `contextual_opportunity` | `context_required` | Value requires a qualifying spell with a Somatic component. |
| `damage_roll_penalty` | `contextual_opportunity` | `context_required` | Damage rolls are reduced without changing attack accuracy; value requires an offensive-output convention. |
| `two_sided_isolation` | `contextual_opportunity` | `context_required` | Interaction is blocked in both directions and cannot be valued as unilateral denial. |
| `target_protection` | `contextual_opportunity` | `context_required` | The controlled target is also protected from outside effects or attacks. |
| `retained_action_option` | `contextual_opportunity` | `context_required` | The target retains a specified Action or movement option that limits net control value. |
| `spellcasting_interruption` | `contextual_opportunity` | `context_required` | Value requires a qualifying observable enemy spellcasting opportunity. |
| `ongoing_spell_removal` | `contextual_opportunity` | `context_required` | Value requires a qualifying ongoing spell state and its established consequence. |
| `hostile_transformation` | `contextual_opportunity` | `context_required` | Value depends on an approved replacement-form inventory and its exact statistics. |
| `attitude_change` | `contextual_opportunity` | `context_required` | Behavioral value depends on encounter choices and is not inferred. |
| `size_change` | `contextual_opportunity` | `context_required` | Size change has value only when another established mechanic depends on size. |
| `open_ended_behavior` | `contextual_opportunity` | `context_required` | Behavioral consequences depend on an encounter-specific choice that the benchmark does not invent. |
| `held_item_loss` | `contextual_opportunity` | `context_required` | Value depends on whether the target holds relevant items and can recover or replace them. |
| `damage_output_change` | `contextual_opportunity` | `context_required` | Damage-output changes remain visible but outside the current Control Value scalar boundary. |
| `hearing_option_denial` | `contextual_opportunity` | `context_required` | Value requires a hearing-dependent option or communication opportunity. |

`unsupported` can also arise dynamically when a known mechanic lacks a trustworthy required magnitude, timing, or placement/exposure basis. Maintained examples of unresolved context include Ball Lightning future area occupancy, Mass Levitation recurring displacement cadence, and condition-context facts such as sight, concentration, speech, fall state, or attacker distance. The benchmark does not manufacture encounter facts to turn these diagnostics into numbers.

### Control Value normalization rules

Normalization prevents double charging while preserving independently established consequences. These statements describe `normalize_exposures()` and the explicit correlated-flat-mobility cap; they are not a second scoring engine.

| Rule | Maintained behavior |
|---|---|
| Duplicates | Identical primitive/basis/qualifier/magnitude consequences do not double count. `mobility_loss_feet` and `forced_displacement` remain source-specific so distinct legitimate sources are not automatically collapsed. |
| Disjoint sequential stages | Explicitly declared disjoint stages combine probabilities instead of becoming duplicate overlap; their combined probability may not exceed 1. |
| Action-economy dominance | Overlapping `active_turn_denial` dominates `bonus_action_denial`, `action_bonus_exclusivity`, `specified_action_requirement`, `attack_action_cap`, and offensive impairment. `bonus_action_denial` also dominates overlapping `action_bonus_exclusivity`. |
| Specified Action interaction | `specified_action_requirement` consumes overlapping all-attacks impairment on the same target-turn exposure instead of charging both at full value. |
| Attack impairment | All-attacks impairment dominates next-attack impairment only when maintained source-overlap metadata identifies the same attack share. An unrelated next-attack effect survives. |
| Save impairment | For the same save ability, `save_auto_failure` dominates `save_disadvantage`, `flat_save_roll_penalty`, and `finite_next_save_roll_penalty`. Impairment of a different save ability survives. |
| Movement dominance | `turn_movement_denial` dominates overlapping `mobility_loss_feet`, `speed_multiplier`, and `standing_movement_cost`. |
| Correlated flat mobility | Only explicit same-window correlation metadata invokes the target-specific complete-movement cap; unrelated flat reductions are not implicitly capped or merged. |
| Partial overlap | When a stronger effect covers only part of the weaker effect's active exposure, the residual weaker exposure is preserved. |
| Unrelated consequences | Unrelated surviving primitives add independently. |

## Reproducibility and maintained sources

- [Kinetic Vanguard rules](KineticVanguard.yaml)
- [Harness methodology](harness/README.md)
- [Benchmark configuration](harness/config/benchmark.json)
- [Control Value scoring configuration](harness/config/control-value.json)
- [Control primitive catalog](harness/data/control_primitives.json)
- [Comparator assumptions](harness/comparators/fighter-subclasses.json)

Creature benchmark data is SRD 5.2.1. Maintained comparator mechanics are independently expressed analytical abstractions under the reviewed comparator source policy; they are not Kinetic Vanguard rules. Battle Master and Eldritch Knight are referenced solely as unofficial third-party comparative benchmarks. The Kinetic Vanguard project is not affiliated with or endorsed by Wizards of the Coast. No project license purports to grant rights in Wizards-owned material outside the System Reference Document. See [LICENSE.md](LICENSE.md) for component boundaries and [NOTICE.md](NOTICE.md) for attribution and notices.

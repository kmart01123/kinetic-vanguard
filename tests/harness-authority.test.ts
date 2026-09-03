import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createHarnessProjection } from "../src/harness-authority.js";
import { loadAuthority } from "../src/load.js";
import { deriveCalculatorProjection } from "../src/mechanics-selectors.js";
import { validateSemantics } from "../src/validate.js";

test("harness projection reads the real authority and joins mechanics by stable entity ID",async()=>{
  const projection=await createHarnessProjection();
  assert.equal(projection.projection_version,"1.3.0");
  assert.match(projection.authority_path,/\/KineticVanguard\.yaml$/);
  assert.ok(Number.isInteger(projection.core.action_economy.standalone_psionic_action_limit_per_turn));
  assert.equal(projection.core.manifested_strike.rider_repeatability,"per_manifested_strike");
  assert.equal(new Set(projection.features.map(item=>item.entity_id)).size,projection.features.length);
  assert.ok(projection.features.every(item=>Number.isInteger(item.minimum_level)&&Number.isInteger(item.psi_cost)&&item.title.length>0));
  assert.equal(projection.features.find(item=>item.entity_id==="explosion_implosion")?.title,"Explosion/Implosion");
  assert.equal(projection.features.find(item=>item.entity_id==="advanced_phase_step")?.advanced_training,true);
  assert.ok(projection.features.every(item=>!Object.hasOwn(item,"repeatability")));
  assert.ok(projection.disciplines.every(item=>item.id&&item.damage_type&&item.signature_save&&item.mastery));
  assert.ok(projection.features.some(item=>item.damage_tiers.length&&item.control_tiers?.length));
  assert.equal(projection.features.find(item=>item.entity_id==="glacial_spike")?.damage_type,"cold");
  assert.deepEqual(projection.features.find(item=>item.entity_id==="advanced_phase_step")?.control_tiers?.[0]?.save,{kind:"discipline_mapping",by_discipline:{cryokinesis:"constitution",pyrokinesis:"dexterity",psychokinesis:"strength",electrokinesis:"charisma"}});
  assert.deepEqual(projection.features.find(item=>item.entity_id==="advanced_improved_phase_step")?.damage_type,{kind:"manifested_strike_damage_type"});
});

test("harness semantic mutations fail with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  const system=(candidate:any,id:string)=>candidate.entities.find((entity:any)=>entity.id===id).system_mechanics;
  expectCode("harness.action_economy",candidate=>{system(candidate,"common_overload").action_economy.action_surge_allows_additional_standalone_psionic_action=true;});
  expectCode("harness.attack_formula",candidate=>{system(candidate,"common_manifested_strike").manifested_strike.attack_bonus.base=1;});
  expectCode("harness.holdout_formula",candidate=>{system(candidate,"common_manifested_strike").manifested_strike.holdout.formulas[1].sides=8;});
  expectCode("harness.save_dc_formula",candidate=>{system(candidate,"common_manifested_strike").manifested_strike.save_dc.components.reverse();});
  expectCode("harness.mastery_control_measurement",candidate=>{delete system(candidate,"common_kinetic_mastery").disciplines.find((item:any)=>item.id==="cryokinesis").mastery.control_magnitude_feet;});
  expectCode("calculator.psi_point_progression",candidate=>{system(candidate,"common_psi_reservoir").psi_point_bands[0].value+=1;});
  expectCode("harness.blood_tax_formula",candidate=>{system(candidate,"common_overload").overload.blood_tax_per_tier.base=1;});
  expectCode("harness.psionic_apex",candidate=>{system(candidate,"advanced_training_progression").psionic_apex.psychokinesis_manifested_strike_hit.uses_per_attack_action=2;});
  expectCode("harness.discipline_coverage",candidate=>{system(candidate,"common_kinetic_mastery").disciplines.pop();});
  expectCode("system_mechanics.owner_missing",candidate=>{delete system(candidate,"advanced_training_progression").psionic_apex;});
});

test("named-condition save enforcement stays scoped to typed hostile applications",async()=>{
  const {authority}=await loadAuthority();
  const namedConditionDiagnostics=(candidate:any)=>validateSemantics(candidate).filter(item=>item.code==="harness.named_condition_save_required");
  assert.deepEqual(namedConditionDiagnostics(authority),[]);

  const rules=deriveCalculatorProjection(authority).harness_mechanics.feature_rules;
  const flare=rules.find(item=>item.entity_id==="flare")!;
  assert.ok(flare.control_tiers?.every(control=>control.application==="failed_save"&&control.save==="dexterity"&&control.effects.every(effect=>effect.gate==="on_failed_save")));

  const noSaveCondition=structuredClone(authority) as any,flareEntity=noSaveCondition.entities.find((entity:any)=>entity.id==="flare"),noSaveTier=flareEntity.mechanics.surfaces[0].tiers[0],savingThrow=noSaveTier.steps.find((step:any)=>step.kind==="saving_throw"),condition=savingThrow.failure.find((step:any)=>step.kind==="condition");
  noSaveTier.steps=noSaveTier.steps.filter((step:any)=>step!==savingThrow);noSaveTier.steps.push(condition);
  assert.equal(namedConditionDiagnostics(noSaveCondition).length,1);

  const missingSave=structuredClone(authority) as any;
  delete missingSave.entities.find((entity:any)=>entity.id==="flare").mechanics.surfaces[0].tiers[0].steps.find((step:any)=>step.kind==="saving_throw").ability;
  assert.equal(namedConditionDiagnostics(missingSave).length,1);

  const glacialSpike=rules.find(item=>item.entity_id==="glacial_spike")!;
  const noSaveNonCondition=glacialSpike.control_tiers?.find(control=>control.tier===0)!;
  assert.equal(noSaveNonCondition.application,"no_save");assert.ok(noSaveNonCondition.effects.every(effect=>!effect.conditions?.length));

  const masteries=deriveCalculatorProjection(authority).harness_mechanics.disciplines.map(discipline=>discipline.mastery);
  assert.ok(masteries.every(mastery=>!Object.hasOwn(mastery,"save")&&!Object.hasOwn(mastery,"conditions")));
  const barrier=authority.entities.find(entity=>entity.id==="advanced_barrier")!;
  assert.match(JSON.stringify(barrier.content),/Charmed/);assert.ok(!rules.find(item=>item.entity_id==="advanced_barrier")?.control_tiers?.some(control=>control.effects.some(effect=>effect.conditions?.length)));
  assert.deepEqual(namedConditionDiagnostics(authority),[]);
});

test("minimal comparator parameters stay isolated from all canonical KV mechanics and benchmark methodology",async()=>{
  const [{authority},yamlSource,configSource,comparatorSource]=await Promise.all([loadAuthority(),readFile("KineticVanguard.yaml","utf8"),readFile("harness/config/benchmark.json","utf8"),readFile("harness/comparators/fighter-subclasses.json","utf8")]);
  const comparatorPattern=/battle.?master|eldritch.?knight/i;
  assert.doesNotMatch(JSON.stringify(authority),comparatorPattern);assert.doesNotMatch(yamlSource,comparatorPattern);assert.doesNotMatch(configSource,comparatorPattern);
  assert.match(comparatorSource,/battle_master/);assert.match(comparatorSource,/eldritch_knight/);
  const comparators=JSON.parse(comparatorSource);assert.equal(comparators.source_ruleset,"2024 fifth-edition rules");assert.deepEqual(comparators.primary_comparator_ids,["battle_master","eldritch_knight"]);
  assert.deepEqual(Object.keys(comparators.damage).sort(),["battle_master","eldritch_knight"]);assert.deepEqual(Object.keys(comparators.control).sort(),["battle_master","eldritch_knight"]);
  const keys=(value:any):string[]=>value&&typeof value==="object"?Object.entries(value).flatMap(([key,child])=>[key,...keys(child)]):[];
  for(const forbidden of ["label","status","description","rules_text","feature_text","spell_text","maneuver_text","flavor"])assert.ok(!keys(comparators).includes(forbidden),forbidden);
});

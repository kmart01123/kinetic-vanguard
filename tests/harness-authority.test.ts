import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createHarnessProjection } from "../src/harness-authority.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

test("harness projection reads the real authority and joins mechanics by stable entity ID",async()=>{
  const projection=await createHarnessProjection();
  assert.equal(projection.projection_version,"1.1.0");
  assert.match(projection.authority_path,/\/KineticVanguard\.yaml$/);
  assert.ok(Number.isInteger(projection.core.action_economy.standalone_psionic_action_limit_per_turn));
  assert.equal(projection.core.manifested_strike.rider_repeatability,"per_manifested_strike");
  assert.equal(new Set(projection.features.map(item=>item.entity_id)).size,projection.features.length);
  assert.ok(projection.features.every(item=>Number.isInteger(item.minimum_level)&&Number.isInteger(item.psi_cost)&&!Object.hasOwn(item,"title")));
  assert.ok(projection.features.every(item=>!Object.hasOwn(item,"repeatability")));
  assert.ok(projection.disciplines.every(item=>item.id&&item.damage_type&&item.signature_save&&item.mastery));
  assert.ok(projection.features.some(item=>item.damage_tiers.length&&item.control_tiers?.length));
});

test("harness semantic mutations fail with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  expectCode("harness.action_economy",candidate=>{candidate.calculator.harness_mechanics.action_economy.action_surge_allows_additional_standalone_psionic_action=true;});
  expectCode("harness.attack_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.attack_bonus.base=1;});
  expectCode("harness.holdout_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.holdout.formulas[1].sides=8;});
  expectCode("harness.save_dc_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.save_dc.components.reverse();});
  expectCode("harness.feature_coverage",candidate=>{candidate.calculator.features=candidate.calculator.features.filter((item:any)=>item.entity_id!=="flare");});
  expectCode("harness.mastery_control_measurement",candidate=>{delete candidate.calculator.harness_mechanics.disciplines.find((item:any)=>item.id==="cryokinesis").mastery.control_magnitude_feet;});
  expectCode("harness.control_attack_scope",candidate=>{delete candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="electron_burst").control_tiers[0].effects[0].attack_scope;});
  expectCode("calculator.psi_point_progression",candidate=>{candidate.calculator.psi_point_bands[0].value+=1;});
  expectCode("harness.blood_tax_formula",candidate=>{candidate.calculator.harness_mechanics.overload.blood_tax_per_tier.base=1;});
  expectCode("harness.psionic_apex",candidate=>{candidate.calculator.harness_mechanics.psionic_apex.psychokinesis_manifested_strike_hit.uses_per_attack_action=2;});
  expectCode("harness.discipline_coverage",candidate=>{candidate.calculator.harness_mechanics.disciplines.pop();});
  expectCode("harness.feature_unknown",candidate=>{candidate.calculator.harness_mechanics.feature_rules[0].entity_id="missing_harness_feature";});
  expectCode("harness.targeting_count",candidate=>{
    const targeting=candidate.calculator.harness_mechanics.feature_rules.flatMap((rule:any)=>rule.targeting_by_tier??[]).find((item:any)=>item.kind==="fixed_additional");
    delete targeting.additional_targets;
  });
  expectCode("harness.control_save_required",candidate=>{
    const control=candidate.calculator.harness_mechanics.feature_rules.flatMap((rule:any)=>rule.control_tiers??[]).find((item:any)=>item.application==="failed_save");
    delete control.save;
  });
  expectCode("harness.control_save_forbidden",candidate=>{
    const control=candidate.calculator.harness_mechanics.feature_rules.flatMap((rule:any)=>rule.control_tiers??[]).find((item:any)=>item.application==="failed_save");
    control.application="no_save";
  });
  expectCode("harness.control_outcome",candidate=>{
    const effect=candidate.calculator.harness_mechanics.feature_rules.flatMap((rule:any)=>rule.control_tiers??[]).flatMap((control:any)=>control.effects).find((item:any)=>item.conditions?.length&&!item.outcomes?.length);
    delete effect.conditions;delete effect.outcomes;
  });
  expectCode("harness.named_condition_save_required",candidate=>{
    const control=candidate.calculator.harness_mechanics.feature_rules.flatMap((rule:any)=>rule.control_tiers??[]).find((item:any)=>item.effects.some((effect:any)=>effect.conditions?.length));
    control.effects.find((effect:any)=>effect.conditions?.length).gate="on_reach";
  });
  expectCode("harness.control_magnitude",candidate=>{
    const effect=candidate.calculator.harness_mechanics.feature_rules.flatMap((rule:any)=>rule.control_tiers??[]).flatMap((control:any)=>control.effects).find((item:any)=>item.outcomes?.includes("forced_movement")&&item.magnitude_feet!==undefined);
    delete effect.magnitude_feet;
  });
});

test("named-condition save enforcement stays scoped to typed hostile applications",async()=>{
  const {authority}=await loadAuthority();
  const namedConditionDiagnostics=(candidate:any)=>validateSemantics(candidate).filter(item=>item.code==="harness.named_condition_save_required");
  assert.deepEqual(namedConditionDiagnostics(authority),[]);

  const rules=authority.calculator.harness_mechanics.feature_rules;
  const flare=rules.find(item=>item.entity_id==="flare")!;
  assert.ok(flare.control_tiers?.every(control=>control.application==="failed_save"&&control.save==="dexterity"&&control.effects.every(effect=>effect.gate==="on_failed_save")));

  const noSaveCondition=structuredClone(authority) as any;
  const noSaveFlare=noSaveCondition.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="flare").control_tiers[0];
  noSaveFlare.application="no_save";delete noSaveFlare.save;noSaveFlare.effects[0].gate="on_reach";
  assert.equal(namedConditionDiagnostics(noSaveCondition).length,1);

  const missingSave=structuredClone(authority) as any;
  delete missingSave.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="flare").control_tiers[0].save;
  assert.equal(namedConditionDiagnostics(missingSave).length,1);

  const glacialSpike=rules.find(item=>item.entity_id==="glacial_spike")!;
  const noSaveNonCondition=glacialSpike.control_tiers?.find(control=>control.tier===0)!;
  assert.equal(noSaveNonCondition.application,"no_save");assert.ok(noSaveNonCondition.effects.every(effect=>!effect.conditions?.length));

  const masteries=authority.calculator.harness_mechanics.disciplines.map(discipline=>discipline.mastery);
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

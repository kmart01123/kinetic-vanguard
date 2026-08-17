import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createHarnessProjection } from "../src/harness-authority.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

test("harness projection reads the real authority and joins mechanics by stable entity ID",async()=>{
  const projection=await createHarnessProjection();
  assert.match(projection.authority_path,/\/KineticVanguard\.yaml$/);
  assert.ok(projection.rules_version);assert.ok(projection.schema_version);
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
  expectCode("harness.save_dc_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.save_dc.components.reverse();});
  expectCode("harness.feature_coverage",candidate=>{candidate.calculator.features=candidate.calculator.features.filter((item:any)=>item.entity_id!=="flare");});
  expectCode("harness.mastery_control_measurement",candidate=>{delete candidate.calculator.harness_mechanics.disciplines.find((item:any)=>item.id==="cryokinesis").mastery.control_magnitude_feet;});
  expectCode("harness.control_attack_scope",candidate=>{delete candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="electron_burst").control_tiers[0].effects[0].attack_scope;});
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

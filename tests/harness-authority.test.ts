import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createHarnessProjection } from "../src/harness-authority.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

test("harness projection reads the real authority and joins mechanics by stable entity ID",async()=>{
  const projection=await createHarnessProjection();
  assert.equal(projection.rules_version,"14.2.0");assert.equal(projection.schema_version,"2.1.0");assert.match(projection.authority_path,/\/KineticVanguard\.yaml$/);
  assert.deepEqual(projection.core.action_economy,{standalone_psionic_action_limit_per_turn:1,action_surge_allows_additional_standalone_psionic_action:false});
  assert.equal(projection.core.manifested_strike.rider_repeatability,"per_manifested_strike");
  assert.deepEqual(projection.disciplines.map(item=>item.id).sort(),["cryokinesis","electrokinesis","psychokinesis","pyrokinesis"]);
  assert.equal(new Set(projection.features.map(item=>item.entity_id)).size,projection.features.length);
  assert.ok(projection.features.every(item=>Number.isInteger(item.minimum_level)&&Number.isInteger(item.psi_cost)&&!Object.hasOwn(item,"title")));
  assert.ok(projection.features.every(item=>!Object.hasOwn(item,"repeatability")));
  const flare=projection.features.find(item=>item.entity_id==="flare")!;assert.equal(flare.minimum_level,15);assert.equal(flare.psi_cost,3);assert.equal(flare.damage_tiers.length,3);assert.equal(flare.control_tiers?.length,3);
});

test("harness semantic mutations fail with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  expectCode("harness.action_economy",candidate=>{candidate.calculator.harness_mechanics.action_economy.action_surge_allows_additional_standalone_psionic_action=true;});
  expectCode("harness.rider_repeatability",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.rider_repeatability="once_per_target";});
  expectCode("harness.attack_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.attack_bonus.base=1;});
  expectCode("harness.save_dc_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.save_dc.components.reverse();});
  expectCode("harness.blood_tax_formula",candidate=>{candidate.calculator.harness_mechanics.overload.blood_tax_per_tier.proficiency_bonus_multiplier=2;});
  expectCode("harness.discipline_duplicate",candidate=>{candidate.calculator.harness_mechanics.disciplines[1].id=candidate.calculator.harness_mechanics.disciplines[0].id;});
  expectCode("harness.feature_duplicate",candidate=>{candidate.calculator.harness_mechanics.feature_rules[1].entity_id=candidate.calculator.harness_mechanics.feature_rules[0].entity_id;});
  expectCode("harness.feature_coverage",candidate=>{candidate.calculator.harness_mechanics.feature_rules=candidate.calculator.harness_mechanics.feature_rules.filter((item:any)=>item.entity_id!=="flare");});
  expectCode("harness.feature_unknown",candidate=>{candidate.calculator.harness_mechanics.feature_rules[0].entity_id="missing_feature";});
  expectCode("harness.targeting_tier_duplicate",candidate=>{candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="branching_bolt").targeting_by_tier[1].tier=0;});
  expectCode("harness.targeting_count",candidate=>{delete candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="branching_bolt").targeting_by_tier[0].additional_targets;});
  expectCode("harness.control_tier_duplicate",candidate=>{candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="flare").control_tiers[1].tier=0;});
  expectCode("harness.control_save_required",candidate=>{delete candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="flare").control_tiers[0].save;});
  expectCode("harness.control_save_forbidden",candidate=>{candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="flare").control_tiers[1].save="dexterity";});
  expectCode("harness.control_outcome",candidate=>{const effect=candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="flare").control_tiers[0].effects[0];delete effect.conditions;delete effect.outcomes;});
});

test("official harness source is positive input while imports and generated outputs remain excluded",async()=>{
  const inputs=JSON.parse(await readFile("build/inputs.json","utf8")).inputs as Array<{path:string;role:string}>;const paths=inputs.map(input=>input.path);
  for(const required of ["src/harness-authority.ts","harness/authority.py","harness/damage_harness.py","harness/control_harness.py","harness/readme_matrices.py","harness/comparison_report.py","harness/config/benchmark.json","harness/comparators/fighter-subclasses.json","harness/data/srd_targets.csv","harness/provenance/legacy-import.json","harness/tests/test_harness.py","harness/tests/test_readme_matrices.py"])assert.ok(paths.includes(required),required);
  assert.ok(paths.every(path=>!path.startsWith(".codex-import/")&&!path.endsWith(".zip")&&!path.includes("harness/results")));
  const [ignore,workflow,packageJson]=await Promise.all([readFile(".gitignore","utf8"),readFile(".github/workflows/ci.yml","utf8"),readFile("package.json","utf8")]);
  assert.match(ignore,/^\.codex-import\/$/m);assert.match(ignore,/^harness\/results\/$/m);assert.match(workflow,/npm run test:harness/);assert.match(workflow,/npm run harness:validate/);assert.match(packageJson,/"test:harness"/);
});

test("minimal comparator parameters stay isolated from all canonical KV mechanics and benchmark methodology",async()=>{
  const [{authority},yamlSource,configSource,comparatorSource]=await Promise.all([loadAuthority(),readFile("KineticVanguard.yaml","utf8"),readFile("harness/config/benchmark.json","utf8"),readFile("harness/comparators/fighter-subclasses.json","utf8")]);
  const comparatorPattern=/battle.?master|eldritch.?knight|hunter.?ranger|open.?hand.?monk/i;
  assert.doesNotMatch(JSON.stringify(authority),comparatorPattern);assert.doesNotMatch(yamlSource,comparatorPattern);assert.doesNotMatch(configSource,comparatorPattern);
  assert.match(comparatorSource,/battle_master/);assert.match(comparatorSource,/eldritch_knight/);assert.doesNotMatch(comparatorSource,/hunter.?ranger|open.?hand.?monk/i);
  const comparators=JSON.parse(comparatorSource);assert.equal(comparators.source_ruleset,"2024 fifth-edition rules");assert.deepEqual(comparators.primary_comparator_ids,["battle_master","eldritch_knight"]);
  assert.deepEqual(Object.keys(comparators.damage).sort(),["battle_master","eldritch_knight"]);assert.deepEqual(Object.keys(comparators.control).sort(),["battle_master","eldritch_knight"]);
  const keys=(value:any):string[]=>value&&typeof value==="object"?Object.entries(value).flatMap(([key,child])=>[key,...keys(child)]):[];
  for(const forbidden of ["label","status","description","rules_text","feature_text","spell_text","maneuver_text","flavor"])assert.ok(!keys(comparators).includes(forbidden),forbidden);
});

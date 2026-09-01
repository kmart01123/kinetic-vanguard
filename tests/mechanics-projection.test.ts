import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import YAML from "yaml";
import { canonicalJson } from "../src/canonical.js";
import { projectCalculatorMechanics,projectHarnessMechanics } from "../src/mechanics.js";
import { deriveCalculatorProjection } from "../src/mechanics-selectors.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

const sentinelIds=["common_empathic_sense","ember_bolt","explosion_implosion","frozen_ground","glacial_spike","static_discharge"];
const compatibilityHashes:Record<string,{calculator:string;harness:string}>={
  common_empathic_sense:{calculator:"b0cf1d38d161ef1d645d006b96d261534e8997f2ae6f7783130dbb0c60acc0f4",harness:"74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"},
  ember_bolt:{calculator:"5e43c3e724101a47467d003f11c0ced6a2b16d979df0f4fa028a4461232f5911",harness:"785f4a9017423e3715bd63fa2e3bfd655b83646782b191fea72daa1c0d998541"},
  explosion_implosion:{calculator:"96c07bc6be62656a4c6716c0951031812340aa485bca12438fdbf60dd337b705",harness:"41bb1403becd0b288a35e2673bcf5174f0e7251a0acc4bb58234d699eda7bbfe"},
  frozen_ground:{calculator:"57dc03988f13ec010258d74d2b81a124ef1b0681910b4928785f00e2e541ac55",harness:"a2be21d15d038a8a3e0931ba373c06291d5f6db74a07265e3ccd285b1bb07977"},
  glacial_spike:{calculator:"2853d1898ad77a1384c9a394c9500fa2d4b4d504a65d61ab3e52ea4a8cbc017c",harness:"43f1be1dc30ba6714224e2336872fce6e799f014968157bca20aae4d07e6b229"},
  static_discharge:{calculator:"fed529b22681cc4ec20e3f5f52b592a4feaf2c4912d47716db6884ff0d034e61",harness:"c1b353dd0df039f04a7c9417b1878426b60f92f17bbbff90855d9678895dc999"}
};
const hash=(value:unknown)=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const systemFields=["proficiency_bonus_bands","psi_point_bands","psionic_focus_bands","manifested_strike_die_bands","tier_minimum_levels","action_economy","manifested_strike","overload","psionic_apex","disciplines"];

test("shared progressions and core mechanics are entity-owned without Calculator or harness registries",async()=>{
  const [{authority},source]=await Promise.all([loadAuthority(),readFile("KineticVanguard.yaml","utf8")]),raw=YAML.parse(source) as any;
  for(const field of [...systemFields,"features","harness_mechanics"])assert.equal(raw.calculator[field],undefined,field);
  const owners=raw.entities.flatMap((entity:any)=>Object.keys(entity.system_mechanics??{}).map(field=>[field,entity.id]));
  assert.deepEqual(owners.map(([field]:string[])=>field).sort(),[...systemFields].sort());
  const calculator=deriveCalculatorProjection(authority),hydrated=[...systemFields.slice(0,5).map(field=>(calculator as any)[field]),...systemFields.slice(5).map(field=>(calculator.harness_mechanics as any)[field])];
  assert.equal(hash(hydrated),"687d71895e63f7fcc2448f2b2eb71a0bdd7cfd0615455e65f12bda4dca987147");
});

test("every machine-consumed ability authors mechanics once and derives consumer contracts",async()=>{
  const [{authority},source]=await Promise.all([loadAuthority(),readFile("KineticVanguard.yaml","utf8")]),raw=YAML.parse(source) as any,entities=authority.entities.filter(entity=>entity.mechanics);
  const projection=deriveCalculatorProjection(authority),calculatorIds=projection.features.map(feature=>feature.entity_id).sort(),harnessIds=projection.harness_mechanics.feature_rules.map(rule=>rule.entity_id).sort();
  assert.equal(calculatorIds.length,30);assert.equal(harnessIds.length,27);assert.deepEqual(entities.map(entity=>entity.id).sort(),calculatorIds);
  assert.equal(raw.calculator.features,undefined);assert.equal(raw.calculator.harness_mechanics,undefined);
  assert.equal(hash(projection.features),"d65242939b39170bc69d333f43cea17aace02313b61a3620f745144425e0220d");
  assert.equal(hash(projection.harness_mechanics.feature_rules),"7f2e225107b7b443a421934022c570b573ba14ba86af64cc8fc8f32129d16bac");
  for(const entity of entities){
    const calculator=projection.features.find(feature=>feature.entity_id===entity.id);assert.ok(calculator,entity.id);assert.deepEqual(projectCalculatorMechanics(entity),calculator,`${entity.id} Calculator projection`);
    const harness=projection.harness_mechanics.feature_rules.find(rule=>rule.entity_id===entity.id)??null;assert.deepEqual(projectHarnessMechanics(entity),harness,`${entity.id} harness projection`);
    if(sentinelIds.includes(entity.id)){assert.equal(hash(calculator),compatibilityHashes[entity.id]!.calculator,`${entity.id} Calculator compatibility contract`);assert.equal(hash(harness),compatibilityHashes[entity.id]!.harness,`${entity.id} harness compatibility contract`);}
  }
});

test("neutral mechanics changes flow directly to consumers and structural drift fails closed",async()=>{
  const {authority}=await loadAuthority(),candidate=structuredClone(authority) as any;
  const ember=candidate.entities.find((entity:any)=>entity.id==="ember_bolt"),damage=ember.mechanics.surfaces[0].tiers[0].steps.find((step:any)=>step.kind==="damage");damage.value.value=3;
  assert.notEqual(hash(deriveCalculatorProjection(candidate).features),hash(deriveCalculatorProjection(authority).features));
  const staticDischarge=candidate.entities.find((entity:any)=>entity.id==="static_discharge"),reaction=staticDischarge.mechanics.surfaces[0].tiers[2].steps.find((step:any)=>step.kind==="saving_throw").failure[0];reaction.duration="until_end_next_turn";
  assert.notEqual(hash(deriveCalculatorProjection(candidate).harness_mechanics.feature_rules),hash(deriveCalculatorProjection(authority).harness_mechanics.feature_rules));
  const brokenReplacement=structuredClone(authority) as any,glacial=brokenReplacement.entities.find((entity:any)=>entity.id==="glacial_spike"),replacement=glacial.mechanics.surfaces[0].tiers[1].steps.find((step:any)=>step.kind==="saving_throw").failure[0];replacement.replaces="missing_step";
  assert.ok(validateSemantics(brokenReplacement).some(diagnostic=>diagnostic.code==="mechanics.replacement_reference"));
  const brokenMode=structuredClone(authority) as any,explosion=brokenMode.entities.find((entity:any)=>entity.id==="explosion_implosion"),movement=explosion.mechanics.surfaces[0].tiers[0].steps.find((step:any)=>step.kind==="saving_throw").failure.find((step:any)=>step.kind==="forced_movement");movement.directions[0].mode="missing_mode";
  assert.ok(validateSemantics(brokenMode).some(diagnostic=>diagnostic.code==="mechanics.mode_reference"));
});

test("shared-system changes flow directly to consumers and retain semantic validation",async()=>{
  const {authority}=await loadAuthority(),candidate=structuredClone(authority) as any;
  candidate.entities.find((entity:any)=>entity.id==="common_psi_reservoir").system_mechanics.psi_point_bands[0].value+=1;
  assert.equal(deriveCalculatorProjection(candidate).psi_point_bands[0]!.value,5);
  assert.ok(validateSemantics(candidate).some(diagnostic=>diagnostic.code==="calculator.psi_point_progression"));
});

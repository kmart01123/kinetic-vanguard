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
  ember_bolt:{calculator:"5e43c3e724101a47467d003f11c0ced6a2b16d979df0f4fa028a4461232f5911",harness:"624dcbba39fc46a1718e8f84bce22db7eda70fecb42883ecceccb6f1538f9036"},
  explosion_implosion:{calculator:"96c07bc6be62656a4c6716c0951031812340aa485bca12438fdbf60dd337b705",harness:"41bb1403becd0b288a35e2673bcf5174f0e7251a0acc4bb58234d699eda7bbfe"},
  frozen_ground:{calculator:"57dc03988f13ec010258d74d2b81a124ef1b0681910b4928785f00e2e541ac55",harness:"8119f049874a4768f91c1ab55c57d1006dd5c8240b4aa0192719aec073916615"},
  glacial_spike:{calculator:"2853d1898ad77a1384c9a394c9500fa2d4b4d504a65d61ab3e52ea4a8cbc017c",harness:"9cf3a1a4fd83d065212c33e7fa7366bfdba449bc205f824bea9bcd85b6e31fdd"},
  static_discharge:{calculator:"fed529b22681cc4ec20e3f5f52b592a4feaf2c4912d47716db6884ff0d034e61",harness:"6dc6e739d5febe412948ba450c69a360e2a3103445dc3dbbcd7ed6048d5e3f68"}
};
const hash=(value:unknown)=>createHash("sha256").update(canonicalJson(value)).digest("hex");
const legacySave=(value:unknown)=>typeof value==="object"&&value!==null&&(value as any).kind==="discipline_mapping"?"discipline_signature":value;
const legacyCalculatorView=(features:any[])=>structuredClone(features).map(feature=>({...feature,...(feature.tiers?{tiers:feature.tiers.map((tier:any)=>({...tier,...(tier.save?{save:legacySave(tier.save)}:{})}))}:{})}));
const legacyHarnessView=(rules:any[])=>{const disciplineAliases=new Set(["glacial_spike","snow_chains","frozen_ground","arctic_tempest","absolute_zero","ember_bolt","thermal_fracture","telekinetic_shove","vectored_thrust","static_discharge"]);return structuredClone(rules).map(rule=>{if(disciplineAliases.has(rule.entity_id))rule.damage_type="discipline";if(rule.entity_id==="advanced_phase_step")rule.damage_type="discipline";if(rule.entity_id==="advanced_improved_phase_step")rule.damage_type="force";for(const control of rule.control_tiers??[])if(control.save)control.save=legacySave(control.save);if(rule.entity_id==="advanced_beguile")delete rule.targeting_by_tier;return rule;});};
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
  assert.equal(hash(projection.features),"8b664602328f1d33b9b0eccdf6fc6aef18e91f88c9e5d0510759ac21965880bf");
  assert.equal(hash(projection.harness_mechanics.feature_rules),"6b9874a624cd1b77df97f6dd5ca12c08f065b166b274444e28e33d098f716807");
  assert.equal(hash(legacyCalculatorView(projection.features)),"d65242939b39170bc69d333f43cea17aace02313b61a3620f745144425e0220d");
  assert.equal(hash(legacyHarnessView(projection.harness_mechanics.feature_rules)),"7f2e225107b7b443a421934022c570b573ba14ba86af64cc8fc8f32129d16bac");
  for(const entity of entities){
    const calculator=projection.features.find(feature=>feature.entity_id===entity.id);assert.ok(calculator,entity.id);assert.deepEqual(projectCalculatorMechanics(entity),calculator,`${entity.id} Calculator projection`);
    const harness=projection.harness_mechanics.feature_rules.find(rule=>rule.entity_id===entity.id)??null;assert.deepEqual(projectHarnessMechanics(entity),harness,`${entity.id} harness projection`);
    if(sentinelIds.includes(entity.id)){assert.equal(hash(calculator),compatibilityHashes[entity.id]!.calculator,`${entity.id} Calculator compatibility contract`);assert.equal(hash(harness),compatibilityHashes[entity.id]!.harness,`${entity.id} harness compatibility contract`);}
  }
});

test("delivery and targeting topology remain independent across representative mechanics",async()=>{
  const {authority}=await loadAuthority(),entity=(id:string)=>authority.entities.find(item=>item.id===id)!,surface=(id:string)=>entity(id).mechanics!.surfaces[0]!,target=(id:string,tier=0)=>surface(id).tiers!.find(item=>item.tier===tier)!.targeting;
  for(const [id,delivery,topology] of [
    ["glacial_spike","rider","single"],
    ["static_discharge","rider","discrete_multi"],
    ["explosion_implosion","rider","area"],
    ["absolute_zero","standalone","single"],
    ["arctic_tempest","standalone","discrete_multi"],
    ["frozen_ground","standalone","area"],
    ["vectored_thrust","standalone","self"]
  ] as const){assert.equal(surface(id).delivery.kind,delivery,id);assert.equal(target(id).topology,topology,id);}
  const passive=entity("common_empathic_sense").mechanics!.surfaces.find(item=>item.id==="passive")!;assert.equal(passive.delivery.kind,"passive");assert.deepEqual(passive.targeting,{topology:"none",kind:"none"});
  const riders=authority.entities.flatMap(item=>item.mechanics?.surfaces??[]).filter(item=>item.delivery.kind==="rider");assert.equal(riders.length,14);assert.ok(riders.every(item=>item.delivery.kind==="rider"&&item.delivery.rider_slot==="manifested_strike"));
  const targetings=authority.entities.flatMap(item=>(item.mechanics?.surfaces??[]).flatMap(item=>[...(item.targeting?[item.targeting]:[]),...(item.tiers??[]).map(tier=>tier.targeting)])??[]);assert.ok(targetings.every(item=>["single","discrete_multi","area","self","none"].includes(item.topology)));assert.ok(targetings.every(item=>String(item.kind)!=="authored_procedure"));
});

test("canonical mechanics reject incomplete topology and single-target secondary effects",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const codes=validateSemantics(candidate).map(item=>item.code);assert.ok(codes.includes(code),`${code}: ${codes.join(", ")}`);};
  expectCode("mechanics.area_geometry",candidate=>{delete candidate.entities.find((item:any)=>item.id==="frozen_ground").mechanics.surfaces[0].tiers[0].targeting.height_feet;});
  expectCode("mechanics.discrete_multi_selection",candidate=>{delete candidate.entities.find((item:any)=>item.id==="static_discharge").mechanics.surfaces[0].tiers[0].targeting.additional_count;});
  expectCode("mechanics.single_secondary_target",candidate=>{candidate.entities.find((item:any)=>item.id==="glacial_spike").mechanics.surfaces[0].tiers[0].steps[0].target="secondary";});
  expectCode("mechanics.passive_targeting",candidate=>{candidate.entities.find((item:any)=>item.id==="advanced_inner_reserve").mechanics.surfaces[0].targeting={topology:"self",kind:"self"};});
  expectCode("mechanics.discipline_damage_type",candidate=>{candidate.entities.find((item:any)=>item.id==="ember_bolt").mechanics.surfaces[0].tiers[0].steps[0].damage_type="cold";});
  expectCode("mechanics.discipline_save",candidate=>{candidate.entities.find((item:any)=>item.id==="flare").mechanics.surfaces[0].tiers[0].steps.find((step:any)=>step.kind==="saving_throw").ability="constitution";});
});

test("canonical D&D facts are concrete or explicitly feature-local and runtime-dependent",async()=>{
  const {authority}=await loadAuthority(),mapping={kind:"discipline_mapping",by_discipline:{cryokinesis:"constitution",pyrokinesis:"dexterity",psychokinesis:"strength",electrokinesis:"charisma"}} as const;
  const json=JSON.stringify(authority.entities.flatMap(entity=>entity.mechanics?[entity.mechanics]:[]));assert.doesNotMatch(json,/"damage_type":"discipline"|"ability":"discipline_signature"/);
  for(const [id,damage,save] of [["absolute_zero","cold","constitution"],["flare","fire","dexterity"],["telekinetic_slam","force","strength"],["electron_burst","lightning","charisma"]] as const){const mechanics=authority.entities.find(entity=>entity.id===id)!.mechanics!,text=JSON.stringify(mechanics);assert.match(text,new RegExp(`"damage_type":"${damage}"`),id);assert.match(text,new RegExp(`"ability":"${save}"`),id);}
  for(const id of ["advanced_phase_step","advanced_improved_phase_step"]){const surface=authority.entities.find(entity=>entity.id===id)!.mechanics!.surfaces[0]!,saves=surface.tiers!.flatMap(tier=>(tier.steps??[]).filter((step):step is Extract<typeof step,{kind:"saving_throw"}>=>step.kind==="saving_throw").map(step=>step.ability));assert.ok(saves.length>0,id);assert.ok(saves.every(save=>JSON.stringify(save)===JSON.stringify(mapping)),id);}
  const improved=authority.entities.find(entity=>entity.id==="advanced_improved_phase_step")!.mechanics!.surfaces[0]!,dynamic={kind:"manifested_strike_damage_type"};assert.deepEqual(improved.damage_type,dynamic);for(const tier of improved.tiers!)for(const step of tier.steps![0]!.kind==="saving_throw"?tier.steps![0]!.failure:[])if(step.kind==="damage")assert.deepEqual(step.damage_type,dynamic);
});

test("Branching Bolt neutral targeting preserves the released 15-foot arc",async()=>{
  const {authority}=await loadAuthority(),branchingBolt=authority.entities.find(entity=>entity.id==="branching_bolt");assert.ok(branchingBolt?.mechanics);
  const ranges=branchingBolt.mechanics.surfaces.flatMap(surface=>(surface.tiers??[]).map(tier=>"within_feet" in tier.targeting?tier.targeting.within_feet:null));
  assert.deepEqual(ranges,[15,15,15]);
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

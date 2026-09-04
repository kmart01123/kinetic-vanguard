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
const intentionallyChangedIds=new Set(["advanced_phase_step","advanced_improved_phase_step"]);
const unchangedLegacySubset=(rows:any[])=>structuredClone(rows.filter(row=>!intentionallyChangedIds.has(row.entity_id)));
const legacyCalculatorView=(features:any[])=>unchangedLegacySubset(features);
const legacyHarnessView=(rules:any[])=>{const disciplineAliases=new Set(["glacial_spike","snow_chains","frozen_ground","arctic_tempest","absolute_zero","ember_bolt","thermal_fracture","telekinetic_shove","vectored_thrust","static_discharge"]);return unchangedLegacySubset(rules).map((rule:any)=>{if(disciplineAliases.has(rule.entity_id))rule.damage_type="discipline";if(rule.entity_id==="advanced_beguile")delete rule.targeting_by_tier;return rule;});};
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
  assert.equal(hash(projection.features),"a82b25a23fad5ba0daa46188b06ee0fabe363d0738cd954bfaf90fc2b67320af");
  assert.equal(hash(projection.harness_mechanics.feature_rules),"9633ae80ebf3850e836048a40261ef971c024e41a70ac6e289b689b5a364f403");
  const legacyCalculator=legacyCalculatorView(projection.features),legacyHarness=legacyHarnessView(projection.harness_mechanics.feature_rules);assert.ok(legacyCalculator.every((feature:any)=>!intentionallyChangedIds.has(feature.entity_id)));assert.ok(legacyHarness.every((rule:any)=>!intentionallyChangedIds.has(rule.entity_id)));
  assert.equal(hash(legacyCalculator),"2e0814e8b20ab395aff14cf24b558082b3c12ffa32ded9ef6ef61f2dafb00afa");
  assert.equal(hash(legacyHarness),"e914f07c839070241281297e3471092c228c936f57e01e80961cd23a0140a0ae");
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

test("canonical D&D facts are concrete",async()=>{
  const {authority}=await loadAuthority();
  const json=JSON.stringify(authority.entities.flatMap(entity=>entity.mechanics?[entity.mechanics]:[]));assert.doesNotMatch(json,/"damage_type":"discipline"|"ability":"discipline_signature"/);
  for(const [id,damage,save] of [["absolute_zero","cold","constitution"],["flare","fire","dexterity"],["telekinetic_slam","force","strength"],["electron_burst","lightning","charisma"]] as const){const mechanics=authority.entities.find(entity=>entity.id===id)!.mechanics!,text=JSON.stringify(mechanics);assert.match(text,new RegExp(`"damage_type":"${damage}"`),id);assert.match(text,new RegExp(`"ability":"${save}"`),id);}
  assert.doesNotMatch(json,/discipline_mapping/);
  assert.doesNotMatch(json,/"damage_type":\{/);
});

test("Phase Step family uses fixed Strength saves and force damage without changing its other mechanics",async()=>{
  const [{authority},source]=await Promise.all([loadAuthority(),readFile("KineticVanguard.yaml","utf8")]),raw=YAML.parse(source) as any;
  const entity=(id:string)=>authority.entities.find(item=>item.id===id)!,rawEntity=(id:string)=>raw.entities.find((item:any)=>item.id===id),surface=(id:string)=>entity(id).mechanics!.surfaces[0]!,saving=(tier:any)=>tier.steps?.find((step:any)=>step.kind==="saving_throw");
  const phase=surface("advanced_phase_step"),[phase0,phase1,phase2]=phase.tiers!;
  assert.equal(phase.delivery.kind,"standalone");assert.equal(phase.delivery.kind==="standalone"&&phase.delivery.activation,"bonus_action");
  assert.deepEqual([phase0!.targeting,phase1!.targeting],[{topology:"self",kind:"self"},{topology:"self",kind:"self"}]);assert.equal(phase0!.steps,undefined);assert.equal(phase1!.steps,undefined);
  assert.deepEqual(phase2!.targeting,{topology:"area",kind:"area",shape:"sphere",origin:"departure_or_arrival_space",radius_feet:5,selection:"creatures_of_choice"});
  const phaseSave=saving(phase2);assert.equal(phaseSave.ability,"strength");assert.deepEqual(phaseSave.failure,[{kind:"reaction_denial",package_id:"control_0",duration:"until_start_next_turn"}]);assert.equal(JSON.stringify(phase).includes("damage"),false);assert.doesNotMatch(JSON.stringify(phase),/discipline_mapping/);

  const improved=surface("advanced_improved_phase_step"),dice=[2,3,4];assert.equal(improved.delivery.kind,"standalone");assert.equal(improved.delivery.kind==="standalone"&&improved.delivery.activation,"bonus_action");assert.equal(improved.damage_type,"force");
  improved.tiers!.forEach((tier,index)=>{assert.deepEqual(tier.targeting,{topology:"area",kind:"area",shape:"sphere",origin:"departure_or_arrival_space",radius_feet:5,selection:"creatures_of_choice",maximum_targets:3,excludes_self:true});const save=saving(tier);assert.equal(save.ability,"strength");assert.equal(save.damage_on_success,"half");const damage=save.failure.find((step:any)=>step.kind==="damage");assert.deepEqual(damage,{kind:"damage",damage_type:"force",value:{kind:"dice",count:dice[index],sides:10}});if(tier.tier===2)assert.deepEqual(save.failure.at(-1),{kind:"reaction_denial",package_id:"control_0",duration:"until_start_next_turn"});else assert.equal(save.failure.some((step:any)=>step.kind==="reaction_denial"),false);});
  assert.doesNotMatch(JSON.stringify(improved),/discipline_mapping/);

  const phaseText=JSON.stringify(rawEntity("advanced_phase_step").content),improvedText=JSON.stringify(rawEntity("advanced_improved_phase_step").content);assert.match(phaseText,/T0 Base: Teleport up to 15 feet.*does not provoke Opportunity Attacks/);assert.match(phaseText,/T1 Overload: Changes from Tier 0: The teleport range increases to 30 feet/);assert.match(phaseText,/Strength saving throw against your Psionic saving throw Difficulty Class/);assert.match(improvedText,/Teleport up to 30 feet to an unoccupied space you can see/);assert.match(improvedText,/Choose either the space you left or the space where you appear as the origin of a 5-foot-radius Sphere/);assert.match(improvedText,/Choose up to three other creatures in the Sphere/);assert.match(improvedText,/Strength saving throw against your Psionic saving throw Difficulty Class, taking 2d10 force damage on a failed save or half as much on a successful one/);assert.match(improvedText,/does not provoke Opportunity Attacks, and you are unaffected by the burst/);assert.doesNotMatch(`${phaseText}${improvedText}`,/Discipline.s signature saving throw|Manifested Strike.s damage type/);

  const projection=deriveCalculatorProjection(authority),calculator=(id:string)=>projection.features.find(item=>item.entity_id===id)!,harness=(id:string)=>projection.harness_mechanics.feature_rules.find(item=>item.entity_id===id)!;
  assert.deepEqual(calculator("advanced_phase_step").tiers!.map(tier=>tier.save),[undefined,undefined,"strength"]);assert.deepEqual(calculator("advanced_improved_phase_step").tiers!.map(tier=>[tier.save,tier.damage]),[["strength",{kind:"dice",resolution:"half_on_success",count:2,sides:10}],["strength",{kind:"dice",resolution:"half_on_success",count:3,sides:10}],["strength",{kind:"dice",resolution:"half_on_success",count:4,sides:10}]]);
  assert.deepEqual(harness("advanced_phase_step").control_tiers?.map(tier=>[tier.tier,tier.save,tier.effects]),[[2,"strength",[{gate:"on_failed_save",outcomes:["reaction_denial"],duration:"until_start_next_turn"}]]]);assert.equal(harness("advanced_improved_phase_step").damage_type,"force");assert.deepEqual(harness("advanced_improved_phase_step").control_tiers?.map(tier=>[tier.tier,tier.save]),[[2,"strength"]]);
  for(const discipline of ["cryokinesis","pyrokinesis","psychokinesis","electrokinesis"]){assert.equal(harness("advanced_phase_step").control_tiers?.[0]?.save,"strength",discipline);assert.equal(harness("advanced_improved_phase_step").damage_type,"force",discipline);assert.equal(harness("advanced_improved_phase_step").control_tiers?.[0]?.save,"strength",discipline);}
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

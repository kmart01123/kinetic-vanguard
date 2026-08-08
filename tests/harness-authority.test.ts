import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { mkdtemp,readFile,rm,writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { stringify } from "yaml";
import { createControlAuthorityProjectionV2,createHarnessProjection } from "../src/harness-authority.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

test("harness projection reads the real authority and joins mechanics by stable entity ID",async()=>{
  const projection=await createHarnessProjection();
  assert.equal(projection.rules_version,"14.1.0");assert.equal(projection.schema_version,"2.2.0");assert.match(projection.authority_path,/\/KineticVanguard\.yaml$/);
  assert.deepEqual(projection.core.action_economy,{standalone_psionic_action_limit_per_turn:1,action_surge_allows_additional_standalone_psionic_action:false});
  assert.deepEqual(projection.disciplines.map(item=>item.id).sort(),["cryokinesis","electrokinesis","psychokinesis","pyrokinesis"]);
  assert.equal(new Set(projection.features.map(item=>item.entity_id)).size,projection.features.length);
  assert.ok(projection.features.every(item=>Number.isInteger(item.minimum_level)&&Number.isInteger(item.psi_cost)&&!Object.hasOwn(item,"title")));
  const flare=projection.features.find(item=>item.entity_id==="flare")!;assert.equal(flare.minimum_level,15);assert.equal(flare.psi_cost,3);assert.equal(flare.damage_tiers.length,3);assert.equal(flare.control_tiers?.length,3);
});

test("control authority v2 projection is explicit, complete, deterministic, and does not coerce legacy labels",async()=>{
  const [first,second]=await Promise.all([createControlAuthorityProjectionV2(),createControlAuthorityProjectionV2()]);
  assert.deepEqual(first,second);assert.equal(first.projection_version,"2.0.0");assert.equal(first.schema_version,"2.2.0");assert.equal(first.rules_version,"14.1.0");
  assert.match(first.authority_path,/\/KineticVanguard\.yaml$/);assert.match(first.authority_sha256,/^[a-f0-9]{64}$/);assert.deepEqual(first.supported_level_range,{minimum:3,maximum:20});
  assert.equal(first.control_authority.contract_version,"2.0.0");assert.equal(first.control_authority.ledger.length,49);
  assert.deepEqual(first.coverage,{total:49,modeled:9,excluded_by_profile:14,unsupported_error:26,benchmark_ready:false});
  const keys=first.control_authority.ledger.map(item=>`${item.entity_id}:T${item.tier}`);assert.deepEqual(keys,[...keys].sort((left,right)=>left<right?-1:left>right?1:0));
  assert.ok(first.control_authority.ledger.some(item=>item.disposition==="modeled"));assert.ok(first.control_authority.ledger.some(item=>item.disposition==="excluded_by_profile"));assert.ok(first.control_authority.ledger.some(item=>item.disposition==="unsupported_error"));
  assert.equal(Object.hasOwn(first,"features"),false);assert.equal(JSON.stringify(first.control_authority).includes('"control_tiers"'),false);
});

test("control authority v2 canonical fixtures preserve representative mechanics",async()=>{
  const {control_authority}=await createControlAuthorityProjectionV2();
  const modeled=(entityId:string,tier:0|1|2)=>{
    const entry=control_authority.ledger.find(item=>item.entity_id===entityId&&item.tier===tier);
    assert.ok(entry,entityId+":T"+tier);
    if(entry.disposition!=="modeled")assert.fail(entityId+":T"+tier+" is not modeled");
    return entry.model;
  };
  const component=(model:ReturnType<typeof modeled>,componentId:string)=>{
    const found=model.components.find(item=>item.component_id===componentId);assert.ok(found,componentId);return found;
  };
  const resolution=(model:ReturnType<typeof modeled>,gateId:string)=>{
    const found=model.resolutions.find(item=>item.gate_id===gateId);assert.ok(found,gateId);return found;
  };
  const branch=(gate:ReturnType<typeof resolution>,outcome:string)=>{
    const found=gate.resolution.branches.find(item=>item.outcome===outcome);assert.ok(found,outcome);return found;
  };

  const glacial=modeled("glacial_spike",1);
  const glacialReduction=component(glacial,"glacial_spike_speed_reduction");
  assert.deepEqual(glacialReduction.magnitude,{kind:"speed_reduction",reduction:{kind:"flat_feet",value:10},movement_modes:["walk","fly","swim","climb","burrow"]});
  assert.deepEqual(glacialReduction.cadence,{apply:["hit"],repeat:["save"],end:["save"]});
  assert.equal(control_authority.policy_inputs.action_economy.attack_rider_declaration,"before_attack_roll");
  assert.deepEqual(glacial.root_gate_ids,["glacial_spike_t1_attack"]);
  assert.deepEqual({declaration:glacial.policy.declaration,psi_cost:glacial.policy.psi_cost,overload_tier:glacial.policy.overload_tier},{declaration:"declaration",psi_cost:0,overload_tier:1});
  const glacialHit=resolution(glacial,"glacial_spike_t1_attack");assert.equal(glacialHit.trigger,"hit");
  assert.deepEqual(branch(glacialHit,"attack_hit").applies,["glacial_spike_speed_reduction"]);
  assert.deepEqual(branch(glacialHit,"attack_hit").next_gate_ids,["glacial_spike_t1_save"]);
  assert.deepEqual(branch(glacialHit,"attack_miss").next_gate_ids,[]);
  const glacialSave=resolution(glacial,"glacial_spike_t1_save");
  assert.deepEqual(branch(glacialSave,"save_success"),{branch_id:"glacial_spike_t1_success",outcome:"save_success",applies:[],replaces:[],terminates:[],refreshes:["glacial_spike_speed_reduction"],next_gate_ids:[]});
  assert.deepEqual(branch(glacialSave,"save_failure"),{branch_id:"glacial_spike_t1_failure",outcome:"save_failure",applies:["glacial_spike_speed_zero"],replaces:["glacial_spike_speed_reduction"],terminates:[],refreshes:[],next_gate_ids:[]});

  for(const tier of [1,2] as const){
    const model=modeled("glacial_spike",tier),attack=resolution(model,"glacial_spike_t"+tier+"_attack"),save=resolution(model,"glacial_spike_t"+tier+"_save");
    assert.deepEqual(model.root_gate_ids,["glacial_spike_t"+tier+"_attack"]);
    assert.deepEqual(branch(attack,"attack_hit").next_gate_ids,["glacial_spike_t"+tier+"_save"]);
    assert.deepEqual(branch(attack,"attack_miss").next_gate_ids,[]);
    assert.ok(save.resolution.branches.every(item=>item.next_gate_ids.length===0));
  }

  const shoveMagnitudes=([0,1,2] as const).map(tier=>{
    const model=modeled("telekinetic_shove",tier),magnitude=component(model,"telekinetic_shove_forced_movement").magnitude;
    if(magnitude.kind!=="forced_movement")assert.fail("telekinetic shove must force movement");
    const attack=resolution(model,"telekinetic_shove_t"+tier+"_attack"),save=resolution(model,"telekinetic_shove_t"+tier+"_save");
    assert.deepEqual(model.root_gate_ids,["telekinetic_shove_t"+tier+"_attack"]);
    assert.deepEqual(branch(attack,"attack_hit").next_gate_ids,["telekinetic_shove_t"+tier+"_save"]);
    assert.deepEqual(branch(attack,"attack_miss").next_gate_ids,[]);
    assert.ok(save.resolution.branches.every(item=>item.next_gate_ids.length===0));
    assert.deepEqual({declaration:model.policy.declaration,psi_cost:model.policy.psi_cost,overload_tier:model.policy.overload_tier},{declaration:"declaration",psi_cost:0,overload_tier:tier});
    return {distance_feet:magnitude.distance_feet,distance_mode:magnitude.distance_mode,movement_mode:magnitude.movement_mode,direction:magnitude.direction,destination:magnitude.destination};
  });
  assert.deepEqual(shoveMagnitudes,[
    {distance_feet:10,distance_mode:"exact",movement_mode:"push",direction:"controller_choice",destination:"legal_destination"},
    {distance_feet:15,distance_mode:"exact",movement_mode:"push",direction:"controller_choice",destination:"legal_destination"},
    {distance_feet:20,distance_mode:"exact",movement_mode:"push",direction:"controller_choice",destination:"legal_destination"}
  ]);
  const masteryPush=control_authority.masteries.find(item=>item.mastery_id==="mastery_push");assert.ok(masteryPush);
  const masteryPushMagnitude=masteryPush.component.magnitude;if(masteryPushMagnitude.kind!=="forced_movement")assert.fail("mastery push must force movement");
  assert.deepEqual(masteryPushMagnitude,{kind:"forced_movement",distance_feet:10,distance_mode:"up_to",movement_mode:"push",direction:"straight_away_from_controller",destination:"legal_destination"});

  const ball=modeled("ball_lightning",2);
  const ballSelector=ball.target_selectors.find(item=>item.selector_id==="ball_lightning_area_targets");assert.ok(ballSelector);
  assert.deepEqual(ballSelector.restrictions,[]);
  assert.deepEqual(ballSelector.area,{area_id:"ball_lightning_sphere",shape:"sphere",origin:"selected_point",radius_feet:30,persistent:true,triggers:["entry","start_turn"],exit_behavior:"ends_area_effects",entry_policy:{frequency:"once_per_turn",moved_area_counts_as_entry:false},movement:{kind:"controller_reposition",controller_action:"bonus_action",distance_feet:15}});
  assert.deepEqual(ball.root_gate_ids,["ball_lightning_entry_save","ball_lightning_start_turn_save"]);
  assert.ok(ball.resolutions.flatMap(item=>item.resolution.branches).every(item=>item.next_gate_ids.length===0));
  assert.deepEqual(component(ball,"ball_lightning_reaction_denial").cadence,{apply:["entry","start_turn"],repeat:["entry","start_turn"],end:["exit"]});
  assert.deepEqual(ball.resolutions.map(item=>({trigger:item.trigger,gate_scope:item.gate_scope})),[
    {trigger:"entry",gate_scope:"independent_per_target"},
    {trigger:"start_turn",gate_scope:"independent_per_target"}
  ]);
  assert.deepEqual(ball.concentration,{kind:"required",startup:"on_resolution",occupancy:"one_controller_slot",replacement:"new_effect_ends_existing",maximum_duration:{value:1,unit:"minute"},termination:["failed_concentration_save","controller_incapacitated","controller_death","duration_expires","voluntary_end"]});

  const levitation=modeled("mass_levitation",0);
  assert.deepEqual(levitation.root_gate_ids,["mass_levitation_initial_saves","mass_levitation_repeat_saves"]);
  assert.ok(levitation.resolutions.flatMap(item=>item.resolution.branches).every(item=>item.next_gate_ids.length===0));
  assert.deepEqual(levitation.target_selectors[0]!.count,{kind:"weighted_slots",slots:5,size_costs:{tiny:1,small:1,medium:1,large:2}});
  assert.deepEqual(levitation.target_selectors[0]!.restrictions,[{kind:"visibility",requirement:"controller_can_see"},{kind:"maximum_size",size:"large_or_smaller"},{kind:"unique_targets",required:true}]);
  assert.deepEqual(component(levitation,"mass_levitation_initial_lift").magnitude,{kind:"forced_movement",distance_feet:30,distance_mode:"exact",movement_mode:"lift",direction:"vertical_up",destination:"legal_unoccupied_space"});
  const repeatSave=resolution(levitation,"mass_levitation_repeat_saves"),repeatSaveResolution=repeatSave.resolution;
  if(repeatSaveResolution.kind!=="saving_throw")assert.fail("mass levitation repeat gate must be a saving throw");
  assert.deepEqual({
    trigger:repeatSave.trigger,
    gate_scope:repeatSave.gate_scope,
    kind:repeatSaveResolution.kind,
    ability:repeatSaveResolution.ability,
    success_terminates:branch(repeatSave,"save_success").terminates,
    failure_refreshes:branch(repeatSave,"save_failure").refreshes
  },{trigger:"repeat_save",gate_scope:"independent_per_target",kind:"saving_throw",ability:"strength",success_terminates:["mass_levitation_restrained"],failure_refreshes:["mass_levitation_restrained"]});

  const forked=modeled("forked_lightning",2);
  assert.deepEqual(forked.inheritance,{kind:"resolved",source_tier:1});
  assert.deepEqual(forked.root_gate_ids,["forked_lightning_independent_saves"]);
  assert.deepEqual(forked.target_selectors.map(item=>item.restrictions),[[{kind:"visibility",requirement:"controller_can_see"}],[{kind:"excludes_primary_target",required:true}]]);
  assert.deepEqual(forked.target_selectors.map(({selector_id,role,count,range})=>({selector_id,role,count,range})),[
    {selector_id:"forked_lightning_primary",role:"primary",count:{kind:"fixed",value:1},range:{feet:60,origin:"controller"}},
    {selector_id:"forked_lightning_secondary",role:"secondary",count:{kind:"up_to",value:5},range:{feet:30,origin:"primary_target"}}
  ]);
  const forkedSave=resolution(forked,"forked_lightning_independent_saves"),forkedSaveResolution=forkedSave.resolution;
  if(forkedSaveResolution.kind!=="saving_throw")assert.fail("forked lightning gate must be a saving throw");
  assert.deepEqual({selector_ids:forkedSave.selector_ids,trigger:forkedSave.trigger,gate_scope:forkedSave.gate_scope,kind:forkedSaveResolution.kind,ability:forkedSaveResolution.ability},{selector_ids:["forked_lightning_primary","forked_lightning_secondary"],trigger:"save",gate_scope:"independent_per_target",kind:"saving_throw",ability:"charisma"});

  assert.deepEqual(control_authority.ledger.find(item=>item.entity_id==="advanced_beguile"&&item.tier===0),{entity_id:"advanced_beguile",tier:0,disposition:"excluded_by_profile",profile_id:"official_default_25_percent_hp",reason:"selectable_advanced_training_disabled"});
  assert.deepEqual(control_authority.ledger.find(item=>item.entity_id==="absolute_zero"&&item.tier===0),{entity_id:"absolute_zero",tier:0,disposition:"unsupported_error",reason:"pending_authority_population"});
});

test("Wisdom saving throws pass the real v2 JSON Schema and semantic validator",async()=>{
  const {authority}=await loadAuthority(),candidate=structuredClone(authority) as any;
  const forked=candidate.calculator.harness_mechanics.control_authority_v2.ledger.find((row:any)=>row.disposition==="modeled"&&row.model.effect_id==="forked_lightning_t2_control");
  forked.model.resolutions[0].resolution.ability="wisdom";
  const directory=await mkdtemp(join(tmpdir(),"kv-wisdom-authority-")),authorityPath=join(directory,"authority.yaml");
  try{
    await writeFile(authorityPath,stringify(candidate),"utf8");
    const loaded=await loadAuthority(authorityPath);
    assert.deepEqual(loaded.diagnostics,[]);
    assert.deepEqual(validateSemantics(loaded.authority).filter(item=>item.severity==="error"),[]);
  }finally{await rm(directory,{recursive:true,force:true});}
});

test("projection-version CLI emits v2 explicitly and rejects unknown versions",()=>{
  const executable="node_modules/.bin/tsx",base=["src/harness-authority.ts"];
  const v2=spawnSync(executable,[...base,"--projection-version","2.0.0"],{encoding:"utf8"});assert.equal(v2.status,0,v2.stderr);assert.equal(JSON.parse(v2.stdout).projection_version,"2.0.0");
  const unknown=spawnSync(executable,[...base,"--projection-version","9.0.0"],{encoding:"utf8"});assert.notEqual(unknown.status,0);assert.match(unknown.stderr,/Unsupported projection version: 9\.0\.0/);
});

test("harness semantic mutations fail with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  expectCode("harness.action_economy",candidate=>{candidate.calculator.harness_mechanics.action_economy.action_surge_allows_additional_standalone_psionic_action=true;});
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

test("control authority v2 semantic mutations fail with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const v2=(candidate:any)=>candidate.calculator.harness_mechanics.control_authority_v2;
  const modeled=(candidate:any,predicate:(model:any)=>boolean)=>v2(candidate).ledger.find((item:any)=>item.disposition==="modeled"&&predicate(item.model));
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  expectCode("control_v2.version",candidate=>{v2(candidate).contract_version="9.0.0";});
  expectCode("control_v2.ids",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.length>1);entry.model.components[1].component_id=entry.model.components[0].component_id;});
  expectCode("control_v2.branch",candidate=>{const entry=modeled(candidate,(model:any)=>model.resolutions.some((gate:any)=>gate.resolution.kind==="saving_throw"));const gate=entry.model.resolutions.find((item:any)=>item.resolution.kind==="saving_throw");gate.resolution.branches=gate.resolution.branches.filter((branch:any)=>branch.outcome!=="save_success");});
  expectCode("control_v2.branch",candidate=>{const entry=modeled(candidate,(model:any)=>model.resolutions.some((gate:any)=>gate.resolution.kind==="saving_throw"));const gate=entry.model.resolutions.find((item:any)=>item.resolution.kind==="saving_throw"),extra=structuredClone(gate.resolution.branches[0]);extra.branch_id+="_extra";extra.outcome="other";gate.resolution.branches.push(extra);});
  expectCode("control_v2.branch",candidate=>{const entry=modeled(candidate,(model:any)=>model.resolutions.some((gate:any)=>gate.resolution.branches.some((branch:any)=>branch.applies.length)));const branch=entry.model.resolutions.flatMap((gate:any)=>gate.resolution.branches).find((item:any)=>item.applies.length);branch.replaces.push(branch.applies[0]);});
  expectCode("control_v2.branch",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.length>1),componentId=entry.model.components[0].component_id;for(const branch of entry.model.resolutions.flatMap((gate:any)=>gate.resolution.branches))for(const field of ["applies","replaces","terminates","refreshes"])branch[field]=branch[field].filter((id:string)=>id!==componentId);});
  expectCode("control_v2.branch",candidate=>{const entry=modeled(candidate,(model:any)=>model.resolutions.some((gate:any)=>gate.resolution.kind==="attack_roll"));entry.model.resolutions.find((gate:any)=>gate.resolution.kind==="attack_roll").resolution.ability="strength";});
  expectCode("control_v2.magnitude",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.some((item:any)=>item.magnitude.kind==="forced_movement"));const component=entry.model.components.find((item:any)=>item.magnitude.kind==="forced_movement");delete component.magnitude.distance_feet;});
  expectCode("control_v2.magnitude",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.some((item:any)=>item.magnitude.kind==="speed_reduction"));const component=entry.model.components.find((item:any)=>item.magnitude.kind==="speed_reduction");component.magnitude.reduction={kind:"fraction",numerator:1,denominator:1};});
  expectCode("control_v2.magnitude",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.some((item:any)=>item.magnitude.kind==="attack_disadvantage"));const component=entry.model.components.find((item:any)=>item.magnitude.kind==="attack_disadvantage");component.magnitude.count=1;});
  expectCode("control_v2.magnitude",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.some((item:any)=>item.magnitude.kind==="speed_zero"));entry.model.components.find((item:any)=>item.magnitude.kind==="speed_zero").magnitude.movement_modes=["teleport"];});
  expectCode("control_v2.timing",candidate=>{const entry=modeled(candidate,(model:any)=>model.components.some((item:any)=>item.duration.kind==="relative"));const component=entry.model.components.find((item:any)=>item.duration.kind==="relative");delete component.duration.owner;});
  expectCode("control_v2.timing",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="ball_lightning_t2_control");entry.model.components.find((item:any)=>item.component_id==="ball_lightning_reaction_denial").cadence.apply=["start_turn"];});
  expectCode("control_v2.timing",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="glacial_spike_t1_control");entry.model.components.find((item:any)=>item.component_id==="glacial_spike_speed_reduction").cadence.repeat=[];});
  expectCode("control_v2.timing",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="glacial_spike_t1_control");entry.model.components.find((item:any)=>item.component_id==="glacial_spike_speed_reduction").cadence.end=[];});
  expectCode("control_v2.area",candidate=>{const entry=modeled(candidate,(model:any)=>model.target_selectors.some((item:any)=>item.area));const area=entry.model.target_selectors.find((item:any)=>item.area).area;delete area.radius_feet;delete area.length_feet;});
  expectCode("control_v2.area",candidate=>{const entry=modeled(candidate,(model:any)=>model.target_selectors.some((item:any)=>item.area));const area=entry.model.target_selectors.find((item:any)=>item.area).area;area.length_feet=30;});
  expectCode("control_v2.concentration",candidate=>{const entry=modeled(candidate,(model:any)=>model.concentration.kind==="required");entry.model.concentration.termination.pop();});
  expectCode("control_v2.target",candidate=>{const entry=modeled(candidate,()=>true);entry.model.components[0].target_selector_ids=["missing_selector"];});
  expectCode("control_v2.inheritance",candidate=>{const entry=modeled(candidate,(model:any)=>model.inheritance.kind==="resolved");entry.model.inheritance.source_tier=entry.tier;});
  expectCode("control_v2.stacking",candidate=>{const entry=modeled(candidate,()=>true);entry.model.components[0].stacking.dominates_component_ids=["missing_component"];});
  expectCode("control_v2.stacking",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="glacial_spike_t1_control"),group=entry.model.relationships.replacement_groups[0],component=entry.model.components.find((item:any)=>item.component_id===group.component_ids[0]);delete component.stacking.replacement_group;});
  expectCode("control_v2.stacking",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="glacial_spike_t2_control"),relation=entry.model.relationships.dominance.find((item:any)=>entry.model.components.find((component:any)=>component.component_id===item.dominant_component_id).stacking.mode==="replace"),component=entry.model.components.find((item:any)=>item.component_id===relation.dominant_component_id);component.stacking.dominates_component_ids=[];});
  expectCode("control_v2.stacking",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="glacial_spike_t2_control");entry.model.components.find((item:any)=>item.component_id==="glacial_spike_speed_zero").stacking.mode="independent";});
  expectCode("control_v2.stacking",candidate=>{const entry=modeled(candidate,(model:any)=>model.effect_id==="telekinetic_shove_t0_control");entry.model.components[0].stacking.mode="replace";});
  expectCode("control_v2.coverage",candidate=>{v2(candidate).ledger.pop();});
  expectCode("control_v2.disposition",candidate=>{const entry=v2(candidate).ledger.find((item:any)=>item.disposition==="excluded_by_profile");entry.profile_id="wrong_profile";});
  expectCode("control_v2.timing",candidate=>{const entity=candidate.entities.find((item:any)=>item.id==="ball_lightning"),entry=modeled(candidate,(model:any)=>model.effect_id==="ball_lightning_t2_control");entity.psi_cost=6;entry.model.policy.psi_cost=6;});
  expectCode("control_v2.concentration",candidate=>{const entity=candidate.entities.find((item:any)=>item.id==="ball_lightning"),entry=modeled(candidate,(model:any)=>model.effect_id==="ball_lightning_t2_control");entity.requires_concentration=false;entry.model.concentration={kind:"none"};});
});

test("official harness source is positive input while imports and generated outputs remain excluded",async()=>{
  const inputs=JSON.parse(await readFile("build/inputs.json","utf8")).inputs as Array<{path:string;role:string}>;const paths=inputs.map(input=>input.path);
  for(const required of ["src/harness-authority.ts","harness/authority.py","harness/damage_harness.py","harness/control_harness.py","harness/readme_matrices.py","harness/comparison_report.py","harness/config/benchmark.json","harness/comparators/fighter-subclasses.json","harness/data/srd_targets.csv","harness/provenance/legacy-import.json","harness/tests/test_authority_v2.py","harness/tests/test_authority_v2_parity.py","harness/tests/test_harness.py","harness/tests/test_readme_matrices.py","tests/control-authority-v2-parity.test.ts","tests/fixtures/control-authority-v2-parity.json"])assert.ok(paths.includes(required),required);
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

import assert from "node:assert/strict";
import test from "node:test";
import {createControlAuthorityProjectionV2} from "../src/harness-authority.js";
import {loadAuthority} from "../src/load.js";
import type {ControlDurationV2,ControlEventV2} from "../src/types.js";

type AnyRecord=Record<string,any>;
const END_NEXT={kind:"relative",owner:"controller",anchor:"end_turn",offset_turns:1};
const START_NEXT={kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1};
const CONTROLLER_END={kind:"turn",owner:"controller",turn_anchor:"end"};
const CONTROLLER_START={kind:"turn",owner:"controller",turn_anchor:"start"};
const TARGET_START={kind:"turn",owner:"target",turn_anchor:"start"};
const ENTRY={kind:"entry",owner:"any_creature",turn_anchor:"during_turn"};
const TRIGGERING_TURN_END={kind:"relative",owner:"triggering_turn",anchor:"end_turn",offset_turns:0} satisfies ControlDurationV2;
const TRIGGERING_TURN_END_EVENT={kind:"turn",owner:"triggering_turn",turn_anchor:"end"} satisfies ControlEventV2;
// @ts-expect-error triggering-turn events are restricted to the end anchor
const INVALID_TRIGGERING_TURN_START_EVENT:ControlEventV2={kind:"turn",owner:"triggering_turn",turn_anchor:"start"};

function modeled(control:AnyRecord,entityId:string,tier:number):AnyRecord{
  const rows=control.ledger.filter((row:AnyRecord)=>row.entity_id===entityId&&row.tier===tier);
  assert.equal(rows.length,1,`${entityId}:T${tier} must have one ledger row`);
  assert.equal(rows[0].disposition,"modeled",`${entityId}:T${tier} must be modeled`);
  return rows[0].model;
}
function components(model:AnyRecord,kind:string):AnyRecord[]{return model.components.filter((item:AnyRecord)=>item.magnitude.kind===kind);}
function conditions(model:AnyRecord,condition:string):AnyRecord[]{return components(model,"condition").filter(item=>item.magnitude.condition===condition);}
function one(values:AnyRecord[],message:string):AnyRecord{assert.equal(values.length,1,message);return values[0]!;}
function saves(model:AnyRecord,role?:string):AnyRecord[]{return model.resolutions.filter((gate:AnyRecord)=>gate.resolution.kind==="saving_throw"&&(!role||gate.resolution.role===role));}
function save(model:AnyRecord,ability:string,role:string,mode:string):AnyRecord{
  const gate=one(saves(model,role),`${model.effect_id} must have one ${role} save`);
  assert.deepEqual({ability:gate.resolution.ability,role:gate.resolution.role,mode:gate.resolution.mode},{ability,role,mode});return gate;
}
function branch(gate:AnyRecord,outcome:string):AnyRecord{return one(gate.resolution.branches.filter((item:AnyRecord)=>item.outcome===outcome),`${gate.gate_id} must have ${outcome}`);}
function assertEmptyBranch(gate:AnyRecord,outcome:string):void{const candidate=branch(gate,outcome);assert.deepEqual({applies:candidate.applies,replaces:candidate.replaces,terminates:candidate.terminates,refreshes:candidate.refreshes,next_gate_ids:candidate.next_gate_ids},{applies:[],replaces:[],terminates:[],refreshes:[],next_gate_ids:[]},gate.gate_id+" "+outcome+" must be effect-free");}
function assertTransitions(gate:AnyRecord,outcome:string,expected:Partial<Record<"applies"|"replaces"|"terminates"|"refreshes"|"next_gate_ids",string[]>>):void{const candidate=branch(gate,outcome);assert.deepEqual({applies:candidate.applies,replaces:candidate.replaces,terminates:candidate.terminates,refreshes:candidate.refreshes,next_gate_ids:candidate.next_gate_ids},{applies:expected.applies??[],replaces:expected.replaces??[],terminates:expected.terminates??[],refreshes:expected.refreshes??[],next_gate_ids:expected.next_gate_ids??[]},gate.gate_id+" "+outcome+" transitions");}
function applied(gate:AnyRecord,outcome:string,component:AnyRecord):void{assert.ok(branch(gate,outcome).applies.includes(component.component_id),`${component.component_id} must apply on ${outcome}`);}
function selector(model:AnyRecord,role:string):AnyRecord{return one(model.target_selectors.filter((item:AnyRecord)=>item.role===role),`${model.effect_id} must have one ${role} selector`);}
function hasEvent(events:AnyRecord[],expected:AnyRecord):boolean{return events.some(event=>JSON.stringify(event)===JSON.stringify(expected));}
function standalone(model:AnyRecord,psi:number,tier:number,activation="action"):void{
  assert.deepEqual({activation:model.policy.activation,declaration:model.policy.declaration,delivery:model.policy.delivery,psi_cost:model.policy.psi_cost,overload_tier:model.policy.overload_tier,blood_tax:model.policy.blood_tax,repeatability:model.policy.repeatability},{activation,declaration:{kind:"declaration"},delivery:"standalone",psi_cost:psi,overload_tier:tier,blood_tax:tier?"tier_formula":"none",repeatability:"once_per_turn"});
}
function rider(model:AnyRecord,psi:number,tier:number,repeatability="once_per_attack_action"):void{
  assert.deepEqual({activation:model.policy.activation,declaration:model.policy.declaration,delivery:model.policy.delivery,psi_cost:model.policy.psi_cost,overload_tier:model.policy.overload_tier,blood_tax:model.policy.blood_tax,repeatability:model.policy.repeatability},{activation:"on_hit",declaration:{kind:"declaration"},delivery:"attack_rider",psi_cost:psi,overload_tier:tier,blood_tax:tier?"tier_formula":"none",repeatability});
}
function assertMovement(component:AnyRecord,distance:number,distanceMode:string,axis:string):void{
  assert.deepEqual({distance_feet:component.magnitude.distance_feet,distance_mode:component.magnitude.distance_mode,axis:component.magnitude.axis},{distance_feet:distance,distance_mode:distanceMode,axis});
}
function assertMassAffectedGuards(model:AnyRecord,tier:number):void{
  const suffixes=tier===0?["repeat_saves","concentration_end"]:["repeat_saves","controller_reposition","concentration_end"];
  for(const suffix of suffixes){const gate=one(model.resolutions.filter((item:AnyRecord)=>item.gate_id==="mass_levitation_t"+tier+"_"+suffix),model.effect_id+" "+suffix+" gate");assert.deepEqual(gate.requires_active_component_ids,["mass_levitation_persistent_elevation"]);}
  const initial=one(saves(model,"initial"),model.effect_id+" initial save");assert.equal(initial.requires_active_component_ids,undefined);assertEmptyBranch(initial,"save_success");
  const initialFailure=branch(initial,"save_failure");assert.deepEqual({applies:initialFailure.applies,replaces:initialFailure.replaces,terminates:initialFailure.terminates,refreshes:initialFailure.refreshes,next_gate_ids:initialFailure.next_gate_ids},{applies:["mass_levitation_initial_lift","mass_levitation_persistent_elevation","mass_levitation_restrained"],replaces:[],terminates:[],refreshes:[],next_gate_ids:suffixes.map(suffix=>"mass_levitation_t"+tier+"_"+suffix)});
  const repeat=one(saves(model,"repeat"),model.effect_id+" repeat save");assert.equal(repeat.resolution.mode,tier===0?"normal":"disadvantage");const repeatSuccess=branch(repeat,"save_success");assert.deepEqual({applies:repeatSuccess.applies,replaces:repeatSuccess.replaces,terminates:repeatSuccess.terminates,refreshes:repeatSuccess.refreshes,next_gate_ids:repeatSuccess.next_gate_ids},{applies:["mass_levitation_fall"],replaces:[],terminates:["mass_levitation_persistent_elevation","mass_levitation_restrained"],refreshes:[],next_gate_ids:[]});
  const repeatFailure=branch(repeat,"save_failure");assert.deepEqual({applies:repeatFailure.applies,replaces:repeatFailure.replaces,terminates:repeatFailure.terminates,refreshes:repeatFailure.refreshes,next_gate_ids:repeatFailure.next_gate_ids},{applies:[],replaces:[],terminates:[],refreshes:["mass_levitation_persistent_elevation","mass_levitation_restrained"],next_gate_ids:tier===2?["mass_levitation_t2_damage_context"]:[]});
  const concentration=one(model.resolutions.filter((item:AnyRecord)=>item.gate_id==="mass_levitation_t"+tier+"_concentration_end"),model.effect_id+" concentration-end gate"),end=branch(concentration,"no_save");assert.deepEqual({applies:end.applies,replaces:end.replaces,terminates:end.terminates,refreshes:end.refreshes,next_gate_ids:end.next_gate_ids},{applies:["mass_levitation_fall"],replaces:[],terminates:["mass_levitation_persistent_elevation","mass_levitation_restrained"],refreshes:[],next_gate_ids:[]});
  if(tier>0){const reposition=one(model.resolutions.filter((item:AnyRecord)=>item.gate_id==="mass_levitation_t"+tier+"_controller_reposition"),model.effect_id+" reposition gate"),move=branch(reposition,"no_save");assert.deepEqual({applies:move.applies,replaces:move.replaces,terminates:move.terminates,refreshes:move.refreshes,next_gate_ids:move.next_gate_ids},{applies:["mass_levitation_reposition"],replaces:[],terminates:[],refreshes:[],next_gate_ids:[]});}
}

test("Control Authority v2.1 projects the complete fail-closed population",async()=>{
  const projection:any=await createControlAuthorityProjectionV2();
  assert.equal(projection.projection_version,"2.1.0");assert.equal(projection.schema_version,"3.1.0");assert.equal(projection.control_authority.contract_version,"2.1.0");
  assert.deepEqual(projection.coverage,{total:49,modeled:35,excluded_by_profile:14,unsupported_error:0,benchmark_ready:true});
  const modeledRows=projection.control_authority.ledger.filter((row:AnyRecord)=>row.disposition==="modeled");assert.equal(modeledRows.length,35);
  for(const row of modeledRows){const expectedInheritance=row.tier===0?{kind:"none"}:{kind:"resolved",source_tier:row.tier-1};assert.deepEqual(row.model.inheritance,expectedInheritance,row.entity_id+":T"+row.tier+" inheritance");const expectedMastery=row.model.policy.delivery==="standalone"?"not_applicable":row.entity_id==="telekinetic_shove"?"replaces_on_declaration":"stacks";assert.equal(row.model.policy.mastery,expectedMastery,row.entity_id+":T"+row.tier+" mastery");}
});

test("Cryokinesis population preserves all twelve canonical row mechanics",async t=>{
  const control=(await createControlAuthorityProjectionV2()).control_authority;

  for(const tier of [0,1,2])await t.test(`absolute_zero:T${tier}`,()=>{
    const model=modeled(control,"absolute_zero",tier);standalone(model,5,tier);
    const target=selector(model,"primary");assert.equal(target.selection,"controller_choice");assert.deepEqual(target.count,{kind:"fixed",value:1});assert.deepEqual(target.range,{kind:"distance",feet:60,origin:"controller"});
    const gate=save(model,"constitution","initial","normal"),speed=one(components(model,"speed_zero"),`${model.effect_id} Speed 0`);assert.deepEqual(speed.duration,END_NEXT);applied(gate,"save_failure",speed);
    const expected=tier===0?undefined:tier===1?"restrained":"stunned";
    if(expected){const condition=one(conditions(model,expected),`${model.effect_id} ${expected}`);assert.deepEqual(condition.duration,END_NEXT);applied(gate,"save_failure",condition);}
    if(tier===2){const inherited=one(conditions(model,"restrained"),"absolute_zero_t2 retains inherited Restrained definition");assert.ok(branch(gate,"save_failure").replaces.includes(inherited.component_id));assert.ok(model.relationships.dominance.some((relation:AnyRecord)=>relation.dominant_component_id===conditions(model,"stunned")[0]!.component_id&&relation.suppressed_component_ids.includes(inherited.component_id)));}assert.equal(branch(gate,"save_success").applies.includes(speed.component_id),tier===2);
  });

  for(const tier of [0,1,2])await t.test(`arctic_tempest:T${tier}`,()=>{
    const model=modeled(control,"arctic_tempest",tier);standalone(model,3,tier);
    const targets=selector(model,"all");assert.equal(targets.selection,"controller_choice");assert.deepEqual(targets.count,{kind:"up_to",value:3});assert.deepEqual(targets.range,{kind:"distance",feet:60,origin:"controller"});assert.equal(targets.gate_scope,"independent_per_target");
    const gate=save(model,"constitution","initial","normal"),expected=tier===2?"stunned":"restrained",condition=one(conditions(model,expected),`${model.effect_id} ${expected}`);
    assert.deepEqual(condition.duration,END_NEXT);applied(gate,"save_failure",condition);assert.deepEqual(branch(gate,"save_success").applies,[]);if(tier===2){const inherited=one(conditions(model,"restrained"),"arctic_tempest_t2 retains inherited Restrained definition");assert.ok(branch(gate,"save_failure").replaces.includes(inherited.component_id));assert.ok(model.relationships.dominance.some((relation:AnyRecord)=>relation.dominant_component_id===condition.component_id&&relation.suppressed_component_ids.includes(inherited.component_id)));}
  });

  for(const tier of [0,1,2])await t.test(`frozen_ground:T${tier}`,()=>{
    const model=modeled(control,"frozen_ground",tier);standalone(model,2,tier);const targets=selector(model,"all"),area=targets.area;
    assert.equal(targets.selection,"all_in_area");assert.deepEqual(targets.count,{kind:"all_eligible"});assert.deepEqual(targets.range,{kind:"area"});
    assert.deepEqual({shape:area.shape,placement:area.placement,radius_feet:area.radius_feet,height_feet:area.height_feet,persistent:area.persistent,entry_policy:area.entry_policy,movement:area.movement,exit_behavior:area.exit_behavior},{shape:"cylinder",placement:{kind:"selected_point",range:{feet:60,origin:"controller"},stationary:true},radius_feet:tier===0?15:25,height_feet:20,persistent:true,entry_policy:{frequency:"once_per_turn",moved_area_counts_as_entry:false},movement:{kind:"stationary"},exit_behavior:"none"});
    assert.ok(hasEvent(area.triggers,ENTRY));assert.ok(hasEvent(area.triggers,TARGET_START));assert.equal(model.concentration.startup,"on_activation");assert.deepEqual(model.concentration.maximum_duration,{value:1,unit:"minute"});
    const recurring=saves(model,"recurring");assert.equal(recurring.length,2);assert.ok(recurring.every(gate=>gate.resolution.ability==="constitution"&&gate.resolution.mode==="normal"&&gate.gate_scope==="independent_per_target"));for(const gate of recurring)assertEmptyBranch(gate,"save_success");
    const terrain=one(components(model,"difficult_terrain"),`${model.effect_id} difficult terrain`);assert.deepEqual(terrain.magnitude,{kind:"difficult_terrain",scope:"area",movement_cost_multiplier:2});
    const speed=one(components(model,"speed_zero"),`${model.effect_id} Speed 0`);assert.deepEqual(speed.duration,TRIGGERING_TURN_END);assert.notEqual(speed.duration.kind,"while_in_area");
    const expectedEndEvents=tier===2?[ENTRY,TARGET_START,TRIGGERING_TURN_END_EVENT]:[TRIGGERING_TURN_END_EVENT];assert.deepEqual(speed.cadence.end,expectedEndEvents,"Frozen Ground expiry cadence follows the triggering turn");
    const entryGate=one(recurring.filter((gate:AnyRecord)=>hasEvent([gate.trigger],ENTRY)),`${model.effect_id} entry save`),startGate=one(recurring.filter((gate:AnyRecord)=>hasEvent([gate.trigger],TARGET_START)),`${model.effect_id} start-turn save`);assert.deepEqual(entryGate.trigger,ENTRY);assert.deepEqual(startGate.trigger,TARGET_START);
    const resolvedExpiryOwner=(triggeringTurnOwner:string):string=>speed.duration.owner==="triggering_turn"?triggeringTurnOwner:speed.duration.owner;assert.equal(resolvedExpiryOwner("another_creature"),"another_creature","forced entry expires with the other creature triggering turn");assert.equal(resolvedExpiryOwner("target"),"target","entry during the affected target own turn expires with that turn");assert.equal(resolvedExpiryOwner(startGate.trigger.owner),"target","start-turn exposure expires with that target turn");
    if(tier===2){const restrained=one(conditions(model,"restrained"),`${model.effect_id} Restrained`);assert.deepEqual(restrained.duration,END_NEXT);}
  });

  for(const tier of [0,1,2])await t.test(`snow_chains:T${tier}`,()=>{
    const model=modeled(control,"snow_chains",tier);rider(model,2,tier);const speed=one(components(model,"speed_zero"),`${model.effect_id} Speed 0`);
    const attack=one(model.resolutions.filter((item:AnyRecord)=>item.resolution.kind==="attack_roll"),model.effect_id+" attack gate");assertEmptyBranch(attack,"attack_miss");
    assert.deepEqual(speed.duration,END_NEXT);assert.ok(speed.cadence.apply.some((event:AnyRecord)=>event.kind==="hit"));
    const gate=save(model,"constitution","initial","normal"),expected=tier===2?"stunned":"restrained",condition=one(conditions(model,expected),`${model.effect_id} ${expected}`);applied(gate,"save_failure",condition);assert.ok(!branch(gate,"save_success").terminates.includes(speed.component_id));
    if(tier>0){const denial=one(components(model,"reaction_denial"),`${model.effect_id} reaction denial`);assert.deepEqual(denial.duration,START_NEXT);applied(gate,"save_failure",denial);assertEmptyBranch(gate,"save_success");}
  });
});

test("Pyrokinesis population preserves all three Flare row mechanics",async t=>{
  const control=(await createControlAuthorityProjectionV2()).control_authority;
  for(const tier of [0,1,2])await t.test(`flare:T${tier}`,()=>{
    const model=modeled(control,"flare",tier);rider(model,3,tier);const blinded=one(conditions(model,"blinded"),`${model.effect_id} Blinded`);assert.deepEqual(blinded.duration,END_NEXT);
    if(tier===0){const gate=save(model,"dexterity","initial","normal");applied(gate,"save_failure",blinded);assert.deepEqual(branch(gate,"save_success").applies,[]);}
    else{assert.equal(saves(model).length,0,`${model.effect_id} removes the inherited save gate`);assert.ok(model.resolutions.some((gate:AnyRecord)=>gate.resolution.kind==="attack_roll"&&gate.resolution.branches.some((candidate:AnyRecord)=>candidate.outcome==="attack_hit"&&candidate.applies.includes(blinded.component_id))));}
  });
});

test("Psychokinesis population preserves all nine canonical row mechanics",async t=>{
  const control=(await createControlAuthorityProjectionV2()).control_authority;

  await t.test("advanced_phase_step:T2",()=>{
    const model=modeled(control,"advanced_phase_step",2);standalone(model,1,2,"bonus_action");
    assert.equal(model.choices.length,1);assert.deepEqual({kind:model.choices[0].kind,timing:model.choices[0].timing,resolution:model.choices[0].resolution,scope:model.choices[0].scope,options:model.choices[0].options},{kind:"placement",timing:{kind:"activation"},resolution:"once_per_effect",scope:"area_origin",options:["departure_space","arrival_space"]});
    const targets=selector(model,"all"),area=targets.area;assert.equal(targets.selection,"controller_choice");assert.ok(targets.restrictions.some((item:AnyRecord)=>item.kind==="unique_targets"));
    assert.deepEqual({shape:area.shape,placement:area.placement,radius_feet:area.radius_feet,persistent:area.persistent},{shape:"sphere",placement:{kind:"endpoint_choice",choice_id:model.choices[0].choice_id,departure:{origin:"controller_current_space"},arrival:{range:{feet:30,origin:"departure_space"},visibility:"required",occupancy:"unoccupied_required"}},radius_feet:5,persistent:false});
    const gate=save(model,"discipline_signature","initial","normal"),denial=one(components(model,"reaction_denial"),`${model.effect_id} reaction denial`);assert.deepEqual(denial.duration,START_NEXT);applied(gate,"save_failure",denial);assertEmptyBranch(gate,"save_success");
  });

  for(const tier of [0,1,2])await t.test(`explosion_implosion:T${tier}`,()=>{
    const model=modeled(control,"explosion_implosion",tier);rider(model,2,tier);assert.equal(model.choices.length,1);assert.deepEqual({kind:model.choices[0].kind,timing:model.choices[0].timing,resolution:model.choices[0].resolution,scope:model.choices[0].scope,options:model.choices[0].options},{kind:"mode",timing:{kind:"declaration"},resolution:"once_per_effect",scope:"all_targets",options:["explosion","implosion"]});
    const primary=selector(model,"primary"),secondary=selector(model,"secondary"),area=primary.area??secondary.area;assert.equal(primary.selection,"automatic");assert.equal(secondary.selection,"all_in_area");assert.ok(secondary.restrictions.some((item:AnyRecord)=>item.kind==="excludes_primary_target"&&item.required===true));assert.equal(area.radius_feet,tier===0?15:30);assert.deepEqual(area.placement,{kind:"primary_target"});
    const gates=saves(model,"initial"),restrained=one(conditions(model,"restrained"),"explosion_implosion must retain Restrained");assert.equal(gates.length,2);assert.ok(gates.every(gate=>gate.resolution.ability==="strength"&&gate.resolution.mode==="normal"&&gate.gate_scope==="independent_per_target"));for(const gate of gates)applied(gate,"save_failure",restrained);
    const movements=components(model,"forced_movement");assert.equal(movements.length,2);
    for(const movement of movements){assert.equal(movement.target_selector_ids.includes(secondary.selector_id),true);assert.equal(movement.target_selector_ids.includes(primary.selector_id),false);assertMovement(movement,tier===0?15:30,"exact","any");assert.deepEqual({reference_point:movement.magnitude.reference_point,destination:movement.magnitude.destination,path:movement.magnitude.path,resolution_order:movement.magnitude.resolution_order},{reference_point:"primary_target",destination:{selection:"rule_determined",visibility:"not_required",occupancy:"unoccupied_required"},path:{line:"straight",blocked:"nearest_unoccupied_along_path"},resolution_order:"controller_selected"});assert.ok(["away_from_reference","toward_reference"].includes(movement.magnitude.direction));assert.equal(movement.choice_requirement.choice_id,model.choices[0].choice_id);}
  });

  for(const tier of [1,2])await t.test(`mass_levitation:T${tier}`,()=>{
    const model=modeled(control,"mass_levitation",tier);standalone(model,5,tier);const targets=selector(model,"all");
    assert.equal(targets.selection,"controller_choice");assert.deepEqual(targets.count,{kind:"weighted_slots",slots:5,size_costs:{tiny:1,small:1,medium:1,large:2}});for(const kind of ["visibility","maximum_size","unique_targets"])assert.ok(targets.restrictions.some((item:AnyRecord)=>item.kind===kind));
    save(model,"strength","initial","normal");const repeat=save(model,"strength","repeat","disadvantage");assert.equal(model.concentration.startup,"on_activation");
    const lift=one(components(model,"forced_movement").filter(item=>item.magnitude.movement_mode==="lift"),`${model.effect_id} lift`),reposition=one(components(model,"forced_movement").filter(item=>item.magnitude.movement_mode==="reposition"),`${model.effect_id} reposition`);
    assertMovement(lift,30,"exact","vertical");assert.equal(lift.magnitude.direction,"vertical_up");assertMovement(reposition,15,"up_to","any");assert.deepEqual(reposition.magnitude.destination,{selection:"controller_choice",visibility:"required",occupancy:"unoccupied_required"});assert.ok(hasEvent(reposition.cadence.apply,CONTROLLER_START));
    assert.equal(conditions(model,"restrained").length,1);assert.equal(components(model,"persistent_elevation").length,1);const falls=components(model,"fall");assert.ok(falls.length>=1);assert.ok(falls.every(fall=>fall.magnitude.origin==="current_position"));const success=branch(repeat,"save_success");assert.ok(falls.some(fall=>success.applies.includes(fall.component_id)));assert.ok(success.terminates.length>=2);assertMassAffectedGuards(model,tier);
  });

  for(const tier of [0,1,2])await t.test(`telekinetic_slam:T${tier}`,()=>{
    const model=modeled(control,"telekinetic_slam",tier);standalone(model,3,tier);const target=selector(model,"primary");assert.deepEqual(target.range,{kind:"distance",feet:60,origin:"controller"});const gate=save(model,"strength","initial","normal"),movements=components(model,"forced_movement"),failure=one(movements.filter(component=>branch(gate,"save_failure").applies.includes(component.component_id)),`${model.effect_id} failure movement`);
    assertMovement(failure,[10,20,30][tier]!,"exact","horizontal");assert.deepEqual({reference_point:failure.magnitude.reference_point,direction:failure.magnitude.direction},{reference_point:"target_current_position",direction:"controller_choice"});
    if(tier<2)assert.equal(branch(gate,"save_success").applies.length,0);
    else{const success=one(movements.filter(component=>branch(gate,"save_success").applies.includes(component.component_id)),`${model.effect_id} success movement`);assertMovement(success,10,"up_to","horizontal");assert.deepEqual({destination:failure.magnitude.destination,path:failure.magnitude.path},{destination:{selection:"controller_choice",visibility:"required",occupancy:"unoccupied_required"},path:{line:"straight",blocked:"movement_not_permitted"}});const speed=one(components(model,"speed_zero"),`${model.effect_id} Speed 0`);assert.deepEqual(speed.duration,END_NEXT);applied(gate,"save_failure",speed);}
  });
});

test("Electrokinesis population preserves both canonical Tier 2 row mechanics",async t=>{
  const control=(await createControlAuthorityProjectionV2()).control_authority;
  await t.test("electron_burst:T2",()=>{
    const model=modeled(control,"electron_burst",2);rider(model,2,2);const primary=selector(model,"primary"),targets=selector(model,"secondary"),area=targets.area;assert.equal(primary.selection,"automatic");assert.equal(targets.selection,"all_in_area");assert.ok(targets.restrictions.some((item:AnyRecord)=>item.kind==="excludes_primary_target"&&item.required===true));assert.deepEqual({shape:area.shape,placement:area.placement,radius_feet:area.radius_feet,persistent:area.persistent},{shape:"sphere",placement:{kind:"primary_target"},radius_feet:10,persistent:false});
    const gate=save(model,"charisma","initial","normal"),denial=one(components(model,"reaction_denial"),`${model.effect_id} reaction denial`),attacks=one(components(model,"attack_disadvantage"),`${model.effect_id} attack disadvantage`);assert.equal(attacks.magnitude.scope,"all_attacks");assert.deepEqual(denial.duration,START_NEXT);assert.deepEqual(attacks.duration,START_NEXT);applied(gate,"save_failure",denial);assertEmptyBranch(gate,"save_success");applied(gate,"save_failure",attacks);
  });
  await t.test("static_discharge:T2",()=>{
    const model=modeled(control,"static_discharge",2);rider(model,0,2,"unlimited");const primary=selector(model,"primary"),secondary=selector(model,"secondary");assert.equal(primary.selection,"automatic");assert.deepEqual(primary.count,{kind:"fixed",value:1});assert.equal(secondary.selection,"controller_choice");assert.deepEqual(secondary.count,{kind:"up_to_proficiency_bonus"});assert.deepEqual(secondary.range,{kind:"distance",feet:5,origin:"primary_target"});for(const kind of ["unique_targets","excludes_primary_target"])assert.ok(secondary.restrictions.some((item:AnyRecord)=>item.kind===kind));
    const gate=save(model,"charisma","initial","normal"),denial=one(components(model,"reaction_denial"),`${model.effect_id} reaction denial`);assert.deepEqual([...gate.selector_ids].sort(),[primary.selector_id,secondary.selector_id].sort());assert.equal(gate.gate_scope,"independent_per_target");assert.deepEqual(denial.duration,START_NEXT);applied(gate,"save_failure",denial);assertEmptyBranch(gate,"save_success");
  });
});

test("representative v2.1 corrections remain concrete and role-safe",async t=>{
  const {authority}=await loadAuthority(),control=(authority as any).calculator.harness_mechanics.control_authority_v2;

  await t.test("ball_lightning:T2 has ownerful recurring exposure and orb movement",()=>{
    const model=modeled(control,"ball_lightning",2),targets=selector(model,"all"),area=targets.area;assert.equal(targets.selection,"all_in_area");assert.deepEqual(targets.range,{kind:"area"});assert.deepEqual(area.placement,{kind:"selected_point",range:{feet:60,origin:"controller"},stationary:false});assert.deepEqual(area.entry_policy,{frequency:"once_per_turn",moved_area_counts_as_entry:false});assert.deepEqual(area.movement,{kind:"controller_reposition",controller_action:"bonus_action",timing:{kind:"turn",owner:"controller",turn_anchor:"during"},distance_feet:15,distance_mode:"up_to"});
    assert.ok(hasEvent(area.triggers,ENTRY));assert.ok(hasEvent(area.triggers,TARGET_START));const recurring=saves(model,"recurring");assert.equal(recurring.length,2);assert.ok(recurring.every(gate=>gate.resolution.mode==="normal"&&gate.gate_scope==="independent_per_target"));assert.equal(model.concentration.startup,"on_activation");
  });

  await t.test("forked_lightning:T2 keeps primary-only Speed 0 role-safe",()=>{
    const model=modeled(control,"forked_lightning",2),primary=selector(model,"primary"),secondary=selector(model,"secondary");assert.equal(secondary.selection,"controller_choice");for(const kind of ["unique_targets","excludes_primary_target"])assert.ok(secondary.restrictions.some((item:AnyRecord)=>item.kind===kind));const gates=saves(model,"initial");assert.ok(gates.length>=1);assert.ok(gates.every(gate=>gate.resolution.ability==="charisma"&&gate.resolution.mode==="normal"&&gate.gate_scope==="independent_per_target"));const speed=one(components(model,"speed_zero"),`${model.effect_id} primary Speed 0`);assert.deepEqual(speed.target_selector_ids,[primary.selector_id]);assert.ok(!speed.target_selector_ids.includes(secondary.selector_id));assert.ok(model.resolutions.filter((gate:AnyRecord)=>gate.selector_ids.includes(primary.selector_id)).some((gate:AnyRecord)=>gate.resolution.branches.some((item:AnyRecord)=>item.outcome==="save_failure"&&item.applies.includes(speed.component_id))));const secondaryGate=one(gates.filter((gate:AnyRecord)=>gate.selector_ids.includes(secondary.selector_id)&&!gate.selector_ids.includes(primary.selector_id)),model.effect_id+" secondary save gate");assert.equal(branch(secondaryGate,"save_failure").applies.includes(speed.component_id),false);
  });

  for(const tier of [0,1,2])await t.test(`glacial_spike:T${tier} uses ordered typed gates and controller-end cadence`,()=>{
    const model=modeled(control,"glacial_spike",tier),reduction=one(components(model,"speed_reduction"),`${model.effect_id} speed reduction`);assert.deepEqual(reduction.duration,END_NEXT);assert.ok(reduction.cadence.apply.some((event:AnyRecord)=>event.kind==="hit"));assert.ok(hasEvent(reduction.cadence.end,CONTROLLER_END));
    if(tier>0){const gate=save(model,"constitution","initial","normal"),hit=one(model.resolutions.filter((item:AnyRecord)=>item.resolution.kind==="attack_roll"),`${model.effect_id} attack gate`);assert.ok(branch(hit,"attack_hit").next_gate_ids.includes(gate.gate_id));assert.deepEqual(reduction.cadence.repeat,[]);}
  });

  await t.test("mass_levitation:T0 models affected-state repeats and falls",()=>{
    const model=modeled(control,"mass_levitation",0);save(model,"strength","initial","normal");const repeat=save(model,"strength","repeat","normal");assert.deepEqual(repeat.trigger,TARGET_START);assert.ok(!model.root_gate_ids.includes(repeat.gate_id));assert.equal(model.concentration.startup,"on_activation");assert.equal(components(model,"persistent_elevation").length,1);const falls=components(model,"fall");assert.ok(falls.length>=1);assert.ok(falls.every(component=>component.magnitude.origin==="current_position"));assert.ok(falls.some(component=>component.cadence.apply.some((event:AnyRecord)=>event.kind==="concentration_end")));assertMassAffectedGuards(model,0);
  });

  for(const tier of [0,1,2])await t.test(`telekinetic_shove:T${tier} keeps horizontal exact movement`,()=>{
    const model=modeled(control,"telekinetic_shove",tier),gate=save(model,"strength","initial","normal"),movement=one(components(model,"forced_movement"),`${model.effect_id} forced movement`);assertMovement(movement,[10,15,20][tier]!,"exact","horizontal");assert.deepEqual({reference_point:movement.magnitude.reference_point,direction:movement.magnitude.direction},{reference_point:"controller",direction:"controller_choice"});applied(gate,"save_failure",movement);assert.equal(branch(gate,"save_success").applies.includes(movement.component_id),false);
    if(tier===2){const speed=one(components(model,"speed_zero"),`${model.effect_id} Speed 0`);assert.deepEqual(speed.duration,END_NEXT);assert.ok(hasEvent(speed.cadence.end,CONTROLLER_END));applied(gate,"save_failure",speed);}
  });
});

test("focused branch transitions remain exact",async t=>{
  const control=(await createControlAuthorityProjectionV2()).control_authority;
  const gateFor=(model:AnyRecord,predicate:(gate:AnyRecord)=>boolean,label:string):AnyRecord=>one(model.resolutions.filter(predicate),`${model.effect_id} ${label}`);
  const exact=(gate:AnyRecord,outcome:string,expected:Partial<AnyRecord>={}):void=>{
    const actual=branch(gate,outcome);
    assert.deepEqual({outcome:actual.outcome,applies:actual.applies,replaces:actual.replaces,terminates:actual.terminates,refreshes:actual.refreshes,next_gate_ids:actual.next_gate_ids},{outcome,applies:[],replaces:[],terminates:[],refreshes:[],next_gate_ids:[],...expected});
  };

  await t.test("Absolute Zero T1 and T2 branches",()=>{
    const t1=modeled(control,"absolute_zero",1),t1Gate=save(t1,"constitution","initial","normal"),t1Speed=one(components(t1,"speed_zero"),"Absolute Zero T1 Speed 0"),t1Restrained=one(conditions(t1,"restrained"),"Absolute Zero T1 Restrained");
    exact(t1Gate,"save_success");exact(t1Gate,"save_failure",{applies:[t1Speed.component_id,t1Restrained.component_id]});
    const t2=modeled(control,"absolute_zero",2),t2Gate=save(t2,"constitution","initial","normal"),t2Speed=one(components(t2,"speed_zero"),"Absolute Zero T2 Speed 0"),t2Restrained=one(conditions(t2,"restrained"),"Absolute Zero T2 inherited Restrained"),t2Stunned=one(conditions(t2,"stunned"),"Absolute Zero T2 Stunned");
    exact(t2Gate,"save_success",{applies:[t2Speed.component_id]});exact(t2Gate,"save_failure",{applies:[t2Speed.component_id,t2Stunned.component_id],replaces:[t2Restrained.component_id]});
  });

  await t.test("Frozen Ground entry and start-turn recurring branches",()=>{
    for(const tier of [0,1,2]){const model=modeled(control,"frozen_ground",tier),recurring=saves(model,"recurring"),speed=one(components(model,"speed_zero"),`Frozen Ground T${tier} Speed 0`);assert.equal(recurring.length,2);
      for(const gate of recurring){exact(gate,"save_success");if(tier<2)exact(gate,"save_failure",{applies:[speed.component_id]});else{const restrained=one(conditions(model,"restrained"),"Frozen Ground T2 Restrained");exact(gate,"save_failure",{applies:[restrained.component_id],replaces:[speed.component_id]});}}
    }
  });

  await t.test("Snow Chains T0 orders no-save Speed 0 before save branches",()=>{
    const model=modeled(control,"snow_chains",0),attack=gateFor(model,gate=>gate.resolution.kind==="attack_roll","attack gate"),saving=save(model,"constitution","initial","normal"),speed=one(components(model,"speed_zero"),"Snow Chains T0 Speed 0"),restrained=one(conditions(model,"restrained"),"Snow Chains T0 Restrained");
    exact(attack,"attack_hit",{applies:[speed.component_id],next_gate_ids:[saving.gate_id]});exact(attack,"attack_miss");exact(saving,"save_success");exact(saving,"save_failure",{applies:[restrained.component_id]});
  });

  await t.test("Explosion and Implosion primary and secondary save successes are empty",()=>{
    for(const tier of [0,1,2]){const model=modeled(control,"explosion_implosion",tier),primary=selector(model,"primary"),secondary=selector(model,"secondary"),primaryGate=gateFor(model,gate=>gate.resolution.kind==="saving_throw"&&gate.selector_ids.includes(primary.selector_id),"primary save"),secondaryGate=gateFor(model,gate=>gate.resolution.kind==="saving_throw"&&gate.selector_ids.includes(secondary.selector_id),"secondary save"),restrained=one(conditions(model,"restrained"),`Explosion/Implosion T${tier} Restrained`),movements=components(model,"forced_movement");
      exact(primaryGate,"save_success");exact(primaryGate,"save_failure",{applies:[restrained.component_id]});exact(secondaryGate,"save_success");exact(secondaryGate,"save_failure",{applies:[restrained.component_id,...movements.map(component=>component.component_id)]});
    }
  });

  await t.test("Ball Lightning both recurring gates have identical exact outcomes",()=>{
    const model=modeled(control,"ball_lightning",2),recurring=saves(model,"recurring"),denial=one(components(model,"reaction_denial"),"Ball Lightning reaction denial"),attacks=one(components(model,"attack_disadvantage"),"Ball Lightning attack disadvantage");assert.equal(recurring.length,2);
    for(const gate of recurring){exact(gate,"save_success");exact(gate,"save_failure",{applies:[denial.component_id,attacks.component_id]});}
  });

  await t.test("Forked Lightning primary and secondary branches are role-safe",()=>{
    const model=modeled(control,"forked_lightning",2),primary=selector(model,"primary"),secondary=selector(model,"secondary"),primaryGate=gateFor(model,gate=>gate.resolution.kind==="saving_throw"&&gate.selector_ids.includes(primary.selector_id),"primary save"),secondaryGate=gateFor(model,gate=>gate.resolution.kind==="saving_throw"&&gate.selector_ids.includes(secondary.selector_id),"secondary save"),denial=one(components(model,"reaction_denial"),"Forked Lightning reaction denial"),attacks=one(components(model,"attack_disadvantage"),"Forked Lightning attack disadvantage"),speed=one(components(model,"speed_zero"),"Forked Lightning primary Speed 0");
    exact(primaryGate,"save_success");exact(primaryGate,"save_failure",{applies:[denial.component_id,attacks.component_id,speed.component_id]});exact(secondaryGate,"save_success");exact(secondaryGate,"save_failure",{applies:[denial.component_id,attacks.component_id]});assert.deepEqual(speed.target_selector_ids,[primary.selector_id]);
  });

  await t.test("Glacial Spike T1 and T2 use branch-specific retain and replace transitions",()=>{
    for(const tier of [1,2]){const model=modeled(control,"glacial_spike",tier),gate=save(model,"constitution","initial","normal"),reduction=one(components(model,"speed_reduction"),`Glacial Spike T${tier} reduction`);exact(gate,"save_success",{refreshes:[reduction.component_id]});
      if(tier===1){const speed=one(components(model,"speed_zero"),"Glacial Spike T1 Speed 0");exact(gate,"save_failure",{applies:[speed.component_id],replaces:[reduction.component_id]});}
      else{const speed=one(components(model,"speed_zero"),"Glacial Spike T2 inherited Speed 0"),restrained=one(conditions(model,"restrained"),"Glacial Spike T2 Restrained");exact(gate,"save_failure",{applies:[restrained.component_id],replaces:[speed.component_id,reduction.component_id]});}
    }
  });

  await t.test("Telekinetic Shove T2 failure alone applies movement and Speed 0",()=>{
    const model=modeled(control,"telekinetic_shove",2),attack=gateFor(model,gate=>gate.resolution.kind==="attack_roll","attack gate"),saving=save(model,"strength","initial","normal"),movement=one(components(model,"forced_movement"),"Telekinetic Shove T2 movement"),speed=one(components(model,"speed_zero"),"Telekinetic Shove T2 Speed 0");
    exact(attack,"attack_hit",{next_gate_ids:[saving.gate_id]});exact(attack,"attack_miss");exact(saving,"save_success");exact(saving,"save_failure",{applies:[movement.component_id,speed.component_id]});
  });

  await t.test("Telekinetic Slam T2 success and failure branches stay distinct",()=>{
    const model=modeled(control,"telekinetic_slam",2),gate=save(model,"strength","initial","normal"),movements=components(model,"forced_movement"),success=one(movements.filter(component=>component.magnitude.distance_mode==="up_to"),"Telekinetic Slam T2 success movement"),failure=one(movements.filter(component=>component.magnitude.distance_mode==="exact"),"Telekinetic Slam T2 failure movement"),speed=one(components(model,"speed_zero"),"Telekinetic Slam T2 Speed 0");
    exact(gate,"save_success",{applies:[success.component_id]});exact(gate,"save_failure",{applies:[failure.component_id,speed.component_id]});
  });
});

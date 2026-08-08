import type {Authority,Diagnostic} from "./types.js";

export const CANONICAL_CONTROL_TIER_KEYS=[
  "absolute_zero:T0","absolute_zero:T1","absolute_zero:T2",
  "advanced_beguile:T0","advanced_beguile:T1","advanced_beguile:T2",
  "advanced_deflection_screen:T2",
  "advanced_gravitic_press:T0","advanced_gravitic_press:T1","advanced_gravitic_press:T2",
  "advanced_improved_phase_step:T2",
  "advanced_mind_lock:T0","advanced_mind_lock:T1","advanced_mind_lock:T2",
  "advanced_phase_step:T2",
  "arctic_tempest:T0","arctic_tempest:T1","arctic_tempest:T2",
  "ball_lightning:T2",
  "electron_burst:T2",
  "explosion_implosion:T0","explosion_implosion:T1","explosion_implosion:T2",
  "flare:T0","flare:T1","flare:T2",
  "forked_lightning:T2",
  "frozen_ground:T0","frozen_ground:T1","frozen_ground:T2",
  "glacial_spike:T0","glacial_spike:T1","glacial_spike:T2",
  "mass_levitation:T0","mass_levitation:T1","mass_levitation:T2",
  "snow_chains:T0","snow_chains:T1","snow_chains:T2",
  "static_discharge:T2",
  "telekinetic_shove:T0","telekinetic_shove:T1","telekinetic_shove:T2",
  "telekinetic_slam:T0","telekinetic_slam:T1","telekinetic_slam:T2",
  "thermal_fracture:T0","thermal_fracture:T1","thermal_fracture:T2"
] as const;
export type CanonicalControlTierKey=typeof CANONICAL_CONTROL_TIER_KEYS[number];

type ObjectValue=Record<string,any>;
const ID=/^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;
const EVENTS=new Set(["declaration","hit","entry","start_turn","save","repeat_save","exit","instantaneous_resolution"]);
const MOVEMENT_MODES=["walk","fly","swim","climb","burrow"];
const TERMINATION=["failed_concentration_save","controller_incapacitated","controller_death","duration_expires","voluntary_end"];
const MODELED=new Set<CanonicalControlTierKey>([
  "ball_lightning:T2","forked_lightning:T2","glacial_spike:T0","glacial_spike:T1","glacial_spike:T2",
  "mass_levitation:T0","telekinetic_shove:T0","telekinetic_shove:T1","telekinetic_shove:T2"
]);
const EXCLUDED:Partial<Record<CanonicalControlTierKey,string>>={
  "advanced_beguile:T0":"selectable_advanced_training_disabled",
  "advanced_beguile:T1":"selectable_advanced_training_disabled",
  "advanced_beguile:T2":"selectable_advanced_training_disabled",
  "advanced_deflection_screen:T2":"incoming_enemy_attacks_unmodeled",
  "advanced_gravitic_press:T0":"selectable_advanced_training_disabled",
  "advanced_gravitic_press:T1":"selectable_advanced_training_disabled",
  "advanced_gravitic_press:T2":"selectable_advanced_training_disabled",
  "advanced_improved_phase_step:T2":"selectable_advanced_training_disabled",
  "advanced_mind_lock:T0":"selectable_advanced_training_disabled",
  "advanced_mind_lock:T1":"selectable_advanced_training_disabled",
  "advanced_mind_lock:T2":"selectable_advanced_training_disabled",
  "thermal_fracture:T0":"outside_headline_control_value",
  "thermal_fracture:T1":"outside_headline_control_value",
  "thermal_fracture:T2":"outside_headline_control_value"
};
const PROFILE={id:"official_default_25_percent_hp",selectable_advanced_training:"excluded",tactical_master:"included",legendary_resistance:"metadata_only",unsupported_disposition:"error"};
const POLICY={
  horizon_rounds:3,
  action_economy:{attack_rider_declaration:"before_attack_roll",standalone_action_limit_per_turn:1,action_surge_additional_standalone:false},
  resources:{psi_source:"psi_point_bands",blood_tax_source:"harness_overload",tier_two_limit_per_attack_action:1},
  concentration:{pressure:"endogenous_only",startup_blood_tax_check:"exempt",occupancy:"one_controller_slot",replacement:"new_effect_ends_existing",termination:TERMINATION}
};
const EXPECTED_MASTERIES=[
  {mastery_id:"mastery_slow",minimum_level:3,trigger:["hit"],component:{component_id:"mastery_slow_speed_reduction",target_selector_ids:["manifested_strike_target"],magnitude:{kind:"speed_reduction",reduction:{kind:"flat_feet",value:10},movement_modes:MOVEMENT_MODES},duration:{kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1},cadence:{apply:["hit"],repeat:[],end:["start_turn"]},stacking:{key:"mastery_slow_speed_reduction",mode:"nonstacking",refresh:"duration",dominates_component_ids:[]}}},
  {mastery_id:"mastery_push",minimum_level:3,trigger:["hit"],component:{component_id:"mastery_push_forced_movement",target_selector_ids:["manifested_strike_large_or_smaller_target"],magnitude:{kind:"forced_movement",distance_feet:10,distance_mode:"up_to",movement_mode:"push",direction:"straight_away_from_controller",path:"legal_destination"},duration:{kind:"instantaneous"},cadence:{apply:["hit"],repeat:[],end:["instantaneous_resolution"]},stacking:{key:"mastery_push_forced_movement",mode:"independent",refresh:"none",dominates_component_ids:[]}}},
  {mastery_id:"mastery_sap",minimum_level:3,trigger:["hit"],component:{component_id:"mastery_sap_attack_disadvantage",target_selector_ids:["manifested_strike_target"],magnitude:{kind:"attack_disadvantage",scope:"next_attack",count:1},duration:{kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1},cadence:{apply:["hit"],repeat:[],end:["start_turn"]},stacking:{key:"mastery_sap_attack_disadvantage",mode:"nonstacking",refresh:"duration",dominates_component_ids:[]}}}
] as const;

const object=(value:unknown):ObjectValue|undefined=>value!==null&&typeof value==="object"&&!Array.isArray(value)?value as ObjectValue:undefined;
const array=(value:unknown):any[]=>Array.isArray(value)?value:[];
const same=(left:unknown,right:unknown):boolean=>JSON.stringify(left)===JSON.stringify(right);
const tierKey=(row:ObjectValue):string=>`${String(row.entity_id)}:T${String(row.tier)}`;
const add=(diagnostics:Diagnostic[],code:string,message:string,path:string):void=>{diagnostics.push({severity:"error",code,message,path});};
const validId=(value:unknown):value is string=>typeof value==="string"&&ID.test(value);
const positiveInteger=(value:unknown):boolean=>Number.isInteger(value)&&Number(value)>0;
const nonnegativeInteger=(value:unknown):boolean=>Number.isInteger(value)&&Number(value)>=0;
const uniqueStrings=(value:unknown,nonempty=false):boolean=>Array.isArray(value)&&(!nonempty||value.length>0)&&value.every(item=>typeof item==="string")&&new Set(value).size===value.length;
const validEvents=(value:unknown,nonempty=false):boolean=>uniqueStrings(value,nonempty)&&array(value).every(item=>EVENTS.has(item));
const validIdArray=(value:unknown,nonempty=false):boolean=>uniqueStrings(value,nonempty)&&array(value).every(validId);
const validMovementModes=(value:unknown):boolean=>validIdArray(value,true)&&array(value).every(item=>MOVEMENT_MODES.includes(item));

function validateMagnitude(value:unknown,diagnostics:Diagnostic[],path:string):void{
  const magnitude=object(value);let valid=Boolean(magnitude);
  switch(magnitude?.kind){
    case "condition":valid=validId(magnitude.condition);break;
    case "forced_movement":valid=positiveInteger(magnitude.distance_feet)&&["exact","up_to"].includes(magnitude.distance_mode)&&["push","pull","reposition","lift"].includes(magnitude.movement_mode)&&validId(magnitude.direction)&&validId(magnitude.path);break;
    case "speed_reduction":{
      const reduction=object(magnitude.reduction);let reductionValid=false;
      if(reduction?.kind==="flat_feet")reductionValid=positiveInteger(reduction.value);
      else if(reduction?.kind==="fraction")reductionValid=positiveInteger(reduction.numerator)&&positiveInteger(reduction.denominator)&&reduction.numerator<reduction.denominator;
      else if(reduction?.kind==="terrain_multiplier")reductionValid=typeof reduction.value==="number"&&Number.isFinite(reduction.value)&&reduction.value>1;
      valid=reductionValid&&validMovementModes(magnitude.movement_modes);break;
    }
    case "speed_zero":case "movement_option_denial":valid=validMovementModes(magnitude.movement_modes);break;
    case "attack_disadvantage":valid=magnitude.scope==="next_attack"?positiveInteger(magnitude.count):magnitude.scope==="all_attacks"&&magnitude.count===undefined;break;
    case "reaction_denial":valid=magnitude.scope==="all_reactions";break;
    case "numerical_modifier":valid=validId(magnitude.target)&&typeof magnitude.value==="number"&&Number.isFinite(magnitude.value);break;
    default:valid=false;
  }
  if(!valid)add(diagnostics,"control_v2.magnitude","Control component magnitude is incomplete or invalid",path);
}

function validateDuration(value:unknown,diagnostics:Diagnostic[],path:string,areaIds:Set<string>,requiredConcentration:boolean):void{
  const duration=object(value);let valid=Boolean(duration);
  switch(duration?.kind){
    case "instantaneous":break;
    case "relative":valid=["controller","target"].includes(duration.owner)&&["start_turn","end_turn"].includes(duration.anchor)&&nonnegativeInteger(duration.offset_turns);break;
    case "while_in_area":valid=validId(duration.area_id)&&areaIds.has(duration.area_id);if(!valid)add(diagnostics,"control_v2.area","Area duration must reference a selector area",path);return;
    case "concentration":valid=requiredConcentration&&positiveInteger(duration.maximum_value)&&["round","minute","hour"].includes(duration.unit);if(!valid)add(diagnostics,"control_v2.concentration","Concentration duration must match a required concentration model",path);return;
    default:valid=false;
  }
  if(!valid)add(diagnostics,"control_v2.timing","Control component duration must have an explicit owner and anchor",path);
}

function validateCadence(value:unknown,diagnostics:Diagnostic[],path:string):void{
  const cadence=object(value);
  if(!cadence||!validEvents(cadence.apply,true)||!validEvents(cadence.repeat)||!validEvents(cadence.end))add(diagnostics,"control_v2.timing","Control cadence must use explicit supported events",path);
}

function validateCount(value:unknown):boolean{
  const count=object(value);
  if(!count)return false;
  if(count.kind==="fixed"||count.kind==="up_to")return positiveInteger(count.value);
  if(count.kind==="proficiency_bonus"||count.kind==="cluster_remainder")return true;
  if(count.kind!=="weighted_slots"||!positiveInteger(count.slots))return false;
  const costs=object(count.size_costs);return Boolean(costs)&&Object.keys(costs!).length>0&&Object.entries(costs!).every(([key,cost])=>validId(key)&&positiveInteger(cost));
}

function validateArea(value:unknown,diagnostics:Diagnostic[],path:string):string|undefined{
  const area=object(value);if(!area)return undefined;let valid=validId(area.area_id)&&["sphere","cylinder","cone","line"].includes(area.shape)&&["controller","primary_target","selected_point","departure_or_arrival"].includes(area.origin)&&typeof area.persistent==="boolean"&&validEvents(area.triggers,true)&&["ends_area_effects","none"].includes(area.exit_behavior);
  if(area?.shape==="sphere")valid=valid&&positiveInteger(area.radius_feet)&&area.height_feet===undefined&&area.length_feet===undefined&&area.width_feet===undefined;
  else if(area?.shape==="cylinder")valid=valid&&positiveInteger(area.radius_feet)&&positiveInteger(area.height_feet)&&area.length_feet===undefined&&area.width_feet===undefined;
  else if(area?.shape==="cone")valid=valid&&positiveInteger(area.length_feet)&&area.radius_feet===undefined&&area.height_feet===undefined&&area.width_feet===undefined;
  else if(area?.shape==="line")valid=valid&&positiveInteger(area.length_feet)&&positiveInteger(area.width_feet)&&area.radius_feet===undefined&&area.height_feet===undefined;
  if(area?.persistent)valid=valid&&array(area.triggers).includes("entry")&&array(area.triggers).includes("start_turn")&&area.exit_behavior==="ends_area_effects";
  if(!valid)add(diagnostics,"control_v2.area","Control area must define its shape, dimensions, origin, triggers, persistence, and exit behavior",path);
  return validId(area.area_id)?area.area_id:undefined;
}

function validateSelector(value:unknown,diagnostics:Diagnostic[],path:string):string|undefined{
  const selector=object(value);if(!selector){add(diagnostics,"control_v2.target","Control target selector is missing",path);return undefined;}
  const range=object(selector.range),restrictions=array(selector.restrictions);
  const valid=validId(selector.selector_id)&&["primary","secondary","all"].includes(selector.role)&&validateCount(selector.count)&&Boolean(range)&&nonnegativeInteger(range?.feet)&&["controller","primary_target","selected_point","departure_or_arrival"].includes(range?.origin)&&Array.isArray(selector.restrictions)&&restrictions.every(item=>{const restriction=object(item);return Boolean(restriction)&&validId(restriction?.kind)&&typeof restriction?.value==="string"&&restriction.value.length>0;})&&["independent_per_target","shared"].includes(selector.gate_scope);
  if(!valid)add(diagnostics,"control_v2.target","Control target selector must define role, count, range, restrictions, and gate scope",path);
  if(selector.area!==undefined)validateArea(selector.area,diagnostics,`${path}/area`);
  return validId(selector.selector_id)?selector.selector_id:undefined;
}

function validateComponent(value:unknown,diagnostics:Diagnostic[],path:string,selectorIds:Set<string>|undefined,areaIds:Set<string>,componentIds:Set<string>,requiredConcentration:boolean):void{
  const component=object(value);if(!component){add(diagnostics,"control_v2.ids","Control component is missing",path);return;}
  if(!validId(component.component_id))add(diagnostics,"control_v2.ids","Control component requires a stable component_id",`${path}/component_id`);
  const targetIds=array(component.target_selector_ids);
  if(!validIdArray(component.target_selector_ids,true)||(selectorIds&&targetIds.some(id=>!selectorIds.has(id))))add(diagnostics,"control_v2.target","Control component must reference defined target selectors",`${path}/target_selector_ids`);
  validateMagnitude(component.magnitude,diagnostics,`${path}/magnitude`);
  validateDuration(component.duration,diagnostics,`${path}/duration`,areaIds,requiredConcentration);
  validateCadence(component.cadence,diagnostics,`${path}/cadence`);
  const stacking=object(component.stacking),dominates=array(stacking?.dominates_component_ids),mode=stacking?.mode;
  const valid=Boolean(stacking)&&validId(stacking?.key)&&["stacks","nonstacking","replace","dominates","independent"].includes(mode)&&["duration","none"].includes(stacking?.refresh)
    &&validIdArray(stacking?.dominates_component_ids)&&dominates.every(id=>componentIds.has(id)&&id!==component.component_id)
    &&(stacking?.replacement_group===undefined||validId(stacking.replacement_group))
    &&(mode!=="replace"||validId(stacking?.replacement_group))&&(mode!=="dominates"||dominates.length>0)&&(!dominates.length||mode==="dominates"||mode==="replace");
  if(!valid)add(diagnostics,"control_v2.stacking","Control component stacking references must be complete and local to the model",`${path}/stacking`);
}

function validateResolution(value:unknown,diagnostics:Diagnostic[],path:string,selectorIds:Set<string>,componentIds:Set<string>,componentsById:Map<string,ObjectValue>,gateIds:Set<string>,branchIds:Set<string>,referencedComponents:Set<string>):void{
  const gate=object(value);if(!gate){add(diagnostics,"control_v2.branch","Control resolution is missing",path);return;}
  if(!validId(gate.gate_id)||gateIds.has(gate.gate_id))add(diagnostics,"control_v2.ids","Resolution gate IDs must be stable and unique within a model",`${path}/gate_id`);else gateIds.add(gate.gate_id);
  const selected=array(gate.selector_ids);
  if(!validIdArray(gate.selector_ids,true)||selected.some(id=>!selectorIds.has(id))||!["independent_per_target","shared"].includes(gate.gate_scope))add(diagnostics,"control_v2.target","Resolution gates must reference defined selectors with explicit gate scope",path);
  if(!EVENTS.has(gate.trigger))add(diagnostics,"control_v2.timing","Resolution gates require an explicit supported trigger",`${path}/trigger`);
  const resolution=object(gate.resolution),branches=array(resolution?.branches),kind=resolution?.kind;
  let complete=Boolean(resolution)&&["attack_roll","saving_throw","no_save","other"].includes(kind)&&branches.length>0,cadenceComplete=true;
  const outcomes=branches.map(branch=>object(branch)?.outcome),expectedOutcomes=kind==="attack_roll"?["attack_hit","attack_miss"]:kind==="saving_throw"?["save_success","save_failure"]:kind==="no_save"?["no_save"]:kind==="other"?["other"]:[];
  complete=complete&&same([...outcomes].sort(),[...expectedOutcomes].sort());
  if(kind==="saving_throw")complete=complete&&["strength","constitution","dexterity","intelligence","charisma","discipline_signature"].includes(resolution?.ability);
  else complete=complete&&resolution?.ability===undefined;
  for(const [branchIndex,branchValue] of branches.entries()){
    const branch=object(branchValue),branchPath=`${path}/resolution/branches/${branchIndex}`;
    if(!branch||!validId(branch.branch_id)||branchIds.has(branch.branch_id)){add(diagnostics,"control_v2.ids","Branch IDs must be stable and unique within a model",`${branchPath}/branch_id`);continue;}branchIds.add(branch.branch_id);
    if(!["attack_hit","attack_miss","save_success","save_failure","no_save","other"].includes(branch.outcome))complete=false;
    const transitions=new Map<string,any[]>();
    for(const field of ["applies","replaces","terminates","refreshes"]){
      const refs=array(branch[field]);
      transitions.set(field,refs);refs.forEach(id=>referencedComponents.add(id));
      if(!validIdArray(branch[field])||refs.some(id=>!componentIds.has(id)))complete=false;
      const cadenceField=field==="applies"?"apply":field==="refreshes"?"repeat":"end";
      for(const id of refs){const component=componentsById.get(id),cadence=object(component?.cadence);if(component&&!array(cadence?.[cadenceField]).includes(gate.trigger))cadenceComplete=false;}
    }
    const applied=new Set(transitions.get("applies"));
    if([...array(transitions.get("replaces")),...array(transitions.get("terminates"))].some(id=>applied.has(id)))complete=false;
  }
  if(!cadenceComplete)add(diagnostics,"control_v2.timing","Branch transitions must match component apply, repeat, and end cadence",`${path}/resolution`);
  if(!complete)add(diagnostics,"control_v2.branch","Resolution branches must be complete and reference defined components",`${path}/resolution`);
}

function validateConcentration(value:unknown,entity:ObjectValue|undefined,diagnostics:Diagnostic[],path:string):boolean{
  const concentration=object(value);
  if(concentration?.kind==="none"){
    if(entity?.requires_concentration===true)add(diagnostics,"control_v2.concentration","Canonical concentration features require a complete concentration model",path);
    return false;
  }
  if(concentration?.kind!=="required"){
    add(diagnostics,"control_v2.concentration","Control concentration must be explicitly none or required",path);return false;
  }
  const maximum=object(concentration.maximum_duration),termination=array(concentration.termination);
  const valid=concentration.startup==="on_resolution"&&concentration.occupancy==="one_controller_slot"&&concentration.replacement==="new_effect_ends_existing"&&positiveInteger(maximum?.value)&&["round","minute","hour"].includes(maximum?.unit)&&uniqueStrings(concentration.termination,true)&&same([...termination].sort(),[...TERMINATION].sort())&&entity?.requires_concentration===true;
  if(!valid)add(diagnostics,"control_v2.concentration","Required concentration must define startup, occupancy, replacement, maximum duration, all termination events, and a canonical entity flag",path);
  return true;
}

function validatePolicy(value:unknown,row:ObjectValue,entity:ObjectValue|undefined,diagnostics:Diagnostic[],path:string):void{
  const policy=object(value),rider=row.entity_id==="glacial_spike"||row.entity_id==="telekinetic_shove";
  const expectedMastery=row.entity_id==="glacial_spike"?"stacks":row.entity_id==="telekinetic_shove"?"replaces_on_declaration":"not_applicable";
  const valid=Boolean(policy)&&["action","bonus_action","reaction","on_hit","passive"].includes(policy?.activation)&&policy?.activation===entity?.activation&&policy?.declaration==="declaration"&&policy?.delivery===(rider?"attack_rider":"standalone")&&nonnegativeInteger(policy?.psi_cost)&&policy?.psi_cost===entity?.psi_cost&&policy?.overload_tier===row.tier&&policy?.blood_tax===(row.tier===0?"none":"tier_formula")&&policy?.repeatability===(rider?"unlimited":"once_per_turn")&&policy?.mastery===expectedMastery;
  if(!valid)add(diagnostics,"control_v2.timing","Control policy must preserve canonical activation, declaration, delivery, resources, repeatability, and mastery interaction",path);
}

function validateRelationships(value:unknown,componentValues:any[],componentIds:Set<string>,diagnostics:Diagnostic[],path:string):void{
  const relationships=object(value),groups=array(relationships?.replacement_groups),dominance=array(relationships?.dominance),groupIds=new Set<string>(),edges=new Map<string,Set<string>>(),componentsById=new Map<string,ObjectValue>();let valid=Boolean(relationships)&&Array.isArray(relationships?.replacement_groups)&&Array.isArray(relationships?.dominance);
  for(const componentValue of componentValues){const component=object(componentValue);if(validId(component?.component_id))componentsById.set(component.component_id,component!);}
  for(const [index,groupValue] of groups.entries()){
    const group=object(groupValue),members=array(group?.component_ids);
    if(!group||!validId(group.group_id)||groupIds.has(group.group_id)||!validIdArray(group.component_ids,true)||members.length<2||members.some(id=>!componentIds.has(id)))valid=false;
    else{groupIds.add(group.group_id);for(const member of members)if(object(componentsById.get(member)?.stacking)?.replacement_group!==group.group_id)valid=false;}
    if(!group)add(diagnostics,"control_v2.stacking","Replacement group is malformed",`${path}/replacement_groups/${index}`);
  }
  for(const relationValue of dominance){
    const relation=object(relationValue),suppressed=array(relation?.suppressed_component_ids);
    if(!relation||!validId(relation.dominant_component_id)||!componentIds.has(relation.dominant_component_id)||!validIdArray(relation.suppressed_component_ids,true)||suppressed.some(id=>!componentIds.has(id)||id===relation.dominant_component_id)){valid=false;continue;}
    const targets=edges.get(relation.dominant_component_id)??new Set<string>();suppressed.forEach(id=>targets.add(id));edges.set(relation.dominant_component_id,targets);
    const inline=array(object(componentsById.get(relation.dominant_component_id)?.stacking)?.dominates_component_ids);if(suppressed.some(id=>!inline.includes(id)))valid=false;
  }
  for(const componentValue of componentValues){
    const component=object(componentValue),stacking=object(component?.stacking);if(!component||!stacking)continue;
    if(stacking.replacement_group!==undefined){const group=groups.map(object).find(item=>item?.group_id===stacking.replacement_group);if(!group||!array(group.component_ids).includes(component.component_id))valid=false;}
    for(const subordinate of array(stacking.dominates_component_ids)){const targets=edges.get(component.component_id);if(!targets?.has(subordinate))valid=false;}
  }
  const state=new Map<string,number>();let cyclic=false;
  const visit=(id:string):void=>{if(state.get(id)===1){cyclic=true;return;}if(state.get(id)===2)return;state.set(id,1);for(const child of edges.get(id)??[])visit(child);state.set(id,2);};
  componentIds.forEach(visit);
  if(cyclic)valid=false;
  if(!valid)add(diagnostics,"control_v2.stacking","Replacement groups and dominance relationships must use local, unique, acyclic component references",path);
}

function validateModel(modelValue:unknown,row:ObjectValue,authority:Authority,ledgerByKey:Map<string,ObjectValue>,effectIds:Set<string>,diagnostics:Diagnostic[],path:string):void{
  const model=object(modelValue);if(!model){add(diagnostics,"control_v2.coverage","Modeled ledger rows require a full model",path);return;}
  if(!validId(model.effect_id)||effectIds.has(model.effect_id))add(diagnostics,"control_v2.ids","Modeled effects require globally unique stable effect IDs",`${path}/effect_id`);else effectIds.add(model.effect_id);
  const entity=authority.entities.find(candidate=>candidate.id===row.entity_id) as unknown as ObjectValue|undefined;
  validatePolicy(model.policy,row,entity,diagnostics,`${path}/policy`);
  const requiredConcentration=validateConcentration(model.concentration,entity,diagnostics,`${path}/concentration`);
  const selectorValues=array(model.target_selectors),selectorIds=new Set<string>(),areaIds=new Set<string>();
  if(!selectorValues.length)add(diagnostics,"control_v2.target","Modeled effects require at least one target selector",`${path}/target_selectors`);
  for(const [index,selectorValue] of selectorValues.entries()){
    const selectorPath=`${path}/target_selectors/${index}`,id=validateSelector(selectorValue,diagnostics,selectorPath),selector=object(selectorValue),area=object(selector?.area);
    if(id){if(selectorIds.has(id))add(diagnostics,"control_v2.ids","Selector IDs must be unique within a model",`${selectorPath}/selector_id`);selectorIds.add(id);}
    if(validId(area?.area_id)){if(areaIds.has(area.area_id))add(diagnostics,"control_v2.ids","Area IDs must be unique within a model",`${selectorPath}/area/area_id`);areaIds.add(area.area_id);}
  }
  const componentValues=array(model.components),componentIds=new Set<string>(),componentsById=new Map<string,ObjectValue>();
  if(!componentValues.length)add(diagnostics,"control_v2.ids","Modeled effects require at least one component",`${path}/components`);
  for(const [index,componentValue] of componentValues.entries()){
    const component=object(componentValue),id=component?.component_id;if(validId(id)){if(componentIds.has(id))add(diagnostics,"control_v2.ids","Component IDs must be unique within a model",`${path}/components/${index}/component_id`);componentIds.add(id);if(component)componentsById.set(id,component);}
  }
  for(const [index,componentValue] of componentValues.entries())validateComponent(componentValue,diagnostics,`${path}/components/${index}`,selectorIds,areaIds,componentIds,requiredConcentration);
  const resolutionValues=array(model.resolutions),gateIds=new Set<string>(),branchIds=new Set<string>(),referencedComponents=new Set<string>();
  if(!resolutionValues.length)add(diagnostics,"control_v2.branch","Modeled effects require at least one explicit resolution",`${path}/resolutions`);
  for(const [index,resolutionValue] of resolutionValues.entries())validateResolution(resolutionValue,diagnostics,`${path}/resolutions/${index}`,selectorIds,componentIds,componentsById,gateIds,branchIds,referencedComponents);
  if([...componentIds].some(id=>!referencedComponents.has(id)))add(diagnostics,"control_v2.branch","Every model component must appear in at least one branch transition",`${path}/resolutions`);
  for(const selectorValue of selectorValues){const area=object(object(selectorValue)?.area);if(!area?.persistent)continue;const resolutions=resolutionValues.map(object);for(const trigger of ["entry","start_turn"])if(!resolutions.some(gate=>gate?.trigger===trigger))add(diagnostics,"control_v2.area","Persistent entry/start-turn areas require matching resolution gates",`${path}/resolutions`);const areaComponents=componentValues.map(object).filter(component=>object(component?.duration)?.kind==="while_in_area"&&object(component?.duration)?.area_id===area.area_id);if(!areaComponents.length||areaComponents.some(component=>!array(object(component?.cadence)?.end).includes("exit")))add(diagnostics,"control_v2.area","Persistent area effects require explicit exit cadence",`${path}/components`);}
  validateRelationships(model.relationships,componentValues,componentIds,diagnostics,`${path}/relationships`);
  const inheritance=object(model.inheritance);
  if(inheritance?.kind==="none"){
    if(row.tier!==0)add(diagnostics,"control_v2.inheritance","Non-base modeled tiers require resolved lower-tier inheritance",`${path}/inheritance`);
  }else if(inheritance?.kind==="resolved"){
    const sourceTier=inheritance.source_tier,calculatorFeature=authority.calculator.features.find(feature=>feature.entity_id===row.entity_id);
    if(!Number.isInteger(sourceTier)||sourceTier<0||sourceTier>=row.tier||!calculatorFeature?.tiers.some(tier=>tier.tier===sourceTier))add(diagnostics,"control_v2.inheritance","Resolved inheritance must reference a lower canonical tier",`${path}/inheritance`);
    const source=ledgerByKey.get(`${row.entity_id}:T${String(sourceTier)}`),sourceModel=source?.disposition==="modeled"?object(source.model):undefined;
    if(sourceModel){const retainedComponents=new Set(componentValues.map(value=>object(value)?.component_id));const retainedSelectors=new Set(selectorValues.map(value=>object(value)?.selector_id));if(array(sourceModel.components).some(value=>!retainedComponents.has(object(value)?.component_id))||array(sourceModel.target_selectors).some(value=>!retainedSelectors.has(object(value)?.selector_id)))add(diagnostics,"control_v2.inheritance","Resolved tier models must retain inherited component and selector IDs",`${path}/inheritance`);}
  }else add(diagnostics,"control_v2.inheritance","Modeled effects require explicit inheritance",`${path}/inheritance`);
  if(!selectorValues.length||!componentValues.length||!resolutionValues.length)add(diagnostics,"control_v2.inheritance","Resolved tier inheritance must contain a full model",path);
}

function validateMasteries(value:unknown,diagnostics:Diagnostic[],path:string):void{
  const masteries=array(value),ids=masteries.map(item=>object(item)?.mastery_id),componentIds=new Set<string>();
  if(!same(ids,EXPECTED_MASTERIES.map(item=>item.mastery_id)))add(diagnostics,"control_v2.ids","Control masteries must be the canonical Slow, Push, and Sap set",path);
  for(const [index,expected] of EXPECTED_MASTERIES.entries()){
    const mastery=object(masteries[index]),masteryPath=`${path}/${index}`,component=object(mastery?.component);
    if(!mastery||mastery.mastery_id!==expected.mastery_id||!validId(mastery.mastery_id))add(diagnostics,"control_v2.ids","Mastery IDs must be stable and ordered",`${masteryPath}/mastery_id`);
    if(mastery?.minimum_level!==expected.minimum_level||!same(mastery?.trigger,expected.trigger))add(diagnostics,"control_v2.timing","Mastery availability and trigger must remain canonical",masteryPath);
    if(component&&validId(component.component_id)){if(componentIds.has(component.component_id))add(diagnostics,"control_v2.ids","Mastery component IDs must be unique",`${masteryPath}/component/component_id`);componentIds.add(component.component_id);}
  }
  for(const [index,expected] of EXPECTED_MASTERIES.entries()){
    const mastery=object(masteries[index]),component=object(mastery?.component),masteryPath=`${path}/${index}`;if(!component){add(diagnostics,"control_v2.ids","Masteries require one explicit component",`${masteryPath}/component`);continue;}
    validateComponent(component,diagnostics,`${masteryPath}/component`,undefined,new Set(),componentIds,false);
    if(!same(component.target_selector_ids,expected.component.target_selector_ids))add(diagnostics,"control_v2.target","Mastery target semantics must remain canonical",`${masteryPath}/component/target_selector_ids`);
    if(!same(component.magnitude,expected.component.magnitude))add(diagnostics,"control_v2.magnitude","Mastery magnitude must remain canonical",`${masteryPath}/component/magnitude`);
    if(!same(component.duration,expected.component.duration)||!same(component.cadence,expected.component.cadence))add(diagnostics,"control_v2.timing","Mastery timing must remain canonical",`${masteryPath}/component`);
    if(!same(component.stacking,expected.component.stacking))add(diagnostics,"control_v2.stacking","Mastery stacking must remain canonical",`${masteryPath}/component/stacking`);
  }
}

export function validateControlAuthorityV2(authority:Authority):Diagnostic[]{
  const diagnostics:Diagnostic[]=[],path="/calculator/harness_mechanics/control_authority_v2",root=object((authority as any)?.calculator?.harness_mechanics?.control_authority_v2);
  if(!root){add(diagnostics,"control_v2.coverage","Harness mechanics require control_authority_v2",path);return diagnostics;}
  if(root.contract_version!=="2.0.0")add(diagnostics,"control_v2.version","Unsupported control-authority contract version",`${path}/contract_version`);
  if(!same(root.active_profile,PROFILE))add(diagnostics,"control_v2.disposition","The active control profile must preserve all maintainer rulings",`${path}/active_profile`);
  if(!same(root.target_data_requirements,["walking_speed","movement_modes","hover","nonvisual_senses"]))add(diagnostics,"control_v2.target","Control target-data requirements must remain complete and canonical",`${path}/target_data_requirements`);
  if(!same(root.policy_inputs,POLICY))add(diagnostics,"control_v2.timing","Control policy inputs must preserve the three-round horizon, action economy, resources, and concentration rules",`${path}/policy_inputs`);
  validateMasteries(root.masteries,diagnostics,`${path}/masteries`);
  const tactical=object(root.tactical_master);
  if(!tactical||tactical.minimum_level!==9||!same(tactical.choice_mastery_ids,["mastery_push","mastery_sap","mastery_slow"])||tactical.choice_timing!=="declaration"||tactical.behavior!=="replaces_kinetic_mastery")add(diagnostics,"control_v2.timing","Tactical Master must become available at level 9 and replace Kinetic Mastery on declaration",`${path}/tactical_master`);
  const ledger=array(root.ledger),keys=ledger.map(row=>tierKey(object(row)??{})),ledgerByKey=new Map<string,ObjectValue>();
  for(const rowValue of ledger){const row=object(rowValue);if(row)ledgerByKey.set(tierKey(row),row);}
  if(!same(keys,CANONICAL_CONTROL_TIER_KEYS)||new Set(keys).size!==keys.length)add(diagnostics,"control_v2.coverage","The control ledger must contain the exact sorted canonical 49-tier universe",`${path}/ledger`);
  const counts={modeled:0,excluded_by_profile:0,unsupported_error:0};
  for(const rowValue of ledger){const row=object(rowValue);if(row&&row.disposition in counts)counts[row.disposition as keyof typeof counts]++;}
  if(counts.modeled!==9||counts.excluded_by_profile!==14||counts.unsupported_error!==26)add(diagnostics,"control_v2.coverage","The foundation ledger must remain 9 modeled, 14 profile-excluded, and 26 unsupported",`${path}/ledger`);
  const effectIds=new Set<string>();
  for(const [index,rowValue] of ledger.entries()){
    const row=object(rowValue),rowPath=`${path}/ledger/${index}`;if(!row){add(diagnostics,"control_v2.coverage","Ledger row is malformed",rowPath);continue;}
    const key=tierKey(row) as CanonicalControlTierKey,excludedReason=EXCLUDED[key];
    if(MODELED.has(key)){
      if(row.disposition!=="modeled")add(diagnostics,"control_v2.disposition",`${key} must remain modeled`,rowPath);
      else validateModel(row.model,row,authority,ledgerByKey,effectIds,diagnostics,`${rowPath}/model`);
    }else if(excludedReason){
      if(row.disposition!=="excluded_by_profile"||row.profile_id!==PROFILE.id||row.reason!==excludedReason||row.model!==undefined)add(diagnostics,"control_v2.disposition",`${key} must retain its maintained profile exclusion`,rowPath);
    }else if((CANONICAL_CONTROL_TIER_KEYS as readonly string[]).includes(key)){
      if(row.disposition!=="unsupported_error"||row.reason!=="pending_authority_population"||row.model!==undefined)add(diagnostics,"control_v2.disposition",`${key} must fail closed as pending authority population`,rowPath);
    }
  }
  return diagnostics;
}

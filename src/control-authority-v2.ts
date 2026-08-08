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
const CONDITIONS=new Set(["blinded","charmed","incapacitated","prone","restrained","stunned"]);
const FORCED_DIRECTIONS=new Set(["straight_away_from_controller","toward_controller","controller_choice","vertical_up"]);
const FORCED_DESTINATIONS=new Set(["legal_unoccupied_space","legal_destination"]);
const SAVE_ABILITIES=new Set(["strength","constitution","dexterity","intelligence","wisdom","charisma","discipline_signature"]);
const SIZE_CATEGORIES=new Set(["tiny","small","medium","large"]);
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
const MODELED_POLICIES:Record<string,{activation:string;delivery:string;psi_cost:number;repeatability:string;mastery:string}>={
  ball_lightning:{activation:"action",delivery:"standalone",psi_cost:5,repeatability:"once_per_turn",mastery:"not_applicable"},
  forked_lightning:{activation:"action",delivery:"standalone",psi_cost:3,repeatability:"once_per_turn",mastery:"not_applicable"},
  mass_levitation:{activation:"action",delivery:"standalone",psi_cost:5,repeatability:"once_per_turn",mastery:"not_applicable"},
  glacial_spike:{activation:"on_hit",delivery:"attack_rider",psi_cost:0,repeatability:"unlimited",mastery:"stacks"},
  telekinetic_shove:{activation:"on_hit",delivery:"attack_rider",psi_cost:0,repeatability:"unlimited",mastery:"replaces_on_declaration"}
};
const CANONICAL_CONCENTRATION_ENTITIES=new Set(["ball_lightning","mass_levitation"]);

const EXPECTED_MASTERIES=[
  {mastery_id:"mastery_slow",minimum_level:3,trigger:["hit"],component:{component_id:"mastery_slow_speed_reduction",target_selector_ids:["manifested_strike_target"],magnitude:{kind:"speed_reduction",reduction:{kind:"flat_feet",value:10},movement_modes:MOVEMENT_MODES},duration:{kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1},cadence:{apply:["hit"],repeat:[],end:["start_turn"]},stacking:{key:"mastery_slow_speed_reduction",mode:"nonstacking",refresh:"duration",dominates_component_ids:[]}}},
  {mastery_id:"mastery_push",minimum_level:3,trigger:["hit"],component:{component_id:"mastery_push_forced_movement",target_selector_ids:["manifested_strike_large_or_smaller_target"],magnitude:{kind:"forced_movement",distance_feet:10,distance_mode:"up_to",movement_mode:"push",direction:"straight_away_from_controller",destination:"legal_destination"},duration:{kind:"instantaneous"},cadence:{apply:["hit"],repeat:[],end:["instantaneous_resolution"]},stacking:{key:"mastery_push_forced_movement",mode:"independent",refresh:"none",dominates_component_ids:[]}}},
  {mastery_id:"mastery_sap",minimum_level:3,trigger:["hit"],component:{component_id:"mastery_sap_attack_disadvantage",target_selector_ids:["manifested_strike_target"],magnitude:{kind:"attack_disadvantage",scope:"next_attack",count:1},duration:{kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1},cadence:{apply:["hit"],repeat:[],end:["start_turn"]},stacking:{key:"mastery_sap_attack_disadvantage",mode:"nonstacking",refresh:"duration",dominates_component_ids:[]}}}
] as const;

const object=(value:unknown):ObjectValue|undefined=>value!==null&&typeof value==="object"&&!Array.isArray(value)?value as ObjectValue:undefined;
const array=(value:unknown):any[]=>Array.isArray(value)?value:[];
const same=(left:unknown,right:unknown):boolean=>{
  if(left===right)return true;
  if(Array.isArray(left)||Array.isArray(right))return Array.isArray(left)&&Array.isArray(right)&&left.length===right.length&&left.every((item,index)=>same(item,right[index]));
  if(left===null||right===null||typeof left!=="object"||typeof right!=="object")return false;
  const leftObject=left as Record<string,unknown>,rightObject=right as Record<string,unknown>,leftKeys=Object.keys(leftObject).sort(),rightKeys=Object.keys(rightObject).sort();
  return leftKeys.length===rightKeys.length&&leftKeys.every((key,index)=>key===rightKeys[index]&&same(leftObject[key],rightObject[key]));
};
const tierKey=(row:ObjectValue):string=>`${String(row.entity_id)}:T${String(row.tier)}`;
const add=(diagnostics:Diagnostic[],code:string,message:string,path:string):void=>{diagnostics.push({severity:"error",code,message,path});};
const validId=(value:unknown):value is string=>typeof value==="string"&&ID.test(value);
const positiveInteger=(value:unknown):boolean=>Number.isInteger(value)&&Number(value)>0;
const nonnegativeInteger=(value:unknown):boolean=>Number.isInteger(value)&&Number(value)>=0;
const uniqueStrings=(value:unknown,nonempty=false):boolean=>Array.isArray(value)&&(!nonempty||value.length>0)&&value.every(item=>typeof item==="string")&&new Set(value).size===value.length;
const validEvents=(value:unknown,nonempty=false):boolean=>uniqueStrings(value,nonempty)&&array(value).every(item=>EVENTS.has(item));
const validIdArray=(value:unknown,nonempty=false):boolean=>uniqueStrings(value,nonempty)&&array(value).every(validId);
const validMovementModes=(value:unknown):boolean=>validIdArray(value,true)&&array(value).every(item=>MOVEMENT_MODES.includes(item));
const hasExactKeys=(value:unknown,keys:readonly string[]):boolean=>{
  const candidate=object(value);return Boolean(candidate)&&same(Object.keys(candidate!).sort(),[...keys].sort());
};
const hasOnlyKeys=(value:unknown,keys:readonly string[]):boolean=>{
  const candidate=object(value);return Boolean(candidate)&&Object.keys(candidate!).every(key=>keys.includes(key));
};

function validateMagnitude(value:unknown,diagnostics:Diagnostic[],path:string):void{
  const magnitude=object(value);let valid=Boolean(magnitude);
  switch(magnitude?.kind){
    case "condition":
      valid=hasExactKeys(magnitude,["kind","condition"])&&CONDITIONS.has(magnitude.condition);
      break;
    case "forced_movement":
      valid=hasExactKeys(magnitude,["kind","distance_feet","distance_mode","movement_mode","direction","destination"])
        &&positiveInteger(magnitude.distance_feet)&&["exact","up_to"].includes(magnitude.distance_mode)
        &&["push","pull","reposition","lift"].includes(magnitude.movement_mode)
        &&FORCED_DIRECTIONS.has(magnitude.direction)&&FORCED_DESTINATIONS.has(magnitude.destination);
      break;
    case "speed_reduction":{
      const reduction=object(magnitude.reduction);let reductionValid=false;
      if(reduction?.kind==="flat_feet")reductionValid=hasExactKeys(reduction,["kind","value"])&&positiveInteger(reduction.value);
      else if(reduction?.kind==="fraction")reductionValid=hasExactKeys(reduction,["kind","numerator","denominator"])&&positiveInteger(reduction.numerator)&&positiveInteger(reduction.denominator)&&reduction.numerator<reduction.denominator;
      else if(reduction?.kind==="terrain_multiplier")reductionValid=hasExactKeys(reduction,["kind","value"])&&typeof reduction.value==="number"&&Number.isFinite(reduction.value)&&reduction.value>1;
      valid=hasExactKeys(magnitude,["kind","reduction","movement_modes"])&&reductionValid&&validMovementModes(magnitude.movement_modes);
      break;
    }
    case "speed_zero":
    case "movement_option_denial":
      valid=hasExactKeys(magnitude,["kind","movement_modes"])&&validMovementModes(magnitude.movement_modes);
      break;
    case "attack_disadvantage":
      valid=magnitude.scope==="next_attack"
        ?hasExactKeys(magnitude,["kind","scope","count"])&&positiveInteger(magnitude.count)
        :magnitude.scope==="all_attacks"&&hasExactKeys(magnitude,["kind","scope"]);
      break;
    case "reaction_denial":
      valid=hasExactKeys(magnitude,["kind","scope"])&&magnitude.scope==="all_reactions";
      break;
    case "numerical_modifier":
      valid=hasExactKeys(magnitude,["kind","target","value"])&&magnitude.target==="armor_class"
        &&typeof magnitude.value==="number"&&Number.isFinite(magnitude.value)&&magnitude.value!==0;
      break;
    default:valid=false;
  }
  if(!valid)add(diagnostics,"control_v2.magnitude","Control component magnitude is incomplete or invalid",path);
}

interface ConcentrationState{required:boolean;maximumValue?:unknown;unit?:unknown}

function validateDuration(value:unknown,diagnostics:Diagnostic[],path:string,areaIds:Set<string>,concentration:ConcentrationState):void{
  const duration=object(value);let valid=Boolean(duration);
  switch(duration?.kind){
    case "instantaneous":
      valid=hasExactKeys(duration,["kind"]);
      break;
    case "relative":
      valid=hasExactKeys(duration,["kind","owner","anchor","offset_turns"])&&["controller","target"].includes(duration.owner)&&["start_turn","end_turn"].includes(duration.anchor)&&nonnegativeInteger(duration.offset_turns);
      break;
    case "while_in_area":
      valid=hasExactKeys(duration,["kind","area_id"])&&validId(duration.area_id)&&areaIds.has(duration.area_id);
      if(!valid)add(diagnostics,"control_v2.area","Area duration must reference a selector area",path);
      return;
    case "concentration":
      valid=hasExactKeys(duration,["kind","maximum_value","unit"])&&concentration.required&&positiveInteger(duration.maximum_value)
        &&["round","minute","hour"].includes(duration.unit)&&duration.maximum_value===concentration.maximumValue&&duration.unit===concentration.unit;
      if(!valid)add(diagnostics,"control_v2.concentration","Concentration duration must match a required concentration model",path);
      return;
    default:valid=false;
  }
  if(!valid)add(diagnostics,"control_v2.timing","Control component duration must have an explicit owner and anchor",path);
}

function validateCadence(value:unknown,diagnostics:Diagnostic[],path:string):void{
  const cadence=object(value);
  if(!hasExactKeys(cadence,["apply","repeat","end"])||!validEvents(cadence?.apply,true)||!validEvents(cadence?.repeat)||!validEvents(cadence?.end))add(diagnostics,"control_v2.timing","Control cadence must use explicit supported events",path);
}

function validateCount(value:unknown):boolean{
  const count=object(value);
  if(!count)return false;
  if(count.kind==="fixed"||count.kind==="up_to")return hasExactKeys(count,["kind","value"])&&positiveInteger(count.value);
  if(count.kind==="proficiency_bonus"||count.kind==="cluster_remainder")return hasExactKeys(count,["kind"]);
  if(count.kind!=="weighted_slots"||!hasExactKeys(count,["kind","slots","size_costs"])||!positiveInteger(count.slots))return false;
  const costs=object(count.size_costs);
  return Boolean(costs)&&Object.keys(costs!).length>0&&Object.entries(costs!).every(([key,cost])=>SIZE_CATEGORIES.has(key)&&positiveInteger(cost));
}

function validateRestriction(value:unknown):boolean{
  const restriction=object(value);
  switch(restriction?.kind){
    case "visibility":return hasExactKeys(restriction,["kind","requirement"])&&restriction.requirement==="controller_can_see";
    case "maximum_size":return hasExactKeys(restriction,["kind","size"])&&restriction.size==="large_or_smaller";
    case "unique_targets":return hasExactKeys(restriction,["kind","required"])&&restriction.required===true;
    case "excludes_primary_target":return hasExactKeys(restriction,["kind","required"])&&restriction.required===true;
    default:return false;
  }
}

function validateArea(value:unknown,diagnostics:Diagnostic[],path:string):string|undefined{
  const area=object(value);if(!area)return undefined;
  const allowedKeys=["area_id","shape","origin","radius_feet","height_feet","length_feet","width_feet","persistent","triggers","exit_behavior","entry_policy","movement"];
  let valid=hasOnlyKeys(area,allowedKeys)&&validId(area.area_id)&&["sphere","cylinder","cone","line"].includes(area.shape)
    &&["controller","primary_target","selected_point","departure_or_arrival"].includes(area.origin)
    &&typeof area.persistent==="boolean"&&validEvents(area.triggers,true)&&["ends_area_effects","none"].includes(area.exit_behavior);
  if(area.shape==="sphere")valid=valid&&positiveInteger(area.radius_feet)&&area.height_feet===undefined&&area.length_feet===undefined&&area.width_feet===undefined;
  else if(area.shape==="cylinder")valid=valid&&positiveInteger(area.radius_feet)&&positiveInteger(area.height_feet)&&area.length_feet===undefined&&area.width_feet===undefined;
  else if(area.shape==="cone")valid=valid&&positiveInteger(area.length_feet)&&area.radius_feet===undefined&&area.height_feet===undefined&&area.width_feet===undefined;
  else if(area.shape==="line")valid=valid&&positiveInteger(area.length_feet)&&positiveInteger(area.width_feet)&&area.radius_feet===undefined&&area.height_feet===undefined;
  if(area.persistent){
    const entryPolicy=object(area.entry_policy),movement=object(area.movement);
    const validEntry=hasExactKeys(entryPolicy,["frequency","moved_area_counts_as_entry"])&&entryPolicy?.frequency==="once_per_turn"&&typeof entryPolicy?.moved_area_counts_as_entry==="boolean";
    const validMovement=movement?.kind==="stationary"
      ?hasExactKeys(movement,["kind"])
      :movement?.kind==="controller_reposition"&&hasExactKeys(movement,["kind","controller_action","distance_feet"])&&movement.controller_action==="bonus_action"&&positiveInteger(movement.distance_feet);
    valid=valid&&validEntry&&validMovement&&array(area.triggers).includes("entry")&&array(area.triggers).includes("start_turn")&&area.exit_behavior==="ends_area_effects";
  }else valid=valid&&area.entry_policy===undefined&&area.movement===undefined;
  if(!valid)add(diagnostics,"control_v2.area","Control area must define typed persistence, entry, movement, dimensions, origin, triggers, and exit behavior",path);
  return validId(area.area_id)?area.area_id:undefined;
}

function validateSelector(value:unknown,diagnostics:Diagnostic[],path:string):string|undefined{
  const selector=object(value);if(!selector){add(diagnostics,"control_v2.target","Control target selector is missing",path);return undefined;}
  const range=object(selector.range),restrictions=array(selector.restrictions),selectorKeys=selector.area===undefined
    ?["selector_id","role","count","range","restrictions","gate_scope"]
    :["selector_id","role","count","range","restrictions","gate_scope","area"];
  const restrictionKinds=restrictions.map(item=>object(item)?.kind);
  const valid=hasExactKeys(selector,selectorKeys)&&validId(selector.selector_id)&&["primary","secondary","all"].includes(selector.role)&&validateCount(selector.count)
    &&hasExactKeys(range,["feet","origin"])&&nonnegativeInteger(range?.feet)&&["controller","primary_target","selected_point","departure_or_arrival"].includes(range?.origin)
    &&Array.isArray(selector.restrictions)&&restrictions.every(validateRestriction)&&new Set(restrictionKinds).size===restrictionKinds.length
    &&["independent_per_target","shared"].includes(selector.gate_scope);
  if(!valid)add(diagnostics,"control_v2.target","Control target selector must define typed role, count, range, restrictions, and gate scope",path);
  if(selector.area!==undefined)validateArea(selector.area,diagnostics,path+"/area");
  return validId(selector.selector_id)?selector.selector_id:undefined;
}

function validateComponent(value:unknown,diagnostics:Diagnostic[],path:string,selectorIds:Set<string>|undefined,areaIds:Set<string>,componentIds:Set<string>,concentration:ConcentrationState):void{
  const component=object(value);if(!component){add(diagnostics,"control_v2.ids","Control component is missing",path);return;}
  if(!hasExactKeys(component,["component_id","target_selector_ids","magnitude","duration","cadence","stacking"])||!validId(component.component_id))add(diagnostics,"control_v2.ids","Control component requires an exact shape and stable component_id",path+"/component_id");
  const targetIds=array(component.target_selector_ids);
  if(!validIdArray(component.target_selector_ids,true)||(selectorIds&&targetIds.some(id=>!selectorIds.has(id))))add(diagnostics,"control_v2.target","Control component must reference defined target selectors",path+"/target_selector_ids");
  validateMagnitude(component.magnitude,diagnostics,path+"/magnitude");
  validateDuration(component.duration,diagnostics,path+"/duration",areaIds,concentration);
  validateCadence(component.cadence,diagnostics,path+"/cadence");
  const stacking=object(component.stacking),dominates=array(stacking?.dominates_component_ids),mode=stacking?.mode;
  const stackingKeys=stacking?.replacement_group===undefined
    ?["key","mode","refresh","dominates_component_ids"]
    :["key","mode","refresh","replacement_group","dominates_component_ids"];
  const valid=hasExactKeys(stacking,stackingKeys)&&validId(stacking?.key)&&["stacks","nonstacking","replace","dominates","independent"].includes(mode)&&["duration","none"].includes(stacking?.refresh)
    &&validIdArray(stacking?.dominates_component_ids)&&dominates.every(id=>componentIds.has(id)&&id!==component.component_id)
    &&(stacking?.replacement_group===undefined||validId(stacking.replacement_group))
    &&(mode!=="replace"||validId(stacking?.replacement_group))&&(mode!=="dominates"||dominates.length>0)&&(!dominates.length||mode==="dominates"||mode==="replace");
  if(!valid)add(diagnostics,"control_v2.stacking","Control component stacking references must be complete and local to the model",path+"/stacking");
}

function validateResolution(value:unknown,diagnostics:Diagnostic[],path:string,selectorIds:Set<string>,selectorScopes:Map<string,unknown>,componentIds:Set<string>,componentsById:Map<string,ObjectValue>,gateIds:Set<string>,branchIds:Set<string>,referencedComponents:Set<string>):void{
  const gate=object(value);if(!gate){add(diagnostics,"control_v2.branch","Control resolution is missing",path);return;}
  if(!hasExactKeys(gate,["gate_id","selector_ids","trigger","gate_scope","resolution"])||!validId(gate.gate_id)||gateIds.has(gate.gate_id))add(diagnostics,"control_v2.ids","Resolution gates require exact shapes and stable unique IDs",path+"/gate_id");else gateIds.add(gate.gate_id);
  const selected=array(gate.selector_ids);
  if(!validIdArray(gate.selector_ids,true)||selected.some(id=>!selectorIds.has(id)||selectorScopes.get(id)!==gate.gate_scope)||!["independent_per_target","shared"].includes(gate.gate_scope))add(diagnostics,"control_v2.target","Resolution gates must reference defined selectors with explicit gate scope",path);
  if(!EVENTS.has(gate.trigger))add(diagnostics,"control_v2.timing","Resolution gates require an explicit supported trigger",path+"/trigger");
  const resolution=object(gate.resolution),branches=array(resolution?.branches),kind=resolution?.kind;
  const resolutionKeys=kind==="saving_throw"?["kind","ability","branches"]:["kind","branches"];
  let complete=hasExactKeys(resolution,resolutionKeys)&&["attack_roll","saving_throw","no_save","other"].includes(kind)&&branches.length>0,cadenceComplete=true,graphComplete=true;
  const outcomes=branches.map(branch=>object(branch)?.outcome),expectedOutcomes=kind==="attack_roll"?["attack_hit","attack_miss"]:kind==="saving_throw"?["save_success","save_failure"]:kind==="no_save"?["no_save"]:kind==="other"?["other"]:[];
  complete=complete&&same([...outcomes].sort(),[...expectedOutcomes].sort());
  if(kind==="saving_throw")complete=complete&&SAVE_ABILITIES.has(resolution?.ability);
  else complete=complete&&resolution?.ability===undefined;
  for(const [branchIndex,branchValue] of branches.entries()){
    const branch=object(branchValue),branchPath=path+"/resolution/branches/"+String(branchIndex);
    if(!branch){add(diagnostics,"control_v2.branch","Resolution branch is missing",branchPath);complete=false;continue;}
    if(!hasExactKeys(branch,["branch_id","outcome","applies","replaces","terminates","refreshes","next_gate_ids"])||!validId(branch.branch_id)||branchIds.has(branch.branch_id))add(diagnostics,"control_v2.ids","Branch IDs must be stable and unique within a model",branchPath+"/branch_id");else branchIds.add(branch.branch_id);
    if(!["attack_hit","attack_miss","save_success","save_failure","no_save","other"].includes(branch.outcome))complete=false;
    const transitions=new Map<string,any[]>();
    for(const field of ["applies","replaces","terminates","refreshes"]){
      const refs=array(branch[field]);
      transitions.set(field,refs);refs.forEach(id=>referencedComponents.add(id));
      if(!validIdArray(branch[field])||refs.some(id=>!componentIds.has(id)))complete=false;
      const cadenceField=field==="applies"?"apply":field==="refreshes"?"repeat":"end";
      for(const id of refs){const component=componentsById.get(id),cadence=object(component?.cadence);if(component&&!array(cadence?.[cadenceField]).includes(gate.trigger))cadenceComplete=false;}
    }
    const transitionSets=[...transitions.values()].map(refs=>new Set(refs));
    for(let left=0;left<transitionSets.length;left++)for(let right=left+1;right<transitionSets.length;right++)if([...transitionSets[left]!].some(id=>transitionSets[right]!.has(id)))complete=false;
    if(!validIdArray(branch.next_gate_ids))graphComplete=false;
  }
  if(!cadenceComplete)add(diagnostics,"control_v2.timing","Branch transitions must match component apply, repeat, and end cadence",path+"/resolution");
  if(!graphComplete)add(diagnostics,"control_v2.graph","Every branch must declare a unique stable next-gate list",path+"/resolution");
  if(!complete)add(diagnostics,"control_v2.branch","Resolution branches must be complete, conflict-free, and reference defined components",path+"/resolution");
}

function validateResolutionGraph(rootValue:unknown,resolutionValues:any[],attackRider:boolean,diagnostics:Diagnostic[],path:string):void{
  const roots=array(rootValue),gateById=new Map<string,ObjectValue>(),edges=new Map<string,Set<string>>(),incoming=new Map<string,number>();
  let valid=validIdArray(rootValue,true);
  for(const gateValue of resolutionValues){const gate=object(gateValue);if(validId(gate?.gate_id)&&!gateById.has(gate.gate_id))gateById.set(gate.gate_id,gate!);}
  if(roots.some(id=>!gateById.has(id)))valid=false;
  const branchRecords:Array<{source:string;outcome:unknown;next:string[]}>= [];
  for(const [source,gate] of gateById){
    const branches=array(object(gate.resolution)?.branches);
    for(const branchValue of branches){
      const branch=object(branchValue),next=array(branch?.next_gate_ids);
      if(!branch||!validIdArray(branch.next_gate_ids)){valid=false;continue;}
      branchRecords.push({source,outcome:branch.outcome,next});
      const targets=edges.get(source)??new Set<string>();
      for(const target of next){
        if(!gateById.has(target)){valid=false;continue;}
        targets.add(target);incoming.set(target,(incoming.get(target)??0)+1);
      }
      edges.set(source,targets);
    }
  }
  if(roots.some(root=>Boolean(incoming.get(root))))valid=false;
  const reachable=new Set<string>(),walk=(starts:Iterable<string>):Set<string>=>{
    const seen=new Set<string>(),stack=[...starts];
    while(stack.length){const id=stack.pop()!;if(seen.has(id)||!gateById.has(id))continue;seen.add(id);for(const next of edges.get(id)??[])stack.push(next);}
    return seen;
  };
  for(const id of walk(roots))reachable.add(id);
  if([...gateById.keys()].some(id=>!reachable.has(id)))valid=false;
  const state=new Map<string,number>();let cyclic=false;
  const visit=(id:string):void=>{if(state.get(id)===1){cyclic=true;return;}if(state.get(id)===2)return;state.set(id,1);for(const next of edges.get(id)??[])visit(next);state.set(id,2);};
  gateById.forEach((_gate,id)=>visit(id));
  if(cyclic)valid=false;
  if(attackRider){
    if(roots.some(root=>object(gateById.get(root)?.resolution)?.kind!=="attack_roll"))valid=false;
    const hitReach=new Set<string>();
    for(const branch of branchRecords){
      const descendants=walk(branch.next);
      if(branch.outcome==="attack_hit")for(const id of descendants)hitReach.add(id);
      if(branch.outcome==="attack_miss"&&[...descendants].some(id=>object(gateById.get(id)?.resolution)?.kind==="saving_throw"))valid=false;
    }
    for(const [id,gate] of gateById)if(gate.trigger==="save"&&object(gate.resolution)?.kind==="saving_throw"&&!roots.includes(id)&&!hitReach.has(id))valid=false;
  }
  if(!valid)add(diagnostics,"control_v2.graph","Resolution graph roots and branch transitions must be known, reachable, acyclic, order-neutral, and hit-gated",path);
}

function validateConcentration(value:unknown,requiredExpected:boolean,diagnostics:Diagnostic[],path:string):ConcentrationState{
  const concentration=object(value);
  if(concentration?.kind==="none"){
    if(!hasExactKeys(concentration,["kind"])||requiredExpected)add(diagnostics,"control_v2.concentration","Canonical concentration features require a complete concentration model",path);
    return {required:false};
  }
  if(concentration?.kind!=="required"){
    add(diagnostics,"control_v2.concentration","Control concentration must be explicitly none or required",path);return {required:false};
  }
  const maximum=object(concentration.maximum_duration),termination=array(concentration.termination);
  const valid=hasExactKeys(concentration,["kind","startup","occupancy","replacement","maximum_duration","termination"])&&hasExactKeys(maximum,["value","unit"])
    &&concentration.startup==="on_resolution"&&concentration.occupancy==="one_controller_slot"&&concentration.replacement==="new_effect_ends_existing"
    &&positiveInteger(maximum?.value)&&["round","minute","hour"].includes(maximum?.unit)&&uniqueStrings(concentration.termination,true)
    &&same([...termination].sort(),[...TERMINATION].sort())&&requiredExpected;
  if(!valid)add(diagnostics,"control_v2.concentration","Required concentration must define startup, occupancy, replacement, maximum duration, all termination events, and a canonical entity flag",path);
  return {required:true,maximumValue:maximum?.value,unit:maximum?.unit};
}

function validatePolicy(value:unknown,row:ObjectValue,diagnostics:Diagnostic[],path:string):void{
  const policy=object(value),expected=MODELED_POLICIES[String(row.entity_id)];
  const valid=hasExactKeys(policy,["activation","declaration","delivery","psi_cost","overload_tier","blood_tax","repeatability","mastery"])&&Boolean(expected)
    &&policy?.activation===expected?.activation&&policy?.declaration==="declaration"&&policy?.delivery===expected?.delivery
    &&policy?.psi_cost===expected?.psi_cost&&policy?.overload_tier===row.tier
    &&policy?.blood_tax===(row.tier===0?"none":"tier_formula")&&policy?.repeatability===expected?.repeatability&&policy?.mastery===expected?.mastery;
  if(!valid)add(diagnostics,"control_v2.timing","Control policy must preserve pinned canonical declaration-time costs, activation, delivery, resources, repeatability, and mastery interaction",path);
}

function validateRelationships(value:unknown,componentValues:any[],componentIds:Set<string>,diagnostics:Diagnostic[],path:string):void{
  const relationships=object(value),groups=array(relationships?.replacement_groups),dominance=array(relationships?.dominance),groupIds=new Set<string>(),dominantIds=new Set<string>(),edges=new Map<string,Set<string>>(),componentsById=new Map<string,ObjectValue>();
  let valid=hasExactKeys(relationships,["replacement_groups","dominance"])&&Array.isArray(relationships?.replacement_groups)&&Array.isArray(relationships?.dominance);
  for(const componentValue of componentValues){const component=object(componentValue);if(validId(component?.component_id))componentsById.set(component.component_id,component!);}
  for(const groupValue of groups){
    const group=object(groupValue),members=array(group?.component_ids);
    if(!hasExactKeys(group,["group_id","component_ids"])||!validId(group?.group_id)||groupIds.has(group!.group_id)||!validIdArray(group?.component_ids,true)||members.length<2||members.some(id=>!componentIds.has(id)))valid=false;
    else{groupIds.add(group!.group_id);for(const member of members)if(object(componentsById.get(member)?.stacking)?.replacement_group!==group!.group_id)valid=false;}
  }
  for(const relationValue of dominance){
    const relation=object(relationValue),suppressed=array(relation?.suppressed_component_ids);
    if(!hasExactKeys(relation,["dominant_component_id","suppressed_component_ids"])||!validId(relation?.dominant_component_id)||dominantIds.has(relation!.dominant_component_id)
      ||!componentIds.has(relation!.dominant_component_id)||!validIdArray(relation?.suppressed_component_ids,true)||suppressed.some(id=>!componentIds.has(id)||id===relation!.dominant_component_id)){valid=false;continue;}
    dominantIds.add(relation!.dominant_component_id);
    const targets=new Set<string>();suppressed.forEach(id=>targets.add(id));edges.set(relation!.dominant_component_id,targets);
    const inline=array(object(componentsById.get(relation!.dominant_component_id)?.stacking)?.dominates_component_ids);
    if(!same([...suppressed].sort(),[...inline].sort()))valid=false;
  }
  for(const componentValue of componentValues){
    const component=object(componentValue),stacking=object(component?.stacking);if(!component||!stacking)continue;
    if(stacking.replacement_group!==undefined){const group=groups.map(object).find(item=>item?.group_id===stacking.replacement_group);if(!group||!array(group.component_ids).includes(component.component_id))valid=false;}
    const inline=array(stacking.dominates_component_ids),targets=edges.get(component.component_id);
    if(inline.length&&(!targets||!same([...inline].sort(),[...targets].sort())))valid=false;
  }
  const state=new Map<string,number>();let cyclic=false;
  const visit=(id:string):void=>{if(state.get(id)===1){cyclic=true;return;}if(state.get(id)===2)return;state.set(id,1);for(const child of edges.get(id)??[])visit(child);state.set(id,2);};
  componentIds.forEach(visit);
  if(cyclic)valid=false;
  if(!valid)add(diagnostics,"control_v2.stacking","Replacement groups and dominance relationships must use exact, bidirectional, local, unique, acyclic component references",path);
}

function validateModel(modelValue:unknown,row:ObjectValue,authority:Authority,ledgerByKey:Map<string,ObjectValue>,effectIds:Set<string>,diagnostics:Diagnostic[],path:string):void{
  const model=object(modelValue);if(!model){add(diagnostics,"control_v2.coverage","Modeled ledger rows require a full model",path);return;}
  if(!hasExactKeys(model,["effect_id","inheritance","policy","target_selectors","components","root_gate_ids","resolutions","concentration","relationships"]))add(diagnostics,"control_v2.coverage","Modeled ledger rows require the exact v2 model shape",path);
  if(!validId(model.effect_id)||effectIds.has(model.effect_id))add(diagnostics,"control_v2.ids","Modeled effects require globally unique stable effect IDs",path+"/effect_id");else effectIds.add(model.effect_id);
  validatePolicy(model.policy,row,diagnostics,path+"/policy");
  const concentration=validateConcentration(model.concentration,CANONICAL_CONCENTRATION_ENTITIES.has(String(row.entity_id)),diagnostics,path+"/concentration");
  const selectorValues=array(model.target_selectors),selectorIds=new Set<string>(),selectorScopes=new Map<string,unknown>(),areaIds=new Set<string>();
  if(!selectorValues.length)add(diagnostics,"control_v2.target","Modeled effects require at least one target selector",path+"/target_selectors");
  for(const [index,selectorValue] of selectorValues.entries()){
    const selectorPath=path+"/target_selectors/"+String(index),id=validateSelector(selectorValue,diagnostics,selectorPath),selector=object(selectorValue),area=object(selector?.area);
    if(id){if(selectorIds.has(id))add(diagnostics,"control_v2.ids","Selector IDs must be unique within a model",selectorPath+"/selector_id");selectorIds.add(id);selectorScopes.set(id,selector?.gate_scope);}
    if(validId(area?.area_id)){if(areaIds.has(area.area_id))add(diagnostics,"control_v2.ids","Area IDs must be unique within a model",selectorPath+"/area/area_id");areaIds.add(area.area_id);}
  }
  const componentValues=array(model.components),componentIds=new Set<string>(),componentsById=new Map<string,ObjectValue>();
  if(!componentValues.length)add(diagnostics,"control_v2.ids","Modeled effects require at least one component",path+"/components");
  for(const [index,componentValue] of componentValues.entries()){
    const component=object(componentValue),id=component?.component_id;
    if(validId(id)){if(componentIds.has(id))add(diagnostics,"control_v2.ids","Component IDs must be unique within a model",path+"/components/"+String(index)+"/component_id");componentIds.add(id);if(component)componentsById.set(id,component);}
  }
  for(const [index,componentValue] of componentValues.entries())validateComponent(componentValue,diagnostics,path+"/components/"+String(index),selectorIds,areaIds,componentIds,concentration);
  const resolutionValues=array(model.resolutions),gateIds=new Set<string>(),branchIds=new Set<string>(),referencedComponents=new Set<string>();
  if(!resolutionValues.length)add(diagnostics,"control_v2.branch","Modeled effects require at least one explicit resolution",path+"/resolutions");
  for(const [index,resolutionValue] of resolutionValues.entries())validateResolution(resolutionValue,diagnostics,path+"/resolutions/"+String(index),selectorIds,selectorScopes,componentIds,componentsById,gateIds,branchIds,referencedComponents);
  validateResolutionGraph(model.root_gate_ids,resolutionValues,model.policy?.delivery==="attack_rider",diagnostics,path+"/root_gate_ids");
  if([...componentIds].some(id=>!referencedComponents.has(id)))add(diagnostics,"control_v2.branch","Every model component must appear in at least one branch transition",path+"/resolutions");
  for(const selectorValue of selectorValues){
    const selector=object(selectorValue),area=object(selector?.area);if(!area?.persistent)continue;
    const resolutions=resolutionValues.map(object);
    for(const trigger of ["entry","start_turn"])if(!resolutions.some(gate=>gate?.trigger===trigger&&array(gate?.selector_ids).includes(selector?.selector_id)))add(diagnostics,"control_v2.area","Persistent entry/start-turn areas require matching selector resolution gates",path+"/resolutions");
    const areaComponents=componentValues.map(object).filter(component=>object(component?.duration)?.kind==="while_in_area"&&object(component?.duration)?.area_id===area.area_id);
    if(!areaComponents.length||areaComponents.some(component=>!array(object(component?.cadence)?.end).includes("exit")||!array(component?.target_selector_ids).includes(selector?.selector_id)))add(diagnostics,"control_v2.area","Persistent area effects require explicit exit cadence and the area-owning selector",path+"/components");
  }
  validateRelationships(model.relationships,componentValues,componentIds,diagnostics,path+"/relationships");
  const inheritance=object(model.inheritance);
  if(inheritance?.kind==="none"){
    if(!hasExactKeys(inheritance,["kind"])||row.tier!==0)add(diagnostics,"control_v2.inheritance","Only base modeled tiers may declare no inheritance",path+"/inheritance");
  }else if(inheritance?.kind==="resolved"){
    const sourceTier=inheritance.source_tier,calculatorFeature=authority.calculator.features.find(feature=>feature.entity_id===row.entity_id);
    if(!hasExactKeys(inheritance,["kind","source_tier"])||!Number.isInteger(sourceTier)||sourceTier<0||sourceTier>=row.tier||!calculatorFeature?.tiers.some(tier=>tier.tier===sourceTier))add(diagnostics,"control_v2.inheritance","Resolved inheritance must reference a lower canonical tier",path+"/inheritance");
    const source=ledgerByKey.get(String(row.entity_id)+":T"+String(sourceTier)),sourceModel=source?.disposition==="modeled"?object(source.model):undefined;
    if(sourceModel){
      const retainedComponents=new Set(componentValues.map(value=>object(value)?.component_id)),retainedSelectors=new Set(selectorValues.map(value=>object(value)?.selector_id));
      if(array(sourceModel.components).some(value=>!retainedComponents.has(object(value)?.component_id))||array(sourceModel.target_selectors).some(value=>!retainedSelectors.has(object(value)?.selector_id)))add(diagnostics,"control_v2.inheritance","Resolved tier models must retain inherited component and selector IDs",path+"/inheritance");
    }
  }else add(diagnostics,"control_v2.inheritance","Modeled effects require explicit inheritance",path+"/inheritance");
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
    validateComponent(component,diagnostics,`${masteryPath}/component`,undefined,new Set(),componentIds,{required:false});
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

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
const MOVEMENT_MODES=["walk","fly","swim","climb","burrow"];
const CONDITIONS=new Set(["blinded","charmed","incapacitated","prone","restrained","stunned"]);
const SAVE_ABILITIES=new Set(["strength","constitution","dexterity","intelligence","wisdom","charisma","discipline_signature"]);
const SIZE_CATEGORIES=new Set(["tiny","small","medium","large"]);
const TERMINATION=["failed_concentration_save","controller_incapacitated","controller_death","duration_expires","voluntary_end"];
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
const MODELED=new Set<CanonicalControlTierKey>(CANONICAL_CONTROL_TIER_KEYS.filter(key=>EXCLUDED[key]===undefined));
const PROFILE={id:"official_default_25_percent_hp",selectable_advanced_training:"excluded",tactical_master:"included",legendary_resistance:"metadata_only",unsupported_disposition:"error"};
const POLICY={
  horizon_rounds:3,
  action_economy:{attack_rider_declaration:"before_attack_roll",standalone_action_limit_per_turn:1,action_surge_additional_standalone:false},
  resources:{psi_source:"psi_point_bands",blood_tax_source:"harness_overload",tier_two_limit_per_attack_action:1},
  concentration:{pressure:"endogenous_only",startup_blood_tax_check:"exempt",occupancy:"one_controller_slot",replacement:"new_effect_ends_existing",termination:TERMINATION}
};
const EXPECTED_MASTERIES=[
  {mastery_id:"mastery_slow",minimum_level:3,trigger:[{kind:"hit"}],component:{component_id:"mastery_slow_speed_reduction",target_selector_ids:["manifested_strike_target"],magnitude:{kind:"speed_reduction",reduction:{kind:"flat_feet",value:10},movement_modes:MOVEMENT_MODES},duration:{kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1},cadence:{apply:[{kind:"hit"}],repeat:[],end:[{kind:"turn",owner:"controller",turn_anchor:"start"}]},stacking:{key:"mastery_slow_speed_reduction",mode:"nonstacking",refresh:"duration",dominates_component_ids:[]}}},
  {mastery_id:"mastery_push",minimum_level:3,trigger:[{kind:"hit"}],component:{component_id:"mastery_push_forced_movement",target_selector_ids:["manifested_strike_large_or_smaller_target"],magnitude:{kind:"forced_movement",distance_feet:10,distance_mode:"up_to",movement_mode:"push",reference_point:"controller",axis:"any",direction:"away_from_reference",destination:{selection:"rule_determined",visibility:"not_required",occupancy:"unoccupied_required"},path:{line:"straight",blocked:"nearest_unoccupied_along_path"},resolution_order:"independent"},duration:{kind:"instantaneous"},cadence:{apply:[{kind:"hit"}],repeat:[],end:[{kind:"instantaneous_resolution"}]},stacking:{key:"mastery_push_forced_movement",mode:"independent",refresh:"none",dominates_component_ids:[]}}},
  {mastery_id:"mastery_sap",minimum_level:3,trigger:[{kind:"hit"}],component:{component_id:"mastery_sap_attack_disadvantage",target_selector_ids:["manifested_strike_target"],magnitude:{kind:"attack_disadvantage",scope:"next_attack",count:1},duration:{kind:"relative",owner:"controller",anchor:"start_turn",offset_turns:1},cadence:{apply:[{kind:"hit"}],repeat:[],end:[{kind:"turn",owner:"controller",turn_anchor:"start"}]},stacking:{key:"mastery_sap_attack_disadvantage",mode:"nonstacking",refresh:"duration",dominates_component_ids:[]}}}
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
const validEvent=(value:unknown):boolean=>{
  const event=object(value);
  if(!event)return false;
  if(["declaration","activation","hit","save","damage_context","concentration_end","instantaneous_resolution"].includes(event.kind))return hasExactKeys(event,["kind"]);
  if(event.kind==="turn")return hasExactKeys(event,["kind","owner","turn_anchor"])&&["controller","target"].includes(event.owner)&&["start","end","during"].includes(event.turn_anchor);
  if(event.kind==="entry")return hasExactKeys(event,["kind","owner","turn_anchor"])&&event.owner==="any_creature"&&event.turn_anchor==="during_turn";
  if(event.kind==="exit")return hasExactKeys(event,["kind","owner","turn_anchor"])&&event.owner==="target"&&event.turn_anchor==="during_turn";
  return false;
};
const validEvents=(value:unknown,nonempty=false):boolean=>Array.isArray(value)&&(!nonempty||value.length>0)&&value.every(validEvent)&&value.every((item,index)=>!value.slice(0,index).some(previous=>same(previous,item)));
const eventKind=(value:unknown):unknown=>object(value)?.kind;
const hasEvent=(value:unknown,event:unknown):boolean=>array(value).some(candidate=>same(candidate,event));
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
    case "forced_movement":{
      const destination=object(magnitude.destination),movementPath=object(magnitude.path);
      valid=hasExactKeys(magnitude,["kind","distance_feet","distance_mode","movement_mode","reference_point","axis","direction","destination","path","resolution_order"])
        &&positiveInteger(magnitude.distance_feet)&&["exact","up_to"].includes(magnitude.distance_mode)
        &&["push","pull","reposition","lift"].includes(magnitude.movement_mode)
        &&["controller","primary_target","selected_point","target_current_position"].includes(magnitude.reference_point)
        &&["horizontal","vertical","any"].includes(magnitude.axis)
        &&["away_from_reference","toward_reference","controller_choice","vertical_up"].includes(magnitude.direction)
        &&hasExactKeys(destination,["selection","visibility","occupancy"])
        &&["controller_choice","rule_determined"].includes(destination?.selection)
        &&["required","not_required"].includes(destination?.visibility)
        &&["unoccupied_required","not_specified"].includes(destination?.occupancy)
        &&hasExactKeys(movementPath,["line","blocked"])&&["straight","not_required"].includes(movementPath?.line)
        &&["nearest_unoccupied_along_path","movement_not_permitted","not_specified"].includes(movementPath?.blocked)
        &&["controller_selected","independent"].includes(magnitude.resolution_order)
        &&(magnitude.direction!=="vertical_up"||(magnitude.axis==="vertical"&&magnitude.movement_mode==="lift"))
        &&(!["nearest_unoccupied_along_path","movement_not_permitted"].includes(movementPath?.blocked)||movementPath?.line==="straight");
      break;
    }
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
    case "difficult_terrain":
      valid=hasExactKeys(magnitude,["kind","scope","movement_cost_multiplier"])&&magnitude.scope==="area"&&magnitude.movement_cost_multiplier===2;
      break;
    case "persistent_elevation":
      valid=hasExactKeys(magnitude,["kind","state","position_reference"])&&magnitude.state==="hovering"&&magnitude.position_reference==="current_position";
      break;
    case "fall":
      valid=hasExactKeys(magnitude,["kind","origin"])&&magnitude.origin==="current_position";
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
  if(count.kind==="up_to_proficiency_bonus"||count.kind==="all_eligible")return hasExactKeys(count,["kind"]);
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

function validateChoices(value:unknown,diagnostics:Diagnostic[],path:string):Map<string,ObjectValue>{
  const choices=array(value),byId=new Map<string,ObjectValue>();
  if(!Array.isArray(value)){add(diagnostics,"control_v2.choice","Modeled effects require an explicit choices array",path);return byId;}
  for(const [index,choiceValue] of choices.entries()){
    const choice=object(choiceValue),choicePath=`${path}/${index}`,options=array(choice?.options);
    let valid=hasExactKeys(choice,["choice_id","kind","timing","resolution","scope","options"])&&validId(choice?.choice_id)
      &&!byId.has(choice!.choice_id)&&["mode","placement"].includes(choice?.kind)&&validEvent(choice?.timing)
      &&choice?.resolution==="once_per_effect"&&["all_targets","area_origin"].includes(choice?.scope)
      &&validIdArray(choice?.options,true)&&options.length>=2;
    if(choice?.kind==="mode")valid=valid&&choice.scope==="all_targets"&&same(choice.timing,{kind:"declaration"});
    if(choice?.kind==="placement")valid=valid&&choice.scope==="area_origin"&&same(choice.timing,{kind:"activation"});
    if(!valid)add(diagnostics,"control_v2.choice","Choices must be stable, one-time, typed, and coupled to the declared target or placement scope",choicePath);
    if(validId(choice?.choice_id)&&!byId.has(choice!.choice_id))byId.set(choice!.choice_id,choice!);
  }
  return byId;
}

function validateArea(value:unknown,choices:Map<string,ObjectValue>,usedChoiceIds:Set<string>,diagnostics:Diagnostic[],path:string):string|undefined{
  const area=object(value);if(!area)return undefined;
  const allowedKeys=["area_id","shape","placement","radius_feet","height_feet","length_feet","width_feet","persistent","triggers","exit_behavior","entry_policy","movement"];
  const placement=object(area.placement),placementRange=object(placement?.range);
  let valid=hasOnlyKeys(area,allowedKeys)&&validId(area.area_id)&&["sphere","cylinder","cone","line"].includes(area.shape)
    &&typeof area.persistent==="boolean"&&validEvents(area.triggers,true)&&["ends_area_effects","none"].includes(area.exit_behavior)&&Boolean(placement);
  if(placement?.kind==="controller"||placement?.kind==="primary_target")valid=valid&&hasExactKeys(placement,["kind"]);
  else if(placement?.kind==="selected_point")valid=valid&&hasExactKeys(placement,["kind","range","stationary"])
    &&hasExactKeys(placementRange,["feet","origin"])&&nonnegativeInteger(placementRange?.feet)&&placementRange?.origin==="controller"&&typeof placement.stationary==="boolean";
  else if(placement?.kind==="endpoint_choice"){
    const choice=choices.get(String(placement.choice_id)),departure=object(placement.departure),arrival=object(placement.arrival),arrivalRange=object(arrival?.range);
    valid=valid&&hasExactKeys(placement,["kind","choice_id","departure","arrival"])&&validId(placement.choice_id)
      &&choice?.kind==="placement"&&same([...array(choice?.options)].sort(),["arrival_space","departure_space"])
      &&hasExactKeys(departure,["origin"])&&departure?.origin==="controller_current_space"
      &&hasExactKeys(arrival,["range","visibility","occupancy"])&&hasExactKeys(arrivalRange,["feet","origin"])
      &&positiveInteger(arrivalRange?.feet)&&arrivalRange?.origin==="departure_space"&&arrival?.visibility==="required"&&arrival?.occupancy==="unoccupied_required";
    if(validId(placement.choice_id))usedChoiceIds.add(placement.choice_id);
  }else valid=false;
  if(area.shape==="sphere")valid=valid&&positiveInteger(area.radius_feet)&&area.height_feet===undefined&&area.length_feet===undefined&&area.width_feet===undefined;
  else if(area.shape==="cylinder")valid=valid&&positiveInteger(area.radius_feet)&&positiveInteger(area.height_feet)&&area.length_feet===undefined&&area.width_feet===undefined;
  else if(area.shape==="cone")valid=valid&&positiveInteger(area.length_feet)&&area.radius_feet===undefined&&area.height_feet===undefined&&area.width_feet===undefined;
  else if(area.shape==="line")valid=valid&&positiveInteger(area.length_feet)&&positiveInteger(area.width_feet)&&area.radius_feet===undefined&&area.height_feet===undefined;
  if(area.persistent){
    const entryPolicy=object(area.entry_policy),movement=object(area.movement);
    const validEntry=hasExactKeys(entryPolicy,["frequency","moved_area_counts_as_entry"])&&entryPolicy?.frequency==="once_per_turn"&&typeof entryPolicy?.moved_area_counts_as_entry==="boolean";
    const validMovement=movement?.kind==="stationary"
      ?hasExactKeys(movement,["kind"])
      :movement?.kind==="controller_reposition"&&hasExactKeys(movement,["kind","controller_action","timing","distance_feet","distance_mode"])
        &&movement.controller_action==="bonus_action"&&same(movement.timing,{kind:"turn",owner:"controller",turn_anchor:"during"})
        &&positiveInteger(movement.distance_feet)&&movement.distance_mode==="up_to";
    valid=valid&&validEntry&&validMovement
      &&hasEvent(area.triggers,{kind:"entry",owner:"any_creature",turn_anchor:"during_turn"})
      &&hasEvent(area.triggers,{kind:"turn",owner:"target",turn_anchor:"start"});
    if(placement?.kind==="selected_point")valid=valid&&placement.stationary===(movement?.kind==="stationary");
  }else valid=valid&&area.entry_policy===undefined&&area.movement===undefined;
  if(placement?.kind==="endpoint_choice")valid=valid&&area.persistent===false;
  if(!valid)add(diagnostics,"control_v2.area","Control area must define typed persistence, placement, entry, movement, dimensions, triggers, and exit behavior",path);
  return validId(area.area_id)?area.area_id:undefined;
}

function validateSelector(value:unknown,choices:Map<string,ObjectValue>,usedChoiceIds:Set<string>,diagnostics:Diagnostic[],path:string):string|undefined{
  const selector=object(value);if(!selector){add(diagnostics,"control_v2.target","Control target selector is missing",path);return undefined;}
  const range=object(selector.range),restrictions=array(selector.restrictions),selectorKeys=selector.area===undefined
    ?["selector_id","role","selection","count","range","restrictions","gate_scope"]
    :["selector_id","role","selection","count","range","restrictions","gate_scope","area"];
  const restrictionKinds=restrictions.map(item=>object(item)?.kind);
  const rangeValid=range?.kind==="area"?hasExactKeys(range,["kind"])&&selector.area!==undefined
    :range?.kind==="distance"&&hasExactKeys(range,["kind","feet","origin"])&&nonnegativeInteger(range.feet)&&["controller","primary_target"].includes(range.origin)&&selector.area===undefined;
  const valid=hasExactKeys(selector,selectorKeys)&&validId(selector.selector_id)&&["primary","secondary","all"].includes(selector.role)
    &&["controller_choice","all_in_area","automatic"].includes(selector.selection)&&validateCount(selector.count)&&rangeValid
    &&(range?.kind!=="area"||object(selector.count)?.kind==="all_eligible")
    &&(selector.selection!=="all_in_area"||selector.area!==undefined)
    &&Array.isArray(selector.restrictions)&&restrictions.every(validateRestriction)&&new Set(restrictionKinds).size===restrictionKinds.length
    &&(selector.role!=="secondary"||restrictionKinds.includes("excludes_primary_target"))
    &&["independent_per_target","shared"].includes(selector.gate_scope);
  if(!valid)add(diagnostics,"control_v2.target","Control target selector must define typed role, choice semantics, eligibility, restrictions, and gate scope",path);
  if(selector.area!==undefined)validateArea(selector.area,choices,usedChoiceIds,diagnostics,path+"/area");
  return validId(selector.selector_id)?selector.selector_id:undefined;
}

function validateComponent(value:unknown,diagnostics:Diagnostic[],path:string,selectorIds:Set<string>|undefined,areaIds:Set<string>,componentIds:Set<string>,concentration:ConcentrationState,choices?:Map<string,ObjectValue>,usedChoiceIds?:Set<string>):void{
  const component=object(value);if(!component){add(diagnostics,"control_v2.ids","Control component is missing",path);return;}
  const componentKeys=component.choice_requirement===undefined
    ?["component_id","target_selector_ids","magnitude","duration","cadence","stacking"]
    :["component_id","target_selector_ids","magnitude","duration","cadence","stacking","choice_requirement"];
  if(!hasExactKeys(component,componentKeys)||!validId(component.component_id))add(diagnostics,"control_v2.ids","Control component requires an exact shape and stable component_id",path+"/component_id");
  const targetIds=array(component.target_selector_ids);
  if(!validIdArray(component.target_selector_ids,true)||(selectorIds&&targetIds.some(id=>!selectorIds.has(id))))add(diagnostics,"control_v2.target","Control component must reference defined target selectors",path+"/target_selector_ids");
  validateMagnitude(component.magnitude,diagnostics,path+"/magnitude");
  validateDuration(component.duration,diagnostics,path+"/duration",areaIds,concentration);
  validateCadence(component.cadence,diagnostics,path+"/cadence");
  if(component.choice_requirement!==undefined){
    const requirement=object(component.choice_requirement),choice=choices?.get(String(requirement?.choice_id));
    const valid=hasExactKeys(requirement,["choice_id","option_id"])&&validId(requirement?.choice_id)&&validId(requirement?.option_id)
      &&choice?.kind==="mode"&&array(choice?.options).includes(requirement?.option_id);
    if(!valid)add(diagnostics,"control_v2.choice","Component choice requirements must reference one declared mode option",path+"/choice_requirement");
    if(validId(requirement?.choice_id))usedChoiceIds?.add(requirement!.choice_id);
  }
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

function validateResolution(value:unknown,diagnostics:Diagnostic[],path:string,selectorIds:Set<string>,selectorScopes:Map<string,unknown>,areaSelectorIds:Set<string>,componentIds:Set<string>,componentsById:Map<string,ObjectValue>,gateIds:Set<string>,branchIds:Set<string>,referencedComponents:Set<string>):void{
  const gate=object(value);if(!gate){add(diagnostics,"control_v2.branch","Control resolution is missing",path);return;}
  const gateKeys=gate.requires_active_component_ids===undefined?["gate_id","selector_ids","trigger","gate_scope","resolution"]:["gate_id","selector_ids","requires_active_component_ids","trigger","gate_scope","resolution"];
  if(!hasExactKeys(gate,gateKeys)||!validId(gate.gate_id)||gateIds.has(gate.gate_id))add(diagnostics,"control_v2.ids","Resolution gates require exact shapes and stable unique IDs",path+"/gate_id");else gateIds.add(gate.gate_id);
  if(gate.requires_active_component_ids!==undefined&&(!validIdArray(gate.requires_active_component_ids,true)||array(gate.requires_active_component_ids).some(id=>!componentIds.has(id))))add(diagnostics,"control_v2.graph","Active-state guards must reference known local components",path+"/requires_active_component_ids");
  const selected=array(gate.selector_ids);
  if(!validEvent(gate.trigger))add(diagnostics,"control_v2.timing","Resolution gates require an explicit supported trigger with event context",path+"/trigger");
  const resolution=object(gate.resolution),branches=array(resolution?.branches),kind=resolution?.kind;
  const areaActivationBranch=branches.length===1?object(branches[0]):undefined,areaActivationApplies=array(areaActivationBranch?.applies);
  const areaActivationOnly=(areaActivationApplies.length===0&&["replaces","terminates","refreshes"].every(field=>array(areaActivationBranch?.[field]).length===0))
    ||(areaActivationApplies.length>0&&["replaces","terminates","refreshes"].every(field=>array(areaActivationBranch?.[field]).length===0)&&areaActivationApplies.every(id=>object(componentsById.get(id)?.magnitude)?.scope==="area"));
  const sharedAreaActivation=gate.gate_scope==="shared"&&same(gate.trigger,{kind:"activation"})&&kind==="no_save"
    &&selected.length>0&&selected.every(id=>areaSelectorIds.has(id)&&selectorScopes.get(id)==="independent_per_target")
    &&Boolean(areaActivationBranch)&&areaActivationOnly;
  if(!validIdArray(gate.selector_ids,true)||selected.some(id=>!selectorIds.has(id))||(!selected.every(id=>selectorScopes.get(id)===gate.gate_scope)&&!sharedAreaActivation)||!["independent_per_target","shared"].includes(gate.gate_scope))add(diagnostics,"control_v2.target","Resolution gates must reference defined selectors with matching scope or a shared area-activation ordering gate",path);
  const resolutionKeys=kind==="saving_throw"?["kind","ability","role","mode","branches"]:["kind","branches"];
  let complete=hasExactKeys(resolution,resolutionKeys)&&["attack_roll","saving_throw","no_save","damage_context","other"].includes(kind)&&branches.length>0,cadenceComplete=true,graphComplete=true;
  const outcomes=branches.map(branch=>object(branch)?.outcome),expectedOutcomes=kind==="attack_roll"?["attack_hit","attack_miss"]:kind==="saving_throw"?["save_success","save_failure"]:kind==="no_save"?["no_save"]:kind==="damage_context"?["damage_context"]:kind==="other"?["other"]:[];
  complete=complete&&same([...outcomes].sort(),[...expectedOutcomes].sort());
  if(kind==="saving_throw"){
    complete=complete&&SAVE_ABILITIES.has(resolution?.ability)&&["initial","repeat","recurring"].includes(resolution?.role)&&["normal","advantage","disadvantage"].includes(resolution?.mode);
    const targetStart=same(gate.trigger,{kind:"turn",owner:"target",turn_anchor:"start"}),entry=eventKind(gate.trigger)==="entry";
    if(resolution?.role==="repeat")complete=complete&&targetStart;
    else if(resolution?.role==="recurring")complete=complete&&(targetStart||entry);
    else complete=complete&&!targetStart&&!entry;
  }
  else complete=complete&&resolution?.ability===undefined;
  for(const [branchIndex,branchValue] of branches.entries()){
    const branch=object(branchValue),branchPath=path+"/resolution/branches/"+String(branchIndex);
    if(!branch){add(diagnostics,"control_v2.branch","Resolution branch is missing",branchPath);complete=false;continue;}
    if(!hasExactKeys(branch,["branch_id","outcome","applies","replaces","terminates","refreshes","next_gate_ids"])||!validId(branch.branch_id)||branchIds.has(branch.branch_id))add(diagnostics,"control_v2.ids","Branch IDs must be stable and unique within a model",branchPath+"/branch_id");else branchIds.add(branch.branch_id);
    if(!["attack_hit","attack_miss","save_success","save_failure","no_save","damage_context","other"].includes(branch.outcome))complete=false;
    const transitions=new Map<string,any[]>();
    for(const field of ["applies","replaces","terminates","refreshes"]){
      const refs=array(branch[field]);
      transitions.set(field,refs);refs.forEach(id=>referencedComponents.add(id));
      if(!validIdArray(branch[field])||refs.some(id=>!componentIds.has(id)))complete=false;
      const cadenceField=field==="applies"?"apply":field==="refreshes"?"repeat":"end";
      for(const id of refs){
        const component=componentsById.get(id),cadence=object(component?.cadence),postHitInitialSave=(field==="refreshes"||field==="replaces")
          &&same(gate.trigger,{kind:"save"})&&kind==="saving_throw"&&resolution?.role==="initial"&&hasEvent(cadence?.apply,{kind:"hit"});
        if(component&&!hasEvent(cadence?.[cadenceField],gate.trigger)&&!postHitInitialSave)cadenceComplete=false;
      }
    }
    const transitionSets=[...transitions.values()].map(refs=>new Set(refs));
    for(let left=0;left<transitionSets.length;left++)for(let right=left+1;right<transitionSets.length;right++)if([...transitionSets[left]!].some(id=>transitionSets[right]!.has(id)))complete=false;
    if(!validIdArray(branch.next_gate_ids))graphComplete=false;
    if(branch.outcome==="attack_miss"&&([...transitions.values()].some(refs=>refs.length>0)||array(branch.next_gate_ids).length>0))complete=false;
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
    if(roots.some(root=>object(gateById.get(root)?.resolution)?.kind!=="attack_roll"||eventKind(gateById.get(root)?.trigger)!=="hit"))valid=false;
    const hitReach=new Set<string>();
    for(const branch of branchRecords){
      const descendants=walk(branch.next);
      if(branch.outcome==="attack_hit")for(const id of descendants)hitReach.add(id);
      if(branch.outcome==="attack_miss"&&[...descendants].some(id=>object(gateById.get(id)?.resolution)?.kind==="saving_throw"))valid=false;
    }
    for(const [id,gate] of gateById)if(eventKind(gate.trigger)==="save"&&object(gate.resolution)?.kind==="saving_throw"&&!roots.includes(id)&&!hitReach.has(id))valid=false;
  }
  if(!valid)add(diagnostics,"control_v2.graph","Resolution graph roots and branch transitions must be known, reachable, acyclic, order-neutral, and hit-gated",path);
}

function canonicalConcentrationDuration(entity:ObjectValue|undefined):{value:number;unit:string}|undefined{
  if(typeof entity?.concentration_duration!=="string")return undefined;
  const match=/^Up to ([1-9][0-9]*) (round|minute|hour)s?$/.exec(entity.concentration_duration);
  return match?{value:Number(match[1]),unit:match[2]!}:undefined;
}

function validateConcentration(value:unknown,entity:ObjectValue|undefined,diagnostics:Diagnostic[],path:string):ConcentrationState{
  const concentration=object(value);
  const requiredExpected=entity?.requires_concentration===true,expectedDuration=canonicalConcentrationDuration(entity);
  if(concentration?.kind==="none"){
    if(!hasExactKeys(concentration,["kind"])||requiredExpected)add(diagnostics,"control_v2.concentration","Canonical concentration features require a complete concentration model",path);
    return {required:false};
  }
  if(concentration?.kind!=="required"){
    add(diagnostics,"control_v2.concentration","Control concentration must be explicitly none or required",path);return {required:false};
  }
  const maximum=object(concentration.maximum_duration),termination=array(concentration.termination);
  const valid=hasExactKeys(concentration,["kind","startup","occupancy","replacement","maximum_duration","termination"])&&hasExactKeys(maximum,["value","unit"])
    &&concentration.startup===(entity?.activation==="on_hit"?"on_hit":"on_activation")&&concentration.occupancy==="one_controller_slot"&&concentration.replacement==="new_effect_ends_existing"
    &&positiveInteger(maximum?.value)&&["round","minute","hour"].includes(maximum?.unit)&&uniqueStrings(concentration.termination,true)
    &&same([...termination].sort(),[...TERMINATION].sort())&&requiredExpected&&Boolean(expectedDuration)
    &&maximum?.value===expectedDuration?.value&&maximum?.unit===expectedDuration?.unit;
  if(!valid)add(diagnostics,"control_v2.concentration","Required concentration must match canonical activation, duration, occupancy, replacement, and every termination event",path);
  return {required:true,maximumValue:maximum?.value,unit:maximum?.unit};
}

function validatePolicy(value:unknown,row:ObjectValue,authority:Authority,diagnostics:Diagnostic[],path:string):void{
  const policy=object(value),entity=authority.entities.find(candidate=>candidate.id===row.entity_id) as ObjectValue|undefined;
  const calculatorFeature=authority.calculator.features.find(candidate=>candidate.entity_id===row.entity_id);
  const featureRule=authority.calculator.harness_mechanics.feature_rules.find(candidate=>candidate.entity_id===row.entity_id);
  const featureRole=object(entity?.classifications)?.feature_role,expectedDelivery=featureRole==="rider"?"attack_rider":featureRole==="standalone"?"standalone":undefined;
  const calculatorDelivery=calculatorFeature?.delivery==="on_hit_rider"?"attack_rider":calculatorFeature?.delivery==="standalone"?"standalone":undefined;
  const expectedRepeatability=expectedDelivery==="standalone"?"once_per_turn":featureRule?.repeatability;
  const expectedMastery=expectedDelivery==="standalone"?"not_applicable":row.entity_id==="telekinetic_shove"?"replaces_on_declaration":"stacks";
  const valid=hasExactKeys(policy,["activation","declaration","delivery","psi_cost","overload_tier","blood_tax","repeatability","mastery"])&&Boolean(entity)&&Boolean(expectedDelivery)
    &&policy?.activation===entity?.activation&&same(policy?.declaration,{kind:"declaration"})&&policy?.delivery===expectedDelivery
    &&(calculatorDelivery===undefined||calculatorDelivery===expectedDelivery)
    &&nonnegativeInteger(entity?.psi_cost)&&policy?.psi_cost===entity?.psi_cost&&policy?.overload_tier===row.tier
    &&policy?.blood_tax===(row.tier===0?"none":"tier_formula")&&policy?.repeatability===expectedRepeatability&&policy?.mastery===expectedMastery;
  if(!valid)add(diagnostics,"control_v2.timing","Control policy must derive activation, delivery, costs, repeatability, and concentration-independent mastery scope from canonical metadata",path);
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
  if(!hasExactKeys(model,["effect_id","inheritance","policy","choices","target_selectors","components","root_gate_ids","resolutions","concentration","relationships"]))add(diagnostics,"control_v2.coverage","Modeled ledger rows require the exact v2.1 model shape",path);
  if(!validId(model.effect_id)||effectIds.has(model.effect_id))add(diagnostics,"control_v2.ids","Modeled effects require globally unique stable effect IDs",path+"/effect_id");else effectIds.add(model.effect_id);
  const entity=authority.entities.find(candidate=>candidate.id===row.entity_id) as ObjectValue|undefined;
  validatePolicy(model.policy,row,authority,diagnostics,path+"/policy");
  const concentration=validateConcentration(model.concentration,entity,diagnostics,path+"/concentration");
  const choices=validateChoices(model.choices,diagnostics,path+"/choices"),usedChoiceIds=new Set<string>();
  const selectorValues=array(model.target_selectors),selectorIds=new Set<string>(),selectorScopes=new Map<string,unknown>(),areaIds=new Set<string>(),areaSelectorIds=new Set<string>();
  if(!selectorValues.length)add(diagnostics,"control_v2.target","Modeled effects require at least one target selector",path+"/target_selectors");
  for(const [index,selectorValue] of selectorValues.entries()){
    const selectorPath=path+"/target_selectors/"+String(index),id=validateSelector(selectorValue,choices,usedChoiceIds,diagnostics,selectorPath),selector=object(selectorValue),area=object(selector?.area);
    if(id){if(selectorIds.has(id))add(diagnostics,"control_v2.ids","Selector IDs must be unique within a model",selectorPath+"/selector_id");selectorIds.add(id);selectorScopes.set(id,selector?.gate_scope);if(area)areaSelectorIds.add(id);}
    if(validId(area?.area_id)){if(areaIds.has(area.area_id))add(diagnostics,"control_v2.ids","Area IDs must be unique within a model",selectorPath+"/area/area_id");areaIds.add(area.area_id);}
  }
  const componentValues=array(model.components),componentIds=new Set<string>(),componentsById=new Map<string,ObjectValue>();
  if(!componentValues.length)add(diagnostics,"control_v2.ids","Modeled effects require at least one component",path+"/components");
  for(const [index,componentValue] of componentValues.entries()){
    const component=object(componentValue),id=component?.component_id;
    if(validId(id)){if(componentIds.has(id))add(diagnostics,"control_v2.ids","Component IDs must be unique within a model",path+"/components/"+String(index)+"/component_id");componentIds.add(id);if(component)componentsById.set(id,component);}
  }
  for(const [index,componentValue] of componentValues.entries()){
    validateComponent(componentValue,diagnostics,path+"/components/"+String(index),selectorIds,areaIds,componentIds,concentration,choices,usedChoiceIds);
    const component=object(componentValue);
    if(object(component?.magnitude)?.kind==="difficult_terrain"&&!array(component?.target_selector_ids).some(id=>areaSelectorIds.has(id)))add(diagnostics,"control_v2.area","Difficult terrain must be an area-wide property of an area-owning selector",path+"/components/"+String(index)+"/magnitude");
  }
  for(const [choiceId,choice] of choices){
    if(choice.kind==="mode"){
      const boundOptions=componentValues.map(object).filter(component=>object(component?.choice_requirement)?.choice_id===choiceId).map(component=>object(component?.choice_requirement)?.option_id);
      if(!same([...boundOptions].sort(),[...array(choice.options)].sort()))add(diagnostics,"control_v2.choice","Every declared mode option must govern exactly one conditional component",path+"/choices");
    }
    if(!usedChoiceIds.has(choiceId))add(diagnostics,"control_v2.choice","Every declared choice must govern a component or area placement",path+"/choices");
  }
  const resolutionValues=array(model.resolutions),gateIds=new Set<string>(),branchIds=new Set<string>(),referencedComponents=new Set<string>();
  if(!resolutionValues.length)add(diagnostics,"control_v2.branch","Modeled effects require at least one explicit resolution",path+"/resolutions");
  for(const [index,resolutionValue] of resolutionValues.entries())validateResolution(resolutionValue,diagnostics,path+"/resolutions/"+String(index),selectorIds,selectorScopes,areaSelectorIds,componentIds,componentsById,gateIds,branchIds,referencedComponents);
  validateResolutionGraph(model.root_gate_ids,resolutionValues,model.policy?.delivery==="attack_rider",diagnostics,path+"/root_gate_ids");
  if([...componentIds].some(id=>!referencedComponents.has(id)))add(diagnostics,"control_v2.branch","Every model component must appear in at least one branch transition",path+"/resolutions");
  for(const selectorValue of selectorValues){
    const selector=object(selectorValue),area=object(selector?.area);if(!area?.persistent)continue;
    const resolutions=resolutionValues.map(object);
    for(const trigger of [{kind:"entry",owner:"any_creature",turn_anchor:"during_turn"},{kind:"turn",owner:"target",turn_anchor:"start"}])if(!resolutions.some(gate=>same(gate?.trigger,trigger)&&array(gate?.selector_ids).includes(selector?.selector_id)))add(diagnostics,"control_v2.area","Persistent entry/start-turn areas require matching selector resolution gates",path+"/resolutions");
    const selectorComponents=componentValues.map(object).filter(component=>array(component?.target_selector_ids).includes(selector?.selector_id));
    const insideComponents=selectorComponents.filter(component=>object(component?.duration)?.kind==="while_in_area"&&object(component?.duration)?.area_id===area.area_id);
    if(!selectorComponents.length||insideComponents.some(component=>!hasEvent(object(component?.cadence)?.end,{kind:"exit",owner:"target",turn_anchor:"during_turn"})))add(diagnostics,"control_v2.area","Persistent area components must reference their selector and inside-only effects must end on target exit",path+"/components");
  }
  const elevationIds=componentValues.map(object).filter(component=>object(component?.magnitude)?.kind==="persistent_elevation").map(component=>component!.component_id);
  const fallIds=componentValues.map(object).filter(component=>object(component?.magnitude)?.kind==="fall").map(component=>component!.component_id);
  if(elevationIds.length){
    const gates=resolutionValues.map(object),concentrationEndBranches=gates.filter(gate=>eventKind(gate?.trigger)==="concentration_end").flatMap(gate=>array(object(gate?.resolution)?.branches));
    const repeatSuccessBranches=gates.filter(gate=>object(gate?.resolution)?.kind==="saving_throw"&&object(gate?.resolution)?.role==="repeat").flatMap(gate=>array(object(gate?.resolution)?.branches)).map(object).filter(branch=>branch?.outcome==="save_success");
    const transitionComplete=(branchValue:unknown):boolean=>{const branch=object(branchValue);return fallIds.some(id=>array(branch?.applies).includes(id))&&elevationIds.every(id=>array(branch?.terminates).includes(id));};
    if(!concentration.required||!fallIds.length||!concentrationEndBranches.some(transitionComplete)||!repeatSuccessBranches.some(transitionComplete))add(diagnostics,"control_v2.timing","Persistent elevation requires current-position fall transitions on repeat-save success and concentration end",path+"/resolutions");
    const rootIds=new Set(array(model.root_gate_ids)),gateById=new Map(gates.filter(Boolean).map(gate=>[String(gate!.gate_id),gate!])),edges=new Map<string,string[]>();
    for(const gate of gates.filter(Boolean))edges.set(String(gate!.gate_id),array(object(gate!.resolution)?.branches).flatMap(branch=>array(object(branch)?.next_gate_ids)));
    const walk=(starts:string[]):Set<string>=>{const seen=new Set<string>(),pending=[...starts];while(pending.length){const id=pending.pop()!;if(seen.has(id))continue;seen.add(id);pending.push(...(edges.get(id)??[]));}return seen;};
    const initialGates=gates.filter(gate=>object(gate?.resolution)?.kind==="saving_throw"&&object(gate?.resolution)?.role==="initial"),failureStarts=initialGates.flatMap(gate=>array(object(gate?.resolution)?.branches).map(object).filter(branch=>branch?.outcome==="save_failure").flatMap(branch=>array(branch?.next_gate_ids))),successStarts=initialGates.flatMap(gate=>array(object(gate?.resolution)?.branches).map(object).filter(branch=>branch?.outcome==="save_success").flatMap(branch=>array(branch?.next_gate_ids)));
    const failureReach=walk(failureStarts),successReach=walk(successStarts),repositionIds=new Set(componentValues.map(object).filter(component=>object(component?.magnitude)?.kind==="forced_movement"&&object(component?.magnitude)?.movement_mode==="reposition").map(component=>String(component!.component_id)));
    const contingentGateIds=gates.filter(gate=>eventKind(gate?.trigger)==="concentration_end"||(object(gate?.resolution)?.kind==="saving_throw"&&object(gate?.resolution)?.role==="repeat")||array(object(gate?.resolution)?.branches).some(branch=>["applies","replaces","terminates","refreshes"].some(field=>array(object(branch)?.[field]).some(id=>repositionIds.has(id))))).map(gate=>String(gate!.gate_id));
    const elevationGuard=[...elevationIds].sort();
    if(!initialGates.length||contingentGateIds.some(id=>rootIds.has(id)||!gateById.has(id)||!failureReach.has(id)||successReach.has(id)||!same([...array(gateById.get(id)?.requires_active_component_ids)].sort(),elevationGuard)))add(diagnostics,"control_v2.graph","Persistent-elevation repeat, reposition, and concentration-end gates must be guarded nonroot continuations of initial-save failure only",path+"/root_gate_ids");
  }
  validateRelationships(model.relationships,componentValues,componentIds,diagnostics,path+"/relationships");
  const inheritance=object(model.inheritance);
  if(inheritance?.kind==="none"){
    if(!hasExactKeys(inheritance,["kind"])||row.tier!==0)add(diagnostics,"control_v2.inheritance","Only base modeled tiers may declare no inheritance",path+"/inheritance");
  }else if(inheritance?.kind==="resolved"){
    const sourceTier=inheritance.source_tier,sourceKey=String(row.entity_id)+":T"+String(sourceTier);
    const calculatorFeature=authority.calculator.features.find(feature=>feature.entity_id===row.entity_id),canonicalEntity=authority.entities.find(entity=>entity.id===row.entity_id);
    const sourceKnown=ledgerByKey.has(sourceKey)||Boolean(calculatorFeature?.tiers.some(tier=>tier.tier===sourceTier))||Boolean(canonicalEntity);
    if(!hasExactKeys(inheritance,["kind","source_tier"])||!Number.isInteger(sourceTier)||sourceTier!==row.tier-1||!sourceKnown)add(diagnostics,"control_v2.inheritance","Resolved inheritance must reference the immediately preceding canonical tier",path+"/inheritance");
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
  if(root.contract_version!=="2.1.0")add(diagnostics,"control_v2.version","Unsupported control-authority contract version",`${path}/contract_version`);
  if(!same(root.active_profile,PROFILE))add(diagnostics,"control_v2.disposition","The active control profile must preserve all maintainer rulings",`${path}/active_profile`);
  if(!same(root.target_data_requirements,["walking_speed","movement_modes","hover","nonvisual_senses"]))add(diagnostics,"control_v2.target","Control target-data requirements must remain complete and canonical",`${path}/target_data_requirements`);
  if(!same(root.policy_inputs,POLICY))add(diagnostics,"control_v2.timing","Control policy inputs must preserve the three-round horizon, action economy, resources, and concentration rules",`${path}/policy_inputs`);
  validateMasteries(root.masteries,diagnostics,`${path}/masteries`);
  const tactical=object(root.tactical_master);
  if(!tactical||tactical.minimum_level!==9||!same(tactical.choice_mastery_ids,["mastery_push","mastery_sap","mastery_slow"])||!same(tactical.choice_timing,{kind:"declaration"})||tactical.behavior!=="replaces_kinetic_mastery")add(diagnostics,"control_v2.timing","Tactical Master must become available at level 9 and replace Kinetic Mastery on declaration",`${path}/tactical_master`);
  const ledger=array(root.ledger),keys=ledger.map(row=>tierKey(object(row)??{})),ledgerByKey=new Map<string,ObjectValue>();
  for(const rowValue of ledger){const row=object(rowValue);if(row)ledgerByKey.set(tierKey(row),row);}
  if(!same(keys,CANONICAL_CONTROL_TIER_KEYS)||new Set(keys).size!==keys.length)add(diagnostics,"control_v2.coverage",`The control ledger must contain the exact sorted canonical ${CANONICAL_CONTROL_TIER_KEYS.length}-tier universe`,`${path}/ledger`);
  const counts={modeled:0,excluded_by_profile:0,unsupported_error:0};
  for(const rowValue of ledger){const row=object(rowValue);if(row&&row.disposition in counts)counts[row.disposition as keyof typeof counts]++;}
  if(counts.modeled!==MODELED.size||counts.excluded_by_profile!==Object.keys(EXCLUDED).length||counts.unsupported_error!==0)add(diagnostics,"control_v2.coverage",`The complete ledger must contain ${MODELED.size} modeled tiers, the exact ${Object.keys(EXCLUDED).length} maintained profile exclusions, and no unsupported rows across ${CANONICAL_CONTROL_TIER_KEYS.length} canonical tiers`,`${path}/ledger`);
  const effectIds=new Set<string>();
  for(const [index,rowValue] of ledger.entries()){
    const row=object(rowValue),rowPath=`${path}/ledger/${index}`;if(!row){add(diagnostics,"control_v2.coverage","Ledger row is malformed",rowPath);continue;}
    const key=tierKey(row) as CanonicalControlTierKey,excludedReason=EXCLUDED[key];
    if(MODELED.has(key)){
      if(row.disposition!=="modeled")add(diagnostics,"control_v2.disposition",`${key} must remain modeled`,rowPath);
      else validateModel(row.model,row,authority,ledgerByKey,effectIds,diagnostics,`${rowPath}/model`);
    }else if(excludedReason){
      if(row.disposition!=="excluded_by_profile"||row.profile_id!==PROFILE.id||row.reason!==excludedReason||row.model!==undefined)add(diagnostics,"control_v2.disposition",`${key} must retain its maintained profile exclusion`,rowPath);
    }else if((CANONICAL_CONTROL_TIER_KEYS as readonly string[]).includes(key))add(diagnostics,"control_v2.disposition",`${key} has no maintained disposition`,rowPath);
  }
  return diagnostics;
}

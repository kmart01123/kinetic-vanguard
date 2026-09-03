import type {CalculatorDamage,CalculatorFeature,CalculatorMetric,CalculatorSave,Entity,HarnessControlEffect,HarnessControlTier,HarnessFeatureRule,MechanicsStep,MechanicsSurface,MechanicsTargeting,MechanicsTier,MechanicsValue} from "./types.js";

const disciplineIds=["pyrokinesis","cryokinesis","psychokinesis","electrokinesis"] as const;
type Gate="on_reach"|"on_failed_save"|"while_in_area";
type SavingStep=Extract<MechanicsStep,{kind:"saving_throw"}>;
interface LocatedStep {step:MechanicsStep;gate:Gate;save?:CalculatorSave;halfOnSuccess?:boolean;saving?:SavingStep}
const uniqueValues=<T>(values:T[]):T[]=>[...new Map(values.map(value=>[JSON.stringify(value),value])).values()];

const calculatorDelivery=(surfaces:MechanicsSurface[]):CalculatorFeature["delivery"]=>surfaces.some(surface=>surface.delivery.kind==="rider")?"on_hit_rider":surfaces.some(surface=>surface.delivery.kind==="passive")?"passive":"standalone";

function locateSteps(steps:MechanicsStep[],gate:Gate="on_reach",save?:CalculatorSave,result:LocatedStep[]=[],saving?:SavingStep):LocatedStep[]{
  for(const step of steps){
    if(step.kind==="saving_throw"){
      locateSteps(step.failure,"on_failed_save",step.ability,result,step);
      if(step.success)locateSteps(step.success,"on_reach",step.ability,result,step);
    }else result.push({step,...("application" in step&&step.application?{gate:step.application}:{gate}),...(save?{save}:{}),...(saving?.damage_on_success==="half"?{halfOnSuccess:true}:{}),...(saving?{saving}:{})});
  }
  return result;
}

const tierSteps=(tier:MechanicsTier):LocatedStep[]=>[...locateSteps(tier.steps??[]),...(tier.events??[]).flatMap(event=>locateSteps(event.steps))];

function mechanicsDamage(value:MechanicsValue,resolution:CalculatorDamage["resolution"]):CalculatorDamage{
  if(value.kind==="fixed")return{kind:"fixed",resolution,value:value.value};
  if(value.kind==="dice")return{kind:"dice",resolution,count:value.count,sides:value.sides};
  if(value.kind==="manifested_strike_dice")return{kind:"manifested_strike_dice",resolution,count:value.count};
  if(value.kind==="psionic_ability_modifier")return{kind:"psionic_ability_modifier",resolution,...(value.multiplier===1?{}:{multiplier:value.multiplier})};
  throw new Error(`Unsupported Calculator damage formula ${value.kind}`);
}

const savingThrow=(tier:MechanicsTier):CalculatorSave|undefined=>{
  const saves=[...(tier.steps??[]),...(tier.events??[]).flatMap(event=>event.steps)].flatMap(function collect(step):CalculatorSave[]{return step.kind==="saving_throw"?[step.ability,...step.failure.flatMap(collect),...(step.success??[]).flatMap(collect)]:[];});
  const unique=uniqueValues(saves);if(unique.length>1)throw new Error(`Tier ${tier.tier} uses multiple Calculator saving throws`);return unique[0];
};

function calculatorTier(tier:MechanicsTier):NonNullable<CalculatorFeature["tiers"]>[number]{
  const located=tierSteps(tier),damages=located.filter((item):item is LocatedStep&{step:Extract<MechanicsStep,{kind:"damage"}>}=>item.step.kind==="damage");
  const primary=damages.find(item=>item.step.target!=="secondary"),secondary=damages.find(item=>item.step.target==="secondary"),save=savingThrow(tier);
  const resolution=(item:typeof primary):CalculatorDamage["resolution"]=>item?.halfOnSuccess?"half_on_success":item?.gate==="on_failed_save"?"failed_save":"always";
  const result:NonNullable<CalculatorFeature["tiers"]>[number]={tier:tier.tier,damage:primary?mechanicsDamage(primary.step.value,resolution(primary)):{kind:"none",resolution:"always"}};
  if(secondary)result.secondary_damage=mechanicsDamage(secondary.step.value,resolution(secondary));
  if(save)result.save=save;
  return result;
}

function totalTargetMetric(surfaces:MechanicsSurface[]):CalculatorMetric|undefined{
  const surface=surfaces.find(candidate=>candidate.tiers?.length===3&&candidate.tiers.every(tier=>tier.targeting.kind==="struck_plus_additional")&&candidate.tiers.some(tier=>tier.targeting.kind==="struck_plus_additional"&&tier.targeting.additional_count.kind==="proficiency_bonus"));if(!surface?.tiers)return undefined;
  return {kind:"fixed_plus_proficiency_bonus_multiplier",label:"total_targets",unit:"creatures",values:surface.tiers.map(tier=>{
    const targeting=tier.targeting as Extract<MechanicsTargeting,{kind:"struck_plus_additional"}>,count=targeting.additional_count;
    return count.kind==="fixed"?{tier:tier.tier,fixed:1+count.value,multiplier:0}:{tier:tier.tier,fixed:1,multiplier:count.multiplier};
  })};
}

function calculatorMetrics(surfaces:MechanicsSurface[]):CalculatorMetric[]{
  const metrics:CalculatorMetric[]=[];
  for(const surface of surfaces)if(surface.limits)metrics.push({kind:"floor_proficiency_bonus_divisor",label:"uses_per_rest",divisor:surface.limits.uses.divisor});
  for(const surface of surfaces)for(const located of locateSteps(surface.steps??[])){
    if(located.step.kind==="skill_modifier")metrics.push({kind:"psionic_ability_modifier_multiplier",label:located.step.metric,multiplier:located.step.value.multiplier});
    if(located.step.kind==="metric"){
      const {metric,value}=located.step;
      if(value.kind==="psionic_ability_modifier"&&metric==="chosen_skill_bonus")metrics.push({kind:"psionic_ability_modifier_multiplier",label:metric,multiplier:value.multiplier});
      else if(value.kind==="psi_points_plus_fixed"&&metric==="maximum_psi_points")metrics.push({kind:"psi_points_plus_fixed",label:metric,value:value.value});
      else throw new Error(`Unsupported untiered Calculator metric formula ${value.kind}`);
    }
  }
  const tierMetrics=new Map<Extract<MechanicsStep,{kind:"metric"}>["metric"],Array<{tier:0|1|2;value:MechanicsValue;unit?:"feet"}>>();
  for(const surface of surfaces)for(const tier of surface.tiers??[])for(const located of tierSteps(tier))if(located.step.kind==="metric"){
    const rows=tierMetrics.get(located.step.metric)??[];rows.push({tier:tier.tier,value:located.step.value,...(located.step.unit?{unit:located.step.unit}:{})});tierMetrics.set(located.step.metric,rows);
  }
  for(const [label,rows] of tierMetrics){
    const first=rows[0]!.value;
    if(first.kind==="fixed_plus_proficiency_bonus_multiplier"&&label==="fly_speed"&&rows.every(row=>row.value.kind===first.kind))metrics.push({kind:first.kind,label,unit:"feet",values:rows.map(row=>{const value=row.value as Extract<MechanicsValue,{kind:"fixed_plus_proficiency_bonus_multiplier"}>;return{tier:row.tier,fixed:value.fixed,multiplier:value.multiplier};})});
    else if(first.kind==="dice_plus_psionic_ability_modifier"&&label==="damage_reduction"&&rows.every(row=>row.value.kind===first.kind))metrics.push({kind:first.kind,label,values:rows.map(row=>{const value=row.value as Extract<MechanicsValue,{kind:"dice_plus_psionic_ability_modifier"}>;return{tier:row.tier,count:value.count,sides:value.sides,multiplier:value.multiplier};})});
    else throw new Error(`Unsupported tiered Calculator metric formula ${first.kind}`);
  }
  const targets=totalTargetMetric(surfaces);if(targets)metrics.push(targets);return metrics;
}

export function projectCalculatorMechanics(entity:Entity):CalculatorFeature|null{
  if(!entity.mechanics)return null;const surfaces=entity.mechanics.surfaces,tiers=surfaces.flatMap(surface=>surface.tiers??[]).sort((left,right)=>left.tier-right.tier),metrics=calculatorMetrics(surfaces);
  return {entity_id:entity.id,delivery:calculatorDelivery(surfaces),...(metrics.length?{metrics}:{}),...(tiers.length?{tiers:tiers.map(calculatorTier)}:{})};
}

function harnessDuration(duration:Extract<MechanicsStep,{kind:"speed_modifier"|"speed_zero"|"speed_reduction"|"condition"|"reaction_denial"|"attack_modifier"}>["duration"]):HarnessControlEffect["duration"]{
  if(duration==="continuous")throw new Error("Continuous effects are not harness control durations");return duration;
}

type ProjectedControlEffect=HarnessControlEffect&{package_id?:string};
function controlEffect(located:LocatedStep,includeAllRole=true):ProjectedControlEffect|null{
  const {step,gate}=located,package_id="package_id" in step?step.package_id:undefined,target_role="target" in step&&(step.target!=="all"||includeAllRole||package_id)?step.target:undefined;
  if(step.kind==="speed_modifier")return{gate,outcomes:["speed_reduction"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{}),magnitude_feet:Math.abs(step.feet)};
  if(step.kind==="speed_reduction")return{gate,outcomes:["speed_reduction"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{})};
  if(step.kind==="speed_zero")return{gate,outcomes:["speed_zero"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{})};
  if(step.kind==="condition")return{gate,conditions:[step.condition],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{})};
  if(step.kind==="reaction_denial")return{gate,outcomes:["reaction_denial"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{})};
  if(step.kind==="attack_modifier")return{gate,outcomes:["attack_disadvantage"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{}),attack_scope:step.scope};
  if(step.kind==="forced_movement")return step.success_feet!==undefined?{gate:"on_reach",outcomes:["forced_movement"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{}),failed_save_magnitude_feet:step.feet,successful_save_magnitude_feet:step.success_feet}:{gate,outcomes:["forced_movement"],duration:harnessDuration(step.duration),...(target_role?{target_role}:{}),...(package_id?{package_id}:{}),magnitude_feet:step.feet,...(step.requires_condition?{requires_condition:step.requires_condition}:{})};
  return null;
}

const mergeKey=(effect:ProjectedControlEffect)=>JSON.stringify({package_id:effect.package_id,gate:effect.gate,duration:effect.duration,target_role:effect.target_role,requires_condition:effect.requires_condition,magnitude_feet:effect.magnitude_feet,failed_save_magnitude_feet:effect.failed_save_magnitude_feet,successful_save_magnitude_feet:effect.successful_save_magnitude_feet});
function mergeControlEffects(effects:ProjectedControlEffect[]):HarnessControlEffect[]{
  const result:ProjectedControlEffect[]=[];
  for(const effect of effects){const prior=result.find(candidate=>mergeKey(candidate)===mergeKey(effect));if(!prior){result.push(effect);continue;}
    if(effect.conditions)prior.conditions=[...new Set([...(prior.conditions??[]),...effect.conditions])];
    if(effect.outcomes)prior.outcomes=[...new Set([...(prior.outcomes??[]),...effect.outcomes])];
    if(effect.attack_scope){if(prior.attack_scope&&prior.attack_scope!==effect.attack_scope)throw new Error("Conflicting attack scopes in one control package");prior.attack_scope=effect.attack_scope;}
  }
  return result.map(effect=>{const {package_id:discarded,...projected}=effect;void discarded;return projected;});
}

function harnessControlTier(tier:MechanicsTier,hitGated:boolean):HarnessControlTier|null{
  const located=tierSteps(tier),effects=mergeControlEffects(located.map(item=>controlEffect(item,tier.targeting.kind==="area")).filter((effect):effect is HarnessControlEffect=>effect!==null));if(!effects.length)return null;
  const failed=located.filter(item=>item.gate==="on_failed_save"&&item.save),saves=uniqueValues(failed.map(item=>item.save!));if(saves.length>1)throw new Error(`Tier ${tier.tier} uses multiple harness control saving throws`);
  const saving=failed[0]?.saving,application=saves.length?"failed_save":"no_save";
  return{tier:tier.tier,application,...(saves[0]?{save:saves[0]}:{}),...(hitGated?{hit_gated:true}:{}),effects,...(saving?.maximum_size?{maximum_size:saving.maximum_size}:{}),...(saving?.required_creature_type?{required_creature_type:saving.required_creature_type}:{}),...(saving?.repeat?{repeat_save_trigger:saving.repeat.trigger,...(saving.repeat.disadvantage?{repeat_save_disadvantage:true}:{})}:{})};
}

const withoutTier=(value:HarnessControlTier):unknown=>{const {tier:discarded,...rest}=value;void discarded;return rest;};
const samePackage=(left:HarnessControlTier,right:HarnessControlTier):boolean=>JSON.stringify(withoutTier(left))===JSON.stringify(withoutTier(right));

function harnessTargeting(tier:MechanicsTier,surface:MechanicsSurface):NonNullable<HarnessFeatureRule["targeting_by_tier"]>[number]|null{
  const target=tier.targeting;
  if(target.kind==="struck_plus_additional")return target.additional_count.kind==="fixed"?{tier:tier.tier,kind:"fixed_additional",additional_targets:target.additional_count.value}:{tier:tier.tier,kind:"proficiency_bonus_additional"};
  if(target.kind==="primary_plus_additional")return target.additional_count.kind==="fixed"?{tier:tier.tier,kind:"fixed_additional",additional_targets:target.additional_count.value}:{tier:tier.tier,kind:"proficiency_bonus_additional"};
  if(target.kind==="selected_targets")return target.count.kind==="fixed"&&target.count.value>1?{tier:tier.tier,kind:"fixed_additional",additional_targets:target.count.value-1}:target.count.kind==="proficiency_bonus"?{tier:tier.tier,kind:"proficiency_bonus_additional"}:null;
  if(target.kind==="area"&&(surface.delivery.kind==="rider"||surface.recurrence==="remaining_round_starts"))return{tier:tier.tier,kind:"cluster_remainder"};
  return null;
}

export function projectHarnessMechanics(entity:Entity):HarnessFeatureRule|null{
  if(!entity.mechanics)return null;const surfaces=entity.mechanics.surfaces,tiers=surfaces.flatMap(surface=>(surface.tiers??[]).map(tier=>({surface,tier}))).sort((left,right)=>left.tier.tier-right.tier.tier);
  const hasHarnessFacts=surfaces.some(surface=>surface.damage_type)||tiers.some(({tier})=>tierSteps(tier).some(item=>item.step.kind==="damage"||item.step.kind==="armor_class_modifier"||controlEffect(item,tier.targeting.kind==="area")!==null));if(!hasHarnessFacts)return null;
  const authoredDisciplines=entity.classifications.rules_area.filter((area):area is typeof disciplineIds[number]=>disciplineIds.includes(area as typeof disciplineIds[number]));if(!authoredDisciplines.length&&entity.classifications.rules_area.includes("advanced_training"))authoredDisciplines.push(...disciplineIds);
  const damageTypes=uniqueValues([...surfaces.flatMap(surface=>surface.damage_type?[surface.damage_type]:[]),...tiers.flatMap(({tier})=>tierSteps(tier).flatMap(item=>item.step.kind==="damage"?[item.step.damage_type]:[]))]);const damage_type=damageTypes[0];if(!damage_type)throw new Error(`${entity.id} lacks an explicit damage type`);if(damageTypes.length>1)throw new Error(`${entity.id} uses multiple explicit damage types`);
  const targeting=tiers.map(({surface,tier})=>harnessTargeting(tier,surface)).filter((row):row is NonNullable<HarnessFeatureRule["targeting_by_tier"]>[number]=>row!==null);
  const controls:HarnessControlTier[]=[];let previousTier:MechanicsTier|undefined;for(const {surface,tier} of tiers){const control=harnessControlTier(tier,surface.delivery.kind==="rider"),damageSignature=(candidate:MechanicsTier|undefined)=>candidate?tierSteps(candidate).filter(item=>item.step.kind==="damage").map(item=>item.step):[],currentDamage=damageSignature(tier),priorDamage=damageSignature(previousTier),scaledRestatement=surface.delivery.kind==="rider"&&currentDamage.length>0&&priorDamage.length>0&&JSON.stringify(currentDamage)!==JSON.stringify(priorDamage);if(control&&(!controls.length||!samePackage(control,controls.at(-1)!)||scaledRestatement))controls.push(control);previousTier=tier;}
  const ignored=tiers.filter(({tier})=>tierSteps(tier).some(item=>item.step.kind==="damage"&&item.step.ignores_resistance)).map(({tier})=>tier.tier);
  const armor=tiers.flatMap(({tier})=>tierSteps(tier).flatMap(item=>item.step.kind==="armor_class_modifier"?[{tier:tier.tier,value:Math.abs(item.step.value)}]:[]));
  const recurrences=[...new Set(surfaces.flatMap(surface=>surface.recurrence?[surface.recurrence]:[]))];if(recurrences.length>1)throw new Error(`${entity.id} uses multiple recurrence contracts`);const recurrence=recurrences[0];
  return {entity_id:entity.id,discipline_ids:[...authoredDisciplines],damage_type,...(ignored.length?{ignore_resistance_tiers:ignored}:{}),...(surfaces.some(surface=>surface.interactions?.kinetic_mastery==="replace")?{replaces_mastery:true}:{}),...(targeting.length?{targeting_by_tier:targeting}:{}),...(armor.length?{armor_class_reduction_by_tier:armor}:{}),...(recurrence==="remaining_round_starts"?{damage_repetition:"remaining_round_starts" as const,starts_persistent_zone:true}:{}),...(recurrence==="start_of_affected_turn_after_repeat_save"?{damage_timing:"start_of_affected_turn_after_repeat_save" as const}:{}),...(controls.length?{control_tiers:controls}:{})};
}

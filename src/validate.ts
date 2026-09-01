import type { Authority, Diagnostic, MechanicsStep, MechanicsSurface, MechanicsTier } from "./types.js";
import { canonicalJson,codepointCompare } from "./canonical.js";
import { projectCalculatorMechanics,projectHarnessMechanics } from "./mechanics.js";

function duplicateDiagnostics(values:string[],code:string,label:string):Diagnostic[]{const seen=new Set<string>();const diagnostics:Diagnostic[]=[];for(const value of values){if(seen.has(value))diagnostics.push({severity:"error",code,message:`Duplicate ${label}: ${value}`});seen.add(value);}return diagnostics;}
function vocabulary(authority:Authority,name:string):Set<string>{return new Set((authority.vocabularies[name]??[]).map(value=>value.id));}
function mechanicsStepDiagnostics(entityId:string,surface:MechanicsSurface,steps:MechanicsStep[],path:string):Diagnostic[]{
  const diagnostics:Diagnostic[]=[],seenStepIds=new Set<string>(),modeIds=new Set((surface.modes??[]).map(mode=>mode.id));
  const visitSteps=(rows:MechanicsStep[],rowsPath:string)=>{for(const [index,step] of rows.entries()){
    const stepPath=`${rowsPath}/${index}`;
    if("replaces" in step&&step.replaces&&!seenStepIds.has(step.replaces))diagnostics.push({severity:"error",code:"mechanics.replacement_reference",message:`${entityId} replacement target must be an earlier step in the same tier: ${step.replaces}`,path:stepPath});
    if("id" in step&&step.id){if(seenStepIds.has(step.id))diagnostics.push({severity:"error",code:"mechanics.step_duplicate",message:`${entityId} mechanics step ID is duplicated: ${step.id}`,path:stepPath});seenStepIds.add(step.id);}
    if(step.kind==="forced_movement")for(const [directionIndex,direction] of (step.directions??[]).entries())if(!modeIds.has(direction.mode))diagnostics.push({severity:"error",code:"mechanics.mode_reference",message:`${entityId} forced-movement direction references unknown mode: ${direction.mode}`,path:`${stepPath}/directions/${directionIndex}/mode`});
    if(step.kind==="saving_throw"){visitSteps(step.failure,`${stepPath}/failure`);visitSteps(step.success??[],`${stepPath}/success`);}
  }};
  visitSteps(steps,path);return diagnostics;
}
function mechanicsTierDiagnostics(entityId:string,surface:MechanicsSurface,tiers:MechanicsTier[],path:string):Diagnostic[]{
  const diagnostics:Diagnostic[]=duplicateDiagnostics(tiers.map(tier=>String(tier.tier)),"mechanics.tier_duplicate",`${entityId} ${surface.id} tier`).map(diagnostic=>({...diagnostic,path}));
  for(const [tierIndex,tier] of tiers.entries()){
    diagnostics.push(...mechanicsStepDiagnostics(entityId,surface,tier.steps??[],`${path}/${tierIndex}/steps`));
    for(const [eventIndex,event] of (tier.events??[]).entries())diagnostics.push(...mechanicsStepDiagnostics(entityId,surface,event.steps,`${path}/${tierIndex}/events/${eventIndex}/steps`));
  }
  return diagnostics;
}
const inlineText=(nodes:any[]|undefined):string=>nodes?.map(node=>node.text??node.label??String(node.value?.value??"")).join("")??"";
export const isCalculatorDeckEntity=(entity:Authority["entities"][number]):boolean=>entity.presentation_metadata.presentation_owner==="calculator_deck"||(entity.kind==="feature"&&entity.presentation_metadata.primary_rules_area!=="common_features");

interface LocatedValue<T>{path:string;value:T}
function collectOnboardingIds(value:unknown,path="/onboarding",result:LocatedValue<string>[]=[]):LocatedValue<string>[] {
  if(Array.isArray(value)){value.forEach((item,index)=>collectOnboardingIds(item,`${path}/${index}`,result));return result;}
  if(!value||typeof value!=="object")return result;
  for(const [key,child] of Object.entries(value)){
    const childPath=`${path}/${key}`;
    if(key==="id"&&typeof child==="string")result.push({path:childPath,value:child});
    else collectOnboardingIds(child,childPath,result);
  }
  return result;
}
function collectOnboardingDestinations(value:unknown,path="/onboarding",result:LocatedValue<any>[]=[]):LocatedValue<any>[] {
  if(Array.isArray(value)){value.forEach((item,index)=>collectOnboardingDestinations(item,`${path}/${index}`,result));return result;}
  if(!value||typeof value!=="object")return result;
  const object=value as Record<string,unknown>;
  if(typeof object.kind==="string"&&(object.kind==="calculator"||typeof object.section_id==="string"||typeof object.category_id==="string"||typeof object.entity_id==="string"))result.push({path,value:object});
  for(const [key,child] of Object.entries(object))collectOnboardingDestinations(child,`${path}/${key}`,result);
  return result;
}
function collectOnboardingStrings(value:unknown,result:string[]=[]):string[]{
  if(typeof value==="string"){result.push(value);return result;}if(Array.isArray(value)){value.forEach(item=>collectOnboardingStrings(item,result));return result;}if(value&&typeof value==="object")Object.values(value).forEach(item=>collectOnboardingStrings(item,result));return result;
}
function validateCalculatorLevelBands(bands:Authority["calculator"]["proficiency_bonus_bands"],minimumLevel:number,maximumLevel:number,label:string,path:string):Diagnostic[]{
  const diagnostics:Diagnostic[]=[];const coverage=new Map<number,number>();
  for(const [index,band] of bands.entries()){
    if(band.minimum_level>band.maximum_level)diagnostics.push({severity:"error",code:"calculator.band_range",message:`${label} band ${index+1} has minimum level ${band.minimum_level} after maximum level ${band.maximum_level}`,path:`${path}/${index}`});
    for(let level=band.minimum_level;level<=band.maximum_level;level++)coverage.set(level,(coverage.get(level)??0)+1);
  }
  const missing:number[]=[],overlapping:number[]=[];for(let level=minimumLevel;level<=maximumLevel;level++){const count=coverage.get(level)??0;if(count===0)missing.push(level);else if(count>1)overlapping.push(level);}
  if(missing.length||overlapping.length)diagnostics.push({severity:"error",code:"calculator.band_coverage",message:`${label} bands must cover Fighter levels ${minimumLevel}–${maximumLevel} exactly once${missing.length?`; missing ${missing.join(", ")}`:""}${overlapping.length?`; overlapping ${overlapping.join(", ")}`:""}`,path});
  return diagnostics;
}

export function validateSemantics(authority:Authority):Diagnostic[]{
  const diagnostics:Diagnostic[]=[];
  const entities=new Map(authority.entities.map(entity=>[entity.id,entity]));
  diagnostics.push(...duplicateDiagnostics(authority.entities.map(entity=>entity.id),"entity.duplicate","entity ID"));
  for(const [entityIndex,entity] of authority.entities.entries())if(entity.concentration_tiers!==undefined){
    if(entity.requires_concentration!==true)diagnostics.push({severity:"error",code:"entity.concentration_tiers_requirement",message:`${entity.id} concentration tiers require requires_concentration: true`,path:`/entities/${entityIndex}/requires_concentration`});
    if(entity.concentration_duration===undefined)diagnostics.push({severity:"error",code:"entity.concentration_tiers_duration",message:`${entity.id} concentration tiers require a concentration duration`,path:`/entities/${entityIndex}/concentration_duration`});
  }
  const calculator=authority.calculator;
  const expectedDefaults={default_card_id:"manifested_strike",default_fighter_level:20,default_psionic_ability_modifier:5} as const;
  for(const [field,expected] of Object.entries(expectedDefaults))if(calculator[field as keyof typeof expectedDefaults]!==expected)diagnostics.push({severity:"error",code:"calculator.default",message:`Calculator ${field} must be ${expected}`,path:`/calculator/${field}`});
  if(calculator.default_fighter_level<calculator.fighter_level_minimum||calculator.default_fighter_level>calculator.fighter_level_maximum)diagnostics.push({severity:"error",code:"calculator.default_level",message:"Calculator default Fighter level is outside its supported range",path:"/calculator/default_fighter_level"});
  if(calculator.default_psionic_ability_modifier<calculator.psionic_ability_modifier_minimum||calculator.default_psionic_ability_modifier>calculator.psionic_ability_modifier_maximum)diagnostics.push({severity:"error",code:"calculator.default_modifier",message:"Calculator default Psionic Ability modifier is outside its supported range",path:"/calculator/default_psionic_ability_modifier"});
  const calculatorFeatureIds=calculator.features.map(feature=>feature.entity_id);
  diagnostics.push(...duplicateDiagnostics(calculatorFeatureIds,"calculator.feature_duplicate","calculator feature entity ID"));
  const projectedRiderIds=calculator.features.filter(feature=>feature.delivery==="on_hit_rider").map(feature=>feature.entity_id).sort(codepointCompare);
  const deckRiderIds=authority.entities.filter(entity=>isCalculatorDeckEntity(entity)&&entity.activation==="on_hit"&&entity.classifications.feature_role==="rider").map(entity=>entity.id).sort(codepointCompare);
  if(JSON.stringify(projectedRiderIds)!==JSON.stringify(deckRiderIds))diagnostics.push({severity:"error",code:"calculator.rider_coverage",message:"Every deck-owned on-hit rider must retain a Calculator projection exactly once",path:"/calculator/features"});
  const calculatorFeaturesById=new Map(calculator.features.map(feature=>[feature.entity_id,feature])),harnessRulesById=new Map(calculator.harness_mechanics.feature_rules.map(rule=>[rule.entity_id,rule]));
  for(const [entityIndex,entity] of authority.entities.entries())if(entity.mechanics){
    const mechanicsPath=`/entities/${entityIndex}/mechanics`,surfaceIds=entity.mechanics.surfaces.map(surface=>surface.id);diagnostics.push(...duplicateDiagnostics(surfaceIds,"mechanics.surface_duplicate",`${entity.id} mechanics surface`).map(diagnostic=>({...diagnostic,path:`${mechanicsPath}/surfaces`})));
    for(const [surfaceIndex,surface] of entity.mechanics.surfaces.entries()){
      diagnostics.push(...duplicateDiagnostics((surface.modes??[]).map(mode=>mode.id),"mechanics.mode_duplicate",`${entity.id} ${surface.id} mode`).map(diagnostic=>({...diagnostic,path:`${mechanicsPath}/surfaces/${surfaceIndex}/modes`})));
      diagnostics.push(...mechanicsStepDiagnostics(entity.id,surface,surface.steps??[],`${mechanicsPath}/surfaces/${surfaceIndex}/steps`));
      diagnostics.push(...mechanicsTierDiagnostics(entity.id,surface,surface.tiers??[],`${mechanicsPath}/surfaces/${surfaceIndex}/tiers`));
    }
    try{
      const projectedCalculator=projectCalculatorMechanics(entity),legacyCalculator=calculatorFeaturesById.get(entity.id)??null;
      if(canonicalJson(projectedCalculator)!==canonicalJson(legacyCalculator))diagnostics.push({severity:"error",code:"mechanics.calculator_equivalence",message:`${entity.id} neutral mechanics do not reproduce its Calculator projection`,path:mechanicsPath});
      const projectedHarness=projectHarnessMechanics(entity),legacyHarness=harnessRulesById.get(entity.id)??null;
      if(canonicalJson(projectedHarness)!==canonicalJson(legacyHarness))diagnostics.push({severity:"error",code:"mechanics.harness_equivalence",message:`${entity.id} neutral mechanics do not reproduce its harness projection`,path:mechanicsPath});
    }catch(error){diagnostics.push({severity:"error",code:"mechanics.projection",message:`${entity.id} neutral mechanics cannot be projected: ${error instanceof Error?error.message:String(error)}`,path:mechanicsPath});}
  }
  const utilityIds=calculator.utility_cards.map(card=>card.id);diagnostics.push(...duplicateDiagnostics(utilityIds,"calculator.utility_duplicate","calculator utility card ID"));
  if(JSON.stringify([...utilityIds].sort(codepointCompare))!==JSON.stringify(["blood_tax","holdout_option","manifested_strike"]))diagnostics.push({severity:"error",code:"calculator.utility_coverage",message:"Calculator utility cards must be exactly Manifested Strike, Holdout Option, and Blood Tax",path:"/calculator/utility_cards"});
  for(const [utilityIndex,card] of calculator.utility_cards.entries()){
    const path=`/calculator/utility_cards/${utilityIndex}`,source=entities.get(card.source_entity_id);
    if(!source)diagnostics.push({severity:"error",code:"calculator.utility_source_unknown",message:`Calculator utility ${card.id} references unknown source entity ${card.source_entity_id}`,path:`${path}/source_entity_id`});
    if(card.id!==card.calculation_kind)diagnostics.push({severity:"error",code:"calculator.utility_kind",message:`Calculator utility ${card.id} must use its matching typed calculation kind`,path:`${path}/calculation_kind`});
    for(const relatedId of card.related_card_ids??[]){
      if(relatedId===card.id)diagnostics.push({severity:"error",code:"calculator.utility_related_self",message:`Calculator utility ${card.id} cannot relate to itself`,path:`${path}/related_card_ids`});
      if(!utilityIds.includes(relatedId))diagnostics.push({severity:"error",code:"calculator.utility_related_unknown",message:`Calculator utility ${card.id} references unknown related card ${relatedId}`,path:`${path}/related_card_ids`});
    }
    for(const [contextIndex,context] of (card.context??[]).entries()){
      const contextEntity=entities.get(context.entity_id),contextPath=`${path}/context/${contextIndex}`;
      if(!contextEntity)diagnostics.push({severity:"error",code:"calculator.utility_context_unknown",message:`Calculator utility ${card.id} references unknown context entity ${context.entity_id}`,path:`${contextPath}/entity_id`});
      else for(const blockIndex of context.content_block_indexes)if(!contextEntity.content[blockIndex])diagnostics.push({severity:"error",code:"calculator.utility_context_block",message:`Calculator utility ${card.id} references missing ${context.entity_id} content block ${blockIndex}`,path:`${contextPath}/content_block_indexes`});
    }
  }
  const tierMinimums=calculator.tier_minimum_levels.map(item=>item.tier);diagnostics.push(...duplicateDiagnostics(tierMinimums.map(String),"calculator.tier_minimum_duplicate","calculator tier minimum"));
  const expectedTierMinimums=[[0,3],[1,3],[2,10]] as const;
  if(JSON.stringify(calculator.tier_minimum_levels.map(item=>[item.tier,item.minimum_level]))!==JSON.stringify(expectedTierMinimums))diagnostics.push({severity:"error",code:"calculator.tier_minimum_levels",message:"Calculator tier minimum levels must be Tier 0 at level 3, Tier 1 at level 3, and Tier 2 at level 10",path:"/calculator/tier_minimum_levels"});
  const harness=calculator.harness_mechanics;
  if(JSON.stringify(harness.action_economy)!==JSON.stringify({standalone_psionic_action_limit_per_turn:1,action_surge_allows_additional_standalone_psionic_action:false}))diagnostics.push({severity:"error",code:"harness.action_economy",message:"Harness action economy must allow at most one standalone psionic Action per turn and no additional standalone activation from Action Surge",path:"/calculator/harness_mechanics/action_economy"});
  if(harness.manifested_strike.rider_repeatability!=="per_manifested_strike")diagnostics.push({severity:"error",code:"harness.rider_repeatability",message:"Manifested Strike riders must use the supported per_manifested_strike repeatability contract",path:"/calculator/harness_mechanics/manifested_strike/rider_repeatability"});
  const expectedHoldout={damage_type:"force",declaration_timing:"before_attack_roll",formulas:[{minimum_level:3,maximum_level:17,kind:"halve_total_rounded_down"},{minimum_level:18,maximum_level:20,kind:"dice_plus_psionic_ability_modifier",count:1,sides:6}]};
  if(JSON.stringify(harness.manifested_strike.holdout)!==JSON.stringify(expectedHoldout))diagnostics.push({severity:"error",code:"harness.holdout_formula",message:"Holdout must retain the level-banded base and Refined Holdout formulas",path:"/calculator/harness_mechanics/manifested_strike/holdout"});
  if(JSON.stringify(harness.manifested_strike.attack_bonus)!==JSON.stringify({base:0,components:["psionic_ability_modifier","proficiency_bonus","psionic_focus"]}))diagnostics.push({severity:"error",code:"harness.attack_formula",message:"Manifested Strike attack bonus must use its canonical base and ordered components",path:"/calculator/harness_mechanics/manifested_strike/attack_bonus"});
  if(JSON.stringify(harness.manifested_strike.save_dc)!==JSON.stringify({base:8,components:["proficiency_bonus","psionic_ability_modifier"]}))diagnostics.push({severity:"error",code:"harness.save_dc_formula",message:"Kinetic Vanguard save DC must use its canonical base and ordered components",path:"/calculator/harness_mechanics/manifested_strike/save_dc"});
  if(JSON.stringify(harness.overload.blood_tax_per_tier)!==JSON.stringify({base:0,proficiency_bonus_multiplier:1}))diagnostics.push({severity:"error",code:"harness.blood_tax_formula",message:"Blood Tax per tier must use its canonical base and Proficiency Bonus multiplier",path:"/calculator/harness_mechanics/overload/blood_tax_per_tier"});
  if(JSON.stringify(harness.overload.mastery)!==JSON.stringify({minimum_level:18,uses_per_rest:1,blood_tax_divisor:2,minimum_per_overload:1}))diagnostics.push({severity:"error",code:"harness.overload_mastery",message:"Overload Mastery must retain its canonical level, use, divisor, and minimum",path:"/calculator/harness_mechanics/overload/mastery"});
  const expectedApex={minimum_level:18,psychokinesis_manifested_strike_hit:{discipline_id:"psychokinesis",uses_per_attack_action:1,reset:"start_of_each_attack_action",damage_type:"force",damage:{kind:"dice",count:3,sides:8},critical_dice_multiplier:1,psi_cost:0,blood_tax:0}};
  if(JSON.stringify(harness.psionic_apex)!==JSON.stringify(expectedApex))diagnostics.push({severity:"error",code:"harness.psionic_apex",message:"Psionic Apex must retain the once-per-Attack-action Psychokinesis damage packet",path:"/calculator/harness_mechanics/psionic_apex"});
  const disciplineIds=harness.disciplines.map(item=>item.id);
  diagnostics.push(...duplicateDiagnostics(disciplineIds,"harness.discipline_duplicate","harness discipline ID"));
  const expectedDisciplines=["cryokinesis","electrokinesis","psychokinesis","pyrokinesis"];
  if(JSON.stringify([...disciplineIds].sort(codepointCompare))!==JSON.stringify(expectedDisciplines))diagnostics.push({severity:"error",code:"harness.discipline_coverage",message:"Harness mechanics must define exactly the four Kinetic Disciplines",path:"/calculator/harness_mechanics/disciplines"});
  for(const [disciplineIndex,discipline] of harness.disciplines.entries()){
    const mastery=discipline.mastery,path=`/calculator/harness_mechanics/disciplines/${disciplineIndex}/mastery`,outcomes=new Set(mastery.control_outcomes);
    if((outcomes.has("speed_reduction")||outcomes.has("forced_movement"))&&(!mastery.control_duration||mastery.control_magnitude_feet===undefined))diagnostics.push({severity:"error",code:"harness.mastery_control_measurement",message:`${discipline.id} measured mastery control requires duration and feet magnitude`,path});
    if(outcomes.has("attack_disadvantage")&&(!mastery.control_duration||!mastery.attack_scope))diagnostics.push({severity:"error",code:"harness.mastery_attack_scope",message:`${discipline.id} attack impairment requires duration and attack scope`,path});
    if(!mastery.control_outcomes.length&&(mastery.control_duration||mastery.control_magnitude_feet!==undefined||mastery.attack_scope))diagnostics.push({severity:"error",code:"harness.mastery_control_extra",message:`${discipline.id} non-control mastery cannot define control measurement fields`,path});
  }
  const featureRules=harness.feature_rules,featureRuleIds=featureRules.map(item=>item.entity_id);
  diagnostics.push(...duplicateDiagnostics(featureRuleIds,"harness.feature_duplicate","harness feature entity ID"));
  const missingShared=featureRuleIds.filter(id=>!calculatorFeatureIds.includes(id));
  if(missingShared.length)diagnostics.push({severity:"error",code:"harness.feature_coverage",message:`Harness mechanics require missing Calculator projections: ${missingShared.join(", ")}`,path:"/calculator/features"});
  for(const [ruleIndex,rule] of featureRules.entries()){
    const rulePath=`/calculator/harness_mechanics/feature_rules/${ruleIndex}`,entity=entities.get(rule.entity_id);
    if(!entity)diagnostics.push({severity:"error",code:"harness.feature_unknown",message:`Harness mechanics reference unknown entity ${rule.entity_id}`,path:`${rulePath}/entity_id`});
    else{
      if(entity.level===undefined)diagnostics.push({severity:"error",code:"harness.feature_level",message:`Harness feature ${rule.entity_id} lacks canonical level availability`,path:`/entities/${authority.entities.indexOf(entity)}/level`});
      if(entity.psi_cost===undefined)diagnostics.push({severity:"error",code:"harness.feature_psi",message:`Harness feature ${rule.entity_id} lacks canonical Psi cost`,path:`/entities/${authority.entities.indexOf(entity)}/psi_cost`});
      const authoredDisciplines=entity.classifications.rules_area.filter(area=>expectedDisciplines.includes(area));
      if(authoredDisciplines.length&&rule.discipline_ids.some(id=>!authoredDisciplines.includes(id)))diagnostics.push({severity:"error",code:"harness.feature_discipline",message:`Harness feature ${rule.entity_id} uses a discipline inconsistent with its canonical classification`,path:`${rulePath}/discipline_ids`});
    }
    const targetingTiers=(rule.targeting_by_tier??[]).map(item=>item.tier);diagnostics.push(...duplicateDiagnostics(targetingTiers.map(String),"harness.targeting_tier_duplicate",`${rule.entity_id} targeting tier`));
    for(const [targetIndex,targeting] of (rule.targeting_by_tier??[]).entries()){
      const targetingPath=`${rulePath}/targeting_by_tier/${targetIndex}`;
      if(targeting.kind==="fixed_additional"&&targeting.additional_targets===undefined)diagnostics.push({severity:"error",code:"harness.targeting_count",message:`${rule.entity_id} fixed targeting requires additional_targets`,path:targetingPath});
      if(targeting.kind!=="fixed_additional"&&targeting.additional_targets!==undefined)diagnostics.push({severity:"error",code:"harness.targeting_count_forbidden",message:`${rule.entity_id} ${targeting.kind} targeting cannot define additional_targets`,path:targetingPath});
    }
    const reductionTiers=(rule.armor_class_reduction_by_tier??[]).map(item=>item.tier);diagnostics.push(...duplicateDiagnostics(reductionTiers.map(String),"harness.armor_reduction_tier_duplicate",`${rule.entity_id} Armor Class reduction tier`));
    if(rule.damage_repetition&&rule.entity_id!=="ball_lightning")diagnostics.push({severity:"error",code:"harness.damage_repetition_feature",message:"Only ball_lightning may repeat damage at remaining round starts",path:`${rulePath}/damage_repetition`});
    if(rule.starts_persistent_zone&&rule.entity_id!=="ball_lightning")diagnostics.push({severity:"error",code:"harness.persistent_zone_feature",message:"Only ball_lightning may start the modeled persistent zone",path:`${rulePath}/starts_persistent_zone`});
    if(rule.damage_timing&&rule.entity_id!=="mass_levitation")diagnostics.push({severity:"error",code:"harness.damage_timing_feature",message:"Only mass_levitation uses start-of-turn post-repeat-save damage timing",path:`${rulePath}/damage_timing`});
    const controlTiers=(rule.control_tiers??[]).map(item=>item.tier);diagnostics.push(...duplicateDiagnostics(controlTiers.map(String),"harness.control_tier_duplicate",`${rule.entity_id} control tier`));
    for(const [controlIndex,control] of (rule.control_tiers??[]).entries()){
      const controlPath=`${rulePath}/control_tiers/${controlIndex}`;
      if(control.application==="failed_save"&&!control.save)diagnostics.push({severity:"error",code:"harness.control_save_required",message:`${rule.entity_id} Tier ${control.tier} control requires a save`,path:controlPath});
      if(control.application==="no_save"&&control.save)diagnostics.push({severity:"error",code:"harness.control_save_forbidden",message:`${rule.entity_id} Tier ${control.tier} no-save control cannot define a save`,path:controlPath});
      const tierConditions=new Set(control.effects.flatMap(effect=>effect.conditions??[]));
      for(const [effectIndex,effect] of control.effects.entries()){
        const effectPath=`${controlPath}/effects/${effectIndex}`;
        if(!(effect.conditions?.length||effect.outcomes?.length))diagnostics.push({severity:"error",code:"harness.control_outcome",message:`${rule.entity_id} Tier ${control.tier} effect must define a condition or non-condition outcome`,path:effectPath});
        if(effect.gate==="on_failed_save"&&control.application!=="failed_save")diagnostics.push({severity:"error",code:"harness.control_gate",message:`${rule.entity_id} Tier ${control.tier} failed-save effect requires failed-save application`,path:effectPath});
        if(effect.conditions?.length&&(control.application!=="failed_save"||!control.save||effect.gate!=="on_failed_save"))diagnostics.push({severity:"error",code:"harness.named_condition_save_required",message:`${rule.entity_id} Tier ${control.tier} hostile named conditions require a canonical save and failed-save gate`,path:effectPath});
        if(effect.requires_condition&&!tierConditions.has(effect.requires_condition))diagnostics.push({severity:"error",code:"harness.control_dependency",message:`${rule.entity_id} Tier ${control.tier} effect depends on an unmodeled ${effect.requires_condition} condition`,path:effectPath});
        const outcomes=new Set(effect.outcomes??[]),hasBranchMagnitude=effect.failed_save_magnitude_feet!==undefined||effect.successful_save_magnitude_feet!==undefined;
        if(outcomes.has("forced_movement")&&!((effect.magnitude_feet!==undefined)!==hasBranchMagnitude))diagnostics.push({severity:"error",code:"harness.control_magnitude",message:`${rule.entity_id} Tier ${control.tier} forced movement requires either one feet magnitude or a save-result magnitude pair`,path:effectPath});
        if(hasBranchMagnitude&&(effect.failed_save_magnitude_feet===undefined||effect.successful_save_magnitude_feet===undefined||control.application!=="failed_save"||effect.gate!=="on_reach"))diagnostics.push({severity:"error",code:"harness.control_branch_magnitude",message:`${rule.entity_id} Tier ${control.tier} branch magnitudes require both save results on an on-reach failed-save effect`,path:effectPath});
        if((effect.magnitude_feet!==undefined||hasBranchMagnitude)&&!outcomes.has("forced_movement")&&!outcomes.has("speed_reduction"))diagnostics.push({severity:"error",code:"harness.control_magnitude_outcome",message:`${rule.entity_id} Tier ${control.tier} feet magnitude requires movement control`,path:effectPath});
        if(outcomes.has("attack_disadvantage")&&!effect.attack_scope)diagnostics.push({severity:"error",code:"harness.control_attack_scope",message:`${rule.entity_id} Tier ${control.tier} attack Disadvantage requires explicit scope`,path:effectPath});
        if(effect.attack_scope&&!outcomes.has("attack_disadvantage"))diagnostics.push({severity:"error",code:"harness.control_attack_scope_extra",message:`${rule.entity_id} Tier ${control.tier} attack scope requires attack Disadvantage`,path:effectPath});
      }
      if(control.repeat_save_trigger&&control.application!=="failed_save")diagnostics.push({severity:"error",code:"harness.repeat_save",message:`${rule.entity_id} Tier ${control.tier} repeat saves require failed-save application`,path:controlPath});
      if(control.repeat_save_disadvantage&&!control.repeat_save_trigger)diagnostics.push({severity:"error",code:"harness.repeat_save_disadvantage",message:`${rule.entity_id} Tier ${control.tier} repeat-save Disadvantage requires a repeat-save trigger`,path:controlPath});
    }
  }
  for(const [featureIndex,feature] of calculator.features.entries()){
    const featurePath=`/calculator/features/${featureIndex}`,entity=entities.get(feature.entity_id);
    if(!entity)diagnostics.push({severity:"error",code:"calculator.feature_unknown",message:`Calculator references unknown feature entity ${feature.entity_id}`,path:`${featurePath}/entity_id`});
    else{
      if(!isCalculatorDeckEntity(entity))diagnostics.push({severity:"error",code:"calculator.feature_ownership",message:`Calculator projection ${feature.entity_id} is not deck-owned`,path:`${featurePath}/entity_id`});
      const validDelivery=feature.delivery==="on_hit_rider"
        ? entity.activation==="on_hit"&&entity.classifications.feature_role==="rider"
        : feature.delivery===entity.classifications.feature_role;
      if(!validDelivery)diagnostics.push({severity:"error",code:"calculator.feature_delivery",message:`Calculator entity ${feature.entity_id} is inconsistent with delivery ${feature.delivery}`,path:`${featurePath}/delivery`});
    }
    const tiers=(feature.tiers??[]).map(tier=>tier.tier);diagnostics.push(...duplicateDiagnostics(tiers.map(String),"calculator.tier_duplicate",`${feature.entity_id} calculator tier`));
    if(feature.tiers&&JSON.stringify([...tiers].sort((a,b)=>a-b))!==JSON.stringify([0,1,2]))diagnostics.push({severity:"error",code:"calculator.tier_coverage",message:`${feature.entity_id} calculator tiers must be exactly 0, 1, and 2`,path:`${featurePath}/tiers`});
    for(const [tierIndex,tier] of (feature.tiers??[]).entries()){
      const tierPath=`${featurePath}/tiers/${tierIndex}`;
      const validateDamage=(damage:typeof tier.damage,path:string,label:string)=>{
        const gated=damage.resolution!=="always";
        if(gated&&!tier.save)diagnostics.push({severity:"error",code:"calculator.damage_save_required",message:`${feature.entity_id} Tier ${tier.tier} ${label} resolution ${damage.resolution} requires a saving throw`,path:`${path}/resolution`});
        if(damage.kind==="none"&&gated)diagnostics.push({severity:"error",code:"calculator.damage_resolution",message:`${feature.entity_id} Tier ${tier.tier} cannot use ${damage.resolution} when ${label} is none`,path:`${path}/resolution`});
      };
      validateDamage(tier.damage,`${tierPath}/damage`,"damage");
      if(tier.secondary_damage){
        if(!["electron_burst","forked_lightning"].includes(feature.entity_id))diagnostics.push({severity:"error",code:"calculator.secondary_damage_feature",message:"Only electron_burst and forked_lightning may define secondary damage",path:`${tierPath}/secondary_damage`});
        validateDamage(tier.secondary_damage,`${tierPath}/secondary_damage`,"secondary damage");
      }else if(["electron_burst","forked_lightning"].includes(feature.entity_id))diagnostics.push({severity:"error",code:"calculator.secondary_damage_required",message:`${feature.entity_id} Tier ${tier.tier} must define secondary damage`,path:`${tierPath}/secondary_damage`});
    }
    for(const [metricIndex,metric] of (feature.metrics??[]).entries())if("values" in metric){const metricTiers=metric.values.map(value=>value.tier);if(JSON.stringify([...metricTiers].sort((a,b)=>a-b))!==JSON.stringify([0,1,2]))diagnostics.push({severity:"error",code:"calculator.metric_tier_coverage",message:`${feature.entity_id} metric ${metric.label} must cover Tiers 0, 1, and 2 exactly once`,path:`${featurePath}/metrics/${metricIndex}/values`});}
  }
  if(!calculator.utility_cards.some(card=>card.id===calculator.default_card_id)&&!authority.entities.some(entity=>isCalculatorDeckEntity(entity)&&entity.id===calculator.default_card_id))diagnostics.push({severity:"error",code:"calculator.default_card_unknown",message:`Calculator default card ${calculator.default_card_id} is not a deck or utility card`,path:"/calculator/default_card_id"});
  diagnostics.push(...validateCalculatorLevelBands(calculator.proficiency_bonus_bands,calculator.fighter_level_minimum,calculator.fighter_level_maximum,"Proficiency Bonus","/calculator/proficiency_bonus_bands"));
  diagnostics.push(...validateCalculatorLevelBands(calculator.psi_point_bands,calculator.fighter_level_minimum,calculator.fighter_level_maximum,"Psi Points","/calculator/psi_point_bands"));
  diagnostics.push(...validateCalculatorLevelBands(calculator.psionic_focus_bands,calculator.fighter_level_minimum,calculator.fighter_level_maximum,"Psionic Focus","/calculator/psionic_focus_bands"));
  diagnostics.push(...validateCalculatorLevelBands(calculator.manifested_strike_die_bands,calculator.fighter_level_minimum,calculator.fighter_level_maximum,"Manifested Strike die","/calculator/manifested_strike_die_bands"));
  for(let level=calculator.fighter_level_minimum;level<=calculator.fighter_level_maximum;level++){
    const proficiencyBand=calculator.proficiency_bonus_bands.find(band=>level>=band.minimum_level&&level<=band.maximum_level);
    const psiBand=calculator.psi_point_bands.find(band=>level>=band.minimum_level&&level<=band.maximum_level);
    if(!proficiencyBand||!psiBand)continue;
    const expected=Math.ceil(level/2)+proficiencyBand.value;
    if(psiBand.value!==expected)diagnostics.push({severity:"error",code:"calculator.psi_point_progression",message:`Calculator Psi Points at Fighter level ${level} must equal half the Fighter level rounded up plus Proficiency Bonus (${expected})`,path:`/calculator/psi_point_bands/${calculator.psi_point_bands.indexOf(psiBand)}/value`});
  }
  diagnostics.push(...duplicateDiagnostics(authority.facets.map(facet=>facet.id),"facet.duplicate","facet ID"));
  const categories=new Map(authority.navigation.categories.map(category=>[category.id,category]));
  if(!categories.has(authority.navigation.default_category_id))diagnostics.push({severity:"error",code:"navigation.default_category",message:"Rules Reference default category is missing"});
  diagnostics.push(...duplicateDiagnostics(authority.navigation.categories.map(category=>category.id),"navigation.category_duplicate","category ID"));
  const topicToArea=new Map<string,string>();const topicEntities=new Map<string,Set<string>>();
  for(const category of authority.navigation.categories){
    if(!category.topics.some(topic=>topic.id===category.default_topic_id))diagnostics.push({severity:"error",code:"navigation.default_topic",message:`Category ${category.id} has an invalid default topic`});
    for(const topic of category.topics){if(topicToArea.has(topic.id))diagnostics.push({severity:"error",code:"navigation.topic_duplicate",message:`Duplicate topic ID ${topic.id}`});topicToArea.set(topic.id,category.id);topicEntities.set(topic.id,new Set(topic.entity_ids));for(const id of topic.entity_ids)if(!entities.has(id))diagnostics.push({severity:"error",code:"navigation.entity_unknown",message:`Topic ${topic.id} references unknown entity ${id}`});}
  }
  const onboardingIds=collectOnboardingIds(authority.onboarding);diagnostics.push(...duplicateDiagnostics(onboardingIds.map(item=>item.value),"onboarding.id_duplicate","onboarding ID"));
  for(const item of onboardingIds)if(entities.has(item.value))diagnostics.push({severity:"error",code:"onboarding.entity_collision",message:`Onboarding ID ${item.value} collides with a publishable entity`,path:item.path});
  if(authority.entities.length!==44)diagnostics.push({severity:"error",code:"onboarding.entity_boundary",message:`Onboarding must remain outside the 44-entity publication boundary; found ${authority.entities.length} entities`,path:"/entities"});
  const sectionIds=new Set([authority.onboarding.basic_turn.id,authority.onboarding.build_checklist.id,authority.onboarding.disciplines.id,authority.onboarding.glossary.id,authority.onboarding.next_destinations.id]);
  const calculatorCardAreas=new Map<string,string>([
    ...authority.calculator.utility_cards.map(card=>[card.id,entities.get(card.source_entity_id)?.presentation_metadata.primary_rules_area??""] as const),
    ...authority.entities.filter(isCalculatorDeckEntity).map(entity=>[entity.id,entity.presentation_metadata.primary_rules_area] as const)
  ]);
  for(const {path,value:destination} of collectOnboardingDestinations(authority.onboarding)){
    if(destination.kind==="calculator"){
      if(destination.rules_area!==undefined&&!vocabulary(authority,"rules_areas").has(destination.rules_area))diagnostics.push({severity:"error",code:"onboarding.calculator_area_unknown",message:`Unknown Calculator rules area ${destination.rules_area}`,path});
      if(destination.card_id!==undefined&&!calculatorCardAreas.has(destination.card_id))diagnostics.push({severity:"error",code:"onboarding.calculator_card_unknown",message:`Unknown Calculator card ${destination.card_id}`,path});
      if(destination.card_id!==undefined&&destination.rules_area!==undefined&&calculatorCardAreas.get(destination.card_id)!==destination.rules_area)diagnostics.push({severity:"error",code:"onboarding.calculator_card_area_mismatch",message:`Calculator card ${destination.card_id} does not belong to ${destination.rules_area}`,path});
      continue;
    }
    if(destination.kind==="onboarding_section"){
      if(!sectionIds.has(destination.section_id))diagnostics.push({severity:"error",code:"onboarding.section_unknown",message:`Unknown onboarding section ${destination.section_id}`,path});
      continue;
    }
    if(destination.kind==="category"){
      const targetCategory=categories.get(destination.category_id);
      if(!targetCategory)diagnostics.push({severity:"error",code:"onboarding.category_unknown",message:`Unknown onboarding category ${destination.category_id}`,path});
      else if(!targetCategory.topics.some(topic=>topic.id===targetCategory.default_topic_id))diagnostics.push({severity:"error",code:"onboarding.category_route",message:`Onboarding category ${destination.category_id} has no resolvable default topic`,path});
      continue;
    }
    if(destination.kind==="entity"){
      const targetEntity=entities.get(destination.entity_id);
      if(!targetEntity){diagnostics.push({severity:"error",code:"onboarding.entity_unknown",message:`Unknown onboarding entity ${destination.entity_id}`,path});continue;}
      if(isCalculatorDeckEntity(targetEntity))continue;
      const primaryArea=targetEntity.presentation_metadata.primary_rules_area,targetCategory=categories.get(primaryArea);
      const containingTopics=targetCategory?.topics.filter(topic=>topic.entity_ids.includes(targetEntity.id))??[];
      const canonicalTopic=targetEntity.presentation_metadata.canonical_topic_by_area[primaryArea]??containingTopics.sort((a,b)=>a.order-b.order)[0]?.id;
      if(!canonicalTopic||!containingTopics.some(topic=>topic.id===canonicalTopic))diagnostics.push({severity:"error",code:"onboarding.entity_route",message:`Onboarding entity ${destination.entity_id} has no resolvable canonical route`,path});
    }
  }
  const disciplineCategories=authority.onboarding.disciplines.cards.map(card=>card.destination.kind==="calculator"?card.destination.rules_area??"":"").sort(codepointCompare);
  const requiredDisciplines=["cryokinesis","electrokinesis","psychokinesis","pyrokinesis"].sort(codepointCompare);
  if(JSON.stringify(disciplineCategories)!==JSON.stringify(requiredDisciplines))diagnostics.push({severity:"error",code:"onboarding.disciplines",message:"Onboarding must target each Discipline Calculator group exactly once",path:"/onboarding/disciplines/cards"});
  const internalPaths=authority.onboarding.primary_paths.filter(path=>path.destination.kind==="onboarding_section").map(path=>path.destination.kind==="onboarding_section"?path.destination.section_id:"").sort(codepointCompare);
  const referencePaths=authority.onboarding.primary_paths.filter(path=>path.destination.kind==="category"&&path.destination.category_id===authority.navigation.default_category_id);
  const calculatorPaths=authority.onboarding.primary_paths.filter(path=>path.destination.kind==="calculator"&&path.destination.rules_area===undefined);
  if(JSON.stringify(internalPaths)!==JSON.stringify([authority.onboarding.basic_turn.id,authority.onboarding.build_checklist.id].sort(codepointCompare))||referencePaths.length!==1||calculatorPaths.length!==1)diagnostics.push({severity:"error",code:"onboarding.primary_paths",message:"Onboarding primary paths must target Build Checklist, Basic Turn, Calculator / Feature Deck, and the default Rules Reference exactly once",path:"/onboarding/primary_paths"});
  if(collectOnboardingStrings(authority.onboarding).some(value=>/(?:https?:|www\.|mailto:)/iu.test(value)))diagnostics.push({severity:"error",code:"onboarding.external_url",message:"Onboarding must not contain raw external URLs",path:"/onboarding"});
  const rulesAreas=vocabulary(authority,"rules_areas"),entityKinds=vocabulary(authority,"entity_kinds"),roles=vocabulary(authority,"feature_roles"),modes=vocabulary(authority,"acquisition_modes");
  const titleByGroup=new Set<string>();
  for(const [index,entity] of authority.entities.entries()){
    const path=`/entities/${index}`;
    if(entity.kind!==entity.classifications.entity_kind)diagnostics.push({severity:"error",code:"classification.kind_mismatch",message:`${entity.id}: kind and entity_kind differ`,path});
    if(!entityKinds.has(entity.kind))diagnostics.push({severity:"error",code:"classification.kind_unknown",message:`${entity.id}: unknown entity kind ${entity.kind}`,path});
    for(const area of entity.classifications.rules_area)if(!rulesAreas.has(area))diagnostics.push({severity:"error",code:"classification.area_unknown",message:`${entity.id}: unknown rules area ${area}`,path});
    if(entity.kind==="feature"&&(!entity.classifications.feature_role||!roles.has(entity.classifications.feature_role)))diagnostics.push({severity:"error",code:"classification.role",message:`${entity.id}: feature requires a valid feature_role`,path});
    if(entity.level===undefined&&!entity.progression_section)diagnostics.push({severity:"error",code:"progression.section_missing",message:`${entity.id}: an unlevelled entity requires an explicit progression_section`,path});
    if(entity.level!==undefined&&entity.progression_section)diagnostics.push({severity:"error",code:"progression.section_conflict",message:`${entity.id}: a levelled entity must not declare progression_section`,path});
    const inAdvanced=entity.classifications.rules_area.includes("advanced_training");
    if(inAdvanced&&(!entity.classifications.acquisition_mode||!modes.has(entity.classifications.acquisition_mode)))diagnostics.push({severity:"error",code:"classification.acquisition",message:`${entity.id}: Advanced Training feature requires acquisition_mode`,path});
    if(!entity.classifications.rules_area.includes(entity.presentation_metadata.primary_rules_area))diagnostics.push({severity:"error",code:"presentation.primary_area",message:`${entity.id}: primary area is not in rules_area`,path});
    const renderedAreas=new Set<string>();const topicsByArea=new Map<string,string[]>();
    for(const [topicId,ids] of topicEntities)if(ids.has(entity.id)){const area=topicToArea.get(topicId)!;renderedAreas.add(area);const list=topicsByArea.get(area)??[];list.push(topicId);topicsByArea.set(area,list);}
    const authored=[...entity.classifications.rules_area].sort(),rendered=[...renderedAreas].sort(),deckOwned=isCalculatorDeckEntity(entity);
    if(deckOwned&&rendered.length)diagnostics.push({severity:"error",code:"presentation.deck_reference_duplicate",message:`${entity.id}: deck-owned feature must not retain Rules Reference long-form topics`,path});
    if(!deckOwned&&JSON.stringify(authored)!==JSON.stringify(rendered))diagnostics.push({severity:"error",code:"classification.rules_area_redundancy",message:`${entity.id}: authored areas [${authored}] differ from rendered Rules Reference areas [${rendered}]`,path});
    for(const [area,topicIds] of topicsByArea)if(topicIds.length>1){const canonical=entity.presentation_metadata.canonical_topic_by_area[area];if(!canonical||!topicIds.includes(canonical))diagnostics.push({severity:"error",code:"presentation.canonical_topic",message:`${entity.id}: area ${area} needs one valid canonical topic`,path});}
    for(const [area,topicId] of Object.entries(entity.presentation_metadata.canonical_topic_by_area))if(!deckOwned&&!topicsByArea.get(area)?.includes(topicId))diagnostics.push({severity:"error",code:"presentation.canonical_topic_extra",message:`${entity.id}: invalid canonical mapping ${area} -> ${topicId}`,path});
    const titleKey=`${entity.presentation_metadata.primary_rules_area}\0${entity.title}`;if(titleByGroup.has(titleKey))diagnostics.push({severity:"error",code:"presentation.name_duplicate",message:`Duplicate Name label ${entity.title} in ${entity.presentation_metadata.primary_rules_area}`,path});titleByGroup.add(titleKey);
    if(!entity.content.length)diagnostics.push({severity:"error",code:"coverage.empty_entity",message:`${entity.id}: no rule-significant content`,path});
    for(const [blockIndex,block] of entity.content.entries()){
      if(!block.row_references)continue;const referencePath=`${path}/content/${blockIndex}/row_references`;
      if(entity.id!=="subclass_feature_reference")diagnostics.push({severity:"error",code:"reference.scope",message:`${entity.id}: row references are only valid on Subclass Feature Reference`,path:referencePath});
      if(block.type!=="table"||!block.rows){diagnostics.push({severity:"error",code:"reference.block_type",message:`${entity.id}: row references require a table`,path:referencePath});continue;}
      if(block.row_references.length!==block.rows.length)diagnostics.push({severity:"error",code:"reference.row_count",message:`${entity.id}: ${block.row_references.length} row references do not match ${block.rows.length} table rows`,path:referencePath});
      for(const [rowIndex,reference] of block.row_references.entries()){
        const row=block.rows[rowIndex];if(!row)continue;const rowPath=`${referencePath}/${rowIndex}`;
        const displayedLevel=inlineText(row[0]),displayedFeature=inlineText(row[1]);
        if(reference.reference_level!==displayedLevel)diagnostics.push({severity:"error",code:"reference.level_display",message:`${entity.id}: row ${rowIndex+1} metadata level ${reference.reference_level} differs from ${displayedLevel}`,path:rowPath});
        if("entity_id" in reference){const referenced=entities.get(reference.entity_id);
          if(!referenced){diagnostics.push({severity:"error",code:"reference.entity_unknown",message:`${entity.id}: row ${rowIndex+1} references unknown entity ${reference.entity_id}`,path:rowPath});continue;}
          if(referenced.kind!=="feature")diagnostics.push({severity:"error",code:"reference.entity_kind",message:`${entity.id}: row ${rowIndex+1} references non-feature ${reference.entity_id}`,path:rowPath});
          if(referenced.title!==displayedFeature)diagnostics.push({severity:"error",code:"reference.feature_display",message:`${entity.id}: row ${rowIndex+1} label ${displayedFeature} differs from ${referenced.title}`,path:rowPath});
          const referenceLevel=Number(reference.reference_level.match(/^\d+/)?.[0]);if(referenced.level!==referenceLevel)diagnostics.push({severity:"error",code:"reference.entity_level",message:`${entity.id}: row ${rowIndex+1} reference level ${reference.reference_level} differs from ${reference.entity_id} level ${referenced.level}`,path:rowPath});
        }
      }
    }
  }
  const subclassReference=entities.get("subclass_feature_reference");const annotatedTables=subclassReference?.content.filter(block=>block.row_references)??[];
  if(annotatedTables.length!==1)diagnostics.push({severity:"error",code:"reference.table_count",message:"Subclass Feature Reference requires exactly one annotated Psi Cost Reference table"});
  diagnostics.push(...duplicateDiagnostics((authority.audits??[]).map(audit=>audit.id),"audit.duplicate","audit ID"));
  for(const audit of authority.audits??[])for(const subjectId of audit.subject_ids)if(!entities.has(subjectId))diagnostics.push({severity:"error",code:"audit.subject_unknown",message:`${audit.id}: unknown subject ${subjectId}`});
  const authorityAudit=(authority.audits??[]).find(audit=>audit.id==="yaml_rules_authority");const authoredEntityIds=[...entities.keys()].sort(codepointCompare);const auditedEntityIds=[...new Set(authorityAudit?.subject_ids??[])].sort(codepointCompare);if(!authorityAudit||JSON.stringify(auditedEntityIds)!==JSON.stringify(authoredEntityIds))diagnostics.push({severity:"error",code:"authority.coverage",message:"YAML authority audit must cover every publishable entity exactly once"});
  for(const facet of authority.facets){if(!authority.vocabularies[facet.vocabulary])diagnostics.push({severity:"error",code:"facet.vocabulary",message:`Facet ${facet.id} references unknown vocabulary ${facet.vocabulary}`});}
  return diagnostics;
}

export type ProgressionSection="foundation"|"levelled"|"reference";
export interface NameIndexEntry {id:string;title:string;primary_rules_area:string;minimum_level:number|null;progression_section:ProgressionSection;routes:Record<string,string>}
export interface NameIndexGroup {id:string;label:string;order:number;entity_ids:string[]}
export interface NameIndex { entities:NameIndexEntry[];name_groups:NameIndexGroup[] }
const progressionSectionOrder:Record<ProgressionSection,number>={foundation:0,levelled:1,reference:2};
const numericLevel=(entry:NameIndexEntry):number=>entry.minimum_level===null?Number.MAX_SAFE_INTEGER:Number(entry.minimum_level);
export function compareNameEntries(a:NameIndexEntry,b:NameIndexEntry):number{
  return (progressionSectionOrder[a.progression_section]-progressionSectionOrder[b.progression_section])
    ||(numericLevel(a)-numericLevel(b))
    ||codepointCompare(a.title,b.title)
    ||codepointCompare(a.id,b.id);
}
export function buildNameIndex(authority:Authority):NameIndex{
  const routesByEntity=new Map<string,Map<string,string[]>>();for(const category of authority.navigation.categories)for(const topic of category.topics)for(const entityId of topic.entity_ids){const areas=routesByEntity.get(entityId)??new Map();const topics=areas.get(category.id)??[];topics.push(topic.id);areas.set(category.id,topics);routesByEntity.set(entityId,areas);}
  const entries=authority.entities.map(entity=>{const primaryArea=entity.presentation_metadata.primary_rules_area;const areaRoutes=routesByEntity.get(entity.id)??new Map<string,string[]>();const routes=Object.fromEntries([...areaRoutes].map(([area,topics])=>[area,entity.presentation_metadata.canonical_topic_by_area[area]??topics[0]! ]));return{id:entity.id,title:entity.title,primary_rules_area:primaryArea,minimum_level:entity.level??null,progression_section:(entity.level===undefined?entity.progression_section!:"levelled") as ProgressionSection,routes};});
  const name_groups=(authority.vocabularies.rules_areas??[]).map(area=>({id:area.id,label:area.label,order:area.order,entity_ids:entries.filter(entry=>entry.primary_rules_area===area.id).sort(compareNameEntries).map(entry=>entry.id)})).sort((a,b)=>a.order-b.order||codepointCompare(a.id,b.id));
  return{entities:entries,name_groups};
}

export function buildNameIndexIntegrity(authority:Authority,index:NameIndex):Record<string,unknown>{
  const checks=index.entities.map(item=>{const entity=authority.entities.find(candidate=>candidate.id===item.id)!;const expectedRouteAreas=isCalculatorDeckEntity(entity)?[]:[...entity.classifications.rules_area].sort();return{entity_id:item.id,identity_retrieval:item.title===entity.title,canonical_area_retrieval:item.primary_rules_area===entity.presentation_metadata.primary_rules_area,route_areas:Object.keys(item.routes).sort(),expected_route_areas:expectedRouteAreas};});
  return{version:1,entity_count:index.entities.length,all_passed:checks.every(check=>check.identity_retrieval&&check.canonical_area_retrieval&&JSON.stringify(check.route_areas)===JSON.stringify(check.expected_route_areas)),identity_domain:index.entities.map(entity=>({id:entity.id,title:entity.title,primary_rules_area:entity.primary_rules_area})),checks};
}

export function summarizeDiagnostics(diagnostics:Diagnostic[]):string{return diagnostics.map(item=>`${item.severity.toUpperCase()} ${item.code}${item.path?` ${item.path}`:""}: ${item.message}`).join("\n");}

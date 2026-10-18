import assert from "node:assert/strict";
import test from "node:test";
import {loadAuthority} from "../src/load.js";
import {deriveCalculatorProjection} from "../src/mechanics-selectors.js";
import {validateSemantics} from "../src/validate.js";

test("approved v14.4 resolution rules reach both consumer projections",async()=>{
  const {authority}=await loadAuthority(),projection=deriveCalculatorProjection(authority);
  const examples=JSON.stringify(authority.entities.find(entity=>entity.id==="example_play")??authority.entities.filter(entity=>JSON.stringify(entity).includes("example_play_section")));
  assert.match(examples,/9 \+ \(6 × 5\) = 39 damage/);assert.match(examples,/21 \+ 34 \+ 39 = 94 lightning damage/);assert.doesNotMatch(examples,/91 lightning damage/);
  assert.deepEqual(projection.harness_mechanics.action_economy,{standalone_psionic_action_limit_per_turn:null,action_surge_allows_additional_standalone_psionic_action:true});
  assert.equal(projection.harness_mechanics.overload.tier_two_damage_ignores_resistance,true);
  const burst=projection.features.find(feature=>feature.entity_id==="electron_burst")!;
  assert.deepEqual(burst.tiers!.map(tier=>tier.damage),[1,2,3].map(count=>({kind:"dice",resolution:"half_on_success",count,sides:8})));
  assert.ok(burst.tiers!.every(tier=>tier.secondary_damage===undefined&&tier.save==="charisma"));
  const discharge=projection.harness_mechanics.feature_rules.find(rule=>rule.entity_id==="static_discharge")!;
  assert.deepEqual(discharge.targeting_by_tier,[1,3,5].map((additional_targets,tier)=>({tier,kind:"fixed_additional",additional_targets})));
  for(const entity of authority.entities){
    const rule=projection.harness_mechanics.feature_rules.find(rule=>rule.entity_id===entity.id);
    if(!rule)continue;
    const tier2=entity.mechanics!.surfaces.flatMap(surface=>surface.tiers??[]).filter(tier=>tier.tier===2);
    if(JSON.stringify(tier2).includes('"kind":"damage"'))assert.deepEqual(rule.ignore_resistance_tiers,[2],entity.id);
  }
  assert.doesNotMatch(JSON.stringify(authority.entities),/"ignores_resistance"/);
  for(const [id,failure,success] of [["telekinetic_slam",30,10],["advanced_deflection_screen",15,5]] as const){
    const rule=projection.harness_mechanics.feature_rules.find(rule=>rule.entity_id===id)!;
    const control=rule.control_tiers!.find(tier=>tier.tier===2)!;
    assert.equal(control.save,"strength");
    assert.deepEqual(control.effects.find(effect=>effect.gate==="partial_on_success"),{gate:"partial_on_success",outcomes:["forced_movement"],duration:"instantaneous",failed_save_magnitude_feet:failure,successful_save_magnitude_feet:success});
  }
});

test("partial-on-success movement cannot lose either save branch or its saving throw",async()=>{
  const {authority}=await loadAuthority();
  for(const mutation of ["missing_success","missing_resolution","outside_save","larger_success"]){
    const candidate=structuredClone(authority),tier=candidate.entities.find(entity=>entity.id==="telekinetic_slam")!.mechanics!.surfaces[0]!.tiers![2]!;
    const save=tier.steps!.find(step=>step.kind==="saving_throw")!;
    assert.equal(save.kind,"saving_throw");if(save.kind!=="saving_throw")throw new Error("missing save");
    const movement=save.failure.find(step=>step.kind==="forced_movement")!;
    if(movement.kind!=="forced_movement")throw new Error("missing movement");
    if(mutation==="missing_success")delete movement.success_feet;
    if(mutation==="missing_resolution")delete movement.resolution;
    if(mutation==="larger_success")movement.success_feet=40;
    if(mutation==="outside_save"){save.failure=save.failure.filter(step=>step!==movement);tier.steps!.unshift(movement);}
    assert.ok(validateSemantics(candidate).some(diagnostic=>diagnostic.code==="mechanics.partial_on_success"),mutation);
  }
});

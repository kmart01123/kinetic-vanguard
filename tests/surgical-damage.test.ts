import assert from "node:assert/strict";
import test from "node:test";
import {loadAuthority} from "../src/load.js";
import {deriveCalculatorProjection} from "../src/mechanics-selectors.js";
import {createHarnessProjection} from "../src/harness-authority.js";
import {validateSemantics} from "../src/validate.js";

test("surgical damage formulas and allocation choices reach both consumers from canonical mechanics",async()=>{
  const {authority}=await loadAuthority(),calculator=deriveCalculatorProjection(authority),harness=await createHarnessProjection();
  assert.equal(authority.rules_version,"15.0.0");assert.equal(authority.schema_version,"2.15.0");
  for(const id of ["absolute_zero","telekinetic_shove","branching_bolt"]){
    const tiers=calculator.features.find(feature=>feature.entity_id===id)!.tiers!;
    assert.deepEqual(harness.features.find(feature=>feature.entity_id===id)!.damage_tiers,tiers);
    for(const tier of tiers){
      if(id==="absolute_zero")assert.deepEqual(tier.damage,{kind:"dice_plus_fixed",count:6,sides:10,fixed:45+tier.tier*10,resolution:"half_on_success"});
      if(id==="telekinetic_shove")assert.deepEqual(tier.damage,{kind:"fixed_by_level",value:2,minimum_level:18,upgraded_value:4,resolution:"always"});
      if(id==="branching_bolt"){
        assert.deepEqual(tier.damage,{kind:"manifested_strike_dice",count:1,resolution:"always"});
        assert.equal(tier.damage_options,undefined);
        assert.deepEqual(tier.damage_allocation,{kind:"exchange_targets_for_dice",minimum_dice_per_target:1,minimum_targets:3,secondary_target_eligibility:"hostile",packet:"per_target",dice_budget:tier.tier+3,maximum_targets:tier.tier+3});
      }
    }
  }
});

test("damage options fail closed when declaration, targeting, level, or inherited effects are incompatible",async()=>{
  const {authority}=await loadAuthority();
  for(const mutate of [
    (surface:any)=>surface.damage_options.push(structuredClone(surface.damage_options[0])),
    (surface:any)=>surface.damage_options[0].minimum_level=3,
    (surface:any)=>surface.damage_options[0].targeting={kind:"area",topology:"area"},
    (surface:any)=>surface.delivery={kind:"standalone",activation:"action"},
    (surface:any)=>surface.tiers[0].steps.push({kind:"speed_zero",duration:"until_end_next_turn"})
  ]){
    const candidate=structuredClone(authority),surface=candidate.entities.find(entity=>entity.id==="branching_bolt")!.mechanics!.surfaces[0]!;
    delete surface.damage_allocation;surface.damage_options=[{id:"focused",label:"Focused Bolt",minimum_level:18,targeting:{kind:"struck_target",topology:"single"},value:{kind:"manifested_strike_dice",count:2}}];mutate(surface);
    assert.ok(validateSemantics(candidate).some(diagnostic=>diagnostic.code.startsWith("mechanics.damage_option")));
  }
});

test("allocation surfaces reject ambiguous timing, packet splits, and impossible minimum targets",async()=>{
  const {authority}=await loadAuthority();
  for(const mutate of [
    (s:any)=>s.delivery.declaration="after_attack_roll",
    (s:any)=>s.delivery.resolution="always",
    (s:any)=>s.tiers[0].steps[0].value.count=2,
    (s:any)=>s.tiers[0].steps[0].target="secondary",
    (s:any)=>s.tiers[0].steps.push({kind:"speed_zero",duration:"until_end_next_turn"}),
    (s:any)=>s.tiers[0].targeting.additional_count={kind:"proficiency_bonus"},
    (s:any)=>s.tiers[2].targeting.additional_count.value=5,
    (s:any)=>s.damage_allocation.minimum_targets=4,
    (s:any)=>s.damage_allocation.secondary_target_eligibility="any_creature",
    (s:any)=>delete s.damage_allocation.secondary_target_eligibility
  ]){
    const candidate=structuredClone(authority);mutate(candidate.entities.find(entity=>entity.id==="branching_bolt")!.mechanics!.surfaces[0]);
    assert.ok(validateSemantics(candidate).some(d=>d.code==="mechanics.damage_allocation_surface"));
  }
});

import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import test from "node:test";
import {mkdtemp,readFile,rm,writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {stringify} from "yaml";
import {createControlAuthorityProjectionV2,createDamageHarnessProjection} from "../src/harness-authority.js";
import {loadAuthority} from "../src/load.js";
import {validateSemantics} from "../src/validate.js";

test("damage projection remains v1 while reading the current 3.1 authority",async()=>{
  const projection=await createDamageHarnessProjection();
  assert.equal(projection.projection_version,"1.0.0");assert.equal(projection.rules_version,"14.2.0");assert.equal(projection.schema_version,"3.1.0");assert.match(projection.authority_path,/\/KineticVanguard\.yaml$/);
  assert.deepEqual(projection.core.action_economy,{standalone_psionic_action_limit_per_turn:1,action_surge_allows_additional_standalone_psionic_action:false});
  assert.equal(new Set(projection.features.map(item=>item.entity_id)).size,projection.features.length);
  assert.ok(projection.features.every(item=>Number.isInteger(item.minimum_level)&&Number.isInteger(item.psi_cost)&&!Object.hasOwn(item,"title")));
  const serialized=JSON.stringify(projection);for(const retired of ["control_tiers","control_outcomes","damage_required"])assert.equal(serialized.includes(`"${retired}"`),false,retired);
});

test("control projection 2.1 is complete, deterministic, and metadata-derived",async()=>{
  const [first,second]=await Promise.all([createControlAuthorityProjectionV2(),createControlAuthorityProjectionV2()]);
  assert.deepEqual(first,second);assert.equal(first.projection_version,"2.1.0");assert.equal(first.schema_version,"3.1.0");assert.equal(first.rules_version,"14.2.0");
  assert.equal(first.control_authority.contract_version,"2.1.0");assert.deepEqual(first.coverage,{total:49,modeled:35,excluded_by_profile:14,unsupported_error:0,benchmark_ready:true});
  const keys=first.control_authority.ledger.map(item=>`${item.entity_id}:T${item.tier}`);assert.equal(keys.length,49);assert.deepEqual(keys,[...keys].sort());
  assert.equal(first.control_authority.ledger.filter(item=>item.disposition==="modeled").length,35);assert.equal(first.control_authority.ledger.filter(item=>item.disposition==="excluded_by_profile").length,14);
  const canonicalIds=first.canonical_inputs.entities.map(item=>item.entity_id),modeledIds=[...new Set(first.control_authority.ledger.filter(item=>item.disposition==="modeled").map(item=>item.entity_id))].sort();
  assert.deepEqual(canonicalIds,modeledIds);
  const forkedInput=first.canonical_inputs.entities.find(item=>item.entity_id==="forked_lightning")!;assert.equal(forkedInput.feature_rule_repeatability,"once_per_attack_action");
  const forked=first.control_authority.ledger.find(item=>item.entity_id==="forked_lightning"&&item.tier===2);assert.ok(forked?.disposition==="modeled");assert.equal(forked.model.policy.repeatability,"once_per_turn");
});

test("control fixtures preserve typed placement, movement, saves, ordering, and active-state guards",async()=>{
  const {control_authority}=await createControlAuthorityProjectionV2();
  const modeled=(entityId:string,tier:0|1|2)=>{const row=control_authority.ledger.find(item=>item.entity_id===entityId&&item.tier===tier);assert.ok(row&&row.disposition==="modeled",`${entityId}:T${tier}`);return row.model;};
  const component=(model:ReturnType<typeof modeled>,id:string)=>{const found=model.components.find(item=>item.component_id===id);assert.ok(found,id);return found;};
  const glacial=modeled("glacial_spike",1);assert.deepEqual(component(glacial,"glacial_spike_speed_reduction").cadence,{apply:[{kind:"hit"}],repeat:[],end:[{kind:"turn",owner:"controller",turn_anchor:"end"}]});
  const masteryPush=control_authority.masteries.find(item=>item.mastery_id==="mastery_push")!;assert.deepEqual(masteryPush.component.magnitude,{kind:"forced_movement",distance_feet:10,distance_mode:"up_to",movement_mode:"push",reference_point:"controller",axis:"any",direction:"away_from_reference",destination:{selection:"rule_determined",visibility:"not_required",occupancy:"unoccupied_required"},path:{line:"straight",blocked:"nearest_unoccupied_along_path"},resolution_order:"independent"});
  const ball=modeled("ball_lightning",2),ballArea=ball.target_selectors.find(item=>item.area)?.area;assert.ok(ballArea?.persistent);assert.deepEqual(ballArea.placement,{kind:"selected_point",range:{feet:60,origin:"controller"},stationary:false});assert.deepEqual(ballArea.movement,{kind:"controller_reposition",controller_action:"bonus_action",timing:{kind:"turn",owner:"controller",turn_anchor:"during"},distance_feet:15,distance_mode:"up_to"});
  assert.deepEqual(ball.concentration,{kind:"required",startup:"on_activation",occupancy:"one_controller_slot",replacement:"new_effect_ends_existing",maximum_duration:{value:1,unit:"minute"},termination:["failed_concentration_save","controller_incapacitated","controller_death","duration_expires","voluntary_end"]});
  const phase=modeled("advanced_phase_step",2),phaseArea=phase.target_selectors.find(item=>item.area)?.area;assert.ok(phaseArea);assert.deepEqual(phaseArea.placement,{kind:"endpoint_choice",choice_id:"advanced_phase_step_endpoint_choice",departure:{origin:"controller_current_space"},arrival:{range:{feet:30,origin:"departure_space"},visibility:"required",occupancy:"unoccupied_required"}});
  const staticModel=modeled("static_discharge",2),secondary=staticModel.target_selectors.find(item=>item.role==="secondary")!;assert.deepEqual(secondary.count,{kind:"up_to_proficiency_bonus"});
  const damageContext=staticModel.resolutions.find(gate=>gate.resolution.kind==="damage_context");assert.ok(damageContext);assert.deepEqual(damageContext.trigger,{kind:"damage_context"});assert.deepEqual(damageContext.resolution.branches.map(branch=>branch.outcome),["damage_context"]);
  for(const tier of [0,1,2] as const){const mass=modeled("mass_levitation",tier),guards=mass.resolutions.filter(gate=>gate.requires_active_component_ids);assert.ok(guards.length);assert.ok(guards.every(gate=>gate.requires_active_component_ids?.join()==="mass_levitation_persistent_elevation"));assert.deepEqual(mass.root_gate_ids,[`mass_levitation_t${tier}_initial_saves`]);}
  assert.deepEqual(control_authority.ledger.find(item=>item.entity_id==="advanced_beguile"&&item.tier===0),{entity_id:"advanced_beguile",tier:0,disposition:"excluded_by_profile",profile_id:"official_default_25_percent_hp",reason:"selectable_advanced_training_disabled"});
});

test("Wisdom saving throws remain schema- and semantic-valid",async()=>{
  const {authority}=await loadAuthority(),candidate=structuredClone(authority) as any;
  const forked=candidate.calculator.harness_mechanics.control_authority_v2.ledger.find((row:any)=>row.disposition==="modeled"&&row.model.effect_id==="forked_lightning_t2_control");forked.model.resolutions.find((gate:any)=>gate.resolution.kind==="saving_throw").resolution.ability="wisdom";
  const directory=await mkdtemp(join(tmpdir(),"kv-wisdom-authority-")),authorityPath=join(directory,"authority.yaml");
  try{await writeFile(authorityPath,stringify(candidate),"utf8");const loaded=await loadAuthority(authorityPath);assert.deepEqual(loaded.diagnostics,[]);assert.deepEqual(validateSemantics(loaded.authority).filter(item=>item.severity==="error"),[]);}finally{await rm(directory,{recursive:true,force:true});}
});
test("triggering-turn expiry events are schema-closed to the end anchor",async()=>{
  const {authority}=await loadAuthority(),candidate=structuredClone(authority) as any,contract=candidate.calculator.harness_mechanics.control_authority_v2;
  const frozen=contract.ledger.find((row:any)=>row.disposition==="modeled"&&row.model.effect_id==="frozen_ground_t0_control").model,speed=frozen.components.find((component:any)=>component.component_id==="frozen_ground_speed_zero"),expiry=speed.cadence.end.find((event:any)=>event.owner==="triggering_turn");assert.ok(expiry);expiry.turn_anchor="start";
  const directory=await mkdtemp(join(tmpdir(),"kv-triggering-turn-schema-")),authorityPath=join(directory,"authority.yaml");
  try{await writeFile(authorityPath,stringify(candidate),"utf8");const loaded=await loadAuthority(authorityPath);assert.ok(loaded.diagnostics.some(item=>item.code==="schema.invalid"),loaded.diagnostics.map(item=>item.message).join("; "));}finally{await rm(directory,{recursive:true,force:true});}
});


test("projection CLI selects 2.1 explicitly and rejects unknown versions",()=>{
  const executable="node_modules/.bin/tsx",base=["src/harness-authority.ts"];
  const damage=spawnSync(executable,base,{encoding:"utf8"});assert.equal(damage.status,0,damage.stderr);assert.equal(JSON.parse(damage.stdout).projection_version,"1.0.0");
  const control=spawnSync(executable,[...base,"--projection-version","2.1.0"],{encoding:"utf8"});assert.equal(control.status,0,control.stderr);assert.equal(JSON.parse(control.stdout).projection_version,"2.1.0");
  const unknown=spawnSync(executable,[...base,"--projection-version","2.0.0"],{encoding:"utf8"});assert.notEqual(unknown.status,0);assert.match(unknown.stderr,/Unsupported projection version: 2\.0\.0/);
});

test("damage authority semantic mutations fail with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  expectCode("damage_authority.action_economy",candidate=>{candidate.calculator.harness_mechanics.action_economy.action_surge_allows_additional_standalone_psionic_action=true;});
  expectCode("damage_authority.attack_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.attack_bonus.base=1;});
  expectCode("damage_authority.save_dc_formula",candidate=>{candidate.calculator.harness_mechanics.manifested_strike.save_dc.components.reverse();});
  expectCode("damage_authority.blood_tax_formula",candidate=>{candidate.calculator.harness_mechanics.overload.blood_tax_per_tier.proficiency_bonus_multiplier=2;});
  expectCode("damage_authority.discipline_duplicate",candidate=>{candidate.calculator.harness_mechanics.disciplines[1].id=candidate.calculator.harness_mechanics.disciplines[0].id;});
  expectCode("damage_authority.graze_damage",candidate=>{delete candidate.calculator.harness_mechanics.disciplines.find((item:any)=>item.id==="pyrokinesis").graze_damage;});
  expectCode("damage_authority.feature_duplicate",candidate=>{candidate.calculator.harness_mechanics.feature_rules[1].entity_id=candidate.calculator.harness_mechanics.feature_rules[0].entity_id;});
  expectCode("damage_authority.feature_coverage",candidate=>{candidate.calculator.harness_mechanics.feature_rules=candidate.calculator.harness_mechanics.feature_rules.filter((item:any)=>item.entity_id!=="flare");});
  expectCode("damage_authority.feature_unknown",candidate=>{candidate.calculator.harness_mechanics.feature_rules[0].entity_id="missing_feature";});
  expectCode("damage_authority.targeting_tier_duplicate",candidate=>{candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="branching_bolt").targeting_by_tier[1].tier=0;});
  expectCode("damage_authority.targeting_count",candidate=>{delete candidate.calculator.harness_mechanics.feature_rules.find((item:any)=>item.entity_id==="branching_bolt").targeting_by_tier[0].additional_targets;});
});

test("control 2.1 semantic mutations fail closed with focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const contract=(candidate:any)=>candidate.calculator.harness_mechanics.control_authority_v2;
  const model=(candidate:any,effectId:string)=>contract(candidate).ledger.find((row:any)=>row.disposition==="modeled"&&row.model.effect_id===effectId).model;
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),`${code}: ${diagnostics.map(item=>item.code).join(", ")}`);};
  expectCode("control_v2.version",candidate=>{contract(candidate).contract_version="2.0.0";});
  expectCode("control_v2.target",candidate=>{model(candidate,"static_discharge_t2_control").target_selectors.find((selector:any)=>selector.role==="secondary").count.kind="proficiency_bonus";});
  expectCode("control_v2.graph",candidate=>{delete model(candidate,"mass_levitation_t2_control").resolutions.find((gate:any)=>gate.requires_active_component_ids).requires_active_component_ids;});
  expectCode("control_v2.magnitude",candidate=>{delete contract(candidate).masteries.find((mastery:any)=>mastery.mastery_id==="mastery_push").component.magnitude.path;});
  expectCode("control_v2.area",candidate=>{delete model(candidate,"advanced_phase_step_t2_control").target_selectors.find((selector:any)=>selector.area).area.placement.arrival.occupancy;});
  expectCode("control_v2.branch",candidate=>{model(candidate,"frozen_ground_t0_control").resolutions.find((gate:any)=>gate.resolution.kind==="saving_throw").resolution.role="initial";});
  expectCode("control_v2.branch",candidate=>{model(candidate,"static_discharge_t2_control").resolutions.find((gate:any)=>gate.resolution.kind==="damage_context").resolution.branches[0].outcome="other";});
  expectCode("control_v2.choice",candidate=>{model(candidate,"explosion_implosion_t0_control").choices[0].options.pop();});
  expectCode("control_v2.concentration",candidate=>{model(candidate,"frozen_ground_t0_control").concentration={kind:"none"};});
  expectCode("control_v2.timing",candidate=>{model(candidate,"frozen_ground_t0_control").components.find((component:any)=>component.component_id==="frozen_ground_speed_zero").duration.owner="target";});
  expectCode("control_v2.timing",candidate=>{model(candidate,"frozen_ground_t0_control").components.find((component:any)=>component.component_id==="frozen_ground_speed_zero").duration.anchor="start_turn";});
  expectCode("control_v2.timing",candidate=>{const speed=model(candidate,"frozen_ground_t0_control").components.find((component:any)=>component.component_id==="frozen_ground_speed_zero");speed.cadence.end[0].owner="target";});
  expectCode("control_v2.timing",candidate=>{const speed=model(candidate,"frozen_ground_t0_control").components.find((component:any)=>component.component_id==="frozen_ground_speed_zero");speed.cadence.end[0].turn_anchor="start";});
  expectCode("control_v2.timing",candidate=>{model(candidate,"forked_lightning_t2_control").policy.repeatability="once_per_attack_action";});
  expectCode("control_v2.coverage",candidate=>{contract(candidate).ledger.pop();});
  expectCode("control_v2.disposition",candidate=>{contract(candidate).ledger.find((row:any)=>row.disposition==="excluded_by_profile").profile_id="wrong_profile";});
});

test("official harness sources and shared parity inputs are declared positive inputs",async()=>{
  const inputs=JSON.parse(await readFile("build/inputs.json","utf8")).inputs as Array<{path:string;role:string}>,paths=inputs.map(input=>input.path);
  for(const required of [
    "src/harness-authority.ts","src/creature-catalog.ts","harness/authority.py","harness/creature_catalog.py",
    "harness/damage_harness.py","harness/damage_report.py","harness/readme_damage.py",
    "harness/config/benchmark.json","harness/config/creature-consumers.json","harness/comparators/fighter-subclasses.json",
    "harness/data/srd_creatures.json","harness/data/srd_creature_rosters.json",
    "harness/provenance/damage-review.json","harness/provenance/damage-delta-v14.1-to-v14.2.json","harness/provenance/srd-creatures.json",
    "harness/tests/test_authority_v2.py","harness/tests/test_authority_v2_parity.py",
    "harness/tests/test_creature_catalog.py","harness/tests/test_creature_rosters.py","harness/tests/test_target_projections.py","harness/tests/test_harness.py","harness/tests/test_readme_damage.py",
    "tests/harness-authority.test.ts","tests/control-authority-v2-parity.test.ts",
    "tests/creature-catalog.test.ts","tests/fixtures/control-authority-v2-parity.json",
  ])assert.ok(paths.includes(required),required);
  for(const retired of ["harness/control_harness.py","harness/readme_matrices.py","harness/comparison_report.py","harness/provenance/legacy-import.json","harness/control_targets.py","src/control-targets.ts","harness/data/srd_targets.csv","harness/data/srd_control_targets.json","harness/provenance/srd-control-targets.json"])assert.equal(paths.includes(retired),false,retired);
  assert.ok(paths.every(path=>!path.startsWith(".codex-import/")&&!path.endsWith(".zip")&&!path.includes("harness/results")));
  const [ignore,workflow,packageJson]=await Promise.all([readFile(".gitignore","utf8"),readFile(".github/workflows/ci.yml","utf8"),readFile("package.json","utf8")]);assert.match(ignore,/^\.codex-import\/$/m);assert.match(ignore,/^harness\/results\/$/m);assert.match(workflow,/npm run test:harness/);assert.match(workflow,/npm run harness:validate/);assert.match(packageJson,/"test:harness"/);
});

test("minimal comparator parameters remain isolated from canonical KV mechanics",async()=>{
  const [{authority},yamlSource,configSource,comparatorSource]=await Promise.all([loadAuthority(),readFile("KineticVanguard.yaml","utf8"),readFile("harness/config/benchmark.json","utf8"),readFile("harness/comparators/fighter-subclasses.json","utf8")]);
  const pattern=/battle.?master|eldritch.?knight|hunter.?ranger|open.?hand.?monk/i;assert.doesNotMatch(JSON.stringify(authority),pattern);assert.doesNotMatch(yamlSource,pattern);assert.doesNotMatch(configSource,pattern);assert.match(comparatorSource,/battle_master/);assert.match(comparatorSource,/eldritch_knight/);
  const comparators=JSON.parse(comparatorSource);assert.deepEqual(comparators.primary_comparator_ids,["battle_master","eldritch_knight"]);assert.equal(Object.hasOwn(comparators,"control"),false);
});

import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

const ownedOnboardingIds=(value:any,result:string[]=[]):string[]=>{if(Array.isArray(value)){value.forEach(item=>ownedOnboardingIds(item,result));return result;}if(!value||typeof value!=="object")return result;for(const [key,child] of Object.entries(value)){if(key==="id"&&typeof child==="string")result.push(child);else ownedOnboardingIds(child,result);}return result;};
const onboardingDestinations=(value:any,result:any[]=[]):any[]=>{if(Array.isArray(value)){value.forEach(item=>onboardingDestinations(item,result));return result;}if(!value||typeof value!=="object")return result;if(typeof value.kind==="string"&&(value.kind==="calculator"||typeof value.section_id==="string"||typeof value.category_id==="string"||typeof value.entity_id==="string"))result.push(value);for(const child of Object.values(value))onboardingDestinations(child,result);return result;};
const onboardingStrings=(value:any,result:string[]=[]):string[]=>{if(typeof value==="string"){result.push(value);return result;}if(Array.isArray(value)){value.forEach(item=>onboardingStrings(item,result));return result;}if(value&&typeof value==="object")Object.values(value).forEach(item=>onboardingStrings(item,result));return result;};

test("YAML authority is schema-valid, semantically valid, and complete",async()=>{
  const loaded=await loadAuthority();
  assert.deepEqual([...loaded.diagnostics,...validateSemantics(loaded.authority)],[]);
  const audit=loaded.authority.audits?.find(item=>item.id==="yaml_rules_authority")!;
  assert.deepEqual([...audit.subject_ids].sort(),loaded.authority.entities.map(entity=>entity.id).sort());
});

test("rider repeatability is one fail-closed Manifested Strike contract",async()=>{
  const {authority}=await loadAuthority();
  assert.equal(authority.calculator.harness_mechanics.manifested_strike.rider_repeatability,"per_manifested_strike");
  assert.ok(authority.calculator.harness_mechanics.feature_rules.every(rule=>!Object.hasOwn(rule,"repeatability")));
  const source=await readFile("KineticVanguard.yaml","utf8"),directory=await mkdtemp(join(tmpdir(),"kv-repeatability-")),path=join(directory,"KineticVanguard.yaml");
  try{
    await writeFile(path,source.replace("rider_repeatability: per_manifested_strike","rider_repeatability: unsupported_value"));
    const invalid=await loadAuthority(path);
    assert.ok(invalid.diagnostics.some(item=>item.code==="schema.invalid"&&item.path?.includes("rider_repeatability")));
  }finally{await rm(directory,{recursive:true,force:true});}
});

test("onboarding IDs are unique and destinations resolve without external leakage",async()=>{
  const {authority}=await loadAuthority();const onboarding=authority.onboarding;
  const ids=ownedOnboardingIds(onboarding);assert.equal(new Set(ids).size,ids.length);
  const entityIds=new Set(authority.entities.map(entity=>entity.id));assert.ok(ids.every(id=>!entityIds.has(id)));assert.ok(!entityIds.has(onboarding.id));
  const auditedIds=new Set(authority.audits?.flatMap(audit=>audit.subject_ids)??[]);assert.ok(ids.every(id=>!auditedIds.has(id)));
  const categories=new Map(authority.navigation.categories.map(category=>[category.id,category]));
  const sectionIds=new Set([onboarding.disciplines.id,onboarding.basic_turn.id,onboarding.build_checklist.id,onboarding.glossary.id,onboarding.next_destinations.id]);
  for(const destination of onboardingDestinations(onboarding)){
    if(destination.kind==="calculator"){assert.ok(destination.rules_area===undefined||authority.vocabularies.rules_areas!.some(area=>area.id===destination.rules_area));continue;}
    if(destination.kind==="onboarding_section"){assert.ok(sectionIds.has(destination.section_id),destination.section_id);continue;}
    if(destination.kind==="category"){const category=categories.get(destination.category_id);assert.ok(category,destination.category_id);assert.ok(category!.topics.some(topic=>topic.id===category!.default_topic_id));continue;}
    const entity=authority.entities.find(candidate=>candidate.id===destination.entity_id);assert.ok(entity,destination.entity_id);assert.equal(entity!.publishable,true);
  }
  assert.doesNotMatch(onboardingStrings(onboarding).join("\n"),/(?:https?:|www\.|mailto:)/iu);
});

test("onboarding semantic mutations produce focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),code+": "+diagnostics.map(item=>item.code).join(", "));};
  expectCode("onboarding.id_duplicate",candidate=>{candidate.onboarding.primary_paths[1].id=candidate.onboarding.primary_paths[0].id;});
  expectCode("onboarding.section_unknown",candidate=>{candidate.onboarding.primary_paths[0].destination.section_id="missing_section";});
  expectCode("onboarding.category_unknown",candidate=>{candidate.onboarding.next_destinations.items.at(-1).destination.category_id="missing_category";});
  expectCode("onboarding.calculator_card_area_mismatch",candidate=>{candidate.onboarding.blood_tax.destination.rules_area="pyrokinesis";});
  expectCode("onboarding.entity_unknown",candidate=>{candidate.onboarding.build_checklist.items[0].destination.entity_id="missing_entity";});
  expectCode("onboarding.external_url",candidate=>{candidate.onboarding.introduction.orientation="Read https://example.invalid for more rules.";});
});

test("prototype and release builds reflect direct YAML edits",async()=>{
  const temporary=await mkdtemp(join(tmpdir(),"kv-yaml-authority-"));const authorityPath=join(temporary,"KineticVanguard.edited.yaml");const source=await readFile("KineticVanguard.yaml","utf8");const edited=source.replace("title: Kinetic Vanguard","title: Kinetic Vanguard YAML Edit Probe");assert.notEqual(edited,source);await writeFile(authorityPath,edited);
  const previousApproval=process.env.KV_RELEASE_APPROVED;
  try{
    const prototypeRoot=join(temporary,"prototype"),releaseRoot=join(temporary,"release");
    const prototype=await executeBuild("prototype",prototypeRoot,authorityPath);process.env.KV_RELEASE_APPROVED="1";const release=await executeBuild("release",releaseRoot,authorityPath);
    const prototypeHtml=await readFile(prototype.htmlPath,"utf8"),releaseHtml=await readFile(release.htmlPath,"utf8");assert.match(prototypeHtml,/NON-RELEASE PROTOTYPE/);assert.doesNotMatch(releaseHtml,/NON-RELEASE PROTOTYPE/);
    for(const result of [prototype,release]){const html=await readFile(result.htmlPath,"utf8");assert.match(html,/Kinetic Vanguard YAML Edit Probe/);assert.doesNotMatch(html,/application_version/);}
  }finally{if(previousApproval===undefined)delete process.env.KV_RELEASE_APPROVED;else process.env.KV_RELEASE_APPROVED=previousApproval;await rm(temporary,{recursive:true,force:true});}
});

test("calculator ownership and rider coverage derive from canonical entities",async()=>{
  const {authority}=await loadAuthority();const entityById=new Map(authority.entities.map(entity=>[entity.id,entity]));
  const registered=authority.calculator.features;assert.equal(new Set(registered.map(feature=>feature.entity_id)).size,registered.length);
  const deckOwned=authority.entities.filter(entity=>entity.presentation_metadata.presentation_owner==="calculator_deck"||(entity.kind==="feature"&&entity.presentation_metadata.primary_rules_area!=="common_features"));
  for(const feature of registered){const entity=entityById.get(feature.entity_id);assert.ok(entity&&deckOwned.includes(entity),feature.entity_id);}
  for(const card of authority.calculator.utility_cards)assert.ok(entityById.has(card.source_entity_id),card.id);
  const authoredRiders=deckOwned.filter(entity=>entity.activation==="on_hit"&&entity.classifications.feature_role==="rider").map(entity=>entity.id).sort();
  const registeredRiders=registered.filter(feature=>feature.delivery==="on_hit_rider").map(feature=>feature.entity_id).sort();assert.deepEqual(registeredRiders,authoredRiders);
  const missing=structuredClone(authority);missing.calculator.features=missing.calculator.features.filter(feature=>feature.entity_id!==registeredRiders[0]);assert.ok(validateSemantics(missing).some(diagnostic=>diagnostic.code==="calculator.rider_coverage"));
  const unknownDefault=structuredClone(authority);unknownDefault.calculator.default_card_id="missing_calculator_card";assert.ok(validateSemantics(unknownDefault).some(diagnostic=>diagnostic.code==="calculator.default_card_unknown"));
});

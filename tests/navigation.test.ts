import assert from "node:assert/strict";
import test from "node:test";
import { loadAuthority } from "../src/load.js";
import {
  buildNameIndex,
  buildNameIndexIntegrity,
  compareNameEntries,
  isCalculatorDeckEntity,
  type NameIndexEntry,
} from "../src/validate.js";

const sortable=(title:string,minimum_level:number|null,progression_section:NameIndexEntry["progression_section"],id=title.toLowerCase().replaceAll(" ","_")):NameIndexEntry=>({id,title,primary_rules_area:"psychokinesis",minimum_level,progression_section,routes:{psychokinesis:"topic"}});

test("Name-navigation integrity covers every canonical identity and route",async()=>{
  const {authority}=await loadAuthority(),index=buildNameIndex(authority),report=buildNameIndexIntegrity(authority,index);
  assert.equal(report.all_passed,true);assert.equal(index.entities.length,authority.entities.length);
  assert.deepEqual(new Set(index.entities.map(entry=>entry.id)),new Set(authority.entities.map(entity=>entity.id)));
});

test("onboarding does not enter the authority-derived Name index",async()=>{
  const {authority}=await loadAuthority(),index=buildNameIndex(authority),withoutOnboarding=structuredClone(authority) as any;delete withoutOnboarding.onboarding;const baseline=buildNameIndex(withoutOnboarding);
  assert.deepEqual(index,baseline);const ownedIds:string[]=[];const collect=(value:any):void=>{if(Array.isArray(value)){value.forEach(collect);return;}if(!value||typeof value!=="object")return;for(const [key,child] of Object.entries(value)){if(key==="id"&&typeof child==="string")ownedIds.push(child);else collect(child);}};collect(authority.onboarding);
  const indexedIds=new Set(index.entities.map(item=>item.id));assert.ok(ownedIds.every(id=>!indexedIds.has(id)));
});

test("Name comparator uses section, numeric level, bare name, and canonical ID",()=>{
  const entries=[
    sortable("Reference",null,"reference","reference"),sortable("Foundation",null,"foundation","foundation"),
    sortable("Level Twenty","20" as unknown as number,"levelled","level_20"),sortable("Twin",7,"levelled","twin_z"),
    sortable("Level Ten","10" as unknown as number,"levelled","level_10"),sortable("Beta",7,"levelled","beta"),
    sortable("Level Three",3,"levelled","level_3"),sortable("Twin","7" as unknown as number,"levelled","twin_a"),sortable("Alpha",7,"levelled","alpha"),
  ];
  assert.deepEqual(entries.sort(compareNameEntries).map(item=>item.id),["foundation","level_3","alpha","beta","twin_a","twin_z","level_10","level_20","reference"]);
});

test("canonical ownership, cleaned names, groups, and destinations feed Name navigation",async()=>{
  const {authority}=await loadAuthority(),index=buildNameIndex(authority),entryById=new Map(index.entities.map(entry=>[entry.id,entry]));
  const expectedGroups=[...authority.vocabularies.rules_areas!].sort((a,b)=>a.order-b.order).map(area=>area.id);assert.deepEqual(index.name_groups.map(group=>group.id),expectedGroups);
  const groupedIds=index.name_groups.flatMap(group=>group.entity_ids);assert.equal(groupedIds.length,authority.entities.length);assert.equal(new Set(groupedIds).size,authority.entities.length);
  const advanced=index.name_groups.find(group=>group.id==="advanced_training")!,pyrokinesis=index.name_groups.find(group=>group.id==="pyrokinesis")!;
  assert.ok(advanced.entity_ids.indexOf("advanced_deflection_screen")<advanced.entity_ids.indexOf("advanced_phase_step"));assert.ok(pyrokinesis.entity_ids.indexOf("thermal_fracture")<pyrokinesis.entity_ids.indexOf("furnace_strike"));
  assert.deepEqual([entryById.get("advanced_deflection_screen")?.title,entryById.get("advanced_phase_step")?.title],["Deflection Screen","Phase Step"]);
  for(const entity of authority.entities){const entry=entryById.get(entity.id)!;assert.equal(entry.primary_rules_area,entity.presentation_metadata.primary_rules_area);if(isCalculatorDeckEntity(entity)){assert.deepEqual(entry.routes,{},entity.id);continue;}const expectedAreas=[...entity.classifications.rules_area].sort();assert.deepEqual(Object.keys(entry.routes).sort(),expectedAreas,entity.id);for(const area of expectedAreas){const category=authority.navigation.categories.find(candidate=>candidate.id===area)!,fallback=category.topics.find(topic=>topic.entity_ids.includes(entity.id))!.id;assert.equal(entry.routes[area],entity.presentation_metadata.canonical_topic_by_area[area]??fallback,`${entity.id} ${area}`);}}
});

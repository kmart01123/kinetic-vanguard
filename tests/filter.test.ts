import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import YAML from "yaml";
import { loadAuthority } from "../src/load.js";
import { buildFilterIndex, buildIntegrity, compareFilterEntries, compareNameEntries, type FilterIndexEntry } from "../src/validate.js";

const select=(index:any,selections:Record<string,string[]>)=>index.entities.filter((item:any)=>Object.entries(selections).every(([facet,values])=>values.some(value=>item.classifications[facet]?.includes(value)))).map((item:any)=>item.id).sort();

test("integrity covers every identity, vector, vocabulary, and route",async()=>{const {authority}=await loadAuthority();const index=buildFilterIndex(authority);const report=buildIntegrity(authority,index);assert.equal(report.all_passed,true);assert.equal(index.entities.length,authority.entities.length);});

test("independently-authored provisional correctness cases agree",async()=>{
  const {authority}=await loadAuthority();const index=buildFilterIndex(authority);const corpus=YAML.parse(await readFile("tests/filtered-search-correctness.yaml","utf8"));
  for(const item of corpus.cases){if(item.expected_set==="all_publishable_entities"){assert.deepEqual(select(index,item.selections),authority.entities.map(entity=>entity.id).sort(),item.id);continue;}if(item.expected_state==="instruction")continue;assert.deepEqual(select(index,item.selections),[...item.expected_result_ids].sort(),item.id);for(const id of item.must_not_include)assert.ok(!select(index,item.selections).includes(id),`${item.id} unexpectedly included ${id}`);}
});


const orderedSelect=(index:any,selections:Record<string,string[]>)=>index.entities.filter((item:any)=>Object.entries(selections).every(([facet,values])=>values.some(value=>item.classifications[facet]?.includes(value))));
const sortable=(title:string,minimum_level:number|null,progression_section:FilterIndexEntry["progression_section"],progression_order=0,id=title.toLowerCase().replaceAll(" ","_")):FilterIndexEntry=>({id,title,primary_rules_area:"psychokinesis",rules_area_order:4,minimum_level,progression_section,progression_order,feature_role_order:0,classifications:{rules_area:["psychokinesis"],entity_kind:["feature"],feature_role:["rider"]},routes:{psychokinesis:"topic"}});

test("Rules area uses only the canonical displayed area",async()=>{
  const {authority}=await loadAuthority();const index=buildFilterIndex(authority);
  const psychokinesis=orderedSelect(index,{rules_area:["psychokinesis"]});
  assert.ok(psychokinesis.every((item:any)=>item.primary_rules_area==="psychokinesis"&&item.classifications.rules_area.length===1&&item.classifications.rules_area[0]==="psychokinesis"));
  assert.ok(!psychokinesis.some((item:any)=>item.id==="common_overload"));
  const common=orderedSelect(index,{rules_area:["common_features"]});
  assert.equal(common.filter((item:any)=>item.id==="common_overload").length,1);
  assert.ok(!common.some((item:any)=>item.id==="telekinetic_shove"));
});

test("multiple canonical areas are grouped in vocabulary order",async()=>{
  const {authority}=await loadAuthority();const index=buildFilterIndex(authority);
  const result=orderedSelect(index,{rules_area:["psychokinesis","common_features"]});
  assert.ok(result.every((item:any)=>["common_features","psychokinesis"].includes(item.primary_rules_area)));
  const areas=result.map((item:any)=>item.primary_rules_area);const firstPsychokinesis=areas.indexOf("psychokinesis");
  assert.ok(firstPsychokinesis>0);assert.ok(areas.slice(0,firstPsychokinesis).every((area:string)=>area==="common_features"));assert.ok(areas.slice(firstPsychokinesis).every((area:string)=>area==="psychokinesis"));
});

test("progression comparator sorts by level before name",()=>{
  const entries=[sortable("Feature A",5,"levelled"),sortable("Feature C",9,"levelled"),sortable("Feature Z",1,"levelled"),sortable("Feature B",5,"levelled"),sortable("Feature M",3,"levelled")];
  assert.deepEqual(entries.sort(compareFilterEntries).map(item=>item.title),["Feature Z","Feature M","Feature A","Feature B","Feature C"]);
});


test("Name comparator uses numeric level, then bare name, then canonical ID",()=>{
  const entries=[
    sortable("Level Twenty","20" as unknown as number,"levelled",0,"level_20"),
    sortable("Twin",7,"levelled",0,"twin_z"),
    sortable("Level Ten","10" as unknown as number,"levelled",0,"level_10"),
    sortable("Beta",7,"levelled",0,"beta"),
    sortable("Level Three",3,"levelled",0,"level_3"),
    sortable("Twin","7" as unknown as number,"levelled",0,"twin_a"),
    sortable("Alpha",7,"levelled",0,"alpha")
  ];
  assert.deepEqual(entries.sort(compareNameEntries).map(item=>item.id),["level_3","alpha","beta","twin_a","twin_z","level_10","level_20"]);
});

test("canonical feature levels, cleaned names, groups, and destinations feed the Name index",async()=>{
  const {authority}=await loadAuthority();const index=buildFilterIndex(authority);
  const entity=(id:string)=>authority.entities.find(candidate=>candidate.id===id)!;
  assert.equal(entity("thermal_fracture").level,7);assert.equal(typeof entity("thermal_fracture").level,"number");
  assert.equal(entity("furnace_strike").level,20);assert.equal(typeof entity("furnace_strike").level,"number");
  assert.deepEqual([entity("advanced_deflection_screen").title,entity("advanced_phase_step").title],["Deflection Screen","Phase Step"]);
  assert.deepEqual([entity("advanced_deflection_screen").level,entity("advanced_phase_step").level],[5,10]);
  assert.deepEqual([entity("advanced_deflection_screen").classifications.acquisition_mode,entity("advanced_phase_step").classifications.acquisition_mode],["granted","granted"]);
  assert.deepEqual([entity("advanced_deflection_screen").presentation_metadata.primary_rules_area,entity("advanced_phase_step").presentation_metadata.primary_rules_area],["advanced_training","advanced_training"]);
  const advanced=index.name_groups.find(group=>group.id==="advanced_training")!,pyrokinesis=index.name_groups.find(group=>group.id==="pyrokinesis")!;
  assert.ok(advanced.entity_ids.indexOf("advanced_deflection_screen")<advanced.entity_ids.indexOf("advanced_phase_step"));
  assert.ok(pyrokinesis.entity_ids.indexOf("thermal_fracture")<pyrokinesis.entity_ids.indexOf("furnace_strike"));
  const indexed=(id:string)=>index.entities.find(candidate=>candidate.id===id)!;
  const advancedTitles=advanced.entity_ids.map(id=>indexed(id).title);
  assert.equal(new Set(advancedTitles).size,advancedTitles.length);
  assert.equal(indexed("advanced_deflection_screen").routes.advanced_training,"advanced_training_advanced_deflection_screen_topic");
  assert.equal(indexed("advanced_phase_step").routes.advanced_training,"advanced_training_advanced_phase_step_topic");
});
test("unlevelled entities use explicit foundation and reference sections",async()=>{
  const {authority}=await loadAuthority();const index=buildFilterIndex(authority);const common=orderedSelect(index,{rules_area:["common_features"]});
  const foundation=common.findIndex((item:any)=>item.id==="how_to_play"),firstLevel=common.findIndex((item:any)=>item.minimum_level!==null),reference=common.findIndex((item:any)=>item.id==="subclass_feature_reference");
  assert.equal(common[foundation].progression_section,"foundation");assert.equal(common[reference].progression_section,"reference");assert.ok(foundation<firstLevel);assert.ok(reference>firstLevel);
});

test("Rules area remains authoritative with a restrictive feature role",async()=>{
  const {authority}=await loadAuthority();const index=buildFilterIndex(authority);const result=orderedSelect(index,{rules_area:["psychokinesis"],feature_role:["rider"]});
  assert.deepEqual(result.map((item:any)=>item.id),["telekinetic_shove","explosion_implosion"]);assert.ok(result.every((item:any)=>item.primary_rules_area==="psychokinesis"));
});

test("stable order uses area, section, level, source order, role order, name, and ID",async()=>{const {authority}=await loadAuthority();const index=buildFilterIndex(authority);assert.deepEqual(index.entities,[...index.entities].sort(compareFilterEntries));});

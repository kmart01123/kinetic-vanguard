import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";
import { validateMigration, validateSemantics } from "../src/validate.js";

test("authority is schema-valid and semantically valid for prototype",async()=>{
  const loaded=await loadAuthority();const migration=await validateMigration(false);
  const diagnostics=[...loaded.diagnostics,...migration.diagnostics,...validateSemantics(loaded.authority,migration.state,false)];
  assert.deepEqual(diagnostics.filter(item=>item.severity==="error"),[]);
  assert.ok(diagnostics.some(item=>item.code==="migration.pending_review"));
});

test("legacy Markdown is inherited provenance, never a direct input",async()=>{
  const manifest=JSON.parse(await readFile("build/inputs.json","utf8"));
  assert.ok(!manifest.inputs.some((input:any)=>input.path==="Kinetic_Vanguard.md"));
  const migration=JSON.parse(await readFile("migration/manifest.json","utf8"));
  assert.equal(migration.migration_source_filename,"Kinetic_Vanguard.md");
});

test("source coverage is exact",async()=>{
  const coverage=JSON.parse(await readFile("migration/source-coverage.json","utf8"));let cursor=0;
  for(const span of coverage.spans){assert.equal(span.start,cursor);cursor=span.end;}
  assert.equal(cursor,coverage.total_byte_count);assert.equal(coverage.covered_byte_count,coverage.total_byte_count);assert.equal(coverage.gap_count,0);assert.equal(coverage.overlap_count,0);
});

test("Manifested Strike owns its progression immediately after the core rule",async()=>{
  const expectedRows=[["3–4","1d6"],["5–10","1d8"],["11–16","1d10"],["17–20","1d12"]] as const;
  const expectedProse="Manifested Strike die by level: 1d6 (3rd–4th) → 1d8 (5th–10th) → 1d10 (11th–16th) → 1d12 (17th–20th)";
  const source=await readFile("Kinetic_Vanguard.md","utf8");
  for(const [level,die] of expectedRows)assert.ok(source.split("\n").includes(`| ${level.padEnd(13)} | ${die.padEnd(6)} |`));

  const {authority}=await loadAuthority();
  const manifested=authority.entities.find(item=>item.id==="common_manifested_strike")!;
  const overload=authority.entities.find(item=>item.id==="common_overload")!;
  const progressionIndex=manifested.content.findIndex(block=>block.type==="paragraph"&&block.inlines?.map(node=>node.text).join("")===expectedProse);
  const tableIndex=manifested.content.findIndex(block=>block.type==="table"&&block.headers?.map(cell=>cell.map(node=>node.text).join("")).join("|")==="Fighter Level|MS Die");
  assert.equal(progressionIndex,1);assert.equal(tableIndex,2);
  const table=manifested.content[tableIndex]!;
  const rows=table.rows!.map(row=>row.map(cell=>cell.map(node=>node.text).join("")));
  assert.deepEqual(rows,expectedRows);assert.doesNotMatch(JSON.stringify(table),/�/u);
  assert.doesNotMatch(JSON.stringify(overload.content),/Manifested Strike die by level|Fighter Level\|MS Die/);

  const progressionSourceIds=["u_l0079_c001_paragraph_fee08637a9","u_l0081_c003_table_cell_9badec117b","u_l0081_c019_table_cell_33739f9c45","u_l0083_c003_table_cell_2ddace8cf2","u_l0083_c019_table_cell_44868e6ec0","u_l0084_c003_table_cell_e64785a46b","u_l0084_c019_table_cell_2409c213e8","u_l0085_c003_table_cell_9c98fb2a8d","u_l0085_c019_table_cell_d814910798","u_l0086_c003_table_cell_a7c2a40e21","u_l0086_c019_table_cell_41af4746c0"];
  const manifestedOrigins=new Set(manifested.origins.flatMap(origin=>origin.source_unit_ids));const overloadOrigins=new Set(overload.origins.flatMap(origin=>origin.source_unit_ids));
  assert.ok(progressionSourceIds.every(id=>manifestedOrigins.has(id)));assert.ok(progressionSourceIds.every(id=>!overloadOrigins.has(id)));

  const common=authority.navigation.categories.find(category=>category.id==="common_features")!;const manifestedTopic=common.topics.find(topic=>topic.id==="common_features_common_manifested_strike_topic")!;const overloadTopic=common.topics.find(topic=>topic.id==="common_features_common_overload_topic")!;
  assert.deepEqual({title:manifestedTopic.title,entityIds:manifestedTopic.entity_ids,order:manifestedTopic.order},{title:"Manifested Strike",entityIds:["common_manifested_strike"],order:7});
  assert.deepEqual({title:overloadTopic.title,entityIds:overloadTopic.entity_ids,order:overloadTopic.order},{title:"Overload",entityIds:["common_overload"],order:8});
});

test("concentration requirements are canonical structured feature data",async()=>{
  const {authority}=await loadAuthority();
  const concentrationIds=authority.entities
    .filter(entity=>entity.requires_concentration===true)
    .map(entity=>entity.id)
    .sort();
  assert.deepEqual(concentrationIds,[
    "advanced_beguile","advanced_gravitic_press","ball_lightning",
    "frozen_ground","mass_levitation","vectored_thrust"
  ]);
  assert.equal(authority.entities.find(entity=>entity.id==="telekinetic_slam")?.requires_concentration,undefined);
});


test("Common rules do not leak into discipline Browse topics",async()=>{
  const {authority}=await loadAuthority();const entities=new Map(authority.entities.map(entity=>[entity.id,entity]));
  const categories=new Map(authority.navigation.categories.map(category=>[category.id,category]));
  const titles=(categoryId:string)=>categories.get(categoryId)!.topics.map(topic=>topic.title);
  assert.equal(titles("common_features").filter(title=>title==="Overload").length,1);
  for(const categoryId of ["cryokinesis","pyrokinesis","psychokinesis","electrokinesis"]){
    assert.ok(!titles(categoryId).includes("Overload"));
    for(const topic of categories.get(categoryId)!.topics)for(const entityId of topic.entity_ids)assert.ok(entities.get(entityId)!.classifications.rules_area.includes(categoryId),`${entityId} leaked into ${categoryId}`);
  }
  const commonOnly=authority.entities.filter(entity=>entity.classifications.rules_area.length===1&&entity.classifications.rules_area[0]==="common_features").map(entity=>entity.id);
  for(const categoryId of ["cryokinesis","pyrokinesis","psychokinesis","electrokinesis"]){const topicEntities=new Set(categories.get(categoryId)!.topics.flatMap(topic=>topic.entity_ids));assert.ok(commonOnly.every(entityId=>!topicEntities.has(entityId)));}
});

test("example turns use one plain-text six-phase authority contract",async()=>{
  const {authority}=await loadAuthority();
  const examplePlay=authority.entities.find(entity=>entity.id==="common_example_play")!;
  const overload=authority.entities.find(entity=>entity.id==="common_overload")!;
  const sections=examplePlay.content.filter(block=>block.type==="example_play_section") as any[];
  const phases=["setup","activation","rolls_or_saves","damage","effects","result"];
  assert.deepEqual(sections.map(block=>block.discipline),["pyrokinesis","psychokinesis","cryokinesis","electrokinesis"]);
  assert.deepEqual(sections.map(block=>block.title.map((node:any)=>node.text).join("")),["Focused Fire — Level 11 Pyrokinesis","Aerial Repositioning — Level 11 Psychokinesis","Frozen Ground Lockdown — Level 11 Cryokinesis","Room Sweep — Level 11 Electrokinesis"]);
  for(const section of sections){
    assert.ok(phases.every(field=>Array.isArray(section[field])));
    for(const field of ["heading","title",...phases]){assert.ok(section[field].length>0);assert.ok(section[field].every((node:any)=>node.type==="text"),section.title[0].text+" "+field+" must use plain text");}
  }
  const overloadExamples=overload.content.filter(block=>block.type==="example") as any[];
  assert.equal(overloadExamples.length,1);assert.equal(overloadExamples[0].title.map((node:any)=>node.text).join(""),"Example — Level 11 Cryokinesis (PB 4, Int +3)");
  assert.equal(sections.some(section=>JSON.stringify(section).includes("u_l0100_c003_blockquote_paragraph_9486363841")),false);
  assert.doesNotMatch(JSON.stringify(sections),/Example assumptions:|Full Attack Turn|Sustained Turn|type":"(?:strong|emphasis)"/);
});

test("tiered rules use an ordered, cumulative hierarchy without changing mechanics",async()=>{
  const {authority}=await loadAuthority();
  const text=(entity:any)=>entity.content.flatMap((block:any)=>block.inlines??[]).map((inline:any)=>inline.text).join("\n");
  const tiered=authority.entities.filter(entity=>text(entity).includes("T0 Base:")&&text(entity).includes("T1 Overload:"));
  assert.ok(tiered.length>=25);
  assert.doesNotMatch(JSON.stringify(authority),/\bTier \d+ Overload(?: \([^)]*\))?:/);
  for(const entity of tiered){
    const rules=text(entity);
    const tier0=rules.indexOf("T0 Base:");
    const tier1=rules.indexOf("T1 Overload: Changes from Tier 0:");
    const tier2=rules.indexOf("T2 Overload: Changes from Tier 1:");
    assert.ok(tier0>=0,entity.id+" is missing T0 Base");
    assert.ok(tier1>tier0,entity.id+" does not place T1 after T0");
    assert.ok(tier2>tier1,entity.id+" does not place T2 after T1");
  }

  const rulesFor=(id:string)=>text(authority.entities.find(entity=>entity.id===id)!);
  const absoluteZero=rulesFor("absolute_zero");
  for(const mechanic of [
    "10d10 cold damage on a failed save, or half on a successful one",
    "speed becomes 0 until the end of your next turn",
    "Damage increases to 12d10",
    "Restrained until the end of your next turn",
    "Damage increases to 14d10",
    "Stunned condition until the end of your next turn",
    "replaces the Restrained condition from Tier 1",
    "speed becomes 0 even on a successful save"
  ])assert.ok(absoluteZero.includes(mechanic),"Absolute Zero mechanic changed: "+mechanic);
  assert.doesNotMatch(absoluteZero,/repeat(?:s| the)? (?:save|saving throw)/i);

  const snowChains=rulesFor("snow_chains");
  for(const mechanic of ["speed becomes 0 until the end of your next turn (no save)","make a Con save","Restrained until the end of your next turn","cannot take reactions until the start of your next turn","Stunned condition until the end of your next turn"])assert.ok(snowChains.includes(mechanic),"Snow Chains mechanic changed: "+mechanic);
  assert.match(snowChains,/Stunned condition[^.]+replaces the Restrained condition retained by Tier 1/);

  const frozenGround=rulesFor("frozen_ground");
  assert.match(frozenGround,/Speed becomes 0 until the end of the current turn/);
  assert.match(frozenGround,/Restrained condition until the end of your next turn replaces Tier 1/);
});

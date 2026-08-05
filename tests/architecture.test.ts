import assert from "node:assert/strict";
import test from "node:test";
import { access, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

const assertAbsent=async(path:string)=>assert.rejects(access(path),(error:any)=>error?.code==="ENOENT");
async function filesUnder(root:string):Promise<string[]>{const entries=await readdir(root,{withFileTypes:true});const files:string[]=[];for(const entry of entries){const path=join(root,entry.name);if(entry.isDirectory())files.push(...await filesUnder(path));else files.push(path);}return files;}

test("YAML authority is schema-valid, semantically valid, and complete",async()=>{
  const loaded=await loadAuthority();const diagnostics=[...loaded.diagnostics,...validateSemantics(loaded.authority)];
  assert.deepEqual(diagnostics,[]);
  assert.equal(loaded.authority.rules_version,"13.1.0");
  const audit=loaded.authority.audits?.find(item=>item.id==="yaml_rules_authority")!;
  assert.deepEqual([...audit.subject_ids].sort(),loaded.authority.entities.map(entity=>entity.id).sort());
});

test("retired migration sources are absent from the active architecture",async()=>{
  await Promise.all([assertAbsent("Kinetic_Vanguard.md"),assertAbsent("src/migrate.ts"),assertAbsent("migration")]);
  const rootFiles=await readdir(".");assert.deepEqual(rootFiles.filter(path=>/^ADR-0001.*\.md$/.test(path)),[]);
  const packageJson=JSON.parse(await readFile("package.json","utf8"));assert.equal(packageJson.scripts.migrate,undefined);
  const inputs=JSON.parse(await readFile("build/inputs.json","utf8")).inputs as Array<{path:string;role:string}>;
  assert.deepEqual(inputs.filter(input=>input.role==="rules_authority").map(input=>input.path),["KineticVanguard.yaml"]);
  assert.ok(inputs.every(input=>!/(?:^|\/)migration(?:\/|$)|Kinetic_Vanguard\.md|ADR-0001|src\/migrate/.test(input.path)));
  const productionFiles=(await Promise.all(["src","build","schema","review","release","policy",".github"].map(filesUnder))).flat();
  for(const path of productionFiles)assert.doesNotMatch(await readFile(path,"utf8"),/Kinetic_Vanguard\.md|ADR-0001|src\/migrate|npm run migrate/,path);
  assert.match(await readFile("CHANGELOG.md","utf8"),/migration/i);
});

test("prototype and release builds reflect direct YAML edits",async()=>{
  const temporary=await mkdtemp(join(tmpdir(),"kv-yaml-authority-"));const authorityPath=join(temporary,"KineticVanguard.edited.yaml");const source=await readFile("KineticVanguard.yaml","utf8");const edited=source.replace("title: Kinetic Vanguard","title: Kinetic Vanguard YAML Edit Probe");assert.notEqual(edited,source);await writeFile(authorityPath,edited);
  const previousApproval=process.env.KV_RELEASE_APPROVED;
  try{
    const prototypeRoot=join(temporary,"prototype"),releaseRoot=join(temporary,"release");
    const prototype=await executeBuild("prototype",prototypeRoot,authorityPath);process.env.KV_RELEASE_APPROVED="1";const release=await executeBuild("release",releaseRoot,authorityPath);
    for(const result of [prototype,release]){const html=await readFile(result.htmlPath,"utf8");assert.match(html,/Kinetic Vanguard YAML Edit Probe/);assert.doesNotMatch(html,/Kinetic_Vanguard\.md|npm run migrate|edit (?:the )?Markdown/i);assert.equal(result.manifest.build_identity.canonical_rules_authority,authorityPath);assert.deepEqual(result.manifest.declared_inputs.filter((input:any)=>input.role==="rules_authority").map((input:any)=>input.path),[authorityPath]);}
    const coverage=JSON.parse(await readFile(join(prototypeRoot,"coverage-ledger.json"),"utf8"));const {authority}=await loadAuthority(authorityPath);assert.equal(coverage.entity_count,authority.entities.length);assert.deepEqual(coverage.entities.map((entity:any)=>entity.entity_id),authority.entities.map(entity=>entity.id));assert.ok(coverage.entities.every((entity:any)=>entity.content_block_count>0&&entity.destinations.length>0));
  }finally{if(previousApproval===undefined)delete process.env.KV_RELEASE_APPROVED;else process.env.KV_RELEASE_APPROVED=previousApproval;await rm(temporary,{recursive:true,force:true});}
});
test("Manifested Strike owns its progression immediately after the core rule",async()=>{
  const expectedRows=[["3–4","1d6"],["5–10","1d8"],["11–16","1d10"],["17–20","1d12"]] as const;
  const expectedProse="Manifested Strike die by level: 1d6 (3rd–4th) → 1d8 (5th–10th) → 1d10 (11th–16th) → 1d12 (17th–20th)";
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

  const common=authority.navigation.categories.find(category=>category.id==="common_features")!;const manifestedTopic=common.topics.find(topic=>topic.id==="common_features_common_manifested_strike_topic")!;const overloadTopic=common.topics.find(topic=>topic.id==="common_features_common_overload_topic")!;
  assert.deepEqual({title:manifestedTopic.title,entityIds:manifestedTopic.entity_ids,order:manifestedTopic.order},{title:"Manifested Strike",entityIds:["common_manifested_strike"],order:7});
  assert.deepEqual({title:overloadTopic.title,entityIds:overloadTopic.entity_ids,order:overloadTopic.order},{title:"Overload",entityIds:["common_overload"],order:8});
});

test("shared Overload startup exception covers every concentration feature",async()=>{
  const {authority}=await loadAuthority();
  const concentrationFeatures=authority.entities.filter(entity=>entity.requires_concentration===true);
  assert.deepEqual(concentrationFeatures.map(entity=>entity.id).sort(),[
    "advanced_beguile","advanced_gravitic_press","ball_lightning",
    "frozen_ground","mass_levitation","vectored_thrust"
  ]);
  assert.ok(concentrationFeatures.every(entity=>entity.classifications.feature_role==="standalone"));
  assert.equal(authority.entities.find(entity=>entity.id==="telekinetic_slam")?.requires_concentration,undefined);
  const overload=authority.entities.find(entity=>entity.id==="common_overload")!;
  const startupException=overload.content
    .filter(block=>block.type==="note")
    .flatMap(block=>block.inlines??[])
    .map(inline=>inline.text)
    .find(value=>value?.startsWith("Concentration Startup Exception:"));
  assert.equal(startupException,"Concentration Startup Exception: When you activate a concentration feature with Overload, the Blood Tax paid for that activation does not trigger a concentration saving throw for the feature being activated. After activation, subsequent damage—including later Blood Tax—forces concentration saving throws as normal. Standard concentration rules still apply—you can concentrate on only one feature at a time.");
});


test("Forked Lightning resolves every target's save and outcomes independently",async()=>{
  const {authority}=await loadAuthority();
  const feature=authority.entities.find(entity=>entity.id==="forked_lightning")!;
  const rules=feature.content.flatMap(block=>block.inlines??[]).map(inline=>inline.text).join("\n");
  assert.match(rules,/Every target makes its own Charisma saving throw and resolves its damage independently\./);
  assert.match(rules,/primary target takes 8d8 lightning damage on a failed save or half as much on a successful one/);
  assert.match(rules,/Each secondary target takes 4d8 lightning damage on a failed save or half as much on a successful one/);
  assert.match(rules,/One target’s saving throw never determines another target’s damage or conditions\./);
  assert.match(rules,/Each target that fails its own saving throw cannot take reactions and has Disadvantage on attack rolls/);
  assert.match(rules,/a target that succeeds suffers neither effect/);
  assert.match(rules,/Only if the primary target fails its saving throw does its Speed also become 0/);
  assert.match(rules,/A secondary target’s Speed does not change\./);
  for(const mechanic of ["up to 3 other creatures","8d8 lightning damage","4d8 lightning damage","10d8","up to 4 other creatures","5d8","12d8","up to 5 other creatures","6d8"])assert.ok(rules.includes(mechanic),"Forked Lightning mechanic changed: "+mechanic);
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

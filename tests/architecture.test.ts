import assert from "node:assert/strict";
import test from "node:test";
import { access, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeBuild } from "../src/build.js";
import { canonicalJson, sha256 } from "../src/canonical.js";
import { loadAuthority } from "../src/load.js";
import { validateSemantics } from "../src/validate.js";

const assertAbsent=async(path:string)=>assert.rejects(access(path),(error:any)=>error?.code==="ENOENT");
async function filesUnder(root:string):Promise<string[]>{const entries=await readdir(root,{withFileTypes:true});const files:string[]=[];for(const entry of entries){const path=join(root,entry.name);if(entry.isDirectory())files.push(...await filesUnder(path));else files.push(path);}return files;}
const inlineText=(nodes:any[]|undefined)=>nodes?.map(node=>node.text??node.label??"").join("")??"";
const blockText=(block:any):string=>[inlineText(block.inlines),...(block.items??[]).map((item:any[])=>inlineText(item)),...(block.body??[]).map((item:any)=>blockText(item))].filter(Boolean).join("\n");
const entityRules=(entity:any)=>entity.content.map((block:any)=>blockText(block)).filter(Boolean).join("\n");
const ownedOnboardingIds=(value:any,result:string[]=[]):string[]=>{if(Array.isArray(value)){value.forEach(item=>ownedOnboardingIds(item,result));return result;}if(!value||typeof value!=="object")return result;for(const [key,child] of Object.entries(value)){if(key==="id"&&typeof child==="string")result.push(child);else ownedOnboardingIds(child,result);}return result;};
const onboardingDestinations=(value:any,result:any[]=[]):any[]=>{if(Array.isArray(value)){value.forEach(item=>onboardingDestinations(item,result));return result;}if(!value||typeof value!=="object")return result;if(typeof value.kind==="string"&&(typeof value.section_id==="string"||typeof value.category_id==="string"||typeof value.entity_id==="string"))result.push(value);for(const child of Object.values(value))onboardingDestinations(child,result);return result;};
const onboardingStrings=(value:any,result:string[]=[]):string[]=>{if(typeof value==="string"){result.push(value);return result;}if(Array.isArray(value)){value.forEach(item=>onboardingStrings(item,result));return result;}if(value&&typeof value==="object")Object.values(value).forEach(item=>onboardingStrings(item,result));return result;};

test("YAML authority is schema-valid, semantically valid, and complete",async()=>{
  const loaded=await loadAuthority();const diagnostics=[...loaded.diagnostics,...validateSemantics(loaded.authority)];
  assert.deepEqual(diagnostics,[]);
  assert.equal(loaded.authority.rules_version,"13.2.0");
  const audit=loaded.authority.audits?.find(item=>item.id==="yaml_rules_authority")!;
  assert.deepEqual([...audit.subject_ids].sort(),loaded.authority.entities.map(entity=>entity.id).sort());
});

test("top-level onboarding is canonical, complete, resolvable, and outside the 44-entity rules domain",async()=>{
  const {authority}=await loadAuthority();const onboarding=authority.onboarding;
  assert.equal(onboarding.id,"start_here");assert.equal(onboarding.title,"Start Here");
  assert.deepEqual({primary:onboarding.primary_paths.length,disciplines:onboarding.disciplines.cards.length,steps:onboarding.basic_turn.steps.length,reminders:onboarding.basic_turn.reminders.length,basicDestinations:onboarding.basic_turn.destinations.length,checklist:onboarding.build_checklist.items.length,glossary:onboarding.glossary.entries.length,next:onboarding.next_destinations.items.length},{primary:3,disciplines:4,steps:4,reminders:3,basicDestinations:2,checklist:6,glossary:5,next:7});
  assert.deepEqual(onboarding.primary_paths.map(item=>item.destination),[
    {kind:"onboarding_section",section_id:"build_checklist"},
    {kind:"onboarding_section",section_id:"basic_turn"},
    {kind:"category",category_id:"common_features"}
  ]);
  assert.deepEqual(onboarding.disciplines.cards.map(item=>[item.title,item.destination]),[
    ["Pyrokinesis",{kind:"category",category_id:"pyrokinesis"}],
    ["Cryokinesis",{kind:"category",category_id:"cryokinesis"}],
    ["Psychokinesis",{kind:"category",category_id:"psychokinesis"}],
    ["Electrokinesis",{kind:"category",category_id:"electrokinesis"}]
  ]);
  assert.deepEqual(onboarding.basic_turn.destinations.map(item=>item.destination),[{kind:"entity",entity_id:"how_to_play"},{kind:"entity",entity_id:"common_overload"}]);
  assert.deepEqual(onboarding.build_checklist.items.map(item=>item.destination.kind==="entity"?item.destination.entity_id:null),["common_psionic_discipline","common_psi_reservoir","common_manifested_strike","common_signature_rider","common_kinetic_mastery","common_manifested_strike"]);
  assert.deepEqual(onboarding.glossary.entries.map(item=>item.destination.kind==="entity"?item.destination.entity_id:null),["common_manifested_strike","how_to_play","common_signature_rider","common_psi_reservoir","common_overload"]);
  assert.deepEqual(onboarding.next_destinations.items.map(item=>item.destination),[
    {kind:"entity",entity_id:"how_to_play"},{kind:"entity",entity_id:"common_example_play"},{kind:"entity",entity_id:"subclass_feature_reference"},{kind:"entity",entity_id:"common_psionic_discipline"},{kind:"entity",entity_id:"common_overload"},{kind:"entity",entity_id:"common_psi_reservoir"},{kind:"category",category_id:"common_features"}
  ]);

  const ids=ownedOnboardingIds(onboarding);assert.equal(ids.length,33);assert.equal(new Set(ids).size,ids.length);
  const entityIds=new Set(authority.entities.map(entity=>entity.id));assert.equal(authority.entities.length,44);assert.ok(ids.every(id=>!entityIds.has(id)));assert.ok(!entityIds.has(onboarding.id));
  const auditedIds=new Set(authority.audits?.flatMap(audit=>audit.subject_ids)??[]);assert.ok(ids.every(id=>!auditedIds.has(id)));

  const categories=new Map(authority.navigation.categories.map(category=>[category.id,category]));
  const sectionIds=new Set([onboarding.disciplines.id,onboarding.basic_turn.id,onboarding.build_checklist.id,onboarding.glossary.id,onboarding.next_destinations.id]);
  const destinations=onboardingDestinations(onboarding);assert.equal(destinations.length,27);
  for(const destination of destinations){
    if(destination.kind==="onboarding_section"){assert.ok(sectionIds.has(destination.section_id),destination.section_id);continue;}
    if(destination.kind==="category"){const category=categories.get(destination.category_id);assert.ok(category,destination.category_id);assert.ok(category!.topics.some(topic=>topic.id===category!.default_topic_id),destination.category_id);continue;}
    const entity=authority.entities.find(candidate=>candidate.id===destination.entity_id);assert.ok(entity,destination.entity_id);assert.equal(entity!.publishable,true);const category=categories.get(entity!.presentation_metadata.primary_rules_area);assert.ok(category,destination.entity_id);const topics=category!.topics.filter(topic=>topic.entity_ids.includes(entity!.id)).sort((a,b)=>a.order-b.order);const route=entity!.presentation_metadata.canonical_topic_by_area[category!.id]??topics[0]?.id;assert.ok(route&&topics.some(topic=>topic.id===route),destination.entity_id);
  }
  assert.deepEqual(Object.fromEntries(["pyrokinesis","cryokinesis","psychokinesis","electrokinesis"].map(id=>[id,categories.get(id)?.default_topic_id])),{pyrokinesis:"pyrokinesis_ember_bolt_topic",cryokinesis:"cryokinesis_glacial_spike_topic",psychokinesis:"psychokinesis_telekinetic_shove_topic",electrokinesis:"electrokinesis_static_discharge_topic"});
  assert.doesNotMatch(onboardingStrings(onboarding).join("\n"),/(?:https?:|www\.|mailto:)/iu);
});

test("onboarding semantic mutations produce focused diagnostics",async()=>{
  const {authority}=await loadAuthority();
  const expectCode=(code:string,mutate:(candidate:any)=>void)=>{const candidate=structuredClone(authority) as any;mutate(candidate);const diagnostics=validateSemantics(candidate);assert.ok(diagnostics.some(item=>item.code===code),code+": "+diagnostics.map(item=>item.code).join(", "));};
  expectCode("onboarding.id_duplicate",candidate=>{candidate.onboarding.primary_paths[1].id=candidate.onboarding.primary_paths[0].id;});
  expectCode("onboarding.entity_collision",candidate=>{candidate.onboarding.id="how_to_play";});
  expectCode("onboarding.entity_boundary",candidate=>{candidate.entities.pop();});
  expectCode("onboarding.section_unknown",candidate=>{candidate.onboarding.primary_paths[0].destination.section_id="missing_section";});
  expectCode("onboarding.category_unknown",candidate=>{candidate.onboarding.disciplines.cards[0].destination.category_id="missing_category";});
  expectCode("onboarding.category_route",candidate=>{candidate.navigation.categories.find((category:any)=>category.id==="common_features").default_topic_id="missing_topic";});
  expectCode("onboarding.entity_unknown",candidate=>{candidate.onboarding.build_checklist.items[0].destination.entity_id="missing_entity";});
  expectCode("onboarding.entity_route",candidate=>{candidate.navigation.categories.find((category:any)=>category.id==="common_features").topics.find((topic:any)=>topic.id==="common_features_common_manifested_strike_topic").entity_ids=[];});
  expectCode("onboarding.disciplines",candidate=>{candidate.onboarding.disciplines.cards[0].destination.category_id="cryokinesis";});
  expectCode("onboarding.primary_paths",candidate=>{candidate.onboarding.primary_paths[2].destination.category_id="advanced_training";});
  expectCode("onboarding.external_url",candidate=>{candidate.onboarding.introduction.orientation="Read https://example.invalid for more rules.";});
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

test("active CI publication names derive from the canonical rules version",async()=>{
  const [{authority},workflow]=await Promise.all([loadAuthority(),readFile(".github/workflows/ci.yml","utf8")]);
  assert.doesNotMatch(workflow,/\b13\.\d+(?:\.\d+)?\b/);
  assert.match(workflow,/rules_version: \$\{\{ steps\.rules-version\.outputs\.rules_version \}\}/);
  assert.match(workflow,/name: v\$\{\{ needs\.metadata\.outputs\.rules_version \}\} verification and release build/);
  assert.match(workflow,/name: kinetic-vanguard-v\$\{\{ needs\.metadata\.outputs\.rules_version \}\}/);
  assert.match(workflow,/\"rules_version\":\"\$\{\{ needs\.metadata\.outputs\.rules_version \}\}\"/);
  const artifactTemplate=workflow.match(/name: (kinetic-vanguard-v\$\{\{ needs\.metadata\.outputs\.rules_version \}\})/)?.[1];
  assert.equal(artifactTemplate?.replace("${{ needs.metadata.outputs.rules_version }}",authority.rules_version),"kinetic-vanguard-v13.2.0");
});

test("prototype and release builds reflect direct YAML edits",async()=>{
  const temporary=await mkdtemp(join(tmpdir(),"kv-yaml-authority-"));const authorityPath=join(temporary,"KineticVanguard.edited.yaml");const source=await readFile("KineticVanguard.yaml","utf8");const edited=source.replace("title: Kinetic Vanguard","title: Kinetic Vanguard YAML Edit Probe");assert.notEqual(edited,source);await writeFile(authorityPath,edited);
  const previousApproval=process.env.KV_RELEASE_APPROVED;
  try{
    const prototypeRoot=join(temporary,"prototype"),releaseRoot=join(temporary,"release");
    const prototype=await executeBuild("prototype",prototypeRoot,authorityPath);process.env.KV_RELEASE_APPROVED="1";const release=await executeBuild("release",releaseRoot,authorityPath);
    for(const result of [prototype,release]){const html=await readFile(result.htmlPath,"utf8");assert.match(html,/Kinetic Vanguard YAML Edit Probe/);assert.doesNotMatch(html,/Kinetic_Vanguard\.md|npm run migrate|edit (?:the )?Markdown/i);assert.equal(result.manifest.build_identity.canonical_rules_authority,authorityPath);assert.deepEqual(result.manifest.declared_inputs.filter((input:any)=>input.role==="rules_authority").map((input:any)=>input.path),[authorityPath]);}
    const coverage=JSON.parse(await readFile(join(prototypeRoot,"coverage-ledger.json"),"utf8"));const {authority}=await loadAuthority(authorityPath);assert.equal(coverage.version,3);assert.equal(coverage.entity_count,44);assert.equal(coverage.entity_count,authority.entities.length);assert.deepEqual(coverage.entities.map((entity:any)=>entity.entity_id),authority.entities.map(entity=>entity.id));assert.ok(coverage.entities.every((entity:any)=>entity.content_block_count>0&&entity.destinations.length>0));assert.equal(coverage.entities.some((entity:any)=>entity.entity_id===authority.onboarding.id),false);assert.deepEqual(coverage.onboarding,{authority_path:authorityPath+"#/onboarding",onboarding_id:"start_here",section_ids:["choose_your_discipline","basic_turn","build_checklist","terms_to_know","where_to_go_next"],destination_ids:[...authority.onboarding.primary_paths,...authority.onboarding.disciplines.cards,...authority.onboarding.basic_turn.destinations,...authority.onboarding.build_checklist.items,...authority.onboarding.glossary.entries,...authority.onboarding.next_destinations.items].map(item=>item.id)});
  }finally{if(previousApproval===undefined)delete process.env.KV_RELEASE_APPROVED;else process.env.KV_RELEASE_APPROVED=previousApproval;await rm(temporary,{recursive:true,force:true});}
});
test("Manifested Strike owns its progression immediately after the core rule",async()=>{
  const expectedRows=[["3–4","1d6"],["5–10","1d8"],["11–16","1d10"],["17–20","1d12"]] as const;
  const expectedProse="Manifested Strike die by level: 1d6 (3rd–4th) → 1d8 (5th–10th) → 1d10 (11th–16th) → 1d12 (17th–20th)";
  const {authority}=await loadAuthority();
  const manifested=authority.entities.find(item=>item.id==="common_manifested_strike")!;
  const overload=authority.entities.find(item=>item.id==="common_overload")!;
  const progressionIndex=manifested.content.findIndex(block=>block.type==="paragraph"&&block.inlines?.map(node=>node.text).join("")===expectedProse);
  const tableIndex=manifested.content.findIndex(block=>block.type==="table"&&block.headers?.map(cell=>cell.map(node=>node.text).join("")).join("|")==="Fighter Level|Manifested Strike Die");
  const indexContaining=(fragment:string)=>manifested.content.findIndex(block=>blockText(block).includes(fragment));
  const orderedCore=[
    indexContaining("When you take the Attack action"),
    indexContaining("Your attack bonus equals"),
    indexContaining("On a hit, the strike deals one Manifested Strike die"),
    progressionIndex,
    tableIndex,
    indexContaining("Manifested Strike costs no Psi"),
    indexContaining("On a critical hit")
  ];
  assert.deepEqual(orderedCore,[...orderedCore].sort((a,b)=>a-b));assert.equal(new Set(orderedCore).size,orderedCore.length);assert.ok(orderedCore.every(index=>index>=0));
  assert.match(blockText(manifested.content[orderedCore[0]!]!),/range of 60 feet/);assert.match(blockText(manifested.content[orderedCore[2]!]!),/Your Discipline determines the strike’s damage type/);
  assert.equal(tableIndex,progressionIndex+1);assert.ok(orderedCore.at(-1)!<indexContaining("For feats, Fighting Styles"));
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
  for(const tier of ["T1 Overload","T2 Overload"]){
    const tierText=feature.content.find(block=>block.type==="paragraph"&&block.inlines?.[0]?.text?.startsWith(tier))!.inlines![0]!.text!;
    assert.match(tierText,/Every target makes its own Charisma saving throw and resolves its own damage\./);
    assert.match(tierText,/primary target takes \d+d8 lightning damage on a failed save or half as much on a successful one/);
    assert.match(tierText,/secondary target takes \d+d8 lightning damage on a failed save or half as much on a successful one/);
  }
  assert.match(rules,/A target that succeeds still takes half damage but can take reactions and does not have Disadvantage on attack rolls\./);
  assert.match(rules,/Only if the primary target fails its saving throw does its Speed also become 0/);
  assert.match(rules,/A secondary target’s Speed does not change\./);
  for(const mechanic of ["up to 3 other creatures","8d8 lightning damage","4d8 lightning damage","10d8","up to 4 other creatures","5d8","12d8","up to 5 other creatures","6d8"])assert.ok(rules.includes(mechanic),"Forked Lightning mechanic changed: "+mechanic);
});


test("approved trigger, timing, replacement, and flavor clarifications remain canonical",async()=>{
  const {authority}=await loadAuthority();
  const rulesFor=(id:string)=>entityRules(authority.entities.find(entity=>entity.id===id)!);

  const howToPlay=authority.entities.find(entity=>entity.id==="how_to_play")!;
  const procedureIndex=howToPlay.content.findIndex(block=>block.type==="list"&&block.style==="ordered");const procedure=howToPlay.content[procedureIndex]!;
  const steps=procedure.items!.map(item=>inlineText(item));assert.equal(steps.length,6);
  const stepMechanics=[["Choose","target"],["Immediately before the attack roll","no rider or one legal rider"],["Tier 0 or an available Overload tier","Whether or not you use a rider","damage-type option"],["Pay","Psi","Blood Tax"],["Roll","fully resolve"],["On a miss","any declared rider does not resolve","Psi and Blood Tax remain spent"]];
  for(const [index,fragments] of stepMechanics.entries())for(const fragment of fragments)assert.ok(steps[index]!.includes(fragment),"How to Play step "+(index+1)+": "+fragment);
  assert.match(blockText(howToPlay.content[0]!),/^Resolve attacks one at a time\. A rider is an on-hit feature/);
  const limits=howToPlay.content.find(block=>block.type==="list"&&block.style==="unordered")!;const limitText=limits.items!.map(item=>inlineText(item)).join("\n");
  for(const rule of ["Signature Rider costs no Psi and can be used repeatedly","Other riders cost their listed Psi, and each can be used once per Attack action","only one rider","Only one rider can be Tier 2","Manifested Strike itself is never Overloaded"])assert.ok(limitText.includes(rule),rule);
  for(const edgeCase of ["Action Surge","Rider Target Parity","only one standalone psionic feature","Short Disruption Timing"])assert.ok(procedureIndex<howToPlay.content.findIndex(block=>blockText(block).includes(edgeCase)),edgeCase);

  const overload=authority.entities.find(entity=>entity.id==="common_overload")!;
  const tier2=overload.content.find(block=>block.type==="tier"&&block.tier===2)!;
  assert.match(JSON.stringify(tier2),/Tier 2’s Blood Tax replaces the Tier 1 amount\./);
  assert.match(JSON.stringify(tier2),/A Tier 2 Overload costs twice your Proficiency Bonus in total\./);
  assert.match(JSON.stringify(overload.content),/2 × Proficiency Bonus = 2 × 4 = 8/);
  assert.doesNotMatch(JSON.stringify(overload.content),/1 × 2 × PB/);
  const overloadIndex=(predicate:(block:any)=>boolean)=>overload.content.findIndex(predicate);const exampleIndex=overloadIndex(block=>block.type==="example");const costTableIndex=overloadIndex(block=>block.type==="table");
  const orderedOverload=[overloadIndex(block=>blockText(block).startsWith("Overload strengthens")),overloadIndex(block=>block.type==="tier"&&block.tier===1),overloadIndex(block=>block.type==="tier"&&block.tier===2),exampleIndex,costTableIndex,overloadIndex(block=>blockText(block).startsWith("Multiple Overloads")),overloadIndex(block=>blockText(block).startsWith("Critical Hits and Riders")),overloadIndex(block=>blockText(block).startsWith("Damage Immunity and Riders")),overloadIndex(block=>blockText(block).startsWith("Blood Tax Resistance and Immunity")),overloadIndex(block=>blockText(block).startsWith("Concentration Startup Exception")),overloadIndex(block=>blockText(block).startsWith("Blood Tax and Temporary Hit Points")),overloadIndex(block=>blockText(block).startsWith("Blood Tax at 0 Hit Points"))];
  assert.deepEqual(orderedOverload,[...orderedOverload].sort((a,b)=>a-b));assert.equal(new Set(orderedOverload).size,orderedOverload.length);assert.ok(orderedOverload.every(index=>index>=0));
  const costTable=overload.content[costTableIndex]!;const cells=(row:any[])=>row.map(cell=>inlineText(cell));const costRows=costTable.rows!.map(cells);const tier2Row=costRows.find(row=>row[0]==="Manifested Strike + Tier 2 rider")!;assert.equal(tier2Row[2],"2 × Proficiency Bonus in total");
  const tier0Row=costRows.find(row=>row[0]==="Manifested Strike + Tier 0 rider")!;assert.match(tier0Row[3]??"",/Signature Rider is repeatable at every tier/);
  const standaloneRow=costRows.find(row=>row[0]==="Overloaded standalone feature")!;assert.equal(standaloneRow[2],"Tier 1: Proficiency Bonus; Tier 2: 2 × Proficiency Bonus in total");
  assert.deepEqual(costRows.find(row=>row[0]==="Overloaded rider + overloaded standalone feature"),["Overloaded rider + overloaded standalone feature","Rider cost + feature cost","Sum both","Each Overload pays separately"]);
  const holdout=rulesFor("common_manifested_strike");assert.match(holdout,/Declare this option before the attack roll\. If the attack has a rider, declare the option at the same time as that rider and its tier\./);

  const ballLightning=rulesFor("ball_lightning");
  for(const rule of ["enters the Sphere for the first time on any turn","Voluntary or forced movement into the Sphere can trigger this effect","trigger it by entering only once per turn","Moving the orb onto a stationary creature does not trigger damage immediately","must later enter the Sphere or start its turn there"])assert.ok(ballLightning.includes(rule),rule);

  assert.match(rulesFor("frozen_ground"),/replaces the Tier 0 effect retained by Tier 1 that makes the target’s Speed 0/);
  assert.doesNotMatch(rulesFor("frozen_ground"),/replaces Tier 1’s effect that makes its Speed 0/);
  assert.ok(rulesFor("telekinetic_slam").startsWith("You seize a foe with overwhelming telekinetic force and hurl it across the battlefield."));
  assert.doesNotMatch(rulesFor("telekinetic_slam"),/ground|Prone|falling damage|collision damage/i);
});

test("newcomer common rules preserve choices, resources, Signature Riders, and Kinetic Mastery",async()=>{
  const {authority}=await loadAuthority();
  const entity=(id:string)=>authority.entities.find(item=>item.id===id)!;
  const rules=(id:string)=>entityRules(entity(id));
  const listItems=(id:string,index=0)=>entity(id).content.filter(block=>block.type==="list")[index]!.items!.map(item=>inlineText(item));

  const discipline=entity("common_psionic_discipline");
  const disciplineRules=rules("common_psionic_discipline");
  assert.equal(discipline.id,"common_psionic_discipline");assert.equal(discipline.title,"Psionic Discipline");assert.equal(discipline.level,3);
  assert.deepEqual(discipline.classifications,{entity_kind:"feature",feature_role:"passive",rules_area:["common_features"]});
  assert.equal(blockText(discipline.content[0]!),"When you gain this subclass at Fighter level 3, choose one Kinetic Discipline: Pyrokinesis, Cryokinesis, Psychokinesis, or Electrokinesis. Your chosen Discipline determines your Manifested Strike’s damage type, Discipline signature saving throw, Kinetic Mastery, Signature Rider, and the Discipline features you gain at Fighter levels 3, 7, 10, 15, and 20. This choice is permanent and is separate from your Psionic Ability choice.");
  assert.equal(blockText(discipline.content[1]!),"Choose Intelligence, Wisdom, or Charisma as your Psionic Ability. Your Psionic Ability choice does not change your Discipline.");
  assert.match(disciplineRules,/Your Psionic Ability modifier is the ability modifier for the ability you chose\./);
  assert.match(disciplineRules,/Your Manifested Strike attack bonus includes this modifier, and you add the modifier to the strike’s damage roll\./);
  assert.match(disciplineRules,/Use it whenever another subclass feature refers to your Psionic Ability\./);
  assert.match(disciplineRules,/Psionic saving throw Difficulty Class = 8 \+ your Proficiency Bonus \+ your Psionic Ability modifier/);
  assert.match(rules("how_to_play"),/At Fighter level 3, choose one Kinetic Discipline; this choice is permanent\./);
  const disciplineTopic=authority.navigation.categories.find(category=>category.id==="common_features")!.topics.find(topic=>topic.id==="common_features_common_psionic_discipline_topic")!;
  assert.deepEqual(disciplineTopic.entity_ids,["common_psionic_discipline"]);
  const retrainingLanguage=authority.entities.flatMap(item=>item.content.map(block=>({id:item.id,text:blockText(block)}))).filter(({text})=>
    /\b(?:can|may)\s+(?:retrain|swap|replace|switch|change|choose (?:another|a different))\b[^.]*\b(?:Kinetic )?Discipline\b/iu.test(text)||
    /\b(?:Kinetic )?Discipline\b[^.]*\b(?:can|may)\s+be\s+(?:retrained|swapped|replaced|switched|changed)\b/iu.test(text)
  );
  assert.deepEqual(retrainingLanguage,[]);

  assert.deepEqual(listItems("common_discipline_signature_save"),[
    "Pyrokinesis: Dexterity saving throw",
    "Cryokinesis: Constitution saving throw",
    "Psychokinesis: Strength saving throw",
    "Electrokinesis: Charisma saving throw"
  ]);
  assert.ok(rules("common_discipline_signature_save").startsWith("A signature saving throw is used only when a feature specifically calls for your Discipline’s signature saving throw."));
  assert.match(rules("common_discipline_signature_save"),/A saving throw named by another feature is not replaced/);

  const reservoir=entity("common_psi_reservoir");const reservoirText=rules("common_psi_reservoir");
  for(const rule of ["only when that feature lists a Psi cost greater than 0","Manifested Strike itself costs no Psi","half your Fighter level, rounded up, plus your Proficiency Bonus","Short or Long Rest"])assert.ok(reservoirText.includes(rule),rule);
  assert.deepEqual(reservoir.content.map(block=>block.type),["paragraph","paragraph","paragraph","table"]);
  assert.deepEqual(reservoir.content[3]!.rows!.map(row=>row.map(cell=>inlineText(cell))),[["3–4","+2","4"],["5–6","+3","6"],["7–8","+3","7"],["9–10","+4","9"],["11–12","+4","10"],["13–14","+5","12"],["15–16","+5","13"],["17–18","+6","15"],["19–20","+6","16"]]);

  assert.deepEqual(listItems("common_signature_rider"),["Pyrokinesis: Ember Bolt","Cryokinesis: Glacial Spike","Psychokinesis: Telekinetic Shove","Electrokinesis: Static Discharge"]);
  const signatureRules=rules("common_signature_rider");
  for(const rule of ["Psi cost remains 0 at every tier","declare it repeatedly for any number of your Manifested Strike attacks","only one rider","pay the applicable Blood Tax","Only one rider in each Attack action can be Tier 2"])assert.ok(signatureRules.includes(rule),rule);

  const mastery=entity("common_kinetic_mastery");const masteryRules=rules("common_kinetic_mastery");
  assert.deepEqual(listItems("common_kinetic_mastery"),["Pyrokinesis: Graze","Cryokinesis: Slow","Psychokinesis: Push","Electrokinesis: Sap"]);
  const separateIndex=mastery.content.findIndex(block=>blockText(block).startsWith("Kinetic Mastery is separate from a rider"));
  const basicIndices=["Pyrokinesis — Graze","Cryokinesis — Slow","Psychokinesis — Push","Electrokinesis — Sap"].map(prefix=>mastery.content.findIndex(block=>blockText(block).startsWith(prefix)));
  const interactionIndices=["Tactical Master","Graze and the Holdout Option","Slow and Glacial Spike","Telekinetic Shove and Push","Masteries and Damage Immunity"].map(prefix=>mastery.content.findIndex(block=>blockText(block).startsWith(prefix)));
  assert.ok(separateIndex>=0&&basicIndices.every(index=>index>separateIndex)&&interactionIndices.every(index=>index>Math.max(...basicIndices)));
  for(const rule of ["does not occupy the hit’s rider slot","does not count against the number of weapons","misses, the target takes damage equal to your Psionic Ability modifier","hits a creature and deals damage","reduce its Speed by 10 feet until the start of your next turn","hits a Large or smaller creature","push it up to 10 feet straight away from you","Disadvantage on its next attack roll before the start of your next turn","replaces Kinetic Mastery rather than stacking","half your Psionic Ability modifier, rounded down","reduced by 20 feet until the start of your next turn","successful saving throw leaves the target unmoved","damage immunity does not prevent them"])assert.ok(masteryRules.includes(rule),rule);
});

test("fixed concentration durations are explicit in structured authority and rules text",async()=>{
  const {authority}=await loadAuthority();
  const expected=[
    ["advanced_beguile","Varies by tier"],
    ["advanced_gravitic_press","Up to 1 minute"],
    ["ball_lightning","Up to 1 minute"],
    ["frozen_ground","Up to 1 minute"],
    ["mass_levitation","Up to 1 minute"],
    ["vectored_thrust","Up to 10 minutes"]
  ];
  const features=authority.entities.filter(entity=>entity.concentration_duration!==undefined).sort((a,b)=>a.id.localeCompare(b.id));
  assert.deepEqual(features.map(entity=>[entity.id,entity.concentration_duration]),expected);
  assert.ok(features.every(entity=>entity.requires_concentration===true));
  for(const entity of features.filter(entity=>entity.id!=="advanced_beguile")){
    const rules=entity.content.flatMap(block=>block.inlines??[]).map(inline=>inline.text).join("\n");
    assert.ok(rules.includes(`requires Concentration for ${entity.concentration_duration!.toLowerCase()}.`),`${entity.id} is missing its canonical maximum duration`);
  }
  const beguile=authority.entities.find(entity=>entity.id==="advanced_beguile")!;const beguileRules=beguile.content.flatMap(block=>block.inlines??[]).map(inline=>inline.text).join("\n");
  assert.match(beguileRules,/T0 Base:[^\n]+up to 1 hour/);assert.equal((beguileRules.match(/up to 8 hours/g)??[]).length,2);
});


test("Mass Levitation uses five target slots, repeat-save falls, and preserves every other mechanic",async()=>{
  const {authority}=await loadAuthority();
  const feature=authority.entities.find(entity=>entity.id==="mass_levitation")!;
  const tiers=feature.content.map(block=>blockText(block));assert.equal(tiers.length,3);
  const tier0=tiers[0]!,tier1=tiers[1]!,tier2=tiers[2]!;
  for(const targetRule of [
    "When you activate this feature, you have five target slots to spend on creatures you can see within 60 feet.",
    "A Medium or smaller creature costs one slot, and a Large creature costs two slots.",
    "You can choose any combination whose total cost does not exceed five slots.",
    "A creature can be chosen only once.",
    "Unused slots are lost.",
    "Huge or larger creatures are immune."
  ])assert.ok(tier0.includes(targetRule),"Mass Levitation target rule missing: "+targetRule);

  type Target={id:string;size:"medium_or_smaller"|"large"|"huge_or_larger"};
  const medium=(id:string):Target=>({id,size:"medium_or_smaller"});
  const large=(id:string):Target=>({id,size:"large"});
  const huge=(id:string):Target=>({id,size:"huge_or_larger"});
  const slotCost=(targets:Target[])=>targets.reduce((total,target)=>total+(target.size==="medium_or_smaller"?1:target.size==="large"?2:Number.POSITIVE_INFINITY),0);
  const canChoose=(targets:Target[])=>new Set(targets.map(target=>target.id)).size===targets.length&&targets.every(target=>target.size!=="huge_or_larger")&&slotCost(targets)<=5;
  const repeated=medium("repeated");
  const cases:Array<{label:string;targets:Target[];cost:number;legal:boolean}>=[
    {label:"five Medium-or-smaller creatures",targets:[medium("m1"),medium("m2"),medium("m3"),medium("m4"),medium("m5")],cost:5,legal:true},
    {label:"two Large creatures",targets:[large("l1"),large("l2")],cost:4,legal:true},
    {label:"one Large creature and three Medium-or-smaller creatures",targets:[large("l1"),medium("m1"),medium("m2"),medium("m3")],cost:5,legal:true},
    {label:"two Large creatures and one Medium-or-smaller creature",targets:[large("l1"),large("l2"),medium("m1")],cost:5,legal:true},
    {label:"three Large creatures exceed five slots",targets:[large("l1"),large("l2"),large("l3")],cost:6,legal:false},
    {label:"two Large and two Medium-or-smaller creatures exceed five slots",targets:[large("l1"),large("l2"),medium("m1"),medium("m2")],cost:6,legal:false},
    {label:"one creature cannot be selected twice",targets:[repeated,repeated],cost:2,legal:false},
    {label:"Huge or larger creatures remain immune",targets:[huge("h1")],cost:Number.POSITIVE_INFINITY,legal:false}
  ];
  for(const selection of cases){
    assert.equal(slotCost(selection.targets),selection.cost,selection.label+" slot cost");
    assert.equal(canChoose(selection.targets),selection.legal,selection.label);
  }

  assert.deepEqual({
    id:feature.id,
    title:feature.title,
    level:feature.level,
    kind:feature.kind,
    activation:feature.activation,
    psi_cost:feature.psi_cost,
    publishable:feature.publishable,
    requires_concentration:feature.requires_concentration,
    concentration_duration:feature.concentration_duration,
    classifications:feature.classifications,
    presentation_metadata:feature.presentation_metadata
  },{
    id:"mass_levitation",
    title:"Mass Levitation",
    level:20,
    kind:"feature",
    activation:"action",
    psi_cost:5,
    publishable:true,
    requires_concentration:true,
    concentration_duration:"Up to 1 minute",
    classifications:{entity_kind:"feature",feature_role:"standalone",rules_area:["psychokinesis"]},
    presentation_metadata:{canonical_topic_by_area:{},primary_rules_area:"psychokinesis"}
  });

  const obsoleteRulings=[
    ["choose one","target group"].join(" "),
    ["cannot choose creatures","from both groups"].join(" "),
    ["descends","safely"].join(" "),
    ["safe","descent"].join(" "),
    ["takes no damage","from this tier"].join(" ")
  ];
  const activeMassRules=tiers.join("\n").toLowerCase();
  for(const obsolete of obsoleteRulings)assert.ok(!activeMassRules.includes(obsolete),"Superseded Mass Levitation ruling remains: "+obsolete);

  const repeatStart="At the start of each affected creature’s turn, it repeats the saving throw.";
  const initialSuccessStart=tier0.indexOf("On a successful save, it is unaffected.");
  assert.ok(initialSuccessStart>=0&&initialSuccessStart<tier0.indexOf(repeatStart));
  const initialSuccess=tier0.slice(initialSuccessStart,tier0.indexOf(repeatStart));
  assert.equal(initialSuccess,"On a successful save, it is unaffected. ");
  assert.doesNotMatch(initialSuccess,/lifted|Restrained|hover|fall/iu);
  assert.match(tier0,/On a failed save, it is lifted 30 feet into the air and Restrained while hovering\./u);
  assert.match(tier0,/At the start of each affected creature’s turn, it repeats the saving throw\. On a successful repeat save, the effect ends for that creature, and it falls from its current position\./u,"A successful repeat save uses the normal falling rules from the creature’s current position");
  assert.match(tier0,/If your concentration ends, all affected creatures fall\./u);
  assert.match(tier1,/Levitated creatures have Disadvantage on repeat saving throws against this feature\..*At the start of each of your turns, you can move each creature still levitated by this feature up to 15 feet.*This is forced movement/u);
  assert.ok(tier0.includes("falls from its current position"),"A creature moved by Tier 1 falls from its resulting current position on a successful repeat save");
  assert.match(tier2,/it first repeats the Strength saving throw from Tier 0\. On a successful save, the effect ends for that creature, it falls from its current position, and it takes no force damage from this tier\. On a failed save, it remains levitated and takes force damage equal to twice your Psionic Ability modifier\./u);

  assert.equal(tier0,"T0 Base: This effect requires Concentration for up to 1 minute. When you activate this feature, you have five target slots to spend on creatures you can see within 60 feet. A Medium or smaller creature costs one slot, and a Large creature costs two slots. You can choose any combination whose total cost does not exceed five slots. A creature can be chosen only once. Unused slots are lost. Huge or larger creatures are immune. Each target must make a Strength saving throw. On a failed save, it is lifted 30 feet into the air and Restrained while hovering. On a successful save, it is unaffected. At the start of each affected creature’s turn, it repeats the saving throw. On a successful repeat save, the effect ends for that creature, and it falls from its current position. While you maintain concentration, creatures that remain Restrained continue to hover. If your concentration ends, all affected creatures fall.");
  assert.equal(tier1,"T1 Overload: Changes from Tier 0: Levitated creatures have Disadvantage on repeat saving throws against this feature. At the start of each of your turns, you can move each creature still levitated by this feature up to 15 feet in any direction to an unoccupied space you can see. This is forced movement; the creature remains lifted and Restrained.");
  assert.equal(tier2,"T2 Overload: Changes from Tier 1: At the start of each levitated creature’s turn, it first repeats the Strength saving throw from Tier 0. On a successful save, the effect ends for that creature, it falls from its current position, and it takes no force damage from this tier. On a failed save, it remains levitated and takes force damage equal to twice your Psionic Ability modifier.");

  const psychokinesis=authority.navigation.categories.find(category=>category.id==="psychokinesis")!;
  const topic=psychokinesis.topics.find(candidate=>candidate.id==="psychokinesis_mass_levitation_topic")!;
  assert.deepEqual(topic,{entity_ids:["mass_levitation"],id:"psychokinesis_mass_levitation_topic",order:4,title:"Mass Levitation"});
});


test("Psi Cost Reference defines complete tier-aware Ongoing Duration values",async()=>{
  const {authority}=await loadAuthority();const reference=authority.entities.find(entity=>entity.id==="subclass_feature_reference")!;
  assert.deepEqual(reference.content.map(block=>block.type),["paragraph","table","paragraph","paragraph","table"]);
  assert.equal(blockText(reference.content[0]!),"The first table shows the features you gain at each Fighter level.");
  const progression=reference.content[1]!;assert.match(inlineText(progression.rows![0]![1]),/^Psionic Discipline \(one permanent Kinetic Discipline choice\)/);
  assert.equal(blockText(reference.content[2]!),"The second table compares each feature’s Discipline, Psi cost, activation, and ongoing duration.");
  const definition="Ongoing Duration shows how long the feature or any condition, zone, or other effect it creates can continue after its initial resolution. Damage, teleportation, and forced movement resolve immediately. ‘Varies by tier’ means the feature’s tiers have different ongoing durations.";
  assert.equal(blockText(reference.content[3]!),definition);
  const table=reference.content.find(block=>block.type==="table"&&block.headers?.some(cell=>cell.some(node=>node.text==="Ongoing Duration")))!;
  assert.equal(reference.content.indexOf(table),reference.content.indexOf(reference.content[3]!)+1);
  const cell=(nodes:any[])=>nodes.map(node=>node.text??node.label??String(node.value?.value??"")).join("");
  const headers=table.headers!.map(cell);assert.deepEqual(headers,["Level","Feature","Discipline","Psi","Activation","Ongoing Duration"]);assert.equal(headers.includes("Duration"),false);
  const rows=table.rows!.map(row=>row.map(cell));assert.ok(rows.every(row=>row.length===6&&row[5]&&row[5]!== "—"));
  assert.equal(rows.length,34);assert.equal(new Set(rows.map(row=>row[1])).size,rows.length);
  const references=table.row_references!;assert.equal(references.length,rows.length);assert.deepEqual(references.map(reference=>reference.reference_level),rows.map(row=>row[0]));
  const entityById=new Map(authority.entities.map(entity=>[entity.id,entity]));
  const groups=references.map(reference=>"entity_id" in reference?entityById.get(reference.entity_id)!.presentation_metadata.primary_rules_area:reference.reference_group);
  for(const [index,reference] of references.entries())if("entity_id" in reference){const entity=entityById.get(reference.entity_id)!;assert.equal(entity.kind,"feature");assert.equal(entity.title,rows[index]![1]);assert.equal(entity.level,Number(reference.reference_level.match(/^\d+/)?.[0]));assert.ok(entity.classifications.rules_area.includes(groups[index]!));}
  const groupCounts=groups.reduce<Record<string,number>>((counts,group)=>({...counts,[group]:(counts[group]??0)+1}),{});
  assert.deepEqual(groupCounts,{cryokinesis:5,pyrokinesis:5,psychokinesis:5,electrokinesis:5,advanced_training:13,common_features:1});
  assert.deepEqual(references.flatMap((reference,index)=>"reference_group" in reference?[[rows[index]![1],reference.reference_group,reference.reference_level]]:[]),[["Advanced Training III choice","advanced_training","15th"],["Advanced Training IV choice","advanced_training","18th"],["Advanced Training V choice","advanced_training","20th"]]);
  const acquisitions=references.flatMap(reference=>"entity_id" in reference?[entityById.get(reference.entity_id)?.classifications.acquisition_mode].filter(Boolean):[]).sort();
  assert.deepEqual(acquisitions,["granted","granted","selectable","selectable","selectable","selectable","selectable","selectable","selectable","selectable"]);
  assert.deepEqual(rows.reduce<Record<string,number>>((counts,row)=>({...counts,[row[0]!]:(counts[row[0]!]??0)+1}),{}),{"3rd":4,"5th":1,"7th":5,"10th":5,"15th":5,"18th":1,"20th":5,"15th+":7,"18th+":1});
  assert.deepEqual(rows.map(row=>[row[1],row[5]]),[["Glacial Spike","Until the end of your next turn"],["Ember Bolt","Instantaneous"],["Telekinetic Shove","Varies by tier"],["Static Discharge","Varies by tier"],["Deflection Screen","Varies by tier"],["Empathic Sense","Continuous"],["Snow Chains","Until the end of your next turn"],["Thermal Fracture","Until the start of your next turn"],["Vectored Thrust","Concentration, up to 10 minutes"],["Branching Bolt","Instantaneous"],["Frozen Ground","Concentration, up to 1 minute"],["Cinder Lance","Instantaneous"],["Explosion/Implosion","Until the end of your next turn"],["Electron Burst","Varies by tier"],["Phase Step","Varies by tier"],["Arctic Tempest","Until the end of your next turn"],["Flare","Until the end of your next turn"],["Telekinetic Slam","Varies by tier"],["Forked Lightning","Varies by tier"],["Advanced Training III choice","Varies by feature"],["Advanced Training IV choice","Varies by feature"],["Advanced Training V choice","Varies by feature"],["Mind Shred","Instantaneous"],["Beguile","Varies by tier"],["Mind Lock","Until the end of your next turn"],["Gravitic Press","Concentration, up to 1 minute"],["Barrier","Varies by tier"],["Improved Phase Step","Varies by tier"],["Overload Mastery II","Continuous"],["Inner Reserve","Continuous"],["Absolute Zero","Until the end of your next turn"],["Furnace Strike","Instantaneous"],["Mass Levitation","Concentration, up to 1 minute"],["Ball Lightning","Concentration, up to 1 minute"]]);
  const byFeature=new Map(rows.map(row=>[row[1],row]));
  assert.equal(byFeature.get("Glacial Spike")?.[4],"Declared before roll · Resolves on hit");
  assert.equal(byFeature.get("Empathic Sense")?.[4],"Passive · Bonus Action scan");
  assert.notEqual(byFeature.get("Explosion/Implosion")?.[5],"Instantaneous");
  assert.notEqual(byFeature.get("Phase Step")?.[5],"Instantaneous");
  assert.notEqual(byFeature.get("Electron Burst")?.[5],"Until the start of your next turn");
  for(const row of rows.filter(row=>row[5]?.startsWith("Concentration")))assert.match(row[5]!,/^Concentration, up to (?:1 minute|10 minutes)$/);
  assert.match(JSON.stringify(table),/Advanced Training I/);assert.match(JSON.stringify(table),/Advanced Training II/);assert.match(JSON.stringify(table),/Advanced Training pool/);
  assert.doesNotMatch(JSON.stringify(table),/\bAT(?: I| II| pool)?\b/);
  assert.match(JSON.stringify(reference.content),/Discipline 10th-Level Feature/);
});

test("final rules decisions leave every unapproved authority field unchanged",async()=>{
  const {authority}=await loadAuthority();const projection=structuredClone(authority) as any;
  delete projection.onboarding;
  projection.rules_version="<approved rules version>";
  const massLevitation=projection.entities.find((entity:any)=>entity.id==="mass_levitation");
  massLevitation.content[0].inlines[0].text=massLevitation.content[0].inlines[0].text.replace(
    /When you activate this feature,.*?(?=Each target must make a Strength saving throw\.)/u,
    "<approved Mass Levitation targeting> "
  );
  const tier0BeforeOutcomeNormalization=massLevitation.content[0].inlines[0].text;
  massLevitation.content[0].inlines[0].text=tier0BeforeOutcomeNormalization.replace(
    "On a successful repeat save, the effect ends for that creature, and it falls from its current position.",
    "<approved Mass Levitation Tier 0 successful repeat-save outcome>"
  );
  assert.notEqual(massLevitation.content[0].inlines[0].text,tier0BeforeOutcomeNormalization);
  const tier2BeforeOutcomeNormalization=massLevitation.content[2].inlines[0].text;
  massLevitation.content[2].inlines[0].text=tier2BeforeOutcomeNormalization.replace(
    "On a successful save, the effect ends for that creature, it falls from its current position, and it takes no force damage from this tier.",
    "<approved Mass Levitation Tier 2 successful repeat-save outcome>"
  );
  assert.notEqual(massLevitation.content[2].inlines[0].text,tier2BeforeOutcomeNormalization);
  const howToPlay=projection.entities.find((entity:any)=>entity.id==="how_to_play");
  const howSummary=howToPlay.content.find((block:any)=>blockText(block).includes("Deflection Screen at 5th level"));
  howSummary.inlines[0].text="Your Discipline grants five features across the subclass progression. Deflection Screen at 5th level and Phase Step at 10th level are universal psionic tools. Advanced Training III, IV, and V at 15th, 18th, and 20th levels grant three choices from the Advanced Training pool regardless of Discipline.";
  const discipline=projection.entities.find((entity:any)=>entity.id==="common_psionic_discipline");
  discipline.content[0].inlines[0].text="When you gain this feature at Fighter level 3, choose Intelligence, Wisdom, or Charisma as your Psionic Ability. This choice is separate from your Discipline.";
  discipline.content[1].inlines[0].text="Your Discipline grants its own features and determines your Manifested Strike’s damage type.";
  const reference=projection.entities.find((entity:any)=>entity.id==="subclass_feature_reference");
  const cell=(nodes:any[])=>nodes.map(node=>node.text??node.label??String(node.value?.value??"")).join("");
  const progression=reference.content.find((block:any)=>block.type==="table"&&block.headers.map(cell).join("|")==="Level|Feature");
  progression.rows[0][1][0].text="Psionic Discipline, Discipline Signature Save, Psi Reservoir, Psionic Link, Manifested Strike, Overload, Signature Rider, Kinetic Mastery, Discipline 3rd-Level Feature";
  reference.content.find((block:any)=>blockText(block).startsWith("The second table compares")).inlines[0].text="The second table compares each feature’s Discipline, Psi cost, activation, and duration.";
  const definitionIndex=reference.content.findIndex((block:any)=>blockText(block).startsWith("Ongoing Duration shows"));assert.ok(definitionIndex>=0);reference.content.splice(definitionIndex,1);
  const table=reference.content.find((block:any)=>block.type==="table"&&block.headers.map(cell).includes("Ongoing Duration"));
  table.headers[5][0].text="Duration";
  const oldDurations=new Map([["Glacial Spike","Varies by tier"],["Deflection Screen","Instantaneous"],["Empathic Sense","Continuous; scan instantaneous"],["Vectored Thrust","Up to 10 minutes"],["Frozen Ground","Up to 1 minute"],["Explosion/Implosion","Instantaneous"],["Electron Burst","Until the start of your next turn"],["Phase Step","Instantaneous"],["Arctic Tempest","Varies by tier"],["Flare","Varies by tier"],["Gravitic Press","Up to 1 minute"],["Absolute Zero","Varies by tier"],["Mass Levitation","Up to 1 minute"],["Ball Lightning","Up to 1 minute"]]);
  for(const row of table.rows){const oldDuration=oldDurations.get(cell(row[1]));if(oldDuration)row[5][0].text=oldDuration;}
  assert.equal(sha256(canonicalJson(projection)),"19a17b024da7cea260e31eacf2b382abab426eefb548479823a3705a8dd5d406");
});

test("active authority and approved UI text use full English without contractions",async()=>{
  const {authority}=await loadAuthority();const ui=JSON.parse(await readFile("ui/approved-ui-text.json","utf8"));
  const strings:string[]=[authority.metadata.title,authority.metadata.attribution,authority.metadata.license];
  for(const facet of authority.facets)strings.push(facet.label);
  for(const vocabulary of Object.values(authority.vocabularies))for(const item of vocabulary)strings.push(item.label);
  for(const category of authority.navigation.categories){strings.push(category.label);for(const topic of category.topics)strings.push(topic.title);}
  const userFacingKeys=new Set(["text","label","title","description","summary","no_psi_note","orientation","definition"]);
  const collect=(value:any):void=>{if(Array.isArray(value)){for(const child of value)if(typeof child==="string")strings.push(child);else collect(child);return;}if(!value||typeof value!=="object")return;for(const [key,child] of Object.entries(value)){if(userFacingKeys.has(key)&&typeof child==="string")strings.push(child);else collect(child);}};
  for(const entity of authority.entities){strings.push(entity.title);if(entity.concentration_duration)strings.push(entity.concentration_duration);collect(entity.content);}
  collect(authority.onboarding);
  for(const text of [...authority.onboarding.basic_turn.steps,...authority.onboarding.basic_turn.reminders])assert.ok(strings.includes(text),`Missing onboarding language-guard coverage for: ${text}`);
  for(const token of ui.tokens)strings.push(token.text??token.template);
  const contractions=/\b(?:can['’]t|won['’]t|don['’]t|doesn['’]t|isn['’]t|aren['’]t|wasn['’]t|weren['’]t|it['’]s|that['’]s|there['’]s|you['’](?:re|ve|ll|d)|we['’](?:re|ve|ll|d)|they['’](?:re|ve|ll|d)|couldn['’]t|wouldn['’]t|shouldn['’]t|mustn['’]t|haven['’]t|hasn['’]t|hadn['’]t|didn['’]t)\b/iu;
  const abbreviations=/(?:\b(?:ft|AT|PB|AC|DC|MS)\b|\b(?:Con|Str|Dex|Int|Cha) saves?\b)/u;
  for(const text of strings){assert.doesNotMatch(text,contractions,text);assert.doesNotMatch(text,abbreviations,text);}
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
  const phases=["setup","activation","rolls_or_saves","damage","effects","result"] as const;
  assert.deepEqual(sections.map(block=>block.discipline),["pyrokinesis","psychokinesis","cryokinesis","electrokinesis"]);
  assert.deepEqual(sections.map(block=>block.title.map((node:any)=>node.text).join("")),["Focused Fire — Level 11 Pyrokinesis","Aerial Repositioning — Level 11 Psychokinesis","Frozen Ground Lockdown — Level 11 Cryokinesis","Room Sweep — Level 11 Electrokinesis"]);
  for(const section of sections){
    assert.ok(phases.every(field=>Array.isArray(section[field])));
    for(const field of ["heading","title",...phases]){assert.ok(section[field].length>0);assert.ok(section[field].every((node:any)=>node.type==="text"),section.title[0].text+" "+field+" must use plain text");}
  }
  const expectedPhases=[
    {
      discipline:"pyrokinesis",
      setup:["40 feet","Armor Class 16","10 Psi","Proficiency Bonus +4","Charisma +4","1d10 Manifested Strike die"],
      activation:["resolve three attacks against the same creature, one at a time","Ember Bolt at Tier 2","8 Blood Tax","Cinder Lance at Tier 0","3 Psi","Ember Bolt at Tier 0"],
      rolls_or_saves:["9 + 10 = 19","13 + 10 = 23","7 + 10 = 17","Armor Class 16"],
      damage:["18 fire damage","21 fire damage","11 fire damage","18 + 21 + 11 = 50 fire damage"],
      effects:["no forced movement, Speed change, condition, or area effect"],
      result:["7 of 10 Psi","8 Hit Points lost to Blood Tax","used your Attack action and all three attacks","50 fire damage"]
    },
    {
      discipline:"psychokinesis",
      setup:["within 5 feet","Armor Class 16","10 Psi","Intelligence +4","open concentration slot"],
      activation:["Vectored Thrust at Tier 1","spend 2 Psi","4 Blood Tax","move to a point 30 feet from the creature’s starting position","Telekinetic Shove at Tier 0"],
      rolls_or_saves:["9 + 10 = 19","12 + 10 = 22","7 + 10 = 17","12 against Difficulty Class 16","fails its Strength saving throw"],
      damage:["13 force damage","10 force damage","8 force damage","13 + 10 + 8 = 31 force damage"],
      effects:["push the creature 10 feet","replaces Push mastery","flight provokes no Opportunity Attacks"],
      result:["30 feet from the creature’s starting position","8 of 10 Psi","4 Hit Points lost to Blood Tax","concentrating on Vectored Thrust","31 force damage","ends 10 feet from its starting position","reaction remains unused"]
    },
    {
      discipline:"cryokinesis",
      setup:["20 feet","15-foot-radius Frozen Ground Cylinder","8 Psi remaining","concentration on the difficult-terrain area"],
      activation:["Glacial Spike at Tier 0","Glacial Spike at Tier 1","4 Blood Tax","Attack 3 is a plain Manifested Strike"],
      rolls_or_saves:["10 + 10 = 20","8 + 10 = 18","12 + 10 = 22","11 against Difficulty Class 16","fails its Constitution saving throw"],
      damage:["12 cold damage","14 cold damage","9 cold damage","12 + 14 + 9 = 35 cold damage"],
      effects:["reduces the creature’s Speed by 10 feet","Speed 0 until the end of your next turn","Frozen Ground remains difficult terrain"],
      result:["8 Psi","4 Hit Points lost to Blood Tax","still concentrating on Frozen Ground","35 cold damage","Speed 0 in difficult terrain","no Psi, bonus action, reaction, or movement this turn"]
    },
    {
      discipline:"electrokinesis",
      setup:["five hostile creatures","three intended primary targets are within 60 feet","four are within 5 feet","all five fit inside the final 10-foot-radius Sphere","10 Psi"],
      activation:["fully resolve each attack before choosing the next target","Static Discharge Signature Rider at Tier 2","8 Blood Tax","Branching Bolt at Tier 0","Electron Burst at Tier 0"],
      rolls_or_saves:["9 + 10 = 19","12 + 10 = 22","7 + 10 = 17","five Static Discharge targets","12 against Difficulty Class 16","five Electron Burst targets","13 against Difficulty Class 16"],
      damage:["11 + (2 × 5) = 21 damage","10 + (8 × 2) = 26 damage","9 + (11 × 5) = 64 damage","21 + 26 + 64 = 111 lightning damage"],
      effects:["three struck primary targets receive Sap","all five fail the saving throw and cannot take reactions","secondary targets are damaged but are not hit and do not receive Sap"],
      result:["6 Psi","8 Hit Points lost to Blood Tax","111 lightning damage in total","Three primary targets are struck and Sapped","none of the five can take reactions","only Tier 2 rider used"]
    }
  ] as const;
  for(const expected of expectedPhases){const section=sections.find(item=>item.discipline===expected.discipline)!;for(const phase of phases)for(const fragment of expected[phase])assert.ok(inlineText(section[phase]).includes(fragment),`${expected.discipline} ${phase}: ${fragment}`);}

  const overloadExamples=overload.content.filter(block=>block.type==="example") as any[];
  assert.equal(overloadExamples.length,1);assert.equal(overloadExamples[0].title.map((node:any)=>node.text).join(""),"Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)");
  assert.doesNotMatch(JSON.stringify(sections),/Example assumptions:|Full Attack Turn|Sustained Turn|type":"(?:strong|emphasis)"/);
});

test("all four Signature Riders retain their approved mechanics",async()=>{
  const {authority}=await loadAuthority();
  const expected={
    glacial_spike:{rulesArea:"cryokinesis",tiers:{
      "T0 Base:":[
        "The struck target takes 2 cold damage",
        "This damage is fixed and does not scale",
        "Speed is reduced by 10 feet until the end of your next turn",
        "This reduction does not stack with itself"
      ],
      "T1 Overload: Changes from Tier 0:":[
        "must make a Constitution saving throw",
        "On a failed save, its Speed becomes 0 until the end of your next turn",
        "replacing the Tier 0 Speed reduction",
        "On a successful save, the Tier 0 Speed reduction remains"
      ],
      "T2 Overload: Changes from Tier 1:":[
        "On a failed save, the struck target is Restrained until the end of your next turn",
        "replaces Tier 1’s effect that makes its Speed 0 for that duration",
        "On a successful save, the Tier 0 Speed reduction remains"
      ]
    }},
    ember_bolt:{rulesArea:"pyrokinesis",tiers:{
      "T0 Base:":["The struck target takes 2 additional fire damage","This damage is fixed, does not scale, and has no per-Attack-action limit"],
      "T1 Overload: Changes from Tier 0:":["additional fire damage increases to 4"],
      "T2 Overload: Changes from Tier 1:":["additional fire damage increases to 6"]
    }},
    telekinetic_shove:{rulesArea:"psychokinesis",tiers:{
      "T0 Base:":[
        "The struck target takes 2 additional force damage",
        "must make a Strength saving throw",
        "On a failed save, push it 10 feet in any horizontal direction",
        "On a successful save, the target remains unmoved",
        "replaces Push mastery for that hit, whether the save succeeds or fails",
        "The target is moved only once"
      ],
      "T1 Overload: Changes from Tier 0:":["push distance increases to 15 feet"],
      "T2 Overload: Changes from Tier 1:":["push distance increases to 20 feet","On a failed save, the target’s Speed also becomes 0 until the end of your next turn"]
    }},
    static_discharge:{rulesArea:"electrokinesis",tiers:{
      "T0 Base:":[
        "The struck target takes 2 lightning damage with no saving throw",
        "Up to one other creature of your choice within 5 feet of it also takes 2 lightning damage with no saving throw"
      ],
      "T1 Overload: Changes from Tier 0:":[
        "Replace the limit of one other creature with a number of other creatures equal to your Proficiency Bonus within 5 feet of the struck target",
        "Each affected creature still takes 2 lightning damage with no saving throw"
      ],
      "T2 Overload: Changes from Tier 1:":[
        "Each affected creature still takes 2 lightning damage with no saving throw",
        "must make a Charisma saving throw",
        "On a failed save, it cannot take reactions until the start of your next turn",
        "On a successful save, it suffers no additional effect",
        "A creature makes this save even if lightning immunity prevents the damage"
      ]
    }}
  } as const;
  const tierRules=(entity:any,label:string)=>{const block=entity.content.find((candidate:any)=>candidate.type==="paragraph"&&blockText(candidate).startsWith(label));assert.ok(block,entity.id+": missing "+label);return blockText(block);};
  for(const [id,spec] of Object.entries(expected)){const entity=authority.entities.find(item=>item.id===id)!;assert.equal(entity.level,3);assert.equal(entity.activation,"on_hit");assert.equal(entity.psi_cost,0);assert.equal(entity.classifications.feature_role,"rider");assert.deepEqual(entity.classifications.rules_area,[spec.rulesArea]);const positions=Object.keys(spec.tiers).map(label=>entity.content.findIndex(block=>blockText(block).startsWith(label)));assert.deepEqual(positions,[...positions].sort((a,b)=>a-b));assert.ok(positions.every(index=>index>=0));for(const [label,fragments] of Object.entries(spec.tiers) as Array<[string,readonly string[]]>){const rules=tierRules(entity,label);for(const fragment of fragments)assert.ok(rules.includes(fragment),id+" "+label+": "+fragment);}}
  const parity=entityRules(authority.entities.find(item=>item.id==="how_to_play")!);
  assert.match(parity,/struck creature is included among the affected creatures/);
  assert.match(parity,/Every affected creature otherwise resolves the same rider damage, saving throw, conditions, and applicable effects/);
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
  for(const mechanic of ["speed becomes 0 until the end of your next turn (no save)","make a Constitution saving throw","Restrained until the end of your next turn","cannot take reactions until the start of your next turn","Stunned condition until the end of your next turn"])assert.ok(snowChains.includes(mechanic),"Snow Chains mechanic changed: "+mechanic);
  assert.match(snowChains,/Stunned condition[^.]+replaces the Restrained condition retained by Tier 1/);

  const frozenGround=rulesFor("frozen_ground");
  assert.match(frozenGround,/Speed becomes 0 until the end of the current turn/);
  assert.match(frozenGround,/Restrained condition until the end of your next turn replaces the Tier 0 effect retained by Tier 1/);
});

import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { JSDOM } from "jsdom";
import { executeBuild } from "../src/build.js";

test("prototype is self-contained, offline, and unmistakably non-release",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  assert.match(html,/NON-RELEASE PROTOTYPE/);assert.match(html,/"release_status":"prototype"/);
  assert.doesNotMatch(html,/<(?:script|link|img)[^>]+(?:src|href)=["']https?:/i);assert.doesNotMatch(html,/(?:fetch|XMLHttpRequest|localStorage|sessionStorage|indexedDB|serviceWorker)/);
  assert.doesNotMatch(html,/<input[^>]+type=["'](?:text|search|number)["']/i);assert.doesNotMatch(html,/<textarea|contenteditable|aria-autocomplete/i);
});

test("rendered rules use Tn shorthand headings and preserve cumulative tier order",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  assert.doesNotMatch(html,/\bTier \d+ Overload(?: \([^)]*\))?:/);
  assert.match(html,/T0 Base:/);
  assert.match(html,/T1 Overload: Changes from Tier 0:/);
  assert.match(html,/T2 Overload: Changes from Tier 1:/);
});

test("overload tier labels and content render as separate compact elements",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const createDom=(route:string)=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#${route}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const glacial=createDom("category=cryokinesis&topic=cryokinesis_glacial_spike_topic");const glacialDocument=glacial.window.document;
  const tiers=[...glacialDocument.querySelectorAll<HTMLElement>("#entity-glacial_spike > .feature-tier")];
  assert.deepEqual(tiers.map(tier=>({
    element:tier.tagName,
    labelElement:tier.querySelector(":scope > .feature-tier__label")?.tagName,
    label:tier.querySelector(":scope > .feature-tier__label")?.textContent,
    contentElement:tier.querySelector(":scope > .feature-tier__content")?.tagName,
    content:tier.querySelector(":scope > .feature-tier__content > p")?.textContent
  })),[
    {element:"DIV",labelElement:"DIV",label:"T0 Base",contentElement:"DIV",content:"The target takes 2 cold damage on hit (fixed, does not scale), and its Speed is reduced by 10 feet until the end of your next turn. This reduction does not stack with itself."},
    {element:"DIV",labelElement:"DIV",label:"T1 Overload",contentElement:"DIV",content:"Changes from Tier 0: The target must make a Constitution saving throw. On a failed save, Tier 1’s effect that makes its Speed 0 until the end of your next turn replaces the Tier 0 Speed reduction. On a successful save, the Tier 0 Speed reduction remains."},
    {element:"DIV",labelElement:"DIV",label:"T2 Overload",contentElement:"DIV",content:"Changes from Tier 1: On a failed save, the Restrained condition until the end of your next turn replaces Tier 1’s effect that makes its Speed 0 for that duration. On a successful save, the Tier 0 Speed reduction remains."}
  ]);
  assert.ok(tiers.every(tier=>!/^T\d/.test(tier.querySelector(".feature-tier__content")?.textContent??"")));
  const empathic=createDom("category=common_features&topic=common_features_common_empathic_sense_topic");const empathicArticle=empathic.window.document.querySelector<HTMLElement>("#entity-common_empathic_sense")!;
  assert.match(empathicArticle.querySelector(":scope > p")?.textContent??"",/^Passive: Your passive Insight/);
  assert.deepEqual([...empathicArticle.querySelectorAll(":scope > .feature-tier")].map(tier=>[tier.querySelector(".feature-tier__label")?.textContent,tier.querySelector(".feature-tier__content")?.textContent]),[["T0 Base","15-foot range."],["T1 Overload","Changes from Tier 0: Range increases to 30 feet."],["T2 Overload","Changes from Tier 1: Range increases to 60 feet."]]);
  await new Promise<void>(resolve=>setImmediate(resolve));glacial.window.close();empathic.window.close();
});

test("Name control has explicit inert activation contract",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  assert.match(html,/id="name-select"/);assert.match(html,/id="name-open"[^>]+aria-disabled="true"[^>]+aria-label="Open selected rule"/);assert.match(html,/Select a rule name, then choose Open\./);
  assert.match(html,/get\("name-select"\)\.addEventListener\("change",\s*updateOpen\)/);assert.match(html,/if\s*\(get\("name-open"\)\.getAttribute\("aria-disabled"\)\s*===\s*["']true["']\)/);
});

test("Example Play renders five consistent six-phase turns",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_common_example_play_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const article=dom.window.document.querySelector<HTMLElement>("#entity-common_example_play")!;const sections=[...article.querySelectorAll<HTMLElement>(":scope > .example-play-flow > .example-play-section")];
  assert.equal(sections.length,5);assert.deepEqual(sections.map(section=>section.querySelector("h4")?.textContent),["Glacial Spike Tier 2 Lockdown — Level 11 Cryokinesis","Focused Fire — Level 11 Pyrokinesis","Aerial Repositioning — Level 11 Psychokinesis","Frozen Ground Lockdown — Level 11 Cryokinesis","Room Sweep — Level 11 Electrokinesis"]);
  for(const section of sections){assert.deepEqual([...section.querySelectorAll<HTMLElement>(".example-play-section__phase-title")].map(node=>node.textContent),["Setup","Activation","Rolls or Saves","Damage","Effects","Result"]);assert.equal(section.querySelectorAll("strong,em").length,0);assert.equal(section.querySelectorAll(".example-play-section__phase > p").length,6);}
  for(const [index,fragments] of [[0,["12 + 7 = 19 cold damage","Restrained"]],[1,["18 + 21 + 11 = 50 fire damage"]],[2,["13 + 10 + 8 = 31 force damage","push the creature 10 feet"]],[3,["12 + 14 + 9 = 35 cold damage","Speed 0"]],[4,["111 lightning damage","three primaries are struck and Sapped"]]] as const)for(const fragment of fragments)assert.ok(sections[index]!.textContent?.includes(fragment),fragment);
  const overloadDom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_common_overload_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});assert.equal(overloadDom.window.document.querySelector("#entity-common_overload .inline-example"),null);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();overloadDom.window.close();
});

test("generated sections render Manifested Strike progression under its stable anchor only",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const createDom=(topic:string)=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=${topic}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const manifested=createDom("common_features_common_manifested_strike_topic");const manifestedDocument=manifested.window.document;
  const manifestedArticle=manifestedDocument.querySelector<HTMLElement>("#entity-common_manifested_strike")!;
  const progression=[...manifestedArticle.querySelectorAll("p")].find(paragraph=>paragraph.textContent?.startsWith("Manifested Strike die by level:"))!;
  const table=[...manifestedArticle.querySelectorAll("table")].find(candidate=>[...candidate.querySelectorAll("th")].map(cell=>cell.textContent).join("|")==="Fighter Level|MS Die")!;
  assert.deepEqual([...table.querySelectorAll("tbody td")].map(cell=>cell.textContent),["3–4","1d6","5–10","1d8","11–16","1d10","17–20","1d12"]);
  const children=[...manifestedArticle.children];const core=children.findIndex(child=>child.textContent?.startsWith("When you take the Attack action"));const progressionPosition=children.indexOf(progression);const tablePosition=children.indexOf(table.parentElement!);
  assert.equal(progressionPosition,core+1);assert.equal(tablePosition,progressionPosition+1);assert.equal((manifestedDocument.querySelector("#topic-select") as HTMLSelectElement).value,"common_features_common_manifested_strike_topic");

  const overload=createDom("common_features_common_overload_topic");const overloadDocument=overload.window.document;const overloadArticle=overloadDocument.querySelector<HTMLElement>("#entity-common_overload")!;const overloadText=overloadArticle.textContent??"";
  assert.doesNotMatch(overloadText,/Manifested Strike die by level/);assert.equal(overloadArticle.querySelector("table th")?.textContent,"Declaration");
  for(const retained of ["The Blood Tax","(3rd level)","(10th level)","more than one feature in the same turn","Critical Hits and Riders","Using Overload","Damage Immunity and Riders"])assert.ok(overloadText.includes(retained),`missing retained Overload content: ${retained}`);
  const tiers=[...overloadArticle.querySelectorAll<HTMLElement>(".feature-tier")];const overloadChildren=[...overloadArticle.children];
  assert.deepEqual(tiers.map(tier=>({element:tier.tagName,label:tier.querySelector(".feature-tier__label")?.textContent,contentElement:tier.querySelector(".feature-tier__content")?.tagName})),[{element:"DIV",label:"T1 Overload",contentElement:"DIV"},{element:"DIV",label:"T2 Overload",contentElement:"DIV"}]);
  assert.ok(overloadChildren.indexOf(tiers[0]!)<overloadChildren.indexOf(tiers[1]!));assert.equal(overloadArticle.querySelector(".inline-example"),null);assert.equal(overloadArticle.querySelector(".example-play-section,.example-turns"),null);
  const overloadParagraphs=[...overloadArticle.querySelectorAll<HTMLElement>(":scope > p")];assert.match(overloadParagraphs[0]?.textContent??"",/^Declare that you are Overloading/);assert.match(overloadParagraphs[1]?.textContent??"",/^Overload is a deliberate escalation/);
  assert.equal((overloadDocument.querySelector("#topic-select") as HTMLSelectElement).value,"common_features_common_overload_topic");
  await new Promise<void>(resolve=>setImmediate(resolve));manifested.window.close();overload.window.close();
});

test("paragraph text beginning with Example is not classified heuristically",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const marker='"text":"On your turn, when you attack with Manifested Strike,';const replacement='"text":"Example ordinary paragraph. On your turn, when you attack with Manifested Strike,';const modified=html.replace(marker,replacement);assert.notEqual(modified,html);
  const dom=new JSDOM(modified,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;assert.match(document.querySelector("article p")?.textContent??"",/^Example ordinary paragraph\./);assert.equal(document.querySelector("article .example-play-section,.inline-example"),null);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});


test("release build fails closed before emitting deployable output",async()=>{await assert.rejects(()=>executeBuild("release"),/Build blocked/);});

test("generated browser runtime initializes and Name activation is explicit",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value.replace(/[^a-zA-Z0-9_-]/g,"_")};}});
  const document=dom.window.document;assert.equal(document.querySelectorAll("#category-select option").length,6);assert.ok(document.querySelector("#rules-content article"));
  const name=document.querySelector("#name-select") as HTMLSelectElement;const open=document.querySelector("#name-open") as HTMLButtonElement;const originalUrl=dom.window.location.href;
  name.value="static_discharge";name.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.equal(dom.window.location.href,originalUrl);assert.equal(open.getAttribute("aria-disabled"),"false");assert.equal(open.getAttribute("aria-label"),"Open Static Discharge");
  open.click();assert.match(dom.window.location.hash,/entity=static_discharge/);assert.equal(name.value,"");assert.equal(open.getAttribute("aria-disabled"),"true");assert.equal(document.activeElement?.textContent,"Static Discharge");
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});

test("classification controls implement AND across facets and metadata-only results",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;const area=document.querySelector('input[data-facet="rules_area"][value="electrokinesis"]') as HTMLInputElement;area.checked=true;area.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  const role=document.querySelector("#facet-feature_role") as HTMLSelectElement;role.value="rider";role.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  const labels=[...document.querySelectorAll("#filter-results button")].map(button=>button.textContent);
  assert.deepEqual(labels,["Static Discharge — Electrokinesis","Branching Bolt — Electrokinesis","Electron Burst — Electrokinesis"]);
  assert.ok(!document.querySelector("#filter-results p span[data-source-unit]"));
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});


test("rendered filters isolate canonical areas and preserve progression order",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=psychokinesis&topic=psychokinesis_telekinetic_shove_topic&filters=rules_area:psychokinesis",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;const labels=()=>[...document.querySelectorAll("#filter-results button")].map(button=>button.textContent);
  assert.deepEqual(labels(),["Telekinetic Shove — Psychokinesis","Vectored Thrust — Psychokinesis","Explosion/Implosion — Psychokinesis","Telekinetic Slam — Psychokinesis","Mass Levitation — Psychokinesis"]);
  assert.ok(!labels().includes("Overload — Common Features"));

  const psychokinesis=document.querySelector(`input[data-facet="rules_area"][value="psychokinesis"]`) as HTMLInputElement;
  const common=document.querySelector(`input[data-facet="rules_area"][value="common_features"]`) as HTMLInputElement;
  common.checked=true;common.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  const multiple=labels();assert.equal(multiple.filter(label=>label==="Overload — Common Features").length,1);assert.ok(multiple.includes("Telekinetic Shove — Psychokinesis"));
  const firstPsychokinesis=multiple.findIndex(label=>label?.endsWith("— Psychokinesis"));assert.ok(firstPsychokinesis>0);assert.ok(multiple.slice(0,firstPsychokinesis).every(label=>label?.endsWith("— Common Features")));

  common.checked=false;common.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  const role=document.querySelector("#facet-feature_role") as HTMLSelectElement;role.value="rider";role.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.deepEqual(labels(),["Telekinetic Shove — Psychokinesis","Explosion/Implosion — Psychokinesis"]);assert.equal(psychokinesis.checked,true);assert.equal(new URLSearchParams(dom.window.location.hash.slice(1)).get("filters"),"rules_area:psychokinesis;feature_role:rider");
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});

test("feature metadata renders concentration only from structured authority",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const render=(source:string,category:string,topic:string)=>new JSDOM(source,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#category=${category}&topic=${topic}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const metadata=(document:Document,entityId:string)=>[...document.querySelectorAll<HTMLElement>(`#entity-${entityId} .feature-metadata__item`)].map(item=>({term:item.querySelector("dt")?.textContent,value:item.querySelector("dd")?.textContent,classes:item.className}));

  const gravitic=render(html,"advanced_training","advanced_training_advanced_gravitic_press_topic");
  const graviticMetadata=metadata(gravitic.window.document,"advanced_gravitic_press");
  assert.ok(graviticMetadata.some(item=>item.term==="Psi"&&item.value==="3"));
  assert.ok(graviticMetadata.some(item=>item.term==="Activation"&&item.value==="action"));
  assert.ok(graviticMetadata.some(item=>item.term==="Requirement"&&item.value==="Concentration"&&item.classes.includes("feature-metadata__item--concentration")));
  assert.equal(gravitic.window.document.querySelector("#entity-advanced_gravitic_press .feature-metadata")?.tagName,"DL");

  const levitation=render(html,"psychokinesis","psychokinesis_mass_levitation_topic");
  const levitationMetadata=metadata(levitation.window.document,"mass_levitation");
  assert.ok(levitationMetadata.some(item=>item.term==="Psi"&&item.value==="5"));
  assert.ok(levitationMetadata.some(item=>item.term==="Activation"&&item.value==="action"));
  assert.ok(levitationMetadata.some(item=>item.value==="Concentration"));

  const slam=render(html,"psychokinesis","psychokinesis_telekinetic_slam_topic");
  const slamMetadata=metadata(slam.window.document,"telekinetic_slam");
  assert.ok(slamMetadata.some(item=>item.term==="Psi"&&item.value==="3"));
  assert.ok(slamMetadata.some(item=>item.term==="Activation"&&item.value==="action"));
  assert.ok(!slamMetadata.some(item=>item.value==="Concentration"));

  const marker='"text":"You seize a foe with overwhelming telekinetic force';
  const replacement='"text":"This description mentions concentration but does not require it. You seize a foe with overwhelming telekinetic force';
  const descriptionOnlyHtml=html.replace(marker,replacement);assert.notEqual(descriptionOnlyHtml,html);
  const descriptionOnly=render(descriptionOnlyHtml,"psychokinesis","psychokinesis_telekinetic_slam_topic");
  assert.match(descriptionOnly.window.document.querySelector("#entity-telekinetic_slam p")?.textContent??"",/mentions concentration/);
  assert.equal(descriptionOnly.window.document.querySelector("#entity-telekinetic_slam .feature-metadata__item--concentration"),null);

  assert.match(html,/\.feature-metadata\{[^}]*flex-wrap:wrap/);
  const metadataCss=html.match(/\.feature-metadata\{([^}]*)\}/)?.[1]??"";
  assert.doesNotMatch(metadataCss,/(?:^|;)width:/);
  await new Promise<void>(resolve=>setImmediate(resolve));
  for(const dom of [gravitic,levitation,slam,descriptionOnly])dom.window.close();
});


test("Browse topics are category-scoped and invalid category/topic state is normalized",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const createDom=(hash="")=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html${hash}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const topicTitles=(document:Document)=>[...document.querySelectorAll<HTMLOptionElement>("#topic-select option")].map(option=>option.textContent);
  const common=createDom("#category=common_features&topic=common_features_common_overload_topic");assert.equal(topicTitles(common.window.document).filter(title=>title==="Overload").length,1);
  const category=common.window.document.querySelector("#category-select") as HTMLSelectElement;category.value="cryokinesis";category.dispatchEvent(new common.window.Event("change",{bubbles:true}));
  assert.ok(!topicTitles(common.window.document).includes("Overload"));assert.equal((common.window.document.querySelector("#topic-select") as HTMLSelectElement).value,"cryokinesis_glacial_spike_topic");assert.equal(common.window.document.querySelector("#rules-content article h2")?.textContent,"Glacial Spike");
  const invalid=createDom("#category=psychokinesis&topic=common_features_common_overload_topic");const invalidDocument=invalid.window.document;
  assert.ok(!topicTitles(invalidDocument).includes("Overload"));assert.equal((invalidDocument.querySelector("#topic-select") as HTMLSelectElement).value,"psychokinesis_telekinetic_shove_topic");assert.equal(invalidDocument.querySelector("#rules-content article h2")?.textContent,"Telekinetic Shove");assert.equal(new URLSearchParams(invalid.window.location.hash.slice(1)).get("topic"),"psychokinesis_telekinetic_shove_topic");
  const staleState={category:"cryokinesis",topic:"common_features_common_overload_topic",classifications:{},entity:"common_overload",resultRoute:"common_features_common_overload_topic",focusOrigin:"history"};
  invalid.window.dispatchEvent(new invalid.window.PopStateEvent("popstate",{state:staleState}));assert.equal((invalidDocument.querySelector("#topic-select") as HTMLSelectElement).value,"cryokinesis_glacial_spike_topic");assert.equal(invalidDocument.querySelector("#rules-content article h2")?.textContent,"Glacial Spike");assert.ok(!invalidDocument.querySelector("#entity-common_overload"));
  await new Promise<void>(resolve=>setImmediate(resolve));common.window.close();invalid.window.close();
});

import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { JSDOM } from "jsdom";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";
import { buildFilterIndex } from "../src/validate.js";

const styledAdditionOperators=/[˖∔⊕⊞➕⨁⨢⨣⨤⨥⨦⨧⨨⨭⨮⨹⨺⩱⩲⩳⩴⩵⩶⩷⩸﬩]/u;
const hasAlternateAddition=(value:string)=>/\bplus\b/iu.test(value)||[...value].some(character=>character!=="+"&&(character.normalize("NFKC")==="+"||styledAdditionOperators.test(character)));
const assertAsciiTableAddition=(values:string[],source:string)=>{for(const value of values)assert.equal(hasAlternateAddition(value),false,`${source} table cell uses a non-ASCII addition operator: ${value}`);};

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
    contentElement:tier.querySelector(":scope > .feature-tier__content")?.tagName
  })),[
    {element:"SECTION",labelElement:"H3",label:"T0 Base",contentElement:"DIV"},
    {element:"SECTION",labelElement:"H3",label:"T1 Overload",contentElement:"DIV"},
    {element:"SECTION",labelElement:"H3",label:"T2 Overload",contentElement:"DIV"}
  ]);
  assert.deepEqual(tiers.map(tier=>tier.dataset.tier),["0","1","2"]);
  assert.ok(tiers.every(tier=>(tier.querySelector(":scope > .feature-tier__content > p")?.textContent?.trim().length??0)>0));
  assert.ok(tiers.every(tier=>tier.dataset.tier&&tier.querySelector(":scope > h3.feature-tier__label")&&!/^T\d/.test(tier.querySelector(".feature-tier__content")?.textContent??"")));
  assert.equal(glacialDocument.querySelector("#entity-glacial_spike > h2")?.textContent,"Glacial Spike");assert.equal(glacialDocument.querySelector("#entity-glacial_spike [role=heading]"),null);
  const empathic=createDom("category=common_features&topic=common_features_common_empathic_sense_topic");const empathicArticle=empathic.window.document.querySelector<HTMLElement>("#entity-common_empathic_sense")!;
  assert.match(empathicArticle.querySelector(":scope > p")?.textContent??"",/^Passive: Your passive Insight/);
  assert.deepEqual([...empathicArticle.querySelectorAll(":scope > .feature-tier")].map(tier=>[tier.querySelector(".feature-tier__label")?.textContent,tier.querySelector(".feature-tier__content")?.textContent]),[["T0 Base","15-foot range."],["T1 Overload","Changes from Tier 0: Range increases to 30 feet."],["T2 Overload","Changes from Tier 1: Range increases to 60 feet."]]);
  await new Promise<void>(resolve=>setImmediate(resolve));glacial.window.close();empathic.window.close();
});

test("rendered permanent Discipline choice and Ongoing Duration reference stay explicit",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const render=(topic:string)=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=${topic}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const discipline=render("common_features_common_psionic_discipline_topic");const disciplineArticle=discipline.window.document.querySelector<HTMLElement>("#entity-common_psionic_discipline")!;
  const disciplineParagraphs=[...disciplineArticle.querySelectorAll<HTMLElement>(":scope > p")].map(paragraph=>paragraph.textContent);
  assert.equal(disciplineArticle.querySelector("h2")?.textContent,"Psionic Discipline");
  assert.equal(disciplineParagraphs[0],"When you gain this subclass at Fighter level 3, choose one Kinetic Discipline: Pyrokinesis, Cryokinesis, Psychokinesis, or Electrokinesis. Your chosen Discipline determines your Manifested Strike’s damage type, Discipline signature saving throw, Kinetic Mastery, Signature Rider, and the Discipline features you gain at Fighter levels 3, 7, 10, 15, and 20. This choice is permanent and is separate from your Psionic Ability choice.");
  assert.equal(disciplineParagraphs[1],"Choose Intelligence, Wisdom, or Charisma as your Psionic Ability. Your Psionic Ability choice does not change your Discipline.");

  const reference=render("common_features_subclass_feature_reference_topic");const referenceArticle=reference.window.document.querySelector<HTMLElement>("#entity-subclass_feature_reference")!;
  const table=[...referenceArticle.querySelectorAll<HTMLTableElement>("table")].find(candidate=>[...candidate.querySelectorAll("th")].some(cell=>cell.textContent==="Ongoing Duration"))!;
  const headers=[...table.querySelectorAll("th")].map(cell=>cell.textContent);assert.deepEqual(headers,["Level","Feature","Discipline","Psi","Activation","Ongoing Duration"]);assert.equal(headers.includes("Duration"),false);
  const definition="Ongoing Duration shows how long the feature or any condition, zone, or other effect it creates can continue after its initial resolution. Damage, teleportation, and forced movement resolve immediately. ‘Varies by tier’ means the feature’s tiers have different ongoing durations.";
  const wrapper=table.closest(".table-scroll")!;assert.equal(wrapper.previousElementSibling?.className,"reference-filters");assert.equal(wrapper.previousElementSibling?.previousElementSibling?.textContent,definition);assert.equal(table.className,"quick-reference-table");
  const rows=[...table.querySelectorAll("tbody tr")].map(row=>[...row.querySelectorAll("td")].map(cell=>cell.textContent??""));assert.equal(rows.length,34);
  const byFeature=new Map(rows.map(row=>[row[1],row[5]]));
  for(const [feature,duration] of [["Explosion/Implosion","Until the end of your next turn"],["Phase Step","Varies by tier"],["Electron Burst","Varies by tier"],["Vectored Thrust","Concentration, up to 10 minutes"],["Frozen Ground","Concentration, up to 1 minute"],["Mass Levitation","Concentration, up to 1 minute"],["Ball Lightning","Concentration, up to 1 minute"],["Gravitic Press","Concentration, up to 1 minute"],["Beguile","Varies by tier"],["Barrier","Varies by tier"],["Inner Reserve","Continuous"],["Overload Mastery II","Continuous"]] as const)assert.equal(byFeature.get(feature),duration);
  await new Promise<void>(resolve=>setImmediate(resolve));discipline.window.close();reference.window.close();
});

test("Subclass Feature Reference filters rows locally from canonical metadata",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_subclass_feature_reference_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document,table=document.querySelector<HTMLTableElement>("#psi-cost-reference-table")!;
  const show=document.querySelector<HTMLSelectElement>("#reference-show")!,level=document.querySelector<HTMLSelectElement>("#reference-level")!;
  assert.equal(show.closest("label")?.textContent?.startsWith("Show"),true);assert.equal(level.closest("label")?.textContent?.startsWith("Level"),true);
  assert.deepEqual([...show.options].map(option=>option.textContent),["All features","Common features","Pyrokinesis","Cryokinesis","Psychokinesis","Electrokinesis","Advanced Training"]);
  assert.deepEqual([...level.options].map(option=>option.textContent),["All levels","3rd","5th","7th","10th","15th","18th","20th","15th+","18th+"]);
  assert.equal(show.value,"");assert.equal(level.value,"");assert.equal(show.tabIndex,0);assert.equal(level.tabIndex,0);
  assert.equal(document.querySelector('label[for="reference-show"]')?.contains(show),true);assert.equal(document.querySelector('label[for="reference-level"]')?.contains(level),true);
  assert.equal(show.getAttribute("aria-controls"),table.id);assert.equal(level.getAttribute("aria-controls"),table.id);assert.equal(table.getAttribute("aria-describedby"),"reference-filter-count");
  const rows=[...table.querySelectorAll<HTMLTableRowElement>("tbody tr")],originalRows=[...rows];assert.equal(rows.length,34);
  const thead=table.tHead,feature=(row:HTMLTableRowElement)=>row.cells[1]!.textContent??"",visible=()=>rows.filter(row=>!row.classList.contains("reference-row--filtered")).map(feature);
  const expectedGroups:Record<string,string[]>={common_features:["Empathic Sense"],pyrokinesis:["Ember Bolt","Thermal Fracture","Cinder Lance","Flare","Furnace Strike"],cryokinesis:["Glacial Spike","Snow Chains","Frozen Ground","Arctic Tempest","Absolute Zero"],psychokinesis:["Telekinetic Shove","Vectored Thrust","Explosion/Implosion","Telekinetic Slam","Mass Levitation"],electrokinesis:["Static Discharge","Branching Bolt","Electron Burst","Forked Lightning","Ball Lightning"],advanced_training:["Deflection Screen","Phase Step","Advanced Training III choice","Advanced Training IV choice","Advanced Training V choice","Mind Shred","Beguile","Mind Lock","Gravitic Press","Barrier","Improved Phase Step","Overload Mastery II","Inner Reserve"]};
  for(const [group,features] of Object.entries(expectedGroups))assert.deepEqual(rows.filter(row=>row.dataset.referenceGroup===group).map(feature),features,group);
  assert.ok(rows.every(row=>row.dataset.referenceGroup&&row.dataset.referenceLevel));for(const choice of ["Advanced Training III choice","Advanced Training IV choice","Advanced Training V choice"])assert.equal(rows.find(row=>feature(row)===choice)?.dataset.referenceEntity,undefined);
  const progressionRows=[...document.querySelectorAll<HTMLTableRowElement>("#entity-subclass_feature_reference table:not(.quick-reference-table) tbody tr")];
  assert.ok(progressionRows.length>0);assert.ok(progressionRows.every(row=>!row.dataset.referenceGroup&&!row.dataset.referenceLevel&&!row.classList.contains("reference-row--filtered")));
  const count=document.querySelector<HTMLElement>("#reference-filter-count")!,noMatches=document.querySelector<HTMLElement>("#reference-filter-no-matches")!,live=document.querySelector<HTMLElement>("#reference-filter-live")!;
  assert.equal(count.textContent,"Showing 34 of 34 features.");assert.equal(noMatches.hidden,true);
  assert.equal(live.getAttribute("role"),"status");assert.equal(live.getAttribute("aria-live"),"polite");assert.equal(live.getAttribute("aria-atomic"),"true");
  const globalState=()=>({hash:dom.window.location.hash,history:dom.window.history.length,category:(document.querySelector("#category-select") as HTMLSelectElement).value,topic:(document.querySelector("#topic-select") as HTMLSelectElement).value,name:[...document.querySelectorAll<HTMLOptionElement>("#name-select option")].map(option=>[option.value,option.textContent]),facets:[...document.querySelectorAll<HTMLInputElement|HTMLSelectElement>("#facet-controls input,#facet-controls select")].map((control:any)=>[control.id,control.dataset.facet,control.value,"checked" in control?control.checked:null]),results:document.querySelector("#filter-results")?.textContent});const globalSnapshot=globalState();
  const change=async(select:HTMLSelectElement,value:string)=>{select.value=value;select.focus();select.dispatchEvent(new dom.window.Event("change",{bubbles:true}));await new Promise<void>(resolve=>setImmediate(resolve));assert.equal(document.activeElement,select);};
  const apply=async(showValue:string,levelValue:string)=>{if(show.value!==showValue)await change(show,showValue);if(level.value!==levelValue)await change(level,levelValue);};
  for(const [group,features] of Object.entries(expectedGroups)){await apply(group,"");assert.deepEqual(visible(),features);assert.equal(count.textContent,`Showing ${features.length} of 34 features.`);}
  await apply("","");assert.deepEqual(visible(),rows.map(feature));
  const levelCounts:Record<string,number>={"3rd":4,"5th":1,"7th":5,"10th":5,"15th":5,"18th":1,"20th":5,"15th+":7,"18th+":1};
  for(const [referenceLevel,expected] of Object.entries(levelCounts)){await apply("",referenceLevel);assert.equal(visible().length,expected,referenceLevel);assert.equal(count.textContent,`Showing ${expected} of 34 features.`);}
  await apply("advanced_training","15th+");
  assert.deepEqual(visible(),["Mind Shred","Beguile","Mind Lock","Gravitic Press","Barrier","Improved Phase Step","Inner Reserve"]);
  assert.equal(count.textContent,"Showing 7 of 34 features.");
  await apply("common_features","3rd");
  assert.deepEqual(visible(),[]);assert.equal(count.textContent,"Showing 0 of 34 features.");
  assert.equal(noMatches.hidden,false);assert.equal(noMatches.textContent,"No features match the selected filters.");assert.equal(live.textContent,"No features match the selected filters. Showing 0 of 34 features.");
  assert.equal(document.activeElement,level);assert.equal(table.tHead,thead);assert.ok(thead?.isConnected);assert.equal(thead?.querySelectorAll("th").length,6);
  assert.equal(table.querySelectorAll("tbody tr").length,34);assert.ok(originalRows.every((row,index)=>row===table.tBodies[0]!.rows[index]&&row.isConnected));
  assert.deepEqual(globalState(),globalSnapshot);
  const name=document.querySelector<HTMLSelectElement>("#name-select")!;name.value="glacial_spike";name.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.ok(document.querySelector("#entity-glacial_spike"));assert.match(dom.window.location.hash,/category=cryokinesis&topic=cryokinesis_glacial_spike_topic&entity=glacial_spike/);
  assert.equal(document.querySelector(".reference-filters"),null);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});

test("Name control uses committed selection without redundant Open UI",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  assert.match(html,/<label for="name-select">Name<\/label><select id="name-select"><\/select>/);
  assert.match(html,/get\("name-select"\)\.addEventListener\("change",\s*event\s*=>\s*openEntity\(event\.target\.value,\s*"name"\)\)/);
  assert.doesNotMatch(html,/id="name-open"|name-row|Open selected rule|Select a rule name, then choose Open\.|Choosing a name does not navigate until you choose Open\./);
  assert.match(html,/\.controls select\{width:100%;min-width:0\}/);
});

test("generated publication uses centralized warm dark theme tokens",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const style=html.match(/<style>([\s\S]*?)<\/style>/)?.[1]??"";
  assert.match(style,/:root\{color-scheme:dark;/);
  for(const token of ["--bg","--panel","--control-bg","--control-hover","--control-active","--control-disabled","--ink","--muted","--accent","--focus","--line","--selected-bg","--note-bg"]){
    assert.match(style,new RegExp(`${token}:#[0-9a-f]{6}`),`${token} must be a shared theme token`);
  }
  for(const sharedHook of [
    /body\{[^}]*background:var\(--bg\)[^}]*color:var\(--ink\)/,
    /\.panel,article\{[^}]*background:var\(--panel\)[^}]*border:1px solid var\(--line\)/,
    /select,button\{[^}]*border:1px solid var\(--line-strong\)[^}]*background:var\(--control-bg\)[^}]*color:var\(--ink\)/,
    /fieldset label:has\(input:checked\)\{[^}]*background:var\(--selected-bg\)[^}]*color:var\(--accent-strong\)/,
    /\.note\{[^}]*border-left:\.3rem solid var\(--accent\)[^}]*background:var\(--note-bg\)/,
    /:focus-visible\{outline:3px solid var\(--focus\)/
  ])assert.match(style,sharedHook);
  for(const legacyLightColor of ["#f7f3ea","#fffdfa","#17202a","#5d6873","#d6cfc2"])assert.equal(style.includes(legacyLightColor),false,`${legacyLightColor} must not remain in the default theme`);
});

test("rendered Name options derive level-name-ID order from canonical data and rebuild with filters",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const {authority}=await loadAuthority();
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_subclass_feature_reference_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document,entityById=new Map(authority.entities.map(entity=>[entity.id,entity]));
  const rulesAreas=authority.vocabularies.rules_areas!;const expectedGroupLabels=[...rulesAreas].sort((a,b)=>a.order-b.order).map(area=>area.label);
  const groups=()=>[...document.querySelectorAll<HTMLOptGroupElement>("#name-select optgroup")];
  assert.deepEqual(groups().map(group=>group.label),expectedGroupLabels);
  for(const group of groups()){
    const area=rulesAreas.find(value=>value.label===group.label)!;
    const visibleFeatureIds=[...group.querySelectorAll<HTMLOptionElement>(":scope > option")].map(option=>option.value).filter(id=>entityById.get(id)?.kind==="feature");
    const expectedFeatureIds=authority.entities
      .filter(entity=>entity.kind==="feature"&&entity.presentation_metadata.primary_rules_area===area.id)
      .sort((a,b)=>Number(a.level)-Number(b.level)||(a.title<b.title?-1:a.title>b.title?1:0)||(a.id<b.id?-1:a.id>b.id?1:0))
      .map(entity=>entity.id);
    assert.deepEqual(visibleFeatureIds,expectedFeatureIds,`${group.label} feature option order`);
  }
  const pyrokinesis=groups().find(group=>group.label==="Pyrokinesis")!;
  const pyrokinesisIds=[...pyrokinesis.querySelectorAll<HTMLOptionElement>(":scope > option")].map(option=>option.value);
  assert.ok(pyrokinesisIds.indexOf("thermal_fracture")<pyrokinesisIds.indexOf("furnace_strike"));
  const advanced=groups().find(group=>group.label==="Advanced Training")!;
  const advancedOptions=[...advanced.querySelectorAll<HTMLOptionElement>(":scope > option")],allOptions=[...document.querySelectorAll<HTMLOptionElement>("#name-select option")].filter(option=>option.value);
  assert.deepEqual(advancedOptions.slice(0,2).map(option=>option.textContent),["Deflection Screen","Phase Step"]);
  assert.equal(new Set(allOptions.map(option=>option.value)).size,allOptions.length);
  assert.equal(allOptions.filter(option=>option.textContent==="Deflection Screen").length,1);
  assert.equal(allOptions.filter(option=>option.textContent==="Phase Step").length,1);
  assert.equal(allOptions.some(option=>option.textContent==="Advanced Training I: Deflection Screen"||option.textContent==="Advanced Training II: Phase Step"),false);
  assert.equal(advanced.querySelector('option[value="advanced_deflection_screen"]')?.textContent,"Deflection Screen");
  assert.equal(advanced.querySelector('option[value="advanced_phase_step"]')?.textContent,"Phase Step");
  const referenceText=document.querySelector("#entity-subclass_feature_reference")?.textContent??"";assert.match(referenceText,/Discipline 10th-Level Feature, Phase Step, Tier 2 Overload/);assert.doesNotMatch(referenceText,/Advanced Training II \(Phase Step\)/);
  const area=document.querySelector('input[data-facet="rules_area"][value="pyrokinesis"]') as HTMLInputElement;
  area.checked=true;area.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.deepEqual(groups().map(group=>group.label),["Pyrokinesis"]);
  assert.deepEqual([...groups()[0]!.querySelectorAll<HTMLOptionElement>(":scope > option")].map(option=>option.value),pyrokinesisIds);
  area.checked=false;area.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  const advancedArea=document.querySelector('input[data-facet="rules_area"][value="advanced_training"]') as HTMLInputElement;
  advancedArea.checked=true;advancedArea.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.deepEqual(groups().map(group=>group.label),["Advanced Training"]);
  const rebuiltLabels=[...groups()[0]!.querySelectorAll<HTMLOptionElement>(":scope > option")].map(option=>option.textContent);
  assert.deepEqual(rebuiltLabels.slice(0,2),["Deflection Screen","Phase Step"]);assert.equal(new Set(rebuiltLabels).size,rebuiltLabels.length);assert.equal(rebuiltLabels.some(label=>label?.startsWith("Advanced Training I:")||label?.startsWith("Advanced Training II:")),false);
  advancedArea.checked=false;advancedArea.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.deepEqual(groups().map(group=>group.label),expectedGroupLabels);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});

test("Example Play keeps four full turns and Overload keeps one Glacial example",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_common_example_play_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const article=dom.window.document.querySelector<HTMLElement>("#entity-common_example_play")!;const sections=[...article.querySelectorAll<HTMLElement>(":scope > .example-play-flow > .example-play-section")];
  assert.equal(sections.length,4);assert.deepEqual(sections.map(section=>section.querySelector("h4")?.textContent),["Focused Fire — Level 11 Pyrokinesis","Aerial Repositioning — Level 11 Psychokinesis","Frozen Ground Lockdown — Level 11 Cryokinesis","Room Sweep — Level 11 Electrokinesis"]);
  for(const section of sections){assert.deepEqual([...section.querySelectorAll<HTMLElement>(".example-play-section__phase-title")].map(node=>node.textContent),["Setup","Activation","Rolls or Saves","Damage","Effects","Result"]);assert.equal(section.querySelectorAll("strong,em").length,0);assert.equal(section.querySelectorAll(".example-play-section__phase > p").length,6);}
  for(const [index,fragments] of [[0,["18 + 21 + 11 = 50 fire damage"]],[1,["13 + 10 + 8 = 31 force damage","push the creature 10 feet"]],[2,["12 + 14 + 9 = 35 cold damage","Speed 0"]],[3,["111 lightning damage","Three primary targets are struck and Sapped"]]] as const)for(const fragment of fragments)assert.ok(sections[index]!.textContent?.includes(fragment),fragment);
  const overloadDom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_common_overload_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});const inline=overloadDom.window.document.querySelector<HTMLElement>("#entity-common_overload .inline-example")!;assert.equal(overloadDom.window.document.querySelectorAll("#entity-common_overload .inline-example").length,1);assert.equal(inline.querySelector("h3")?.textContent,"Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)");assert.match(inline.textContent??"",/Glacial Spike at Tier 2.*1d10.*Blood Tax: 2 × Proficiency Bonus = 2 × 4 = 8.*Miss: Glacial Spike does not resolve/s);assert.equal(article.textContent?.includes("Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)"),false);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();overloadDom.window.close();
});

test("generated sections render Manifested Strike progression under its stable anchor only",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const createDom=(topic:string)=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=${topic}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const manifested=createDom("common_features_common_manifested_strike_topic");const manifestedDocument=manifested.window.document;
  const manifestedArticle=manifestedDocument.querySelector<HTMLElement>("#entity-common_manifested_strike")!;
  const progression=[...manifestedArticle.querySelectorAll("p")].find(paragraph=>paragraph.textContent?.startsWith("Manifested Strike die by level:"))!;
  const table=[...manifestedArticle.querySelectorAll("table")].find(candidate=>[...candidate.querySelectorAll("th")].map(cell=>cell.textContent).join("|")==="Fighter Level|Manifested Strike Die")!;
  assert.deepEqual([...table.querySelectorAll("tbody td")].map(cell=>cell.textContent),["3–4","1d6","5–10","1d8","11–16","1d10","17–20","1d12"]);
  const children=[...manifestedArticle.children];const position=(prefix:string)=>children.findIndex(child=>child.textContent?.startsWith(prefix));const progressionPosition=children.indexOf(progression);const tablePosition=children.indexOf(table.parentElement!);
  const orderedCore=[position("When you take the Attack action"),position("Your attack bonus equals"),position("On a hit, the strike deals one Manifested Strike die"),progressionPosition,tablePosition,position("Manifested Strike costs no Psi"),position("On a critical hit")];
  assert.deepEqual(orderedCore,[...orderedCore].sort((a,b)=>a-b));assert.equal(new Set(orderedCore).size,orderedCore.length);assert.ok(orderedCore.every(index=>index>=0));assert.equal(tablePosition,progressionPosition+1);assert.ok(orderedCore.at(-1)!<position("For feats, Fighting Styles"));
  assert.match(manifestedArticle.textContent??"",/range of 60 feet.*Psionic Ability modifier \+ your Proficiency Bonus \+ your Psionic Focus bonus.*one Manifested Strike die \+ your Psionic Ability modifier.*Discipline determines the strike’s damage type/s);assert.equal((manifestedDocument.querySelector("#topic-select") as HTMLSelectElement).value,"common_features_common_manifested_strike_topic");

  const overload=createDom("common_features_common_overload_topic");const overloadDocument=overload.window.document;const overloadArticle=overloadDocument.querySelector<HTMLElement>("#entity-common_overload")!;const overloadText=overloadArticle.textContent??"";
  assert.doesNotMatch(overloadText,/Manifested Strike die by level/);assert.equal(overloadArticle.querySelector("table th")?.textContent,"Declaration");
  for(const retained of ["Pay Blood Tax immediately","(3rd level)","(10th level)","more than one feature in the same turn","Critical Hits and Riders","Multiple Overloads and Tier 2 Riders","Damage Immunity and Riders"])assert.ok(overloadText.includes(retained),"missing retained Overload content: "+retained);
  const tiers=[...overloadArticle.querySelectorAll<HTMLElement>(".feature-tier")];const overloadChildren=[...overloadArticle.children];
  assert.deepEqual(tiers.map(tier=>({element:tier.tagName,label:tier.querySelector(".feature-tier__label")?.textContent,contentElement:tier.querySelector(".feature-tier__content")?.tagName})),[{element:"SECTION",label:"T1 Overload",contentElement:"DIV"},{element:"SECTION",label:"T2 Overload",contentElement:"DIV"}]);
  assert.ok(overloadChildren.indexOf(tiers[0]!)<overloadChildren.indexOf(tiers[1]!));const inline=overloadArticle.querySelector<HTMLElement>(".inline-example")!;assert.equal(overloadArticle.querySelectorAll(".inline-example").length,1);assert.equal(overloadChildren.indexOf(inline),overloadChildren.indexOf(tiers[1]!)+1);assert.equal(overloadArticle.querySelector(".example-play-section,.example-turns"),null);
  const overloadParagraphs=[...overloadArticle.querySelectorAll<HTMLElement>(":scope > p")];assert.match(overloadParagraphs[0]?.textContent??"",/^Overload strengthens a rider or standalone psionic feature/);assert.match(overloadParagraphs[1]?.textContent??"",/^Pay Blood Tax immediately/);
  assert.equal((overloadDocument.querySelector("#topic-select") as HTMLSelectElement).value,"common_features_common_overload_topic");
  await new Promise<void>(resolve=>setImmediate(resolve));manifested.window.close();overload.window.close();
});

test("table formulae use literal ASCII + in source and rendered output",async()=>{
  assert.equal(hasAlternateAddition("PB + INT"),false);
  for(const alternate of ["PB plus INT","level ＋ 1","PB ➕ INT"])assert.equal(hasAlternateAddition(alternate),true,alternate);
  const {authority}=await loadAuthority();
  const tableEntities=authority.entities.filter(entity=>entity.content.some(block=>block.type==="table"));
  const canonicalCells=tableEntities.flatMap(entity=>entity.content.filter(block=>block.type==="table").flatMap(block=>[...(block.headers??[]),...(block.rows??[]).flat()]).map(cell=>cell.map(node=>node.text??node.label??String(node.value?.value??"")).join("")));
  assertAsciiTableAddition(canonicalCells,"canonical authority");
  assert.ok(canonicalCells.includes("Rider cost + feature cost"));
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  for(const entity of tableEntities){
    const route=authority.navigation.categories.flatMap(category=>category.topics.map(topic=>({category,topic}))).find(({topic})=>topic.entity_ids.includes(entity.id))!;
    const dom=new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#category=${route.category.id}&topic=${route.topic.id}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
    const renderedCells=[...dom.window.document.querySelectorAll<HTMLElement>(`#entity-${entity.id} table th, #entity-${entity.id} table td`)].map(cell=>cell.textContent??"");
    assert.ok(renderedCells.length>0,`${entity.id} did not render its table`);assertAsciiTableAddition(renderedCells,`rendered ${entity.id}`);dom.window.close();
  }
});

test("paragraph text beginning with Example is not classified heuristically",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const marker='"text":"Resolve attacks one at a time.';const replacement='"text":"Example ordinary paragraph. Resolve attacks one at a time.';const modified=html.replace(marker,replacement);assert.notEqual(modified,html);
  const dom=new JSDOM(modified,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;assert.match(document.querySelector("article p")?.textContent??"",/^Example ordinary paragraph\./);assert.equal(document.querySelector("article .example-play-section,.inline-example"),null);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});


test("release build fails closed before emitting deployable output",async()=>{await assert.rejects(()=>executeBuild("release"),/Build blocked/);});

test("committed Name selection opens exactly once, preserves history state, and remains synchronized",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  let pushCount=0;
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value.replace(/[^a-zA-Z0-9_-]/g,"_")};const push=window.history.pushState.bind(window.history);window.history.pushState=(...args:any[])=>{pushCount++;return push(...args);};}});
  const document=dom.window.document;assert.equal(document.querySelectorAll("#category-select option").length,6);assert.ok(document.querySelector("#rules-content article"));
  const name=document.querySelector("#name-select") as HTMLSelectElement;assert.equal(document.querySelector("#name-open"),null);assert.equal(name.value,"");
  const area=document.querySelector('input[data-facet="rules_area"][value="advanced_training"]') as HTMLInputElement;const kind=document.querySelector("#facet-entity_kind") as HTMLSelectElement;const role=document.querySelector("#facet-feature_role") as HTMLSelectElement;const acquisition=document.querySelector("#facet-acquisition_mode") as HTMLSelectElement;const initialArticle=document.querySelector("#rules-content article");
  area.checked=true;area.dispatchEvent(new dom.window.Event("change",{bubbles:true}));kind.value="feature";kind.dispatchEvent(new dom.window.Event("change",{bubbles:true}));role.value="standalone";role.dispatchEvent(new dom.window.Event("change",{bubbles:true}));acquisition.value="granted";acquisition.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assert.equal(pushCount,4);assert.equal(name.value,"");assert.equal(document.querySelector("#rules-content article"),initialArticle);assert.match(dom.window.location.hash,/filters=rules_area%3Aadvanced_training%3Bentity_kind%3Afeature%3Bfeature_role%3Astandalone%3Bacquisition_mode%3Agranted/);
  const content=document.querySelector("#rules-content")!;const observer=new dom.window.MutationObserver(()=>{});observer.observe(content,{childList:true});
  name.focus();
  name.value="advanced_deflection_screen";name.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  const openedArticle=document.querySelector("#entity-advanced_deflection_screen");
  assert.equal(pushCount,5);assert.ok(openedArticle);assert.equal(document.querySelector("#rules-content article h2")?.textContent,"Deflection Screen");assert.equal(name.value,"advanced_deflection_screen");assert.equal(document.activeElement,name);
  const route=new URLSearchParams(dom.window.location.hash.slice(1));assert.equal(route.get("category"),"advanced_training");assert.equal(route.get("topic"),"advanced_training_advanced_deflection_screen_topic");assert.equal(route.get("entity"),"advanced_deflection_screen");assert.equal(route.get("filters"),null);
  assert.equal((document.querySelector('input[data-facet="rules_area"][value="advanced_training"]') as HTMLInputElement).checked,false);assert.equal((document.querySelector("#facet-entity_kind") as HTMLSelectElement).value,"");assert.equal((document.querySelector("#facet-feature_role") as HTMLSelectElement).value,"");assert.equal((document.querySelector("#facet-acquisition_mode") as HTMLSelectElement).value,"");
  const addedArticles=observer.takeRecords().flatMap(record=>[...record.addedNodes]).filter(node=>node.nodeType===1&&(node as Element).matches("article"));assert.equal(addedArticles.length,1);
  name.dispatchEvent(new dom.window.Event("change",{bubbles:true}));assert.equal(pushCount,5);assert.equal(document.querySelector("#rules-content article"),openedArticle);assert.equal(observer.takeRecords().length,0);
  name.value="";name.dispatchEvent(new dom.window.Event("change",{bubbles:true}));assert.equal(pushCount,5);assert.equal(document.querySelector("#rules-content article"),openedArticle);
  const restored=new Promise<void>(resolve=>dom.window.addEventListener("popstate",()=>resolve(),{once:true}));dom.window.history.back();await restored;
  assert.equal((document.querySelector('input[data-facet="rules_area"][value="advanced_training"]') as HTMLInputElement).checked,true);assert.equal((document.querySelector("#facet-entity_kind") as HTMLSelectElement).value,"feature");assert.equal((document.querySelector("#facet-feature_role") as HTMLSelectElement).value,"standalone");assert.equal((document.querySelector("#facet-acquisition_mode") as HTMLSelectElement).value,"granted");assert.equal(name.value,"");assert.match(dom.window.location.hash,/filters=rules_area%3Aadvanced_training%3Bentity_kind%3Afeature%3Bfeature_role%3Astandalone%3Bacquisition_mode%3Agranted/);
  const forwarded=new Promise<void>(resolve=>dom.window.addEventListener("popstate",()=>resolve(),{once:true}));dom.window.history.forward();await forwarded;
  assert.equal(name.value,"advanced_deflection_screen");assert.ok(document.querySelector("#entity-advanced_deflection_screen"));assert.equal(pushCount,5);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});

test("Any classifications expose the complete canonical result set in a compact disclosure",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const {authority}=await loadAuthority();const index=buildFilterIndex(authority);
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;const disclosure=document.querySelector<HTMLDetailsElement>("#filter-results details.results__all")!;
  assert.ok(disclosure);assert.equal(disclosure.open,false);assert.equal(disclosure.querySelector("summary")?.textContent,index.entities.length+" matches.");
  const buttons=[...disclosure.querySelectorAll<HTMLButtonElement>("button")];assert.equal(buttons.length,index.entities.length);
  assert.deepEqual(buttons.map(button=>button.textContent),index.entities.map(entity=>entity.title+" — "+authority.vocabularies.rules_areas!.find(area=>area.id===entity.primary_rules_area)!.label));
  assert.doesNotMatch(document.querySelector("#filter-results")?.textContent??"",/Select at least one classification/);
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
  assert.ok(graviticMetadata.some(item=>item.term==="Activation"&&item.value==="Action"));
  assert.ok(graviticMetadata.some(item=>item.term==="Requirement"&&item.value==="Concentration"&&item.classes.includes("feature-metadata__item--concentration")));
  assert.equal(gravitic.window.document.querySelector("#entity-advanced_gravitic_press .feature-metadata")?.tagName,"DL");

  const levitation=render(html,"psychokinesis","psychokinesis_mass_levitation_topic");
  const levitationMetadata=metadata(levitation.window.document,"mass_levitation");
  assert.ok(levitationMetadata.some(item=>item.term==="Psi"&&item.value==="5"));
  assert.ok(levitationMetadata.some(item=>item.term==="Activation"&&item.value==="Action"));
  assert.ok(levitationMetadata.some(item=>item.value==="Concentration"));

  const frozen=render(html,"cryokinesis","cryokinesis_frozen_ground_topic");
  const vectored=render(html,"psychokinesis","psychokinesis_vectored_thrust_topic");
  const ball=render(html,"electrokinesis","electrokinesis_ball_lightning_topic");
  const beguile=render(html,"advanced_training","advanced_training_advanced_beguile_topic");
  for(const [dom,entityId,duration] of [
    [gravitic,"advanced_gravitic_press","Up to 1 minute"],
    [levitation,"mass_levitation","Up to 1 minute"],
    [frozen,"frozen_ground","Up to 1 minute"],
    [vectored,"vectored_thrust","Up to 10 minutes"],
    [ball,"ball_lightning","Up to 1 minute"],
    [beguile,"advanced_beguile","Varies by tier"]
  ] as const)assert.ok(metadata(dom.window.document,entityId).some(item=>item.term==="Duration"&&item.value===duration),`${entityId} duration metadata is missing`);

  const rider=render(html,"cryokinesis","cryokinesis_glacial_spike_topic");
  const manifested=render(html,"common_features","common_features_common_manifested_strike_topic");
  const empathic=render(html,"common_features","common_features_common_empathic_sense_topic");
  assert.ok(metadata(rider.window.document,"glacial_spike").some(item=>item.term==="Activation"&&item.value==="Declared before roll · Resolves on hit"));
  assert.ok(metadata(manifested.window.document,"common_manifested_strike").some(item=>item.term==="Activation"&&item.value==="Attack action · Replaces an attack"));
  assert.ok(metadata(empathic.window.document,"common_empathic_sense").some(item=>item.term==="Activation"&&item.value==="Passive · Bonus Action scan"));
  for(const document of [gravitic.window.document,levitation.window.document,rider.window.document,manifested.window.document,empathic.window.document])assert.doesNotMatch(document.querySelector(".feature-metadata")?.textContent??"",/on_hit|bonus_action/);

  const slam=render(html,"psychokinesis","psychokinesis_telekinetic_slam_topic");
  const slamMetadata=metadata(slam.window.document,"telekinetic_slam");
  assert.ok(slamMetadata.some(item=>item.term==="Psi"&&item.value==="3"));
  assert.ok(slamMetadata.some(item=>item.term==="Activation"&&item.value==="Action"));
  assert.ok(!slamMetadata.some(item=>item.value==="Concentration"));
  assert.ok(!slamMetadata.some(item=>item.term==="Duration"));

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
  for(const dom of [gravitic,levitation,frozen,vectored,ball,beguile,rider,manifested,empathic,slam,descriptionOnly])dom.window.close();
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

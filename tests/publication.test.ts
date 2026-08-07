import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { JSDOM } from "jsdom";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";
import { buildFilterIndex } from "../src/validate.js";

const defaultReferenceFragment="#category=common_features&topic=common_features_how_to_play_topic";
const styledAdditionOperators=/[˖∔⊕⊞➕⨁⨢⨣⨤⨥⨦⨧⨨⨭⨮⨹⨺⩱⩲⩳⩴⩵⩶⩷⩸﬩]/u;
const hasAlternateAddition=(value:string)=>/\bplus\b/iu.test(value)||[...value].some(character=>character!=="+"&&(character.normalize("NFKC")==="+"||styledAdditionOperators.test(character)));
const assertAsciiTableAddition=(values:string[],source:string)=>{for(const value of values)assert.equal(hasAlternateAddition(value),false,`${source} table cell uses a non-ASCII addition operator: ${value}`);};

test("prototype is self-contained, offline, and unmistakably non-release",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  assert.match(html,/NON-RELEASE PROTOTYPE/);assert.match(html,/"release_status":"prototype"/);assert.match(html,/<div class="versions"><span>Rules version: 14\.1\.0<\/span><\/div>/);
  assert.doesNotMatch(html,/<(?:script|link|img)[^>]+(?:src|href)=["']https?:/i);assert.doesNotMatch(html,/(?:fetch|XMLHttpRequest|localStorage|sessionStorage|indexedDB|serviceWorker)/);
  assert.doesNotMatch(html,/<input[^>]+type=["'](?:text|search|number)["']/i);assert.doesNotMatch(html,/<textarea|contenteditable|aria-autocomplete/i);
  assert.doesNotMatch(html,/Application version|application_version|0\.1\.0/);
  const provenanceSource=html.match(/<script type="application\/json" id="publication-provenance">([^<]+)<\/script>/)?.[1];assert.ok(provenanceSource);
  const provenance=JSON.parse(provenanceSource);
  assert.deepEqual(Object.keys(provenance).sort(),["authority_sha256","release_status","rules_version","schema_version"]);
  assert.equal(provenance.rules_version,"14.1.0");
  assert.equal(result.manifest.build_identity.rules_version,"14.1.0");assert.equal("application_version" in result.manifest.build_identity,false);
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

test("six dense rules targets render as scoped semantic lists",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const render=(route:string)=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#${route}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const rendered=[
    {id:"common_manifested_strike",dom:render("category=common_features&topic=common_features_common_manifested_strike_topic")},
    {id:"explosion_implosion",dom:render("category=psychokinesis&topic=psychokinesis_explosion_implosion_topic")},
    {id:"mass_levitation",dom:render("category=psychokinesis&topic=psychokinesis_mass_levitation_topic")},
    {id:"forked_lightning",dom:render("category=electrokinesis&topic=electrokinesis_forked_lightning_topic")},
    {id:"advanced_gravitic_press",dom:render("category=advanced_training&topic=advanced_training_advanced_gravitic_press_topic")}
  ];
  const article=(id:string)=>rendered.find(item=>item.id===id)!.dom.window.document.querySelector<HTMLElement>(`#entity-${id}`)!;
  const directLists=(parent:Element)=>[...parent.children].filter(child=>child.tagName==="OL"||child.tagName==="UL") as HTMLElement[];
  const listShape=(parent:Element)=>directLists(parent).map(list=>[list.tagName,list.querySelectorAll(":scope > li").length]);

  assert.deepEqual(listShape(article("common_manifested_strike")),[["UL",3],["UL",5],["OL",2],["UL",2]]);
  const cases=[
    {id:"explosion_implosion",tiers:[[0,[["UL",2],["UL",2]]],[1,[]],[2,[]]]},
    {id:"mass_levitation",tiers:[[0,[["OL",4]]],[1,[]],[2,[]]]},
    {id:"forked_lightning",tiers:[[0,[["UL",5]]],[1,[["UL",4]]],[2,[["UL",8]]]]},
    {id:"advanced_gravitic_press",tiers:[[0,[["UL",5]]],[1,[]],[2,[]]]}
  ] as const;
  for(const candidate of cases){
    const feature=article(candidate.id),tiers=[...feature.querySelectorAll<HTMLElement>(":scope > .feature-tier")];
    assert.deepEqual(tiers.map(tier=>tier.querySelector(":scope > .feature-tier__label")?.textContent),["T0 Base","T1 Overload","T2 Overload"],candidate.id);
    assert.equal(directLists(feature).length,0,candidate.id+" tier lists must not escape their tier");
    for(const [value,shape] of candidate.tiers){
      const content=feature.querySelector<HTMLElement>(`:scope > .feature-tier[data-tier="${value}"] > .feature-tier__content`)!;
      assert.deepEqual(listShape(content),shape,candidate.id+" T"+value);
      for(const list of directLists(content))assert.equal(list.querySelectorAll(":scope > li > strong").length,list.querySelectorAll(":scope > li").length,candidate.id+" labels");
    }
  }
  await new Promise<void>(resolve=>setImmediate(resolve));for(const item of rendered)item.dom.window.close();
});

test("completed readability pass keeps every new list inside its authored common-rule or tier scope",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const doms:JSDOM[]=[];
  const article=(id:string)=>{const dom=new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#entity=${id}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});doms.push(dom);return dom.window.document.querySelector<HTMLElement>(`#entity-${id}`)!;};
  const directLists=(parent:Element)=>[...parent.children].filter(child=>child.tagName==="OL"||child.tagName==="UL") as HTMLElement[];
  const shape=(parent:Element)=>directLists(parent).map(list=>[list.tagName,list.querySelectorAll(":scope > li").length]);
  const common={
    how_to_play:[["OL",6],["UL",5],["UL",4],["UL",4],["UL",2],["UL",3]],
    common_overload:[["UL",2],["UL",3],["UL",4],["UL",4],["UL",4]],
    common_psionic_discipline:[["UL",4],["UL",5]],
    common_psionic_link:[["UL",4]],
    common_manifested_strike:[["UL",3],["UL",5],["OL",2],["UL",2]],
    common_empathic_sense:[["UL",3]]
  } as const;
  for(const [id,expected] of Object.entries(common))assert.deepEqual(shape(article(id)),expected,id);

  const tiered={
    frozen_ground:{0:[["UL",4]]},telekinetic_shove:{0:[["UL",5]]},telekinetic_slam:{2:[["UL",3]]},static_discharge:{2:[["UL",4]]},
    ball_lightning:{0:[["UL",5]],2:[["UL",2]]},advanced_deflection_screen:{2:[["UL",5]]},
    advanced_beguile:{0:[["UL",3]],1:[["UL",3]],2:[["UL",3]]},advanced_improved_phase_step:{0:[["OL",4]]}
  } as const;
  for(const [id,expectedTiers] of Object.entries(tiered)){
    const feature=article(id);assert.deepEqual([...feature.querySelectorAll<HTMLElement>(":scope > .feature-tier > .feature-tier__label")].map(label=>label.textContent),["T0 Base","T1 Overload","T2 Overload"],id);
    assert.deepEqual(shape(feature),id==="advanced_beguile"?[["UL",4]]:[],id+" direct article lists");
    for(const [tierValue,expected] of Object.entries(expectedTiers)){const content=feature.querySelector<HTMLElement>(`:scope > .feature-tier[data-tier="${tierValue}"] > .feature-tier__content`)!;assert.ok(content);assert.deepEqual(shape(content),expected,id+" T"+tierValue);for(const list of directLists(content))assert.equal(list.closest(".feature-tier__content"),content,id+" T"+tierValue+" containment");}
  }
  await new Promise<void>(resolve=>setImmediate(resolve));for(const dom of doms)dom.window.close();
});

test("rendered permanent Discipline choice and Ongoing Duration reference stay explicit",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const render=(topic:string)=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=${topic}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const discipline=render("common_features_common_psionic_discipline_topic");const disciplineArticle=discipline.window.document.querySelector<HTMLElement>("#entity-common_psionic_discipline")!;
  const disciplineParagraphs=[...disciplineArticle.querySelectorAll<HTMLElement>(":scope > p")].map(paragraph=>paragraph.textContent);
  const disciplineLists=[...disciplineArticle.querySelectorAll<HTMLElement>(":scope > ul")].map(list=>[...list.querySelectorAll(":scope > li")].map(item=>item.textContent));
  assert.equal(disciplineArticle.querySelector("h2")?.textContent,"Psionic Discipline");
  assert.deepEqual(disciplineParagraphs.slice(0,4),["When you gain this subclass at Fighter level 3, choose one Kinetic Discipline:","Your chosen Discipline determines:","This choice is permanent and is separate from your Psionic Ability choice.","Choose Intelligence, Wisdom, or Charisma as your Psionic Ability. Your Psionic Ability choice does not change your Discipline."]);
  assert.deepEqual(disciplineLists,[["Pyrokinesis","Cryokinesis","Psychokinesis","Electrokinesis"],["your Manifested Strike’s damage type","your Discipline signature saving throw","your Kinetic Mastery","your Signature Rider","the Discipline features you gain at Fighter levels 3, 7, 10, 15, and 20"]]);

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
  assert.deepEqual(sections.map(section=>section.querySelectorAll(".example-play-section__phase ol,.example-play-section__phase ul").length),[5,6,6,6]);
  for(const section of sections){const phases=[...section.querySelectorAll<HTMLElement>(".example-play-section__phase")];assert.deepEqual([...section.querySelectorAll<HTMLElement>(".example-play-section__phase-title")].map(node=>node.textContent),["Setup","Activation","Rolls or Saves","Damage","Effects","Result"]);assert.equal(section.querySelectorAll("em").length,0);assert.ok(section.querySelectorAll("strong").length>0);assert.equal(phases.length,6);assert.ok(phases.every(phase=>phase.querySelector(":scope > p,:scope > ol,:scope > ul")));assert.ok([...section.querySelectorAll("li")].every(item=>item.querySelector(":scope > strong")));}
  for(const [index,fragments] of [[0,["18 + 21 + 11 = 50 fire damage"]],[1,["13 + 10 + 8 = 31 force damage","push the creature 10 feet"]],[2,["12 + 14 + 9 = 35 cold damage","Speed 0"]],[3,["111 lightning damage","Three primary targets are struck and Sapped"]]] as const)for(const fragment of fragments)assert.ok(sections[index]!.textContent?.includes(fragment),fragment);
  const overloadDom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_common_overload_topic",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});const inline=overloadDom.window.document.querySelector<HTMLElement>("#entity-common_overload .inline-example")!;assert.equal(overloadDom.window.document.querySelectorAll("#entity-common_overload .inline-example").length,1);assert.equal(inline.querySelector("h3")?.textContent,"Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)");assert.deepEqual([...inline.querySelectorAll(":scope > .inline-example__body > ul")].map(list=>list.querySelectorAll(":scope > li").length),[3]);assert.deepEqual([...inline.querySelectorAll(":scope > .inline-example__body > ul > li > strong")].map(node=>node.textContent),["Hit: ","Blood Tax: ","Miss: "]);assert.equal(inline.querySelectorAll(":scope > .inline-example__body > p").length,2);assert.match(inline.textContent??"",/Glacial Spike at Tier 2.*1d10.*Blood Tax: 2 × Proficiency Bonus = 2 × 4 = 8.*Miss: Glacial Spike does not resolve/s);assert.equal(article.textContent?.includes("Example — Level 11 Cryokinesis (Proficiency Bonus 4, Intelligence +3)"),false);
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
  const dom=new JSDOM(modified,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html"+defaultReferenceFragment,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;assert.match(document.querySelector("article p")?.textContent??"",/^Example ordinary paragraph\./);assert.equal(document.querySelector("article .example-play-section,.inline-example"),null);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});


test("release build fails closed before emitting deployable output",async()=>{await assert.rejects(()=>executeBuild("release"),/Build blocked/);});

test("committed Name selection opens exactly once, preserves history state, and remains synchronized",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  let pushCount=0;
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html"+defaultReferenceFragment,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value.replace(/[^a-zA-Z0-9_-]/g,"_")};const push=window.history.pushState.bind(window.history);window.history.pushState=(...args:any[])=>{pushCount++;return push(...args);};}});
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
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html"+defaultReferenceFragment,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const document=dom.window.document;const disclosure=document.querySelector<HTMLDetailsElement>("#filter-results details.results__all")!;
  assert.ok(disclosure);assert.equal(disclosure.open,false);assert.equal(disclosure.querySelector("summary")?.textContent,index.entities.length+" matches.");
  const buttons=[...disclosure.querySelectorAll<HTMLButtonElement>("button")];assert.equal(buttons.length,index.entities.length);
  assert.deepEqual(buttons.map(button=>button.textContent),index.entities.map(entity=>entity.title+" — "+authority.vocabularies.rules_areas!.find(area=>area.id===entity.primary_rules_area)!.label));
  assert.doesNotMatch(document.querySelector("#filter-results")?.textContent??"",/Select at least one classification/);
  await new Promise<void>(resolve=>setImmediate(resolve));dom.window.close();
});

test("classification controls implement AND across facets and metadata-only results",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html"+defaultReferenceFragment,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
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
  const barrier=render(html,"advanced_training","advanced_training_advanced_barrier_topic");
  assert.ok(metadata(barrier.window.document,"advanced_barrier").some(item=>item.term==="Requirement"&&item.value==="Concentration"&&item.classes.includes("feature-metadata__item--concentration")));
  const barrierLists=barrier.window.document.querySelectorAll("#entity-advanced_barrier > ul");assert.equal(barrierLists.length,1);
  assert.deepEqual([...barrierLists[0]!.querySelectorAll(":scope > li")].map(item=>item.textContent),[
    "Blade Shield: You have Resistance to bludgeoning, piercing, and slashing damage from weapon attacks.",
    "Elemental Shroud: Choose acid, cold, fire, lightning, or thunder; you have Resistance to that damage type.",
    "Spellward: You have Advantage on saving throws against spells.",
    "Steadfast Guard: You have Advantage on Strength saving throws and on ability checks and saving throws made to resist being Grappled, shoved, knocked Prone, or forcibly moved.",
    "Mental Bulwark: You have Advantage on saving throws against being Charmed, Frightened, Blinded, Restrained, Incapacitated, Paralyzed, or Stunned."
  ]);
  for(const [dom,entityId,duration] of [
    [gravitic,"advanced_gravitic_press","Up to 1 minute"],
    [levitation,"mass_levitation","Up to 1 minute"],
    [frozen,"frozen_ground","Up to 1 minute"],
    [vectored,"vectored_thrust","Up to 10 minutes"],
    [ball,"ball_lightning","Up to 1 minute"],
    [beguile,"advanced_beguile","Varies by tier"],
    [barrier,"advanced_barrier","Varies by tier"]
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
  for(const dom of [gravitic,levitation,frozen,vectored,ball,beguile,barrier,rider,manifested,empathic,slam,descriptionOnly])dom.window.close();
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
  const staleState={view:"reference",category:"cryokinesis",topic:"common_features_common_overload_topic",classifications:{},entity:"common_overload",resultRoute:"common_features_common_overload_topic",focusOrigin:"history"};
  invalid.window.dispatchEvent(new invalid.window.PopStateEvent("popstate",{state:staleState}));assert.equal((invalidDocument.querySelector("#topic-select") as HTMLSelectElement).value,"cryokinesis_glacial_spike_topic");assert.equal(invalidDocument.querySelector("#rules-content article h2")?.textContent,"Glacial Spike");assert.ok(!invalidDocument.querySelector("#entity-common_overload"));
  assert.equal(invalid.window.location.hash,"#category=cryokinesis&topic=cryokinesis_glacial_spike_topic");assert.equal(invalid.window.history.state.entity,null);assert.equal(invalid.window.history.state.resultRoute,null);assert.equal(invalid.window.history.state.focusOrigin,"history");
  await new Promise<void>(resolve=>setImmediate(resolve));common.window.close();invalid.window.close();
});

function installOnboardingBrowserShims(window:any):void {
  window.structuredClone=globalThis.structuredClone;
  window.CSS={escape:(value:string)=>value.replace(/[^a-zA-Z0-9_-]/g,"_")};
  Object.defineProperty(window.HTMLElement.prototype,"scrollIntoView",{configurable:true,value(){}});
}

const settleOnboarding=()=>new Promise<void>(resolve=>setImmediate(resolve));

test("Start Here owns empty and home fragments while existing deep links keep the reference contract",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const makeDom=(fragment:string,counters?:{pushes:number;replaces:number})=>new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html${fragment}`,beforeParse(window:any){
    installOnboardingBrowserShims(window);
    if(counters){const push=window.history.pushState.bind(window.history),replace=window.history.replaceState.bind(window.history);window.history.pushState=(...args:any[])=>{counters.pushes++;return push(...args);};window.history.replaceState=(...args:any[])=>{counters.replaces++;return replace(...args);};}
  }});
  const assertHome=(dom:JSDOM)=>{
    const document=dom.window.document,layout=document.querySelector<HTMLElement>("main.layout")!,controls=document.querySelector<HTMLElement>(".controls")!;
    assert.equal(layout.dataset.view,"home");assert.equal(layout.classList.contains("layout--home"),true);assert.equal(controls.hidden,true);
    assert.equal(document.querySelector("#start_here_heading")?.textContent,"Start Here");assert.equal(document.querySelector("#rules-content article"),null);
    assert.equal(document.querySelector("#view-start-here")?.getAttribute("aria-current"),"page");assert.equal(document.querySelector("#view-rules-reference")?.hasAttribute("aria-current"),false);
    assert.equal(document.activeElement,document.body);assert.equal(new URLSearchParams(dom.window.location.hash.slice(1)).has("category"),false);assert.equal(new URLSearchParams(dom.window.location.hash.slice(1)).has("topic"),false);
  };

  const counters={pushes:0,replaces:0},empty=makeDom("",counters);assertHome(empty);assert.equal(empty.window.location.hash,"#home");assert.deepEqual(counters,{pushes:0,replaces:1});assert.equal(empty.window.history.length,1);
  (empty.window.document.querySelector(".skip") as HTMLElement).click();assert.equal(empty.window.document.activeElement?.id,"rules-content");assert.equal(empty.window.location.hash,"#home");assert.deepEqual(counters,{pushes:0,replaces:1});assert.equal(empty.window.history.length,1);
  const explicitHome=makeDom("#home");assertHome(explicitHome);assert.equal(explicitHome.window.location.hash,"#home");

  const category=makeDom("#category=cryokinesis&topic=cryokinesis_frozen_ground_topic");
  assert.equal(category.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"reference");assert.equal(category.window.document.querySelector("#entity-frozen_ground h2")?.textContent,"Frozen Ground");assert.equal(category.window.document.querySelector<HTMLElement>(".controls")?.hidden,false);assert.equal(category.window.document.activeElement,category.window.document.body);
  assert.equal(category.window.location.hash,"#category=cryokinesis&topic=cryokinesis_frozen_ground_topic");
  const categoryHash=category.window.location.hash;(category.window.document.querySelector(".skip") as HTMLElement).click();assert.equal(category.window.document.activeElement?.id,"rules-content");assert.equal(category.window.location.hash,categoryHash);assert.equal(category.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"reference");assert.equal(category.window.document.querySelector("#entity-frozen_ground h2")?.textContent,"Frozen Ground");

  const entity=makeDom("#entity=ball_lightning"),entityRoute=new URLSearchParams(entity.window.location.hash.slice(1));
  assert.equal(entity.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"reference");assert.equal(entityRoute.get("category"),"electrokinesis");assert.equal(entityRoute.get("topic"),"electrokinesis_ball_lightning_topic");assert.equal(entityRoute.get("entity"),"ball_lightning");
  assert.equal(entity.window.location.hash,"#category=electrokinesis&topic=electrokinesis_ball_lightning_topic&entity=ball_lightning");
  assert.equal((entity.window.document.querySelector("#name-select") as HTMLSelectElement).value,"ball_lightning");assert.equal(entity.window.document.querySelector("#entity-ball_lightning h2")?.textContent,"Ball Lightning");assert.equal(entity.window.document.activeElement,entity.window.document.body);

  const filtered=makeDom("#category=psychokinesis&topic=psychokinesis_telekinetic_shove_topic&filters=rules_area:psychokinesis;feature_role:rider");
  assert.equal(filtered.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"reference");assert.equal((filtered.window.document.querySelector('input[data-facet="rules_area"][value="psychokinesis"]') as HTMLInputElement).checked,true);assert.equal((filtered.window.document.querySelector("#facet-feature_role") as HTMLSelectElement).value,"rider");

  assert.equal(filtered.window.location.hash,"#category=psychokinesis&topic=psychokinesis_telekinetic_shove_topic&filters=rules_area%3Apsychokinesis%3Bfeature_role%3Arider");
  const deduplicated=makeDom("#category=pyrokinesis&topic=pyrokinesis_ember_bolt_topic&filters=rules_area:pyrokinesis,pyrokinesis");
  assert.equal(deduplicated.window.location.hash,"#category=pyrokinesis&topic=pyrokinesis_ember_bolt_topic&filters=rules_area%3Apyrokinesis");assert.deepEqual(deduplicated.window.history.state.classifications,{rules_area:["pyrokinesis"]});
  const invalid=makeDom("#not-a-canonical-route"),invalidRoute=new URLSearchParams(invalid.window.location.hash.slice(1));
  assert.equal(invalid.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"reference");assert.equal(invalidRoute.get("category"),"common_features");assert.equal(invalidRoute.get("topic"),"common_features_how_to_play_topic");assert.equal(invalid.window.document.querySelector("#entity-how_to_play h2")?.textContent,"How to Play This Subclass");

  assert.equal(invalid.window.location.hash,"#category=common_features&topic=common_features_how_to_play_topic");
  for(const dom of [empty,explicitHome,category,entity,filtered,deduplicated,invalid]){await settleOnboarding();dom.window.close();}
});

test("view navigation is idempotent and browser history restores the complete reference snapshot",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const counters={pushes:0,replaces:0};
  const fragment="#category=advanced_training&topic=advanced_training_advanced_deflection_screen_topic&filters=rules_area:advanced_training;entity_kind:feature;feature_role:standalone;acquisition_mode:granted&entity=advanced_deflection_screen";
  const dom=new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html${fragment}`,beforeParse(window:any){installOnboardingBrowserShims(window);const push=window.history.pushState.bind(window.history),replace=window.history.replaceState.bind(window.history);window.history.pushState=(...args:any[])=>{counters.pushes++;return push(...args);};window.history.replaceState=(...args:any[])=>{counters.replaces++;return replace(...args);};}});
  const document=dom.window.document,layout=document.querySelector<HTMLElement>("main.layout")!;
  assert.deepEqual(counters,{pushes:0,replaces:1});assert.equal(layout.dataset.view,"reference");assert.equal((document.querySelector("#name-select") as HTMLSelectElement).value,"advanced_deflection_screen");
  (document.querySelector("#view-start-here") as HTMLElement).click();assert.equal(layout.dataset.view,"home");assert.equal(dom.window.location.hash,"#home");assert.equal(counters.pushes,1);assert.equal(document.activeElement?.id,"start_here_heading");
  (document.querySelector("#view-start-here") as HTMLElement).click();assert.equal(counters.pushes,1);assert.equal(dom.window.location.hash,"#home");

  const back=new Promise<void>(resolve=>dom.window.addEventListener("popstate",()=>resolve(),{once:true}));dom.window.history.back();await back;
  assert.equal(layout.dataset.view,"reference");assert.equal((document.querySelector("#category-select") as HTMLSelectElement).value,"advanced_training");assert.equal((document.querySelector("#topic-select") as HTMLSelectElement).value,"advanced_training_advanced_deflection_screen_topic");
  assert.equal((document.querySelector('input[data-facet="rules_area"][value="advanced_training"]') as HTMLInputElement).checked,true);assert.equal((document.querySelector("#facet-entity_kind") as HTMLSelectElement).value,"feature");assert.equal((document.querySelector("#facet-feature_role") as HTMLSelectElement).value,"standalone");assert.equal((document.querySelector("#facet-acquisition_mode") as HTMLSelectElement).value,"granted");
  assert.equal((document.querySelector("#name-select") as HTMLSelectElement).value,"advanced_deflection_screen");assert.ok(document.querySelector("#entity-advanced_deflection_screen"));assert.equal(counters.pushes,1);
  assert.equal(dom.window.location.hash,"#category=advanced_training&topic=advanced_training_advanced_deflection_screen_topic&filters=rules_area%3Aadvanced_training%3Bentity_kind%3Afeature%3Bfeature_role%3Astandalone%3Bacquisition_mode%3Agranted&entity=advanced_deflection_screen");assert.equal(dom.window.history.state.resultRoute,"advanced_training_advanced_deflection_screen_topic");assert.equal(dom.window.history.state.focusOrigin,"fragment");

  const forward=new Promise<void>(resolve=>dom.window.addEventListener("popstate",()=>resolve(),{once:true}));dom.window.history.forward();await forward;
  assert.equal(layout.dataset.view,"home");assert.equal(dom.window.location.hash,"#home");assert.equal(counters.pushes,1);assert.notEqual(document.activeElement?.id,"start_here_heading");
  (document.querySelector("#view-rules-reference") as HTMLElement).click();assert.equal(layout.dataset.view,"reference");assert.equal(counters.pushes,2);assert.equal((document.querySelector("#category-select") as HTMLSelectElement).value,"advanced_training");assert.equal((document.querySelector("#topic-select") as HTMLSelectElement).value,"advanced_training_advanced_deflection_screen_topic");assert.equal((document.querySelector("#name-select") as HTMLSelectElement).value,"advanced_deflection_screen");assert.equal((document.querySelector('input[data-facet="rules_area"][value="advanced_training"]') as HTMLInputElement).checked,true);assert.equal(document.activeElement,document.querySelector("#entity-advanced_deflection_screen > h2"));
  assert.equal(dom.window.history.state.resultRoute,"advanced_training_advanced_deflection_screen_topic");assert.equal(dom.window.history.state.focusOrigin,"view");
  (document.querySelector("#view-rules-reference") as HTMLElement).click();assert.equal(counters.pushes,2);
  await settleOnboarding();dom.window.close();
});

test("history restoration rejects invalid classifications and canonicalizes repaired routes",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const fragment="#category=common_features&topic=common_features_how_to_play_topic";
  const dom=new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html${fragment}`,beforeParse(window:any){installOnboardingBrowserShims(window);}});
  const document=dom.window.document,baseState=structuredClone(dom.window.history.state);
  const invalidClassifications=[{entity_kind:"bogus"},{entity_kind:["feature"]},{rules_area:"common_features"},{rules_area:["common_features","common_features"]}];
  for(const classifications of invalidClassifications){
    const snapshot={...baseState,classifications,focusOrigin:"history"};
    dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate",{state:snapshot}));
    assert.deepEqual(dom.window.history.state.classifications,{});assert.equal((document.querySelector("#facet-entity_kind") as HTMLSelectElement).value,"");assert.equal((document.querySelector('input[data-facet="rules_area"][value="common_features"]') as HTMLInputElement).checked,false);assert.ok(document.querySelector("#entity-how_to_play"));
  }
  const invalidModifier={...baseState,psiModifier:6,focusOrigin:"history"};
  dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate",{state:invalidModifier}));
  assert.equal(dom.window.history.state.psiModifier,5);
  const repaired={...baseState,topic:"missing_topic",entity:"how_to_play",resultRoute:"missing_topic",focusOrigin:"history"};
  dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate",{state:repaired}));
  assert.equal(dom.window.location.hash,"#category=common_features&topic=common_features_how_to_play_topic&entity=how_to_play");
  assert.equal(dom.window.history.state.topic,"common_features_how_to_play_topic");assert.equal(dom.window.history.state.resultRoute,"common_features_how_to_play_topic");assert.equal(dom.window.history.state.focusOrigin,"history");
  assert.equal((document.querySelector("#name-select") as HTMLSelectElement).value,"how_to_play");assert.ok(document.querySelector("#entity-how_to_play"));assert.equal(document.activeElement,document.body);
  await settleOnboarding();dom.window.close();
});

test("Start Here renders semantic canonical sections and every destination exposes and activates its canonical route",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");const {authority}=await loadAuthority();const index=buildFilterIndex(authority);
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#home",beforeParse(window:any){installOnboardingBrowserShims(window);}});
  const document=dom.window.document,onboarding=authority.onboarding,layout=document.querySelector<HTMLElement>("main.layout")!,home=document.querySelector<HTMLElement>('.home-guide[data-onboarding-id="start_here"]')!;
  assert.ok(home);assert.equal(layout.dataset.view,"home");assert.equal(document.querySelector<HTMLElement>(".controls")?.hidden,true);assert.equal(document.querySelector(".skip")?.getAttribute("href"),"#rules-content");
  assert.equal(home.querySelector(":scope > h2")?.id,"start_here_heading");assert.equal(home.querySelector(":scope > h2")?.textContent,onboarding.title);
  for(const text of Object.values(onboarding.introduction))assert.ok(home.textContent?.includes(text));
  for(const section of [onboarding.disciplines,onboarding.basic_turn,onboarding.build_checklist,onboarding.glossary,onboarding.next_destinations]){const element=home.querySelector<HTMLElement>(`#${section.id}`)!;assert.ok(element);assert.equal(element.classList.contains("home-section"),true);assert.equal(element.querySelector(":scope > h3")?.textContent,section.title);}
  assert.equal(home.querySelectorAll(".home-card-list .home-card").length,4);assert.equal(home.querySelectorAll(".home-card__title").length,4);assert.equal(home.querySelectorAll(".home-checklist > li").length,6);assert.equal(home.querySelectorAll(".home-glossary > dt").length,5);assert.equal(home.querySelectorAll(".home-glossary > dd").length,5);
  const headingLevels=[...document.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5,h6")].map(heading=>Number(heading.tagName.slice(1)));assert.equal(home.querySelectorAll("h1").length,0);assert.equal(home.querySelectorAll("h2").length,1);for(let position=1;position<headingLevels.length;position++)assert.ok(headingLevels[position]!<=headingLevels[position-1]!+1,`heading level skipped at position ${position}`);

  const internal=onboarding.primary_paths.filter(path=>path.destination.kind==="onboarding_section");
  for(const path of internal){const control=document.querySelector<HTMLElement>(`[data-onboarding-link-id="${path.id}"]`)!;assert.equal(control.tagName,"BUTTON");assert.equal(control.getAttribute("data-destination-kind"),"onboarding_section");assert.ok(control.textContent?.includes(path.title));control.click();assert.equal(document.activeElement?.id,`${path.destination.kind==="onboarding_section"?path.destination.section_id:""}_heading`);assert.equal(layout.dataset.view,"home");}

  const links=[...onboarding.primary_paths,...onboarding.disciplines.cards,...onboarding.basic_turn.destinations,...onboarding.build_checklist.items,...onboarding.glossary.entries,...onboarding.next_destinations.items].filter(link=>link.destination.kind!=="onboarding_section");
  const categoryById=new Map(authority.navigation.categories.map(category=>[category.id,category])),entryById=new Map(index.entities.map(entry=>[entry.id,entry]));
  const destination=(value:any)=>{
    if(value.kind==="category"){const category=categoryById.get(value.category_id)!;return{fragment:`#category=${category.id}&topic=${category.default_topic_id}`,entityId:category.topics.find(topic=>topic.id===category.default_topic_id)!.entity_ids[0]!};}
    const entry=entryById.get(value.entity_id)!;const area=entry.primary_rules_area,topic=entry.routes[area]!;return{fragment:`#category=${area}&topic=${topic}&entity=${entry.id}`,entityId:entry.id};
  };
  assert.equal(new Set(links.map(link=>link.id)).size,links.length);
  for(const link of links){
    const expected=destination(link.destination),control=document.querySelector<HTMLAnchorElement>(`[data-onboarding-link-id="${link.id}"]`)!;
    assert.equal(control.tagName,"A",link.id);assert.equal(control.getAttribute("data-destination-kind"),link.destination.kind,link.id);assert.equal(control.getAttribute("href"),expected.fragment,link.id);assert.ok(control.textContent?.includes(link.title),link.id);
    control.click();assert.equal(layout.dataset.view,"reference",link.id);assert.equal(document.querySelector<HTMLElement>(".controls")?.hidden,false,link.id);const heading=document.querySelector<HTMLElement>(`#entity-${expected.entityId} > h2`)!;assert.ok(heading,link.id);assert.equal(document.activeElement,heading,link.id);
    if(link.destination.kind==="entity")assert.equal((document.querySelector("#name-select") as HTMLSelectElement).value,link.destination.entity_id,link.id);
    (document.querySelector("#view-start-here") as HTMLElement).click();assert.equal(layout.dataset.view,"home",link.id);assert.equal(document.activeElement?.id,"start_here_heading",link.id);
  }
  await settleOnboarding();dom.window.close();
});
const calculatorRiders=[
  ["glacial_spike","Glacial Spike",3] as const,["snow_chains","Snow Chains",7] as const,
  ["ember_bolt","Ember Bolt",3] as const,["thermal_fracture","Thermal Fracture",7] as const,
  ["cinder_lance","Cinder Lance",10] as const,["flare","Flare",15] as const,["furnace_strike","Furnace Strike",20] as const,
  ["telekinetic_shove","Telekinetic Shove",3] as const,["explosion_implosion","Explosion/Implosion",10] as const,
  ["static_discharge","Static Discharge",3] as const,["branching_bolt","Branching Bolt",7] as const,
  ["electron_burst","Electron Burst",10] as const,["advanced_mind_shred","Mind Shred",15] as const,["advanced_mind_lock","Mind Lock",15] as const
] as const;
const calculatorStandaloneFeatures=[
  ["arctic_tempest","Arctic Tempest",15] as const,["absolute_zero","Absolute Zero",20] as const,
  ["telekinetic_slam","Telekinetic Slam",15] as const,["mass_levitation","Mass Levitation",20] as const,
  ["forked_lightning","Forked Lightning",15] as const,["ball_lightning","Ball Lightning",20] as const
] as const;
const calculatorFeatures=[["common_manifested_strike","Manifested Strike",3] as const,...calculatorRiders,...calculatorStandaloneFeatures] as const;
const normalizedCalculatorText=(element:Element)=>element.textContent?.replace(/\s+/g," ").trim()??"";
const exactCalculatorTextCount=(root:Element,expected:string)=>[root,...root.querySelectorAll("*")].filter(element=>normalizedCalculatorText(element)===expected).length;
const assertCalculatorText=(root:Element,expected:string)=>assert.ok([root,...root.querySelectorAll("*")].some(element=>normalizedCalculatorText(element).includes(expected)),`Missing calculator text: ${expected}`);
const calculatorTierHeadings=(root:Element)=>[...root.querySelectorAll("h2,h3,h4,h5,h6")].map(normalizedCalculatorText).filter(text=>/^Tier [012]$/u.test(text));
const calculatorEffectPaths=(root:Element,tier:number)=>[...root.querySelectorAll<HTMLElement>(`.calculator__tier[data-tier="${tier}"] .calculator__effects [data-source-path]`)].map(element=>element.dataset.sourcePath);
const calculatorSharedEffectPaths=(root:Element)=>[...root.querySelectorAll<HTMLElement>(".calculator__shared-effects [data-source-path]")].map(element=>element.dataset.sourcePath);
const calculatorListItemPaths=(base:string,count:number)=>Array.from({length:count},(_,index)=>`${base}.items.${index}`);
const assertCalculatorStrikeCalculations=(root:Element,pb:number,modifier:number,focus:number,die:string)=>{const hit=`Hit calculation: 1d20 + Proficiency Bonus (${pb}) + Psionic Ability Modifier (${modifier}) + Psionic Focus (${focus}) = 1d20 + ${pb+modifier+focus}`,damageTotal=modifier===0?die:`${die} + ${modifier}`,damage=`Damage calculation: Manifested Strike die (${die}) + Psionic Ability Modifier (${modifier}) = ${damageTotal}`,calculations=[...root.querySelectorAll<HTMLElement>(".calculator__calculation.calculator__breakdown")];assert.equal(calculations.length,2);assert.equal(exactCalculatorTextCount(root,hit),1);assert.equal(exactCalculatorTextCount(root,damage),1);for(const calculation of calculations){const text=normalizedCalculatorText(calculation);assert.match(text,/ calculation: .+ = .+$/u);assert.doesNotMatch(text,/\b(?:PB|Psi Mod)\b| · /u);}};
const calculatorProficiencyBonusAtLevel=(level:number)=>level>=17?6:level>=13?5:level>=9?4:level>=5?3:2;
const assertCalculatorSaveCalculation=(root:Element,pb:number,modifier:number,dc:number,count=1)=>{const expected=`Saving throw calculation: 8 + Proficiency Bonus (${pb}) + Psionic Ability Modifier (${modifier}) = ${dc}`,calculations=[...root.querySelectorAll<HTMLElement>(".calculator__calculation.calculator__save-calculation")];assert.equal(calculations.length,count);assert.equal(exactCalculatorTextCount(root,expected),count);for(const calculation of calculations){const text=normalizedCalculatorText(calculation);assert.match(text,/ calculation: .+ = .+$/u);assert.doesNotMatch(text,/\b(?:PB|Psi Mod)\b| · /u);}};
const calculatorPsiPointBands=[
  {minimumLevel:3,maximumLevel:4,value:4},{minimumLevel:5,maximumLevel:6,value:6},{minimumLevel:7,maximumLevel:8,value:7},
  {minimumLevel:9,maximumLevel:10,value:9},{minimumLevel:11,maximumLevel:12,value:10},{minimumLevel:13,maximumLevel:14,value:12},
  {minimumLevel:15,maximumLevel:16,value:13},{minimumLevel:17,maximumLevel:18,value:15},{minimumLevel:19,maximumLevel:20,value:16}
] as const;
const calculatorPsiPointsAtLevel=(level:number)=>calculatorPsiPointBands.find(band=>level>=band.minimumLevel&&level<=band.maximumLevel)!.value;
const assertCalculatorPsiTotal=(root:Element,total:number)=>{
  const facts=root.querySelector<HTMLElement>(".calculator__facts")!;assert.ok(facts);
  const metrics=[...facts.querySelectorAll<HTMLElement>(":scope > p")].map(normalizedCalculatorText),psiCostIndex=metrics.findIndex(text=>/^Psi cost: \d+$/u.test(text));
  assert.notEqual(psiCostIndex,-1);assert.equal(metrics[psiCostIndex+1],`Total Psi Points: ${total}`);
  const labels=[...facts.querySelectorAll("strong")].map(normalizedCalculatorText);
  assert.equal(labels.filter(label=>label==="Psi cost:").length,1);assert.equal(labels.filter(label=>label==="Total Psi Points:").length,1);
  assert.equal(exactCalculatorTextCount(facts,`Total Psi Points: ${total}`),1);
};
const assertCalculatorPsiFacts=(root:Element,cost:number,total:number)=>{assert.equal(exactCalculatorTextCount(root,`Psi cost: ${cost}`),1);assertCalculatorPsiTotal(root,total);};

test("calculator exposes exactly three native selects, twenty-one feature choices, and the required Manifested Strike level 20 defaults",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator",beforeParse(window:any){installOnboardingBrowserShims(window);}});
  const root=dom.window.document.querySelector<HTMLElement>("#calculator-root")!;assert.ok(root);assert.equal(dom.window.location.hash,"#calculator");
  const feature=root.querySelector<HTMLSelectElement>("#calculator-feature")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!,modifier=root.querySelector<HTMLSelectElement>("#calculator-psi-modifier")!;
  assert.deepEqual([...root.querySelectorAll("select")],[feature,level,modifier]);assert.deepEqual([feature,level,modifier].map(control=>control.tagName),["SELECT","SELECT","SELECT"]);
  const labelText=(control:HTMLSelectElement)=>{const label=root.querySelector<HTMLLabelElement>(`label[for="${control.id}"]`)!;assert.ok(label);const clone=label.cloneNode(true) as HTMLLabelElement;clone.querySelector(`#${control.id}`)?.remove();return clone.textContent?.trim();};
  assert.deepEqual([feature,level,modifier].map(labelText),["Skill / Feature","Fighter Level","Psionic Ability Modifier"]);
  assert.equal(feature.value,"common_manifested_strike");assert.equal(level.value,"20");assert.equal(modifier.value,"5");assert.equal(modifier.selectedOptions[0]?.textContent?.trim(),"+5");
  for(const control of [feature,level,modifier])assert.equal(control.getAttribute("aria-controls"),"calculator-feature-results");
  assert.deepEqual([...modifier.options].map(option=>option.textContent?.trim()),["+0","+1","+2","+3","+4","+5"]);
  assert.equal(root.querySelector("#target-ac,[name='target-ac'],[aria-label='Target AC']"),null);assert.doesNotMatch(root.textContent??"",/Target AC|hit chance/iu);
  assert.equal([...root.querySelectorAll("button")].some(button=>/^(?:Apply|Calculate)$/iu.test(button.textContent?.trim()??"")),false);
  assert.equal(feature.options.length,21);assert.deepEqual([...feature.options].map(option=>option.value).sort(),calculatorFeatures.map(([id])=>id).sort());
  for(const [id,title,minimumLevel] of calculatorFeatures){
    const option=[...feature.options].find(candidate=>candidate.value===id)!;assert.ok(option);assert.equal(option.textContent?.trim(),title);assert.equal(option.disabled,minimumLevel>20,id);
  }
  const results=root.querySelector<HTMLElement>("#calculator-feature-results")!;assert.equal(root.querySelector("#manifested-strike-summary"),null);assert.ok(results);
  assert.equal(root.querySelectorAll("#calculator-feature-results.calculator__result").length,1);
  assert.equal(results.hidden,false);assert.equal(results.querySelector(":scope > h3")?.textContent,"Manifested Strike");assert.equal(results.querySelector(".calculator__trigger,.calculator__facts,.calculator__tiers"),null);
  assertCalculatorText(results,"Hit: 1d20 + 14");assertCalculatorText(results,"Damage: 1d12 + 5");assertCalculatorText(results,"Expected avg damage: 11.5");assertCalculatorText(results,"Psionic Save DC: 19");assertCalculatorStrikeCalculations(results,6,5,3,"1d12");assertCalculatorSaveCalculation(results,6,5,19);
  assert.doesNotMatch(results.textContent??"",/Expected rider damage:/u);
  feature.value="telekinetic_shove";feature.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
  assertCalculatorText(results,"Telekinetic Shove");assert.deepEqual(calculatorTierHeadings(results),["Tier 0","Tier 1","Tier 2"]);
  assert.equal(exactCalculatorTextCount(results,"Triggering Manifested Strike"),1);
  const trigger=results.querySelector<HTMLElement>(".calculator__trigger")!;assert.ok(trigger);assertCalculatorText(trigger,"Hit: 1d20 + 14");assertCalculatorText(trigger,"Damage: 1d12 + 5");assertCalculatorText(trigger,"Expected avg damage: 11.5");assert.equal(exactCalculatorTextCount(results,"Psionic Save DC: 19"),0);
  assertCalculatorStrikeCalculations(trigger,6,5,3,"1d12");assert.equal(trigger.querySelector(".calculator__save-calculation"),null);
  assert.equal(exactCalculatorTextCount(results,"Rider damage: 2"),3);assert.equal(exactCalculatorTextCount(results,"Combined damage: 1d12 + 7"),3);assert.equal(exactCalculatorTextCount(results,"Expected combined damage: 13.5"),3);
  assert.equal(exactCalculatorTextCount(results,"Strength save: DC 19"),1);assertCalculatorSaveCalculation(results,6,5,19);assertCalculatorPsiFacts(results,0,16);
  const save=results.querySelector<HTMLElement>(".calculator__save")!;assert.ok(save);assert.equal(save.dataset.saveTiers,"0 1 2");assertCalculatorText(results,"Applies to Tiers 0–2.");
  assert.equal(exactCalculatorTextCount(results,"Blood Tax: 0"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 6"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 12"),1);
  assert.deepEqual(calculatorEffectPaths(results,0),calculatorListItemPaths("entities.telekinetic_shove.content.0.body.0",5));
  assert.deepEqual(calculatorEffectPaths(results,1),["entities.telekinetic_shove.content.1.body.1"]);
  assert.deepEqual(calculatorEffectPaths(results,2),["entities.telekinetic_shove.content.2.body.1"]);
  assert.deepEqual(calculatorSharedEffectPaths(results),[]);
  assert.deepEqual([...results.querySelectorAll(".calculator__effects")].map(section=>section.getAttribute("aria-label")),["Target and effect","Target and effect","Target and effect"]);
  assert.equal(exactCalculatorTextCount(results,"Target and effect"),0);
  assert.doesNotMatch(results.textContent??"",/\bT[012] (?:Base|Overload):|Changes from Tier/iu);
  await settleOnboarding();dom.window.close();
});

test("each calculator select updates synchronously and level changes enforce every progression boundary",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator",beforeParse(window:any){installOnboardingBrowserShims(window);}});
  const root=dom.window.document.querySelector<HTMLElement>("#calculator-root")!;assert.ok(root);const results=root.querySelector<HTMLElement>("#calculator-feature-results")!;assert.equal(root.querySelector("#manifested-strike-summary"),null);
  const feature=root.querySelector<HTMLSelectElement>("#calculator-feature")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!,modifier=root.querySelector<HTMLSelectElement>("#calculator-psi-modifier")!;
  const change=(control:HTMLSelectElement,value:string)=>{control.value=value;assert.equal(control.value,value);control.dispatchEvent(new dom.window.Event("change",{bubbles:true}));};
  change(level,"11");change(feature,"ember_bolt");assertCalculatorText(results,"Ember Bolt");for(const average of ["12.5","14.5","16.5"])assertCalculatorText(results,`Expected combined damage: ${average}`);
  change(feature,"telekinetic_shove");change(modifier,"4");let trigger=results.querySelector<HTMLElement>(".calculator__trigger")!;assertCalculatorText(trigger,"Hit: 1d20 + 10");assertCalculatorText(trigger,"Damage: 1d10 + 4");assertCalculatorText(trigger,"Expected avg damage: 9.5");assertCalculatorText(results,"Strength save: DC 16");assertCalculatorSaveCalculation(results,4,4,16);
  assertCalculatorStrikeCalculations(trigger,4,4,2,"1d10");
  change(modifier,"5");trigger=results.querySelector<HTMLElement>(".calculator__trigger")!;assertCalculatorText(trigger,"Hit: 1d20 + 11");assertCalculatorText(trigger,"Damage: 1d10 + 5");assertCalculatorText(trigger,"Expected avg damage: 10.5");assertCalculatorText(results,"Strength save: DC 17");assertCalculatorSaveCalculation(results,4,5,17);
  assertCalculatorStrikeCalculations(trigger,4,5,2,"1d10");
  change(modifier,"0");trigger=results.querySelector<HTMLElement>(".calculator__trigger")!;assertCalculatorText(trigger,"Hit: 1d20 + 6");assertCalculatorText(trigger,"Damage: 1d10");assertCalculatorText(results,"Strength save: DC 12");assertCalculatorStrikeCalculations(trigger,4,0,2,"1d10");assertCalculatorSaveCalculation(results,4,0,12);change(modifier,"5");
  const boundaries=[
    {level:3,pb:2,psi:4,focus:1,die:"1d6",hit:8,dc:15,average:"8.5"},{level:4,pb:2,psi:4,focus:1,die:"1d6",hit:8,dc:15,average:"8.5"},
    {level:5,pb:3,psi:6,focus:1,die:"1d8",hit:9,dc:16,average:"9.5"},{level:6,pb:3,psi:6,focus:1,die:"1d8",hit:9,dc:16,average:"9.5"},
    {level:7,pb:3,psi:7,focus:1,die:"1d8",hit:9,dc:16,average:"9.5"},{level:8,pb:3,psi:7,focus:1,die:"1d8",hit:9,dc:16,average:"9.5"},
    {level:9,pb:4,psi:9,focus:2,die:"1d8",hit:11,dc:17,average:"9.5"},{level:10,pb:4,psi:9,focus:2,die:"1d8",hit:11,dc:17,average:"9.5"},
    {level:11,pb:4,psi:10,focus:2,die:"1d10",hit:11,dc:17,average:"10.5"},{level:12,pb:4,psi:10,focus:2,die:"1d10",hit:11,dc:17,average:"10.5"},
    {level:13,pb:5,psi:12,focus:2,die:"1d10",hit:12,dc:18,average:"10.5"},{level:14,pb:5,psi:12,focus:2,die:"1d10",hit:12,dc:18,average:"10.5"},
    {level:15,pb:5,psi:13,focus:2,die:"1d10",hit:12,dc:18,average:"10.5"},{level:16,pb:5,psi:13,focus:2,die:"1d10",hit:12,dc:18,average:"10.5"},
    {level:17,pb:6,psi:15,focus:3,die:"1d12",hit:14,dc:19,average:"11.5"},{level:18,pb:6,psi:15,focus:3,die:"1d12",hit:14,dc:19,average:"11.5"},
    {level:19,pb:6,psi:16,focus:3,die:"1d12",hit:14,dc:19,average:"11.5"},{level:20,pb:6,psi:16,focus:3,die:"1d12",hit:14,dc:19,average:"11.5"}
  ];
  for(const candidate of boundaries){
    change(level,String(candidate.level));trigger=results.querySelector<HTMLElement>(".calculator__trigger")!;assertCalculatorText(trigger,`Hit: 1d20 + ${candidate.hit}`);
    assertCalculatorText(trigger,`Damage: ${candidate.die} + 5`);assertCalculatorText(trigger,`Expected avg damage: ${candidate.average}`);assertCalculatorText(results,`Strength save: DC ${candidate.dc}`);assertCalculatorSaveCalculation(results,candidate.pb,5,candidate.dc);
    assertCalculatorStrikeCalculations(trigger,candidate.pb,5,candidate.focus,candidate.die);
    assertCalculatorPsiFacts(results,0,candidate.psi);
    assert.equal(feature.options.length,21);for(const [id,,minimumLevel] of calculatorFeatures){const option=[...feature.options].find(value=>value.value===id)!;assert.ok(option);assert.equal(option.disabled,minimumLevel>candidate.level,`${id} availability at level ${candidate.level}`);}
    for(const tier of [0,1,2])assert.ok(calculatorTierHeadings(results).some(heading=>heading.endsWith(`Tier ${tier}`)),`Tier ${tier} remains shown at level ${candidate.level}`);
    if(candidate.level<10)assertCalculatorText(results,"Available at Fighter level 10.");else assert.doesNotMatch(results.textContent??"",/Available at Fighter level 10\./u);
  }
  for(const [id,title] of calculatorFeatures){const option=[...feature.options].find(candidate=>candidate.value===id);assert.ok(option&&!option.disabled,id);assert.equal(option.textContent?.trim(),title);}
  await settleOnboarding();dom.window.close();
});

test("one selected calculator feature card shows all tier damage, authored saves, Psi costs, and Blood Tax",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator",beforeParse(window:any){installOnboardingBrowserShims(window);}});
  const root=dom.window.document.querySelector<HTMLElement>("#calculator-root")!;assert.ok(root);const feature=root.querySelector<HTMLSelectElement>("#calculator-feature")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!,results=root.querySelector<HTMLElement>("#calculator-feature-results")!;
  const change=(control:HTMLSelectElement,value:string)=>{control.value=value;assert.equal(control.value,value);control.dispatchEvent(new dom.window.Event("change",{bubbles:true}));};
  change(level,"11");
  const typedSaveCount=()=>[results,...results.querySelectorAll("*")].filter(element=>/^(?:Strength|Constitution|Dexterity|Charisma|Intelligence) save: DC \d+$/u.test(normalizedCalculatorText(element))).length;
  const assertSaveTiers=(expected:string)=>assert.equal(results.querySelector<HTMLElement>(".calculator__save")?.dataset.saveTiers,expected);
  const selectRider=(id:string,title:string)=>{change(feature,id);assertCalculatorText(results,title);assert.equal(root.querySelectorAll("#calculator-feature-results.calculator__result").length,1);assert.equal(exactCalculatorTextCount(results,"Triggering Manifested Strike"),1);assert.deepEqual(calculatorTierHeadings(results),["Tier 0","Tier 1","Tier 2"],title);assert.equal(results.querySelectorAll(".calculator__facts").length,1);assertCalculatorPsiTotal(results,calculatorPsiPointsAtLevel(Number(level.value)));assert.doesNotMatch(results.textContent??"",/Psionic Save DC:/u);assert.doesNotMatch(results.textContent??"",/\bT[012] (?:Base|Overload):|Changes from Tier/iu);};
  selectRider("telekinetic_shove","Telekinetic Shove");
  assert.equal(exactCalculatorTextCount(results,"Strength save: DC 17"),1);assertCalculatorSaveCalculation(results,4,5,17);assertCalculatorPsiFacts(results,0,10);assertSaveTiers("0 1 2");
  assertCalculatorText(results,"Applies to Tiers 0–2.");
  assert.equal(exactCalculatorTextCount(results,"Rider damage: 2"),3);assert.equal(exactCalculatorTextCount(results,"Combined damage: 1d10 + 7"),3);assert.equal(exactCalculatorTextCount(results,"Expected combined damage: 12.5"),3);
  assert.equal(exactCalculatorTextCount(results,"Blood Tax: 0"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 4"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 8"),1);
  selectRider("cinder_lance","Cinder Lance");for(const [rider,combined,average] of [["2d10","3d10 + 5","21.5"],["3d10","4d10 + 5","27"],["4d10","5d10 + 5","32.5"]] as const){
    assertCalculatorText(results,`Rider damage: ${rider}`);assertCalculatorText(results,`Combined damage: ${combined}`);assertCalculatorText(results,`Expected combined damage: ${average}`);
  }
  assert.equal(exactCalculatorTextCount(results,"Psi cost: 3"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 0"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 4"),1);assert.equal(exactCalculatorTextCount(results,"Blood Tax: 8"),1);assert.equal(typedSaveCount(),0);assertCalculatorSaveCalculation(results,4,5,17,0);
  assertCalculatorText(results,"No feature tier requires a saving throw.");
  selectRider("glacial_spike","Glacial Spike");assert.equal(exactCalculatorTextCount(results,"Constitution save: DC 17"),1);assertCalculatorSaveCalculation(results,4,5,17);assert.equal(typedSaveCount(),1);assertSaveTiers("1 2");
  assertCalculatorText(results,"Applies to Tiers 1–2.");
  selectRider("static_discharge","Static Discharge");assert.equal(exactCalculatorTextCount(results,"Charisma save: DC 17"),1);assertCalculatorSaveCalculation(results,4,5,17);assert.equal(typedSaveCount(),1);assertSaveTiers("2");
  assert.deepEqual(calculatorEffectPaths(results,0),["entities.static_discharge.content.0.body.0"]);assert.deepEqual(calculatorEffectPaths(results,1),["entities.static_discharge.content.1.body.1"]);assert.deepEqual(calculatorEffectPaths(results,2),calculatorListItemPaths("entities.static_discharge.content.2.body.1",4));
  assertCalculatorText(results,"Applies to Tier 2.");
  selectRider("ember_bolt","Ember Bolt");assert.equal(typedSaveCount(),0);assert.equal(results.querySelector(".calculator__save"),null);assertCalculatorSaveCalculation(results,4,5,17,0);assert.equal(exactCalculatorTextCount(results,"No feature tier requires a saving throw."),1);
  selectRider("explosion_implosion","Explosion/Implosion");
  assertCalculatorText(results,"Rider damage: 5 on a failed save · 0 on a successful save");
  assertCalculatorText(results,"Combined damage: 1d10 + 10 on a failed save · 1d10 + 5 on a successful save");
  assertCalculatorText(results,"Expected combined damage: 15.5 on a failed save · 10.5 on a successful save");
  assert.equal(exactCalculatorTextCount(results,"Strength save: DC 17"),1);assertCalculatorSaveCalculation(results,4,5,17);assertSaveTiers("0 1 2");
  assert.deepEqual(calculatorEffectPaths(results,0),["entities.explosion_implosion.content.0.body.0",...calculatorListItemPaths("entities.explosion_implosion.content.0.body.1",2),...calculatorListItemPaths("entities.explosion_implosion.content.0.body.2",2)]);
  assert.deepEqual(calculatorEffectPaths(results,1),["entities.explosion_implosion.content.2.body.0"]);
  assert.deepEqual(calculatorEffectPaths(results,2),["entities.explosion_implosion.content.3.body.0"]);
  assert.deepEqual([...results.querySelectorAll<HTMLElement>('.calculator__tier[data-tier="0"] .calculator__effects > ul')].map(list=>list.querySelectorAll(":scope > li").length),[2,2]);
  assert.deepEqual([...results.querySelectorAll<HTMLElement>('.calculator__tier[data-tier="0"] .calculator__effects li > strong')].map(normalizedCalculatorText),["Explosion (outward):","Implosion (inward):","Struck target:","Successful save:"]);
  assertCalculatorText(results,"Each creature other than the struck target that fails is also pushed 15 feet away from the target.");
  assertCalculatorText(results,"The Sphere’s radius and push or pull distance both increase to 30 feet.");
  assert.deepEqual(calculatorSharedEffectPaths(results),["entities.explosion_implosion.content.1","entities.explosion_implosion.content.4"]);
  change(level,"20");selectRider("flare","Flare");assert.equal(exactCalculatorTextCount(results,"Dexterity save: DC 19"),1);assertCalculatorSaveCalculation(results,6,5,19);assert.equal(typedSaveCount(),1);assertSaveTiers("0");
  assertCalculatorText(results,"Applies to Tier 0.");
  selectRider("advanced_mind_lock","Mind Lock");assert.equal(exactCalculatorTextCount(results,"Intelligence save: DC 19"),1);assertCalculatorSaveCalculation(results,6,5,19);assert.equal(typedSaveCount(),1);assertSaveTiers("1 2");
  assertCalculatorText(results,"Applies to Tiers 1–2.");
  for(const [id,title] of calculatorRiders)selectRider(id,title);
  await settleOnboarding();dom.window.close();
});

test("six registered standalone damage features render exact standalone calculations without a triggering strike",async()=>{
  const result=await executeBuild("prototype");const html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator",beforeParse(window:any){installOnboardingBrowserShims(window);}});
  const root=dom.window.document.querySelector<HTMLElement>("#calculator-root")!,feature=root.querySelector<HTMLSelectElement>("#calculator-feature")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!,modifier=root.querySelector<HTMLSelectElement>("#calculator-psi-modifier")!,results=root.querySelector<HTMLElement>("#calculator-feature-results")!;
  const change=(control:HTMLSelectElement,value:string)=>{control.value=value;assert.equal(control.value,value);control.dispatchEvent(new dom.window.Event("change",{bubbles:true}));};
  const tier=(value:number)=>{const section=results.querySelector<HTMLElement>(`.calculator__tier[data-tier="${value}"]`)!;assert.ok(section);return section;};
  const selectStandalone=(id:string,title:string)=>{const option=[...feature.options].find(candidate=>candidate.value===id)!;assert.ok(option&&!option.disabled,id);change(feature,id);assert.equal(results.querySelector(":scope > h3")?.textContent,title);assert.equal(root.querySelectorAll("#calculator-feature-results.calculator__result:not([hidden])").length,1);assert.equal(results.querySelector(".calculator__trigger"),null);assert.equal(exactCalculatorTextCount(results,"Triggering Manifested Strike"),0);assert.deepEqual(calculatorTierHeadings(results),["Tier 0","Tier 1","Tier 2"],title);assert.deepEqual([...results.querySelectorAll<HTMLElement>(".calculator__tier")].map(section=>section.dataset.available),["true","true","true"],title);assert.equal(results.querySelector(".calculator__availability"),null);assert.equal(results.querySelectorAll(".calculator__facts").length,1);assert.equal(results.querySelectorAll(".calculator__breakdown").length,0);assert.doesNotMatch(results.textContent??"",/Rider damage:|Combined damage:|Expected combined damage:|Psionic Save DC:|\bT[012] (?:Base|Overload):|Changes from Tier/iu,title);};
  const assertStandaloneFacts=(saveLabel:string,dc:number,psi:number,taxes:readonly number[])=>{assertCalculatorPsiFacts(results,psi,calculatorPsiPointsAtLevel(Number(level.value)));assert.equal(exactCalculatorTextCount(results,`${saveLabel} save: DC ${dc}`),1);assertCalculatorSaveCalculation(results,calculatorProficiencyBonusAtLevel(Number(level.value)),Number(modifier.value),dc);const saves=results.querySelectorAll<HTMLElement>(".calculator__save");assert.equal(saves.length,1);assert.equal(saves[0]!.dataset.saveTiers,"0 1 2");assertCalculatorText(results,"Applies to Tiers 0–2.");for(const tax of taxes)assert.equal([...results.querySelectorAll(".calculator__metrics > p")].filter(metric=>normalizedCalculatorText(metric)===`Blood Tax: ${tax}`).length,1);};
  const assertSingleTargetDamage=(tierIndex:number,expression:string,failed:string,success:string)=>{const section=tier(tierIndex);assert.equal(exactCalculatorTextCount(section,`Damage: ${expression} on a failed save · half on a successful save`),1);assert.equal(exactCalculatorTextCount(section,`Expected avg damage: ${failed} on a failed save · ${success} on a successful save`),1);};
  const assertForkedDamage=(tierIndex:number,primary:string,primaryFailed:string,primarySuccess:string,secondary:string,secondaryFailed:string,secondarySuccess:string)=>{const section=tier(tierIndex);assert.equal(exactCalculatorTextCount(section,`Primary target damage: ${primary} on a failed save · half on a successful save`),1);assert.equal(exactCalculatorTextCount(section,`Expected avg primary target damage: ${primaryFailed} on a failed save · ${primarySuccess} on a successful save`),1);assert.equal(exactCalculatorTextCount(section,`Secondary target damage: ${secondary} on a failed save · half on a successful save`),1);assert.equal(exactCalculatorTextCount(section,`Expected avg secondary target damage: ${secondaryFailed} on a failed save · ${secondarySuccess} on a successful save`),1);};

  change(level,"15");selectStandalone("telekinetic_slam","Telekinetic Slam");
  assert.deepEqual(calculatorStandaloneFeatures.filter(([, ,minimum])=>minimum===15).map(([id])=>id).sort(),["arctic_tempest","forked_lightning","telekinetic_slam"]);
  assertStandaloneFacts("Strength",18,3,[0,5,10]);
  const slamDamage=[["8d10","44","21.75"],["10d10","55","27.25"],["12d10","66","32.75"]] as const;
  for(const [tierIndex,[expression,failed,success]] of slamDamage.entries())assertSingleTargetDamage(tierIndex,expression,failed,success);
  assert.deepEqual(calculatorEffectPaths(results,0),["entities.telekinetic_slam.content.1.body.0"]);
  assert.deepEqual(calculatorEffectPaths(results,1),["entities.telekinetic_slam.content.2.body.1"]);
  assert.deepEqual(calculatorEffectPaths(results,2),calculatorListItemPaths("entities.telekinetic_slam.content.3.body.1",3));
  assert.deepEqual(calculatorSharedEffectPaths(results),["entities.telekinetic_slam.content.0"]);
  change(modifier,"4");assertStandaloneFacts("Strength",17,3,[0,5,10]);
  assertSingleTargetDamage(0,"8d10","44","21.75");
  change(modifier,"5");

  selectStandalone("forked_lightning","Forked Lightning");
  assertStandaloneFacts("Charisma",18,3,[0,5,10]);
  const forkedDamage=[["8d8","36","17.75","4d8","18","8.75"],["10d8","45","22.25","5d8","22.5","11"],["12d8","54","26.75","6d8","27","13.25"]] as const;
  for(const [tierIndex,[primary,primaryFailed,primarySuccess,secondary,secondaryFailed,secondarySuccess]] of forkedDamage.entries())assertForkedDamage(tierIndex,primary,primaryFailed,primarySuccess,secondary,secondaryFailed,secondarySuccess);
  assert.deepEqual(calculatorEffectPaths(results,0),calculatorListItemPaths("entities.forked_lightning.content.0.body.0",5));
  assert.deepEqual(calculatorEffectPaths(results,1),calculatorListItemPaths("entities.forked_lightning.content.1.body.1",4));
  assert.deepEqual(calculatorEffectPaths(results,2),calculatorListItemPaths("entities.forked_lightning.content.2.body.1",8));
  assert.deepEqual(calculatorSharedEffectPaths(results),[]);
  assert.deepEqual([...tier(2).querySelectorAll(".calculator__effects li > strong")].map(normalizedCalculatorText),["Targets:","Saving throws:","Primary damage:","Secondary damage:","Failed-save conditions:","Successful save:","Primary target only:","Secondary targets:"]);

  change(level,"20");selectStandalone("mass_levitation","Mass Levitation");
  assertStandaloneFacts("Strength",19,5,[0,6,12]);
  for(const tierIndex of [0,1]){const labels=[...tier(tierIndex).querySelectorAll("strong")].map(normalizedCalculatorText);assert.equal(labels.includes("Damage:"),false);assert.equal(labels.includes("Expected avg damage:"),false);}
  assert.equal(exactCalculatorTextCount(tier(2),"Damage: 10 on a failed save · 0 on a successful save"),1);assert.equal(exactCalculatorTextCount(tier(2),"Expected avg damage: 10 on a failed save · 0 on a successful save"),1);
  change(modifier,"4");
  assert.deepEqual(calculatorEffectPaths(results,0),["entities.mass_levitation.content.0.body.0",...calculatorListItemPaths("entities.mass_levitation.content.0.body.1",4)]);
  assert.deepEqual(calculatorEffectPaths(results,1),["entities.mass_levitation.content.1.body.0"]);
  assert.deepEqual(calculatorEffectPaths(results,2),["entities.mass_levitation.content.2.body.0"]);
  assert.deepEqual(calculatorSharedEffectPaths(results),[]);
  assert.deepEqual([...tier(0).querySelectorAll(".calculator__effects li > strong")].map(normalizedCalculatorText),["Targeting:","Initial saving throw:","Repeat saving throw:","Ongoing effect:"]);
  assertStandaloneFacts("Strength",18,5,[0,6,12]);
  assert.equal(exactCalculatorTextCount(tier(2),"Damage: 8 on a failed save · 0 on a successful save"),1);assert.equal(exactCalculatorTextCount(tier(2),"Expected avg damage: 8 on a failed save · 0 on a successful save"),1);
  change(modifier,"5");

  const singleTargetCases=[
    {id:"arctic_tempest",title:"Arctic Tempest",save:"Constitution",psi:3,damage:[["8d10","44","21.75"],["10d10","55","27.25"],["12d10","66","32.75"]]},
    {id:"absolute_zero",title:"Absolute Zero",save:"Constitution",psi:5,damage:[["10d10","55","27.25"],["12d10","66","32.75"],["14d10","77","38.25"]]},
    {id:"ball_lightning",title:"Ball Lightning",save:"Charisma",psi:5,damage:[["4d8","18","8.75"],["4d8","18","8.75"],["4d8","18","8.75"]]}
  ] as const;
  for(const candidate of singleTargetCases){
    selectStandalone(candidate.id,candidate.title);
    assertStandaloneFacts(candidate.save,19,candidate.psi,[0,6,12]);
    for(const [tierIndex,[expression,failed,success]] of candidate.damage.entries())assertSingleTargetDamage(tierIndex,expression,failed,success);
    if(candidate.id==="ball_lightning"){assert.deepEqual(calculatorEffectPaths(results,0),calculatorListItemPaths("entities.ball_lightning.content.0.body.0",5));assert.deepEqual(calculatorEffectPaths(results,1),["entities.ball_lightning.content.1.body.1"]);assert.deepEqual(calculatorEffectPaths(results,2),calculatorListItemPaths("entities.ball_lightning.content.2.body.1",2));assert.deepEqual(calculatorSharedEffectPaths(results),["entities.ball_lightning.content.3"]);}
  }
  await settleOnboarding();dom.window.close();
});

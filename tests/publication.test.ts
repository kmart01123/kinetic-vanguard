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
  assert.match(html,/NON-RELEASE PROTOTYPE/);assert.match(html,/"release_status":"prototype"/);assert.match(html,/<div class="versions"><span>Rules version: 14\.3\.0<\/span><\/div>/);
  assert.doesNotMatch(html,/<(?:script|link|img)[^>]+(?:src|href)=["']https?:/i);assert.doesNotMatch(html,/(?:fetch|XMLHttpRequest|localStorage|sessionStorage|indexedDB|serviceWorker)/);
  assert.doesNotMatch(html,/<input[^>]+type=["'](?:text|search|number)["']/i);assert.doesNotMatch(html,/<textarea|contenteditable|aria-autocomplete/i);
  assert.doesNotMatch(html,/Application version|application_version|0\.1\.0/);
  const provenanceSource=html.match(/<script type="application\/json" id="publication-provenance">([^<]+)<\/script>/)?.[1];assert.ok(provenanceSource);
  const provenance=JSON.parse(provenanceSource);
  assert.deepEqual(Object.keys(provenance).sort(),["authority_sha256","release_status","rules_version","schema_version"]);
  assert.equal(provenance.rules_version,"14.3.0");
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
  const tiers=[...glacialDocument.querySelectorAll<HTMLElement>(".calculator__canonical-rules > .feature-tier")];
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
  assert.equal(glacialDocument.querySelector("#calculator-feature-results > h3")?.textContent,"Glacial Spike");assert.equal(glacialDocument.querySelector(".calculator__canonical-rules [role=heading]"),null);
  const empathic=createDom("category=common_features&topic=common_features_common_empathic_sense_topic");const empathicArticle=empathic.window.document.querySelector<HTMLElement>(".calculator__canonical-rules")!;
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
  const article=(id:string)=>{const document=rendered.find(item=>item.id===id)!.dom.window.document;return document.querySelector<HTMLElement>(`#entity-${id}`)??document.querySelector<HTMLElement>(".calculator__canonical-rules")!;};
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
  const article=(id:string)=>{const dom=new JSDOM(html,{runScripts:"dangerously",url:`https://local.invalid/KineticVanguard.prototype.html#entity=${id}`,beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});doms.push(dom);return dom.window.document.querySelector<HTMLElement>(`#entity-${id}`)??dom.window.document.querySelector<HTMLElement>(".calculator__canonical-rules")!;};
  const directLists=(parent:Element)=>[...parent.children].filter(child=>child.tagName==="OL"||child.tagName==="UL") as HTMLElement[];
  const shape=(parent:Element)=>directLists(parent).map(list=>[list.tagName,list.querySelectorAll(":scope > li").length]);
  const common={
    how_to_play:[["OL",6],["UL",6],["UL",4],["UL",4],["UL",2],["UL",3]],
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
  for(const [feature,duration] of [["Explosion/Implosion","Until the end of your next turn"],["Phase Step","Varies by tier"],["Electron Burst","Varies by tier"],["Vectored Thrust","Up to 10 minutes"],["Frozen Ground","Concentration, up to 1 minute"],["Mass Levitation","Concentration, up to 1 minute"],["Ball Lightning","Concentration, up to 1 minute"],["Gravitic Press","Concentration, up to 1 minute"],["Beguile","Varies by tier"],["Barrier","Varies by tier"],["Inner Reserve","Continuous"],["Overload Mastery II","Continuous"]] as const)assert.equal(byFeature.get(feature),duration);
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
  assert.ok(document.querySelector("#calculator-root"));assert.equal(document.querySelector("#calculator-feature-results > h3")?.textContent,"Glacial Spike");assert.match(dom.window.location.hash,/^#calculator&card=glacial_spike&/u);
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


test("release build requires explicit authorization",async()=>{await assert.rejects(()=>executeBuild("release"),/release\.approval_required/);});


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
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=common_features&topic=common_features_how_to_play_topic&filters=rules_area:psychokinesis",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
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
  const metadata=(document:Document,entityId:string)=>{const scope=document.querySelector(`#entity-${entityId}`)??document.querySelector("#calculator-feature-results")!;return [...scope.querySelectorAll<HTMLElement>(".feature-metadata__item")].map(item=>({term:item.querySelector("dt")?.textContent,value:item.querySelector("dd")?.textContent,classes:item.className}));};

  const gravitic=render(html,"advanced_training","advanced_training_advanced_gravitic_press_topic");
  const graviticMetadata=metadata(gravitic.window.document,"advanced_gravitic_press");
  assert.ok(graviticMetadata.some(item=>item.term==="Psi"&&item.value==="3"));
  assert.ok(graviticMetadata.some(item=>item.term==="Activation"&&item.value==="Action"));
  assert.ok(graviticMetadata.some(item=>item.term==="Requirement"&&item.value==="Concentration"&&item.classes.includes("feature-metadata__item--concentration")));
  assert.equal(gravitic.window.document.querySelector("#calculator-feature-results .feature-metadata")?.tagName,"DL");

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
  assert.ok(metadata(vectored.window.document,"vectored_thrust").some(item=>item.term==="Requirement"&&item.value==="Concentration (T0–T1)"&&item.classes.includes("feature-metadata__item--concentration")));
  assert.ok(metadata(barrier.window.document,"advanced_barrier").some(item=>item.term==="Requirement"&&item.value==="Concentration"&&item.classes.includes("feature-metadata__item--concentration")));
  const barrierLists=barrier.window.document.querySelectorAll(".calculator__canonical-rules > ul");assert.equal(barrierLists.length,1);
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
  const manifested=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator",beforeParse(window:any){window.structuredClone=globalThis.structuredClone;window.CSS={escape:(value:string)=>value};}});
  const empathic=render(html,"common_features","common_features_common_empathic_sense_topic");
  assert.ok(metadata(rider.window.document,"glacial_spike").some(item=>item.term==="Activation"&&item.value==="Declared before roll · Resolves on hit"));
  assert.ok(metadata(manifested.window.document,"common_manifested_strike").some(item=>item.term==="Activation"&&item.value==="Attack action · Replaces an attack"));
  assert.ok(metadata(empathic.window.document,"common_empathic_sense").some(item=>item.term==="Activation"&&item.value==="Passive"));
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
  assert.match(descriptionOnly.window.document.querySelector(".calculator__canonical-rules p")?.textContent??"",/mentions concentration/);
  assert.equal(descriptionOnly.window.document.querySelector("#calculator-feature-results .feature-metadata__item--concentration"),null);

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
  const common=createDom("#category=common_features&topic=common_features_common_overload_topic");assert.deepEqual([...common.window.document.querySelectorAll<HTMLOptionElement>("#category-select option")].map(option=>option.value),["common_features"]);assert.equal(topicTitles(common.window.document).filter(title=>title==="Overload").length,1);assert.equal(topicTitles(common.window.document).length,11);
  const legacy=createDom("#category=psychokinesis&topic=psychokinesis_telekinetic_shove_topic");assert.equal(legacy.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"calculator");assert.equal(legacy.window.document.querySelector("#calculator-feature-results > h3")?.textContent,"Telekinetic Shove");
  const invalid=createDom("#category=psychokinesis&topic=common_features_common_overload_topic");const invalidDocument=invalid.window.document;
  assert.equal((invalidDocument.querySelector("#category-select") as HTMLSelectElement).value,"common_features");assert.equal((invalidDocument.querySelector("#topic-select") as HTMLSelectElement).value,"common_features_common_overload_topic");assert.equal(invalidDocument.querySelector("#entity-common_overload h2")?.textContent,"Overload");assert.equal(invalid.window.location.hash,"#category=common_features&topic=common_features_common_overload_topic");
  await new Promise<void>(resolve=>setImmediate(resolve));common.window.close();legacy.window.close();invalid.window.close();
});

function installOnboardingBrowserShims(window:any):void {
  window.structuredClone=globalThis.structuredClone;
  window.CSS={escape:(value:string)=>value.replace(/[^a-zA-Z0-9_-]/g,"_")};
  Object.defineProperty(window.HTMLElement.prototype,"scrollIntoView",{configurable:true,value(){}});
}

const settleOnboarding=()=>new Promise<void>(resolve=>setImmediate(resolve));



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
  assert.equal(home.querySelectorAll(".home-card-list .home-card").length,4);assert.equal(home.querySelectorAll(".home-card__title").length,5);assert.equal(home.querySelectorAll(".home-checklist > li").length,6);assert.equal(home.querySelectorAll(".home-glossary > dt").length,5);assert.equal(home.querySelectorAll(".home-glossary > dd").length,5);
  const bloodTaxCard=home.querySelector<HTMLElement>('.home-blood-tax[data-onboarding-id="start_blood_tax"]')!;assert.ok(bloodTaxCard);assert.equal(bloodTaxCard.querySelector("h3")?.textContent,"Blood Tax");assert.equal(bloodTaxCard.querySelector("p")?.textContent,onboarding.blood_tax.description);
  const headingLevels=[...document.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5,h6")].map(heading=>Number(heading.tagName.slice(1)));assert.equal(home.querySelectorAll("h1").length,0);assert.equal(home.querySelectorAll("h2").length,1);for(let position=1;position<headingLevels.length;position++)assert.ok(headingLevels[position]!<=headingLevels[position-1]!+1,`heading level skipped at position ${position}`);

  const internal=onboarding.primary_paths.filter(path=>path.destination.kind==="onboarding_section");
  for(const path of internal){const control=document.querySelector<HTMLElement>(`[data-onboarding-link-id="${path.id}"]`)!;assert.equal(control.tagName,"BUTTON");assert.equal(control.getAttribute("data-destination-kind"),"onboarding_section");assert.ok(control.textContent?.includes(path.title));control.click();assert.equal(document.activeElement?.id,`${path.destination.kind==="onboarding_section"?path.destination.section_id:""}_heading`);assert.equal(layout.dataset.view,"home");}

  const links=[onboarding.blood_tax,...onboarding.primary_paths,...onboarding.disciplines.cards,...onboarding.basic_turn.destinations,...onboarding.build_checklist.items,...onboarding.glossary.entries,...onboarding.next_destinations.items].filter(link=>link.destination.kind!=="onboarding_section");
  const categoryById=new Map(authority.navigation.categories.map(category=>[category.id,category])),entryById=new Map(index.entities.map(entry=>[entry.id,entry])),utilityEntity=new Map<string,(typeof authority.entities)[number]>(authority.calculator.utility_cards.map(card=>[card.id,authority.entities.find(entity=>entity.id===card.source_entity_id)!])),calculatorCards:string[]=[...authority.calculator.utility_cards.map(card=>card.id),...authority.entities.filter(entity=>entity.presentation_metadata.presentation_owner==="calculator_deck"||(entity.kind==="feature"&&entity.presentation_metadata.primary_rules_area!=="common_features")).map(entity=>entity.id)];
  const destination=(value:any)=>{
    if(value.kind==="category"){const category=categoryById.get(value.category_id)!;return{fragment:`#category=${category.id}&topic=${category.default_topic_id}`,entityId:category.topics.find(topic=>topic.id===category.default_topic_id)!.entity_ids[0]!};}
    if(value.kind==="calculator"){const card=value.card_id??(value.rules_area?calculatorCards.find(id=>(utilityEntity.get(id)??authority.entities.find(entity=>entity.id===id))?.presentation_metadata.primary_rules_area===value.rules_area):undefined)??"manifested_strike",entity=utilityEntity.get(card)??authority.entities.find(candidate=>candidate.id===card),area=value.rules_area??(value.card_id?entity?.presentation_metadata.primary_rules_area:undefined),group=area?`&group=${area}`:"";return{fragment:`#calculator&card=${card}&level=20&modifier=5${group}`,entityId:card,view:"calculator"};}
    const entry=entryById.get(value.entity_id)!;const area=entry.primary_rules_area,topic=entry.routes[area]!;return{fragment:`#category=${area}&topic=${topic}&entity=${entry.id}`,entityId:entry.id};
  };
  assert.equal(new Set(links.map(link=>link.id)).size,links.length);
  for(const link of links){
    const expected=destination(link.destination),control=document.querySelector<HTMLAnchorElement>(`[data-onboarding-link-id="${link.id}"]`)!;
    assert.equal(control.tagName,"A",link.id);assert.equal(control.getAttribute("data-destination-kind"),link.destination.kind,link.id);assert.equal(control.getAttribute("href"),expected.fragment,link.id);assert.ok(control.textContent?.includes(link.title),link.id);
    control.click();if(link.destination.kind==="calculator"){assert.equal(layout.dataset.view,"calculator",link.id);assert.ok(document.querySelector("#calculator-root"),link.id);assert.equal(document.activeElement?.id,"calculator-heading",link.id);assert.equal(document.querySelector<HTMLElement>('.calculator__card[aria-pressed="true"]')?.dataset.cardId,expected.entityId,link.id);}else{assert.equal(layout.dataset.view,"reference",link.id);assert.equal(document.querySelector<HTMLElement>(".controls")?.hidden,false,link.id);const heading=document.querySelector<HTMLElement>(`#entity-${expected.entityId} > h2`)!;assert.ok(heading,link.id);assert.equal(document.activeElement,heading,link.id);if(link.destination.kind==="entity")assert.equal((document.querySelector("#name-select") as HTMLSelectElement).value,link.destination.entity_id,link.id);}
    (document.querySelector("#view-start-here") as HTMLElement).click();assert.equal(layout.dataset.view,"home",link.id);assert.equal(document.activeElement?.id,"start_here_heading",link.id);
  }
  await settleOnboarding();dom.window.close();
});

const normalizedDeckText=(element:Element)=>element.textContent?.replace(/\s+/g," ").trim()??"";
const deckTextCount=(root:Element,text:string)=>[root,...root.querySelectorAll("*")].filter(element=>normalizedDeckText(element)===text).length;
const changeDeckSelect=(dom:JSDOM,control:HTMLSelectElement,value:string)=>{control.value=value;assert.equal(control.value,value);control.dispatchEvent(new dom.window.Event("change",{bubbles:true}));};
const clickDeckCard=(document:Document,id:string)=>{const button=document.querySelector<HTMLButtonElement>(`.calculator__card[data-card-id="${id}"]`)!;assert.ok(button,id);button.click();return document.querySelector<HTMLElement>("#calculator-feature-results")!;};

test("Calculator is the exhaustive 35-card player-facing Feature Deck",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8"),{authority}=await loadAuthority();
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator",beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=dom.window.document,root=document.querySelector<HTMLElement>("#calculator-root")!;
  assert.ok(root);assert.equal(document.querySelector<HTMLElement>("main.layout")?.dataset.view,"calculator");
  const controls=[...root.querySelectorAll<HTMLSelectElement>("select")];assert.deepEqual(controls.map(control=>control.id),["calculator-feature-group","calculator-level","calculator-psi-modifier"]);
  assert.ok(controls.every(control=>control.getAttribute("aria-controls")==="calculator-deck calculator-feature-results"));
  const cards=[...root.querySelectorAll<HTMLButtonElement>(".calculator__card")],ids=cards.map(card=>card.dataset.cardId!);
  assert.equal(cards.length,35);assert.equal(new Set(ids).size,35);assert.deepEqual(ids.slice().sort(),[...authority.calculator.features.map(feature=>feature.entity_id),...authority.calculator.utility_cards.map(card=>card.id),"common_psionic_link","advanced_barrier","advanced_overload_mastery_ii"].sort());
  assert.equal(cards.filter(card=>card.textContent?.includes("Calculated")).length,32);assert.equal(cards.filter(card=>card.textContent?.includes("Reference only")).length,3);
  const selected=root.querySelector<HTMLButtonElement>('.calculator__card[aria-pressed="true"]')!;assert.equal(selected.dataset.cardId,"manifested_strike");assert.equal(root.querySelector("#calculator-feature-results > h3")?.textContent,"Manifested Strike");
  assert.equal(root.querySelectorAll(".calculator__canonical-rules").length,1);assert.equal(deckTextCount(root,"Complete canonical rules"),1);
  const bloodTaxCard=root.querySelector<HTMLButtonElement>('.calculator__card[data-card-id="blood_tax"]')!;assert.ok(bloodTaxCard);assert.equal(bloodTaxCard.closest(".calculator__group")?.querySelector(":scope > h3")?.textContent,"Common Features");assert.match(normalizedDeckText(bloodTaxCard),/^Blood TaxOverload self-damage · Level 3\+ · Calculated$/u);bloodTaxCard.click();assert.equal(root.querySelector<HTMLElement>('.calculator__card[aria-pressed="true"]')?.dataset.cardId,"blood_tax");assert.equal(root.querySelector("#calculator-feature-results > h3")?.textContent,"Blood Tax");
  changeDeckSelect(dom,root.querySelector<HTMLSelectElement>("#calculator-level")!,"3");const lowLevelCards=[...root.querySelectorAll<HTMLButtonElement>(".calculator__card")];assert.equal(lowLevelCards.length,35);assert.equal(lowLevelCards.filter(card=>card.dataset.available==="false").length>0,true);assert.ok(lowLevelCards.filter(card=>card.dataset.available==="false").every(card=>card.textContent?.includes("Future level")));
  await settleOnboarding();dom.window.close();
});

test("Feature Deck cards stay complete at low level and expose canonical content exactly once",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator&card=advanced_barrier&level=3&modifier=2&group=advanced_training",beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=dom.window.document,root=document.querySelector<HTMLElement>("#calculator-root")!;
  assert.equal(root.querySelectorAll(".calculator__card").length,10);assert.equal(root.querySelectorAll('.calculator__card[data-available="false"]').length>0,true);
  const detail=root.querySelector<HTMLElement>("#calculator-feature-results")!;assert.equal(detail.querySelector(":scope > h3")?.textContent,"Barrier");assert.equal(detail.querySelectorAll(".calculator__projection").length,0);assert.equal(detail.querySelectorAll(".calculator__reference-note").length,1);assert.equal(detail.querySelectorAll(".calculator__canonical-rules").length,1);assert.equal(deckTextCount(detail,"Complete canonical rules"),1);
  assert.match(normalizedDeckText(detail),/Reference only/u);assert.match(normalizedDeckText(detail),/Level15/u);
  clickDeckCard(document,"advanced_deflection_screen");const calculated=document.querySelector<HTMLElement>("#calculator-feature-results")!;assert.equal(calculated.querySelectorAll(".calculator__projection").length,1);assert.equal(calculated.querySelectorAll(".calculator__canonical-rules").length,1);assert.equal(calculated.querySelectorAll('.calculator__tier[data-available="false"]').length,3);assert.match(normalizedDeckText(calculated),/Available at Fighter level 5\./u);assert.match(normalizedDeckText(calculated),/Available at Fighter level 10\./u);
  await settleOnboarding();dom.window.close();
});

test("Feature Deck computes the newly projected values and authored save metadata",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator&card=frozen_ground&level=20&modifier=5",beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=dom.window.document,root=document.querySelector<HTMLElement>("#calculator-root")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!,modifier=root.querySelector<HTMLSelectElement>("#calculator-psi-modifier")!;
  let detail=root.querySelector<HTMLElement>("#calculator-feature-results")!;assert.match(normalizedDeckText(detail),/Constitution save: DC 19/u);assert.match(normalizedDeckText(detail),/Concentration.*up to 1 minute/u);
  detail=clickDeckCard(document,"vectored_thrust");assert.match(normalizedDeckText(detail),/Fly Speed: 60 feet/u);assert.match(normalizedDeckText(detail),/30 \+ \(5 × Proficiency Bonus 6\) = 60 feet/u);assert.match(normalizedDeckText(detail),/Concentration.*up to 10 minutes/u);
  detail=clickDeckCard(document,"common_empathic_sense");assert.match(normalizedDeckText(detail),/Active Scan uses: 3/u);assert.match(normalizedDeckText(detail),/floor\(Proficiency Bonus 6 ÷ 2\) = 3/u);assert.match(normalizedDeckText(detail),/Passive Insight bonus: \+5/u);
  detail=clickDeckCard(document,"static_discharge");assert.match(normalizedDeckText(detail),/Total targets: 7 creatures/u);
  detail=clickDeckCard(document,"advanced_deflection_screen");assert.match(normalizedDeckText(detail),/Damage reduction: 7d8 \+ 5/u);assert.match(normalizedDeckText(detail),/7d8 \+ \(1 × Psionic Ability Modifier 5\) = 7d8 \+ 5/u);assert.match(normalizedDeckText(detail),/Strength save: DC 19/u);
  detail=clickDeckCard(document,"advanced_improved_phase_step");assert.match(normalizedDeckText(detail),/Damage: 4d10 on a failed save/u);assert.match(normalizedDeckText(detail),/Discipline signature save: DC 19/u);
  detail=clickDeckCard(document,"advanced_inner_reserve");assert.match(normalizedDeckText(detail),/Maximum Psi Points with Inner Reserve: 20/u);assert.match(normalizedDeckText(detail),/Base Psi Points \(16\) \+ 4 = 20/u);
  changeDeckSelect(dom,level,"9");changeDeckSelect(dom,modifier,"3");detail=root.querySelector<HTMLElement>("#calculator-feature-results")!;assert.match(normalizedDeckText(detail),/Maximum Psi Points with Inner Reserve: 13/u);
  await settleOnboarding();dom.window.close();
});

test("Blood Tax is a tiered quick reference with canonical context and explicit Overload Mastery",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator&card=blood_tax&level=3&modifier=5",beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=dom.window.document,root=document.querySelector<HTMLElement>("#calculator-root")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!;
  const detail=()=>root.querySelector<HTMLElement>("#calculator-feature-results")!;
  const projectionMetrics=(text:string)=>[...detail().querySelectorAll<HTMLElement>(".calculator__projection .calculator__metrics > p")].filter(metric=>normalizedDeckText(metric)===text).length;
  const tiers=()=>[...detail().querySelectorAll<HTMLElement>(".calculator__tier")];assert.deepEqual(tiers().map(tier=>tier.querySelector("h5")?.textContent),["T0 — No Overload","T1 — Overload","T2 — Overload"]);assert.deepEqual(tiers().map(tier=>tier.dataset.available),["true","true","false"]);assert.equal(projectionMetrics("Blood Tax: 0 HP"),1);assert.equal(projectionMetrics("Calculation: 1 × Proficiency Bonus"),1);assert.equal(projectionMetrics("Blood Tax: 2 HP"),1);assert.equal(projectionMetrics("Calculation: 2 × Proficiency Bonus"),1);assert.equal(projectionMetrics("Blood Tax: 4 HP"),1);assert.match(normalizedDeckText(tiers()[2]!),/Available at Fighter level 10\./u);
  const context=detail().querySelector<HTMLElement>(".calculator__context")!;assert.equal(context.querySelector(":scope > h4")?.textContent,"Blood Tax rules context");for(const rule of [/Blood Tax is psychic damage/u,/Blood Tax remain spent/u,/pay Blood Tax separately/u,/Temporary Hit Points cannot absorb, reduce, or pay Blood Tax/u,/Immunity to psychic damage instead functions as Resistance/u,/reduces you to 0 hit points/u,/only one rider can be Tier 2/u,/does not restrict standalone features/u])assert.match(normalizedDeckText(context),rule);
  changeDeckSelect(dom,level,"10");assert.deepEqual(tiers().map(tier=>tier.dataset.available),["true","true","true"]);assert.doesNotMatch(normalizedDeckText(tiers()[2]!),/Available at Fighter level/u);
  changeDeckSelect(dom,level,"18");assert.equal(projectionMetrics("Blood Tax: 6 HP"),1);assert.equal(projectionMetrics("Blood Tax: 12 HP"),1);assert.equal(projectionMetrics("With Overload Mastery: 3 HP"),1);assert.equal(projectionMetrics("With Overload Mastery: 6 HP"),1);const mastery=detail().querySelector<HTMLElement>(".calculator__mastery")!;assert.equal(mastery.querySelector(":scope > h4")?.textContent,"Overload Mastery");assert.match(normalizedDeckText(mastery),/Blood Tax divisor: 2/u);assert.match(normalizedDeckText(mastery),/Minimum per Overload: 1 HP/u);assert.match(normalizedDeckText(mastery),/Baseline uses per Short or Long Rest: 1/u);assert.match(normalizedDeckText(mastery),/Overload Mastery II is a selectable feature with a Psionic Apex prerequisite/u);
  await settleOnboarding();dom.window.close();
});

test("Calculator repairs card/group mismatches and restores valid history while invalid state fails closed",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8"),canonical="#calculator&card=glacial_spike&level=20&modifier=5&group=cryokinesis";
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator&card=glacial_spike&level=20&modifier=5&group=pyrokinesis",beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=dom.window.document;
  assert.equal(dom.window.location.hash,canonical);assert.equal(document.querySelector<HTMLSelectElement>("#calculator-feature-group")?.value,"cryokinesis");assert.equal(document.querySelector<HTMLElement>('.calculator__card[aria-pressed="true"]')?.dataset.cardId,"glacial_spike");assert.deepEqual({view:dom.window.history.state.view,card:dom.window.history.state.calculatorSelection,group:dom.window.history.state.calculatorFeatureGroup,level:dom.window.history.state.fighterLevel,modifier:dom.window.history.state.psiModifier},{view:"calculator",card:"glacial_spike",group:"cryokinesis",level:20,modifier:5});
  const restored={...structuredClone(dom.window.history.state),focusOrigin:"history"};dom.window.history.replaceState(restored,"",canonical);dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate",{state:restored}));assert.equal(document.querySelector<HTMLElement>("main.layout")?.dataset.view,"calculator");assert.equal(document.querySelector<HTMLElement>('.calculator__card[aria-pressed="true"]')?.dataset.cardId,"glacial_spike");assert.equal(document.querySelector<HTMLSelectElement>("#calculator-feature-group")?.value,"cryokinesis");assert.equal(document.querySelector<HTMLSelectElement>("#calculator-level")?.value,"20");assert.equal(document.querySelector<HTMLSelectElement>("#calculator-psi-modifier")?.value,"5");assert.equal(dom.window.location.hash,canonical);assert.equal(dom.window.history.state.focusOrigin,"history");
  const invalid={...restored,calculatorSelection:"missing_card",calculatorFeatureGroup:"pyrokinesis"};dom.window.history.replaceState(invalid,"",canonical);dom.window.dispatchEvent(new dom.window.PopStateEvent("popstate",{state:invalid}));assert.equal(dom.window.location.hash,canonical);assert.equal(dom.window.history.state.calculatorSelection,"glacial_spike");assert.equal(dom.window.history.state.calculatorFeatureGroup,"cryokinesis");assert.equal(document.querySelector<HTMLElement>('.calculator__card[aria-pressed="true"]')?.dataset.cardId,"glacial_spike");
  await settleOnboarding();dom.window.close();
});

test("Calculator rounds displayed expected averages upward after the underlying damage calculation",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8");const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#calculator&card=manifested_strike&level=5&modifier=5",beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=dom.window.document,root=document.querySelector<HTMLElement>("#calculator-root")!,level=root.querySelector<HTMLSelectElement>("#calculator-level")!;
  const detail=()=>normalizedDeckText(root.querySelector<HTMLElement>("#calculator-feature-results")!);assert.match(detail(),/Damage: 1d8 \+ 5.*Expected avg damage: 10/u);changeDeckSelect(dom,level,"11");assert.match(detail(),/Damage: 1d10 \+ 5.*Expected avg damage: 11/u);changeDeckSelect(dom,level,"17");assert.match(detail(),/Damage: 1d12 \+ 5.*Expected avg damage: 12/u);
  changeDeckSelect(dom,level,"3");let selected=clickDeckCard(document,"branching_bolt");assert.match(normalizedDeckText(selected),/Combined damage: 2d6 \+ 5.*Expected combined damage: 12/u);selected=clickDeckCard(document,"glacial_spike");assert.match(normalizedDeckText(selected),/Expected combined damage: 11/u);selected=clickDeckCard(document,"advanced_improved_phase_step");assert.match(normalizedDeckText(selected),/Expected avg damage: 22 on a failed save · 11 on a successful save/u);selected=clickDeckCard(document,"advanced_deflection_screen");assert.match(normalizedDeckText(selected),/Damage reduction: 3d8 \+ 5.*Expected avg damage: 19/u);
  await settleOnboarding();dom.window.close();
});

test("onboarding Calculator card routing is generic rather than feature-name based",async()=>{const runtime=await readFile("src/runtime.ts","utf8");assert.doesNotMatch(runtime,/function destinationControl[^\n]*blood_tax/u);assert.doesNotMatch(runtime,/function openCalculator[^\n]*blood_tax/u);});

test("Name, result, onboarding, and legacy feature links converge on canonical Calculator routes",async()=>{
  const result=await executeBuild("prototype"),html=await readFile(result.htmlPath,"utf8");
  const legacy=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html#category=cryokinesis&topic=cryokinesis_glacial_spike_topic",beforeParse(window:any){installOnboardingBrowserShims(window);}});
  assert.equal(legacy.window.document.querySelector<HTMLElement>("main.layout")?.dataset.view,"calculator");assert.equal(legacy.window.document.querySelector("#calculator-feature-results > h3")?.textContent,"Glacial Spike");assert.equal(legacy.window.location.hash,"#calculator&card=glacial_spike&level=20&modifier=5&group=cryokinesis");
  const reference=new JSDOM(html,{runScripts:"dangerously",url:"https://local.invalid/KineticVanguard.prototype.html"+defaultReferenceFragment,beforeParse(window:any){installOnboardingBrowserShims(window);}}),document=reference.window.document,name=document.querySelector<HTMLSelectElement>("#name-select")!;
  name.value="advanced_beguile";name.dispatchEvent(new reference.window.Event("change",{bubbles:true}));assert.equal(document.querySelector<HTMLElement>("main.layout")?.dataset.view,"calculator");assert.equal(document.querySelector("#calculator-feature-results > h3")?.textContent,"Beguile");assert.match(reference.window.location.hash,/^#calculator&card=advanced_beguile&/u);
  (document.querySelector("#view-rules-reference") as HTMLButtonElement).click();name.value="common_overload";name.dispatchEvent(new reference.window.Event("change",{bubbles:true}));assert.equal(document.querySelector<HTMLElement>("main.layout")?.dataset.view,"reference");assert.ok(document.querySelector("#entity-common_overload"));
  await settleOnboarding();legacy.window.close();reference.window.close();
});

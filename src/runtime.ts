/* Serialized into the publication. It deliberately has no imports or network behavior. */
export function clientRuntime(model: any): void {
  "use strict";
  const get = (id: string) => document.getElementById(id)!;
  const ui = new Map(model.ui.tokens.map((token: any) => [token.id, token.text ?? token.template]));
  const areaValues = model.authority.vocabularies.rules_areas;
  const areas: Map<string,any> = new Map(areaValues.map((value: any) => [value.id, value]));
  const entities: Map<string,any> = new Map(model.authority.entities.map((entity: any) => [entity.id, entity]));
  const categories: Map<string,any> = new Map(model.authority.navigation.categories.map((category: any) => [category.id, category]));
  const indexed = model.filterIndex.entities;
  const indexedById:Map<string,any>=new Map(indexed.map((item:any)=>[item.id,item]));
  const state: any = { view: "home", category: model.authority.navigation.default_category_id, topic: "", classifications: {}, entity: null, resultRoute: null, focusOrigin: "fragment" };
  const homeFragment=String(model.policy.home_fragment);
  const category = () => categories.get(state.category) as any;
  const categoryTopics = (categoryId=state.category) => [...(categories.get(categoryId)?.topics ?? [])].sort((a:any,b:any)=>a.order-b.order);
  const defaultTopic = (categoryId=state.category) => categories.get(categoryId)?.default_topic_id??categoryTopics(categoryId)[0]?.id??"";
  const topic = () => categoryTopics().find((item: any) => item.id === state.topic);
  function normalizeNavigation(requestedCategory:any=state.category,requestedTopic:any=state.topic):boolean {
    const nextCategory=typeof requestedCategory==="string"&&categories.has(requestedCategory)?requestedCategory:model.authority.navigation.default_category_id;
    const options=categoryTopics(nextCategory);const requestedIsValid=typeof requestedTopic==="string"&&options.some((item:any)=>item.id===requestedTopic);
    const nextTopic=requestedIsValid?requestedTopic:defaultTopic(nextCategory);let corrected=nextCategory!==requestedCategory||nextTopic!==requestedTopic;
    state.category=nextCategory;state.topic=nextTopic;
    if(state.entity){if(!topic()?.entity_ids.includes(state.entity)){state.entity=null;state.resultRoute=null;corrected=true;}else if(corrected)state.resultRoute=state.topic;}
    return corrected;
  }
  const match = (item: any, selections = state.classifications) => Object.entries(selections).every(([facet, raw]: any) => {
    const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
    return values.length === 0 || values.some((value: string) => item.classifications[facet]?.includes(value));
  });
  const matches = () => indexed.filter((item: any) => match(item));
  const hasSelections = () => Object.values(state.classifications).some((value: any) => Array.isArray(value) ? value.length : Boolean(value));
  const isMobile = () => typeof matchMedia === "function" && matchMedia("(max-width: 760px)").matches;
  const safeState = () => ({ view: state.view, category: state.category, topic: state.topic, classifications: structuredClone(state.classifications), entity: state.entity, resultRoute: state.resultRoute, focusOrigin: state.focusOrigin });
  const referenceFragment = (categoryId=state.category,topicId=state.topic,classifications:any=state.classifications,entityId:string|null=state.entity) => {
    const parameters = new URLSearchParams(); parameters.set("category", categoryId); parameters.set("topic", topicId);
    const filters = Object.entries(classifications).filter(([,value]: any) => Array.isArray(value) ? value.length : value).map(([facet,value]: any) => `${facet}:${(Array.isArray(value)?value:[value]).join(",")}`).join(";");
    if (filters) parameters.set("filters", filters); if (entityId) parameters.set("entity", entityId);
    return `#${parameters.toString()}`;
  };
  const fragment = () => state.view==="home"?`#${homeFragment}`:referenceFragment();
  const writeHistory = (mode: "push"|"replace") => history[mode === "push" ? "pushState" : "replaceState"](safeState(), "", fragment());
  const ordinaryActivation = (event:MouseEvent) => !event.defaultPrevented&&event.button===0&&!event.metaKey&&!event.ctrlKey&&!event.shiftKey&&!event.altKey;
  function syncNameSelection(): void { const select=get("name-select") as HTMLSelectElement;select.value=state.entity&&indexedById.has(state.entity)?state.entity:""; }
  function announce(message: string): void {
    const region=get("filter-live"); get("filter-root").setAttribute("data-filter-settled","false"); region.textContent="";
    queueMicrotask(()=>{region.textContent=message;get("filter-root").setAttribute("data-filter-settled","true");});
  }
  function renderNavigation(): void {
    const categorySelect=get("category-select") as HTMLSelectElement; categorySelect.textContent="";
    for(const item of [...categories.values()].sort((a:any,b:any)=>a.order-b.order)){const option=document.createElement("option");option.value=item.id;option.textContent=item.label;categorySelect.append(option);}
    categorySelect.value=state.category;
    const topicSelect=get("topic-select") as HTMLSelectElement;topicSelect.textContent="";
    for(const item of categoryTopics()){const option=document.createElement("option");option.value=item.id;option.textContent=item.title;topicSelect.append(option);}
    topicSelect.value=state.topic;
  }
  const appendInline = (parent: HTMLElement, node: any) => {
    const element=node.type==="strong"?document.createElement("strong"):node.type==="emphasis"?document.createElement("em"):node.type==="code"?document.createElement("code"):document.createElement("span");
    element.textContent=node.text??node.label??String(node.value?.value??"");parent.append(element);
  };
  const inlineText = (nodes:any[]) => nodes.map(node=>node.text??node.label??String(node.value?.value??"")).join("");
  const inlineSlice = (nodes:any[],start:number,end:number) => {const result:any[]=[];let offset=0;for(const node of nodes){const value=node.text??node.label??String(node.value?.value??"");const from=Math.max(start-offset,0),to=Math.min(end-offset,value.length);if(from<to)result.push({...node,text:value.slice(from,to),label:undefined,value:undefined});offset+=value.length;}return result;};
  const trimInlineRange = (text:string,start:number,end:number) => {while(start<end&&/\s/.test(text[start]!))start++;while(end>start&&/\s/.test(text[end-1]!))end--;return [start,end] as const;};
  const appendParagraph = (parent:HTMLElement,nodes:any[]) => {const paragraph=document.createElement("p");nodes.forEach((node:any)=>appendInline(paragraph,node));parent.append(paragraph);};
  const appendFeatureTier = (parent:HTMLElement,labelText:string,body:(content:HTMLElement)=>void,tier?:number) => {const tierElement=document.createElement("section");tierElement.className="feature-tier";if(tier!==undefined)tierElement.dataset.tier=String(tier);const label=document.createElement("h3");label.className="feature-tier__label";label.textContent=labelText;const content=document.createElement("div");content.className="feature-tier__content";body(content);tierElement.append(label,content);parent.append(tierElement);};
  function renderTierParagraph(parent:HTMLElement,block:any):boolean {const text=inlineText(block.inlines);const matches=[...text.matchAll(/(^|\s)(T(\d+) (?:Base|Overload)):\s*/g)];if(!matches.length)return false;const first=matches[0]!,prefixEnd=first.index??0;const [prefixStart,prefixTrimmedEnd]=trimInlineRange(text,0,prefixEnd);if(prefixStart<prefixTrimmedEnd)appendParagraph(parent,inlineSlice(block.inlines,prefixStart,prefixTrimmedEnd));matches.forEach((match,index)=>{const next=matches[index+1];const start=(match.index??0)+match[0].length,end=next?.index??text.length;const [trimmedStart,trimmedEnd]=trimInlineRange(text,start,end);appendFeatureTier(parent,match[2]!,content=>appendParagraph(content,inlineSlice(block.inlines,trimmedStart,trimmedEnd)),Number(match[3]));});return true;}
  const referenceCountMessage=(visible:number,total:number):string=>String(ui.get("reference_showing_count")).replace("{visible_count}",String(visible)).replace("{total_count}",String(total));
  function updateReferenceFilter(rows:HTMLTableRowElement[],show:HTMLSelectElement,level:HTMLSelectElement,count:HTMLElement,noMatches:HTMLElement,live:HTMLElement,root:HTMLElement,shouldAnnounce:boolean):void {let visible=0;for(const row of rows){const matches=(!show.value||row.dataset.referenceGroup===show.value)&&(!level.value||row.dataset.referenceLevel===level.value);row.classList.toggle("reference-row--filtered",!matches);if(matches)visible++;}const countMessage=referenceCountMessage(visible,rows.length),message=visible?countMessage:`${String(ui.get("reference_no_matches"))} ${countMessage}`;count.textContent=countMessage;noMatches.hidden=visible!==0;if(!shouldAnnounce)return;root.dataset.referenceFilterSettled="false";live.textContent="";queueMicrotask(()=>{live.textContent=message;root.dataset.referenceFilterSettled="true";});}
  function appendReferenceFilters(parent:HTMLElement,table:HTMLTableElement,rows:HTMLTableRowElement[]):void {
    const showOptions=[["","reference_show_all"],["common_features","reference_show_common"],["pyrokinesis","reference_show_pyrokinesis"],["cryokinesis","reference_show_cryokinesis"],["psychokinesis","reference_show_psychokinesis"],["electrokinesis","reference_show_electrokinesis"],["advanced_training","reference_show_advanced_training"]] as const;
    const levelValues=["","3rd","5th","7th","10th","15th","18th","20th","15th+","18th+"] as const;
    const makeField=(id:string,labelText:string)=>{const label=document.createElement("label");label.className="field reference-filter__field";label.htmlFor=id;label.append(document.createTextNode(labelText));const select=document.createElement("select");select.id=id;select.setAttribute("aria-controls",table.id);label.append(select);return{label,select};};
    const show=makeField("reference-show",String(ui.get("reference_show_label"))),level=makeField("reference-level",String(ui.get("reference_level_label")));for(const [value,tokenId] of showOptions){const option=document.createElement("option");option.value=value;option.textContent=String(ui.get(tokenId));show.select.append(option);}for(const value of levelValues){const option=document.createElement("option");option.value=value;option.textContent=value||String(ui.get("reference_level_all"));level.select.append(option);}
    const root=document.createElement("div");root.className="reference-filters";root.dataset.referenceFilterSettled="true";
    const feedback=document.createElement("div");feedback.className="reference-filter__feedback";const count=document.createElement("p");count.id="reference-filter-count";count.className="reference-filter__count";const noMatches=document.createElement("p");noMatches.id="reference-filter-no-matches";noMatches.className="reference-filter__empty";noMatches.textContent=String(ui.get("reference_no_matches"));noMatches.hidden=true;const live=document.createElement("div");live.id="reference-filter-live";live.className="sr-only";live.setAttribute("role","status");live.setAttribute("aria-live","polite");live.setAttribute("aria-atomic","true");feedback.append(count,noMatches,live);
    root.append(show.label,level.label,feedback);table.setAttribute("aria-describedby",count.id);parent.append(root);
    const update=(announce:boolean)=>updateReferenceFilter(rows,show.select,level.select,count,noMatches,live,root,announce);show.select.addEventListener("change",()=>update(true));level.select.addEventListener("change",()=>update(true));update(false);
  }
  function renderBlock(parent: HTMLElement, block: any): void {
    if(block.type==="example_play_section"){const section=document.createElement("section");section.className=`example-play-section example-play-section--${block.discipline}`;section.dataset.discipline=block.discipline;const heading=document.createElement("h3");heading.className="example-play-section__heading";heading.id=`example-play-${block.discipline}-${inlineText(block.title).toLowerCase().replaceAll(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")}`;block.heading.forEach((node:any)=>appendInline(heading,node));section.setAttribute("aria-labelledby",heading.id);const content=document.createElement("div");content.className="example-play-section__content";const title=document.createElement("h4");title.className="example-play-section__title";block.title.forEach((node:any)=>appendInline(title,node));const body=document.createElement("div");body.className="example-play-section__body";for(const [field,label] of [["setup","Setup"],["activation","Activation"],["rolls_or_saves","Rolls or Saves"],["damage","Damage"],["effects","Effects"],["result","Result"]] as const){const phase=document.createElement("section");phase.className=`example-play-section__phase example-play-section__phase--${field.replaceAll("_","-")}`;const phaseTitle=document.createElement("h5");phaseTitle.className="example-play-section__phase-title";phaseTitle.textContent=label;phase.append(phaseTitle);appendParagraph(phase,block[field]);body.append(phase);}content.append(title,body);section.append(heading,content);parent.append(section);return;}
    if(block.type==="example"){const aside=document.createElement("aside");aside.className="inline-example";aside.dataset.overloadTier=String(block.tier);const title=document.createElement("h3");title.className="inline-example__title";block.title.forEach((node:any)=>appendInline(title,node));const body=document.createElement("div");body.className="inline-example__body";block.body.forEach((child:any)=>renderBlock(body,child));aside.append(title,body);parent.append(aside);return;}
    if(block.type==="tier"){appendFeatureTier(parent,`T${block.tier} Overload`,content=>block.body.forEach((child:any)=>renderBlock(content,child)),block.tier);return;}
    if(block.type==="paragraph"||block.type==="note"){if(block.type==="paragraph"&&renderTierParagraph(parent,block))return;const element=document.createElement(block.type==="note"?"aside":"p");if(block.type==="note")element.className=`note ${block.kind}`;block.inlines.forEach((node:any)=>appendInline(element,node));parent.append(element);return;}
    if(block.type==="list"){const list=document.createElement(block.style==="ordered"?"ol":"ul");for(const item of block.items){const li=document.createElement("li");item.forEach((node:any)=>appendInline(li,node));list.append(li);}parent.append(list);return;}
    if(block.type==="table"){const wrapper=document.createElement("div");wrapper.className="table-scroll";wrapper.tabIndex=0;const table=document.createElement("table");if(block.row_references||block.headers.some((cell:any)=>inlineText(cell)==="Ongoing Duration"))table.className="quick-reference-table";const thead=document.createElement("thead");const headerRow=document.createElement("tr");
      for(const cell of block.headers){const th=document.createElement("th");th.scope="col";cell.forEach((node:any)=>appendInline(th,node));headerRow.append(th);}thead.append(headerRow);table.append(thead);const tbody=document.createElement("tbody");
      for(const [rowIndex,row] of block.rows.entries()){const tr=document.createElement("tr"),reference=block.row_references?.[rowIndex];if(reference){const referencedEntity="entity_id" in reference?entities.get(reference.entity_id):undefined,group=referencedEntity?.presentation_metadata.primary_rules_area??reference.reference_group;tr.dataset.referenceGroup=group;tr.dataset.referenceLevel=reference.reference_level;if(referencedEntity)tr.dataset.referenceEntity=referencedEntity.id;}for(const cell of row){const td=document.createElement("td");cell.forEach((node:any)=>appendInline(td,node));tr.append(td);}tbody.append(tr);}table.append(tbody);wrapper.append(table);if(block.row_references){table.id="psi-cost-reference-table";appendReferenceFilters(parent,table,[...tbody.rows]);}parent.append(wrapper);}
  }
  const activationDisplay = (entity:any):string => {
    if(entity.id==="common_manifested_strike")return "Attack action · Replaces an attack";
    if(entity.id==="common_empathic_sense")return "Passive · Bonus Action scan";
    if(entity.classifications.feature_role==="rider")return "Declared before roll · Resolves on hit";
    return ({action:"Action",bonus_action:"Bonus Action",reaction:"Reaction",passive:"Passive"} as Record<string,string>)[entity.activation]??"Special";
  };
  function renderTopic(focusEntity?: string,focusMode:"none"|"result"|"mobile"="none"): void {
    normalizeNavigation();const main=get("rules-content");main.textContent="";const current=topic();if(!current)return;
    for(const entityId of current.entity_ids){const entity=entities.get(entityId) as any;const article=document.createElement("article");article.id="entity-"+entity.id;const heading=document.createElement("h2");heading.textContent=entity.title;heading.tabIndex=-1;heading.dataset.sourcePath="entities."+entity.id+".title";article.append(heading);
      const activation=entity.activation===undefined?undefined:activationDisplay(entity);
      if(entity.level!==undefined||entity.psi_cost!==undefined||activation!==undefined||entity.requires_concentration===true){const dl=document.createElement("dl");dl.className="facts feature-metadata";for(const [tokenId,value] of [["fact_level",entity.level],["fact_psi",entity.psi_cost],["fact_activation",activation],["fact_duration",entity.concentration_duration]])if(value!==undefined){const item=document.createElement("div");item.className="feature-metadata__item";const dt=document.createElement("dt");dt.textContent=String(ui.get(tokenId));const dd=document.createElement("dd");dd.textContent=String(value);item.append(dt,dd);dl.append(item);}if(entity.requires_concentration===true){const item=document.createElement("div");item.className="feature-metadata__item feature-metadata__item--concentration";const dt=document.createElement("dt");dt.className="sr-only";dt.textContent=String(ui.get("fact_requirement"));const dd=document.createElement("dd");dd.textContent=String(ui.get("fact_concentration"));item.append(dt,dd);dl.append(item);}article.append(dl);}
      if(entity.content.every((block:any)=>block.type==="example_play_section")){const sections=document.createElement("div");sections.className="example-play-flow";entity.content.forEach((block:any)=>renderBlock(sections,block));article.append(sections);}else entity.content.forEach((block:any)=>renderBlock(article,block));main.append(article);}
    const heading=(focusEntity?document.querySelector("#entity-"+CSS.escape(focusEntity)+" h2"):main.querySelector("article h2")) as HTMLElement|null;const mobile=isMobile();
    if(heading&&(focusMode==="result"||(focusMode==="mobile"&&mobile))){if(mobile){heading.focus({preventScroll:true});heading.scrollIntoView({block:"start"});}else heading.focus();}
  }
  const canonicalText=(element:HTMLElement,text:string,path:string)=>{element.textContent=text;element.dataset.sourcePath=path;return element;};
  const appendCanonicalParagraph=(parent:HTMLElement,text:string,path:string,className?:string)=>{const paragraph=canonicalText(document.createElement("p"),text,path);if(className)paragraph.className=className;parent.append(paragraph);return paragraph;};
  const focusHeading=(heading:HTMLElement|null)=>{if(!heading)return;heading.focus({preventScroll:true});if(typeof heading.scrollIntoView==="function")heading.scrollIntoView({block:"start"});};
  function syncViewChrome():void {const home=state.view==="home",main=document.querySelector<HTMLElement>("main.layout")!,controls=document.querySelector<HTMLElement>("aside.controls")!,content=get("rules-content"),startLink=get("view-start-here"),referenceLink=get("view-rules-reference");controls.hidden=home;main.dataset.view=state.view;main.classList.toggle("layout--home",home);main.classList.toggle("layout--reference",!home);content.classList.toggle("home",home);content.classList.toggle("rules",!home);startLink.setAttribute("href",`#${homeFragment}`);referenceLink.setAttribute("href",referenceFragment());for(const [link,active] of [[startLink,home],[referenceLink,!home]] as const)if(active)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current");}
  function categoryHref(categoryId:string):string {const target=categories.get(categoryId);return target?referenceFragment(target.id,target.default_topic_id,{},null):referenceFragment(model.authority.navigation.default_category_id,defaultTopic(model.authority.navigation.default_category_id),{},null);}
  function entityHref(entityId:string):string {const item=indexedById.get(entityId);if(!item)return categoryHref(model.authority.navigation.default_category_id);const area=item.primary_rules_area;return referenceFragment(area,item.routes[area],{},entityId);}
  function focusOnboardingSection(sectionId:string):void {const section=document.getElementById(sectionId),heading=section?.querySelector<HTMLElement>(":scope > h3")??null;focusHeading(heading);}
  function destinationControl(link:any,path:string):HTMLButtonElement|HTMLAnchorElement {const destination=link.destination;let control:HTMLButtonElement|HTMLAnchorElement;if(destination.kind==="onboarding_section"){const button=document.createElement("button");button.type="button";button.addEventListener("click",()=>focusOnboardingSection(destination.section_id));control=button;}else{const anchor=document.createElement("a");anchor.href=destination.kind==="category"?categoryHref(destination.category_id):entityHref(destination.entity_id);anchor.addEventListener("click",event=>{if(!ordinaryActivation(event))return;event.preventDefault();if(destination.kind==="category")openCategory(destination.category_id);else openEntity(destination.entity_id,"onboarding");});control=anchor;}canonicalText(control,link.title,path+".title");control.dataset.onboardingLinkId=link.id;control.dataset.destinationKind=destination.kind;return control;}
  function appendDestinationList(parent:HTMLElement,links:any[],path:string):void {const list=document.createElement("ul");list.className="home-links";links.forEach((link,index)=>{const item=document.createElement("li");item.append(destinationControl(link,`${path}.${index}`));list.append(item);});parent.append(list);}
  function homeSection(section:any,path:string):HTMLElement {const element=document.createElement("section");element.id=section.id;element.className="home-section";element.dataset.onboardingId=section.id;const heading=canonicalText(document.createElement("h3"),section.title,path+".title");heading.id=section.id+"_heading";heading.tabIndex=-1;element.append(heading);return element;}
  function renderHome(focusPage=false):void {
    const onboarding=model.authority.onboarding;syncViewChrome();const root=get("rules-content");root.textContent="";
    const guide=document.createElement("div");guide.className="home-guide";guide.dataset.onboardingId=onboarding.id;
    const heading=canonicalText(document.createElement("h2"),onboarding.title,"onboarding.title");heading.id=onboarding.id+"_heading";heading.tabIndex=-1;
    const introduction=document.createElement("div");introduction.className="home-introduction";
    appendCanonicalParagraph(introduction,onboarding.introduction.summary,"onboarding.introduction.summary");
    appendCanonicalParagraph(introduction,onboarding.introduction.no_psi_note,"onboarding.introduction.no_psi_note","home-key-point");
    appendCanonicalParagraph(introduction,onboarding.introduction.orientation,"onboarding.introduction.orientation");guide.append(heading,introduction);
    const primary=document.createElement("ul");primary.className="home-primary-paths";
    onboarding.primary_paths.forEach((link:any,index:number)=>{const item=document.createElement("li");item.className="home-card";item.append(destinationControl(link,`onboarding.primary_paths.${index}`));if(link.description)appendCanonicalParagraph(item,link.description,`onboarding.primary_paths.${index}.description`,"home-card__description");primary.append(item);});guide.append(primary);
    const disciplines=homeSection(onboarding.disciplines,"onboarding.disciplines"),disciplineCards=document.createElement("ul");disciplineCards.className="home-card-list";
    onboarding.disciplines.cards.forEach((link:any,index:number)=>{const card=document.createElement("li");card.className="home-card";const title=document.createElement("h4");title.className="home-card__title";title.append(destinationControl(link,`onboarding.disciplines.cards.${index}`));card.append(title);if(link.description)appendCanonicalParagraph(card,link.description,`onboarding.disciplines.cards.${index}.description`,"home-card__description");disciplineCards.append(card);});disciplines.append(disciplineCards);guide.append(disciplines);
    const basic=homeSection(onboarding.basic_turn,"onboarding.basic_turn"),steps=document.createElement("ol");
    onboarding.basic_turn.steps.forEach((text:string,index:number)=>{const item=canonicalText(document.createElement("li"),text,`onboarding.basic_turn.steps.${index}`);steps.append(item);});basic.append(steps);
    const reminders=document.createElement("ul");onboarding.basic_turn.reminders.forEach((text:string,index:number)=>{const item=canonicalText(document.createElement("li"),text,`onboarding.basic_turn.reminders.${index}`);reminders.append(item);});basic.append(reminders);
    appendDestinationList(basic,onboarding.basic_turn.destinations,"onboarding.basic_turn.destinations");guide.append(basic);
    const build=homeSection(onboarding.build_checklist,"onboarding.build_checklist"),checklist=document.createElement("ol");checklist.className="home-checklist";
    onboarding.build_checklist.items.forEach((link:any,index:number)=>{const item=document.createElement("li");item.append(destinationControl(link,`onboarding.build_checklist.items.${index}`));checklist.append(item);});build.append(checklist);guide.append(build);
    const glossary=homeSection(onboarding.glossary,"onboarding.glossary"),definitions=document.createElement("dl");definitions.className="home-glossary";
    onboarding.glossary.entries.forEach((entry:any,index:number)=>{const term=document.createElement("dt");term.append(destinationControl(entry,`onboarding.glossary.entries.${index}`));const definition=canonicalText(document.createElement("dd"),entry.definition,`onboarding.glossary.entries.${index}.definition`);definitions.append(term,definition);});glossary.append(definitions);guide.append(glossary);
    const next=homeSection(onboarding.next_destinations,"onboarding.next_destinations");appendDestinationList(next,onboarding.next_destinations.items,"onboarding.next_destinations.items");guide.append(next);
    root.append(guide);if(focusPage)focusHeading(heading);
  }
  function renderNameOptions(): void {
    const select=get("name-select") as HTMLSelectElement;select.textContent="";const placeholder=document.createElement("option");placeholder.value="";placeholder.textContent=String(ui.get("name_placeholder"));select.append(placeholder);
    for(const area of model.filterIndex.name_groups){const names=area.entity_ids.map((id:string)=>indexedById.get(id)).filter((item:any)=>item&&match(item));if(!names.length)continue;const group=document.createElement("optgroup");group.label=area.label;for(const item of names){const option=document.createElement("option");option.value=item.id;option.textContent=item.title;group.append(option);}select.append(group);}
    syncNameSelection();
  }
  function readFacetControls(): void {
    for(const facet of model.authority.facets){if(facet.cardinality==="multi")state.classifications[facet.id]=[...document.querySelectorAll(`[data-facet="${facet.id}"]:checked`)].map((node:any)=>node.value);else state.classifications[facet.id]=(get(`facet-${facet.id}`) as HTMLSelectElement).value||"";}
  }
  function renderFacets(): void {
    const root=get("facet-controls");root.textContent="";
    for(const facet of [...model.authority.facets].sort((a:any,b:any)=>a.order-b.order)){const values=model.authority.vocabularies[facet.vocabulary];
      if(facet.cardinality==="multi"){const fieldset=document.createElement("fieldset");const legend=document.createElement("legend");legend.textContent=facet.label;fieldset.append(legend);for(const value of values){const label=document.createElement("label");const input=document.createElement("input");input.type="checkbox";input.value=value.id;input.dataset.facet=facet.id;input.checked=(state.classifications[facet.id]??[]).includes(value.id);label.append(input,document.createTextNode(` ${value.label}`));fieldset.append(label);}root.append(fieldset);}
      else{const label=document.createElement("label");label.className="field";label.htmlFor=`facet-${facet.id}`;label.append(document.createTextNode(facet.label));const select=document.createElement("select");select.id=`facet-${facet.id}`;select.dataset.facet=facet.id;const any=document.createElement("option");any.value="";any.textContent=String(ui.get("any_value"));select.append(any);for(const value of values){const option=document.createElement("option");option.value=value.id;option.textContent=value.label;select.append(option);}select.value=state.classifications[facet.id]??"";label.append(select);root.append(label);}}
  }
  function updateAvailability(): void {
    for(const facet of model.authority.facets){
      if(facet.cardinality==="multi"){const controls=[...document.querySelectorAll(`input[data-facet="${facet.id}"]`)] as HTMLInputElement[];for(const control of controls){const candidate=structuredClone(state.classifications);const active=new Set(candidate[facet.id]??[]);active.add(control.value);candidate[facet.id]=[...active];control.disabled=!control.checked&&!indexed.some((item:any)=>match(item,candidate));}}
      else{const select=get(`facet-${facet.id}`) as HTMLSelectElement;for(const option of [...select.options]){if(!option.value)continue;const candidate=structuredClone(state.classifications);candidate[facet.id]=option.value;option.disabled=option.selected?false:!indexed.some((item:any)=>match(item,candidate));}}
    }
  }
  function renderResults(shouldAnnounce=false): void {
    const root=get("filter-results");root.textContent="";const result=matches();
    if(!result.length){const p=document.createElement("p");p.textContent=String(ui.get("no_matches"));root.append(p);}else{const list=document.createElement("ul");for(const item of result){const li=document.createElement("li");const button=document.createElement("button");const area=areas.get(item.primary_rules_area) as any;const label=String(ui.get("result_identity")).replace("{entity_title}",item.title).replace("{primary_rules_area_label}",area.label);button.textContent=label;button.setAttribute("aria-label",label);button.addEventListener("click",()=>openEntity(item.id,"result"));li.append(button);list.append(li);}if(hasSelections())root.append(list);else{const details=document.createElement("details");details.className="results__all";const summary=document.createElement("summary");summary.textContent=String(ui.get("match_count")).replace("{count}",String(result.length));details.append(summary,list);root.append(details);}}updateAvailability();
    if(shouldAnnounce)announce(result.length===1?String(ui.get("one_match")).replace("{count}",String(result.length)):result.length?String(ui.get("match_count")).replace("{count}",String(result.length)):String(ui.get("no_matches")));
  }
  function resultArea(item:any):string{return item.primary_rules_area;}
  function renderReference(focusEntity?:string,focusMode:"none"|"result"|"mobile"="none"):void {syncViewChrome();renderNavigation();renderNameOptions();renderFacets();renderResults(false);renderTopic(focusEntity,focusMode);}
  function renderView(focusMode:"none"|"home"|"reference"="none"):void {if(state.view==="home")renderHome(focusMode==="home");else renderReference(state.entity??undefined,focusMode==="reference"?"result":"none");}
  function openCategory(id:string):void {const target=categories.get(id);if(!target)return;const route=target.default_topic_id;if(state.view==="reference"&&state.category===id&&state.topic===route&&state.entity===null&&!hasSelections())return;state.view="reference";state.category=id;state.topic=route;state.classifications={};state.entity=null;state.resultRoute=null;state.focusOrigin="onboarding";writeHistory("push");renderReference(undefined,"result");}
  function openEntity(id:string,origin:"name"|"result"|"onboarding"):void {
    const item=indexedById.get(id);if(!item)return;const area=origin==="name"?item.primary_rules_area:resultArea(item);const route=item.routes[area];if(state.view==="reference"&&state.entity===id&&state.category===area&&state.topic===route){syncNameSelection();return;}state.view="reference";state.category=area;state.topic=route;state.classifications={};state.entity=id;state.resultRoute=route;state.focusOrigin=origin;writeHistory("push");renderReference(id,origin==="name"?"mobile":"result");if(origin==="name")announce(String(ui.get("filter_cleared")));
  }
  function openHome():void {if(state.view==="home")return;state.view="home";state.focusOrigin="view";writeHistory("push");renderHome(true);}
  function openReference():void {if(state.view==="reference")return;state.view="reference";state.focusOrigin="view";writeHistory("push");renderReference(state.entity??undefined,"result");}
  function parseFragment():boolean {
    let corrected=false;const raw=location.hash.slice(1);state.focusOrigin="fragment";state.classifications={};state.entity=null;state.resultRoute=null;
    if(raw===""||raw===homeFragment){state.view="home";normalizeNavigation(model.authority.navigation.default_category_id,defaultTopic(model.authority.navigation.default_category_id));return false;}
    state.view="reference";const parameters=new URLSearchParams(raw),requestedCategory=parameters.get("category"),requestedTopic=parameters.get("topic");if(normalizeNavigation(requestedCategory,requestedTopic))corrected=true;
    const filters=parameters.get("filters");if(filters)for(const pair of filters.split(";")){const [facetId,rawValue]=pair.split(":");if(!facetId||!rawValue){corrected=true;continue;}const facet=model.authority.facets.find((candidate:any)=>candidate.id===facetId);if(!facet){corrected=true;continue;}const allowed=new Set(model.authority.vocabularies[facet.vocabulary].map((value:any)=>value.id));const values=[...new Set<string>(rawValue.split(",").filter((value:string)=>allowed.has(value)))];if(!values.length){corrected=true;continue;}state.classifications[facetId]=facet.cardinality==="multi"?values.slice(0,allowed.size):values[0];}
    const entityId=parameters.get("entity");if(entityId&&entities.has(entityId)){state.entity=entityId;const currentTopic=topic();if(!currentTopic.entity_ids.includes(entityId)){const item=indexedById.get(entityId);state.category=item.primary_rules_area;state.topic=item.routes[item.primary_rules_area];state.classifications={};corrected=true;}state.resultRoute=state.topic;}else if(entityId)corrected=true;return corrected;
  }
  function classificationsAreValid(value:any):boolean {
    if(!value||typeof value!=="object"||Array.isArray(value))return false;
    return Object.entries(value).every(([id,selection]:any)=>{
      const facet=model.authority.facets.find((candidate:any)=>candidate.id===id);
      if(!facet)return false;
      const allowed=new Set<string>(model.authority.vocabularies[facet.vocabulary].map((item:any)=>item.id));
      if(facet.cardinality==="multi")return Array.isArray(selection)&&selection.length===new Set(selection).size&&selection.every((item:any)=>typeof item==="string"&&allowed.has(item));
      return typeof selection==="string"&&(selection===""||allowed.has(selection));
    });
  }
  function restore(snapshot:any):void {
    const fields=new Set(model.policy.history_state_fields),keys=Object.keys(snapshot??{}),validFields=keys.length===fields.size&&keys.every(key=>fields.has(key)),validView=model.policy.application_views.includes(snapshot?.view),validFilters=classificationsAreValid(snapshot?.classifications),validFocus=model.policy.focus_origins.includes(snapshot?.focusOrigin),validEntity=snapshot?.entity===null||entities.has(snapshot?.entity),validResultRoute=snapshot?.entity===null?snapshot?.resultRoute===null:typeof snapshot?.resultRoute==="string"&&snapshot.resultRoute===snapshot.topic;
    if(!snapshot||!validFields||!validView||!validFilters||!validFocus||!validEntity||!validResultRoute){initialize();return;}Object.assign(state,snapshot);const corrected=normalizeNavigation();renderView();if(corrected)writeHistory("replace");
  }
  function initialize():void {const corrected=parseFragment();renderView();writeHistory("replace");if(corrected&&state.view==="reference")announce(String(ui.get("filter_instruction")));}
  get("category-select").addEventListener("change",event=>{normalizeNavigation((event.target as HTMLSelectElement).value,"");state.entity=null;state.resultRoute=null;state.focusOrigin="category";syncNameSelection();renderNavigation();renderTopic(undefined,"mobile");writeHistory("push");syncViewChrome();announce(category().label);});
  get("topic-select").addEventListener("change",event=>{normalizeNavigation(state.category,(event.target as HTMLSelectElement).value);state.entity=null;state.resultRoute=null;state.focusOrigin="topic";syncNameSelection();renderTopic(undefined,"mobile");writeHistory("push");syncViewChrome();announce(topic()?.title??category().label);});
  get("name-select").addEventListener("change",event=>openEntity((event.target as HTMLSelectElement).value,"name"));
  get("facet-controls").addEventListener("change",()=>{readFacetControls();state.entity=null;state.resultRoute=null;state.focusOrigin="result";renderNameOptions();writeHistory("push");syncViewChrome();renderResults(true);});
  document.querySelector<HTMLAnchorElement>(".skip")!.addEventListener("click",event=>{if(!ordinaryActivation(event))return;event.preventDefault();const content=get("rules-content");content.focus({preventScroll:true});content.scrollIntoView({block:"start"});});
  get("view-start-here").addEventListener("click",event=>{if(!ordinaryActivation(event))return;event.preventDefault();openHome();});
  get("view-rules-reference").addEventListener("click",event=>{if(!ordinaryActivation(event))return;event.preventDefault();openReference();});
  addEventListener("popstate",event=>restore(event.state));initialize();
}

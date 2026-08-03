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
  const state: any = { category: model.authority.navigation.default_category_id, topic: "", classifications: {}, entity: null, resultRoute: null, focusOrigin: "fragment" };
  const category = () => categories.get(state.category) as any;
  const categoryTopics = (categoryId=state.category) => [...(categories.get(categoryId)?.topics ?? [])].sort((a:any,b:any)=>a.order-b.order);
  const topic = () => categoryTopics().find((item: any) => item.id === state.topic);
  function normalizeNavigation(requestedCategory:any=state.category,requestedTopic:any=state.topic):boolean {
    const nextCategory=typeof requestedCategory==="string"&&categories.has(requestedCategory)?requestedCategory:model.authority.navigation.default_category_id;
    const options=categoryTopics(nextCategory);const requestedIsValid=typeof requestedTopic==="string"&&options.some((item:any)=>item.id===requestedTopic);
    const nextTopic=requestedIsValid?requestedTopic:(options[0]?.id??"");const corrected=nextCategory!==requestedCategory||nextTopic!==requestedTopic;
    state.category=nextCategory;state.topic=nextTopic;
    if(state.entity&&!topic()?.entity_ids.includes(state.entity)){state.entity=null;state.resultRoute=null;}
    return corrected;
  }
  const selectedName = () => (get("name-select") as HTMLSelectElement).value;
  const match = (item: any, selections = state.classifications) => Object.entries(selections).every(([facet, raw]: any) => {
    const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
    return values.length === 0 || values.some((value: string) => item.classifications[facet]?.includes(value));
  });
  const matches = () => indexed.filter((item: any) => match(item));
  const hasSelections = () => Object.values(state.classifications).some((value: any) => Array.isArray(value) ? value.length : Boolean(value));
  const safeState = () => ({ category: state.category, topic: state.topic, classifications: structuredClone(state.classifications), entity: state.entity, resultRoute: state.resultRoute, focusOrigin: state.focusOrigin });
  const fragment = () => {
    const parameters = new URLSearchParams(); parameters.set("category", state.category); parameters.set("topic", state.topic);
    const filters = Object.entries(state.classifications).filter(([,value]: any) => Array.isArray(value) ? value.length : value).map(([facet,value]: any) => `${facet}:${(Array.isArray(value)?value:[value]).join(",")}`).join(";");
    if (filters) parameters.set("filters", filters); if (state.entity) parameters.set("entity", state.entity);
    return `#${parameters.toString()}`;
  };
  const writeHistory = (mode: "push"|"replace") => history[mode === "push" ? "pushState" : "replaceState"](safeState(), "", fragment());
  function resetName(): void { (get("name-select") as HTMLSelectElement).value = ""; updateOpen(); }
  function updateOpen(): void {
    const button = get("name-open"); const entity = entities.get(selectedName()) as any;
    button.setAttribute("aria-disabled", entity ? "false" : "true");
    button.setAttribute("aria-label", entity ? String(ui.get("open_entity")).replace("{entity_title}", entity.title) : String(ui.get("open_inactive_name")));
  }
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
    element.textContent=node.text??node.label??String(node.value?.value??"");element.dataset.sourceUnit=node.source_unit_id;parent.append(element);
  };
  const inlineText = (nodes:any[]) => nodes.map(node=>node.text??node.label??String(node.value?.value??"")).join("");
  const inlineSlice = (nodes:any[],start:number,end:number) => {const result:any[]=[];let offset=0;for(const node of nodes){const value=node.text??node.label??String(node.value?.value??"");const from=Math.max(start-offset,0),to=Math.min(end-offset,value.length);if(from<to)result.push({...node,text:value.slice(from,to),label:undefined,value:undefined});offset+=value.length;}return result;};
  const trimInlineRange = (text:string,start:number,end:number) => {while(start<end&&/\s/.test(text[start]!))start++;while(end>start&&/\s/.test(text[end-1]!))end--;return [start,end] as const;};
  const appendParagraph = (parent:HTMLElement,nodes:any[]) => {const paragraph=document.createElement("p");nodes.forEach((node:any)=>appendInline(paragraph,node));parent.append(paragraph);};
  const examplePhases=[
    ["setup","example_setup_label"],
    ["activation","example_activation_label"],
    ["rolls_or_saves","example_rolls_or_saves_label"],
    ["damage","example_damage_label"],
    ["effects","example_effects_label"],
    ["result","example_result_label"]
  ] as const;
  function renderExampleTurns(parent:HTMLElement,entity:any):void {
    if(!entity.example_turns?.length)return;
    const section=document.createElement("section");section.className="example-turns";const heading=document.createElement("h3");heading.className="example-turns__heading";heading.id=`entity-${entity.id}-example-turns`;heading.textContent=String(ui.get("example_turns_heading"));section.setAttribute("aria-labelledby",heading.id);const list=document.createElement("div");list.className="example-turns__list";
    for(const turn of entity.example_turns){const aside=document.createElement("aside");aside.className="example-turn";const titleText=inlineText(turn.title);aside.setAttribute("aria-label",String(ui.get("example_accessible_name")).replace("{example_title}",titleText));const title=document.createElement("h4");title.className="example-turn__title";turn.title.forEach((node:any)=>appendInline(title,node));const phases=document.createElement("div");phases.className="example-turn__phases";
      for(const [field,tokenId] of examplePhases){if(!turn[field]?.length)continue;const phase=document.createElement("section");phase.className=`example-turn__phase example-turn__phase--${field.replaceAll("_","-")}`;const phaseTitle=document.createElement("h5");phaseTitle.className="example-turn__phase-title";phaseTitle.textContent=String(ui.get(tokenId));phase.append(phaseTitle);appendParagraph(phase,turn[field]);phases.append(phase);}
      aside.append(title,phases);list.append(aside);}
    section.append(heading,list);parent.append(section);
  }
  const appendFeatureTier = (parent:HTMLElement,labelText:string,body:(content:HTMLElement)=>void,tier?:number) => {const tierElement=document.createElement("div");tierElement.className="feature-tier";if(tier!==undefined)tierElement.dataset.tier=String(tier);const label=document.createElement("div");label.className="feature-tier__label";label.textContent=labelText;const content=document.createElement("div");content.className="feature-tier__content";body(content);tierElement.append(label,content);parent.append(tierElement);};
  function renderTierParagraph(parent:HTMLElement,block:any):boolean {const text=inlineText(block.inlines);const matches=[...text.matchAll(/(^|\s)(T(\d+) (?:Base|Overload)):\s*/g)];if(!matches.length)return false;const first=matches[0]!,prefixEnd=first.index??0;const [prefixStart,prefixTrimmedEnd]=trimInlineRange(text,0,prefixEnd);if(prefixStart<prefixTrimmedEnd)appendParagraph(parent,inlineSlice(block.inlines,prefixStart,prefixTrimmedEnd));matches.forEach((match,index)=>{const next=matches[index+1];const start=(match.index??0)+match[0].length,end=next?.index??text.length;const [trimmedStart,trimmedEnd]=trimInlineRange(text,start,end);appendFeatureTier(parent,match[2]!,content=>appendParagraph(content,inlineSlice(block.inlines,trimmedStart,trimmedEnd)),Number(match[3]));});return true;}
  function renderBlock(parent: HTMLElement, block: any): void {
    if(block.type==="tier"){appendFeatureTier(parent,`T${block.tier} Overload`,content=>block.body.forEach((child:any)=>renderBlock(content,child)),block.tier);return;}
    if(block.type==="paragraph"||block.type==="note"){if(block.type==="paragraph"&&renderTierParagraph(parent,block))return;const element=document.createElement(block.type==="note"?"aside":"p");if(block.type==="note")element.className=`note ${block.kind}`;block.inlines.forEach((node:any)=>appendInline(element,node));parent.append(element);return;}
    if(block.type==="list"){const list=document.createElement(block.style==="ordered"?"ol":"ul");for(const item of block.items){const li=document.createElement("li");item.forEach((node:any)=>appendInline(li,node));list.append(li);}parent.append(list);return;}
    if(block.type==="table"){const wrapper=document.createElement("div");wrapper.className="table-scroll";wrapper.tabIndex=0;const table=document.createElement("table");const thead=document.createElement("thead");const headerRow=document.createElement("tr");
      for(const cell of block.headers){const th=document.createElement("th");th.scope="col";cell.forEach((node:any)=>appendInline(th,node));headerRow.append(th);}thead.append(headerRow);table.append(thead);const tbody=document.createElement("tbody");
      for(const row of block.rows){const tr=document.createElement("tr");for(const cell of row){const td=document.createElement("td");cell.forEach((node:any)=>appendInline(td,node));tr.append(td);}tbody.append(tr);}table.append(tbody);wrapper.append(table);parent.append(wrapper);}
  }
  function renderTopic(focusEntity?: string): void {
    normalizeNavigation();const main=get("rules-content");main.textContent="";const current=topic();if(!current)return;
    for(const entityId of current.entity_ids){const entity=entities.get(entityId) as any;const article=document.createElement("article");article.id=`entity-${entity.id}`;const heading=document.createElement("h2");heading.textContent=entity.title;heading.tabIndex=-1;heading.dataset.sourcePath=`entities.${entity.id}.title`;article.append(heading);
      if(entity.level!==undefined||entity.psi_cost!==undefined||entity.activation||entity.requires_concentration===true){const dl=document.createElement("dl");dl.className="facts feature-metadata";for(const [tokenId,value] of [["fact_level",entity.level],["fact_psi",entity.psi_cost],["fact_activation",entity.activation]])if(value!==undefined){const item=document.createElement("div");item.className="feature-metadata__item";const dt=document.createElement("dt");dt.textContent=String(ui.get(tokenId));const dd=document.createElement("dd");dd.textContent=String(value).replaceAll("_"," ");item.append(dt,dd);dl.append(item);}if(entity.requires_concentration===true){const item=document.createElement("div");item.className="feature-metadata__item feature-metadata__item--concentration";const dt=document.createElement("dt");dt.className="sr-only";dt.textContent=String(ui.get("fact_requirement"));const dd=document.createElement("dd");dd.textContent=String(ui.get("fact_concentration"));item.append(dt,dd);dl.append(item);}article.append(dl);}
      entity.content.forEach((block:any)=>renderBlock(article,block));renderExampleTurns(article,entity);main.append(article);}
    if(focusEntity)(document.querySelector(`#entity-${CSS.escape(focusEntity)} h2`) as HTMLElement|null)?.focus();
  }
  function renderNameOptions(): void {
    const select=get("name-select") as HTMLSelectElement;select.textContent="";const placeholder=document.createElement("option");placeholder.value="";placeholder.textContent=String(ui.get("name_placeholder"));select.append(placeholder);
    for(const area of areaValues){const group=document.createElement("optgroup");group.label=area.label;const names=indexed.filter((candidate:any)=>candidate.primary_rules_area===area.id).sort((a:any,b:any)=>a.title<b.title?-1:a.title>b.title?1:a.id<b.id?-1:a.id>b.id?1:0);for(const item of names){const option=document.createElement("option");option.value=item.id;option.textContent=item.title;group.append(option);}select.append(group);}
    resetName();
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
    const root=get("filter-results");root.textContent="";if(!hasSelections()){const p=document.createElement("p");p.textContent=String(ui.get("filter_instruction"));root.append(p);updateAvailability();return;}
    const result=matches();if(!result.length){const p=document.createElement("p");p.textContent=String(ui.get("no_matches"));root.append(p);}else{const list=document.createElement("ul");for(const item of result){const li=document.createElement("li");const button=document.createElement("button");const area=areas.get(item.primary_rules_area) as any;const label=String(ui.get("result_identity")).replace("{entity_title}",item.title).replace("{primary_rules_area_label}",area.label);button.textContent=label;button.setAttribute("aria-label",label);button.addEventListener("click",()=>openEntity(item.id,"result"));li.append(button);list.append(li);}root.append(list);}updateAvailability();
    if(shouldAnnounce)announce(result.length===1?String(ui.get("one_match")).replace("{count}",String(result.length)):result.length?String(ui.get("match_count")).replace("{count}",String(result.length)):String(ui.get("no_matches")));
  }
  function resultArea(item:any):string{return item.primary_rules_area;}
  function openEntity(id:string,origin:"name_open"|"result"):void {
    const item=indexed.find((candidate:any)=>candidate.id===id);if(!item)return;const area=origin==="name_open"?item.primary_rules_area:resultArea(item);state.category=area;state.topic=item.routes[area];state.classifications={};state.entity=id;state.resultRoute=item.routes[area];state.focusOrigin=origin;writeHistory("push");renderNavigation();renderFacets();renderResults(false);resetName();renderTopic(id);if(origin==="name_open")announce(String(ui.get("filter_cleared")));
  }
  function parseFragment():boolean {
    let corrected=false;const parameters=new URLSearchParams(location.hash.slice(1));const requestedCategory=parameters.get("category");const requestedTopic=parameters.get("topic");if(normalizeNavigation(requestedCategory,requestedTopic))corrected=true;state.classifications={};
    const filters=parameters.get("filters");if(filters)for(const pair of filters.split(";")){const [facetId,raw]=pair.split(":");if(!facetId||!raw){corrected=true;continue;}const facet=model.authority.facets.find((candidate:any)=>candidate.id===facetId);if(!facet){corrected=true;continue;}const allowed=new Set(model.authority.vocabularies[facet.vocabulary].map((value:any)=>value.id));const values=raw.split(",").filter((value:string)=>allowed.has(value));if(!values.length){corrected=true;continue;}state.classifications[facetId]=facet.cardinality==="multi"?values.slice(0,allowed.size):values[0];}
    const entityId=parameters.get("entity");if(entityId&&entities.has(entityId)){state.entity=entityId;const currentTopic=topic();if(!currentTopic.entity_ids.includes(entityId)){const item=indexed.find((candidate:any)=>candidate.id===entityId);state.category=item.primary_rules_area;state.topic=item.routes[item.primary_rules_area];state.classifications={};corrected=true;}}else{if(entityId)corrected=true;state.entity=null;}return corrected;
  }
  function restore(snapshot:any):void {
    const fields=new Set(model.policy.history_state_fields);const facetIds=new Set(model.authority.facets.map((facet:any)=>facet.id));const validFilters=snapshot?.classifications&&typeof snapshot.classifications==="object"&&!Array.isArray(snapshot.classifications)&&Object.entries(snapshot.classifications).every(([id,value]:any)=>facetIds.has(id)&&(typeof value==="string"||Array.isArray(value)));const validFocus=model.policy.focus_origins.includes(snapshot?.focusOrigin);const validEntity=snapshot?.entity===null||entities.has(snapshot?.entity);
    if(!snapshot||Object.keys(snapshot).some(key=>!fields.has(key))||!validFilters||!validFocus||!validEntity){initialize();return;}Object.assign(state,snapshot);normalizeNavigation();renderNavigation();renderFacets();renderResults(false);renderNameOptions();renderTopic();
  }
  function initialize():void {const corrected=parseFragment();renderNavigation();renderNameOptions();renderFacets();renderResults(false);renderTopic();writeHistory("replace");if(corrected)announce(String(ui.get("filter_instruction")));}
  get("category-select").addEventListener("change",event=>{normalizeNavigation((event.target as HTMLSelectElement).value,"");state.entity=null;state.resultRoute=null;state.focusOrigin="category";renderNavigation();renderTopic();writeHistory("push");announce(category().label);});
  get("topic-select").addEventListener("change",event=>{normalizeNavigation(state.category,(event.target as HTMLSelectElement).value);state.entity=null;state.resultRoute=null;state.focusOrigin="topic";renderTopic();writeHistory("push");announce(topic()?.title??category().label);});
  get("name-select").addEventListener("change",updateOpen);
  get("name-open").addEventListener("click",()=>{if(get("name-open").getAttribute("aria-disabled")==="true")return;openEntity(selectedName(),"name_open");});
  get("facet-controls").addEventListener("change",()=>{readFacetControls();resetName();state.entity=null;state.focusOrigin="result";writeHistory("push");renderResults(true);});
  addEventListener("popstate",event=>restore(event.state));initialize();
}

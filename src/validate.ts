import type { Authority, Diagnostic } from "./types.js";
import { codepointCompare } from "./canonical.js";

function duplicateDiagnostics(values:string[],code:string,label:string):Diagnostic[]{const seen=new Set<string>();const diagnostics:Diagnostic[]=[];for(const value of values){if(seen.has(value))diagnostics.push({severity:"error",code,message:`Duplicate ${label}: ${value}`});seen.add(value);}return diagnostics;}
function vocabulary(authority:Authority,name:string):Set<string>{return new Set((authority.vocabularies[name]??[]).map(value=>value.id));}
const inlineText=(nodes:any[]|undefined):string=>nodes?.map(node=>node.text??node.label??String(node.value?.value??"")).join("")??"";

interface LocatedValue<T>{path:string;value:T}
function collectOnboardingIds(value:unknown,path="/onboarding",result:LocatedValue<string>[]=[]):LocatedValue<string>[] {
  if(Array.isArray(value)){value.forEach((item,index)=>collectOnboardingIds(item,`${path}/${index}`,result));return result;}
  if(!value||typeof value!=="object")return result;
  for(const [key,child] of Object.entries(value)){
    const childPath=`${path}/${key}`;
    if(key==="id"&&typeof child==="string")result.push({path:childPath,value:child});
    else collectOnboardingIds(child,childPath,result);
  }
  return result;
}
function collectOnboardingDestinations(value:unknown,path="/onboarding",result:LocatedValue<any>[]=[]):LocatedValue<any>[] {
  if(Array.isArray(value)){value.forEach((item,index)=>collectOnboardingDestinations(item,`${path}/${index}`,result));return result;}
  if(!value||typeof value!=="object")return result;
  const object=value as Record<string,unknown>;
  if(typeof object.kind==="string"&&(typeof object.section_id==="string"||typeof object.category_id==="string"||typeof object.entity_id==="string"))result.push({path,value:object});
  for(const [key,child] of Object.entries(object))collectOnboardingDestinations(child,`${path}/${key}`,result);
  return result;
}
function collectOnboardingStrings(value:unknown,result:string[]=[]):string[]{
  if(typeof value==="string"){result.push(value);return result;}if(Array.isArray(value)){value.forEach(item=>collectOnboardingStrings(item,result));return result;}if(value&&typeof value==="object")Object.values(value).forEach(item=>collectOnboardingStrings(item,result));return result;
}

export function validateSemantics(authority:Authority):Diagnostic[]{
  const diagnostics:Diagnostic[]=[];
  const entities=new Map(authority.entities.map(entity=>[entity.id,entity]));
  diagnostics.push(...duplicateDiagnostics(authority.entities.map(entity=>entity.id),"entity.duplicate","entity ID"));
  diagnostics.push(...duplicateDiagnostics(authority.facets.map(facet=>facet.id),"facet.duplicate","facet ID"));
  const requiredAreas=["common_features","advanced_training","cryokinesis","pyrokinesis","psychokinesis","electrokinesis"];
  const categories=new Map(authority.navigation.categories.map(category=>[category.id,category]));
  for(const area of requiredAreas)if(!categories.has(area))diagnostics.push({severity:"error",code:"navigation.category_missing",message:`Required category ${area} is missing`});
  if(authority.navigation.categories.some(category=>category.id==="disciplines"||category.label==="Disciplines"))diagnostics.push({severity:"error",code:"navigation.umbrella",message:"Umbrella Disciplines category is prohibited"});
  diagnostics.push(...duplicateDiagnostics(authority.navigation.categories.map(category=>category.id),"navigation.category_duplicate","category ID"));
  const topicToArea=new Map<string,string>();const topicEntities=new Map<string,Set<string>>();
  for(const category of authority.navigation.categories){
    if(!category.topics.some(topic=>topic.id===category.default_topic_id))diagnostics.push({severity:"error",code:"navigation.default_topic",message:`Category ${category.id} has an invalid default topic`});
    for(const topic of category.topics){if(topicToArea.has(topic.id))diagnostics.push({severity:"error",code:"navigation.topic_duplicate",message:`Duplicate topic ID ${topic.id}`});topicToArea.set(topic.id,category.id);topicEntities.set(topic.id,new Set(topic.entity_ids));for(const id of topic.entity_ids)if(!entities.has(id))diagnostics.push({severity:"error",code:"navigation.entity_unknown",message:`Topic ${topic.id} references unknown entity ${id}`});}
  }
  const onboardingIds=collectOnboardingIds(authority.onboarding);diagnostics.push(...duplicateDiagnostics(onboardingIds.map(item=>item.value),"onboarding.id_duplicate","onboarding ID"));
  for(const item of onboardingIds)if(entities.has(item.value))diagnostics.push({severity:"error",code:"onboarding.entity_collision",message:`Onboarding ID ${item.value} collides with a publishable entity`,path:item.path});
  if(authority.entities.length!==44)diagnostics.push({severity:"error",code:"onboarding.entity_boundary",message:`Onboarding must remain outside the 44-entity publication boundary; found ${authority.entities.length} entities`,path:"/entities"});
  const sectionIds=new Set([authority.onboarding.basic_turn.id,authority.onboarding.build_checklist.id,authority.onboarding.disciplines.id,authority.onboarding.glossary.id,authority.onboarding.next_destinations.id]);
  for(const {path,value:destination} of collectOnboardingDestinations(authority.onboarding)){
    if(destination.kind==="onboarding_section"){
      if(!sectionIds.has(destination.section_id))diagnostics.push({severity:"error",code:"onboarding.section_unknown",message:`Unknown onboarding section ${destination.section_id}`,path});
      continue;
    }
    if(destination.kind==="category"){
      const targetCategory=categories.get(destination.category_id);
      if(!targetCategory)diagnostics.push({severity:"error",code:"onboarding.category_unknown",message:`Unknown onboarding category ${destination.category_id}`,path});
      else if(!targetCategory.topics.some(topic=>topic.id===targetCategory.default_topic_id))diagnostics.push({severity:"error",code:"onboarding.category_route",message:`Onboarding category ${destination.category_id} has no resolvable default topic`,path});
      continue;
    }
    if(destination.kind==="entity"){
      const targetEntity=entities.get(destination.entity_id);
      if(!targetEntity){diagnostics.push({severity:"error",code:"onboarding.entity_unknown",message:`Unknown onboarding entity ${destination.entity_id}`,path});continue;}
      const primaryArea=targetEntity.presentation_metadata.primary_rules_area,targetCategory=categories.get(primaryArea);
      const containingTopics=targetCategory?.topics.filter(topic=>topic.entity_ids.includes(targetEntity.id))??[];
      const canonicalTopic=targetEntity.presentation_metadata.canonical_topic_by_area[primaryArea]??containingTopics.sort((a,b)=>a.order-b.order)[0]?.id;
      if(!canonicalTopic||!containingTopics.some(topic=>topic.id===canonicalTopic))diagnostics.push({severity:"error",code:"onboarding.entity_route",message:`Onboarding entity ${destination.entity_id} has no resolvable canonical route`,path});
    }
  }
  const disciplineCategories=authority.onboarding.disciplines.cards.map(card=>card.destination.kind==="category"?card.destination.category_id:"").sort(codepointCompare);
  const requiredDisciplines=["cryokinesis","electrokinesis","psychokinesis","pyrokinesis"].sort(codepointCompare);
  if(JSON.stringify(disciplineCategories)!==JSON.stringify(requiredDisciplines))diagnostics.push({severity:"error",code:"onboarding.disciplines",message:"Onboarding must target each Discipline category exactly once",path:"/onboarding/disciplines/cards"});
  const internalPaths=authority.onboarding.primary_paths.filter(path=>path.destination.kind==="onboarding_section").map(path=>path.destination.kind==="onboarding_section"?path.destination.section_id:"").sort(codepointCompare);
  const referencePaths=authority.onboarding.primary_paths.filter(path=>path.destination.kind==="category"&&path.destination.category_id===authority.navigation.default_category_id);
  if(JSON.stringify(internalPaths)!==JSON.stringify([authority.onboarding.basic_turn.id,authority.onboarding.build_checklist.id].sort(codepointCompare))||referencePaths.length!==1)diagnostics.push({severity:"error",code:"onboarding.primary_paths",message:"Onboarding primary paths must target Build Checklist, Basic Turn, and the default Rules Reference exactly once",path:"/onboarding/primary_paths"});
  if(collectOnboardingStrings(authority.onboarding).some(value=>/(?:https?:|www\.|mailto:)/iu.test(value)))diagnostics.push({severity:"error",code:"onboarding.external_url",message:"Onboarding must not contain raw external URLs",path:"/onboarding"});
  const rulesAreas=vocabulary(authority,"rules_areas"),entityKinds=vocabulary(authority,"entity_kinds"),roles=vocabulary(authority,"feature_roles"),modes=vocabulary(authority,"acquisition_modes");
  const titleByGroup=new Set<string>();
  for(const [index,entity] of authority.entities.entries()){
    const path=`/entities/${index}`;
    if(entity.kind!==entity.classifications.entity_kind)diagnostics.push({severity:"error",code:"classification.kind_mismatch",message:`${entity.id}: kind and entity_kind differ`,path});
    if(!entityKinds.has(entity.kind))diagnostics.push({severity:"error",code:"classification.kind_unknown",message:`${entity.id}: unknown entity kind ${entity.kind}`,path});
    for(const area of entity.classifications.rules_area)if(!rulesAreas.has(area))diagnostics.push({severity:"error",code:"classification.area_unknown",message:`${entity.id}: unknown rules area ${area}`,path});
    if(entity.kind==="feature"&&(!entity.classifications.feature_role||!roles.has(entity.classifications.feature_role)))diagnostics.push({severity:"error",code:"classification.role",message:`${entity.id}: feature requires a valid feature_role`,path});
    if(entity.level===undefined&&!entity.progression_section)diagnostics.push({severity:"error",code:"progression.section_missing",message:`${entity.id}: an unlevelled entity requires an explicit progression_section`,path});
    if(entity.level!==undefined&&entity.progression_section)diagnostics.push({severity:"error",code:"progression.section_conflict",message:`${entity.id}: a levelled entity must not declare progression_section`,path});
    const inAdvanced=entity.classifications.rules_area.includes("advanced_training");
    if(inAdvanced&&(!entity.classifications.acquisition_mode||!modes.has(entity.classifications.acquisition_mode)))diagnostics.push({severity:"error",code:"classification.acquisition",message:`${entity.id}: Advanced Training feature requires acquisition_mode`,path});
    if(!entity.classifications.rules_area.includes(entity.presentation_metadata.primary_rules_area))diagnostics.push({severity:"error",code:"presentation.primary_area",message:`${entity.id}: primary area is not in rules_area`,path});
    const renderedAreas=new Set<string>();const topicsByArea=new Map<string,string[]>();
    for(const [topicId,ids] of topicEntities)if(ids.has(entity.id)){const area=topicToArea.get(topicId)!;renderedAreas.add(area);const list=topicsByArea.get(area)??[];list.push(topicId);topicsByArea.set(area,list);}
    const authored=[...entity.classifications.rules_area].sort(),rendered=[...renderedAreas].sort();
    if(JSON.stringify(authored)!==JSON.stringify(rendered))diagnostics.push({severity:"error",code:"classification.rules_area_redundancy",message:`${entity.id}: authored areas [${authored}] differ from rendered areas [${rendered}]`,path});
    for(const [area,topicIds] of topicsByArea)if(topicIds.length>1){const canonical=entity.presentation_metadata.canonical_topic_by_area[area];if(!canonical||!topicIds.includes(canonical))diagnostics.push({severity:"error",code:"presentation.canonical_topic",message:`${entity.id}: area ${area} needs one valid canonical topic`,path});}
    for(const [area,topicId] of Object.entries(entity.presentation_metadata.canonical_topic_by_area))if(!topicsByArea.get(area)?.includes(topicId))diagnostics.push({severity:"error",code:"presentation.canonical_topic_extra",message:`${entity.id}: invalid canonical mapping ${area} -> ${topicId}`,path});
    const titleKey=`${entity.presentation_metadata.primary_rules_area}\0${entity.title}`;if(titleByGroup.has(titleKey))diagnostics.push({severity:"error",code:"presentation.name_duplicate",message:`Duplicate Name label ${entity.title} in ${entity.presentation_metadata.primary_rules_area}`,path});titleByGroup.add(titleKey);
    if(!entity.content.length)diagnostics.push({severity:"error",code:"coverage.empty_entity",message:`${entity.id}: no rule-significant content`,path});
    for(const [blockIndex,block] of entity.content.entries()){
      if(!block.row_references)continue;const referencePath=`${path}/content/${blockIndex}/row_references`;
      if(entity.id!=="subclass_feature_reference")diagnostics.push({severity:"error",code:"reference.scope",message:`${entity.id}: row references are only valid on Subclass Feature Reference`,path:referencePath});
      if(block.type!=="table"||!block.rows){diagnostics.push({severity:"error",code:"reference.block_type",message:`${entity.id}: row references require a table`,path:referencePath});continue;}
      if(block.row_references.length!==block.rows.length)diagnostics.push({severity:"error",code:"reference.row_count",message:`${entity.id}: ${block.row_references.length} row references do not match ${block.rows.length} table rows`,path:referencePath});
      for(const [rowIndex,reference] of block.row_references.entries()){
        const row=block.rows[rowIndex];if(!row)continue;const rowPath=`${referencePath}/${rowIndex}`;
        const displayedLevel=inlineText(row[0]),displayedFeature=inlineText(row[1]);
        if(reference.reference_level!==displayedLevel)diagnostics.push({severity:"error",code:"reference.level_display",message:`${entity.id}: row ${rowIndex+1} metadata level ${reference.reference_level} differs from ${displayedLevel}`,path:rowPath});
        if("entity_id" in reference){const referenced=entities.get(reference.entity_id);
          if(!referenced){diagnostics.push({severity:"error",code:"reference.entity_unknown",message:`${entity.id}: row ${rowIndex+1} references unknown entity ${reference.entity_id}`,path:rowPath});continue;}
          if(referenced.kind!=="feature")diagnostics.push({severity:"error",code:"reference.entity_kind",message:`${entity.id}: row ${rowIndex+1} references non-feature ${reference.entity_id}`,path:rowPath});
          if(referenced.title!==displayedFeature)diagnostics.push({severity:"error",code:"reference.feature_display",message:`${entity.id}: row ${rowIndex+1} label ${displayedFeature} differs from ${referenced.title}`,path:rowPath});
          const referenceLevel=Number(reference.reference_level.match(/^\d+/)?.[0]);if(referenced.level!==referenceLevel)diagnostics.push({severity:"error",code:"reference.entity_level",message:`${entity.id}: row ${rowIndex+1} reference level ${reference.reference_level} differs from ${reference.entity_id} level ${referenced.level}`,path:rowPath});
        }
      }
    }
  }
  const subclassReference=entities.get("subclass_feature_reference");const annotatedTables=subclassReference?.content.filter(block=>block.row_references)??[];
  if(annotatedTables.length!==1)diagnostics.push({severity:"error",code:"reference.table_count",message:"Subclass Feature Reference requires exactly one annotated Psi Cost Reference table"});
  diagnostics.push(...duplicateDiagnostics((authority.audits??[]).map(audit=>audit.id),"audit.duplicate","audit ID"));
  for(const audit of authority.audits??[])for(const subjectId of audit.subject_ids)if(!entities.has(subjectId))diagnostics.push({severity:"error",code:"audit.subject_unknown",message:`${audit.id}: unknown subject ${subjectId}`});
  const authorityAudit=(authority.audits??[]).find(audit=>audit.id==="yaml_rules_authority");const authoredEntityIds=[...entities.keys()].sort(codepointCompare);const auditedEntityIds=[...new Set(authorityAudit?.subject_ids??[])].sort(codepointCompare);if(!authorityAudit||JSON.stringify(auditedEntityIds)!==JSON.stringify(authoredEntityIds))diagnostics.push({severity:"error",code:"authority.coverage",message:"YAML authority audit must cover every publishable entity exactly once"});
  for(const facet of authority.facets){if(!authority.vocabularies[facet.vocabulary])diagnostics.push({severity:"error",code:"facet.vocabulary",message:`Facet ${facet.id} references unknown vocabulary ${facet.vocabulary}`});}
  return diagnostics;
}

export type ProgressionSection="foundation"|"levelled"|"reference";
export interface FilterIndexEntry {id:string;title:string;primary_rules_area:string;rules_area_order:number;minimum_level:number|null;progression_section:ProgressionSection;progression_order:number;feature_role_order:number;classifications:Record<string,string[]>;routes:Record<string,string>}
export interface NameIndexGroup {id:string;label:string;order:number;entity_ids:string[]}
export interface FilterIndex { entities:FilterIndexEntry[];name_groups:NameIndexGroup[] }
const progressionSectionOrder:Record<ProgressionSection,number>={foundation:0,levelled:1,reference:2};
const numericLevel=(entry:FilterIndexEntry):number=>entry.minimum_level===null?Number.MAX_SAFE_INTEGER:Number(entry.minimum_level);
export function compareNameEntries(a:FilterIndexEntry,b:FilterIndexEntry):number{
  return (progressionSectionOrder[a.progression_section]-progressionSectionOrder[b.progression_section])
    ||(numericLevel(a)-numericLevel(b))
    ||codepointCompare(a.title,b.title)
    ||codepointCompare(a.id,b.id);
}
export function compareFilterEntries(a:FilterIndexEntry,b:FilterIndexEntry):number{
  return (a.rules_area_order-b.rules_area_order)
    ||(progressionSectionOrder[a.progression_section]-progressionSectionOrder[b.progression_section])
    ||(numericLevel(a)-numericLevel(b))
    ||(a.progression_order-b.progression_order)
    ||(a.feature_role_order-b.feature_role_order)
    ||codepointCompare(a.title,b.title)
    ||codepointCompare(a.id,b.id);
}
export function buildFilterIndex(authority:Authority):FilterIndex{
  const routesByEntity=new Map<string,Map<string,string[]>>();for(const category of authority.navigation.categories)for(const topic of category.topics)for(const entityId of topic.entity_ids){const areas=routesByEntity.get(entityId)??new Map();const topics=areas.get(category.id)??[];topics.push(topic.id);areas.set(category.id,topics);routesByEntity.set(entityId,areas);}
  const areaOrder=new Map((authority.vocabularies.rules_areas??[]).map(value=>[value.id,value.order]));
  const roleOrder=new Map((authority.vocabularies.feature_roles??[]).map(value=>[value.id,value.order]));
  const topicOrderByEntityArea=new Map<string,number>();for(const category of authority.navigation.categories)for(const topic of category.topics)for(const entityId of topic.entity_ids)topicOrderByEntityArea.set(`${entityId}\0${category.id}`,Math.min(topic.order,topicOrderByEntityArea.get(`${entityId}\0${category.id}`)??Number.MAX_SAFE_INTEGER));
  const entries=authority.entities.map(entity=>{const primaryArea=entity.presentation_metadata.primary_rules_area;const areaRoutes=routesByEntity.get(entity.id)!;const routes=Object.fromEntries([...areaRoutes].map(([area,topics])=>[area,entity.presentation_metadata.canonical_topic_by_area[area]??topics[0]! ]));return{id:entity.id,title:entity.title,primary_rules_area:primaryArea,rules_area_order:areaOrder.get(primaryArea)!,minimum_level:entity.level??null,progression_section:(entity.level===undefined?entity.progression_section!:"levelled") as ProgressionSection,progression_order:topicOrderByEntityArea.get(`${entity.id}\0${primaryArea}`)!,feature_role_order:entity.classifications.feature_role?roleOrder.get(entity.classifications.feature_role)!:Number.MAX_SAFE_INTEGER,classifications:{rules_area:[primaryArea],entity_kind:[entity.classifications.entity_kind],...(entity.classifications.feature_role?{feature_role:[entity.classifications.feature_role]}:{}),...(entity.classifications.acquisition_mode?{acquisition_mode:[entity.classifications.acquisition_mode]}:{})},routes};});
  const name_groups=(authority.vocabularies.rules_areas??[]).map(area=>({id:area.id,label:area.label,order:area.order,entity_ids:entries.filter(entry=>entry.primary_rules_area===area.id).sort(compareNameEntries).map(entry=>entry.id)})).sort((a,b)=>a.order-b.order||codepointCompare(a.id,b.id));
  return{entities:[...entries].sort(compareFilterEntries),name_groups};
}

export function buildIntegrity(authority:Authority,index:FilterIndex):Record<string,unknown>{
  const checks=index.entities.map(item=>{const entity=authority.entities.find(candidate=>candidate.id===item.id)!;const canonicalAreas=item.classifications.rules_area!;return{entity_id:item.id,identity_retrieval:item.title===entity.title,canonical_area_retrieval:canonicalAreas.length===1&&canonicalAreas[0]===item.primary_rules_area,classification_vector_retrieval:Object.entries(item.classifications).every(([facet,values])=>values.every(value=>(entity.classifications as any)[facet]?.includes?.(value)||(entity.classifications as any)[facet]===value)),route_areas:Object.keys(item.routes).sort(),rules_areas:[...entity.classifications.rules_area].sort()};});
  return{version:1,entity_count:index.entities.length,all_passed:checks.every(check=>check.identity_retrieval&&check.canonical_area_retrieval&&check.classification_vector_retrieval&&JSON.stringify(check.route_areas)===JSON.stringify(check.rules_areas)),controlled_vocabularies:Object.fromEntries(Object.entries(authority.vocabularies).map(([name,values])=>[name,values.map(value=>value.id)])),identity_domain:index.entities.map(entity=>({id:entity.id,title:entity.title,primary_rules_area:entity.primary_rules_area})),checks};
}

export function summarizeDiagnostics(diagnostics:Diagnostic[]):string{return diagnostics.map(item=>`${item.severity.toUpperCase()} ${item.code}${item.path?` ${item.path}`:""}: ${item.message}`).join("\n");}

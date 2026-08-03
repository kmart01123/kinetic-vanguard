import { readFile } from "node:fs/promises";
import type { Authority, Diagnostic, Entity } from "./types.js";
import { hashFile, sha256, prettyCanonicalJson, codepointCompare } from "./canonical.js";

type LedgerEntry={ledger_entry_id:string;source_unit_id:string;workflow_state:string;disposition:string|null;destination_entity_ids:string[]};
export interface MigrationState { manifest:Record<string,any>; inventory:Record<string,any>; coverage:Record<string,any>; ledger:Record<string,any>; effective:Record<string,any>; accepted:boolean }

const QUALIFYING=new Set(["transposed","consolidated","rewritten_equivalent","corrected_by_rules_decision"]);

function duplicateDiagnostics(values:string[],code:string,label:string):Diagnostic[]{const seen=new Set<string>();const diagnostics:Diagnostic[]=[];for(const value of values){if(seen.has(value))diagnostics.push({severity:"error",code,message:`Duplicate ${label}: ${value}`});seen.add(value);}return diagnostics;}
function vocabulary(authority:Authority,name:string):Set<string>{return new Set((authority.vocabularies[name]??[]).map(value=>value.id));}

export async function validateMigration(requireAccepted:boolean):Promise<{state:MigrationState;diagnostics:Diagnostic[]}>{
  const diagnostics:Diagnostic[]=[];
  const [manifestText,inventoryText,coverageText,ledgerText]=await Promise.all(["migration/manifest.json","migration/source-units.json","migration/source-coverage.json","migration/disposition-ledger.json"].map(path=>readFile(path,"utf8")));
  const manifest=JSON.parse(manifestText!),inventory=JSON.parse(inventoryText!),coverage=JSON.parse(coverageText!),ledger=JSON.parse(ledgerText!);
  const checks:Array<[string,string,string]>=[
    [manifest.source_unit_inventory.path,manifest.source_unit_inventory.sha256,"inventory"],
  ];
  checks.push([manifest.source_coverage.path,manifest.source_coverage.sha256,"coverage"],[manifest.disposition_ledger.path,manifest.disposition_ledger.sha256,"ledger"]);
  for(const [path,expected,label] of checks)if(await hashFile(path)!==expected)diagnostics.push({severity:"error",code:"migration.hash",message:`Migration ${label} hash does not match manifest`,path});
  if(coverage.source_sha256!==manifest.migration_source_sha256||inventory.source_sha256!==manifest.migration_source_sha256||ledger.source_sha256!==manifest.migration_source_sha256)diagnostics.push({severity:"error",code:"migration.source_hash",message:"Migration artifacts disagree on pinned source hash"});
  let cursor=0;for(const span of coverage.spans as Array<{start:number;end:number}>){if(span.start!==cursor)diagnostics.push({severity:"error",code:"migration.coverage",message:`Coverage gap or overlap at byte ${cursor}`});cursor=span.end;}
  if(cursor!==coverage.total_byte_count||coverage.covered_byte_count!==coverage.total_byte_count||coverage.gap_count!==0||coverage.overlap_count!==0)diagnostics.push({severity:"error",code:"migration.coverage",message:"Source coverage is not an exact partition"});
  const unitIds=(inventory.units as Array<{id:string}>).map(unit=>unit.id);diagnostics.push(...duplicateDiagnostics(unitIds,"migration.unit_duplicate","source unit ID"));
  const entries=ledger.entries as LedgerEntry[];diagnostics.push(...duplicateDiagnostics(entries.map(entry=>entry.source_unit_id),"migration.ledger_duplicate","ledger source unit"));
  if(new Set(entries.map(entry=>entry.source_unit_id)).size!==new Set(unitIds).size||unitIds.some(id=>!entries.some(entry=>entry.source_unit_id===id)))diagnostics.push({severity:"error",code:"migration.ledger_coverage",message:"Disposition ledger does not cover every inventory unit exactly once"});
  const pending=entries.filter(entry=>entry.workflow_state==="pending_review"||!entry.disposition);
  if(pending.length)diagnostics.push({severity:requireAccepted?"error":"warning",code:"migration.pending_review",message:`${pending.length} source units remain pending human disposition review`});
  const effective={format_version:"1.0.0",source_sha256:manifest.migration_source_sha256,entries:entries.map(entry=>({source_unit_id:entry.source_unit_id,terminal_id:entry.ledger_entry_id,effective_disposition:entry.disposition,destination_entity_ids:entry.destination_entity_ids,amendment_chain:[]})).sort((a,b)=>codepointCompare(a.source_unit_id,b.source_unit_id))};
  const accepted=pending.length===0&&Boolean(manifest.migration_acceptance);
  if(requireAccepted&&!manifest.migration_acceptance)diagnostics.push({severity:"error",code:"migration.not_accepted",message:"Migration manifest has no human-reviewed acceptance record"});
  return{state:{manifest,inventory,coverage,ledger,effective,accepted},diagnostics};
}

export function validateSemantics(authority:Authority,migration:MigrationState,requireAccepted:boolean):Diagnostic[]{
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
  const rulesAreas=vocabulary(authority,"rules_areas"),entityKinds=vocabulary(authority,"entity_kinds"),roles=vocabulary(authority,"feature_roles"),modes=vocabulary(authority,"acquisition_modes");
  const inventoryIds=new Set((migration.inventory.units as Array<{id:string}>).map(unit=>unit.id));
  const effectiveByUnit=new Map((migration.effective.entries as Array<any>).map(entry=>[entry.source_unit_id,entry]));
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
    const originIds=entity.origins.flatMap(origin=>origin.source_unit_ids);if(!originIds.length)diagnostics.push({severity:"error",code:"origin.missing",message:`${entity.id}: missing origin`,path});
    for(const id of originIds){if(!inventoryIds.has(id))diagnostics.push({severity:"error",code:"origin.unknown",message:`${entity.id}: unknown origin unit ${id}`,path});if(requireAccepted&&!QUALIFYING.has(effectiveByUnit.get(id)?.effective_disposition))diagnostics.push({severity:"error",code:"origin.unaccepted",message:`${entity.id}: origin ${id} lacks qualifying accepted disposition`,path});}
    if(!entity.content.length)diagnostics.push({severity:"error",code:"coverage.empty_entity",message:`${entity.id}: no rule-significant content`,path});
    const contentOriginIds=new Set<string>();const addInlines=(nodes:Entity["content"][number]["inlines"])=>nodes?.forEach(node=>contentOriginIds.add(node.source_unit_id));const visitBlock=(block:Entity["content"][number])=>{addInlines(block.inlines);addInlines(block.heading);block.items?.forEach(addInlines);block.headers?.forEach(addInlines);block.rows?.forEach(row=>row.forEach(addInlines));block.body?.forEach(visitBlock);};entity.content.forEach(visitBlock);
    for(const turn of entity.example_turns??[]){addInlines(turn.title);addInlines(turn.setup);addInlines(turn.activation);addInlines(turn.rolls_or_saves);addInlines(turn.damage);addInlines(turn.effects);addInlines(turn.result);}
    for(const id of contentOriginIds)if(!originIds.includes(id))diagnostics.push({severity:"error",code:"coverage.origin",message:`${entity.id}: rendered leaf ${id} is absent from entity origins`,path});
  }
  for(const facet of authority.facets){if(!authority.vocabularies[facet.vocabulary])diagnostics.push({severity:"error",code:"facet.vocabulary",message:`Facet ${facet.id} references unknown vocabulary ${facet.vocabulary}`});}
  return diagnostics;
}

export type ProgressionSection="foundation"|"levelled"|"reference";
export interface FilterIndexEntry {id:string;title:string;primary_rules_area:string;rules_area_order:number;minimum_level:number|null;progression_section:ProgressionSection;progression_order:number;feature_role_order:number;classifications:Record<string,string[]>;routes:Record<string,string>}
export interface FilterIndex { entities:FilterIndexEntry[] }
const progressionSectionOrder:Record<ProgressionSection,number>={foundation:0,levelled:1,reference:2};
export function compareFilterEntries(a:FilterIndexEntry,b:FilterIndexEntry):number{
  return (a.rules_area_order-b.rules_area_order)
    ||(progressionSectionOrder[a.progression_section]-progressionSectionOrder[b.progression_section])
    ||((a.minimum_level??Number.MAX_SAFE_INTEGER)-(b.minimum_level??Number.MAX_SAFE_INTEGER))
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
  return{entities:authority.entities.map(entity=>{const primaryArea=entity.presentation_metadata.primary_rules_area;const areaRoutes=routesByEntity.get(entity.id)!;const routes=Object.fromEntries([...areaRoutes].map(([area,topics])=>[area,entity.presentation_metadata.canonical_topic_by_area[area]??topics[0]! ]));return{id:entity.id,title:entity.title,primary_rules_area:primaryArea,rules_area_order:areaOrder.get(primaryArea)!,minimum_level:entity.level??null,progression_section:(entity.level===undefined?entity.progression_section!:"levelled") as ProgressionSection,progression_order:topicOrderByEntityArea.get(`${entity.id}\0${primaryArea}`)!,feature_role_order:entity.classifications.feature_role?roleOrder.get(entity.classifications.feature_role)!:Number.MAX_SAFE_INTEGER,classifications:{rules_area:[primaryArea],entity_kind:[entity.classifications.entity_kind],...(entity.classifications.feature_role?{feature_role:[entity.classifications.feature_role]}:{}),...(entity.classifications.acquisition_mode?{acquisition_mode:[entity.classifications.acquisition_mode]}:{})},routes};}).sort(compareFilterEntries)};
}

export function buildIntegrity(authority:Authority,index:FilterIndex):Record<string,unknown>{
  const checks=index.entities.map(item=>{const entity=authority.entities.find(candidate=>candidate.id===item.id)!;const canonicalAreas=item.classifications.rules_area!;return{entity_id:item.id,identity_retrieval:item.title===entity.title,canonical_area_retrieval:canonicalAreas.length===1&&canonicalAreas[0]===item.primary_rules_area,classification_vector_retrieval:Object.entries(item.classifications).every(([facet,values])=>values.every(value=>(entity.classifications as any)[facet]?.includes?.(value)||(entity.classifications as any)[facet]===value)),route_areas:Object.keys(item.routes).sort(),rules_areas:[...entity.classifications.rules_area].sort()};});
  return{version:1,entity_count:index.entities.length,all_passed:checks.every(check=>check.identity_retrieval&&check.canonical_area_retrieval&&check.classification_vector_retrieval&&JSON.stringify(check.route_areas)===JSON.stringify(check.rules_areas)),controlled_vocabularies:Object.fromEntries(Object.entries(authority.vocabularies).map(([name,values])=>[name,values.map(value=>value.id)])),identity_domain:index.entities.map(entity=>({id:entity.id,title:entity.title,primary_rules_area:entity.primary_rules_area})),checks};
}

export function summarizeDiagnostics(diagnostics:Diagnostic[]):string{return diagnostics.map(item=>`${item.severity.toUpperCase()} ${item.code}${item.path?` ${item.path}`:""}: ${item.message}`).join("\n");}

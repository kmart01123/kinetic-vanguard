import {readFile} from "node:fs/promises";
import {canonicalJson,codepointCompare,sha256} from "./canonical.js";

type JsonRecord=Record<string,unknown>;

export type CreatureCatalogDocument=JsonRecord&{
  readonly contract:JsonRecord;
  readonly provenance_id:string;
  readonly source_ruleset:string;
  readonly source_stat_block_count:number;
  readonly passive_trait_registry:JsonRecord;
  readonly creatures:readonly JsonRecord[];
};

export type CreatureRosterDocument=JsonRecord&{
  readonly contract:JsonRecord;
  readonly catalog:JsonRecord;
  readonly profiles:readonly JsonRecord[];
  readonly accounting:readonly JsonRecord[];
};

export type CreatureCatalogProvenanceDocument=JsonRecord&{
  readonly format_version:number;
  readonly provenance_id:string;
  readonly source:JsonRecord;
  readonly catalog:JsonRecord;
  readonly rosters:JsonRecord;
};

export type CreatureCatalogBundle={
  readonly catalog:CreatureCatalogDocument;
  readonly rosters:CreatureRosterDocument;
  readonly provenance:CreatureCatalogProvenanceDocument;
  readonly digests:{
    readonly catalogSha256:string;
    readonly rostersSha256:string;
    readonly provenanceSha256:string;
  };
};

export const DEFAULT_CREATURE_CATALOG_PATH="harness/data/srd_creatures.json";
export const DEFAULT_CREATURE_ROSTERS_PATH="harness/data/srd_creature_rosters.json";
export const DEFAULT_CREATURE_PROVENANCE_PATH="harness/provenance/srd-creatures.json";

const CATALOG_CONTRACT={id:"srd521_creature_catalog",version:"1.0.0"} as const;
const ROSTER_CONTRACT={id:"srd521_creature_rosters",version:"1.0.0"} as const;
const REGISTRY_CONTRACT={id:"srd521_passive_trait_registry",version:"1.0.0"} as const;
const PROVENANCE_ID="official_srd_5_2_1_creatures";
const SOURCE_RULESET="D&D SRD 5.2.1";
const ELIGIBILITY_POLICY_ID="srd521_level_cr_closed_ranges_v1";
const SOURCE_STAT_BLOCK_COUNT=330;
const BENCHMARK_LEVELS=[7,11,15,20] as const;
const BENCHMARK_LEVEL_KEYS=BENCHMARK_LEVELS.map(String);
const PROFILE_IDENTITIES=[
  {profile_id:"srd521_headline_source_diversity_v1",profile_version:"1.0.0",purpose:"bounded_source_mechanical_diversity"},
  {profile_id:"srd521_eligible_census_v1",profile_version:"1.0.0",purpose:"complete_projection_feasible_eligible_census"}
] as const;
const EXPECTED_SOURCE={
  ruleset:SOURCE_RULESET,
  official_pdf_url:"https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",
  official_pdf_sha256:"8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",
  official_pdf_bytes:6031375,
  page_count:364,
  monster_rules_pages:[254,257],
  stat_block_pages:[258,364]
} as const;
const CATALOG_KEYS=["contract","creatures","passive_trait_registry","provenance_id","source_ruleset","source_stat_block_count"];
const CREATURE_KEYS=["abilities","armor_class","challenge","classification","communication","creature_id","defenses","display_name","gear","hit_points","initiative","legendary_resistance","magic_resistance","movement","passive_perception","passive_traits","senses","skills","source","source_variant_tags"];
const CREATURE_OBJECT_FIELDS=["abilities","armor_class","challenge","classification","communication","defenses","hit_points","initiative","legendary_resistance","magic_resistance","movement","senses"];
const CREATURE_ARRAY_FIELDS=["gear","passive_traits","skills","source_variant_tags"];
const SOURCE_KEYS=["modification_notice","page","ruleset","stat_block_anchor","stat_block_order"];
const ROSTER_KEYS=["accounting","catalog","contract","eligibility_policy","exclusion_reason_ids","profiles","selection_algorithm","selection_audit"];
const PROFILE_KEYS=["entries","profile_id","profile_sha256","profile_version","purpose"];
const PROFILE_ENTRY_KEYS=["benchmark_level","creature_id","eligibility_policy_id","profile_id","profile_order","profile_version","purpose","weight"];
const ACCOUNTING_KEYS=["benchmark_level","challenge_rating","creature_id","disposition","eligibility_policy_id","projection_feasible","reason_id"];
const LEVEL_AUDIT_KEYS=["census_count","coverage","eligible_count","excluded_count","greedy_pick_trace","headline_count","major_family_audit","numeric_bucket_maps","projection_feasible_count","token_universes"];
const PROVENANCE_KEYS=["accounting","catalog","extraction","format_version","license","modifications","provenance_id","rosters","source","source_exceptions"];

function record(value:unknown,label:string):JsonRecord{
  if(value===null||typeof value!=="object"||Array.isArray(value))throw new Error(`${label} must be an object`);
  return value as JsonRecord;
}

function array(value:unknown,label:string):unknown[]{
  if(!Array.isArray(value))throw new Error(`${label} must be an array`);
  return value;
}

function exactKeys(value:JsonRecord,expected:readonly string[],label:string):void{
  const actual=Object.keys(value).sort(codepointCompare),wanted=[...expected].sort(codepointCompare);
  if(actual.length!==wanted.length||actual.some((key,index)=>key!==wanted[index]))throw new Error(`${label} keys are invalid`);
}

function trimmedString(value:unknown,label:string):string{
  if(typeof value!=="string"||value.length===0||value.trim()!==value)throw new Error(`${label} must be a non-empty trimmed string`);
  return value;
}

function integer(value:unknown,label:string):number{
  if(typeof value!=="number"||!Number.isInteger(value))throw new Error(`${label} must be an integer`);
  return value;
}

function nonNegativeInteger(value:unknown,label:string):number{
  const parsed=integer(value,label);
  if(parsed<0)throw new Error(`${label} must be non-negative`);
  return parsed;
}

function positiveInteger(value:unknown,label:string):number{
  const parsed=integer(value,label);
  if(parsed<=0)throw new Error(`${label} must be positive`);
  return parsed;
}

function digest(value:unknown,label:string):string{
  const parsed=trimmedString(value,label);
  if(!/^[0-9a-f]{64}$/.test(parsed))throw new Error(`${label} must be a lowercase SHA-256 digest`);
  return parsed;
}

function nullableString(value:unknown,label:string):string|null{
  return value===null?null:trimmedString(value,label);
}

function rational(value:unknown,label:string):JsonRecord{
  const parsed=record(value,label);
  exactKeys(parsed,["denominator","numerator"],label);
  integer(parsed.numerator,`${label}.numerator`);
  positiveInteger(parsed.denominator,`${label}.denominator`);
  return parsed;
}

function stringArray(value:unknown,label:string):string[]{
  return array(value,label).map((item,index)=>trimmedString(item,`${label}[${index}]`));
}

function contract(value:unknown,expected:{readonly id:string;readonly version:string},label:string):JsonRecord{
  const parsed=record(value,label);
  exactKeys(parsed,["id","version"],label);
  if(parsed.id!==expected.id||parsed.version!==expected.version)throw new Error(`${label} is unsupported`);
  return parsed;
}

function assertStrictlySortedUnique(values:readonly string[],label:string):void{
  for(let index=1;index<values.length;index++){
    if(codepointCompare(values[index-1]!,values[index]!)>=0)throw new Error(`${label} must be strictly codepoint-sorted and unique`);
  }
}

function assertUnique(values:readonly string[],label:string):void{
  if(new Set(values).size!==values.length)throw new Error(`${label} contains a duplicate`);
}

function parseJson(bytes:Uint8Array,label:string):unknown{
  try{return JSON.parse(Buffer.from(bytes).toString("utf8")) as unknown;}
  catch(error){throw new Error(`${label} is not valid JSON`,{cause:error});}
}

type CatalogIdentity={readonly creatureId:string;readonly page:number;readonly sourceOrder:number;readonly sourceAnchor:string;readonly challengeRating:JsonRecord};

function catalogIdentities(catalog:CreatureCatalogDocument):CatalogIdentity[]{
  return catalog.creatures.map((creature,index)=>{
    const source=record(creature.source,`catalog.creatures[${index}].source`);
    const challenge=record(creature.challenge,`catalog.creatures[${index}].challenge`);
    return {
      creatureId:creature.creature_id as string,
      page:source.page as number,
      sourceOrder:source.stat_block_order as number,
      sourceAnchor:source.stat_block_anchor as string,
      challengeRating:record(challenge.rating,`catalog.creatures[${index}].challenge.rating`)
    };
  });
}

export function validateCreatureCatalog(value:unknown):CreatureCatalogDocument{
  const catalog=record(value,"creature catalog");
  exactKeys(catalog,CATALOG_KEYS,"creature catalog");
  contract(catalog.contract,CATALOG_CONTRACT,"creature catalog.contract");
  if(catalog.provenance_id!==PROVENANCE_ID)throw new Error("creature catalog provenance identity is unsupported");
  if(catalog.source_ruleset!==SOURCE_RULESET)throw new Error("creature catalog source ruleset is unsupported");
  if(catalog.source_stat_block_count!==SOURCE_STAT_BLOCK_COUNT)throw new Error("creature catalog source stat-block count is unsupported");

  const registry=record(catalog.passive_trait_registry,"creature catalog.passive_trait_registry");
  exactKeys(registry,["definitions","id","irrelevant_reason_ids","retained_reason_ids","source_heading_count","source_occurrence_count","version"],"creature catalog.passive_trait_registry");
  if(registry.id!==REGISTRY_CONTRACT.id||registry.version!==REGISTRY_CONTRACT.version)throw new Error("creature catalog passive-trait registry is unsupported");
  positiveInteger(registry.source_heading_count,"creature catalog.passive_trait_registry.source_heading_count");
  positiveInteger(registry.source_occurrence_count,"creature catalog.passive_trait_registry.source_occurrence_count");
  for(const field of ["irrelevant_reason_ids","retained_reason_ids"] as const){
    const values=stringArray(registry[field],`creature catalog.passive_trait_registry.${field}`);
    assertStrictlySortedUnique(values,`creature catalog.passive_trait_registry.${field}`);
  }
  const definitions=array(registry.definitions,"creature catalog.passive_trait_registry.definitions");
  const traitIds=definitions.map((item,index)=>{
    const label=`creature catalog.passive_trait_registry.definitions[${index}]`,definition=record(item,label);
    exactKeys(definition,["disposition","impact_axes","reason_id","source_headings","trait_id"],label);
    const traitId=trimmedString(definition.trait_id,`${label}.trait_id`);
    if(!/^[a-z][a-z0-9_]*$/.test(traitId))throw new Error(`${label}.trait_id is not canonical`);
    const headings=stringArray(definition.source_headings,`${label}.source_headings`);
    if(headings.length===0)throw new Error(`${label}.source_headings must not be empty`);
    stringArray(definition.impact_axes,`${label}.impact_axes`);
    trimmedString(definition.disposition,`${label}.disposition`);
    nullableString(definition.reason_id,`${label}.reason_id`);
    return traitId;
  });
  assertStrictlySortedUnique(traitIds,"creature catalog passive-trait definitions");

  const creatures=array(catalog.creatures,"creature catalog.creatures");
  if(creatures.length!==SOURCE_STAT_BLOCK_COUNT)throw new Error("creature catalog creature count does not match its pinned source count");
  const creatureIds:string[]=[],sourceOrders:number[]=[],sourceAnchors:string[]=[],sourcePages:number[]=[];
  creatures.forEach((item,index)=>{
    const label=`creature catalog.creatures[${index}]`,creature=record(item,label);
    exactKeys(creature,CREATURE_KEYS,label);
    const creatureId=trimmedString(creature.creature_id,`${label}.creature_id`);
    if(!/^srd521:[a-z0-9]+(?:-[a-z0-9]+)*$/.test(creatureId))throw new Error(`${label}.creature_id is not canonical`);
    trimmedString(creature.display_name,`${label}.display_name`);
    CREATURE_OBJECT_FIELDS.forEach(field=>record(creature[field],`${label}.${field}`));
    CREATURE_ARRAY_FIELDS.forEach(field=>array(creature[field],`${label}.${field}`));
    const challenge=record(creature.challenge,`${label}.challenge`);
    rational(challenge.rating,`${label}.challenge.rating`);
    const source=record(creature.source,`${label}.source`);
    exactKeys(source,SOURCE_KEYS,`${label}.source`);
    if(source.ruleset!==SOURCE_RULESET)throw new Error(`${label}.source.ruleset is unsupported`);
    const page=positiveInteger(source.page,`${label}.source.page`),sourceOrder=positiveInteger(source.stat_block_order,`${label}.source.stat_block_order`);
    if(page<EXPECTED_SOURCE.stat_block_pages[0]||page>EXPECTED_SOURCE.stat_block_pages[1])throw new Error(`${label}.source.page is outside the pinned stat-block pages`);
    const anchor=trimmedString(source.stat_block_anchor,`${label}.source.stat_block_anchor`),expectedAnchor=`p${page}-o${String(sourceOrder).padStart(3,"0")}`;
    if(anchor!==expectedAnchor)throw new Error(`${label}.source.stat_block_anchor does not match page and source order`);
    trimmedString(source.modification_notice,`${label}.source.modification_notice`);
    creatureIds.push(creatureId);sourceOrders.push(sourceOrder);sourceAnchors.push(anchor);sourcePages.push(page);
  });
  assertStrictlySortedUnique(creatureIds,"creature catalog creature IDs");
  assertUnique(sourceAnchors,"creature catalog source identities");
  assertUnique(sourceOrders.map(String),"creature catalog source orders");
  const bySourceOrder=sourceOrders.map((sourceOrder,index)=>({sourceOrder,page:sourcePages[index]!})).sort((left,right)=>left.sourceOrder-right.sourceOrder);
  bySourceOrder.forEach((identity,index)=>{
    if(identity.sourceOrder!==index+1)throw new Error("creature catalog source orders must cover the contiguous source sequence");
    if(index>0&&identity.page<bySourceOrder[index-1]!.page)throw new Error("creature catalog source pages must be nondecreasing in source order");
  });
  return catalog as CreatureCatalogDocument;
}

function validateProfile(profileValue:unknown,identity:typeof PROFILE_IDENTITIES[number],catalogIndex:ReadonlyMap<string,CatalogIdentity>,accountingIndex:ReadonlyMap<string,JsonRecord>,index:number):JsonRecord{
  const label=`creature rosters.profiles[${index}]`,profile=record(profileValue,label);
  exactKeys(profile,PROFILE_KEYS,label);
  if(profile.profile_id!==identity.profile_id||profile.profile_version!==identity.profile_version||profile.purpose!==identity.purpose)throw new Error(`${label} identity is unsupported`);
  const declaredDigest=digest(profile.profile_sha256,`${label}.profile_sha256`),unsigned=Object.fromEntries(Object.entries(profile).filter(([key])=>key!=="profile_sha256"));
  if(declaredDigest!==sha256(canonicalJson(unsigned)))throw new Error(`${label} SHA-256 does not match its profile payload`);
  const entries=array(profile.entries,`${label}.entries`),ids:string[]=[],ordered:{level:number;page:number;sourceOrder:number;creatureId:string}[]=[];
  entries.forEach((entryValue,entryIndex)=>{
    const entryLabel=`${label}.entries[${entryIndex}]`,entry=record(entryValue,entryLabel);
    exactKeys(entry,PROFILE_ENTRY_KEYS,entryLabel);
    const creatureId=trimmedString(entry.creature_id,`${entryLabel}.creature_id`),catalogIdentity=catalogIndex.get(creatureId),accounting=accountingIndex.get(creatureId);
    if(!catalogIdentity||!accounting)throw new Error(`${entryLabel}.creature_id is absent from catalog accounting`);
    const level=positiveInteger(entry.benchmark_level,`${entryLabel}.benchmark_level`);
    if(!BENCHMARK_LEVELS.includes(level as typeof BENCHMARK_LEVELS[number]))throw new Error(`${entryLabel}.benchmark_level is unsupported`);
    if(entry.eligibility_policy_id!==ELIGIBILITY_POLICY_ID)throw new Error(`${entryLabel}.eligibility_policy_id is unsupported`);
    if(entry.profile_id!==profile.profile_id||entry.profile_version!==profile.profile_version||entry.purpose!==profile.purpose)throw new Error(`${entryLabel} does not inherit its profile identity`);
    if(positiveInteger(entry.profile_order,`${entryLabel}.profile_order`)!==entryIndex+1)throw new Error(`${entryLabel}.profile_order does not match serialized order`);
    rational(entry.weight,`${entryLabel}.weight`);
    if(accounting.benchmark_level!==level||accounting.projection_feasible!==true)throw new Error(`${entryLabel} disagrees with accounting eligibility`);
    ids.push(creatureId);ordered.push({level,page:catalogIdentity.page,sourceOrder:catalogIdentity.sourceOrder,creatureId});
  });
  assertUnique(ids,`${label} creature IDs`);
  for(let position=1;position<ordered.length;position++){
    const previous=ordered[position-1]!,current=ordered[position]!;
    const comparison=previous.level-current.level||previous.page-current.page||previous.sourceOrder-current.sourceOrder||codepointCompare(previous.creatureId,current.creatureId);
    if(comparison>=0)throw new Error(`${label}.entries must use canonical benchmark-level and source ordering`);
  }
  return profile;
}

function sameSet(actual:readonly string[],expected:readonly string[],label:string):void{
  const left=[...actual].sort(codepointCompare),right=[...expected].sort(codepointCompare);
  if(left.length!==right.length||left.some((value,index)=>value!==right[index]))throw new Error(`${label} is inconsistent with roster accounting`);
}

export function validateCreatureRosters(value:unknown,catalog:CreatureCatalogDocument,catalogBytes:string|Uint8Array):CreatureRosterDocument{
  const rosters=record(value,"creature rosters");
  exactKeys(rosters,ROSTER_KEYS,"creature rosters");
  contract(rosters.contract,ROSTER_CONTRACT,"creature rosters.contract");
  const catalogBinding=record(rosters.catalog,"creature rosters.catalog");
  exactKeys(catalogBinding,["contract_version","sha256"],"creature rosters.catalog");
  if(catalogBinding.contract_version!==CATALOG_CONTRACT.version)throw new Error("creature rosters catalog contract version is unsupported");
  if(digest(catalogBinding.sha256,"creature rosters.catalog.sha256")!==sha256(catalogBytes))throw new Error("creature rosters catalog SHA-256 does not match the catalog bytes");

  const policy=record(rosters.eligibility_policy,"creature rosters.eligibility_policy");
  exactKeys(policy,["closed_ranges","id","intentional_gaps"],"creature rosters.eligibility_policy");
  if(policy.id!==ELIGIBILITY_POLICY_ID)throw new Error("creature roster eligibility policy is unsupported");
  const ranges=record(policy.closed_ranges,"creature rosters.eligibility_policy.closed_ranges");
  exactKeys(ranges,BENCHMARK_LEVEL_KEYS,"creature rosters.eligibility_policy.closed_ranges");
  for(const level of BENCHMARK_LEVEL_KEYS){
    const range=record(ranges[level],`creature rosters.eligibility_policy.closed_ranges.${level}`);
    exactKeys(range,["maximum","minimum"],`creature rosters.eligibility_policy.closed_ranges.${level}`);
    rational(range.minimum,`creature rosters.eligibility_policy.closed_ranges.${level}.minimum`);
    rational(range.maximum,`creature rosters.eligibility_policy.closed_ranges.${level}.maximum`);
  }
  array(policy.intentional_gaps,"creature rosters.eligibility_policy.intentional_gaps").forEach((gap,index)=>rational(gap,`creature rosters.eligibility_policy.intentional_gaps[${index}]`));
  const exclusionReasonIds=stringArray(rosters.exclusion_reason_ids,"creature rosters.exclusion_reason_ids");
  assertStrictlySortedUnique(exclusionReasonIds,"creature roster exclusion reason IDs");
  const exclusionReasonSet=new Set(exclusionReasonIds);

  const identities=catalogIdentities(catalog),catalogIndex=new Map(identities.map(identity=>[identity.creatureId,identity]));
  const sourceOrderedIdentities=[...identities].sort((left,right)=>left.sourceOrder-right.sourceOrder);
  const accounting=array(rosters.accounting,"creature rosters.accounting");
  if(accounting.length!==identities.length)throw new Error("creature roster accounting must contain one row per catalog creature");
  const accountingIndex=new Map<string,JsonRecord>();
  accounting.forEach((item,index)=>{
    const label=`creature rosters.accounting[${index}]`,row=record(item,label);
    exactKeys(row,ACCOUNTING_KEYS,label);
    const creatureId=trimmedString(row.creature_id,`${label}.creature_id`),expected=sourceOrderedIdentities[index];
    if(creatureId!==expected?.creatureId)throw new Error("creature roster accounting must follow exact catalog source order");
    if(canonicalJson(rational(row.challenge_rating,`${label}.challenge_rating`))!==canonicalJson(expected.challengeRating))throw new Error(`${label}.challenge_rating disagrees with the catalog`);
    if(row.benchmark_level!==null){
      const level=positiveInteger(row.benchmark_level,`${label}.benchmark_level`);
      if(!BENCHMARK_LEVELS.includes(level as typeof BENCHMARK_LEVELS[number]))throw new Error(`${label}.benchmark_level is unsupported`);
    }
    if(row.eligibility_policy_id!==ELIGIBILITY_POLICY_ID)throw new Error(`${label}.eligibility_policy_id is unsupported`);
    if(typeof row.projection_feasible!=="boolean")throw new Error(`${label}.projection_feasible must be a boolean`);
    trimmedString(row.disposition,`${label}.disposition`);
    const reasonId=nullableString(row.reason_id,`${label}.reason_id`);
    if(reasonId!==null&&!exclusionReasonSet.has(reasonId))throw new Error(`${label}.reason_id is not declared`);
    accountingIndex.set(creatureId,row);
  });

  const profileValues=array(rosters.profiles,"creature rosters.profiles");
  if(profileValues.length!==PROFILE_IDENTITIES.length)throw new Error("creature rosters must contain the exact supported profile set");
  const profiles=profileValues.map((profile,index)=>validateProfile(profile,PROFILE_IDENTITIES[index]!,catalogIndex,accountingIndex,index));
  const headlineIds=array(profiles[0]!.entries,"headline profile entries").map(entry=>(entry as JsonRecord).creature_id as string);
  const censusIds=array(profiles[1]!.entries,"census profile entries").map(entry=>(entry as JsonRecord).creature_id as string);
  const censusIdSet=new Set(censusIds);
  if(headlineIds.some(creatureId=>!censusIdSet.has(creatureId)))throw new Error("headline profile must be a subset of the eligible census profile");
  sameSet(censusIds,accounting.filter(row=>(row as JsonRecord).benchmark_level!==null&&(row as JsonRecord).projection_feasible===true).map(row=>(row as JsonRecord).creature_id as string),"eligible census profile");
  sameSet(headlineIds,accounting.filter(row=>(row as JsonRecord).disposition==="headline_selected").map(row=>(row as JsonRecord).creature_id as string),"headline profile");

  const algorithm=record(rosters.selection_algorithm,"creature rosters.selection_algorithm");
  exactKeys(algorithm,["dimension_weight","headline_cap_per_level","id","result_blind","serialized_order","tie_break","token_weight"],"creature rosters.selection_algorithm");
  if(algorithm.id!=="srd521_source_diversity_greedy_v1")throw new Error("creature roster selection algorithm identity is unsupported");
  positiveInteger(algorithm.headline_cap_per_level,"creature rosters.selection_algorithm.headline_cap_per_level");
  rational(algorithm.dimension_weight,"creature rosters.selection_algorithm.dimension_weight");
  trimmedString(algorithm.token_weight,"creature rosters.selection_algorithm.token_weight");
  stringArray(algorithm.tie_break,"creature rosters.selection_algorithm.tie_break");
  stringArray(algorithm.serialized_order,"creature rosters.selection_algorithm.serialized_order");
  if(algorithm.result_blind!==true)throw new Error("creature roster selection algorithm must declare result_blind true");

  const audit=record(rosters.selection_audit,"creature rosters.selection_audit");
  exactKeys(audit,["levels"],"creature rosters.selection_audit");
  const auditLevels=record(audit.levels,"creature rosters.selection_audit.levels");
  exactKeys(auditLevels,BENCHMARK_LEVEL_KEYS,"creature rosters.selection_audit.levels");
  for(const level of BENCHMARK_LEVELS){
    const label=`creature rosters.selection_audit.levels.${level}`,levelAudit=record(auditLevels[String(level)],label);
    exactKeys(levelAudit,LEVEL_AUDIT_KEYS,label);
    const levelAccounting=accounting.map(row=>row as JsonRecord).filter(row=>row.benchmark_level===level);
    const expectedCounts={
      eligible_count:levelAccounting.length,
      projection_feasible_count:levelAccounting.filter(row=>row.projection_feasible===true).length,
      excluded_count:levelAccounting.filter(row=>row.projection_feasible===false).length,
      headline_count:headlineIds.filter(creatureId=>accountingIndex.get(creatureId)?.benchmark_level===level).length,
      census_count:censusIds.filter(creatureId=>accountingIndex.get(creatureId)?.benchmark_level===level).length
    };
    for(const [field,expected] of Object.entries(expectedCounts))if(nonNegativeInteger(levelAudit[field],`${label}.${field}`)!==expected)throw new Error(`${label}.${field} disagrees with accounting`);
    record(levelAudit.numeric_bucket_maps,`${label}.numeric_bucket_maps`);
    record(levelAudit.token_universes,`${label}.token_universes`);
    record(levelAudit.coverage,`${label}.coverage`);
    record(levelAudit.major_family_audit,`${label}.major_family_audit`);
    array(levelAudit.greedy_pick_trace,`${label}.greedy_pick_trace`);
  }
  return rosters as CreatureRosterDocument;
}

function validateExtraction(value:unknown):void{
  const extraction=record(value,"creature provenance.extraction");
  exactKeys(extraction,["coordinate_metadata","font_metadata","inference","ocr","parser_policy","primary_text_layer","trait_audit_sha256","trait_heading_policy","visual_source_checks"],"creature provenance.extraction");
  for(const field of ["primary_text_layer","coordinate_metadata","font_metadata"] as const){
    const label=`creature provenance.extraction.${field}`,metadata=record(extraction[field],label),expected=field==="primary_text_layer"?["options","sha256","tool","tool_version"]:["options","pages","sha256","tool","tool_version"];
    exactKeys(metadata,expected,label);
    trimmedString(metadata.tool,`${label}.tool`);trimmedString(metadata.tool_version,`${label}.tool_version`);trimmedString(metadata.options,`${label}.options`);digest(metadata.sha256,`${label}.sha256`);
    if(field!=="primary_text_layer")array(metadata.pages,`${label}.pages`).forEach((page,index)=>positiveInteger(page,`${label}.pages[${index}]`));
  }
  trimmedString(extraction.parser_policy,"creature provenance.extraction.parser_policy");
  trimmedString(extraction.trait_heading_policy,"creature provenance.extraction.trait_heading_policy");
  digest(extraction.trait_audit_sha256,"creature provenance.extraction.trait_audit_sha256");
  array(extraction.visual_source_checks,"creature provenance.extraction.visual_source_checks").forEach((page,index)=>positiveInteger(page,`creature provenance.extraction.visual_source_checks[${index}]`));
  trimmedString(extraction.inference,"creature provenance.extraction.inference");
  trimmedString(extraction.ocr,"creature provenance.extraction.ocr");
}

export function validateCreatureCatalogProvenance(value:unknown,catalog:CreatureCatalogDocument,rosters:CreatureRosterDocument,catalogBytes:string|Uint8Array,rosterBytes:string|Uint8Array):CreatureCatalogProvenanceDocument{
  const provenance=record(value,"creature provenance");
  exactKeys(provenance,PROVENANCE_KEYS,"creature provenance");
  if(provenance.format_version!==1)throw new Error("creature provenance format version is unsupported");
  if(provenance.provenance_id!==PROVENANCE_ID||catalog.provenance_id!==provenance.provenance_id)throw new Error("creature provenance identity is unsupported or unbound");
  const source=record(provenance.source,"creature provenance.source");
  exactKeys(source,Object.keys(EXPECTED_SOURCE),"creature provenance.source");
  if(canonicalJson(source)!==canonicalJson(EXPECTED_SOURCE))throw new Error("creature provenance does not identify the pinned official SRD source");

  const catalogManifest=record(provenance.catalog,"creature provenance.catalog");
  exactKeys(catalogManifest,["contract_id","contract_version","file","first_source_identity","last_source_identity","sha256","stat_block_count"],"creature provenance.catalog");
  if(catalogManifest.file!==DEFAULT_CREATURE_CATALOG_PATH||catalogManifest.contract_id!==CATALOG_CONTRACT.id||catalogManifest.contract_version!==CATALOG_CONTRACT.version)throw new Error("creature provenance catalog identity is unsupported");
  if(digest(catalogManifest.sha256,"creature provenance.catalog.sha256")!==sha256(catalogBytes))throw new Error("creature catalog SHA-256 does not match provenance");
  if(catalogManifest.stat_block_count!==catalog.source_stat_block_count)throw new Error("creature provenance catalog count disagrees with the catalog");
  const sourceOrdered=[...catalogIdentities(catalog)].sort((left,right)=>left.sourceOrder-right.sourceOrder);
  if(catalogManifest.first_source_identity!==sourceOrdered[0]?.sourceAnchor||catalogManifest.last_source_identity!==sourceOrdered.at(-1)?.sourceAnchor)throw new Error("creature provenance source identity bounds disagree with the catalog");

  const rosterManifest=record(provenance.rosters,"creature provenance.rosters");
  exactKeys(rosterManifest,["contract_id","contract_version","file","sha256"],"creature provenance.rosters");
  if(rosterManifest.file!==DEFAULT_CREATURE_ROSTERS_PATH||rosterManifest.contract_id!==ROSTER_CONTRACT.id||rosterManifest.contract_version!==ROSTER_CONTRACT.version)throw new Error("creature provenance roster identity is unsupported");
  if(digest(rosterManifest.sha256,"creature provenance.rosters.sha256")!==sha256(rosterBytes))throw new Error("creature roster SHA-256 does not match provenance");
  if(record(rosters.catalog,"creature rosters.catalog").sha256!==catalogManifest.sha256)throw new Error("creature roster catalog binding disagrees with provenance");

  validateExtraction(provenance.extraction);
  const accounting=record(provenance.accounting,"creature provenance.accounting");
  exactKeys(accounting,["alternate_lair_xp_stat_blocks","animal_stat_blocks","explicit_skill_stat_blocks","hover_stat_blocks","monsters_a_z_stat_blocks","multi_size_stat_blocks","passive_trait_occurrences","passive_trait_source_headings","qualified_defense_facts","special_sense_occurrences","static_gear_stat_blocks","swarm_stat_blocks","telepathy_stat_blocks","total_stat_blocks"],"creature provenance.accounting");
  for(const [field,fieldValue] of Object.entries(accounting)){
    if(field==="special_sense_occurrences")continue;
    nonNegativeInteger(fieldValue,`creature provenance.accounting.${field}`);
  }
  if(accounting.total_stat_blocks!==catalog.source_stat_block_count)throw new Error("creature provenance accounting total disagrees with the catalog");
  const registry=record(catalog.passive_trait_registry,"creature catalog.passive_trait_registry");
  if(accounting.passive_trait_source_headings!==registry.source_heading_count||accounting.passive_trait_occurrences!==registry.source_occurrence_count)throw new Error("creature provenance passive-trait accounting disagrees with the catalog registry");
  const senses=record(accounting.special_sense_occurrences,"creature provenance.accounting.special_sense_occurrences");
  exactKeys(senses,["blindsight","darkvision","tremorsense","truesight"],"creature provenance.accounting.special_sense_occurrences");
  Object.entries(senses).forEach(([sense,count])=>nonNegativeInteger(count,`creature provenance.accounting.special_sense_occurrences.${sense}`));

  const catalogIndex=new Map(catalogIdentities(catalog).map(identity=>[identity.creatureId,identity]));
  const exceptions=array(provenance.source_exceptions,"creature provenance.source_exceptions"),exceptionIds:string[]=[];
  exceptions.forEach((item,index)=>{
    const label=`creature provenance.source_exceptions[${index}]`,exception=record(item,label);
    exactKeys(exception,["creature_id","exception_id","field","source_page","source_value"],label);
    const creatureId=trimmedString(exception.creature_id,`${label}.creature_id`),identity=catalogIndex.get(creatureId);
    if(!identity)throw new Error(`${label}.creature_id is absent from the catalog`);
    if(positiveInteger(exception.source_page,`${label}.source_page`)!==identity.page)throw new Error(`${label}.source_page disagrees with the catalog`);
    trimmedString(exception.field,`${label}.field`);exceptionIds.push(trimmedString(exception.exception_id,`${label}.exception_id`));
    if(exception.source_value===null||typeof exception.source_value==="object")throw new Error(`${label}.source_value must be scalar`);
  });
  assertUnique(exceptionIds,"creature provenance source exception IDs");
  trimmedString(provenance.modifications,"creature provenance.modifications");
  trimmedString(provenance.license,"creature provenance.license");
  return provenance as CreatureCatalogProvenanceDocument;
}

export async function loadCreatureCatalogBundle(catalogPath=DEFAULT_CREATURE_CATALOG_PATH,rosterPath=DEFAULT_CREATURE_ROSTERS_PATH,provenancePath=DEFAULT_CREATURE_PROVENANCE_PATH):Promise<CreatureCatalogBundle>{
  const [catalogBytes,rosterBytes,provenanceBytes]=await Promise.all([readFile(catalogPath),readFile(rosterPath),readFile(provenancePath)]);
  const catalog=validateCreatureCatalog(parseJson(catalogBytes,"creature catalog"));
  const rosters=validateCreatureRosters(parseJson(rosterBytes,"creature rosters"),catalog,catalogBytes);
  const provenance=validateCreatureCatalogProvenance(parseJson(provenanceBytes,"creature provenance"),catalog,rosters,catalogBytes,rosterBytes);
  return {catalog,rosters,provenance,digests:{catalogSha256:sha256(catalogBytes),rostersSha256:sha256(rosterBytes),provenanceSha256:sha256(provenanceBytes)}};
}

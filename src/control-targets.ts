import {readFile} from "node:fs/promises";
import {canonicalJson,sha256} from "./canonical.js";

type ObjectValue=Record<string,unknown>;
const SUPPORTED_SENSES=["blindsight","tremorsense"] as const;

export const DEFAULT_CONTROL_TARGET_SUPPLEMENT="harness/data/srd_control_targets.json";
export const DEFAULT_CONTROL_TARGET_ROSTER="harness/data/srd_targets.csv";
export const DEFAULT_CONTROL_TARGET_PROVENANCE="harness/provenance/srd-control-targets.json";
const EXPECTED_SOURCE={ruleset:"D&D SRD 5.2.1",official_pdf_url:"https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",official_pdf_sha256:"8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",pages:364};
const EXPECTED_JOIN={base_fields:["Level","Target"],supplement_fields:["level","target"],match:"exact_case_sensitive",expected_rows:28};
const EXPECTED_EXTRACTION={source_location:"Each monster stat block's Speed and Senses lines on the row's source_page",fields:["walking_speed","fly_speed","swim_speed","climb_speed","burrow_speed","hover","nonvisual_senses"],ordinary_darkvision:"excluded",truesight:"excluded_as_enhanced_vision",absence:"explicit_null_movement_modes_and_empty_nonvisual_sense_arrays",inference:"none",sense_limitations:"preserve_official_material_limitation_when_present",modifications:"Selected control-relevant movement facts and only Blindsight or Tremorsense facts, normalized feet to integer fields, lower-cased sense names, and represented absence explicitly; Truesight is excluded as enhanced vision."};

function object(value:unknown,label:string):ObjectValue{
  if(value===null||typeof value!=="object"||Array.isArray(value))throw new Error(`${label} must be an object`);
  return value as ObjectValue;
}

function exactKeys(value:ObjectValue,expected:string[],label:string):void{
  const actual=Object.keys(value).sort(),canonical=[...expected].sort();
  if(actual.length!==canonical.length||actual.some((key,index)=>key!==canonical[index]))throw new Error(`${label} keys are invalid`);
}

function positiveInteger(value:unknown,label:string):number{
  if(!Number.isInteger(value)||Number(value)<=0)throw new Error(`${label} must be a positive integer`);
  return Number(value);
}

function trimmedString(value:unknown,label:string):string{
  if(typeof value!=="string"||value.length===0||value.trim()!==value)throw new Error(`${label} must be a non-empty trimmed string`);
  return value;
}

function rosterRows(csv:string):Array<{key:[number,string];sourcePage:number}>{
  const lines=csv.replace(/\r\n/g,"\n").split("\n");if(lines.at(-1)==="")lines.pop();
  const header=lines.shift()?.split(",");
  if(header?.[0]!=="Level"||header[1]!=="Target")throw new Error("SRD target roster must begin with exact Level and Target columns");
  const sourcePageIndex=header.indexOf("Source Page");if(sourcePageIndex<0)throw new Error("SRD target roster must contain Source Page");
  const rows=lines.map((line,index)=>{
    const first=line.indexOf(","),second=line.indexOf(",",first+1);
    if(first<=0||second<=first+1)throw new Error(`SRD target roster row ${index} lacks Level plus Target`);
    const columns=line.split(","),level=Number(line.slice(0,first)),target=line.slice(first+1,second);
    return {key:[positiveInteger(level,`SRD target roster row ${index}.Level`),trimmedString(target,`SRD target roster row ${index}.Target`)] as [number,string],sourcePage:positiveInteger(Number(columns[sourcePageIndex]),`SRD target roster row ${index}.Source Page`)};
  });
  const encoded=rows.map(({key:[level,target]})=>`${level}\u0000${target}`);
  if(new Set(encoded).size!==encoded.length)throw new Error("Pinned SRD target roster contains a duplicate Level plus Target key");
  return rows;
}

function validateMovement(value:unknown,label:string):void{
  const movement=object(value,label);exactKeys(movement,["walk_ft","fly_ft","swim_ft","climb_ft","burrow_ft","hover"],label);
  positiveInteger(movement.walk_ft,`${label}.walk_ft`);
  for(const field of ["fly_ft","swim_ft","climb_ft","burrow_ft"] as const)if(movement[field]!==null)positiveInteger(movement[field],`${label}.${field}`);
  if(typeof movement.hover!=="boolean")throw new Error(`${label}.hover must be a boolean`);
  if(movement.hover&&movement.fly_ft===null)throw new Error(`${label}.hover requires a fly speed`);
}

function validateSenses(value:unknown,label:string):void{
  if(!Array.isArray(value))throw new Error(`${label} must be an array`);
  const names=value.map((item,index)=>{
    const sense=object(item,`${label}[${index}]`);exactKeys(sense,["sense","range_ft","limitation"],`${label}[${index}]`);
    const name=trimmedString(sense.sense,`${label}[${index}].sense`);
    if(!(SUPPORTED_SENSES as readonly string[]).includes(name))throw new Error(`${label}[${index}].sense is unknown or unsupported: ${name}`);
    positiveInteger(sense.range_ft,`${label}[${index}].range_ft`);
    if(sense.limitation!==null)trimmedString(sense.limitation,`${label}[${index}].limitation`);
    return name;
  });
  if(new Set(names).size!==names.length)throw new Error(`${label} contains a duplicate sense`);
  const ordered=[...names].sort((left,right)=>SUPPORTED_SENSES.indexOf(left as typeof SUPPORTED_SENSES[number])-SUPPORTED_SENSES.indexOf(right as typeof SUPPORTED_SENSES[number]));
  if(names.some((name,index)=>name!==ordered[index]))throw new Error(`${label} must use canonical sense ordering`);
}

export function validateControlTargetSupplement(value:unknown,rosterCsv:string):void{
  const supplement=object(value,"control-target supplement");exactKeys(supplement,["format_version","join_key","targets"],"control-target supplement");
  if(supplement.format_version!==1)throw new Error("Unsupported control-target supplement format version");
  if(!Array.isArray(supplement.join_key)||supplement.join_key.length!==2||supplement.join_key[0]!=="level"||supplement.join_key[1]!=="target")throw new Error("Control-target supplement join_key must be exact level plus target");
  if(!Array.isArray(supplement.targets))throw new Error("control-target supplement.targets must be an array");
  const supplementRows=supplement.targets.map((item,index)=>{
    const label=`control-target supplement.targets[${index}]`,row=object(item,label);exactKeys(row,["level","target","movement","nonvisual_senses","source_page"],label);
    const level=positiveInteger(row.level,`${label}.level`),target=trimmedString(row.target,`${label}.target`);
    validateMovement(row.movement,`${label}.movement`);validateSenses(row.nonvisual_senses,`${label}.nonvisual_senses`);const sourcePage=positiveInteger(row.source_page,`${label}.source_page`);
    return {key:[level,target] as [number,string],sourcePage};
  });
  const roster=rosterRows(rosterCsv),encode=([level,target]:[number,string])=>`${level}\u0000${target}`,encoded=supplementRows.map(row=>encode(row.key));
  if(new Set(encoded).size!==encoded.length)throw new Error("Control-target supplement contains a duplicate level plus target key");
  const rosterSet=new Set(roster.map(row=>encode(row.key))),supplementSet=new Set(encoded),missing=[...rosterSet].filter(key=>!supplementSet.has(key)),extra=[...supplementSet].filter(key=>!rosterSet.has(key));
  if(missing.length||extra.length)throw new Error(`Control-target supplement join is incomplete; missing=${missing.length}, extra=${extra.length}`);
  if(encoded.some((key,index)=>key!==encode(roster[index]!.key)))throw new Error("Control-target supplement rows must follow the exact pinned roster order");
  supplementRows.forEach((row,index)=>{if(row.sourcePage!==roster[index]!.sourcePage)throw new Error(`Control-target source_page disagrees with the roster for ${encoded[index]}`);});
}

export function validateControlTargetProvenance(value:unknown,rosterBytes:string|Uint8Array,supplementBytes:string|Uint8Array):void{
  const provenance=object(value,"control-target provenance");exactKeys(provenance,["format_version","source","data_file","data_sha256","roster_file","roster_sha256","join","extraction"],"control-target provenance");
  if(provenance.format_version!==1)throw new Error("Unsupported control-target provenance format version");
  const source=object(provenance.source,"control-target provenance.source");exactKeys(source,Object.keys(EXPECTED_SOURCE),"control-target provenance.source");if(canonicalJson(source)!==canonicalJson(EXPECTED_SOURCE))throw new Error("Control-target provenance does not identify the pinned official SRD 5.2.1 PDF");
  if(provenance.data_file!==DEFAULT_CONTROL_TARGET_SUPPLEMENT||provenance.roster_file!==DEFAULT_CONTROL_TARGET_ROSTER)throw new Error("Control-target provenance file identities are unsupported");
  if(provenance.data_sha256!==sha256(supplementBytes))throw new Error("Control-target supplement SHA-256 does not match provenance");
  if(provenance.roster_sha256!==sha256(rosterBytes))throw new Error("SRD target roster SHA-256 does not match control-target provenance");
  const join=object(provenance.join,"control-target provenance.join");exactKeys(join,Object.keys(EXPECTED_JOIN),"control-target provenance.join");if(canonicalJson(join)!==canonicalJson(EXPECTED_JOIN))throw new Error("Control-target provenance join contract is unsupported");
  const extraction=object(provenance.extraction,"control-target provenance.extraction");exactKeys(extraction,Object.keys(EXPECTED_EXTRACTION),"control-target provenance.extraction");if(canonicalJson(extraction)!==canonicalJson(EXPECTED_EXTRACTION))throw new Error("Control-target provenance extraction policy is unsupported");
}

export async function loadControlTargetSupplement(supplementPath=DEFAULT_CONTROL_TARGET_SUPPLEMENT,rosterPath=DEFAULT_CONTROL_TARGET_ROSTER,provenancePath=DEFAULT_CONTROL_TARGET_PROVENANCE):Promise<unknown>{
  const [supplementBytes,rosterBytes,provenanceBytes]=await Promise.all([readFile(supplementPath),readFile(rosterPath),readFile(provenancePath)]),supplementSource=supplementBytes.toString("utf8"),rosterCsv=rosterBytes.toString("utf8");
  const supplement=JSON.parse(supplementSource) as unknown,provenance=JSON.parse(provenanceBytes.toString("utf8")) as unknown;validateControlTargetSupplement(supplement,rosterCsv);validateControlTargetProvenance(provenance,rosterBytes,supplementBytes);return supplement;
}

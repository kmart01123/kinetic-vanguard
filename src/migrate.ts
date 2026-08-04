import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import YAML from "yaml";
import { sha256, prettyCanonicalJson } from "./canonical.js";
import { writeAtomic } from "./io.js";
import type { Authority, ContentBlock, Entity, InlineNode, SourceUnit } from "./types.js";

const SOURCE = "Kinetic_Vanguard.md";
const PINNED_COMMIT = "9c8d0bfb95b23ff724537acefaacefa01bad9538";
const PARSER_VERSION = "kv-markdown-blocks/1.1.2";
const ENUMERATION_VERSION = "reviewable-block-content/1.0.1";
const LEAF_MODEL_VERSION = "1.0.0";
const utf8Decoder = new TextDecoder("utf-8", { fatal: true });
const EXAMPLE_REGIONS = [
  { titleLine:100, endLine:110 },
  { titleLine:112, endLine:122 },
  { titleLine:124, endLine:136 },
  { titleLine:138, endLine:148 }
] as const;

interface CoverageSpan { start:number; end:number; span_type:"source_unit"|"syntax_only_exclusion"; source_unit_id?:string; exclusion_id?:string; content_sha256:string; exclusion_reason?:string }
interface Inventory { source_sha256:string; parser_version:string; enumeration_algorithm_version:string; leaf_model_version:string; units:SourceUnit[] }

function makeUnit(type: string, start: number, end: number, line: number, column: number, bytes: Buffer): SourceUnit {
  const source = utf8Decoder.decode(bytes.subarray(start, end));
  const digest = sha256(source);
  return {
    id: `u_l${String(line).padStart(4,"0")}_c${String(column).padStart(3,"0")}_${type.replaceAll("-","_")}_${digest.slice(0,10)}`,
    type, spans:[{start,end}], location:{line,column}, content_sha256:digest,
    normalized_source:source.normalize("NFC"),
    inline_metadata:{link_destinations:[...source.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)].map((match) => match[1]!).sort()}
  };
}

function enumerate(bytes: Buffer): { coverage: CoverageSpan[]; inventory: Inventory; unitByLine: Map<number, SourceUnit[]> } {
  const coverage: CoverageSpan[] = [];
  const units: SourceUnit[] = [];
  const unitByLine = new Map<number, SourceUnit[]>();
  let offset = 0;
  let exclusion = 0;
  const addExclusion = (start:number,end:number,reason:string) => {
    if (end <= start) return;
    coverage.push({start,end,span_type:"syntax_only_exclusion",exclusion_id:`x_${String(++exclusion).padStart(5,"0")}`,content_sha256:sha256(bytes.subarray(start,end)),exclusion_reason:reason});
  };
  const addUnit = (type:string,start:number,end:number,line:number,column:number) => {
    if (end <= start) return;
    const unit = makeUnit(type,start,end,line,column,bytes);
    units.push(unit); coverage.push({start,end,span_type:"source_unit",source_unit_id:unit.id,content_sha256:unit.content_sha256});
    const existing = unitByLine.get(line) ?? []; existing.push(unit); unitByLine.set(line,existing);
  };
  const text = utf8Decoder.decode(bytes);
  const byteOffset = (value:string, characterOffset:number) => Buffer.byteLength(value.slice(0,characterOffset),"utf8");
  const lines = text.match(/.*(?:\n|$)/g)!.filter((line) => line.length > 0);
  for (let index=0; index<lines.length; index++) {
    const rawWithNewline = lines[index]!;
    const hasNewline = rawWithNewline.endsWith("\n");
    const raw = hasNewline ? rawWithNewline.slice(0,-1) : rawWithNewline;
    const start = offset; const end = start + Buffer.byteLength(raw); const line = index + 1;
    if (raw.trim() === "") addExclusion(start,end,"inter-unit whitespace");
    else if (/^#{1,6} /.test(raw)) {
      const prefix = raw.match(/^#{1,6} /)![0]; const contentStart = start + Buffer.byteLength(prefix);
      addExclusion(start,contentStart,"structural Markdown heading delimiter");
      addUnit("heading",contentStart,end,line,prefix.length+1);
    } else if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(raw)) {
      addExclusion(start,end,"structural Markdown table alignment row");
    } else if (raw.startsWith("|") && raw.endsWith("|")) {
      let cursor = 0;
      for (const match of raw.matchAll(/\|([^|]*)/g)) {
        const pipe = match.index; const pipeByte = byteOffset(raw,pipe);
        addExclusion(start+cursor,start+pipeByte+1,"structural Markdown table delimiter");
        const segment = match[1] ?? ""; const segmentStart = pipe+1;
        const segmentStartByte = byteOffset(raw,segmentStart); const segmentEndByte = byteOffset(raw,segmentStart+segment.length);
        if (segment.trim() === "") {
          addExclusion(start+segmentStartByte,start+segmentEndByte,"structural Markdown empty table cell and padding");
        } else {
          const left = segment.match(/^\s*/)![0].length; const right = segment.match(/\s*$/)![0].length;
          const cellStart = byteOffset(raw,segmentStart+left); const cellEnd = byteOffset(raw,segmentStart+segment.length-right);
          addExclusion(start+segmentStartByte,start+cellStart,"structural Markdown table padding");
          addUnit("table_cell",start+cellStart,start+cellEnd,line,segmentStart+left+1);
          addExclusion(start+cellEnd,start+segmentEndByte,"structural Markdown table padding");
        }
        cursor = segmentEndByte;
      }
      addExclusion(start+cursor,end,"structural Markdown table delimiter");
    } else {
      const prefix = raw.match(/^(?:>\s?|[-*+]\s+|\d+[.)]\s+)/)?.[0] ?? "";
      if (prefix) addExclusion(start,start+Buffer.byteLength(prefix),"structural Markdown block delimiter");
      const type = raw.startsWith(">") ? "blockquote_paragraph" : /^[-*+]\s+/.test(raw) ? "list_item" : /^\d+[.)]\s+/.test(raw) ? "ordered_list_item" : "paragraph";
      addUnit(type,start+Buffer.byteLength(prefix),end,line,prefix.length+1);
    }
    if (hasNewline) addExclusion(end,end+1,"line ending");
    offset += Buffer.byteLength(rawWithNewline);
  }
  coverage.sort((a,b)=>a.start-b.start);
  let cursor=0;
  for (const span of coverage) { if (span.start !== cursor) throw new Error(`Coverage gap/overlap at byte ${cursor}; next span ${span.start}-${span.end} (${span.span_type})`); cursor=span.end; }
  if (cursor !== bytes.length) throw new Error(`Coverage ends at ${cursor}, expected ${bytes.length}`);
  return {coverage,inventory:{source_sha256:sha256(bytes),parser_version:PARSER_VERSION,enumeration_algorithm_version:ENUMERATION_VERSION,leaf_model_version:LEAF_MODEL_VERSION,units},unitByLine};
}

function cleanInline(source: string): string {
  return source
    .replace(/^\s*>\s?/, "").replace(/^\s*(?:[-*+] |\d+[.)] )/, "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)")
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, "$1 ($2)")
    .replace(/\\([\[\]*_`])/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replaceAll("Advanced Training I: Deflection Screen","Deflection Screen")
    .replaceAll("Advanced Training II: Phase Step","Phase Step")
    .replaceAll("Advanced Training II (Phase Step)","Phase Step")
    .trim();
}

function formattedInlines(source:string,unit:SourceUnit):InlineNode[]{
  const value=source.replace(/^\s*>\s?/,"").replace(/^\s*(?:[-*+] |\d+[.)] )/,"").trim();
  const nodes:InlineNode[]=[];let cursor=0;
  const append=(type:InlineNode["type"],text:string)=>{if(text)nodes.push({type,text,source_unit_id:unit.id});};
  for(const match of value.matchAll(/\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g)){
    append("text",value.slice(cursor,match.index));
    append(match[1]!==undefined?"strong":match[2]!==undefined?"emphasis":"code",match[1]??match[2]??match[3]??"");
    cursor=match.index+match[0].length;
  }
  append("text",value.slice(cursor));return nodes;
}

function slug(value:string):string {
  const result = value.normalize("NFKD").toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"");
  return result || "untitled";
}

function unitForLine(unitByLine:Map<number,SourceUnit[]>, line:number):SourceUnit | undefined { return unitByLine.get(line)?.[0]; }

function blocksForLines(lines:string[], start:number, end:number, unitByLine:Map<number,SourceUnit[]>, excluded = new Set<number>(), preserveFormatting=false, blockquotesAsParagraphs=false):ContentBlock[] {
  const blocks:ContentBlock[]=[];
  let line=start;
  const inlines = (text:string, unit:SourceUnit):InlineNode[] => preserveFormatting?formattedInlines(text,unit):[{type:"text",text:cleanInline(text),source_unit_id:unit.id}];
  while(line<=end){
    if(excluded.has(line)||!lines[line-1]?.trim()||/^#{1,6} /.test(lines[line-1]!)){line++;continue;}
    const raw=lines[line-1]!;
    const example=EXAMPLE_REGIONS.find(region=>region.titleLine===line);
    if(example){
      const titleUnit=unitForLine(unitByLine,line);if(!titleUnit)throw new Error(`Example title at line ${line} has no source unit`);
      const title=cleanInline(raw).replace(/^Example\s+—\s+/,"");
      const body=blocksForLines(lines,line+1,example.endLine,unitByLine,excluded,true,true);
      blocks.push({type:"example",title:[{type:"text",text:title,source_unit_id:titleUnit.id}],body});line=example.endLine+1;continue;
    }
    if(raw.startsWith("|")&&raw.endsWith("|")){
      const tableLines:number[]=[]; let scan=line;
      while(scan<=end && lines[scan-1]?.startsWith("|")){ if(!/^\|(?:\s*:?-+:?\s*\|)+$/.test(lines[scan-1]!)) tableLines.push(scan); scan++; }
      const toCells=(lineNumber:number)=> (unitByLine.get(lineNumber)??[]).map((unit)=>inlines(unit.normalized_source,unit));
      if(tableLines.length>1) blocks.push({type:"table",headers:toCells(tableLines[0]!),rows:tableLines.slice(1).map(toCells)});
      line=scan;continue;
    }
    if(/^(?:[-*+] |\d+[.)] )/.test(raw)){
      const ordered=/^\d+[.)] /.test(raw); const items:InlineNode[][]=[]; let scan=line;
      while(scan<=end && (ordered?/^\d+[.)] /.test(lines[scan-1]!):/^[-*+] /.test(lines[scan-1]!))){const unit=unitForLine(unitByLine,scan);if(unit)items.push(inlines(lines[scan-1]!,unit));scan++;}
      if(items.length)blocks.push({type:"list",style:ordered?"ordered":"unordered",items});line=scan;continue;
    }
    const unit=unitForLine(unitByLine,line);
    if(unit){const text=cleanInline(raw);if(text)blocks.push(raw.startsWith(">")&&!blockquotesAsParagraphs?{type:"note",kind:"note",inlines:inlines(raw,unit)}:{type:"paragraph",inlines:inlines(raw,unit)});}
    line++;
  }
  return blocks;
}

function headerMetadata(header:string):{level?:number;psi_cost?:number;activation?:string;requires_concentration?:boolean}{
  const level=header.match(/(?:^|\s)(\d+)(?:rd|th|st|nd)(?: Level)?(?:\s|$)/i)?.[1];
  const cost=header.match(/(?:^|\s)(\d+) Psi(?:\s|$)/i)?.[1];
  const lower=header.toLowerCase();
  const activation=lower.includes("manifested strike hit")?"on_hit":lower.includes("bonus action")?"bonus_action":lower.includes("reaction")?"reaction":lower.includes("action")?"action":lower.includes("passive")?"passive":undefined;
  const requires_concentration=lower.includes("concentration");
  return { ...(level?{level:Number(level)}:{}), ...(cost?{psi_cost:Number(cost)}:{}), ...(activation?{activation}:{}), ...(requires_concentration?{requires_concentration:true}:{}) };
}

function featureRole(header:string):string { const lower=header.toLowerCase(); return lower.includes("manifested strike hit")?"rider":lower.includes("passive")?"passive":"standalone"; }

function createEntity(id:string,title:string,area:string,kind:string,content:ContentBlock[],originIds:string[],extra:Partial<Entity>={}):Entity{
  return {
    id,title,publishable:true,kind,content,
    classifications:{rules_area:[area],entity_kind:kind,...(kind==="feature"?{feature_role:extra.classifications?.feature_role??"standalone"}:{}),...(extra.classifications?.acquisition_mode?{acquisition_mode:extra.classifications.acquisition_mode}:{})},
    presentation_metadata:{primary_rules_area:area,canonical_topic_by_area:{}},origins:[{source_unit_ids:[...new Set(originIds)].sort()}],
    ...Object.fromEntries(Object.entries(extra).filter(([key])=>!["classifications","presentation_metadata","origins"].includes(key)))
  } as Entity;
}

function originIds(content:ContentBlock[], titleUnit?:SourceUnit):string[]{
  const ids:string[]=[]; if(titleUnit)ids.push(titleUnit.id);
  const visit=(nodes:InlineNode[]|undefined)=>nodes?.forEach(node=>ids.push(node.source_unit_id));
  const visitBlock=(block:ContentBlock)=>{visit(block.inlines);visit(block.title);visit(block.heading);block.items?.forEach(visit);block.headers?.forEach(visit);block.rows?.forEach(row=>row.forEach(visit));block.body?.forEach(visitBlock);};
  content.forEach(visitBlock);
  return ids;
}

function buildAuthority(lines:string[],unitByLine:Map<number,SourceUnit[]>):Authority{
  const entities:Entity[]=[];
  const addRegion=(id:string,title:string,area:string,start:number,end:number,excluded=new Set<number>(),kind="system")=>{const content=blocksForLines(lines,start,end,unitByLine,excluded);entities.push(createEntity(id,title,area,kind,content,originIds(content,unitForLine(unitByLine,start))));};
  addRegion("how_to_play","How to Play This Subclass","common_features",29,45,new Set([34]));entities.at(-1)!.progression_section="foundation";
  addRegion("common_overload","Overload","common_features",47,149,undefined,"feature");
  const overload=entities.at(-1)!;
  overload.level=3;overload.classifications.feature_role="standalone";
  for(const [sourceUnitId,tier] of [["u_l0052_c003_blockquote_paragraph_fce5d5e549",1],["u_l0054_c003_blockquote_paragraph_bdcb2ee9c3",2]] as const){const index=overload.content.findIndex(block=>block.inlines?.some(node=>node.source_unit_id===sourceUnitId));const original=overload.content[index]!;const text=original.inlines![0]!.text!.replace(/^T\d Overload:\s*/,"");overload.content[index]={type:"tier",tier,heading:[{type:"text",text:"Overload",source_unit_id:sourceUnitId}],body:[{type:"paragraph",inlines:[{type:"text",text,source_unit_id:sourceUnitId}]}]};}
  addRegion("subclass_feature_reference","Subclass Feature Reference","common_features",273,322,undefined,"progression");entities.at(-1)!.progression_section="reference";
  const parseFeatures=(area:string,start:number,end:number,idPrefix="")=>{
    const headers:Array<{line:number;title:string;meta:string}>=[];
    for(let line=start;line<=end;line++){const match=lines[line-1]?.match(/^\*\*(.+?)\*\* · \*(.+)\*$/);if(match)headers.push({line,title:cleanInline(match[1]!),meta:cleanInline(match[2]!)});}
    headers.forEach((header,index)=>{
      const sliceEnd=(headers[index+1]?.line??end+1)-1;
      const content=blocksForLines(lines,header.line+1,sliceEnd,unitByLine);
      const metadata=headerMetadata(header.meta); const role=featureRole(header.meta);
      if(!metadata.requires_concentration&&/\brequires? concentration\b/i.test(JSON.stringify(content)))metadata.requires_concentration=true;
      const baseTitle=header.title.replace(/^Advanced Training [IVX]+:\s*/,"");
      const acquisition=area==="advanced_training"?(["Deflection Screen","Phase Step"].includes(baseTitle)?"granted":"selectable"):undefined;
      if(acquisition==="selectable"&&metadata.level===undefined)metadata.level=baseTitle==="Overload Mastery II"?18:15;
      const id=`${idPrefix}${slug(baseTitle)}`;
      if(id==="common_overload"){
        const existingIndex=entities.findIndex(entity=>entity.id===id);const existing=entities.splice(existingIndex,1)[0]!;
        const base=content.map(block=>{for(const inline of block.inlines??[])if(inline.text)inline.text=inline.text.replace(/ See [^.]+\(Section 01\) for full rules\.$/,"");return block;});
        existing.content=[...base,...existing.content];existing.origins[0]!.source_unit_ids.unshift(...originIds(base,unitForLine(unitByLine,header.line)));entities.push(existing);return;
      }
      entities.push(createEntity(id,baseTitle,area,"feature",content,originIds(content,unitForLine(unitByLine,header.line)),{...metadata,classifications:{rules_area:[area],entity_kind:"feature",feature_role:role,...(acquisition?{acquisition_mode:acquisition}:{})}}));
    });
  };
  parseFeatures("common_features",150,237,"common_");
  addRegion("advanced_training_progression","Advanced Training Progression","common_features",238,271);entities.at(-1)!.progression_section="reference";
  parseFeatures("cryokinesis",327,372);
  parseFeatures("pyrokinesis",373,418);
  parseFeatures("psychokinesis",419,469);
  parseFeatures("electrokinesis",470,517);
  parseFeatures("advanced_training",518,607,"advanced_");
  const areaDefinitions=[
    ["common_features","Common Features"],["advanced_training","Advanced Training"],["cryokinesis","Cryokinesis"],
    ["pyrokinesis","Pyrokinesis"],["psychokinesis","Psychokinesis"],["electrokinesis","Electrokinesis"]
  ] as const;
  const categories=areaDefinitions.map(([id,label],areaOrder)=>{
    const areaEntities=entities.filter(entity=>entity.classifications.rules_area.includes(id));
    const topics=areaEntities.map((entity,order)=>({id:`${id}_${entity.id}_topic`,title:entity.title,entity_ids:[entity.id],order}));
    return {id,label,order:areaOrder,default_topic_id:topics[0]!.id,topics};
  });
  return {
    schema_version:"1.0.0",rules_version:"13.0.1",
    metadata:{title:"Kinetic Vanguard",attribution:"Created by NixNinja in collaboration with AI assistants. Special thanks to various muses, great and small.",license:"Original Kinetic Vanguard material may be used, copied, modified, and redistributed for non-commercial purposes with credit to NixNinja. Commercial use requires prior written permission. SRD-derived rules text and references are separately governed by the Creative Commons Attribution 4.0 International License.",compatibility:"Fighter subclass rules reference"},
    vocabularies:{
      rules_areas:areaDefinitions.map(([id,label],order)=>({id,label,order})),
      entity_kinds:[{id:"feature",label:"Feature",order:0},{id:"system",label:"System",order:1},{id:"progression",label:"Progression",order:2}],
      feature_roles:[{id:"rider",label:"Rider",order:0},{id:"standalone",label:"Standalone",order:1},{id:"passive",label:"Passive",order:2}],
      acquisition_modes:[{id:"granted",label:"Granted",order:0},{id:"selectable",label:"Selectable",order:1}]
    },
    facets:[
      {id:"rules_area",label:"Rules area",cardinality:"multi",requiredness:"always",applicability:{kind:"all"},order:0,vocabulary:"rules_areas"},
      {id:"entity_kind",label:"Entity kind",cardinality:"single",requiredness:"always",applicability:{kind:"all"},order:1,vocabulary:"entity_kinds"},
      {id:"feature_role",label:"Feature role",cardinality:"single",requiredness:"applicable",applicability:{kind:"entity_kind",values:["feature"]},order:2,vocabulary:"feature_roles"},
      {id:"acquisition_mode",label:"Acquisition mode",cardinality:"single",requiredness:"applicable",applicability:{kind:"rules_area",values:["advanced_training"]},order:3,vocabulary:"acquisition_modes"}
    ],entities,navigation:{default_category_id:"common_features",categories},
    audits:[{id:"source_migration_provisional",assertion:"All current entity origins trace to the pinned master; human dispositions and attestations remain required.",subject_ids:entities.map(entity=>entity.id)}]
  };
}

async function main(){
  const {values}=parseArgs({options:{force:{type:"boolean",default:false}}});
  const bytes=await readFile(SOURCE); const {coverage,inventory,unitByLine}=enumerate(bytes);
  const lines=utf8Decoder.decode(bytes).split("\n");
  const authority=buildAuthority(lines,unitByLine);
  const sourceCoverage={source_sha256:inventory.source_sha256,parser_version:PARSER_VERSION,enumeration_algorithm_version:ENUMERATION_VERSION,leaf_model_version:LEAF_MODEL_VERSION,total_byte_count:bytes.length,covered_byte_count:coverage.reduce((sum,span)=>sum+span.end-span.start,0),gap_count:0,overlap_count:0,spans:coverage};
  const ledger={format_version:"1.0.0",source_sha256:inventory.source_sha256,inventory_sha256:sha256(prettyCanonicalJson(inventory)),entries:inventory.units.map(unit=>({ledger_entry_id:`ledger_${unit.id}`,source_unit_id:unit.id,workflow_state:"pending_review",disposition:null,destination_entity_ids:[],reviewer:null,review_method:null}))};
  const coverageBytes=prettyCanonicalJson(sourceCoverage),inventoryBytes=prettyCanonicalJson(inventory),ledgerBytes=prettyCanonicalJson(ledger);
  let commit=PINNED_COMMIT; try{execFileSync("git",["cat-file","-e",`${PINNED_COMMIT}:${SOURCE}`],{stdio:"ignore"});}catch{commit=execFileSync("git",["rev-parse","HEAD"],{encoding:"utf8"}).trim();}
  const manifest={format_version:"1.0.0",migration_source_filename:SOURCE,migration_source_sha256:inventory.source_sha256,repository_commit:commit,parser_version:PARSER_VERSION,source_unit_enumeration_algorithm_version:ENUMERATION_VERSION,source_coverage:{path:"migration/source-coverage.json",sha256:sha256(coverageBytes)},source_unit_inventory:{path:"migration/source-units.json",sha256:sha256(inventoryBytes)},disposition_ledger:{path:"migration/disposition-ledger.json",format_version:"1.0.0",sha256:sha256(ledgerBytes)},migration_acceptance:null,reviewers:[]};
  await writeAtomic("migration/source-coverage.json",coverageBytes);await writeAtomic("migration/source-units.json",inventoryBytes);await writeAtomic("migration/disposition-ledger.json",ledgerBytes);await writeAtomic("migration/manifest.json",prettyCanonicalJson(manifest));
  const yaml=YAML.stringify(authority,{indent:2,lineWidth:0,sortMapEntries:true});
  await writeAtomic("KineticVanguard.yaml",yaml);
  process.stdout.write(`Enumerated ${inventory.units.length} source units across ${bytes.length} bytes and wrote ${authority.entities.length} provisional entities.\n`);
  if(!values.force)process.stdout.write("Migration dispositions remain pending_review; release builds will fail closed.\n");
}

await main();

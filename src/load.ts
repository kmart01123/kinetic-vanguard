import { readFile } from "node:fs/promises";
import Ajv2020Module from "ajv/dist/2020.js";
import addFormatsModule from "ajv-formats";
import YAML, { isAlias, isMap, isNode, isPair, visit } from "yaml";
import type { Authority, Diagnostic } from "./types.js";
import { projectCalculatorMechanics,projectHarnessMechanics } from "./mechanics.js";

export interface LoadedAuthority { authority: Authority; sourceBytes: Buffer; diagnostics: Diagnostic[] }

interface MechanicsProjectionReference {entity_id:string;derived_from:"entity_mechanics"}
const isMechanicsProjectionReference=(value:unknown):value is MechanicsProjectionReference=>typeof value==="object"&&value!==null&&(value as Record<string,unknown>).derived_from==="entity_mechanics"&&typeof (value as Record<string,unknown>).entity_id==="string";

function materializeMechanicsProjections(authority:Authority,diagnostics:Diagnostic[]):void{
  const entityById=new Map(authority.entities.map(entity=>[entity.id,entity]));
  authority.calculator.features=(authority.calculator.features as unknown[]).map((source,index)=>{
    if(!isMechanicsProjectionReference(source)){
      const entity=typeof source==="object"&&source!==null?entityById.get(String((source as Record<string,unknown>).entity_id)):undefined;
      if(entity?.mechanics)diagnostics.push({severity:"error",code:"mechanics.calculator_legacy_source",message:`${entity.id} Calculator mechanics must be derived from entity_mechanics`,path:`/calculator/features/${index}`});
      return source as Authority["calculator"]["features"][number];
    }
    const entity=entityById.get(source.entity_id);
    if(!entity?.mechanics){diagnostics.push({severity:"error",code:"mechanics.calculator_reference",message:`${source.entity_id} does not provide entity mechanics for its Calculator projection`,path:`/calculator/features/${index}`});return source as unknown as Authority["calculator"]["features"][number];}
    try{return projectCalculatorMechanics(entity) as Authority["calculator"]["features"][number];}
    catch(error){diagnostics.push({severity:"error",code:"mechanics.calculator_projection",message:`${source.entity_id} Calculator projection failed: ${error instanceof Error?error.message:String(error)}`,path:`/calculator/features/${index}`});return source as unknown as Authority["calculator"]["features"][number];}
  });
  authority.calculator.harness_mechanics.feature_rules=(authority.calculator.harness_mechanics.feature_rules as unknown[]).map((source,index)=>{
    if(!isMechanicsProjectionReference(source)){
      const entity=typeof source==="object"&&source!==null?entityById.get(String((source as Record<string,unknown>).entity_id)):undefined;
      if(entity?.mechanics)diagnostics.push({severity:"error",code:"mechanics.harness_legacy_source",message:`${entity.id} harness mechanics must be derived from entity_mechanics`,path:`/calculator/harness_mechanics/feature_rules/${index}`});
      return source as Authority["calculator"]["harness_mechanics"]["feature_rules"][number];
    }
    const entity=entityById.get(source.entity_id);
    if(!entity?.mechanics){diagnostics.push({severity:"error",code:"mechanics.harness_reference",message:`${source.entity_id} does not provide entity mechanics for its harness projection`,path:`/calculator/harness_mechanics/feature_rules/${index}`});return source as unknown as Authority["calculator"]["harness_mechanics"]["feature_rules"][number];}
    try{
      const projection=projectHarnessMechanics(entity);
      if(projection)return projection;
      diagnostics.push({severity:"error",code:"mechanics.harness_projection",message:`${source.entity_id} entity mechanics do not produce a harness projection`,path:`/calculator/harness_mechanics/feature_rules/${index}`});
    }catch(error){diagnostics.push({severity:"error",code:"mechanics.harness_projection",message:`${source.entity_id} harness projection failed: ${error instanceof Error?error.message:String(error)}`,path:`/calculator/harness_mechanics/feature_rules/${index}`});}
    return source as unknown as Authority["calculator"]["harness_mechanics"]["feature_rules"][number];
  });
}

export async function loadAuthority(authorityPath="KineticVanguard.yaml",schemaPath="schema/KineticVanguard.schema.json"):Promise<LoadedAuthority>{
  const sourceBytes=await readFile(authorityPath); const diagnostics:Diagnostic[]=[];
  try{new TextDecoder("utf-8",{fatal:true}).decode(sourceBytes);}catch{diagnostics.push({severity:"error",code:"yaml.utf8",message:"Authority must be valid UTF-8",path:authorityPath});}
  const source=sourceBytes.toString("utf8");
  const document=YAML.parseDocument(source,{version:"1.2",uniqueKeys:true,strict:true,merge:false});
  for(const error of document.errors)diagnostics.push({severity:"error",code:"yaml.parse",message:error.message,path:authorityPath});
  visit(document,(key,node)=>{
    if(isAlias(node))diagnostics.push({severity:"error",code:"yaml.alias",message:"YAML aliases are prohibited",path:String(key)});
    if(isNode(node)&&node.anchor)diagnostics.push({severity:"error",code:"yaml.anchor",message:"YAML anchors are prohibited",path:String(key)});
    if(isNode(node)&&node.tag&&node.tag!=="tag:yaml.org,2002:map"&&node.tag!=="tag:yaml.org,2002:seq"&&node.tag!=="tag:yaml.org,2002:str"&&node.tag!=="tag:yaml.org,2002:int"&&node.tag!=="tag:yaml.org,2002:bool"&&node.tag!=="tag:yaml.org,2002:null")diagnostics.push({severity:"error",code:"yaml.tag",message:`Custom YAML tag ${node.tag} is prohibited`,path:String(key)});
    if(isMap(node))for(const item of node.items)if(isPair(item)&&String(item.key)==="<<")diagnostics.push({severity:"error",code:"yaml.merge",message:"YAML merge keys are prohibited",path:String(key)});
  });
  const authority=document.toJS({maxAliasCount:0}) as Authority;
  const schema=JSON.parse(await readFile(schemaPath,"utf8"));
  const Ajv2020=((Ajv2020Module as any).default??Ajv2020Module) as new(options:any)=>any;
  const addFormats=((addFormatsModule as any).default??addFormatsModule) as (ajv:any)=>void;
  const ajv=new Ajv2020({allErrors:true,strict:true});addFormats(ajv);const validate=ajv.compile(schema);
  if(!validate(authority))for(const error of validate.errors??[])diagnostics.push({severity:"error",code:"schema.invalid",message:`${error.instancePath||"/"} ${error.message??"is invalid"}`,path:error.instancePath||"/"});
  if(!diagnostics.some(diagnostic=>diagnostic.severity==="error"))materializeMechanicsProjections(authority,diagnostics);
  return{authority,sourceBytes,diagnostics};
}

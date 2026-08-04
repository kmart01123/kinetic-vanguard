import { readFile } from "node:fs/promises";
import Ajv2020Module from "ajv/dist/2020.js";
import addFormatsModule from "ajv-formats";
import YAML, { isAlias, isMap, isNode, isPair, visit } from "yaml";
import type { Authority, Diagnostic } from "./types.js";

export interface LoadedAuthority { authority: Authority; sourceBytes: Buffer; diagnostics: Diagnostic[] }

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
  return{authority,sourceBytes,diagnostics};
}

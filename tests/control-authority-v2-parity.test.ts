import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import Ajv2020Module from "ajv/dist/2020.js";
import addFormatsModule from "ajv-formats";
import {validateControlAuthorityV2} from "../src/control-authority-v2.js";
import {loadAuthority} from "../src/load.js";

type PathSegment=string|number;
type Target={kind:"authority"}|{kind:"model";effect_id:string}|{kind:"mastery";mastery_id:string};
type Operation=
  |{op:"set";path:PathSegment[];value:unknown}
  |{op:"delete";path:PathSegment[]}
  |{op:"append";path:PathSegment[];value:unknown}
  |{op:"remove_index";path:PathSegment[];index:number}
  |{op:"reverse";path:PathSegment[]};
interface ParityCase{id:string;target:Target;expected_valid:boolean;operations:Operation[];diagnostic?:string}
interface ParityCorpus{version:number;description:string;cases:ParityCase[]}

function decodeSpecialNumbers(value:unknown):unknown{
  if(Array.isArray(value))return value.map(decodeSpecialNumbers);
  if(value===null||typeof value!=="object")return value;
  const candidate=value as Record<string,unknown>;
  if(Object.keys(candidate).length===1&&typeof candidate.special_number==="string"){
    if(candidate.special_number==="nan")return Number.NaN;
    if(candidate.special_number==="positive_infinity")return Number.POSITIVE_INFINITY;
    if(candidate.special_number==="negative_infinity")return Number.NEGATIVE_INFINITY;
    throw new Error("Unknown special_number sentinel: "+candidate.special_number);
  }
  return Object.fromEntries(Object.entries(candidate).map(([key,child])=>[key,decodeSpecialNumbers(child)]));
}

function atPath(root:any,path:PathSegment[],caseId:string):any{
  let current=root;
  for(const segment of path){
    assert.ok(current!==null&&typeof current==="object",caseId+": path crosses a scalar at "+String(segment));
    assert.ok(segment in current,caseId+": missing path segment "+String(segment));
    current=current[segment];
  }
  return current;
}

function targetFor(authority:any,target:Target,caseId:string):any{
  const root=authority.calculator.harness_mechanics.control_authority_v2;
  if(target.kind==="authority")return root;
  if(target.kind==="mastery"){
    const matches=root.masteries.filter((item:any)=>item.mastery_id===target.mastery_id);
    assert.equal(matches.length,1,caseId+": mastery target must resolve exactly once");
    return matches[0];
  }
  const matches=root.ledger.filter((row:any)=>row.disposition==="modeled"&&row.model.effect_id===target.effect_id);
  assert.equal(matches.length,1,caseId+": model target must resolve exactly once");
  return matches[0].model;
}

function applyOperation(target:any,operation:Operation,caseId:string):void{
  if(operation.op==="append"){
    const destination=atPath(target,operation.path,caseId);
    assert.ok(Array.isArray(destination),caseId+": append target must be an array");
    destination.push(decodeSpecialNumbers(operation.value));
    return;
  }
  if(operation.op==="remove_index"){
    const destination=atPath(target,operation.path,caseId);
    assert.ok(Array.isArray(destination),caseId+": remove_index target must be an array");
    assert.ok(Number.isInteger(operation.index)&&operation.index>=0&&operation.index<destination.length,caseId+": remove_index is out of bounds");
    destination.splice(operation.index,1);
    return;
  }
  if(operation.op==="reverse"){
    const destination=atPath(target,operation.path,caseId);
    assert.ok(Array.isArray(destination),caseId+": reverse target must be an array");
    destination.reverse();
    return;
  }
  assert.ok(operation.path.length>0,caseId+": set/delete path must not be empty");
  const parent=atPath(target,operation.path.slice(0,-1),caseId),key=operation.path.at(-1)!;
  assert.ok(parent!==null&&typeof parent==="object",caseId+": operation parent must be an object or array");
  if(operation.op==="delete"){
    assert.ok(key in parent,caseId+": delete target must exist");
    delete parent[key];
  }else parent[key]=decodeSpecialNumbers(operation.value);
}

test("shared control-authority-v2 mutation corpus has TypeScript acceptance parity",async t=>{
  const [{authority},corpusSource,schemaSource]=await Promise.all([loadAuthority(),readFile("tests/fixtures/control-authority-v2-parity.json","utf8"),readFile("schema/KineticVanguard.schema.json","utf8")]);
  const corpus=JSON.parse(corpusSource) as ParityCorpus;
  const Ajv2020=((Ajv2020Module as any).default??Ajv2020Module) as new(options:any)=>any,addFormats=((addFormatsModule as any).default??addFormatsModule) as (ajv:any)=>void;
  const ajv=new Ajv2020({allErrors:true,strict:true});addFormats(ajv);
  const validateSchema=ajv.compile(JSON.parse(schemaSource));
  assert.equal(corpus.version,1);
  assert.ok(corpus.description.includes("v1 is never an oracle"));
  assert.equal(new Set(corpus.cases.map(item=>item.id)).size,corpus.cases.length);
  for(const parityCase of corpus.cases)await t.test(parityCase.id,()=>{
    const candidate=structuredClone(authority) as any,target=targetFor(candidate,parityCase.target,parityCase.id);
    for(const operation of parityCase.operations)applyOperation(target,operation,parityCase.id);
    const schemaValid=Boolean(validateSchema(candidate)),diagnostics=validateControlAuthorityV2(candidate);
    const valid=schemaValid&&!diagnostics.some(item=>item.severity==="error");
    const schemaSummary=(validateSchema.errors??[]).map((item:any)=>"schema "+(item.instancePath||"/")+" "+String(item.message??"invalid")).join("; ");
    assert.equal(valid,parityCase.expected_valid,parityCase.id+": "+[schemaSummary,...diagnostics.map(item=>item.code+" "+item.path)].filter(Boolean).join("; "));
    if(!parityCase.expected_valid&&parityCase.diagnostic)assert.ok(diagnostics.some(item=>item.code===parityCase.diagnostic),parityCase.id+": expected "+parityCase.diagnostic+", got "+diagnostics.map(item=>item.code).join(", "));
  });
});

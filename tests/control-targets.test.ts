import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import {loadControlTargetSupplement,validateControlTargetProvenance,validateControlTargetSupplement} from "../src/control-targets.js";

async function fixture():Promise<{supplement:any;supplementSource:string;roster:string;provenance:any}>{
  const [supplementSource,roster,provenanceSource]=await Promise.all([readFile("harness/data/srd_control_targets.json","utf8"),readFile("harness/data/srd_targets.csv","utf8"),readFile("harness/provenance/srd-control-targets.json","utf8")]);
  return {supplement:JSON.parse(supplementSource),supplementSource,roster,provenance:JSON.parse(provenanceSource)};
}

test("control-target supplement joins all 28 exact roster keys",async()=>{
  const {supplement,roster}=await fixture();assert.doesNotThrow(()=>validateControlTargetSupplement(supplement,roster));
  const loaded=await loadControlTargetSupplement() as any;assert.equal(loaded.targets.length,28);
  assert.deepEqual(loaded.targets.filter((row:any)=>row.movement.hover).map((row:any)=>row.target),["Air Elemental","Deva","Solar"]);
});

test("control-target join rejects missing, duplicate, and reordered rows",async()=>{
  const {supplement,roster}=await fixture(),reject=(mutate:(value:any)=>void)=>{const value=structuredClone(supplement);mutate(value);assert.throws(()=>validateControlTargetSupplement(value,roster));};
  reject(value=>value.targets.pop());
  reject(value=>value.targets.push(structuredClone(value.targets[0])));
  reject(value=>{[value.targets[0],value.targets[1]]=[value.targets[1],value.targets[0]];});
});

test("control-target movement, hover, and senses are fail closed",async()=>{
  const {supplement,roster}=await fixture(),reject=(mutate:(value:any)=>void,pattern:RegExp)=>{const value=structuredClone(supplement);mutate(value);assert.throws(()=>validateControlTargetSupplement(value,roster),pattern);};
  reject(value=>{value.targets[0].movement.walk_ft="10";},/positive integer/);
  reject(value=>{value.targets[0].movement.teleport_ft=30;},/keys are invalid/);
  reject(value=>{value.targets[1].movement.hover=true;},/hover requires a fly speed/);
  reject(value=>{value.targets[0].nonvisual_senses.push({sense:"darkvision",range_ft:60,limitation:null});},/unknown or unsupported/);
});

test("control-target pages, provenance policy, and both input hashes are fail closed",async()=>{
  const {supplement,supplementSource,roster,provenance}=await fixture();
  assert.doesNotThrow(()=>validateControlTargetProvenance(provenance,roster,supplementSource));
  const changedSupplement=structuredClone(supplement);changedSupplement.targets[0].source_page=999;
  assert.throws(()=>validateControlTargetSupplement(changedSupplement,roster),/source_page disagrees/);
  const reject=(mutate:(value:any)=>void,pattern:RegExp)=>{const value=structuredClone(provenance);mutate(value);assert.throws(()=>validateControlTargetProvenance(value,roster,supplementSource),pattern);};
  reject(value=>{value.source.pages=363;},/pinned official SRD/);
  reject(value=>{value.join.expected_rows=27;},/join contract/);
  reject(value=>{value.extraction.inference="allowed";},/extraction policy/);
  reject(value=>{value.data_sha256="0".repeat(64);},/supplement SHA-256/);
  reject(value=>{value.roster_sha256="0".repeat(64);},/roster SHA-256/);
});

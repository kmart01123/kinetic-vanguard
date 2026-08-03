import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeBuild } from "./build.js";
import { sha256 } from "./canonical.js";

const first=await mkdtemp(join(tmpdir(),"kv-build-a-"));const second=await mkdtemp(join(tmpdir(),"kv-build-b-"));
try{
  const a=await executeBuild("prototype",first);const b=await executeBuild("prototype",second);
  const files=["effective-ledger.json","filtered-search-integrity.json","coverage-ledger.json","KineticVanguard.prototype.html","build-manifest.json"];
  for(const file of files){const [left,right]=await Promise.all([readFile(join(first,file)),readFile(join(second,file))]);if(!left.equals(right))throw new Error(`Determinism failure: ${file} differs (${sha256(left)} != ${sha256(right)})`);}
  process.stdout.write(`Determinism verified for ${files.length} staged prototype artifacts.\n`);
}finally{await rm(first,{recursive:true,force:true});await rm(second,{recursive:true,force:true});}

import { mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import ts from "typescript";
import { sha256 } from "./canonical.js";
import { writeAtomic } from "./io.js";
import { loadAuthority } from "./load.js";
import { renderHtml } from "./render.js";
import { buildNameIndex, buildNameIndexIntegrity, summarizeDiagnostics, validateSemantics } from "./validate.js";
import type { Diagnostic } from "./types.js";

export type BuildProfile="prototype"|"release";

const buildModes={
  prototype:{releaseStatus:"prototype",filename:"KineticVanguard.prototype.html"},
  release:{releaseStatus:"release",filename:"KineticVanguard.html"}
} as const satisfies Record<BuildProfile,{releaseStatus:BuildProfile;filename:string}>;

async function json(path:string):Promise<any>{return JSON.parse(await readFile(path,"utf8"));}

export async function executeBuild(profileName:BuildProfile,outputRoot="artifacts",authorityPath="KineticVanguard.yaml") {
  const profile=buildModes[profileName];if(!profile)throw new Error(`Unknown build profile ${profileName}`);
  const loaded=await loadAuthority(authorityPath);const diagnostics:Diagnostic[]=[...loaded.diagnostics];
  if(!loaded.diagnostics.some(item=>item.severity==="error"))diagnostics.push(...validateSemantics(loaded.authority));
  if(profileName==="release"&&process.env.KV_RELEASE_APPROVED!=="1")diagnostics.push({severity:"error",code:"release.approval_required",message:"Release generation requires explicit KV_RELEASE_APPROVED=1 authorization"});
  const errors=diagnostics.filter(item=>item.severity==="error");if(errors.length)throw new Error(`Build blocked:\n${summarizeDiagnostics(diagnostics)}`);
  const nameIndex=buildNameIndex(loaded.authority);const integrity=buildNameIndexIntegrity(loaded.authority,nameIndex);if(!integrity.all_passed)throw new Error("Generated Name-navigation integrity checks failed");
  const [ui,derived,policy]=await Promise.all(["ui/approved-ui-text.json","ui/derived-output-registry.json","ui/navigation-interaction-policy.json"].map(json));
  const runtimeTypeScript=await readFile("src/runtime.ts","utf8");
  const runtimeSource=ts.transpileModule(runtimeTypeScript,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,removeComments:true}}).outputText.replace(/^export\s+/m,"");
  if(/\bexport\b/.test(runtimeSource))throw new Error("Browser runtime transpilation left an export declaration");
  const html=renderHtml({authority:loaded.authority,ui,derived,policy,nameIndex,runtimeSource,releaseStatus:profile.releaseStatus,authorityHash:sha256(loaded.sourceBytes)});
  const htmlPath=resolve(outputRoot,profile.filename);await mkdir(resolve(outputRoot),{recursive:true});await writeAtomic(htmlPath,html);
  return{htmlPath,diagnostics};
}

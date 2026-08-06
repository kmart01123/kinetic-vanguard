import { execFileSync } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import YAML from "yaml";
import ts from "typescript";
import { hashFile, prettyCanonicalJson, sha256 } from "./canonical.js";
import { writeAtomic } from "./io.js";
import { loadAuthority } from "./load.js";
import { renderHtml } from "./render.js";
import { buildFilterIndex, buildIntegrity, summarizeDiagnostics, validateSemantics } from "./validate.js";
import type { Diagnostic } from "./types.js";

export type BuildProfile="prototype"|"release";
interface InputDefinition{path:string;role:string}

async function json(path:string):Promise<any>{return JSON.parse(await readFile(path,"utf8"));}
async function jsonc(path:string):Promise<any>{const parsed=ts.parseConfigFileTextToJson(path,await readFile(path,"utf8"));if(parsed.error)throw new Error(`Invalid JSONC in ${path}`);return parsed.config;}
function commit():string{try{return execFileSync("git",["rev-parse","HEAD"],{encoding:"utf8"}).trim();}catch{return "unavailable";}}

export async function executeBuild(profileName:BuildProfile,outputRoot="artifacts",authorityPath="KineticVanguard.yaml") {
  const profiles=await json("build/profiles.json");const profile=profiles.profiles[profileName];if(!profile)throw new Error(`Unknown build profile ${profileName}`);
  const packageJson=await json("package.json");const inputsManifest=await json("build/inputs.json");const inputs=inputsManifest.inputs as InputDefinition[];
  const declaredInputs=[];for(const input of inputs){const path=input.role==="rules_authority"?authorityPath:input.path;declaredInputs.push({path,role:input.role,sha256:await hashFile(path)});}
  const evidencePolicy=await json("review/content-evidence-policy.json");const evidenceRegistry=await json("review/content-evidence-policy-registry.json");const evidencePolicyHash=await hashFile("review/content-evidence-policy.json");
  const policyBindings=evidenceRegistry.bindings.filter((binding:any)=>binding.policy_version===evidencePolicy.policy_version);
  if(policyBindings.length!==1||policyBindings[0].policy_sha256!==evidencePolicyHash)throw new Error("Content-evidence policy registry does not contain exactly one current version/hash binding");
  const loaded=await loadAuthority(authorityPath);const diagnostics:Diagnostic[]=[...loaded.diagnostics];
  if(!loaded.diagnostics.some(item=>item.severity==="error"))diagnostics.push(...validateSemantics(loaded.authority));
  if(profileName==="release"){
    if(process.env.KV_RELEASE_APPROVED!=="1")diagnostics.push({severity:"error",code:"release.approval_required",message:"Release generation requires explicit KV_RELEASE_APPROVED=1 authorization"});
    if(policyBindings[0].status!=="accepted")diagnostics.push({severity:"error",code:"evidence.policy_unaccepted",message:"Content-evidence policy has no accepted registry binding"});
    const correctness=YAML.parse(await readFile("tests/filtered-search-correctness.yaml","utf8"));if(correctness.review_status!=="accepted")diagnostics.push({severity:"error",code:"filter.correctness_unreviewed",message:"Filtered-search correctness corpus lacks accepted maintainer review"});
  }
  const errors=diagnostics.filter(item=>item.severity==="error");if(errors.length)throw new Error(`Build blocked:\n${summarizeDiagnostics(diagnostics)}`);
  const filterIndex=buildFilterIndex(loaded.authority);const integrity=buildIntegrity(loaded.authority,filterIndex);if(!integrity.all_passed)throw new Error("Generated filtered-search integrity checks failed");
  const [ui,derived,policy]=await Promise.all(["ui/approved-ui-text.json","ui/derived-output-registry.json","ui/filter-interaction-policy.json"].map(json));
  const runtimeTypeScript=await readFile("src/runtime.ts","utf8");
  const runtimeSource=ts.transpileModule(runtimeTypeScript,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,removeComments:true}}).outputText.replace(/^export\s+/m,"");
  if(/\bexport\b/.test(runtimeSource))throw new Error("Browser runtime transpilation left an export declaration");
  const html=renderHtml({authority:loaded.authority,ui,derived,policy,filterIndex,runtimeSource,applicationVersion:packageJson.version,releaseStatus:profile.release_status,authorityHash:sha256(loaded.sourceBytes)});
  const artifactPrefix=resolve(outputRoot);await mkdir(artifactPrefix,{recursive:true});
  const integrityPath=resolve(artifactPrefix,"filtered-search-integrity.json"),coveragePath=resolve(artifactPrefix,"coverage-ledger.json");
  const htmlPath=resolve(outputRoot,profileName==="prototype"?"KineticVanguard.prototype.html":"KineticVanguard.html");
  const onboarding=loaded.authority.onboarding;
  const onboardingLinks=[...onboarding.primary_paths,...onboarding.disciplines.cards,...onboarding.basic_turn.destinations,...onboarding.build_checklist.items,...onboarding.glossary.entries,...onboarding.next_destinations.items];
  const onboardingCoverage={authority_path:`${authorityPath}#/onboarding`,onboarding_id:onboarding.id,section_ids:[onboarding.disciplines.id,onboarding.basic_turn.id,onboarding.build_checklist.id,onboarding.glossary.id,onboarding.next_destinations.id],destination_ids:onboardingLinks.map(item=>item.id)};
  const coverage={version:3,authority_path:authorityPath,entity_count:loaded.authority.entities.length,entities:loaded.authority.entities.map(entity=>({entity_id:entity.id,content_block_count:entity.content.length,destinations:loaded.authority.navigation.categories.flatMap(category=>category.topics.filter(topic=>topic.entity_ids.includes(entity.id)).map(topic=>({category_id:category.id,topic_id:topic.id})))})),onboarding:onboardingCoverage,diagnostics};
  const integrityBytes=prettyCanonicalJson(integrity),coverageBytes=prettyCanonicalJson(coverage);
  await Promise.all([writeAtomic(integrityPath,integrityBytes),writeAtomic(coveragePath,coverageBytes),writeAtomic(htmlPath,html)]);
  const artifactHashes={filtered_search_integrity:sha256(integrityBytes),coverage_ledger:sha256(coverageBytes),html:sha256(html)};
  const devcontainer=await jsonc(".devcontainer/devcontainer.json");const devcontainerLock=await json(".devcontainer/devcontainer-lock.json");
  const manifest={manifest_version:"1.0.0",build_identity:{release_status:profile.release_status,rules_version:loaded.authority.rules_version,schema_version:loaded.authority.schema_version,application_version:packageJson.version,repository_commit:commit(),build_profile:profileName,build_profile_sha256:await hashFile("build/profiles.json"),canonical_rules_authority:authorityPath,authority_sha256:sha256(loaded.sourceBytes),node_version:process.version,package_manager:packageJson.packageManager,toolchain:{typescript:packageJson.devDependencies.typescript,ajv:packageJson.dependencies.ajv,yaml:packageJson.dependencies.yaml,jsdom:packageJson.devDependencies.jsdom},timezone:"UTC",locale:"C",newline_policy:"LF",encoding_policy:"UTF-8",environment_specification:{path:".devcontainer/devcontainer.json",sha256:await hashFile(".devcontainer/devcontainer.json"),base_image:devcontainer.image,resolved_base_image_digest:null},environment_lock:{path:".devcontainer/devcontainer-lock.json",sha256:await hashFile(".devcontainer/devcontainer-lock.json"),features:devcontainerLock.features}},input_manifest_sha256:await hashFile("build/inputs.json"),declared_inputs:declaredInputs,generated_artifacts:artifactHashes,diagnostics_summary:{errors:0,warnings:diagnostics.filter(item=>item.severity==="warning").length}};
  const manifestPath=resolve(artifactPrefix,"build-manifest.json");await writeAtomic(manifestPath,prettyCanonicalJson(manifest));
  return{manifest,manifestPath,htmlPath,diagnostics,artifactHashes};
}

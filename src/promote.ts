import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import Ajv2020Module from "ajv/dist/2020.js";
import addFormatsModule from "ajv-formats";
import { sha256 } from "./canonical.js";
import { replaceDirectoryAtomically, writeAtomic } from "./io.js";

const manifestPath="artifacts/build-manifest.json",htmlPath="artifacts/KineticVanguard.html",evidencePath="artifacts/release-evidence.json";
const legalAssetPaths=["LICENSE.md","LICENSE-CODE","LICENSE-CONTENT","NOTICE.md"] as const;
const [manifestBytes,html,evidenceBytes,schemaBytes,legalAssetBytes]=await Promise.all([
  readFile(manifestPath),
  readFile(htmlPath,"utf8"),
  readFile(evidencePath),
  readFile("release/release-evidence-schema.json"),
  Promise.all(legalAssetPaths.map(path=>readFile(path)))
] as const);
const manifest=JSON.parse(manifestBytes.toString("utf8")),evidence=JSON.parse(evidenceBytes.toString("utf8")),schema=JSON.parse(schemaBytes.toString("utf8"));
const Ajv2020=((Ajv2020Module as any).default??Ajv2020Module) as new(options:any)=>any;const addFormats=((addFormatsModule as any).default??addFormatsModule) as (ajv:any)=>void;const ajv=new Ajv2020({allErrors:true,strict:true});addFormats(ajv);
if(!ajv.validate(schema,evidence))throw new Error(`Release evidence is invalid: ${ajv.errorsText()}`);
if(manifest.build_identity.release_status!=="release")throw new Error("Refusing to promote a non-release build");
if(evidence.decision!=="approved")throw new Error("Release evidence decision is not approved");
if(evidence.build_manifest_sha256!==sha256(manifestBytes))throw new Error("Release evidence references a different build manifest");
if(manifest.generated_artifacts.html!==sha256(html))throw new Error("Staged HTML differs from the verified manifest");
if(html.includes('<p class="prototype"')||!html.includes('"release_status":"release"'))throw new Error("Staged publication has an invalid release identity");
for(const marker of ["Copyright © 2026 NixNinja","Changes have been made to the SRD 5.2.1 material","Section 5 of CC-BY-4.0","BSD-3-Clause"])if(!html.includes(marker))throw new Error(`Staged publication lacks required legal marker: ${marker}`);
const declaredInputs=new Map((manifest.declared_inputs as Array<{path:string;sha256:string}>).map(input=>[input.path,input.sha256]));
for(const [index,path] of legalAssetPaths.entries())if(declaredInputs.get(path)!==sha256(legalAssetBytes[index]!))throw new Error(`Legal asset differs from the verified manifest: ${path}`);
const temporary=await mkdtemp(resolve("deployable.stage-"));
await Promise.all([
  writeAtomic(resolve(temporary,"KineticVanguard.html"),html),
  ...legalAssetPaths.map((path,index)=>writeAtomic(resolve(temporary,path),legalAssetBytes[index]!))
]);
const inventory=(await readdir(temporary)).sort(),expected=["KineticVanguard.html",...legalAssetPaths].sort();
if(JSON.stringify(inventory)!==JSON.stringify(expected))throw new Error("Fresh deployable directory does not contain exactly the publication and required legal assets");
await replaceDirectoryAtomically(temporary,resolve("deployable"));
process.stdout.write(`Promoted ${manifest.generated_artifacts.html} with ${legalAssetPaths.length} legal assets to deployable/\n`);

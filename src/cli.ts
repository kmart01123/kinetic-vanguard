import { parseArgs } from "node:util";
import { executeBuild, type BuildProfile } from "./build.js";
import { loadAuthority } from "./load.js";
import { summarizeDiagnostics, validateSemantics } from "./validate.js";

const command=process.argv[2]??"validate";const {values}=parseArgs({args:process.argv.slice(3),options:{profile:{type:"string",default:"prototype"}}});
if(command==="validate"){const loaded=await loadAuthority();const diagnostics=[...loaded.diagnostics,...validateSemantics(loaded.authority)];if(diagnostics.length)process.stdout.write(`${summarizeDiagnostics(diagnostics)}\n`);if(diagnostics.some(item=>item.severity==="error"))process.exitCode=1;else process.stdout.write(`Validated ${loaded.authority.entities.length} YAML-authored entities.\n`);}
else if(command==="build"){const result=await executeBuild(values.profile as BuildProfile);for(const diagnostic of result.diagnostics)process.stdout.write(`${diagnostic.severity.toUpperCase()} ${diagnostic.code}: ${diagnostic.message}\n`);process.stdout.write(`Wrote ${result.htmlPath}\n`);}
else throw new Error(`Unknown command: ${command}`);

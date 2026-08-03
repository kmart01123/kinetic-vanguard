import { parseArgs } from "node:util";
import { executeBuild, type BuildProfile } from "./build.js";
import { loadAuthority } from "./load.js";
import { summarizeDiagnostics, validateMigration, validateSemantics } from "./validate.js";

const command=process.argv[2]??"validate";const {values}=parseArgs({args:process.argv.slice(3),options:{profile:{type:"string",default:"prototype"}}});
if(command==="validate"){const loaded=await loadAuthority();const migration=await validateMigration(false);const diagnostics=[...loaded.diagnostics,...migration.diagnostics,...validateSemantics(loaded.authority,migration.state,false)];if(diagnostics.length)process.stdout.write(`${summarizeDiagnostics(diagnostics)}\n`);if(diagnostics.some(item=>item.severity==="error"))process.exitCode=1;else process.stdout.write(`Validated ${loaded.authority.entities.length} entities; prototype-only migration warnings remain.\n`);}
else if(command==="build"){const result=await executeBuild(values.profile as BuildProfile);for(const diagnostic of result.diagnostics)process.stdout.write(`${diagnostic.severity.toUpperCase()} ${diagnostic.code}: ${diagnostic.message}\n`);process.stdout.write(`Wrote ${result.htmlPath}\nWrote ${result.manifestPath}\n`);}
else throw new Error(`Unknown command: ${command}`);

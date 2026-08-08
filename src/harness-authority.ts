import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { codepointCompare,sha256 } from "./canonical.js";
import { loadAuthority } from "./load.js";
import { summarizeDiagnostics,validateSemantics } from "./validate.js";
import type { Authority,CalculatorLevelBand,ControlAuthorityV2,DamageHarnessFeatureRule } from "./types.js";

export interface DamageHarnessProjection {
  projection_version:"1.0.0";
  authority_path:string;
  authority_sha256:string;
  rules_version:string;
  schema_version:string;
  supported_level_range:{minimum:number;maximum:number};
  progressions:{proficiency_bonus:CalculatorLevelBand[];psi_points:CalculatorLevelBand[];psionic_focus:CalculatorLevelBand[];manifested_strike_die:CalculatorLevelBand[];tier_minimum_levels:Authority["calculator"]["tier_minimum_levels"]};
  core:Pick<Authority["calculator"]["harness_mechanics"],"action_economy"|"manifested_strike"|"overload">;
  disciplines:Authority["calculator"]["harness_mechanics"]["disciplines"];
  features:Array<DamageHarnessFeatureRule&{minimum_level:number;psi_cost:number;activation:string;damage_delivery:string|null;damage_tiers:Authority["calculator"]["features"][number]["tiers"];selectable_advanced_training:boolean}>;
}

export interface ControlAuthorityProjectionV2 {
  projection_version:"2.0.0";
  authority_path:string;
  authority_sha256:string;
  rules_version:string;
  schema_version:string;
  supported_level_range:{minimum:number;maximum:number};
  control_authority:ControlAuthorityV2;
  coverage:{total:number;modeled:number;excluded_by_profile:number;unsupported_error:number;benchmark_ready:boolean};
}

export async function createDamageHarnessProjection(authorityPath="KineticVanguard.yaml"):Promise<DamageHarnessProjection>{
  const loaded=await loadAuthority(authorityPath),diagnostics=[...loaded.diagnostics];
  if(!diagnostics.some(item=>item.severity==="error"))diagnostics.push(...validateSemantics(loaded.authority));
  if(diagnostics.some(item=>item.severity==="error"))throw new Error(`Damage authority projection blocked:\n${summarizeDiagnostics(diagnostics)}`);
  const authority=loaded.authority,calculator=authority.calculator,harness=calculator.harness_mechanics;
  const entities=new Map(authority.entities.map(entity=>[entity.id,entity]));
  const damageFeatures=new Map(calculator.features.map(feature=>[feature.entity_id,feature]));
  const features=harness.feature_rules.map(rule=>{
    const entity=entities.get(rule.entity_id);if(!entity||entity.level===undefined||entity.psi_cost===undefined)throw new Error(`Damage authority feature ${rule.entity_id} lacks canonical entity availability or Psi cost`);
    const damage=damageFeatures.get(rule.entity_id);
    return {...structuredClone(rule),minimum_level:entity.level,psi_cost:entity.psi_cost,activation:entity.activation??"passive",damage_delivery:damage?.delivery??null,damage_tiers:structuredClone(damage?.tiers??[]),selectable_advanced_training:entity.classifications.rules_area.includes("advanced_training")&&entity.classifications.acquisition_mode==="selectable"};
  });
  return {
    projection_version:"1.0.0",authority_path:resolve(authorityPath),authority_sha256:sha256(loaded.sourceBytes),rules_version:authority.rules_version,schema_version:authority.schema_version,
    supported_level_range:{minimum:calculator.fighter_level_minimum,maximum:calculator.fighter_level_maximum},
    progressions:{proficiency_bonus:structuredClone(calculator.proficiency_bonus_bands),psi_points:structuredClone(calculator.psi_point_bands),psionic_focus:structuredClone(calculator.psionic_focus_bands),manifested_strike_die:structuredClone(calculator.manifested_strike_die_bands),tier_minimum_levels:structuredClone(calculator.tier_minimum_levels)},
    core:{action_economy:structuredClone(harness.action_economy),manifested_strike:structuredClone(harness.manifested_strike),overload:structuredClone(harness.overload)},disciplines:structuredClone(harness.disciplines),features
  };
}

export async function createControlAuthorityProjectionV2(authorityPath="KineticVanguard.yaml"):Promise<ControlAuthorityProjectionV2>{
  const loaded=await loadAuthority(authorityPath),diagnostics=[...loaded.diagnostics];
  if(!diagnostics.some(item=>item.severity==="error"))diagnostics.push(...validateSemantics(loaded.authority));
  if(diagnostics.some(item=>item.severity==="error"))throw new Error(`Control authority v2 projection blocked:\n${summarizeDiagnostics(diagnostics)}`);
  const authority=loaded.authority,calculator=authority.calculator;
  const controlAuthority=structuredClone(calculator.harness_mechanics.control_authority_v2);
  if(controlAuthority.contract_version!=="2.0.0")throw new Error(`Unsupported control authority contract version: ${String(controlAuthority.contract_version)}`);
  controlAuthority.ledger.sort((left,right)=>codepointCompare(left.entity_id,right.entity_id)||(left.tier-right.tier));
  const modeled=controlAuthority.ledger.filter(item=>item.disposition==="modeled").length;
  const excludedByProfile=controlAuthority.ledger.filter(item=>item.disposition==="excluded_by_profile").length;
  const unsupportedError=controlAuthority.ledger.filter(item=>item.disposition==="unsupported_error").length;
  return {
    projection_version:"2.0.0",
    authority_path:resolve(authorityPath),
    authority_sha256:sha256(loaded.sourceBytes),
    rules_version:authority.rules_version,
    schema_version:authority.schema_version,
    supported_level_range:{minimum:calculator.fighter_level_minimum,maximum:calculator.fighter_level_maximum},
    control_authority:controlAuthority,
    coverage:{total:controlAuthority.ledger.length,modeled,excluded_by_profile:excludedByProfile,unsupported_error:unsupportedError,benchmark_ready:unsupportedError===0}
  };
}

function option(args:string[],name:string):string|undefined{const index=args.indexOf(name);if(index<0)return undefined;const value=args[index+1];if(!value||value.startsWith("--"))throw new Error(`${name} requires a value`);return value;}

async function main():Promise<void>{
  const args=process.argv.slice(2),authorityPath=option(args,"--authority")??"KineticVanguard.yaml",projectionVersion=option(args,"--projection-version")??"1.0.0";
  if(projectionVersion!=="1.0.0"&&projectionVersion!=="2.0.0")throw new Error(`Unsupported projection version: ${projectionVersion}`);
  const projection=projectionVersion==="2.0.0"?await createControlAuthorityProjectionV2(authorityPath):await createDamageHarnessProjection(authorityPath);
  process.stdout.write(JSON.stringify(projection,null,args.includes("--pretty")?2:undefined)+"\n");
}

if(import.meta.url===pathToFileURL(process.argv[1]??"").href)main().catch(error=>{process.stderr.write(`${error instanceof Error?error.message:String(error)}\n`);process.exitCode=1;});

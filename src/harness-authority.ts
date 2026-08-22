import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { sha256 } from "./canonical.js";
import { loadAuthority } from "./load.js";
import { summarizeDiagnostics,validateSemantics } from "./validate.js";
import type { Authority,CalculatorLevelBand,HarnessFeatureRule } from "./types.js";

export interface HarnessProjection {
  projection_version:"1.2.0";
  authority_path:string;
  authority_sha256:string;
  rules_version:string;
  schema_version:string;
  supported_level_range:{minimum:number;maximum:number};
  progressions:{proficiency_bonus:CalculatorLevelBand[];psi_points:CalculatorLevelBand[];psionic_focus:CalculatorLevelBand[];manifested_strike_die:CalculatorLevelBand[];tier_minimum_levels:Authority["calculator"]["tier_minimum_levels"]};
  core:Pick<Authority["calculator"]["harness_mechanics"],"action_economy"|"manifested_strike"|"overload"|"psionic_apex">;
  disciplines:Authority["calculator"]["harness_mechanics"]["disciplines"];
  features:Array<HarnessFeatureRule&{title:string;minimum_level:number;psi_cost:number;activation:string;damage_delivery:string|null;damage_tiers:NonNullable<Authority["calculator"]["features"][number]["tiers"]>;advanced_training:boolean;selectable_advanced_training:boolean}>;
}

export async function createHarnessProjection(authorityPath="KineticVanguard.yaml"):Promise<HarnessProjection>{
  const loaded=await loadAuthority(authorityPath),diagnostics=[...loaded.diagnostics];
  if(!diagnostics.some(item=>item.severity==="error"))diagnostics.push(...validateSemantics(loaded.authority));
  if(diagnostics.some(item=>item.severity==="error"))throw new Error(`Harness authority projection blocked:\n${summarizeDiagnostics(diagnostics)}`);
  const authority=loaded.authority,calculator=authority.calculator,harness=calculator.harness_mechanics;
  const entities=new Map(authority.entities.map(entity=>[entity.id,entity]));
  const damageFeatures=new Map(calculator.features.map(feature=>[feature.entity_id,feature]));
  const features=harness.feature_rules.map(rule=>{
    const entity=entities.get(rule.entity_id);if(!entity||entity.level===undefined||entity.psi_cost===undefined)throw new Error(`Harness feature ${rule.entity_id} lacks canonical entity availability or Psi cost`);
    const damage=damageFeatures.get(rule.entity_id);
    const advancedTraining=entity.classifications.rules_area.includes("advanced_training");
    return {...structuredClone(rule),title:entity.title,minimum_level:entity.level,psi_cost:entity.psi_cost,activation:entity.activation??"passive",damage_delivery:damage?.delivery??null,damage_tiers:structuredClone(damage?.tiers??[]),advanced_training:advancedTraining,selectable_advanced_training:advancedTraining&&entity.classifications.acquisition_mode==="selectable"};
  });
  return {
    projection_version:"1.2.0",authority_path:resolve(authorityPath),authority_sha256:sha256(loaded.sourceBytes),rules_version:authority.rules_version,schema_version:authority.schema_version,
    supported_level_range:{minimum:calculator.fighter_level_minimum,maximum:calculator.fighter_level_maximum},
    progressions:{proficiency_bonus:structuredClone(calculator.proficiency_bonus_bands),psi_points:structuredClone(calculator.psi_point_bands),psionic_focus:structuredClone(calculator.psionic_focus_bands),manifested_strike_die:structuredClone(calculator.manifested_strike_die_bands),tier_minimum_levels:structuredClone(calculator.tier_minimum_levels)},
    core:{action_economy:structuredClone(harness.action_economy),manifested_strike:structuredClone(harness.manifested_strike),overload:structuredClone(harness.overload),psionic_apex:structuredClone(harness.psionic_apex)},disciplines:structuredClone(harness.disciplines),features
  };
}

function option(args:string[],name:string):string|undefined{const index=args.indexOf(name);if(index<0)return undefined;const value=args[index+1];if(!value||value.startsWith("--"))throw new Error(`${name} requires a value`);return value;}

async function main():Promise<void>{
  const args=process.argv.slice(2),authorityPath=option(args,"--authority")??"KineticVanguard.yaml";
  const projection=await createHarnessProjection(authorityPath);
  process.stdout.write(JSON.stringify(projection,null,args.includes("--pretty")?2:undefined)+"\n");
}

if(import.meta.url===pathToFileURL(process.argv[1]??"").href)main().catch(error=>{process.stderr.write(`${error instanceof Error?error.message:String(error)}\n`);process.exitCode=1;});

import { projectCalculatorMechanics,projectHarnessMechanics } from "./mechanics.js";
import type { Authority,CalculatorProjection,EntitySystemMechanics,SystemMechanicsField } from "./types.js";

export const systemMechanicsFields=["proficiency_bonus_bands","psi_point_bands","psionic_focus_bands","manifested_strike_die_bands","tier_minimum_levels","action_economy","manifested_strike","overload","psionic_apex","disciplines"] as const satisfies readonly SystemMechanicsField[];

export function systemMechanicsOwners(authority:Authority):Map<SystemMechanicsField,{entityId:string;value:NonNullable<EntitySystemMechanics[SystemMechanicsField]>}>{
  const owners=new Map<SystemMechanicsField,{entityId:string;value:NonNullable<EntitySystemMechanics[SystemMechanicsField]>}>();
  for(const entity of authority.entities)for(const field of systemMechanicsFields){
    const value=entity.system_mechanics?.[field];if(value===undefined)continue;
    const prior=owners.get(field);if(prior)throw new Error(`${field} is authored by both ${prior.entityId} and ${entity.id}`);
    owners.set(field,{entityId:entity.id,value});
  }
  return owners;
}

export function selectSystemMechanics(authority:Authority):Required<EntitySystemMechanics>{
  const owners=systemMechanicsOwners(authority),result={} as Required<EntitySystemMechanics>;
  for(const field of systemMechanicsFields){const owner=owners.get(field);if(!owner)throw new Error(`${field} has no canonical system_mechanics owner`);(result as Record<string,unknown>)[field]=owner.value;}
  return result;
}

export function deriveCalculatorProjection(authority:Authority):CalculatorProjection{
  const system=selectSystemMechanics(authority),features=authority.entities.flatMap(entity=>{const projected=projectCalculatorMechanics(entity);return projected?[projected]:[];}),feature_rules=authority.entities.flatMap(entity=>{const projected=projectHarnessMechanics(entity);return projected?[projected]:[];});
  return {...authority.calculator,
    proficiency_bonus_bands:structuredClone(system.proficiency_bonus_bands),psi_point_bands:structuredClone(system.psi_point_bands),psionic_focus_bands:structuredClone(system.psionic_focus_bands),manifested_strike_die_bands:structuredClone(system.manifested_strike_die_bands),tier_minimum_levels:structuredClone(system.tier_minimum_levels),
    harness_mechanics:{action_economy:structuredClone(system.action_economy),manifested_strike:structuredClone(system.manifested_strike),overload:structuredClone(system.overload),psionic_apex:structuredClone(system.psionic_apex),disciplines:structuredClone(system.disciplines),feature_rules},features
  };
}

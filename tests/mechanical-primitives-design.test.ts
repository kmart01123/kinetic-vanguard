import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";

type Disposition="promote"|"generalize"|"derive"|"benchmark_only";
type Audit={
  format_version:number;
  groups:Record<string,{source:string;fields:Record<string,{disposition:Disposition;target:string}>}>;
  value_dispositions:Record<string,Record<string,{disposition:Disposition;target:string}>>;
};

const keys=(rows:readonly Record<string,unknown>[]):string[]=>[...new Set(rows.flatMap(row=>Object.keys(row)))].sort();
const audited=(audit:Audit,group:string):string[]=>Object.keys(audit.groups[group]!.fields).sort();
const values=(rows:readonly Record<string,unknown>[],field:string):string[]=>[...new Set(rows.map(row=>row[field]).filter((value):value is string=>typeof value==="string"))].sort();

test("mechanical field audit covers every populated Calculator and harness source field",async()=>{
  const [{authority},auditSource,design]=await Promise.all([loadAuthority(),readFile("policy/mechanical-field-dispositions.json","utf8"),readFile("docs/mechanical-primitives-design.md","utf8")]);
  const audit=JSON.parse(auditSource) as Audit;assert.equal(audit.format_version,1);
  const calculatorFeatures=authority.calculator.features as unknown as Record<string,unknown>[];
  const calculatorTiers=calculatorFeatures.flatMap(row=>(row.tiers??[]) as Record<string,unknown>[]);
  const calculatorDamage=calculatorTiers.flatMap(row=>[row.damage,row.secondary_damage].filter((value):value is Record<string,unknown>=>value!==undefined));
  const calculatorMetrics=calculatorFeatures.flatMap(row=>(row.metrics??[]) as Record<string,unknown>[]);
  const calculatorMetricValues=calculatorMetrics.flatMap(row=>(row.values??[]) as Record<string,unknown>[]);
  const harnessRules=authority.calculator.harness_mechanics.feature_rules as unknown as Record<string,unknown>[];
  const harnessTargeting=harnessRules.flatMap(row=>(row.targeting_by_tier??[]) as Record<string,unknown>[]);
  const harnessArmorReduction=harnessRules.flatMap(row=>(row.armor_class_reduction_by_tier??[]) as Record<string,unknown>[]);
  const harnessControlTiers=harnessRules.flatMap(row=>(row.control_tiers??[]) as Record<string,unknown>[]);
  const harnessControlEffects=harnessControlTiers.flatMap(row=>(row.effects??[]) as Record<string,unknown>[]);
  const groups:Record<string,Record<string,unknown>[]>={calculator_feature:calculatorFeatures,calculator_tier:calculatorTiers,calculator_damage:calculatorDamage,calculator_metric:calculatorMetrics,calculator_metric_value:calculatorMetricValues,harness_feature_rule:harnessRules,harness_targeting:harnessTargeting,harness_armor_reduction:harnessArmorReduction,harness_control_tier:harnessControlTiers,harness_control_effect:harnessControlEffects};
  assert.deepEqual(Object.keys(audit.groups).sort(),Object.keys(groups).sort());
  for(const [group,rows] of Object.entries(groups)){assert.deepEqual(audited(audit,group),keys(rows),group);for(const item of Object.values(audit.groups[group]!.fields)){assert.ok(["promote","generalize","derive","benchmark_only"].includes(item.disposition));assert.ok(item.target.length>0);}}
  const valueAudits:[string,Record<string,unknown>[],string][]=[
    ["calculator.features[].delivery",calculatorFeatures,"delivery"],
    ["calculator.harness_mechanics.feature_rules[].targeting_by_tier[].kind",harnessTargeting,"kind"],
    ["calculator.harness_mechanics.feature_rules[].control_tiers[].application",harnessControlTiers,"application"],
    ["calculator.harness_mechanics.feature_rules[].control_tiers[].effects[].gate",harnessControlEffects,"gate"]
  ];
  for(const [path,rows,field] of valueAudits)assert.deepEqual(Object.keys(audit.value_dispositions[path]!).sort(),values(rows,field),path);
  assert.equal(audit.value_dispositions["calculator.harness_mechanics.feature_rules[].targeting_by_tier[].kind"]!.cluster_remainder!.disposition,"benchmark_only");
  for(const sentinel of ["ember_bolt","glacial_spike","static_discharge","explosion_implosion","frozen_ground","common_empathic_sense"])assert.ok(design.includes(`| \`${sentinel}\` |`),sentinel);
  assert.match(design,/There is no composite-rider delivery/);
  assert.match(design,/Generated prose is not a goal/);
});

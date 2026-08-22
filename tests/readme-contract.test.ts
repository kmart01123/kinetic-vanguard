import assert from "node:assert/strict";
import test from "node:test";
import { access, readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";

const parseVersion=(value:string):readonly number[]=>value.split(".").map(Number);
const compareVersions=(left:string,right:string):number=>{const a=parseVersion(left),b=parseVersion(right);for(let index=0;index<3;index+=1){const difference=(a[index]??0)-(b[index]??0);if(difference!==0)return difference;}return 0;};

const readReleaseStatus=(source:string):{published:string;development:string}=>{
  const published=[...source.matchAll(/^- Current published release: \*\*v(\d+\.\d+\.\d+)\*\*$/gm)].map(match=>match[1]!);
  const development=[...source.matchAll(/^- Current development line: \*\*(v\d+\.\d+\.\d+|None)\*\*$/gm)].map(match=>match[1]!);
  assert.equal(published.length,1);assert.equal(development.length,1);
  return {published:published[0]!,development:development[0]!};
};

type BalanceSnapshot={kind:"published";rulesVersion:string}|{kind:"development";rulesVersion:string;publishedVersion:string};

const readBalanceSnapshot=(region:string):BalanceSnapshot=>{
  const lines=[...region.matchAll(/^\*\*(?:Published|Unreleased development) snapshot\*\*.*$/gm)].map(match=>match[0]);assert.equal(lines.length,1);
  const published=lines[0]!.match(/^\*\*Published snapshot\*\* — canonical rules \*\*v(\d+\.\d+\.\d+)\*\*\.$/);if(published)return {kind:"published",rulesVersion:published[1]!};
  const development=lines[0]!.match(/^\*\*Unreleased development snapshot\*\* — canonical rules \*\*v(\d+\.\d+\.\d+)\*\*; current published release \*\*v(\d+\.\d+\.\d+)\*\*\.$/);assert.ok(development);
  return {kind:"development",rulesVersion:development[1]!,publishedVersion:development[2]!};
};

const assertBalanceSnapshotState=(snapshot:BalanceSnapshot,release:{published:string;development:string},authorityVersion:string):void=>{
  if(snapshot.kind==="published"){
    assert.equal(snapshot.rulesVersion,release.published);
    if(release.development==="None")assert.equal(snapshot.rulesVersion,authorityVersion);
    else{assert.equal(release.development,`v${authorityVersion}`);assert.ok(compareVersions(snapshot.rulesVersion,authorityVersion)<0);}
    return;
  }
  assert.notEqual(release.development,"None");assert.equal(release.development,`v${authorityVersion}`);assert.equal(snapshot.rulesVersion,authorityVersion);assert.equal(snapshot.publishedVersion,release.published);
};

test("README release status matches canonical development truth",async()=>{
  const [{authority},readme]=await Promise.all([loadAuthority(),readFile("README.md","utf8")]);const release=readReleaseStatus(readme);
  assert.ok(compareVersions(release.published,authority.rules_version)<=0);
  if(release.development!=="None")assert.equal(release.development,`v${authority.rules_version}`);
});

test("balance snapshot identity cannot claim newer authority",()=>{
  assertBalanceSnapshotState(readBalanceSnapshot("**Published snapshot** — canonical rules **v14.2.0**."),{published:"14.2.0",development:"v14.3.0"},"14.3.0");
  assertBalanceSnapshotState(readBalanceSnapshot("**Unreleased development snapshot** — canonical rules **v14.3.0**; current published release **v14.2.0**."),{published:"14.2.0",development:"v14.3.0"},"14.3.0");
  assert.throws(()=>assertBalanceSnapshotState(readBalanceSnapshot("**Published snapshot** — canonical rules **v14.3.0**."),{published:"14.2.0",development:"v14.3.0"},"14.3.0"));
});

test("README exposes one structurally valid headline balance snapshot",async()=>{
  const [{authority},readme,detail,harnessGuide,packageJsonSource,benchmarkConfigSource]=await Promise.all([loadAuthority(),readFile("README.md","utf8"),readFile("CONTROL_BENCHMARK_DETAIL.md","utf8"),readFile("harness/README.md","utf8"),readFile("package.json","utf8"),readFile("harness/config/benchmark.json","utf8")]);
  const packageJson=JSON.parse(packageJsonSource) as {readonly scripts?:Readonly<Record<string,string>>};
  const benchmarkConfig=JSON.parse(benchmarkConfigSource) as {readonly methodology:{readonly levels:readonly number[]}};
  const beginMarker="<!-- BEGIN GENERATED BALANCE MATRICES -->",endMarker="<!-- END GENERATED BALANCE MATRICES -->";
  const occurrences=(source:string,value:string):number=>source.split(value).length-1;assert.equal(occurrences(readme,beginMarker),1);assert.equal(occurrences(readme,endMarker),1);
  const begin=readme.indexOf(beginMarker),end=readme.indexOf(endMarker);assert.ok(begin>=0&&end>begin);const region=readme.slice(begin,end+endMarker.length);
  assertBalanceSnapshotState(readBalanceSnapshot(region),readReleaseStatus(readme),authority.rules_version);
  assert.ok(region.includes("Target profile: `headline`."));assert.match(region,/exact analytical full-roster results/i);
  for(const heading of ["Balance benchmark snapshot","Single-Target Damage","Control benchmark"])assert.match(region,new RegExp("^#{2,4} "+heading.replace(/[.*+?^$(){}|[\]\\]/g,"\\$&")+"$","m"));
  const tableHeader="| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |";assert.equal(occurrences(region,tableHeader),1);
  const lines=region.split("\n"),headerIndexes=lines.flatMap((line,index)=>line===tableHeader?[index]:[]),expectedLevels=benchmarkConfig.methodology.levels.map(String),publicResult=/^(?:IDEAL|N\/A|COLD \(-\d+(?:\.\d+)?%\)|HOT \(\+\d+(?:\.\d+)?%\))$/;
  for(const headerIndex of headerIndexes){assert.equal(lines[headerIndex+1],"|---|---|---|---|---|");const rows=lines.slice(headerIndex+2,headerIndex+2+expectedLevels.length);assert.equal(rows.length,expectedLevels.length);rows.forEach((row,rowIndex)=>{const cells=row.split("|").slice(1,-1).map(cell=>cell.trim());assert.equal(cells.length,5);assert.equal(cells[0],expectedLevels[rowIndex]);for(const cell of cells.slice(1))assert.match(cell,publicResult);});}
  const exactDamageTable=[tableHeader,"|---|---|---|---|---|","| 7 | COLD (-6.99%) | IDEAL | COLD (-2.61%) | IDEAL |","| 11 | COLD (-19.47%) | IDEAL | COLD (-0.20%) | IDEAL |","| 15 | COLD (-18.10%) | IDEAL | IDEAL | COLD (-6.75%) |","| 20 | COLD (-41.52%) | COLD (-12.76%) | COLD (-14.95%) | COLD (-26.58%) |"].join("\n");assert.equal(occurrences(region,exactDamageTable),1);
  assert.match(region,/47 creature profiles from SRD 5\.2\.1 at levels 7, 11, 15, and 20/);assert.match(region,/weighted equally within their level/);
  assert.match(region,/Battle Master and Eldritch Knight define the comparison envelope for the front-door Single-Target Damage result/);assert.match(region,/comparator-envelope benchmark, not a universal real-play balance tolerance/);assert.match(region,/Front-door damage comparator-table cells contain only the public balance classification/);assert.doesNotMatch(region,/README cells intentionally contain only/);
  assert.match(region,/Control Value and Control Reliability require more context than the front-door damage check.*exhaustive exact-form results, effective coverage, Control Unit methodology, and Reliability analysis/s);
  const detailLink="[Full control benchmark, catalog, and methodology](CONTROL_BENCHMARK_DETAIL.md)";assert.equal(occurrences(region,detailLink),1);assert.doesNotMatch(region,/CONTROL_BENCHMARK\.md/);
  for(const heading of ["Control Value","Kinetic Vanguard mean Control Value","Control Reliability — delivery diagnostic","Kinetic Vanguard mean Reliability","Why Control Value and Reliability can disagree","Control methodology","Kinetic Vanguard control catalog","Control coverage exceptions","Control Unit primitive pricing rubric","Context-dependent and unpriced control primitives","Control Value normalization rules"])assert.doesNotMatch(region,new RegExp("^#{2,4} "+heading+"$","m"));
  assert.doesNotMatch(region,/Configured Reliability metric|Sap can be very reliable|Stunned-style control|Normalization prevents double counting|Zero Control Value from missing context/);
  assert.match(detail,/^# Kinetic Vanguard Control Benchmark Detail$/m);
  for(const heading of ["Kinetic Vanguard control catalog","Control coverage exceptions","Benchmark roster, effectiveness, and coverage","How Control Value is calculated","Worked example: Sap-style next-attack Disadvantage","Worked example: Stunned","Control Unit primitive pricing rubric","Maintained transform definitions","How movement control is normalized","Context-dependent and unpriced control primitives","Control Value normalization rules"])assert.match(detail,new RegExp("^#{2,4} "+heading.replace(/[.*+?^$(){}|[\]\\]/g,"\\$&")+"$","m"));
  assert.equal(occurrences(detail,"| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |"),4);assert.match(detail,/Forked Lightning — T2 — primary/);assert.match(detail,/Forked Lightning — T2 — secondary/);assert.match(detail,/Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20\. Each column uses the complete maintained roster for that level\./);
  assert.match(detail,/catalog is a decomposition view.*Each Kinetic Mastery row reports only that Mastery's control.*each rider\/tier\/role row reports only control produced by that exact rider form.*headline discipline benchmark above remains a separate whole-legal-package view/s);
  assert.match(detail,/\*\*Cell format:\*\* `CU · delivery · effective\/roster`/);assert.match(detail,/`0\.143 CU · 95\.00% · 12\/12` means `0\.143 CU` average Control Value and `95\.00%` average initial control-delivery probability.*at least one modeled control consequence.*structural restrictions, immunities, and effect dependencies/s);
  assert.match(detail,/`12\/12 effective` does \*\*not\*\* mean 100% delivery or that every consequence works.*`10\/11 effective` means one of the 11 creatures cannot receive any modeled control/s);assert.match(detail,/partial-effect exception.*Coverage is not a save result, hit count, successful application count, CU threshold, pricing state, or delivery probability/s);assert.doesNotMatch(detail,/eligible\/roster/);
  assert.match(detail,/`Unpriced` retains measurable delivery and effectiveness coverage without reporting zero CU/);assert.match(detail,/`No modeled control` means `0\.000 CU` and no control delivery \(`—`\)/);assert.match(detail,/`N\/A` means the exact form is unavailable at that level/);
  const exceptionsHeading="### Control coverage exceptions",methodologyHeading="### Benchmark roster, effectiveness, and coverage",methodologyLink="[Benchmark roster, effectiveness, and coverage](#benchmark-roster-effectiveness-and-coverage)";assert.equal(occurrences(detail,exceptionsHeading),1);assert.equal(occurrences(detail,methodologyHeading),1);assert.equal(occurrences(detail,methodologyLink),1);
  assert.match(detail,/Structural legality remains an internal prerequisite.*`target_is_eligible\(\)`.*maximum-size and required-creature-type restrictions.*`effective\/roster` coverage/s);assert.match(detail,/immunity can instead remove one or more consequences.*partially effective and remains in the coverage numerator.*every modeled consequence is nullified, the target is ineffective/s);assert.match(detail,/Effective coverage is descriptive metadata, not a success roll, CU threshold, pricing state, delivery probability, or alternate averaging population.*ineffective target remains in the aggregate denominator/s);assert.match(detail,/Do not divide only by effective targets.*Effective-only averaging would hide practical restrictions/s);assert.match(detail,/\*\*Instructional example \(not a published scenario\):\*\*.*9 effective targets.*3 ineffective targets.*\(9 × 0\.80 \+ 3 × 0\) \/ 12 = 0\.60 = 60%.*effective-only 80% is not the roster-wide result/s);
  const catalogRegion=detail.slice(detail.indexOf("### Kinetic Vanguard control catalog"),detail.indexOf(exceptionsHeading));const catalogRows=catalogRegion.split("\n").filter(line=>/^\| (?!Rider \/ form|---)/.test(line));assert.equal(catalogRows.length,67);
  const ratios=catalogRegion.match(/\b\d+\/\d+\b/g)??[];const ratioCounts=Object.fromEntries([...new Set(ratios)].sort().map(ratio=>[ratio,ratios.filter(value=>value===ratio).length]));assert.deepEqual(ratioCounts,{"10/11":1,"11/11":29,"11/12":8,"12/12":56,"3/12":3,"4/11":1,"9/12":1});
  const exceptionRegion=detail.slice(detail.indexOf(exceptionsHeading),detail.indexOf(methodologyHeading));const exceptionRows=exceptionRegion.split("\n").filter(line=>/^\| (?!Discipline \/ exact form|---)/.test(line));assert.equal(exceptionRows.length,26);assert.match(exceptionRegion,/Cryokinesis — Snow Chains — T0 \| Fighter 7 \| Air Elemental \| Partial \| immune to Restrained; Speed 0 remains effective/);assert.match(exceptionRegion,/Cryokinesis — Snow Chains — T1 \| Fighter 7 \| Air Elemental \| Partial \| immune to Restrained; Speed 0 and Reaction denial remain effective/);assert.match(exceptionRegion,/Purple Worm.*exceeds maximum size Large/);assert.doesNotMatch(exceptionRegion,/Purple Worm[^\n]*Blinded/i);
  const pricingCounts={priced:0,partial:0,unpriced:0,noControl:0};for(const row of catalogRows){if(row.includes("no modeled control"))pricingCounts.noControl+=1;else if(row.includes("Unpriced ·"))pricingCounts.unpriced+=1;else if(row.includes("(partial)"))pricingCounts.partial+=1;else{assert.match(row,/\d+\.\d{3} CU ·/);pricingCounts.priced+=1;}}assert.deepEqual(pricingCounts,{priced:27,partial:8,unpriced:1,noControl:31});
  assert.match(detail,/1\.0 CU = denial of one target's normal Action \+ Bonus Action for one scored target-turn window\./);
  assert.match(detail,/offensive_impairment_next_attack.*0\.15 CU per expected placed attack opportunity.*0\.15 × 0\.95 = 0\.1425 CU/s);
  assert.match(detail,/active-turn denial.*reaction denial.*Strength save automatic failure.*Dexterity save automatic failure.*incoming attack Advantage.*\*\*2\.25 CU\*\*/s);
  assert.match(detail,/opportunity-normalized synthetic example.*1\.00 expected exposure independently.*target_turn_window.*reaction_window.*save_opportunity.*incoming_attack_opportunity/s);
  assert.match(detail,/Real Stunned benchmark rows do \*\*not\*\* automatically equal 2\.25 CU/);
  assert.match(detail,/Stunned does \*\*not\*\* gain Speed 0/);const stunnedRegion=detail.slice(detail.indexOf("#### Worked example: Stunned"),detail.indexOf("### Control Unit primitive pricing rubric"));assert.doesNotMatch(stunnedRegion,/^\| Speed 0 \|/m);
  const rubricRegion=detail.slice(detail.indexOf("### Control Unit primitive pricing rubric"),detail.indexOf("### Context-dependent and unpriced control primitives"));const pricingRows=rubricRegion.split("\n").filter(line=>/^\| `[^`]+` \| `[^`]+` \| `(?:candidate|context_required|unsupported)` \| \d+\.\d{2} CU \| `[^`]+` \|$/.test(line));assert.equal(pricingRows.length,19);const transformRows=rubricRegion.split("\n").filter(line=>/^\| `[^`]+` \| `CU =/.test(line));assert.equal(transformRows.length,6);
  assert.match(rubricRegion,/There is \*\*no universal 30-foot target assumption\*\*/);assert.match(rubricRegion,/-10 ft against benchmark Speed 10 \| 0\.30 × min\(10 \/ 10, 1\) \| 0\.30 CU/);assert.match(rubricRegion,/-10 ft against benchmark Speed 30 \| 0\.30 × min\(10 \/ 30, 1\) \| 0\.10 CU/);assert.match(rubricRegion,/-10 ft against benchmark Speed 60 \| 0\.30 × min\(10 \/ 60, 1\) \| 0\.05 CU/);assert.match(rubricRegion,/-30 ft against benchmark Speed 60 \| 0\.30 × min\(30 \/ 60, 1\) \| 0\.15 CU/);assert.match(rubricRegion,/Speed 0 against any ordinary Speed \| 0\.30 × 1\.00 active exposure \| 0\.30 CU/);
  const unpricedRegion=detail.slice(detail.indexOf("### Context-dependent and unpriced control primitives"),detail.indexOf("### Control Value normalization rules"));const unpricedRows=unpricedRegion.split("\n").filter(line=>/^\| `[^`]+` \| `[^`]+` \| `(?:context_required|unsupported)` \|/.test(line));assert.equal(unpricedRows.length,32);assert.match(unpricedRegion,/lacks a trustworthy required magnitude, timing, or placement\/exposure basis/);
  const normalizationRegion=detail.slice(detail.indexOf("### Control Value normalization rules"),detail.indexOf("## Reproducibility and maintained sources"));for(const rule of ["Duplicates","Disjoint sequential stages","Action-economy dominance","Specified Action interaction","Attack impairment","Save impairment","Movement dominance","Correlated flat mobility","Partial overlap","Unrelated consequences"])assert.equal(occurrences(normalizationRegion,`| ${rule} |`),1);
  assert.match(detail,/That fail-closed zero does \*\*not\*\* mean the mechanic is worthless in actual play/);
  assert.doesNotMatch(region,/Reliability-selected|independent Reliability selection/i);
  const sourcePaths=["KineticVanguard.yaml","harness/README.md","harness/config/benchmark.json","harness/config/control-value.json","harness/data/control_primitives.json","harness/comparators/fighter-subclasses.json"];for(const path of sourcePaths)assert.ok(detail.includes(`](${path})`));await Promise.all(sourcePaths.map(path=>access(path)));
  assert.match(harnessGuide,/Structural eligibility is internal prerequisite evidence.*Public effective coverage instead reports effective targets \/ total roster targets.*Partially effective targets remain in the numerator; fully nullified and structurally excluded targets do not.*complete roster denominator.*never creates an effective-only averaging population/s);assert.doesNotMatch(harnessGuide,/coverage reports eligible \/ total targets/);assert.match(harnessGuide,/\.\.\/CONTROL_BENCHMARK_DETAIL\.md/);
  assert.match(detail,/independently expressed analytical abstractions under the reviewed comparator source policy/);assert.doesNotMatch(detail,/Eldritch Knight[^\n.]*SRD(?: |-)only/i);
  assert.doesNotMatch(region,/ORDER CHECK|KV DPR|KV control %|KV as % of EK|KV as % of BM/);assert.doesNotMatch(region,/IDEAL \([^)]*%\)|COLD \(\+|HOT \(-/);
  assert.match(packageJson.scripts?.["readme:benchmarks"]??"",/^python3 -m harness\.readme_matrices --write(?:\s|$)/);assert.match(packageJson.scripts?.["readme:benchmarks:check"]??"",/^python3 -m harness\.readme_matrices --check(?:\s|$)/);
  assert.equal(packageJson.scripts?.["readme:control"],"python3 -m harness.readme_matrices --write --control-only");assert.equal(packageJson.scripts?.["readme:control:check"],"python3 -m harness.readme_matrices --check --control-only");
});

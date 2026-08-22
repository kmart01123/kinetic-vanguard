import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
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
  const [{authority},readme,packageJsonSource,benchmarkConfigSource]=await Promise.all([loadAuthority(),readFile("README.md","utf8"),readFile("package.json","utf8"),readFile("harness/config/benchmark.json","utf8")]);
  const packageJson=JSON.parse(packageJsonSource) as {readonly scripts?:Readonly<Record<string,string>>};
  const benchmarkConfig=JSON.parse(benchmarkConfigSource) as {readonly methodology:{readonly levels:readonly number[]}};
  const beginMarker="<!-- BEGIN GENERATED BALANCE MATRICES -->",endMarker="<!-- END GENERATED BALANCE MATRICES -->";
  const occurrences=(source:string,value:string):number=>source.split(value).length-1;assert.equal(occurrences(readme,beginMarker),1);assert.equal(occurrences(readme,endMarker),1);
  const begin=readme.indexOf(beginMarker),end=readme.indexOf(endMarker);assert.ok(begin>=0&&end>begin);const region=readme.slice(begin,end+endMarker.length);
  assertBalanceSnapshotState(readBalanceSnapshot(region),readReleaseStatus(readme),authority.rules_version);
  assert.ok(region.includes("Target profile: `headline`."));assert.match(region,/exact analytical full-roster results/i);
  for(const heading of ["Balance benchmark snapshot","Single-Target Damage","Control Value","Kinetic Vanguard mean Control Value","Kinetic Vanguard control catalog","Benchmark roster, eligibility, and coverage","How Control Value is calculated","Worked example: Sap-style next-attack Disadvantage","Worked example: Stunned","Control Reliability — delivery diagnostic","Kinetic Vanguard mean Reliability","Why Control Value and Reliability can disagree","Control methodology"])assert.match(region,new RegExp("^#{2,4} "+heading.replace(/[.*+?^$(){}|[\]\\]/g,"\\$&")+"$","m"));
  const tableHeader="| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |";assert.equal(occurrences(region,tableHeader),5);
  const lines=region.split("\n"),headerIndexes=lines.flatMap((line,index)=>line===tableHeader?[index]:[]),expectedLevels=benchmarkConfig.methodology.levels.map(String),publicResult=/^(?:IDEAL|N\/A|COLD \(-\d+(?:\.\d+)?%\)|HOT \(\+\d+(?:\.\d+)?%\))$/;
  for(const [tableIndex,headerIndex] of headerIndexes.entries()){assert.equal(lines[headerIndex+1],"|---|---|---|---|---|");const rows=lines.slice(headerIndex+2,headerIndex+2+expectedLevels.length);assert.equal(rows.length,expectedLevels.length);rows.forEach((row,rowIndex)=>{const cells=row.split("|").slice(1,-1).map(cell=>cell.trim());assert.equal(cells.length,5);assert.equal(cells[0],expectedLevels[rowIndex]);const cellPattern=tableIndex===2?/^\d+\.\d{3} CU$/:tableIndex===4?/^\d+\.\d{2}%$/:publicResult;for(const cell of cells.slice(1))assert.match(cell,cellPattern);});}
  assert.match(region,/47 creature profiles from SRD 5\.2\.1 at levels 7, 11, 15, and 20/);assert.match(region,/weighted equally within their level/);
  assert.match(region,/Battle Master and Eldritch Knight define the comparison envelope/);assert.match(region,/comparator-envelope benchmark, not a universal real-play balance tolerance/);
  assert.match(region,/\*\*Primary control-balance metric:\*\* how much mechanically useful control/);assert.match(region,/\*\*Secondary diagnostic:\*\* how reliably/);
  assert.match(region,/selects the legal package with the highest Control Value/);assert.match(region,/exact CU tie is resolved by higher whole-package Control Reliability, then by ascending stable scenario ID/);
  assert.match(region,/Control Reliability measures delivery probability for the same CU-selected package/);
  assert.equal(occurrences(region,"| Rider / form | Fighter 7 | Fighter 11 | Fighter 15 | Fighter 20 |"),4);assert.match(region,/Forked Lightning — T2 — primary/);assert.match(region,/Forked Lightning — T2 — secondary/);assert.match(region,/Columns are benchmark snapshots at Fighter levels 7, 11, 15, and 20\. Each column uses the complete maintained roster for that level\./);
  assert.match(region,/catalog is a decomposition view.*Each Kinetic Mastery row reports only that Mastery's control.*each rider\/tier\/role row reports only control produced by that exact rider form.*headline discipline benchmark above remains a separate whole-legal-package view/s);
  assert.match(region,/\*\*Cell format:\*\* `CU · delivery · eligible\/roster`/);assert.match(region,/`0\.143 CU · 95\.00% · 12\/12` means `0\.143 CU` average Control Value and `95\.00%` average initial control-delivery probability.*`12\/12` means all 12 targets satisfy the exact form's structural target restrictions/s);assert.match(region,/ratio is \*\*eligible targets \/ roster targets\*\*/);
  assert.match(region,/`9\/12`, only 9 of 12 targets satisfy the exact form's structural target restrictions.*other 3.*remain in the roster denominator and contribute `0 CU` and `0% delivery`/s);assert.match(region,/`eligible\/roster` reports structural target eligibility.*maximum-size and required-creature-type restrictions.*not universal susceptibility.*Condition immunity or other effect-level ineffectiveness can reduce a target's CU or delivery while that target remains structurally eligible in the ratio/s);assert.match(region,/Eligibility is not a save result, hit count, successful application count, or probability/);assert.doesNotMatch(region,/immunity\/effect-eligibility.*reduce|condition or effect immunity where it makes the package ineffective/i);
  assert.match(region,/`Unpriced` retains measurable delivery and eligibility without reporting zero CU/);assert.match(region,/`No modeled control` means `0\.000 CU` and no control delivery \(`—`\)/);assert.match(region,/`N\/A` means the exact form is unavailable at that level/);
  const methodologyHeading="### Benchmark roster, eligibility, and coverage",methodologyLink="[Benchmark roster, eligibility, and coverage](#benchmark-roster-eligibility-and-coverage)";assert.equal(occurrences(region,methodologyHeading),1);assert.equal(occurrences(region,methodologyLink),1);
  assert.match(region,/`eligible\/roster` means \*\*structurally eligible targets \/ total maintained benchmark targets\*\*.*`target_is_eligible\(\)`.*maximum-size and required-creature-type restrictions/s);assert.match(region,/`12\/12` means all 12 roster targets satisfy those structural restrictions.*does not mean.*universal susceptibility to every control consequence/s);assert.match(region,/An ineligible target remains in the aggregate denominator.*`CU = 0` and `delivery = 0%`/s);assert.match(region,/Condition immunity and other effect-level ineffectiveness.*not automatically coverage exclusions.*structurally eligible but immune target.*remain in the coverage numerator while contributing `0 CU` or `0% delivery`/s);assert.match(region,/Do not divide only by eligible targets.*Eligible-only averaging would hide practical restrictions/s);assert.match(region,/\*\*Instructional example \(not a published scenario\):\*\*.*9 structurally eligible targets.*3 targets are structurally ineligible.*\(9 × 0\.80 \+ 3 × 0\) \/ 12 = 0\.60 = 60%.*eligible-only 80% is not the roster-wide result/s);
  const catalogRegion=region.slice(region.indexOf("### Kinetic Vanguard control catalog"),region.indexOf(methodologyHeading));const catalogRows=catalogRegion.split("\n").filter(line=>/^\| (?!Rider \/ form|---)/.test(line));assert.equal(catalogRows.length,67);
  const pricingCounts={priced:0,partial:0,unpriced:0,noControl:0};for(const row of catalogRows){if(row.includes("no modeled control"))pricingCounts.noControl+=1;else if(row.includes("Unpriced ·"))pricingCounts.unpriced+=1;else if(row.includes("(partial)"))pricingCounts.partial+=1;else{assert.match(row,/\d+\.\d{3} CU ·/);pricingCounts.priced+=1;}}assert.deepEqual(pricingCounts,{priced:27,partial:8,unpriced:1,noControl:31});
  assert.match(region,/1\.0 CU = denial of one target's normal Action \+ Bonus Action for one scored target-turn window\./);
  assert.match(region,/offensive_impairment_next_attack.*0\.15 CU per expected placed attack opportunity.*0\.15 × 0\.95 = 0\.1425 CU/s);
  assert.match(region,/active-turn denial.*reaction denial.*Strength save automatic failure.*Dexterity save automatic failure.*incoming attack Advantage.*\*\*2\.25 CU\*\*/s);
  assert.match(region,/Stunned does \*\*not\*\* gain Speed 0/);
  assert.match(region,/Zero Control Value from missing context does \*\*not\*\* mean that a mechanic has no value in actual play/);
  assert.match(region,/HOT \(\+46\.97%\).*does \*\*not\*\* mean a 46\.97% chance to apply control.*signed distance outside the nearest Battle Master \/ Eldritch Knight Reliability comparator boundary/s);
  assert.match(region,/High Reliability \+ low Value.*soft control that lands consistently.*Lower Reliability \+ high Value/s);
  assert.doesNotMatch(region,/Reliability-selected|independent Reliability selection/i);
  for(const path of ["harness/README.md","harness/config/benchmark.json","harness/config/control-value.json","harness/data/control_primitives.json","harness/comparators/fighter-subclasses.json"])assert.ok(region.includes(`](${path})`));
  assert.match(region,/independently expressed analytical abstractions under the reviewed comparator source policy/);assert.doesNotMatch(region,/Eldritch Knight[^\n.]*SRD(?: |-)only/i);
  assert.doesNotMatch(region,/ORDER CHECK|KV DPR|KV control %|KV as % of EK|KV as % of BM/);assert.doesNotMatch(region,/IDEAL \([^)]*%\)|COLD \(\+|HOT \(-/);
  assert.match(packageJson.scripts?.["readme:benchmarks"]??"",/^python3 -m harness\.readme_matrices --write(?:\s|$)/);assert.match(packageJson.scripts?.["readme:benchmarks:check"]??"",/^python3 -m harness\.readme_matrices --check(?:\s|$)/);
  assert.equal(packageJson.scripts?.["readme:control"],"python3 -m harness.readme_matrices --write --control-only");assert.equal(packageJson.scripts?.["readme:control:check"],"python3 -m harness.readme_matrices --check --control-only");
});

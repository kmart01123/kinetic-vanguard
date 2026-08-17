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
  for(const heading of ["Balance benchmark snapshot","Single-Target Damage","Control Reliability"])assert.match(region,new RegExp("^#{2,4} "+heading.replace(/[.*+?^$(){}|[\]\\]/g,"\\$&")+"$","m"));
  const tableHeader="| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |";assert.equal(occurrences(region,tableHeader),2);
  const lines=region.split("\n"),headerIndexes=lines.flatMap((line,index)=>line===tableHeader?[index]:[]),expectedLevels=benchmarkConfig.methodology.levels.map(String),publicResult=/^(?:IDEAL|N\/A|COLD \(-\d+(?:\.\d+)?%\)|HOT \(\+\d+(?:\.\d+)?%\))$/;
  for(const headerIndex of headerIndexes){assert.equal(lines[headerIndex+1],"|---|---|---|---|---|");const rows=lines.slice(headerIndex+2,headerIndex+2+expectedLevels.length);assert.equal(rows.length,expectedLevels.length);rows.forEach((row,rowIndex)=>{const cells=row.split("|").slice(1,-1).map(cell=>cell.trim());assert.equal(cells.length,5);assert.equal(cells[0],expectedLevels[rowIndex]);for(const cell of cells.slice(1))assert.match(cell,publicResult);});}
  assert.match(region,/Battle Master and Eldritch Knight define the comparison envelope/);assert.match(region,/Control Reliability measures how often.*does not measure/s);
  assert.doesNotMatch(region,/ORDER CHECK|KV DPR|KV control %|KV as % of EK|KV as % of BM/);assert.doesNotMatch(region,/IDEAL \([^)]*%\)|COLD \(\+|HOT \(-/);
  assert.match(packageJson.scripts?.["readme:benchmarks"]??"",/^python3 -m harness\.readme_matrices --write(?:\s|$)/);assert.match(packageJson.scripts?.["readme:benchmarks:check"]??"",/^python3 -m harness\.readme_matrices --check(?:\s|$)/);
});

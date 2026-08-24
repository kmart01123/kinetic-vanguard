import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import test from "node:test";
import YAML from "yaml";

type Step={uses?:string;run?:string;with?:Record<string,unknown>};
type Job={if?:string;needs?:string;permissions?:Record<string,string>;environment?:{name?:string};steps?:Step[]};
type Workflow={on?:Record<string,unknown>;permissions?:Record<string,string>;concurrency?:{group?:string;"cancel-in-progress"?:boolean};jobs?:Record<string,Job>};

test("development prototype Pages workflow is main/manual and non-release only",async()=>{
  const source=await readFile(".github/workflows/prototype-pages.yml","utf8");
  const workflow=YAML.parse(source) as Workflow;
  assert.deepEqual(Object.keys(workflow.on??{}).sort(),["push","workflow_dispatch"]);
  assert.deepEqual(workflow.on?.push,{branches:["main"]});
  assert.equal(workflow.concurrency?.group,"pages");
  assert.equal(workflow.concurrency?.["cancel-in-progress"],false);
  assert.equal(workflow.permissions,undefined);

  const build=workflow.jobs?.build,deploy=workflow.jobs?.deploy;
  assert.equal(build?.if,"github.ref == 'refs/heads/main'");
  assert.deepEqual(build?.permissions,{contents:"read",pages:"read"});
  assert.deepEqual(deploy?.permissions,{pages:"write","id-token":"write"});
  assert.equal(deploy?.needs,"build");
  assert.equal(deploy?.if,undefined);
  assert.equal(deploy?.environment?.name,"github-pages");

  const buildSteps=build?.steps??[],deploySteps=deploy?.steps??[];
  assert.equal(buildSteps.filter(step=>step.run?.trim()==="npm run build").length,1);
  assert.doesNotMatch(source,/build:release|KV_RELEASE_APPROVED/);
  const commands=buildSteps.map(step=>step.run??"").join("\n");
  assert.match(commands,/test -s artifacts\/KineticVanguard\.prototype\.html/);
  assert.match(commands,/NON-RELEASE PROTOTYPE/);
  assert.match(commands,/"release_status":"prototype"/);
  assert.match(commands,/! grep -Fq '"release_status":"release"'/);
  assert.match(commands,/install -m 0644 artifacts\/KineticVanguard\.prototype\.html _site\/index\.html/);
  assert.ok(buildSteps.some(step=>step.uses==="actions/configure-pages@v6"));
  assert.ok(buildSteps.some(step=>step.uses==="actions/upload-pages-artifact@v5"&&step.with?.path==="_site"));
  assert.ok(deploySteps.some(step=>step.uses==="actions/deploy-pages@v5"));
});

test("generated prototype remains ignored and untracked",()=>{
  const artifact="artifacts/KineticVanguard.prototype.html";
  assert.equal(spawnSync("git",["check-ignore","-q",artifact]).status,0);
  assert.notEqual(spawnSync("git",["ls-files","--error-unmatch",artifact]).status,0);
});

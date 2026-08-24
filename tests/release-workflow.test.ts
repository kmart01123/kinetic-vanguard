import assert from "node:assert/strict";
import test from "node:test";
import { readFile, readdir } from "node:fs/promises";
import YAML from "yaml";

const workflowPath=".github/workflows/release-verify.yml";

test("only ordinary CI, development Pages, and release verification workflows remain",async()=>{
  const inventory=(await readdir(".github/workflows")).sort();
  assert.deepEqual(inventory,["ci.yml","prototype-pages.yml","release-verify.yml"]);
  assert.ok(inventory.every(path=>!/^publish-v\d/.test(path)));
});

test("release verification is manual, read-only, and non-publishing",async()=>{
  const source=await readFile(workflowPath,"utf8"),workflow=YAML.parse(source);
  assert.deepEqual(Object.keys(workflow.on),["workflow_dispatch"]);
  assert.deepEqual(Object.keys(workflow.on.workflow_dispatch.inputs).sort(),["approved_sha","version"]);
  assert.deepEqual(workflow.permissions,{actions:"read",contents:"read"});
  assert.doesNotMatch(source,/\bgh\s+release\s+(?:create|edit|upload|delete)\b|\bgit\s+push\b|\bgit\s+tag\s+(?:-a|-f|--force)\b|--clobber/);
  assert.doesNotMatch(source,/npm run (?:typecheck|validate|test(?::harness|:layout|:determinism)?|harness:validate|build\s*$)/m);
});

test("release verification binds GitHub identity and uploads one checksummed legal candidate",async()=>{
  const source=await readFile(workflowPath,"utf8");
  for(const marker of [
    "refs/heads/release/$VERSION","$GITHUB_SHA","$APPROVED_SHA","git cat-file -t","refs/tags/v$VERSION^{}",
    "actions/workflows/ci.yml/runs","Main branch gate","npm run build:release","KV_RELEASE_APPROVED",
    "KineticVanguard.html","LICENSE.md","LICENSE-CODE","LICENSE-CONTENT","NOTICE.md","SHA256SUMS","sha256sum -c"
  ])assert.match(source,new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")),marker);
  assert.equal((source.match(/actions\/upload-artifact@/g)??[]).length,1);
  assert.match(source,/path: release-candidate\//);
  assert.doesNotMatch(source,/build-manifest|filtered-search-integrity|coverage-ledger|release-evidence/i);
});

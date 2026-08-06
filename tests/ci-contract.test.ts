import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { parse } from "yaml";

test("CI exposes a stable main branch gate backed by complete verification", async () => {
  const workflow = parse(await readFile(".github/workflows/ci.yml", "utf8")) as any;
  const gate = workflow.jobs?.main_branch_gate;

  assert.ok(gate, "main_branch_gate job exists");
  assert.equal(gate.name, "Main branch gate");
  assert.doesNotMatch(gate.name, /\$\{\{|rules_version|\d+\.\d+\.\d+/);
  assert.deepEqual(gate.needs, ["metadata", "verification"]);
  assert.equal(gate.if, "${{ always() }}");
  assert.equal(gate["runs-on"], "ubuntu-24.04");
  assert.equal(gate.steps?.length, 1);

  const step = gate.steps[0];
  assert.equal(step.name, "Require successful verification");
  assert.deepEqual(step.env, {
    METADATA_RESULT: "${{ needs.metadata.result }}",
    VERIFICATION_RESULT: "${{ needs.verification.result }}"
  });
  assert.match(step.run, /test "\$METADATA_RESULT" = "success"/);
  assert.match(step.run, /test "\$VERIFICATION_RESULT" = "success"/);
});

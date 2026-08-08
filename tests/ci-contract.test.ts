import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { parse } from "yaml";

test("CI exposes a stable main branch gate backed by complete verification", async () => {
  const workflowSource = await readFile(".github/workflows/ci.yml", "utf8");
  const workflow = parse(workflowSource) as any;
  const verification = workflow.jobs?.verification;
  const gate = workflow.jobs?.main_branch_gate;

  assert.ok(verification, "verification job exists");
  assert.equal(verification.needs, "metadata");
  assert.equal(verification["continue-on-error"], undefined);

  assert.equal(workflow.jobs?.benchmark_snapshot, undefined, "ordinary CI excludes analytical benchmark regeneration");
  assert.doesNotMatch(workflowSource, /readme:benchmarks:check|harness\.readme_matrices/);

  assert.ok(gate, "main_branch_gate job exists");
  assert.equal(gate.name, "Main branch gate");
  assert.doesNotMatch(gate.name, /\$\{\{|rules_version|\d+\.\d+\.\d+/);
  assert.deepEqual(gate.needs, ["metadata", "verification"]);
  assert.equal(gate.if, "${{ always() }}");
  assert.equal(gate["runs-on"], "ubuntu-24.04");
  assert.equal(gate["continue-on-error"], undefined);
  assert.equal(gate.steps?.length, 1);

  const step = gate.steps[0];
  assert.equal(step.name, "Require successful verification");
  assert.deepEqual(step.env, {
    METADATA_RESULT: "${{ needs.metadata.result }}",
    VERIFICATION_RESULT: "${{ needs.verification.result }}"
  });
  assert.equal(step["continue-on-error"], undefined);
  assert.equal(
    step.run,
    "test \"$METADATA_RESULT\" = \"success\"\n" +
      "test \"$VERIFICATION_RESULT\" = \"success\"\n"
  );
});

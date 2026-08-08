import assert from "node:assert/strict";
import test from "node:test";
import { readdir, readFile } from "node:fs/promises";
import { parse } from "yaml";

test("CI exposes a stable main branch gate backed by complete verification", async () => {
  const workflowDirectory = ".github/workflows";
  const workflowNames = (await readdir(workflowDirectory)).filter((name) => /\.ya?ml$/.test(name));
  const sources = await Promise.all(
    workflowNames.map(async (name) => [name, await readFile(`${workflowDirectory}/${name}`, "utf8")] as const)
  );
  const workflowSource = sources.find(([name]) => name === "ci.yml")?.[1];
  assert.ok(workflowSource, "ci.yml exists");
  const workflow = parse(workflowSource) as any;
  const verification = workflow.jobs?.verification;
  const gate = workflow.jobs?.main_branch_gate;

  assert.ok(verification, "verification job exists");
  assert.equal(verification.needs, "metadata");
  assert.equal(verification["continue-on-error"], undefined);

  assert.equal(workflow.jobs?.benchmark_snapshot, undefined, "ordinary CI excludes analytical benchmark regeneration");
  assert.doesNotMatch(workflowSource, /readme:damage(?::check)?|harness\.readme_damage/);
  assert.equal(
    verification.steps?.find((step: any) => step.run === "npm run harness:validate")?.name,
    "Validate damage authority and Control Authority v2 projections"
  );
  assert.equal(
    verification.steps?.find((step: any) => step.run === "npm run test:harness")?.name,
    "Test maintained damage and Control Authority v2 contracts"
  );

  const retiredPublication = `publish-v${["14", "1", "0"].join(".")}.yml`;
  assert.ok(!workflowNames.includes(retiredPublication), "current-main v14.1 publication wiring is retired");
  const forbiddenWorkflowTokens = [
    ["harness", "control"].join(":"),
    ["control", "harness"].join("_"),
    ["readme", "benchmarks"].join(":"),
    ["readme", "matrices"].join("_")
  ];
  const retiredReportFragments = [
    ["control", "comparison", "matrix"].join("-"),
    ["control", "selection", "audit"].join("-")
  ];
  for (const [name, source] of sources) {
    for (const token of [...forbiddenWorkflowTokens, ...retiredReportFragments]) {
      assert.ok(!source.includes(token), `${name} does not invoke or expect ${token}`);
    }
  }

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

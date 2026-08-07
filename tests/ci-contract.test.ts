import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { parse } from "yaml";

test("CI exposes a stable main branch gate backed by complete verification", async () => {
  const workflow = parse(await readFile(".github/workflows/ci.yml", "utf8")) as any;
  const benchmark = workflow.jobs?.benchmark_snapshot;
  const gate = workflow.jobs?.main_branch_gate;

  assert.ok(benchmark, "benchmark_snapshot job exists");
  assert.equal(benchmark.needs, "metadata");
  assert.equal(
    benchmark.name,
    "v${{ needs.metadata.outputs.rules_version }} README benchmark synchronization"
  );
  assert.equal(benchmark["runs-on"], "ubuntu-24.04");
  assert.equal(benchmark["timeout-minutes"], 20);
  assert.ok(
    benchmark.steps?.some(
      (candidate: any) =>
        candidate.name === "Verify README benchmark matrices" &&
        candidate.run === "npm run readme:benchmarks:check"
    )
  );
  assert.ok(
    !benchmark.steps?.some((candidate: any) => candidate.name === "Install browser engines"),
    "benchmark synchronization does not wait for browser installation"
  );

  assert.ok(gate, "main_branch_gate job exists");
  assert.equal(gate.name, "Main branch gate");
  assert.doesNotMatch(gate.name, /\$\{\{|rules_version|\d+\.\d+\.\d+/);
  assert.deepEqual(gate.needs, ["metadata", "verification", "benchmark_snapshot"]);
  assert.equal(gate.if, "${{ always() }}");
  assert.equal(gate["runs-on"], "ubuntu-24.04");
  assert.equal(gate.steps?.length, 1);

  const step = gate.steps[0];
  assert.equal(step.name, "Require successful verification");
  assert.deepEqual(step.env, {
    METADATA_RESULT: "${{ needs.metadata.result }}",
    VERIFICATION_RESULT: "${{ needs.verification.result }}",
    BENCHMARK_SNAPSHOT_RESULT: "${{ needs.benchmark_snapshot.result }}"
  });
  assert.match(step.run, /test "\$METADATA_RESULT" = "success"/);
  assert.match(step.run, /test "\$VERIFICATION_RESULT" = "success"/);
  assert.match(step.run, /test "\$BENCHMARK_SNAPSHOT_RESULT" = "success"/);
});

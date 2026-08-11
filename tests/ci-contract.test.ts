import assert from "node:assert/strict";
import test from "node:test";
import { readdir, readFile } from "node:fs/promises";
import { parse } from "yaml";

type WorkflowRecord = {
  readonly name: string;
  readonly workflow: any;
};

const loadWorkflows = async (): Promise<readonly WorkflowRecord[]> => {
  const directory = ".github/workflows";
  const names = (await readdir(directory)).filter((name) => /\.ya?ml$/.test(name));
  return Promise.all(names.map(async (name) => ({
    name,
    workflow: parse(await readFile(`${directory}/${name}`, "utf8"))
  })));
};

const workflowSteps = (workflow: any): readonly any[] =>
  Object.values(workflow.jobs ?? {}).flatMap((job: any) => Array.isArray(job?.steps) ? job.steps : []);

const stepRuns = (workflow: any): readonly string[] =>
  workflowSteps(workflow)
    .map((step) => step.run)
    .filter((run): run is string => typeof run === "string");

test("CI exposes a stable main branch gate backed by complete verification", async () => {
  const workflow = (await loadWorkflows()).find(({ name }) => name === "ci.yml")?.workflow;
  assert.ok(workflow, "ci.yml exists");
  assert.deepEqual(Object.keys(workflow.jobs ?? {}), ["metadata", "verification", "main_branch_gate"], "ordinary CI retains exactly three jobs");
  const verification = workflow.jobs?.verification;
  const gate = workflow.jobs?.main_branch_gate;

  assert.ok(verification, "verification job exists");
  assert.equal(verification.needs, "metadata");
  assert.equal(verification["continue-on-error"], undefined);
  assert.equal(
    verification.steps?.find((step: any) => step.run === "npm run harness:validate")?.name,
    "Validate damage authority, Control Authority v2, control-target inputs, and shared control engine"
  );
  assert.equal(
    verification.steps?.find((step: any) => step.run === "npm run test:harness")?.name,
    "Test maintained damage, Control Authority v2, control-target, and shared control-engine contracts"
  );
  const requiredVerificationCommands = [
    "npm run typecheck",
    "npm run validate",
    "npm test",
    "npm run harness:validate",
    "npm run test:harness",
    "npm run build",
    "npm run test:determinism",
    "npm run test:layout"
  ];
  const verificationRuns = new Set(stepRuns({ jobs: { verification } }));
  for (const command of requiredVerificationCommands) {
    assert.ok(verificationRuns.has(command), `verification runs ${command}`);
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

test("control-engine validation entrypoints are exact and reuse the maintained verification job", async () => {
  const packageJson = JSON.parse(await readFile("package.json", "utf8")) as {
    readonly scripts: Readonly<Record<string, string>>;
  };
  assert.equal(
    packageJson.scripts["control:engine:validate"],
    "python3 -m harness.control_engine --validate-only"
  );
  assert.equal(
    packageJson.scripts["control:engine:fixtures"],
    "python3 -m unittest harness.tests.test_control_engine_fixtures"
  );
  assert.equal(
    packageJson.scripts["harness:validate"],
    "python3 -m harness.creature_catalog && python3 -m harness.damage_harness --output-dir /tmp/kv-harness-validation --validate-only && python3 -m harness.authority --projection-version 2.1.0 --require-benchmark-ready && python3 -m harness.control_engine --validate-only"
  );
  assert.doesNotMatch(packageJson.scripts["harness:validate"] ?? "", /harness:damage|readme:damage|--fixtures-only/);
});
test("maintained automation cannot execute retired Control Reliability or regenerate analytical evidence in ordinary CI", async () => {
  const [workflows, packageJsonSource] = await Promise.all([
    loadWorkflows(),
    readFile("package.json", "utf8")
  ]);
  const scripts = (JSON.parse(packageJsonSource) as {
    readonly scripts: Readonly<Record<string, string>>;
  }).scripts;
  const retiredHarnessCommand = ["harness", "control"].join(":");
  const retiredReadmeCommand = ["readme", "benchmarks"].join(":");
  for (const name of [retiredHarnessCommand, retiredReadmeCommand, `${retiredReadmeCommand}:check`]) {
    assert.equal(Object.hasOwn(scripts, name), false, `package entrypoint ${name} remains retired`);
  }

  const retiredPublication = `publish-v${["14", "1", "0"].join(".")}.yml`;
  assert.ok(!workflows.some(({ name }) => name === retiredPublication), "current-main v14.1 publication wiring remains retired");

  const retiredConsumers = [
    `npm run ${retiredHarnessCommand}`,
    `npm run ${retiredReadmeCommand}`,
    ["harness", "control_harness"].join("."),
    ["harness", "readme_matrices"].join("."),
    ["harness", "comparison_report"].join("."),
    ["control", "comparison", "matrix"].join("-"),
    ["control", "selection", "audit"].join("-"),
    ["control", "detail"].join("-")
  ];
  for (const { name, workflow } of workflows) {
    const consumerFields = workflowSteps(workflow).flatMap((step) => [
      typeof step.run === "string" ? step.run : "",
      typeof step.with?.path === "string" ? step.with.path : ""
    ]).join("\n");
    for (const retired of retiredConsumers) {
      assert.ok(!consumerFields.includes(retired), `${name} does not execute or upload ${retired}`);
    }
  }

  const ci = workflows.find(({ name }) => name === "ci.yml")?.workflow;
  assert.ok(ci, "ci.yml exists");
  assert.equal(ci.jobs?.benchmark_snapshot, undefined, "ordinary CI has no analytical benchmark job");
  const ordinaryCiRuns = stepRuns(ci).join("\n");
  for (const analyticalEntrypoint of [
    "npm run readme:damage",
    "python3 -m harness.readme_damage",
    "npm run harness:damage"
  ]) {
    assert.ok(!ordinaryCiRuns.includes(analyticalEntrypoint), `ordinary CI does not run ${analyticalEntrypoint}`);
  }
});

test("release-gate orchestration authorizes one release build and uploads every required artifact", async () => {
  const ci = (await loadWorkflows()).find(({ name }) => name === "ci.yml")?.workflow;
  assert.ok(ci, "ci.yml exists");
  const steps = workflowSteps({ jobs: { verification: ci.jobs?.verification } });

  const releaseBuildIndexes = steps.flatMap((step, index) =>
    step.run === "npm run build:release" ? [index] : []
  );
  assert.equal(releaseBuildIndexes.length, 1, "CI has exactly one release-profile build");
  const releaseBuild = steps[releaseBuildIndexes[0]!]!;
  assert.equal(releaseBuild.env?.KV_RELEASE_APPROVED, "1", "release-profile build is explicitly authorized");
  assert.equal(releaseBuild["continue-on-error"], undefined);

  const identityIndexes = steps.flatMap((step, index) =>
    typeof step.name === "string" && /^Verify .* release identity$/.test(step.name) && typeof step.run === "string"
      ? [index]
      : []
  );
  assert.equal(identityIndexes.length, 1, "CI has one release-identity verification step");

  const publicationUploads = steps.flatMap((step, index) => {
    if (typeof step.uses !== "string" || !step.uses.startsWith("actions/upload-artifact@")) return [];
    const paths = typeof step.with?.path === "string"
      ? step.with.path.split(/\r?\n/).map((path: string) => path.trim()).filter(Boolean)
      : [];
    return paths.includes("artifacts/KineticVanguard.html") ? [{ index, step, paths }] : [];
  });
  assert.equal(publicationUploads.length, 1, "CI has one current-release publication upload");
  const publication = publicationUploads[0]!;
  assert.equal(publication.step.with?.["if-no-files-found"], "error");
  for (const path of [
    "artifacts/KineticVanguard.html",
    "artifacts/build-manifest.json",
    "artifacts/filtered-search-integrity.json",
    "artifacts/coverage-ledger.json",
    "LICENSE.md",
    "LICENSE-CODE",
    "LICENSE-CONTENT",
    "NOTICE.md"
  ]) {
    assert.ok(publication.paths.includes(path), `publication upload includes ${path}`);
  }
  assert.ok(releaseBuildIndexes[0]! < identityIndexes[0]!);
  assert.ok(identityIndexes[0]! < publication.index);
});

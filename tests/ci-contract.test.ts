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
const gha = (expression: string): string => "$" + "{{ " + expression + " }}";

const prHeadRepository = gha(
  "github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name || github.repository"
);
const prHeadSha = gha(
  "github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha"
);

const assertExactSourceContract = (workflow: any): void => {
  assert.deepEqual(
    Object.keys(workflow.jobs ?? {}),
    ["metadata", "verification", "main_branch_gate"],
    "ordinary CI retains exactly three jobs"
  );
  assert.equal(workflow.on?.workflow_dispatch, null, "workflow_dispatch has no special SHA input");
  assert.equal(workflow.concurrency, undefined, "workflow concurrency remains unchanged");

  const metadata = workflow.jobs?.metadata;
  const verification = workflow.jobs?.verification;
  const gate = workflow.jobs?.main_branch_gate;
  assert.ok(metadata, "metadata job exists");
  assert.ok(verification, "verification job exists");
  assert.ok(gate, "main_branch_gate job exists");

  assert.deepEqual(metadata.outputs, {
    rules_version: gha("steps.rules-version.outputs.rules_version"),
    source_repository: gha("steps.source.outputs.source_repository"),
    source_sha: gha("steps.source.outputs.source_sha")
  });
  const metadataCheckout = metadata.steps?.[0];
  const metadataSourceCheck = metadata.steps?.[1];
  assert.match(metadataCheckout?.uses ?? "", /^actions\/checkout@/);
  assert.equal(metadataCheckout?.with?.repository, prHeadRepository);
  assert.equal(metadataCheckout?.with?.ref, prHeadSha);
  assert.equal(metadataSourceCheck?.id, "source");
  assert.equal(metadataSourceCheck?.env?.EXPECTED_SOURCE_REPOSITORY, prHeadRepository);
  assert.equal(metadataSourceCheck?.env?.EXPECTED_SOURCE_SHA, prHeadSha);
  assert.match(metadataSourceCheck?.run ?? "", /checked_out_sha="\$\(git rev-parse HEAD\)"/);
  assert.match(
    metadataSourceCheck?.run ?? "",
    /test "\$checked_out_sha" = "\$EXPECTED_SOURCE_SHA"/
  );
  assert.match(
    metadataSourceCheck?.run ?? "",
    /source_repository=\$EXPECTED_SOURCE_REPOSITORY/
  );
  assert.match(metadataSourceCheck?.run ?? "", /source_sha=\$EXPECTED_SOURCE_SHA/);
  assert.equal(metadata.steps?.[2]?.id, "rules-version", "HEAD is asserted immediately after checkout");

  assert.equal(verification.needs, "metadata");
  const verificationCheckout = verification.steps?.[0];
  const verificationSourceCheck = verification.steps?.[1];
  assert.match(verificationCheckout?.uses ?? "", /^actions\/checkout@/);
  assert.equal(
    verificationCheckout?.with?.repository,
    gha("needs.metadata.outputs.source_repository")
  );
  assert.equal(verificationCheckout?.with?.ref, gha("needs.metadata.outputs.source_sha"));
  assert.equal(
    verificationSourceCheck?.env?.EXPECTED_SOURCE_SHA,
    gha("needs.metadata.outputs.source_sha")
  );
  assert.match(verificationSourceCheck?.run ?? "", /checked_out_sha="\$\(git rev-parse HEAD\)"/);
  assert.match(
    verificationSourceCheck?.run ?? "",
    /test "\$checked_out_sha" = "\$EXPECTED_SOURCE_SHA"/
  );
  assert.match(
    verification.steps?.[2]?.uses ?? "",
    /^actions\/setup-node@/,
    "verification asserts HEAD immediately after checkout"
  );

  for (const command of [
    "npm install --global npm@11.16.0",
    "npm ci",
    "npx playwright install --with-deps chromium firefox",
    "npm run typecheck",
    "npm run validate",
    "npm test",
    "npm run harness:validate",
    "npm run test:harness",
    "npm run build",
    "npm run test:determinism",
    "npm run test:layout",
    "npm run build:release"
  ]) {
    assert.equal(
      stepRuns(workflow).filter((run) => run === command).length,
      1,
      command + " appears exactly once in ordinary CI"
    );
    assert.ok(stepRuns({ jobs: { verification } }).includes(command));
  }

  assert.equal(gate.name, "Main branch gate");
  assert.deepEqual(gate.needs, ["metadata", "verification"]);
  assert.equal(gate.if, gha("always()"));
  assert.equal(gate.steps?.length, 1, "Main branch gate remains structurally simple");

  const uploads = workflowSteps(workflow).filter(
    (step: any) => typeof step.uses === "string" && step.uses.startsWith("actions/upload-artifact@")
  );
  assert.equal(uploads.length, 1);
  assert.deepEqual(
    uploads[0]?.with?.path.split(/\r?\n/).map((path: string) => path.trim()).filter(Boolean),
    [
      "artifacts/KineticVanguard.html",
      "artifacts/build-manifest.json",
      "artifacts/filtered-search-integrity.json",
      "artifacts/coverage-ledger.json",
      "LICENSE.md",
      "LICENSE-CODE",
      "LICENSE-CONTENT",
      "NOTICE.md"
    ],
    "publication artifact inventory remains exact"
  );
};

test("CI exposes a stable main branch gate backed by complete verification", async () => {
  const workflow = (await loadWorkflows()).find(({ name }) => name === "ci.yml")?.workflow;
  assert.ok(workflow, "ci.yml exists");
  assertExactSourceContract(workflow);
  assert.deepEqual(Object.keys(workflow.jobs ?? {}), ["metadata", "verification", "main_branch_gate"], "ordinary CI retains exactly three jobs");
  const verification = workflow.jobs?.verification;
  const gate = workflow.jobs?.main_branch_gate;

  assert.ok(verification, "verification job exists");
  assert.equal(verification.needs, "metadata");
  assert.equal(verification["continue-on-error"], undefined);
  assert.equal(
    verification.steps?.find((step: any) => step.run === "npm run harness:validate")?.name,
    "Validate damage authority, creature inputs, and Control Authority v2"
  );
  assert.equal(
    verification.steps?.find((step: any) => step.run === "npm run test:harness")?.name,
    "Test maintained damage, static target, and authority contracts"
  );
  assert.ok(
    verification.steps?.every((step: any) => typeof step.name !== "string" || !/(?:active|maintained|shared) control[- ]engine/i.test(step.name)),
    "CI labels do not claim an active control engine"
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

test("CI exact-source assertions reject the two root regressions", async (t) => {
  const workflow = (await loadWorkflows()).find(({ name }) => name === "ci.yml")?.workflow;
  assert.ok(workflow, "ci.yml exists");

  await t.test("missing authored PR-head checkout", () => {
    const mutated = structuredClone(workflow);
    mutated.jobs.metadata.steps[0].with.repository = gha("github.repository");
    assert.throws(() => assertExactSourceContract(mutated));
  });

  await t.test("missing checked-out SHA assertion", () => {
    const mutated = structuredClone(workflow);
    mutated.jobs.verification.steps[1].run = "checked_out_sha=\"$(git rev-parse HEAD)\"\n";
    assert.throws(() => assertExactSourceContract(mutated));
  });
});

test("retired control-engine entrypoints are absent and maintained harness validation is exact", async () => {
  const packageJson = JSON.parse(await readFile("package.json", "utf8")) as {
    readonly scripts: Readonly<Record<string, string>>;
  };
  for (const name of ["control:engine:validate", "control:engine:fixtures"]) {
    assert.equal(Object.hasOwn(packageJson.scripts, name), false, `${name} remains absent`);
  }
  assert.equal(
    packageJson.scripts["harness:validate"],
    "python3 -m harness.creature_catalog && python3 -m harness.damage_harness --output-dir /tmp/kv-harness-validation --validate-only && python3 -m harness.authority --projection-version 2.1.0 --require-benchmark-ready"
  );
  assert.doesNotMatch(packageJson.scripts["harness:validate"] ?? "", /control_engine|harness:damage|readme:damage|--fixtures-only/);
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
  assert.doesNotMatch(
    ordinaryCiRuns,
    /control:engine|harness\.control_engine|\bplanner\b|\bsensitivity\b|Control (?:Value|Reliability)/i,
    "ordinary CI has no analytical control, planner, or sensitivity command"
  );
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

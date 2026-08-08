import assert from "node:assert/strict";
import test from "node:test";
import { access, readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { parse } from "yaml";
import {
  createControlAuthorityProjectionV2,
  createDamageHarnessProjection
} from "../src/harness-authority.js";

const exists = async (path: string): Promise<boolean> => {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
};

const walk = async (root: string): Promise<string[]> => {
  const entries = await readdir(root, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(root, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  }));
  return nested.flat().sort();
};

const retiredRuntime = ["control", "harness"].join("_");
const retiredReporter = ["comparison", "report"].join("_");
const retiredReadmeModule = ["readme", "matrices"].join("_");
const retiredReadmeCommand = ["readme", "benchmarks"].join(":");
const retiredHarnessCommand = ["harness", "control"].join(":");
const retiredControlTiers = ["control", "tiers"].join("_");
const retiredControlMatrix = ["control", "matrix"].join("_");
const retiredControlSeed = ["control", "seed"].join("_");
const retiredControlTrials = ["control", "default", "trials"].join("_");
const retiredImport = ["legacy", "import"].join("-");
const retiredReportFragments = [
  ["control", "detail"].join("-"),
  ["control", "selection", "audit"].join("-"),
  ["control", "comparison", "matrix"].join("-")
];

test("retired runtime, report, provenance, workflow, and test paths are absent", async () => {
  const retiredPaths = [
    `harness/${retiredRuntime}.py`,
    `harness/${retiredReporter}.py`,
    `harness/${retiredReadmeModule}.py`,
    `harness/provenance/${retiredImport}.json`,
    `harness/tests/test_${retiredReadmeModule}.py`,
    `.github/workflows/publish-v${["14", "1", "0"].join(".")}.yml`
  ];
  for (const path of retiredPaths) assert.equal(await exists(path), false, path);

  const harnessPaths = await walk("harness");
  for (const fragment of retiredReportFragments) {
    assert.ok(!harnessPaths.some((path) => path.includes(fragment)), `no retired report asset contains ${fragment}`);
  }

  const requiredPaths = [
    "harness/damage_report.py",
    "harness/readme_damage.py",
    "harness/provenance/damage-review.json",
    "harness/tests/test_readme_damage.py",
    "policy/superseded-implementations.md",
    "src/control-authority-v2.ts",
    "tests/fixtures/control-authority-v2-parity.json",
    "tests/control-authority-v2-parity.test.ts",
    "harness/tests/test_authority_v2.py",
    "harness/tests/test_authority_v2_parity.py"
  ];
  for (const path of requiredPaths) assert.equal(await exists(path), true, path);
});

test("build inputs describe only maintained damage and Control Authority v2 boundaries", async () => {
  const manifest = JSON.parse(await readFile("build/inputs.json", "utf8")) as {
    readonly inputs: readonly { readonly path: string }[];
  };
  const paths = new Set(manifest.inputs.map((entry) => entry.path));
  const retiredPaths = [
    `harness/${retiredRuntime}.py`,
    `harness/${retiredReporter}.py`,
    `harness/${retiredReadmeModule}.py`,
    `harness/provenance/${retiredImport}.json`,
    `harness/tests/test_${retiredReadmeModule}.py`
  ];
  for (const path of retiredPaths) assert.equal(paths.has(path), false, path);

  for (const path of [
    "harness/damage_report.py",
    "harness/readme_damage.py",
    "harness/provenance/damage-review.json",
    "harness/tests/test_readme_damage.py",
    "policy/superseded-implementations.md",
    "tests/legacy-control-retirement.test.ts",
    "src/control-authority-v2.ts",
    "tests/fixtures/control-authority-v2-parity.json"
  ]) assert.equal(paths.has(path), true, path);

  for (const path of paths) assert.equal(await exists(path), true, `declared build input exists: ${path}`);
});

test("configuration and comparator data are damage-only and declare the effect boundary", async () => {
  const config = JSON.parse(await readFile("harness/config/benchmark.json", "utf8")) as any;
  const comparators = JSON.parse(await readFile("harness/comparators/fighter-subclasses.json", "utf8")) as any;

  assert.equal(Object.hasOwn(config, retiredControlMatrix), false);
  assert.equal(Object.hasOwn(config.methodology, retiredControlSeed), false);
  assert.equal(Object.hasOwn(config.methodology, retiredControlTrials), false);
  assert.deepEqual(config.damage_matrix.non_damage_effect_boundary, {
    rider_conditions_and_save_outcomes: "excluded_from_damage",
    ally_turn_accuracy_and_damage: "excluded",
    modeled_self_attack_exception: "thermal_fracture_ac_reduction"
  });

  assert.deepEqual(Object.keys(comparators).sort(), [
    "damage",
    "format_version",
    "primary_comparator_ids",
    "source_ruleset"
  ]);
  assert.equal(Object.hasOwn(comparators, "control"), false);
  for (const id of comparators.primary_comparator_ids) assert.ok(comparators.damage[id], id);
  assert.doesNotMatch(JSON.stringify(comparators), /scenario/i);
});

test("canonical YAML keeps Control Authority v2 but removes flattened evaluator inputs", async () => {
  const source = await readFile("KineticVanguard.yaml", "utf8");
  const authority = parse(source) as any;
  const mechanics = authority.calculator?.harness_mechanics;
  assert.ok(mechanics?.control_authority_v2, "Control Authority v2 remains canonical");
  assert.equal(mechanics.control_authority_v2.contract_version, "2.0.0");
  assert.ok(Array.isArray(mechanics.control_authority_v2.ledger));
  assert.ok(Array.isArray(mechanics.feature_rules));
  for (const rule of mechanics.feature_rules) assert.equal(Object.hasOwn(rule, retiredControlTiers), false);
});

test("damage projection is explicit, contains no retired fields, and has no generic aliases", async () => {
  const [projection, v2, typescriptSource, pythonSource, reportSource, readmeGenerator] = await Promise.all([
    createDamageHarnessProjection(),
    createControlAuthorityProjectionV2(),
    readFile("src/harness-authority.ts", "utf8"),
    readFile("harness/authority.py", "utf8"),
    readFile("harness/damage_report.py", "utf8"),
    readFile("harness/readme_damage.py", "utf8")
  ]);

  assert.equal(projection.projection_version, "1.0.0");
  assert.equal(Object.hasOwn(projection, "control_authority"), false);
  const serialized = JSON.stringify(projection);
  for (const field of [
    retiredControlTiers,
    ["control", "outcomes"].join("_"),
    ["damage", "required"].join("_"),
    ["maximum", "size"].join("_"),
    ["replaces", "mastery"].join("_")
  ]) assert.ok(!serialized.includes(`"${field}"`), field);

  assert.equal(v2.projection_version, "2.0.0");
  assert.equal(v2.control_authority.contract_version, "2.0.0");
  assert.ok(Array.isArray(v2.control_authority.ledger));

  assert.match(typescriptSource, /export interface DamageHarnessProjection/);
  assert.match(typescriptSource, /export async function createDamageHarnessProjection/);
  const genericProjectionType = ["Harness", "Projection"].join("");
  const genericProjectionFactory = ["create", "Harness", "Projection"].join("");
  assert.doesNotMatch(typescriptSource, new RegExp(`\\binterface ${genericProjectionType}\\b`));
  assert.doesNotMatch(typescriptSource, new RegExp(`\\b${genericProjectionFactory}\\b`));

  assert.match(pythonSource, /def load_damage_projection\(/);
  assert.match(pythonSource, /class DamageAuthorityModel:/);
  const genericLoader = ["load", "projection"].join("_");
  const genericModel = ["Authority", "Model"].join("");
  assert.doesNotMatch(pythonSource, new RegExp(`^def ${genericLoader}\\(`, "m"));
  assert.doesNotMatch(pythonSource, new RegExp(`^class ${genericModel}:`, "m"));

  assert.match(reportSource, /def damage_matrix_row\(/);
  assert.match(reportSource, /def write_damage_matrix\(/);
  assert.doesNotMatch(reportSource, /^def matrix_row\(/m);
  assert.doesNotMatch(reportSource, /^def write_matrix\(/m);
  assert.doesNotMatch(readmeGenerator, /\bcontrol\b/i);
});

test("package commands and every workflow exclude the retired stack and report assets", async () => {
  const packageJson = JSON.parse(await readFile("package.json", "utf8")) as {
    readonly scripts: Readonly<Record<string, string>>;
  };
  const scripts = packageJson.scripts;
  assert.equal(Object.hasOwn(scripts, retiredHarnessCommand), false);
  assert.equal(Object.hasOwn(scripts, retiredReadmeCommand), false);
  assert.equal(Object.hasOwn(scripts, `${retiredReadmeCommand}:check`), false);
  assert.deepEqual(
    Object.keys(scripts).filter((name) => name.startsWith("readme:")).sort(),
    ["readme:damage", "readme:damage:check"]
  );
  assert.equal(scripts["harness:damage"], "python3 -m harness.damage_harness");
  assert.match(scripts["readme:damage"] ?? "", /^python3 -m harness\.readme_damage --write/);
  assert.match(scripts["readme:damage:check"] ?? "", /^python3 -m harness\.readme_damage --check/);
  const forbiddenCommandFragments = [
    retiredRuntime,
    retiredReadmeModule,
    retiredReporter,
    retiredHarnessCommand,
    retiredReadmeCommand,
    ...retiredReportFragments
  ];
  for (const [name, command] of Object.entries(scripts)) {
    for (const fragment of forbiddenCommandFragments) {
      assert.ok(!command.includes(fragment), `${name} excludes ${fragment}`);
    }
  }

  const workflowDirectory = ".github/workflows";
  const workflowNames = (await readdir(workflowDirectory)).filter((name) => /\.ya?ml$/.test(name));
  const workflowSources = await Promise.all(
    workflowNames.map(async (name) => [name, await readFile(join(workflowDirectory, name), "utf8")] as const)
  );
  for (const [name, source] of workflowSources) {
    for (const fragment of [
      retiredRuntime,
      retiredReadmeModule,
      retiredReadmeCommand,
      retiredHarnessCommand,
      ...retiredReportFragments
    ]) assert.ok(!source.includes(fragment), `${name} excludes ${fragment}`);
  }

  const ciSource = workflowSources.find(([name]) => name === "ci.yml")?.[1];
  assert.ok(ciSource);
  const ci = parse(ciSource) as any;
  assert.equal(ci.jobs?.benchmark_snapshot, undefined);
  const commands = new Set(
    (ci.jobs?.verification?.steps ?? []).map((step: any) => step.run).filter((run: unknown): run is string => typeof run === "string")
  );
  for (const command of [
    "npm run typecheck",
    "npm run validate",
    "npm test",
    "npm run harness:validate",
    "npm run test:harness",
    "npm run build",
    "npm run test:determinism",
    "npm run test:layout",
    "npm run build:release"
  ]) assert.ok(commands.has(command), `CI maintains ${command}`);
  assert.ok(ci.jobs?.main_branch_gate, "stable main gate remains present");
});

test("README presents one damage table and only historical or transitional control wording", async () => {
  const [readme, harnessReadme] = await Promise.all([
    readFile("README.md", "utf8"),
    readFile("harness/README.md", "utf8")
  ]);
  const beginMarker = "<!-- BEGIN GENERATED DAMAGE MATRIX -->";
  const endMarker = "<!-- END GENERATED DAMAGE MATRIX -->";
  const begin = readme.indexOf(beginMarker);
  const end = readme.indexOf(endMarker);
  const statusStart = readme.indexOf("## Control methodology status");
  const publication = readme.indexOf("## Publication interface");
  assert.ok(begin >= 0 && end > begin && statusStart > end && publication > statusStart);
  assert.ok(readme.slice(end + endMarker.length).trimStart().startsWith("## Control methodology status"));

  const damageRegion = readme.slice(begin, end + endMarker.length);
  const controlStatus = readme.slice(statusStart, publication);
  const tableHeader = "| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |";
  assert.equal(readme.split(tableHeader).length - 1, 1, "README has one damage heat table and no control table");
  assert.equal((damageRegion.match(/^\|---\|---\|---\|---\|---\|$/gm) ?? []).length, 1);
  assert.doesNotMatch(controlStatus, /^\|/m);
  assert.match(controlStatus, /v14\.1.*Control Reliability.*historical release evidence/s);
  assert.match(controlStatus, /v14\.1\.0 GitHub Release/);
  assert.match(controlStatus, /v14\.2 control methodology is being redesigned/);
  assert.match(controlStatus, /#32/);
  assert.match(controlStatus, /#39.*#40.*#41.*#42/s);
  assert.match(controlStatus, /No v14\.2 control headline, matrix, or HOT\/IDEAL\/COLD classification is authoritative until #42/);
  assert.match(harnessReadme, /maintained evaluator is damage-only/);
  assert.match(harnessReadme, /Control Authority v2 is separate/);
  assert.doesNotMatch(harnessReadme, /Control Reliability.*(?:current|maintained) (?:benchmark|methodology)/i);
});

test("retirement policy preserves history without indefinite dual-stack burden", async () => {
  const policy = await readFile("policy/superseded-implementations.md", "utf8");
  assert.match(policy, /Once a successor is viable.*retired from `main`/is);
  assert.match(policy, /frozen release branches, annotated tags, GitHub Releases, published evidence assets, and Git history/i);
  assert.match(policy, /principles and invariants.*without carrying forward obsolete code structure/is);
  assert.match(policy, /parallel old and new implementations, output-parity gates, golden outputs, compatibility aliases/is);
  assert.match(policy, /concrete reason.*named owner.*specific sunset date or release milestone/is);
  assert.match(policy, /temporary capability gap.*superseded or misleading methodology/is);
});

import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";

const parseVersion = (value: string): readonly number[] => value.split(".").map(Number);
const compareVersions = (left: string, right: string): number => {
  const a = parseVersion(left);
  const b = parseVersion(right);
  for (let index = 0; index < 3; index += 1) {
    const difference = (a[index] ?? 0) - (b[index] ?? 0);
    if (difference !== 0) return difference;
  }
  return 0;
};

const readReleaseStatus = (source: string): { published: string; development: string } => {
  const publishedLines = [...source.matchAll(/^- Current published release:.*$/gm)];
  const developmentLines = [...source.matchAll(/^- Current development line:.*$/gm)];
  assert.equal(publishedLines.length, 1, "README has exactly one published-release line");
  assert.equal(developmentLines.length, 1, "README has exactly one development-line entry");
  const published = [...source.matchAll(/^- Current published release: \*\*v(\d+\.\d+\.\d+)\*\*$/gm)].map(
    (match) => match[1]!
  );
  const development = [...source.matchAll(/^- Current development line: \*\*(v\d+\.\d+\.\d+|None)\*\*$/gm)].map(
    (match) => match[1]!
  );
  assert.equal(published.length, 1, "README published-release line is well formed");
  assert.equal(development.length, 1, "README development-line entry is well formed");
  return { published: published[0]!, development: development[0]! };
};

test("README and release process stay synchronized with canonical development status", async () => {
  const [{ authority }, readme, checklist, pullRequestTemplate] = await Promise.all([
    loadAuthority(),
    readFile("README.md", "utf8"),
    readFile("RELEASE_CHECKLIST.md", "utf8"),
    readFile(".github/pull_request_template.md", "utf8")
  ]);

  const { published, development } = readReleaseStatus(readme);
  assert.ok(compareVersions(published, authority.rules_version) <= 0, "published release cannot be newer than canonical authority");
  if (development !== "None") assert.equal(development, `v${authority.rules_version}`);

  for (const field of ["Development branch", "Release candidate branch", "Implementation pull request", "Release candidate status"]) {
    assert.doesNotMatch(
      readme,
      new RegExp(`^- ${field.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}:`, "m"),
      `README must not track mutable ${field.toLowerCase()} metadata`
    );
  }

  for (const heading of [
    "Release status",
    "Damage benchmark snapshot",
    "Control methodology status",
    "Publication interface",
    "Commands",
    "Architecture",
    "Licensing",
    "Development and release discipline"
  ]) {
    assert.match(readme, new RegExp(`^## ${heading}$`, "m"));
  }

  assert.match(readme, /Start Here/);
  assert.match(readme, /Category and Topic browsing/);
  assert.match(readme, /Name selector/);
  assert.match(readme, /global classification filters/);
  assert.match(readme, /Subclass Feature Reference/);
  assert.match(readme, /kinetic-vanguard-v<rules_version>/);
  assert.doesNotMatch(readme, /kinetic-vanguard-v\d+\.\d+\.\d+/);
  assert.doesNotMatch(readme, /Forked Lightning needs explicit failed-save wording/);

  for (const heading of ["Start of a development line", "Before marking a release pull request ready", "Publication", "Required release assets"]) {
    assert.match(checklist, new RegExp(`^## ${heading}$`, "m"));
  }
  for (const requirement of [
    "README.md",
    "KineticVanguard.yaml",
    "CHANGELOG.md",
    "Main branch gate",
    "Protect main",
    "LICENSE.md",
    "NOTICE.md",
    "policy/superseded-implementations.md",
    "readme:damage:check"
  ]) assert.ok(checklist.includes(requirement), requirement);
  assert.match(checklist, /mutable branch and pull-request pointers/i);
  assert.match(checklist, /every CI\/release workflow/i);
  assert.match(checklist, /frozen release branches, tags, GitHub Releases, published evidence assets, and Git history/i);

  assert.match(pullRequestTemplate, /RELEASE_CHECKLIST\.md/);
  assert.match(pullRequestTemplate, /README\.md/);
  assert.match(pullRequestTemplate, /Main branch gate/);
});

test("README exposes one synchronized damage snapshot and a static control status", async () => {
  const [{ authority }, readme, packageJsonSource, benchmarkConfigSource] = await Promise.all([
    loadAuthority(),
    readFile("README.md", "utf8"),
    readFile("package.json", "utf8"),
    readFile("harness/config/benchmark.json", "utf8")
  ]);
  const packageJson = JSON.parse(packageJsonSource) as {
    readonly scripts?: Readonly<Record<string, string>>;
  };
  const benchmarkConfig = JSON.parse(benchmarkConfigSource) as {
    readonly methodology: { readonly status: string };
    readonly kv_profile: { readonly id: string };
  };

  const beginMarker = "<!-- BEGIN GENERATED DAMAGE MATRIX -->";
  const endMarker = "<!-- END GENERATED DAMAGE MATRIX -->";
  const occurrences = (source: string, value: string): number => source.split(value).length - 1;
  assert.equal(occurrences(readme, beginMarker), 1, "README has exactly one damage-region start marker");
  assert.equal(occurrences(readme, endMarker), 1, "README has exactly one damage-region end marker");

  const begin = readme.indexOf(beginMarker);
  const end = readme.indexOf(endMarker);
  const controlStatus = readme.indexOf("## Control methodology status");
  const publication = readme.indexOf("## Publication interface");
  assert.ok(begin >= 0 && end > begin, "generated damage-region markers are ordered");
  assert.ok(controlStatus > end && publication > controlStatus);
  assert.ok(
    readme.slice(end + endMarker.length).trimStart().startsWith("## Control methodology status"),
    "static control status follows the generated damage region immediately"
  );
  const precedingLevelTwoHeadings = [...readme.slice(0, begin).matchAll(/^## (.+)$/gm)].map((match) => match[1]);
  assert.deepEqual(precedingLevelTwoHeadings, ["Release status"]);

  const region = readme.slice(begin, end + endMarker.length);
  assert.ok(region.includes(`**Canonical damage evidence** — rules **v${authority.rules_version}**.`));
  assert.doesNotMatch(
    region,
    /\*\*(?:Published|Unreleased development) snapshot\*\*|current published release/i,
    "analytical evidence is independent of release-status metadata"
  );
  assert.ok(region.includes(`Profile: \`${benchmarkConfig.kv_profile.id}\`.`));
  assert.ok(region.includes(`Numerical review status: \`${benchmarkConfig.methodology.status}\`.`));
  assert.match(region, /exact analytical full-roster damage results, not Monte Carlo estimates/i);
  assert.match(region, /^## Damage benchmark snapshot$/m);
  assert.doesNotMatch(region, /^### /m);

  const tableHeader = "| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |";
  assert.equal(occurrences(region, tableHeader), 1, "snapshot has exactly one single-target damage table");
  assert.equal((region.match(/^\|---\|---\|---\|---\|---\|$/gm) ?? []).length, 1);
  const lines = region.split("\n");
  const headerIndex = lines.indexOf(tableHeader);
  assert.ok(headerIndex >= 0);
  const expectedLevels = ["7", "11", "15", "20"];
  const publicResult = /^(?:IDEAL|N\/A|COLD \(-\d+(?:\.\d+)?%\)|HOT \(\+\d+(?:\.\d+)?%\))$/;
  const rows = lines.slice(headerIndex + 2, headerIndex + 6);
  assert.equal(rows.length, 4);
  rows.forEach((row, rowIndex) => {
    const cells = row.split("|").slice(1, -1).map((cell) => cell.trim());
    assert.equal(cells.length, 5);
    assert.equal(cells[0], expectedLevels[rowIndex]);
    for (const cell of cells.slice(1)) assert.match(cell, publicResult);
  });

  assert.match(region, /primary-target DPR at cluster size 1/);
  assert.match(region, /all other primary-target and aggregate-cluster results remain/);
  assert.match(region, /Battle Master and Eldritch Knight define the comparison envelope/);
  assert.match(region, /IDEAL.*falls between.*inclusive/s);
  assert.match(region, /COLD.*below both.*HOT.*above both/s);
  assert.match(region, /signed distance outside the nearest envelope boundary/);
  assert.match(region, /N\/A.*reserved for a comparison that cannot be evaluated/);
  assert.match(region, /Detailed release CSV, Markdown, and HTML reports retain raw/);
  assert.doesNotMatch(region, /KV DPR|KV as % of EK|KV as % of BM/);
  assert.doesNotMatch(region, /IDEAL \([^)]*%\)|COLD \(\+|HOT \(-/);

  for (const source of [
    "[`KineticVanguard.yaml`](KineticVanguard.yaml)",
    "[maintained damage harness guide](harness/README.md)",
    "[methodology configuration](harness/config/benchmark.json)",
    "[SRD target roster](harness/data/srd_targets.csv)",
    "[comparator assumptions](harness/comparators/fighter-subclasses.json)",
    "[`LICENSE.md`](LICENSE.md)",
    "[`NOTICE.md`](NOTICE.md)"
  ]) assert.ok(region.includes(source), `snapshot links to ${source}`);
  assert.match(region, /not affiliated with or endorsed by Wizards of the Coast/i);

  const status = readme.slice(controlStatus, publication);
  assert.match(status, /v14\.1.*Control Reliability.*historical release evidence/s);
  assert.match(status, /v14\.1\.0 GitHub Release/);
  assert.match(status, /v14\.2 control methodology is being redesigned/);
  for (const issue of ["#32", "#39", "#40", "#41", "#42"]) assert.ok(status.includes(issue));
  assert.match(status, /No v14\.2 control headline, matrix, or HOT\/IDEAL\/COLD classification is authoritative until #42/);
  assert.doesNotMatch(status, /^\|/m, "control status contains no table");

  assert.deepEqual(
    Object.keys(packageJson.scripts ?? {}).filter((name) => name.startsWith("readme:")).sort(),
    ["readme:damage", "readme:damage:check"]
  );
  assert.match(packageJson.scripts?.["readme:damage"] ?? "", /^python3 -m harness\.readme_damage --write(?:\s|$)/);
  assert.match(packageJson.scripts?.["readme:damage:check"] ?? "", /^python3 -m harness\.readme_damage --check(?:\s|$)/);
});

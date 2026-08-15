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

  if (development !== "None") {
    assert.equal(development, `v${authority.rules_version}`);
    assert.ok(readme.split("\n").includes(`- Development branch: \`${authority.rules_version}\``));
    assert.match(readme, /^- Implementation pull request: /m);
  }

  for (const heading of ["Release status", "Publication interface", "Commands", "Architecture", "Licensing", "Development and release discipline"]) {
    assert.match(readme, new RegExp(`^## ${heading}$`, "m"));
  }

  assert.match(readme, /Start Here/);
  assert.match(readme, /Category and Topic browsing/);
  assert.match(readme, /Name selector/);
  assert.match(readme, /global classification filters/);
  assert.match(readme, /Subclass Feature Reference/);
  assert.doesNotMatch(readme, /Forked Lightning needs explicit failed-save wording/);
  assert.doesNotMatch(readme, /Kinetic Vanguard \*\*v13\.0\.1\*\* is the current/);

  for (const heading of ["Before release", "Publication", "Required release assets"]) {
    assert.match(checklist, new RegExp(`^## ${heading}$`, "m"));
  }
  assert.match(checklist, /README\.md/);
  assert.match(checklist, /rules_version/);
  assert.match(checklist, /CHANGELOG\.md/);
  assert.match(checklist, /npm run typecheck/);
  assert.match(checklist, /damage and control benchmarks once when rules, comparator behavior, roster, methodology, or benchmark code changed/);
  assert.match(checklist, /generated release identity/);
  assert.match(checklist, /GitHub CI passes/);
  assert.match(checklist, /Squash-merge/);
  assert.match(checklist, /exact merged release commit/);
  assert.match(checklist, /release\/X\.Y\.Z/);
  assert.match(checklist, /vX\.Y\.Z/);
  assert.match(checklist, /GitHub Release/);
  assert.match(checklist, /README published status/);
  assert.match(checklist, /LICENSE\.md/);
  assert.match(checklist, /NOTICE\.md/);

  assert.match(pullRequestTemplate, /RELEASE_CHECKLIST\.md/);
  assert.match(pullRequestTemplate, /actual release and publication work/);
});

test("README exposes one synchronized headline balance snapshot", async () => {
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

  const beginMarker = "<!-- BEGIN GENERATED BALANCE MATRICES -->";
  const endMarker = "<!-- END GENERATED BALANCE MATRICES -->";
  const occurrences = (source: string, value: string): number => source.split(value).length - 1;
  assert.equal(occurrences(readme, beginMarker), 1, "README has exactly one balance-region start marker");
  assert.equal(occurrences(readme, endMarker), 1, "README has exactly one balance-region end marker");

  const begin = readme.indexOf(beginMarker);
  const end = readme.indexOf(endMarker);
  const publication = readme.indexOf("## Publication interface");
  assert.ok(begin >= 0 && end > begin, "generated balance-region markers are ordered");
  assert.ok(publication > end, "balance snapshot appears before implementation-oriented README sections");
  const precedingLevelTwoHeadings = [...readme.slice(0, begin).matchAll(/^## (.+)$/gm)].map(
    (match) => match[1]
  );
  assert.deepEqual(
    precedingLevelTwoHeadings,
    ["Release status"],
    "balance snapshot stays near the top, immediately after release orientation"
  );

  const region = readme.slice(begin, end + endMarker.length);
  const { published, development } = readReleaseStatus(readme);
  assert.ok(region.includes(`canonical rules **v${authority.rules_version}**`));
  if (development === "None") {
    assert.ok(region.includes("**Published snapshot**"));
    assert.equal(published, authority.rules_version);
  } else {
    assert.equal(development, `v${authority.rules_version}`);
    assert.ok(region.includes("**Unreleased development snapshot**"));
    assert.ok(region.includes(`current published release **v${published}**`));
  }
  assert.ok(region.includes(`Profile: \`${benchmarkConfig.kv_profile.id}\`.`));
  assert.ok(region.includes(`Numerical review status: \`${benchmarkConfig.methodology.status}\`.`));
  assert.match(region, /exact analytical full-roster results, not Monte Carlo estimates/i);

  for (const heading of [
    "Balance benchmark snapshot",
    "Single-Target Damage",
    "Control Reliability"
  ]) {
    assert.match(region, new RegExp("^#{2,4} " + heading.replace(/[.*+?^$(){}|[\]\\]/g, "\\$&") + "$", "m"));
  }

  const tableHeader = "| Level | Cryokinesis | Pyrokinesis | Psychokinesis | Electrokinesis |";
  assert.equal(occurrences(region, tableHeader), 2, "snapshot has one single-target damage matrix and one control matrix");
  assert.doesNotMatch(region, /^#### Cluster size /m);

  const lines = region.split("\n");
  const headerIndexes = lines.flatMap((line, index) => line === tableHeader ? [index] : []);
  const expectedLevels = ["7", "11", "15", "20"];
  const publicResult = /^(?:IDEAL|N\/A|COLD \(-\d+(?:\.\d+)?%\)|HOT \(\+\d+(?:\.\d+)?%\))$/;
  let sawCold = false;
  let sawHot = false;
  for (const headerIndex of headerIndexes) {
    assert.equal(lines[headerIndex + 1], "|---|---|---|---|---|");
    const rows = lines.slice(headerIndex + 2, headerIndex + 6);
    assert.equal(rows.length, 4);
    rows.forEach((row, rowIndex) => {
      const cells = row.split("|").slice(1, -1).map((cell) => cell.trim());
      assert.equal(cells.length, 5, "heat row has one level and four discipline results");
      assert.equal(cells[0], expectedLevels[rowIndex]);
      for (const cell of cells.slice(1)) {
        assert.match(cell, publicResult, "README heat cell contains only a public balance result");
        sawCold ||= cell.startsWith("COLD ");
        sawHot ||= cell.startsWith("HOT ");
      }
    });
  }
  assert.ok(sawCold, "current snapshot exposes COLD results");
  assert.ok(sawHot, "current snapshot exposes HOT results");

  const damageStart = region.indexOf("### Single-Target Damage");
  const controlStart = region.indexOf("### Control Reliability");
  assert.ok(damageStart >= 0 && controlStart > damageStart);
  assert.match(region, /primary-target DPR at cluster size 1/);
  assert.match(region, /This single-target benchmark evaluates each configured control package/);
  assert.match(region, /All other primary-target and aggregate-cluster results remain in the generated detailed release reports/);
  assert.match(region, /Battle Master and Eldritch Knight define the comparison envelope/);
  assert.match(region, /IDEAL.*falls between.*inclusive/s);
  assert.match(region, /COLD.*below both.*HOT.*above both/s);
  assert.match(region, /signed distance outside the nearest envelope boundary/);
  assert.match(region, /N\/A.*reserved for a comparison that cannot be evaluated/);
  assert.match(region, /Signature Riders were already 0-Psi and repeatable before issue #58/);
  assert.match(region, /Battle Master maneuvers receive legal hit-gated retries/);
  assert.match(region, /Eldritch Knight keeps one Blindness\/Deafness cast and uses all ordinary primer attacks for Eldritch Strike/);
  assert.match(region, /Published v14\.1 used simpler one-shot approximations/);
  assert.match(region, /not assumed to be additively separable/);
  assert.match(
    region,
    /Control Reliability measures how often the configured control package takes effect\. It does not measure the relative severity, duration, area, or strategic value of different control effects\. A HOT result is a balance-review signal, not an automatic finding that the feature is overpowered\./
  );
  assert.match(region, /Detailed release CSV, Markdown, and HTML reports retain raw/);
  assert.doesNotMatch(region, /ORDER CHECK/);
  assert.doesNotMatch(region, /KV DPR|KV control %|KV as % of EK|KV as % of BM/);
  assert.doesNotMatch(region, /IDEAL \([^)]*%\)/);
  assert.doesNotMatch(region, /COLD \(\+|HOT \(-/);
  for (const comparator of ["Eldritch Knight", "Battle Master"]) {
    assert.match(region, new RegExp(comparator));
  }

  for (const source of [
    "[`KineticVanguard.yaml`](KineticVanguard.yaml)",
    "[maintained harness guide](harness/README.md)",
    "[methodology configuration](harness/config/benchmark.json)",
    "[SRD target roster](harness/data/srd_targets.csv)",
    "[comparator assumptions](harness/comparators/fighter-subclasses.json)",
    "[`LICENSE.md`](LICENSE.md)",
    "[`NOTICE.md`](NOTICE.md)"
  ]) {
    assert.ok(region.includes(source), `snapshot links to ${source}`);
  }
  assert.match(region, /not affiliated with or endorsed by Wizards of the Coast/i);
  assert.match(
    region,
    /No project license purports to grant rights in Wizards-owned material outside the System Reference Document/
  );
  assert.match(region, /LICENSE\.md.*component boundaries.*NOTICE\.md.*attribution and notices/s);
  assert.doesNotMatch(region, /Hunter(?: Ranger)?|Open Hand(?: Monk)?/i);

  assert.match(
    packageJson.scripts?.["readme:benchmarks"] ?? "",
    /^python3 -m harness\.readme_matrices --write(?:\s|$)/
  );
  assert.match(
    packageJson.scripts?.["readme:benchmarks:check"] ?? "",
    /^python3 -m harness\.readme_matrices --check(?:\s|$)/
  );
});

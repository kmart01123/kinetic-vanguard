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

type BalanceSnapshot =
  | { kind: "published"; rulesVersion: string }
  | { kind: "development"; rulesVersion: string; publishedVersion: string };

const readBalanceSnapshot = (region: string): BalanceSnapshot => {
  const identityLines = [
    ...region.matchAll(/^\*\*(?:Published|Unreleased development) snapshot\*\*.*$/gm)
  ].map((match) => match[0]);
  assert.equal(identityLines.length, 1, "balance region has exactly one evidence-identity line");
  const line = identityLines[0]!;
  const published = line.match(/^\*\*Published snapshot\*\* — canonical rules \*\*v(\d+\.\d+\.\d+)\*\*\.$/);
  if (published) return { kind: "published", rulesVersion: published[1]! };
  const development = line.match(
    /^\*\*Unreleased development snapshot\*\* — canonical rules \*\*v(\d+\.\d+\.\d+)\*\*; current published release \*\*v(\d+\.\d+\.\d+)\*\*\.$/
  );
  assert.ok(development, "balance evidence identity is well formed");
  return { kind: "development", rulesVersion: development[1]!, publishedVersion: development[2]! };
};

const assertBalanceSnapshotState = (
  snapshot: BalanceSnapshot,
  release: { published: string; development: string },
  authorityVersion: string
): void => {
  if (snapshot.kind === "published") {
    assert.equal(snapshot.rulesVersion, release.published, "published evidence matches the published release");
    if (release.development === "None") assert.equal(snapshot.rulesVersion, authorityVersion);
    else {
      assert.equal(release.development, `v${authorityVersion}`);
      assert.ok(
        compareVersions(snapshot.rulesVersion, authorityVersion) < 0,
        "retained published evidence must not claim to represent newer development authority"
      );
    }
    return;
  }
  assert.notEqual(release.development, "None", "development evidence requires an active development line");
  assert.equal(release.development, `v${authorityVersion}`);
  assert.equal(snapshot.rulesVersion, authorityVersion, "development evidence matches canonical authority");
  assert.equal(snapshot.publishedVersion, release.published, "development evidence identifies the published release");
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
    assert.ok(readme.split("\n").includes(`- Implementation status: Active v${authority.rules_version.replace(/\.0$/u, "")} development`));
    assert.doesNotMatch(readme, /^- Release candidate (?:branch|status):/m);
  }
  assert.doesNotMatch(readme, /^- Development branch:/m);

  for (const heading of ["Release status", "Publication interface", "Commands", "Architecture", "Licensing", "Development and release discipline"]) {
    assert.match(readme, new RegExp(`^## ${heading}$`, "m"));
  }

  assert.match(readme, /Start Here/);
  assert.match(readme, /Calculator \/ Feature Deck/);
  assert.match(readme, /reference-only cards/);
  assert.match(readme, /Category and Topic browsing/);
  assert.match(readme, /Name selector/);
  assert.match(readme, /global classification filters/);
  assert.match(readme, /Subclass Feature Reference/);
  assert.doesNotMatch(readme, /Forked Lightning needs explicit failed-save wording/);
  assert.doesNotMatch(readme, /Kinetic Vanguard \*\*v13\.0\.1\*\* is the current/);

  for (const heading of ["Prepare and freeze the candidate", "Verify on GitHub", "Independent review", "Publish deliberately"]) {
    assert.match(checklist, new RegExp(`^## ${heading}$`, "m"));
  }
  assert.match(checklist, /rules_version/);
  assert.match(checklist, /CHANGELOG\.md/);
  assert.match(checklist, /fresh analytical evidence only when that input-aware policy requires it/);
  assert.match(checklist, /Main branch gate/);
  assert.match(checklist, /Squash-merge/);
  assert.match(checklist, /merged commit SHA/);
  assert.match(checklist, /release\/X\.Y\.Z/);
  assert.match(checklist, /vX\.Y\.Z/);
  assert.match(checklist, /release-verify\.yml/);
  assert.match(checklist, /workflow run ID/);
  assert.match(checklist, /artifact digest/);
  assert.match(checklist, /sha256sum -c SHA256SUMS/);
  assert.match(checklist, /gh release create/);
  assert.match(checklist, /GitHub Release/);
  assert.match(checklist, /README published status/);
  assert.match(checklist, /LICENSE\.md/);
  assert.match(checklist, /NOTICE\.md/);
  assert.doesNotMatch(checklist, /build-manifest|filtered-search-integrity|coverage-ledger|release-evidence/i);

  assert.match(pullRequestTemplate, /RELEASE_CHECKLIST\.md/);
  assert.match(pullRequestTemplate, /actual release and publication work/);
});

test("balance snapshot identity separates development rules from benchmark evidence", () => {
  assertBalanceSnapshotState(
    readBalanceSnapshot("**Published snapshot** — canonical rules **v14.2.0**."),
    { published: "14.2.0", development: "v14.3.0" },
    "14.3.0"
  );
  assertBalanceSnapshotState(
    readBalanceSnapshot("**Unreleased development snapshot** — canonical rules **v14.3.0**; current published release **v14.2.0**."),
    { published: "14.2.0", development: "v14.3.0" },
    "14.3.0"
  );
  assert.throws(() =>
    assertBalanceSnapshotState(
      readBalanceSnapshot("**Published snapshot** — canonical rules **v14.3.0**."),
      { published: "14.2.0", development: "v14.3.0" },
      "14.3.0"
    )
  );
  assert.throws(() =>
    assertBalanceSnapshotState(
      readBalanceSnapshot("**Unreleased development snapshot** — canonical rules **v14.2.0**; current published release **v14.2.0**."),
      { published: "14.2.0", development: "v14.3.0" },
      "14.3.0"
    )
  );
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
  const release = readReleaseStatus(readme);
  const snapshot = readBalanceSnapshot(region);
  assertBalanceSnapshotState(snapshot, release, authority.rules_version);
  if (snapshot.kind === "published" && release.development !== "None") {
    assert.ok(
      region.includes(
        `The current ${release.development} development line contains rule changes not yet reflected in this published benchmark snapshot.`
      )
    );
  }
  assert.ok(region.includes("Target profile: `headline`."));
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
    "[SRD creature profiles](harness/data/srd_creature_rosters.json)",
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

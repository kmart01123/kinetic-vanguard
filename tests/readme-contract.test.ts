import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
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
    "Control capability status",
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
  assert.match(checklist, /npm run harness:damage -- --output-dir <private-output>/);
  assert.match(checklist, /npm run readme:damage -- --report-input <private-output>\/run-manifest\.json/);
  assert.match(checklist, /npm run readme:damage:check -- --report-input <private-output>\/run-manifest\.json/);
  assert.match(checklist, /both synchronization commands must read the same manifest and must not evaluate/i);

  assert.match(pullRequestTemplate, /RELEASE_CHECKLIST\.md/);
  assert.match(pullRequestTemplate, /README\.md/);
  assert.match(pullRequestTemplate, /Main branch gate/);
});

test("README keeps current authority, historical review basis, and publication status distinct", async () => {
  const [{ authority }, readme, packageJsonSource, benchmarkConfigSource, damageReviewSource, consumerRequirementsSource, harnessReadme, readmeWriter] = await Promise.all([
    loadAuthority(),
    readFile("README.md", "utf8"),
    readFile("package.json", "utf8"),
    readFile("harness/config/benchmark.json", "utf8"),
    readFile("harness/provenance/damage-review.json", "utf8"),
    readFile("harness/config/creature-consumers.json", "utf8"),
    readFile("harness/README.md", "utf8"),
    readFile("harness/readme_damage.py", "utf8")
  ]);
  const packageJson = JSON.parse(packageJsonSource) as {
    readonly scripts?: Readonly<Record<string, string>>;
  };
  const benchmarkConfig = JSON.parse(benchmarkConfigSource) as {
    readonly kv_profile: { readonly id: string };
    readonly methodology: { readonly target_profile_id: string };
  };
  const damageReview = JSON.parse(damageReviewSource) as {
    readonly pinned_srd: {
      readonly consumer_requirements_version: string;
      readonly consumer_requirements_registry_sha256: string;
      readonly damage_consumer_requirements_sha256: string;
    };
    readonly current_damage_review: {
      readonly rules_version: string;
      readonly status: string;
      readonly review_date: string;
      readonly durable_record: string;
    };
    readonly expanded_roster_baseline_evidence: {
      readonly rules_version: string;
      readonly release_tag: string;
      readonly release_commit: string;
      readonly source_url: string;
      readonly filename: string;
      readonly bytes: number;
      readonly rows: number;
      readonly sha256: string;
      readonly evaluator: string;
    };
    readonly current_development_disposition: {
      readonly current_rules_version: string;
      readonly review_basis_rules_version: string;
      readonly review_disposition: string;
      readonly fresh_full_roster_run: boolean;
      readonly fresh_numerical_certification: boolean;
      readonly fresh_monte_carlo_certification: boolean;
      readonly reason: string;
      readonly durable_record: string;
      readonly invalidated_run_evidence: null | {
        readonly invalidation_disposition: string;
        readonly reason: string;
        readonly numerical_evidence_role: string;
        readonly numerical_defect_demonstrated: boolean;
        readonly run_manifest_sha256: string;
        readonly consumer_requirements_sha256: string;
        readonly rules_version: string;
        readonly target_profile_id: string;
        readonly target_profile_sha256: string;
        readonly damage_target_projection_sha256: string;
        readonly evaluator: string;
        readonly evaluator_implementation_sha256: string;
        readonly output_sha256: Readonly<Record<string, string>>;
        readonly row_counts: { readonly detail: number; readonly matrix: number };
      };
      readonly fresh_run_evidence: null | {
        readonly run_manifest_sha256: string;
        readonly baseline_evidence_sha256: string;
        readonly rules_version: string;
        readonly target_profile_id: string;
        readonly target_profile_sha256: string;
        readonly damage_target_projection_sha256: string;
        readonly consumer_requirements_version: string;
        readonly damage_consumer_requirements_sha256: string;
        readonly evaluator: string;
        readonly evaluator_implementation_sha256: string;
        readonly output_sha256: Readonly<Record<string, string>>;
        readonly row_counts: { readonly detail: number; readonly matrix: number };
      };
    };
  };
  const review = damageReview.current_damage_review;
  const baseline = damageReview.expanded_roster_baseline_evidence;
  const disposition = damageReview.current_development_disposition;
  assert.equal(damageReview.pinned_srd.consumer_requirements_version, "1.0.0");
  assert.equal(
    damageReview.pinned_srd.consumer_requirements_registry_sha256,
    createHash("sha256").update(consumerRequirementsSource).digest("hex")
  );
  assert.match(damageReview.pinned_srd.damage_consumer_requirements_sha256, /^[0-9a-f]{64}$/);
  const carriedForward = "CARRIED_FORWARD_WITHOUT_FRESH_NUMERICAL_REVIEW";
  const freshExpandedRoster = "FRESH_EXPANDED_ROSTER_RUN_WITHOUT_INDEPENDENT_CERTIFICATION";
  const invalidatedPremerge = "invalidated_premerge_provenance_boundary_correction";
  assert.equal(disposition.current_rules_version, authority.rules_version);
  assert.equal(disposition.review_basis_rules_version, review.rules_version);
  assert.notEqual(disposition.current_rules_version, disposition.review_basis_rules_version);
  assert.equal(review.rules_version, "14.1.0");
  assert.equal(review.review_date, "2026-08-07");
  assert.equal(review.durable_record, "GitHub PR #20");
  assert.deepEqual(baseline, {
    rules_version: "14.1.0",
    release_tag: "v14.1.0",
    release_commit: "40d0d191e7ef3ba7be7a3ed6f5f4c0e1c6059bef",
    source_url: "https://github.com/kmart01123/kinetic-vanguard/releases/tag/v14.1.0",
    filename: "kv-14-1-0-damage-comparison-matrix.csv",
    bytes: 265819,
    rows: 96,
    sha256: "e0a9aec2d5c8da9409b8158163d44085001c26686385ddacb7108ff48d2326b4",
    evaluator: "exact_analytical_enumeration"
  });
  assert.ok(
    [carriedForward, invalidatedPremerge, freshExpandedRoster].includes(disposition.review_disposition),
    `supported development disposition: ${disposition.review_disposition}`
  );
  assert.equal(disposition.fresh_full_roster_run, disposition.review_disposition === freshExpandedRoster);
  assert.equal(disposition.fresh_numerical_certification, false);
  assert.equal(disposition.fresh_monte_carlo_certification, false);
  assert.ok(disposition.reason.length > 0);
  assert.ok(disposition.durable_record.length > 0);
  if (disposition.review_disposition === carriedForward) {
    assert.equal(disposition.invalidated_run_evidence, null);
    assert.equal(disposition.fresh_run_evidence, null);
  } else if (disposition.review_disposition === invalidatedPremerge) {
    const invalidated = disposition.invalidated_run_evidence;
    assert.ok(invalidated, "invalidated disposition preserves exact comparison evidence");
    assert.equal(disposition.fresh_run_evidence, null);
    assert.equal(invalidated.invalidation_disposition, invalidatedPremerge);
    assert.equal(invalidated.numerical_evidence_role, "comparison_evidence_only");
    assert.equal(invalidated.numerical_defect_demonstrated, false);
    assert.equal(invalidated.rules_version, authority.rules_version);
    assert.equal(invalidated.target_profile_id, benchmarkConfig.methodology.target_profile_id);
    assert.equal(invalidated.evaluator, "exact_analytical_enumeration");
    assert.deepEqual(invalidated.row_counts, { detail: 564, matrix: 96 });
    assert.deepEqual(Object.keys(invalidated.output_sha256).sort(), ["detail_csv", "matrix_csv", "matrix_html", "matrix_markdown"]);
    for (const digest of [
      invalidated.run_manifest_sha256,
      invalidated.consumer_requirements_sha256,
      invalidated.target_profile_sha256,
      invalidated.damage_target_projection_sha256,
      invalidated.evaluator_implementation_sha256,
      ...Object.values(invalidated.output_sha256)
    ]) assert.match(digest, /^[0-9a-f]{64}$/);
  } else {
    assert.ok(disposition.invalidated_run_evidence, "replacement evidence preserves the invalidated predecessor");
    const evidence = disposition.fresh_run_evidence;
    assert.ok(evidence, "fresh expanded-roster disposition binds exact run evidence");
    assert.equal(evidence.rules_version, authority.rules_version);
    assert.equal(evidence.target_profile_id, benchmarkConfig.methodology.target_profile_id);
    assert.equal(evidence.evaluator, "exact_analytical_enumeration");
    assert.equal(evidence.consumer_requirements_version, damageReview.pinned_srd.consumer_requirements_version);
    assert.deepEqual(evidence.row_counts, { detail: 564, matrix: 96 });
    assert.deepEqual(Object.keys(evidence.output_sha256).sort(), ["detail_csv", "matrix_csv", "matrix_html", "matrix_markdown"]);
    for (const digest of [
      evidence.run_manifest_sha256,
      evidence.baseline_evidence_sha256,
      evidence.target_profile_sha256,
      evidence.damage_target_projection_sha256,
      evidence.damage_consumer_requirements_sha256,
      evidence.evaluator_implementation_sha256,
      ...Object.values(evidence.output_sha256)
    ]) assert.match(digest, /^[0-9a-f]{64}$/);
  }

  const beginMarker = "<!-- BEGIN GENERATED DAMAGE MATRIX -->";
  const endMarker = "<!-- END GENERATED DAMAGE MATRIX -->";
  const occurrences = (source: string, value: string): number => source.split(value).length - 1;
  assert.equal(occurrences(readme, beginMarker), 1, "README has exactly one damage-region start marker");
  assert.equal(occurrences(readme, endMarker), 1, "README has exactly one damage-region end marker");

  const begin = readme.indexOf(beginMarker);
  const end = readme.indexOf(endMarker);
  const controlStatus = readme.indexOf("## Control capability status");
  const publication = readme.indexOf("## Publication interface");
  assert.ok(begin >= 0 && end > begin, "generated damage-region markers are ordered");
  assert.ok(controlStatus > end && publication > controlStatus);
  assert.ok(
    readme.slice(end + endMarker.length).trimStart().startsWith("## Control capability status"),
    "static control status follows the generated damage region immediately"
  );
  const precedingLevelTwoHeadings = [...readme.slice(0, begin).matchAll(/^## (.+)$/gm)].map((match) => match[1]);
  assert.deepEqual(precedingLevelTwoHeadings, ["Release status"]);

  const region = readme.slice(begin, end + endMarker.length);
  assert.ok(region.includes(`**Current canonical damage authority:** rules **v${authority.rules_version}**.`));
  if (!disposition.fresh_full_roster_run) {
    const plainRegion = region.replace(/[*_`]/g, "");
    const currentRulesPattern = disposition.current_rules_version.split(".").join("\\.");
    assert.doesNotMatch(
      plainRegion,
      new RegExp(`\\bgenerated\\s+under\\s+rules\\s+v${currentRulesPattern}\\b`, "i"),
      "carried-forward public text cannot claim generation under the current rules version"
    );
  }
  assert.doesNotMatch(
    region,
    /\*\*(?:Published|Unreleased development) snapshot\*\*|current published release|Current development line/i,
    "analytical evidence is independent of release-status metadata"
  );
  assert.ok(
    region.includes(`Profile: \`${benchmarkConfig.kv_profile.id}\`.`)
      || region.includes(`Kinetic Vanguard profile: \`${benchmarkConfig.kv_profile.id}\`.`),
    "snapshot identifies the Kinetic Vanguard benchmark profile"
  );
  if (disposition.review_disposition === carriedForward) {
    assert.ok(region.includes(
      `Numerical-review basis: reviewed rules **v${review.rules_version}** evidence (\`${review.status}\`).`
    ));
    assert.ok(region.includes(
      `Snapshot values are carried forward from that reviewed evidence and were not regenerated for **v${authority.rules_version}**. No fresh **v${authority.rules_version}** full-roster run, numerical certification, or Monte Carlo certification was performed.`
    ));
    assert.ok(region.includes(`Reason: ${disposition.reason}`));
    assert.doesNotMatch(region, /replacement exact analytical run/);
  } else if (disposition.review_disposition === invalidatedPremerge) {
    const invalidated = disposition.invalidated_run_evidence!;
    assert.ok(region.includes(`\`${invalidatedPremerge}\``));
    assert.ok(region.includes(
      `Its manifest SHA-256 is \`${invalidated.run_manifest_sha256}\`.`
    ));
    assert.match(region, /retained only as comparison evidence/);
    assert.match(region, /no numerical defect has been demonstrated/i);
    assert.ok(region.includes(
      `No corrected-contract replacement **v${authority.rules_version}** full-roster run has been performed.`
    ));
    assert.doesNotMatch(region, /replacement exact analytical run/);
  } else {
    assert.ok(region.includes(
      `A corrected-contract replacement exact analytical run for **v${authority.rules_version}**`
    ));
    assert.ok(region.includes(
      `used all `
    ));
    assert.ok(region.includes(
      ` targets in \`${benchmarkConfig.methodology.target_profile_id}\`. It replaces the invalidated pre-merge comparison snapshot`
    ));
    assert.ok(region.includes(
      `independently reviewed rules **v${review.rules_version}** evidence remains the review basis (\`${review.status}\`)`
    ));
    assert.match(region, /No fresh independent numerical or Monte Carlo certification is claimed\./);
    assert.match(region, /Run-manifest SHA-256: `[0-9a-f]{64}`\./);
    assert.match(region, /^Target profile: `[^`]+` \(\d+ source-ordered targets\)\.$/m);
    assert.ok(region.includes(`Target profile: \`${benchmarkConfig.methodology.target_profile_id}\``));
    assert.doesNotMatch(region, /Snapshot values are carried forward|No fresh v14\.2 full-roster run/);
  }
  assert.doesNotMatch(region, /Numerical review status:/i);
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
  assert.match(region, /all other primary-target and aggregate-cluster (?:results|values) remain/);
  assert.match(region, /Battle Master and Eldritch Knight define the comparison envelope/);
  assert.match(region, /IDEAL.*falls between.*inclusive/s);
  assert.match(region, /COLD.*below both.*HOT.*above both/s);
  assert.match(region, /signed distance outside the nearest envelope boundary/);
  assert.match(region, /N\/A.*reserved for a comparison that cannot be evaluated/);
  if (disposition.review_disposition === invalidatedPremerge) {
    assert.match(region, /invalidated run's detailed analytical CSV, Markdown, and HTML reports preserve raw/);
  } else {
    assert.match(region, /Generated detailed analytical CSV, Markdown, and HTML reports retain raw/);
  }
  assert.doesNotMatch(region, /KV DPR|KV as % of EK|KV as % of BM/);
  assert.doesNotMatch(region, /IDEAL \([^)]*%\)|COLD \(\+|HOT \(-/);

  for (const source of [
    "[`KineticVanguard.yaml`](KineticVanguard.yaml)",
    "[maintained damage harness guide](harness/README.md)",
    "[methodology configuration](harness/config/benchmark.json)",
    "[SRD creature catalog audit](docs/srd-creature-catalog-audit.md)",
    "[comparator assumptions](harness/comparators/fighter-subclasses.json)",
    "[`LICENSE.md`](LICENSE.md)",
    "[`NOTICE.md`](NOTICE.md)"
  ]) assert.ok(region.includes(source), `snapshot links to ${source}`);
  assert.match(region, /not affiliated with or endorsed by Wizards of the Coast/i);

  for (const statement of [
    `canonical rules **v${disposition.current_rules_version}**`,
    `numerical-review basis **v${disposition.review_basis_rules_version}**`
  ]) assert.ok(harnessReadme.includes(statement), `harness guide states ${statement}`);
  if (disposition.review_disposition === carriedForward) {
    assert.match(harnessReadme, /No fresh v14\.2 full-roster run, numerical certification, or Monte Carlo certification was performed/);
  } else if (disposition.review_disposition === invalidatedPremerge) {
    assert.match(harnessReadme, /invalidated_premerge_provenance_boundary_correction/);
    assert.match(harnessReadme, /No corrected-contract replacement v14\.2 full-roster run has been performed/);
    assert.match(harnessReadme, /no numerical defect has been demonstrated/i);
  } else {
    assert.match(harnessReadme, /fresh expanded-roster|corrected-contract replacement exact analytical run/i);
    assert.doesNotMatch(harnessReadme, /No fresh v14\.2 full-roster run/);
  }
  for (const path of [
    "data/srd_creatures.json",
    "data/srd_creature_rosters.json",
    "config/creature-consumers.json",
    "provenance/srd-creatures.json"
  ]) assert.ok(harnessReadme.includes(path), `harness guide links the maintained ${path}`);
  for (const controlTargetContract of [
    "passive Perception",
    "canonically sorted, source-explicit skill facts",
    "Live Advantage, Disadvantage, roll mode",
    "scenario/event state",
    "429 explicit skill facts across 216 creatures",
    "105 explicit skill facts across 40 targets",
    "165 explicit skill facts across 71 targets"
  ]) assert.ok(harnessReadme.includes(controlTargetContract), `harness guide states ${controlTargetContract}`);
  assert.match(harnessReadme, /fall(?:s)? back to its associated raw ability modifier/);
  for (const retired of ["srd_targets.csv", "srd_control_targets.json", "srd-control-targets.json"]) {
    assert.ok(!readme.includes(retired), `README does not reference retired ${retired}`);
    assert.ok(!harnessReadme.includes(retired), `harness guide does not reference retired ${retired}`);
  }

  const status = readme.slice(controlStatus, publication);
  assert.match(status, /v14\.1.*Control Reliability.*historical release evidence/s);
  assert.match(status, /v14\.1\.0 GitHub Release/);
  assert.match(status, /v14\.2.*no maintained control evaluator/s);
  assert.match(status, /no current v14\.2 control result/);
  assert.match(status, /retired runtime.*no compatibility or fallback path/s);
  assert.match(status, /Control Authority v2.*ControlTarget.*static inputs only/s);
  assert.match(status, /not a benchmark methodology or execution runtime/);
  assert.match(status, /minimum execution contract.*named-condition runner.*designed separately/s);
  assert.match(status, /neither is implemented/);
  assert.doesNotMatch(status, /being redesigned.*#42|until #42 promotes|shared control[- ]engine/is);
  assert.doesNotMatch(status, /^\|/m, "control status contains no table");

  assert.deepEqual(
    Object.keys(packageJson.scripts ?? {}).filter((name) => name.startsWith("readme:")).sort(),
    ["readme:damage", "readme:damage:check"]
  );
  assert.match(packageJson.scripts?.["readme:damage"] ?? "", /^python3 -m harness\.readme_damage --write(?:\s|$)/);
  assert.match(packageJson.scripts?.["readme:damage:check"] ?? "", /^python3 -m harness\.readme_damage --check(?:\s|$)/);
  for (const script of [packageJson.scripts?.["readme:damage"], packageJson.scripts?.["readme:damage:check"]]) {
    assert.doesNotMatch(script ?? "", /damage_harness|harness:damage|--output-dir/);
  }
  assert.match(readmeWriter, /parser\.add_argument\("--report-input", type=Path, required=True\)/);
  assert.match(readmeWriter, /load_verified_damage_run\(args\.report_input\)/);
  assert.doesNotMatch(readmeWriter, /\bfrom \.damage_harness import run\b|\bdamage_harness\.run\s*\(|(?<![\w.])run\s*\(/);
  const missingReportInput = spawnSync(
    "python3",
    ["-m", "harness.readme_damage", "--check"],
    { encoding: "utf8" }
  );
  assert.equal(missingReportInput.status, 2);
  assert.match(missingReportInput.stderr, /the following arguments are required: --report-input/);
});

test("expanded-roster damage delta audit is compact, complete, and provenance-bound", async () => {
  const [source, reviewSource, harnessReadme, auditDoc] = await Promise.all([
    readFile("harness/provenance/damage-delta-v14.1-to-v14.2.json", "utf8"),
    readFile("harness/provenance/damage-review.json", "utf8"),
    readFile("harness/README.md", "utf8"),
    readFile("docs/srd-creature-catalog-audit.md", "utf8")
  ]);
  const audit = JSON.parse(source) as any;
  const review = JSON.parse(reviewSource) as any;
  const invalidatedEvidence = review.current_development_disposition.invalidated_run_evidence;
  const replacementEvidence = review.current_development_disposition.fresh_run_evidence;

  assert.equal(audit.schema_version, "1.3.0");
  assert.deepEqual(audit.evidence_disposition, {
    current: "FRESH_EXPANDED_ROSTER_RUN_WITHOUT_INDEPENDENT_CERTIFICATION",
    numerical_evidence_role: "corrected_contract_replacement_evidence",
    numerical_defect_demonstrated: false,
    corrected_contract_replacement_run_performed: true,
    invalidated_premerge_comparison_preserved: true,
    superseded_audit_sha256: "fa1a207881a9de81b035f4b4e11526eef18d997c20607476ae50f45a901429d3",
    reason: "The completed corrected-contract replacement differs from the invalidated pre-merge run only in corrected provenance identities and resulting manifest/report digests; all 564 detail rows and 96 matrix rows are numerically and classificationally identical. A separately recorded first attempt failed before producing output."
  });
  assert.equal(audit.method.result_generation, "read-only comparison of existing artifacts; evaluator was not invoked");
  assert.match(audit.method.primary_target_population, /cluster sizes 1, 3, and 6/);
  assert.match(audit.method.absolute_delta_population, /288 entity values overall/);
  assert.deepEqual(audit.target_counts_by_level, [
    { level: 7, before: 8, after: 12, delta: 4 },
    { level: 11, before: 6, after: 12, delta: 6 },
    { level: 15, before: 6, after: 11, delta: 5 },
    { level: 20, before: 8, after: 12, delta: 4 }
  ]);
  assert.equal(audit.validation.matching_row_identity_sets, true);
  assert.equal(audit.validation.baseline_matrix_row_count, 96);
  assert.equal(audit.validation.invalidated_premerge_comparison_matrix_row_count, 96);
  assert.equal(audit.validation.invalidated_premerge_comparison_detail_row_count, 564);
  assert.equal(audit.validation.corrected_contract_replacement_matrix_row_count, 96);
  assert.equal(audit.validation.corrected_contract_replacement_detail_row_count, 564);
  assert.deepEqual(audit.validation.invalidated_to_replacement_exact_equality, {
    detail_compared_fields_per_row: 30,
    detail_comparison_count: 16920,
    detail_row_count: 564,
    differing_provenance_fields: [
      "Provenance Consumer Requirements Sha256 -> Provenance Damage Consumer Requirements Sha256",
      "Provenance Damage Target Projection Sha256",
      "Provenance Evaluator Implementation Sha256"
    ],
    matrix_compared_fields_per_row: 17,
    matrix_comparison_count: 1632,
    matrix_row_count: 96,
    notice_fields_equal: true,
    ordered_row_identities_equal: true,
    result_and_classification_fields_equal: true
  });
  assert.deepEqual(audit.newly_unevaluable_rows, []);
  assert.equal(audit.primary_target_changes.length, 16);
  assert.equal(audit.aggregate_scope_changes.length, 48);
  assert.equal(audit.classification_changes.transition_count, 11);
  assert.deepEqual(audit.classification_changes.transition_pair_counts, {
    "HOT->IDEAL": 2,
    "IDEAL->COLD": 9
  });
  assert.equal(audit.absolute_dpr_delta.overall.value_count, 288);
  assert.equal(audit.absolute_dpr_delta.overall.mean_absolute_dpr_delta, "3.336333510417");
  assert.equal(audit.absolute_dpr_delta.overall.max_absolute_dpr_delta, "39.306652");
  assert.equal(
    audit.artifacts_and_provenance.invalidated_premerge_comparison.reports.run_manifest.sha256,
    invalidatedEvidence.run_manifest_sha256
  );
  assert.equal(
    audit.artifacts_and_provenance.invalidated_premerge_comparison.reports.matrix_csv.sha256,
    invalidatedEvidence.output_sha256.matrix_csv
  );
  assert.equal(
    audit.artifacts_and_provenance.corrected_contract_replacement.reports.run_manifest.sha256,
    replacementEvidence.run_manifest_sha256
  );
  assert.equal(
    audit.artifacts_and_provenance.corrected_contract_replacement.reports.detail_csv.sha256,
    replacementEvidence.output_sha256.detail_csv
  );
  assert.equal(
    audit.artifacts_and_provenance.corrected_contract_replacement.reports.matrix_csv.sha256,
    replacementEvidence.output_sha256.matrix_csv
  );
  assert.equal(
    audit.artifacts_and_provenance.corrected_contract_replacement.reports.matrix_markdown.sha256,
    replacementEvidence.output_sha256.matrix_markdown
  );
  assert.equal(
    audit.artifacts_and_provenance.corrected_contract_replacement.reports.matrix_html.sha256,
    replacementEvidence.output_sha256.matrix_html
  );
  assert.equal(
    audit.artifacts_and_provenance.baseline.reports.matrix_csv.sha256,
    review.expanded_roster_baseline_evidence.sha256
  );
  const digest = createHash("sha256").update(source).digest("hex");
  assert.match(digest, /^[0-9a-f]{64}$/);
  assert.equal(source.trimEnd().includes("\n"), false, "delta audit remains compact");
  assert.ok(harnessReadme.includes("provenance/damage-delta-v14.1-to-v14.2.json"));
  assert.ok(harnessReadme.includes("invalidated_premerge_provenance_boundary_correction"));
  assert.ok(harnessReadme.includes(replacementEvidence.run_manifest_sha256));
  assert.ok(auditDoc.includes("harness/provenance/damage-delta-v14.1-to-v14.2.json"));
  assert.ok(auditDoc.includes("invalidated_premerge_provenance_boundary_correction"));
  assert.ok(auditDoc.includes(replacementEvidence.run_manifest_sha256));
  assert.match(auditDoc, /first attempt that failed before producing output/);
  assert.ok(auditDoc.includes(review.pinned_srd.consumer_requirements_registry_sha256));
  assert.ok(auditDoc.includes(review.pinned_srd.damage_consumer_requirements_sha256));
  assert.ok(auditDoc.includes("2549ae2884aeb11bf53e3f079afc094172f5288276cd036ea86181381c4fd3d5"));
  assert.match(auditDoc, /passive Perception for all 330 creatures/);
  assert.match(auditDoc, /429 source-explicit skill facts across 216 creatures/);
  assert.match(auditDoc, /105 explicit skill facts across 40 targets/);
  assert.match(auditDoc, /165 explicit skill facts across 71 targets/);
  assert.match(auditDoc, /later check resolution falls back to the associated raw ability modifier/);
  assert.match(auditDoc, /all other check circumstances remain scenario\/event state/);
});

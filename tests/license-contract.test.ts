import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { access, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { executeBuild } from "../src/build.js";
import { sha256 } from "../src/canonical.js";
import { loadAuthority } from "../src/load.js";

const srdAttribution = "This work includes material from the System Reference Document 5.2.1 (“SRD 5.2.1”) by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode.";
const srdDisclaimer = "Section 5 of CC-BY-4.0 includes a Disclaimer of Warranties and Limitation of Liability that limits our liability to you.";
const srdModification = "Changes have been made to the SRD 5.2.1 material";
const requiredLicenseFiles = ["LICENSE.md", "LICENSE-CODE", "LICENSE-CONTENT", "NOTICE.md"] as const;
const requiredInputRoles = new Map([
  ["LICENSE.md", "component_license_index"],
  ["LICENSE-CODE", "software_license"],
  ["LICENSE-CONTENT", "original_content_license_notice"],
  ["NOTICE.md", "attribution_notice"]
]);
const requiredSrdInventoryRoles = new Map([
  ["harness/data/srd_creatures.json", "pinned_srd_creature_catalog"],
  ["harness/data/srd_creature_rosters.json", "pinned_srd_creature_rosters"],
  ["harness/provenance/srd-creatures.json", "harness_provenance"],
  ["docs/srd-creature-catalog-audit.md", "harness_documentation"]
]);
const retiredSrdInventory = [
  "harness/data/srd_targets.csv",
  "harness/data/srd_control_targets.json",
  "harness/provenance/srd-control-targets.json"
] as const;
const retiredTrackedPaths = new Set([
  "harness/control_targets.py",
  ...retiredSrdInventory,
  "harness/tests/test_control_targets.py",
  "src/control-targets.ts",
  "tests/control-targets.test.ts"
]);
const srdCreatureModification = "Selected source-authored creature facts were transcribed, structured, normalized, assigned deterministic IDs, and dispositioned for maintained consumer contracts. Full stat-block and trait prose is not reproduced.";

const escaped = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const staleCustomGrant = "Commercial use requires " + "prior written permission";
const staleCustomGrantPattern = new RegExp(escaped(staleCustomGrant), "i");
const bsdReservation = "All rights " + "reserved.";

test("repository and generated publication expose the approved component license boundaries", async () => {
  await Promise.all([...requiredLicenseFiles, "docs/licensing-audit.md"].map(path => access(path)));
  const [{ authority }, licenseIndex, codeLicense, contentLicense, notice, yaml, workflow, promote, inputsText, audit, srdProvenanceText, packageJsonText, packageLockText] = await Promise.all([
    loadAuthority(),
    readFile("LICENSE.md", "utf8"),
    readFile("LICENSE-CODE", "utf8"),
    readFile("LICENSE-CONTENT", "utf8"),
    readFile("NOTICE.md", "utf8"),
    readFile("KineticVanguard.yaml", "utf8"),
    readFile(".github/workflows/ci.yml", "utf8"),
    readFile("src/promote.ts", "utf8"),
    readFile("build/inputs.json", "utf8"),
    readFile("docs/licensing-audit.md", "utf8"),
    readFile("harness/provenance/srd-creatures.json", "utf8"),
    readFile("package.json", "utf8"),
    readFile("package-lock.json", "utf8")
  ]);
  const inputs = JSON.parse(inputsText).inputs as Array<{path:string;role:string}>;
  const inputRoles = new Map(inputs.map(input => [input.path, input.role]));
  const srdProvenance = JSON.parse(srdProvenanceText) as {
    readonly source: { readonly ruleset: string; readonly official_pdf_url: string };
    readonly catalog: { readonly file: string };
    readonly rosters: { readonly file: string };
    readonly modifications: string;
    readonly license: string;
  };
  const packageJson = JSON.parse(packageJsonText), packageLock = JSON.parse(packageLockText);

  assert.match(licenseIndex, /component-based licensing/i);
  assert.match(licenseIndex, /project-authored configuration structure and benchmark methodology/);
  assert.match(licenseIndex, /CC BY-NC-SA 4\.0/);
  assert.match(licenseIndex, /SRD 5\.2\.1-derived material[\s\S]*CC BY 4\.0/);
  assert.doesNotMatch(licenseIndex, /SRD 5\.2\.1-derived material[^\n]*CC BY-NC-SA/);
  assert.match(licenseIndex, /No project license grants or purports to grant rights in Wizards-owned material outside the System Reference Document/);
  assert.ok(licenseIndex.indexOf("## Third-party comparator references") < licenseIndex.indexOf("## Mixed files and generated publications"));

  assert.match(codeLicense, /BSD 3-Clause License/);
  assert.match(codeLicense, /Copyright \(c\) 2026, NixNinja/);
  assert.equal((codeLicense.match(new RegExp(escaped(bsdReservation), "g")) ?? []).length, 1);
  assert.match(codeLicense, /Redistribution and use in source and binary forms/);
  assert.match(codeLicense, /Neither the name of the copyright holder nor the names of its contributors/);
  assert.match(codeLicense, /THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS”/);

  assert.match(contentLicense, /Application Notice/);
  assert.match(contentLicense, /Creative Commons Attribution-NonCommercial-ShareAlike 4\.0 International/);
  assert.match(contentLicense, /https:\/\/creativecommons\.org\/licenses\/by-nc-sa\/4\.0\/legalcode/);
  assert.match(contentLicense, /canonical legal code controls/i);
  assert.match(contentLicense, /Nothing here adds restrictions, limits exceptions or limitations/);
  assert.match(contentLicense, /SRD 5\.2\.1-derived material remains separately available under CC BY 4\.0/);
  assert.doesNotMatch(contentLicense, /commercial use requires (?:a separate license|prior written permission)/i);

  assert.equal(notice.includes(srdAttribution), true);
  assert.equal((notice.match(/Wizards of the Coast LLC/g) ?? []).length, 1);
  assert.match(notice, new RegExp(escaped(srdDisclaimer)));
  assert.match(notice, new RegExp(srdModification));
  assert.match(notice, /Original Kinetic Vanguard content is Copyright © 2026 NixNinja/);
  assert.match(notice, /Project-authored software and technical implementation are Copyright \(c\) 2026, NixNinja/);
  assert.match(notice, /referenced solely as unofficial third-party comparative benchmarks/);
  assert.match(notice, /not affiliated with or endorsed by Wizards of the Coast/);
  assert.match(notice, /No project license purports to grant rights in Wizards-owned material outside the System Reference Document/);

  assert.match(authority.metadata.attribution, /Original Kinetic Vanguard content is Copyright © 2026 NixNinja/);
  assert.match(authority.metadata.attribution, /Created by NixNinja/);
  assert.equal(authority.metadata.attribution.includes(srdAttribution), true);
  assert.match(authority.metadata.attribution, new RegExp(escaped(srdDisclaimer)));
  assert.match(authority.metadata.attribution, new RegExp(srdModification));
  assert.match(authority.metadata.license, /CC BY-NC-SA 4\.0/);
  assert.match(authority.metadata.license, /Copyright \(c\) 2026, NixNinja/);
  assert.match(authority.metadata.license, /BSD-3-Clause/);
  assert.match(authority.metadata.license, /SRD 5\.2\.1-derived material remains licensed under CC BY 4\.0/);
  assert.match(authority.metadata.license, /github\.com\/kmart01123\/kinetic-vanguard\/blob\/main\/LICENSE\.md/);
  assert.doesNotMatch(yaml, staleCustomGrantPattern);

  for (const [path, role] of requiredInputRoles) {
    assert.equal(inputRoles.get(path), role);
    assert.match(workflow, new RegExp(escaped(path)));
    assert.match(promote, new RegExp(escaped(path)));
  }
  for (const [path, role] of requiredSrdInventoryRoles) assert.equal(inputRoles.get(path), role, path);
  for (const path of retiredSrdInventory) assert.equal(inputRoles.has(path), false, path);
  for (const path of [
    "harness/data/srd_creatures.json",
    "harness/data/srd_creature_rosters.json",
    "harness/provenance/srd-creatures.json"
  ]) assert.ok(audit.includes(`\`${path}\``), `licensing audit inventories ${path}`);
  for (const path of retiredSrdInventory) assert.ok(!audit.includes(`\`${path}\``), `licensing audit retires ${path}`);
  assert.equal(srdProvenance.source.ruleset, "D&D SRD 5.2.1");
  assert.equal(srdProvenance.source.official_pdf_url, "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf");
  assert.equal(srdProvenance.catalog.file, "harness/data/srd_creatures.json");
  assert.equal(srdProvenance.rosters.file, "harness/data/srd_creature_rosters.json");
  assert.equal(srdProvenance.modifications, srdCreatureModification);
  assert.equal(srdProvenance.license, "Creative Commons Attribution 4.0 International (CC BY 4.0)");
  assert.equal(inputRoles.get("tests/license-contract.test.ts"), "test_source");
  assert.equal(packageJson.license, "SEE LICENSE IN LICENSE.md");
  assert.equal(packageLock.packages[""].license, packageJson.license);

  for (const section of ["Maintained component inventory", "Repository search report", "Intentionally unchanged", "Unresolved maintainer or legal review"]) assert.match(audit, new RegExp(section));

  const temporary = await mkdtemp(join(tmpdir(), "kv-license-contract-"));
  const previousApproval = process.env.KV_RELEASE_APPROVED;
  try {
    const prototype = await executeBuild("prototype", join(temporary, "prototype"));
    process.env.KV_RELEASE_APPROVED = "1";
    const release = await executeBuild("release", join(temporary, "release"));
    for (const result of [prototype, release]) {
      const html = await readFile(result.htmlPath, "utf8");
      assert.match(html, /Original Kinetic Vanguard content is Copyright © 2026 NixNinja/);
      assert.match(html, /Copyright \(c\) 2026, NixNinja/);
      assert.equal(html.includes(srdAttribution), true);
      assert.match(html, new RegExp(escaped(srdDisclaimer)));
      assert.match(html, new RegExp(srdModification));
      assert.match(html, /CC BY-NC-SA 4\.0/);
      assert.match(html, /BSD-3-Clause/);
      assert.match(html, /SRD 5\.2\.1-derived material remains licensed under CC BY 4\.0/);
      assert.match(html, /github\.com\/kmart01123\/kinetic-vanguard\/blob\/main\/NOTICE\.md/);
      assert.doesNotMatch(html, staleCustomGrantPattern);
      const declared = new Map((result.manifest.declared_inputs as Array<{path:string;sha256:string}>).map(input => [input.path, input.sha256]));
      for (const path of requiredLicenseFiles) assert.match(declared.get(path) ?? "", /^[0-9a-f]{64}$/);
    }
  } finally {
    if (previousApproval === undefined) delete process.env.KV_RELEASE_APPROVED;
    else process.env.KV_RELEASE_APPROVED = previousApproval;
    await rm(temporary, { recursive: true, force: true });
  }
});

test("promotion emits the complete legal bundle and rejects a changed legal asset", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "kv-promote-contract-"));
  const previousApproval = process.env.KV_RELEASE_APPROVED;
  const promoteScript = resolve("src/promote.ts");
  const tsxExecutable = resolve("node_modules/.bin/tsx");
  try {
    process.env.KV_RELEASE_APPROVED = "1";
    const release = await executeBuild("release", join(temporary, "artifacts"));
    const [manifestBytes, schemaBytes, ...legalBytes] = await Promise.all([
      readFile(release.manifestPath),
      readFile("release/release-evidence-schema.json"),
      ...requiredLicenseFiles.map(path => readFile(path))
    ]);
    await mkdir(join(temporary, "release"), { recursive: true });
    await Promise.all([
      writeFile(join(temporary, "release", "release-evidence-schema.json"), schemaBytes),
      ...requiredLicenseFiles.map((path, index) => writeFile(join(temporary, path), legalBytes[index]!))
    ]);
    const evidence = {
      build_manifest_sha256: sha256(manifestBytes), evidence: [], approver: "license contract test",
      decision: "approved", date: "2026-08-07"
    };
    await writeFile(join(temporary, "artifacts", "release-evidence.json"), `${JSON.stringify(evidence, null, 2)}\n`);

    const runPromote = () => execFileSync(tsxExecutable, [promoteScript], { cwd: temporary, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    assert.match(runPromote(), /Promoted [0-9a-f]{64} with 4 legal assets/);
    const expectedInventory = ["KineticVanguard.html", ...requiredLicenseFiles].sort();
    assert.deepEqual((await readdir(join(temporary, "deployable"))).sort(), expectedInventory);
    for (const [index, path] of requiredLicenseFiles.entries()) {
      assert.deepEqual(await readFile(join(temporary, "deployable", path)), legalBytes[index]);
    }

    await writeFile(join(temporary, "deployable", "stale.txt"), "stale\n");
    runPromote();
    assert.deepEqual((await readdir(join(temporary, "deployable"))).sort(), expectedInventory);

    await writeFile(join(temporary, "NOTICE.md"), "tampered\n");
    let failure: (Error & { stderr?: Buffer }) | undefined;
    try { runPromote(); } catch (error) { failure = error as Error & { stderr?: Buffer }; }
    assert.ok(failure);
    assert.match(failure.stderr?.toString("utf8") ?? failure.message, /Legal asset differs from the verified manifest: NOTICE\.md/);
    assert.deepEqual(await readFile(join(temporary, "deployable", "NOTICE.md")), legalBytes[requiredLicenseFiles.indexOf("NOTICE.md")]);
  } finally {
    if (previousApproval === undefined) delete process.env.KV_RELEASE_APPROVED;
    else process.env.KV_RELEASE_APPROVED = previousApproval;
    await rm(temporary, { recursive: true, force: true });
  }
});

test("tracked licensing language has no stale custom grant or blanket reservation", async () => {
  const paths = execFileSync("git", ["ls-files"], { encoding: "utf8" }).trim().split("\n").filter(Boolean);
  for (const path of paths) {
    if (path === "docs/licensing-audit.md") continue;
    let content: string;
    try {
      content = await readFile(path, "utf8");
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        assert.ok(retiredTrackedPaths.has(path), `unexpected missing tracked path: ${path}`);
        continue;
      }
      throw error;
    }
    assert.equal(content.toLowerCase().includes(staleCustomGrant.toLowerCase()), false, path);
    if (content.includes(bsdReservation)) assert.equal(path, "LICENSE-CODE");
  }
});

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { access, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";

const srdAttribution = "This work includes material from the System Reference Document 5.2.1 (“SRD 5.2.1”) by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode.";
const srdDisclaimer = "Section 5 of CC-BY-4.0 includes a Disclaimer of Warranties and Limitation of Liability that limits our liability to you.";
const srdModification = "Changes have been made to the SRD 5.2.1 material";
const requiredLicenseFiles = ["LICENSE.md", "LICENSE-CODE", "LICENSE-CONTENT", "NOTICE.md"] as const;

const escaped = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const staleCustomGrant = "Commercial use requires " + "prior written permission";
const staleCustomGrantPattern = new RegExp(escaped(staleCustomGrant), "i");
const bsdReservation = "All rights " + "reserved.";

test("repository and generated publication expose the approved component license boundaries", async () => {
  await Promise.all([...requiredLicenseFiles, "docs/licensing-audit.md"].map(path => access(path)));
  const [{ authority }, licenseIndex, codeLicense, contentLicense, notice, yaml, audit, packageJsonText, packageLockText] = await Promise.all([
    loadAuthority(),
    readFile("LICENSE.md", "utf8"),
    readFile("LICENSE-CODE", "utf8"),
    readFile("LICENSE-CONTENT", "utf8"),
    readFile("NOTICE.md", "utf8"),
    readFile("KineticVanguard.yaml", "utf8"),
    readFile("docs/licensing-audit.md", "utf8"),
    readFile("package.json", "utf8"),
    readFile("package-lock.json", "utf8")
  ]);
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
    }
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
    const content = await readFile(path, "utf8");
    assert.equal(content.toLowerCase().includes(staleCustomGrant.toLowerCase()), false, path);
    if (content.includes(bsdReservation)) assert.equal(path, "LICENSE-CODE");
  }
});

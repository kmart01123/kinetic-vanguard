import assert from "node:assert/strict";
import test from "node:test";
import { access, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { executeBuild } from "../src/build.js";
import { loadAuthority } from "../src/load.js";

const srdAttribution = "This work includes material from the System Reference Document 5.2.1 (“SRD 5.2.1”) by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode.";

const requiredLicenseFiles = ["LICENSE.md", "LICENSE-CODE", "LICENSE-CONTENT", "NOTICE.md"] as const;

test("repository and generated publication expose the approved split license", async () => {
  await Promise.all(requiredLicenseFiles.map(path => access(path)));
  const [{ authority }, licenseIndex, codeLicense, contentLicense, notice, yaml, workflow] = await Promise.all([
    loadAuthority(),
    readFile("LICENSE.md", "utf8"),
    readFile("LICENSE-CODE", "utf8"),
    readFile("LICENSE-CONTENT", "utf8"),
    readFile("NOTICE.md", "utf8"),
    readFile("KineticVanguard.yaml", "utf8"),
    readFile(".github/workflows/ci.yml", "utf8")
  ]);

  assert.match(licenseIndex, /component-based licensing/i);
  assert.match(licenseIndex, /BSD-3-Clause/);
  assert.match(licenseIndex, /CC BY-NC-SA 4\.0/);
  assert.match(licenseIndex, /SRD 5\.2\.1-derived material[\s\S]*CC BY 4\.0/);
  assert.doesNotMatch(licenseIndex, /SRD 5\.2\.1-derived material[^\n]*CC BY-NC-SA/);
  assert.match(licenseIndex, /No project license grants or purports to grant rights in Wizards-owned material outside the System Reference Document/);

  assert.match(codeLicense, /BSD 3-Clause License/);
  assert.match(codeLicense, /Redistribution and use in source and binary forms/);
  assert.match(codeLicense, /Neither the name of the copyright holder nor the names of its contributors/);
  assert.match(codeLicense, /THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS”/);

  assert.match(contentLicense, /Creative Commons Attribution-NonCommercial-ShareAlike 4\.0 International/);
  assert.match(contentLicense, /https:\/\/creativecommons\.org\/licenses\/by-nc-sa\/4\.0\/legalcode/);
  assert.match(contentLicense, /SRD 5\.2\.1-derived material[\s\S]*CC BY 4\.0/);

  assert.equal(notice.includes(srdAttribution), true);
  assert.equal((notice.match(/Wizards of the Coast LLC/g) ?? []).length, 1);
  assert.match(notice, /Changes have been made to the SRD 5\.2\.1 material/);
  assert.match(notice, /referenced solely as unofficial third-party comparative benchmarks/);
  assert.match(notice, /not affiliated with or endorsed by Wizards of the Coast/);
  assert.match(notice, /No project license purports to grant rights in Wizards-owned material outside the System Reference Document/);

  assert.match(authority.metadata.attribution, /Created by NixNinja/);
  assert.equal(authority.metadata.attribution.includes(srdAttribution), true);
  assert.match(authority.metadata.license, /CC BY-NC-SA 4\.0/);
  assert.match(authority.metadata.license, /BSD-3-Clause/);
  assert.match(authority.metadata.license, /SRD 5\.2\.1-derived material remains licensed under CC BY 4\.0/);
  assert.doesNotMatch(yaml, /Commercial use requires prior written permission/);

  for (const path of requiredLicenseFiles) assert.match(workflow, new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));

  const temporary = await mkdtemp(join(tmpdir(), "kv-license-contract-"));
  const previousApproval = process.env.KV_RELEASE_APPROVED;
  try {
    const prototype = await executeBuild("prototype", join(temporary, "prototype"));
    process.env.KV_RELEASE_APPROVED = "1";
    const release = await executeBuild("release", join(temporary, "release"));
    for (const result of [prototype, release]) {
      const html = await readFile(result.htmlPath, "utf8");
      assert.match(html, /Created by NixNinja/);
      assert.equal(html.includes(srdAttribution), true);
      assert.match(html, /CC BY-NC-SA 4\.0/);
      assert.match(html, /BSD-3-Clause/);
      assert.match(html, /SRD 5\.2\.1-derived material remains licensed under CC BY 4\.0/);
      assert.doesNotMatch(html, /Commercial use requires prior written permission/);
    }
  } finally {
    if (previousApproval === undefined) delete process.env.KV_RELEASE_APPROVED;
    else process.env.KV_RELEASE_APPROVED = previousApproval;
    await rm(temporary, { recursive: true, force: true });
  }
});

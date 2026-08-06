from pathlib import Path

srd_attribution = (
    'This work includes material from the System Reference Document 5.2.1 '
    '(“SRD 5.2.1”) by Wizards of the Coast LLC, available at '
    'https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the '
    'Creative Commons Attribution 4.0 International License, available at '
    'https://creativecommons.org/licenses/by/4.0/legalcode.'
)

license_index = '''# Kinetic Vanguard Licensing

Kinetic Vanguard uses component-based licensing. No single license applies to every file or to every part of a generated publication.

## Software and technical implementation — BSD 3-Clause

Copyright (c) 2026 NixNinja

The BSD 3-Clause License (`BSD-3-Clause`) applies to the software and technical implementation unless a file states otherwise. This includes application code, build tooling, tests, schema, continuous-integration workflows, interface code, configuration, and the software portions of generated publications.

The complete terms are in `LICENSE-CODE`.

## Original Kinetic Vanguard content — CC BY-NC-SA 4.0

Copyright © 2026 NixNinja

The Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License (`CC BY-NC-SA 4.0`) applies to the copyrightable original expression in Kinetic Vanguard rules, examples, explanatory prose, and documentation unless otherwise noted.

Canonical legal code: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

The license permits sharing and adaptation for noncommercial purposes with attribution. Adapted material must be distributed under the same license. Commercial permission for original Kinetic Vanguard content may be granted separately by the copyright holder.

This license does not apply to SRD 5.2.1-derived material.

## SRD 5.2.1-derived material — CC BY 4.0

Material derived from the System Reference Document 5.2.1 remains licensed under the Creative Commons Attribution 4.0 International License (`CC BY 4.0`). Nothing in the Kinetic Vanguard CC BY-NC-SA license limits, replaces, or adds restrictions to the rights granted for SRD-derived material under CC BY 4.0.

The required attribution and modification notice are in `NOTICE.md`.

## Mixed files and generated publications

`KineticVanguard.yaml` and generated `KineticVanguard.html` publications contain components under different licenses:

- application code and presentation software: BSD-3-Clause;
- original Kinetic Vanguard rules, examples, and editorial text: CC BY-NC-SA 4.0;
- SRD 5.2.1-derived material: CC BY 4.0.

Each component retains its own license. A recipient may continue to use SRD-derived material under CC BY 4.0 even when it appears beside original Kinetic Vanguard content.

## No endorsement

The licenses do not grant permission to imply sponsorship, endorsement, or official status.
'''

license_code = '''BSD 3-Clause License

Copyright (c) 2026, NixNinja
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

license_content = '''Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

Copyright © 2026 NixNinja

Except for software components and SRD 5.2.1-derived material, the copyrightable original Kinetic Vanguard rules, examples, explanatory prose, and documentation are licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License (`CC BY-NC-SA 4.0`).

Canonical legal code:
https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

Under this license, you may share and adapt the licensed material for noncommercial purposes if you provide appropriate attribution, indicate changes, and distribute adaptations under the same license. The canonical legal code controls if this notice and the license differ.

Commercial use of original Kinetic Vanguard content requires a separate license from the copyright holder. This restriction does not apply to SRD 5.2.1-derived material, which remains separately available under CC BY 4.0.

See `LICENSE.md` for component boundaries and `NOTICE.md` for SRD attribution.
'''

notice = f'''# Notices

## Kinetic Vanguard

Original Kinetic Vanguard content is copyright © 2026 NixNinja.

Created by NixNinja in collaboration with artificial intelligence assistants. Special thanks to various muses, great and small.

Original Kinetic Vanguard rules, examples, and editorial text are licensed under CC BY-NC-SA 4.0. Software and technical implementation are licensed under BSD-3-Clause. See `LICENSE.md`, `LICENSE-CONTENT`, and `LICENSE-CODE`.

## System Reference Document 5.2.1

{srd_attribution}

Changes have been made to the SRD 5.2.1 material used in this work. Use of SRD material does not imply endorsement.
'''

Path('LICENSE.md').write_text(license_index, encoding='utf-8')
Path('LICENSE-CODE').write_text(license_code, encoding='utf-8')
Path('LICENSE-CONTENT').write_text(license_content, encoding='utf-8')
Path('NOTICE.md').write_text(notice, encoding='utf-8')

authority_path = Path('KineticVanguard.yaml')
authority = authority_path.read_text(encoding='utf-8')
old_attribution = '  attribution: Created by NixNinja in collaboration with artificial intelligence assistants. Special thanks to various muses, great and small.\n'
old_license = '  license: Original Kinetic Vanguard material may be used, copied, modified, and redistributed for non-commercial purposes with credit to NixNinja. Commercial use requires prior written permission. System Reference Document-derived rules text and references are separately governed by the Creative Commons Attribution 4.0 International License.\n'
new_attribution = (
    '  attribution: Created by NixNinja in collaboration with artificial intelligence assistants. '
    'Special thanks to various muses, great and small. ' + srd_attribution + '\n'
)
new_license = (
    '  license: Original Kinetic Vanguard rules, examples, and editorial text are licensed under '
    'CC BY-NC-SA 4.0, available at https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode. '
    'Software and tooling are licensed under BSD-3-Clause. SRD 5.2.1-derived material remains '
    'licensed under CC BY 4.0. See LICENSE.md and NOTICE.md for scope and attribution.\n'
)
if old_attribution not in authority:
    raise SystemExit('Expected creator attribution was not found')
if old_license not in authority:
    raise SystemExit('Expected legacy license text was not found')
authority = authority.replace(old_attribution, new_attribution, 1)
authority = authority.replace(old_license, new_license, 1)
authority_path.write_text(authority, encoding='utf-8')

render_path = Path('src/render.ts')
render = render_path.read_text(encoding='utf-8')
old_footer = '<section id="rules-content" class="rules" tabindex="-1"></section></main><footer><p>${escapeHtml(input.authority.metadata.attribution)}</p></footer>'
new_footer = '<section id="rules-content" class="rules" tabindex="-1"></section></main><footer><p>${escapeHtml(input.authority.metadata.attribution)}</p><p>${escapeHtml(input.authority.metadata.license)}</p></footer>'
if old_footer not in render:
    raise SystemExit('Expected publication footer was not found')
render_path.write_text(render.replace(old_footer, new_footer, 1), encoding='utf-8')

workflow_path = Path('.github/workflows/ci.yml')
workflow = workflow_path.read_text(encoding='utf-8')
artifact_anchor = '            artifacts/coverage-ledger.json\n'
artifact_replacement = (
    artifact_anchor
    + '            LICENSE.md\n'
    + '            LICENSE-CODE\n'
    + '            LICENSE-CONTENT\n'
    + '            NOTICE.md\n'
)
if artifact_anchor not in workflow:
    raise SystemExit('Expected CI artifact list was not found')
workflow_path.write_text(workflow.replace(artifact_anchor, artifact_replacement, 1), encoding='utf-8')

changelog_path = Path('CHANGELOG.md')
changelog = changelog_path.read_text(encoding='utf-8')
changed_heading = '## 13.2.0 — Unreleased\n\n### Changed\n\n'
license_entry = (
    '- Adopted component-based licensing: BSD-3-Clause for software and tooling, '
    'CC BY-NC-SA 4.0 for original Kinetic Vanguard content, and CC BY 4.0 for '
    'SRD 5.2.1-derived material, with exact SRD attribution in repository notices '
    'and generated publications.\n'
)
if changed_heading not in changelog:
    raise SystemExit('Expected 13.2.0 changelog heading was not found')
changelog_path.write_text(changelog.replace(changed_heading, changed_heading + license_entry, 1), encoding='utf-8')

test_content = r'''import assert from "node:assert/strict";
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
'''
Path('tests/license-contract.test.ts').write_text(test_content, encoding='utf-8')

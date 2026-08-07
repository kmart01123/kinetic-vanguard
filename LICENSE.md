# Kinetic Vanguard Licensing

Kinetic Vanguard uses component-based licensing. No single license applies to every file or every part of a generated publication. This index identifies the intended boundaries; the canonical license texts control, and this summary does not add restrictions or limit exceptions, limitations, or independently available rights.

## Software and technical implementation — BSD 3-Clause

Copyright (c) 2026, NixNinja

The BSD 3-Clause License (`BSD-3-Clause`) applies to project-authored software and technical implementation unless a file states otherwise. This includes application and harness code, build tooling, tests, schemas, continuous-integration workflows, interface code, technical report rendering, and project-authored configuration structure and benchmark methodology.

That assignment does not relicense original Kinetic Vanguard expression embedded in code or fixtures, SRD-derived rules/data, third-party package material, or non-SRD names and underlying game material. Those components retain the boundaries below.

The complete BSD terms and project copyright notice are in `LICENSE-CODE`.

## Original Kinetic Vanguard content — CC BY-NC-SA 4.0

Copyright © 2026 NixNinja

The Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License (`CC BY-NC-SA 4.0`) applies to the copyrightable original expression in Kinetic Vanguard rules, examples, explanatory and editorial prose, documentation, approved interface text, and project-authored benchmark explanation unless otherwise noted.

Canonical legal code: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

The canonical legal code controls. This summary does not modify its Attribution, NonCommercial, ShareAlike, no-additional-restrictions, exceptions-and-limitations, or disclaimer provisions.

This license does not apply to SRD 5.2.1-derived material or material the project does not own.

## SRD 5.2.1-derived material — CC BY 4.0

Material derived from the System Reference Document 5.2.1 remains licensed under the Creative Commons Attribution 4.0 International Public License (`CC BY 4.0`). Nothing in the Kinetic Vanguard CC BY-NC-SA license limits, replaces, or adds restrictions to rights independently granted for SRD-derived material under CC BY 4.0.

The Wizards-supplied attribution, disclaimer reference, and project modification notice are retained in `NOTICE.md`. Canonical legal code: https://creativecommons.org/licenses/by/4.0/legalcode

## Third-party comparator references

The BSD-3-Clause license applies to project-authored harness software, configuration structure, benchmark selection, and analytical implementation. It does not license third-party names, rules, or other underlying game material.

Battle Master and Eldritch Knight are used only as unofficial comparative benchmark identifiers. No project license grants or purports to grant rights in Wizards-owned material outside the System Reference Document. See `NOTICE.md` and `harness/README.md`.

## Mixed files and generated publications

`KineticVanguard.yaml` and generated `KineticVanguard.html` publications contain distinguishable components under different licenses:

- project-authored application code, technical structure, and presentation software: BSD-3-Clause;
- original Kinetic Vanguard rules, examples, interface text, and editorial expression: CC BY-NC-SA 4.0;
- SRD 5.2.1-derived material: CC BY 4.0.

Harness configuration and output are also mixed. Project-authored technical structure and methodology are BSD-3-Clause; original explanatory prose is CC BY-NC-SA 4.0; SRD-derived target data and base rules components remain CC BY 4.0; and non-SRD comparator names or underlying material are not licensed by the project.

Build manifests, integrity ledgers, and coverage ledgers use project-authored technical structures under BSD-3-Clause. Any embedded source text, identifiers, or data retain their source component's license or third-party status.

Each component retains its own license. A recipient may continue to use SRD-derived material under CC BY 4.0 even when it appears beside original Kinetic Vanguard content. Current release automation and deployment promotion include this index, both license notices, and `NOTICE.md` beside the generated HTML.

## Third-party packages and services

The project does not vendor dependency source. The 85 locked npm packages retain their own license metadata in `package-lock.json`; the audited set contains MIT, MIT-0, ISC, BSD-2-Clause, BSD-3-Clause, and Apache-2.0 packages. Build and test dependencies are not relicensed by this project, and generated browser publications embed only project-authored runtime source.

GitHub Actions and external services referenced by configuration remain subject to their own terms and licenses.

## Machine-readable marking

`package.json` and its root lockfile entry use `SEE LICENSE IN LICENSE.md` because a single SPDX identifier would misstate this mixed repository. Targeted SPDX headers are intentionally not added to mixed YAML, JSON, CSV, HTML, or generated artifacts. The repository-level map and embedded notices provide the component-level boundary.

## No endorsement

The licenses do not grant permission to imply sponsorship, endorsement, or official status. See `NOTICE.md` for the specific unofficial comparator and no-affiliation notice.

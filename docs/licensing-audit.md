# Repository licensing and attribution audit

Audit date: 2026-08-07
Audited base: `main` at `0732ac9912d492f58407b29145680b635ba52757` (PR #20 merge)
Durable work order: GitHub issue #21

This is a repository compliance record, not legal advice. It records source evidence, component boundaries, corrections, intentionally unchanged notices, and questions that repository evidence cannot resolve.

## Authoritative sources checked

- CC BY-NC-SA 4.0 legal code: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode
- Creative Commons marking guidance: https://creativecommons.org/cc-license-your-work/
- CC BY 4.0 legal code: https://creativecommons.org/licenses/by/4.0/legalcode
- OSI BSD 3-Clause text: https://opensource.org/license/bsd-3-clause
- D&D SRD 5.2.1 page: https://www.dndbeyond.com/srd
- D&D SRD 5.2.1 PDF legal page: https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf

The audit applied these source-level conclusions:

- a licensor can license only rights it controls, and material outside a CC license should be marked clearly;
- supplied creator, copyright, license, disclaimer, source, and modification information must be retained when the applicable CC material is shared;
- CC BY-NC-SA does not add restrictions to independently licensed CC BY material, and the project summary must not add terms to either canonical license;
- BSD source and binary redistributions must retain or reproduce the copyright notice, conditions, and disclaimer;
- attribution does not imply endorsement; and
- the SRD's prescribed attribution is retained verbatim as a distinct statement.

## Maintained component inventory

The pre-change tree contained 74 tracked files. This table covers every maintained path category, including this added audit record.

| Component category | Maintained paths | Intended boundary and disposition |
| --- | --- | --- |
| Legal texts and notices | `LICENSE-CODE`, `LICENSE-CONTENT`, `LICENSE.md`, `NOTICE.md` | `LICENSE-CODE` retains the BSD notice and terms. The other files are project-authored scope/attribution notices pointing to canonical legal code. |
| Canonical mixed authority | `KineticVanguard.yaml` | Project-authored technical structure is BSD-3-Clause; original rules, examples, and editorial expression are CC BY-NC-SA 4.0; SRD-derived components remain CC BY 4.0. No single SPDX identifier is accurate. |
| Original documentation | root Markdown, `.github/pull_request_template.md`, `docs/*`, `policy/*`, `harness/*.md` | Original expression is CC BY-NC-SA 4.0. Embedded SRD and third-party components retain their source boundary. |
| Application and harness source | `src/*.ts`, Python under `harness/`, Python/TypeScript tests | Project-authored software is BSD-3-Clause. Embedded fixtures retain the license or third-party status of their source expression/data. |
| Schemas, technical policy, UI/build/review configuration | `schema/*`, `release/*`, `review/*`, `ui/*`, `build/*`, `.devcontainer/*`, `.github/workflows/*`, `tsconfig.json`, `.gitignore` | Project-authored technical structures are BSD-3-Clause. Original approved UI prose is CC BY-NC-SA; embedded source facts retain their source boundary. |
| Benchmark methodology configuration | `harness/config/benchmark.json` | Project-authored benchmark structure, selection, aggregation, and methodology are BSD-3-Clause. SRD-derived Fighter progression/mechanics remain CC BY 4.0. |
| Comparator configuration | `harness/comparators/fighter-subclasses.json` | Project-authored structure, benchmark selection, and independently authored analytical/policy expression are BSD-3-Clause. Individual parameters retain SRD or third-party status as applicable; Battle Master/Eldritch Knight identifiers and underlying non-SRD material are not licensed by the project. |
| SRD roster and provenance | `harness/data/srd_targets.csv`, SRD components in `harness/provenance/*` | SRD-derived data remain CC BY 4.0 with exact attribution and modification marking. Project-authored selection/technical structure is BSD-3-Clause where copyright applies. |
| Generated publications | `KineticVanguard.html` / prototype output | Mixed: BSD presentation/runtime, CC BY-NC-SA original expression, and CC BY SRD components. The HTML embeds scoped notices; current release/deployable paths retain all four legal files. |
| Generated benchmark reports | damage/control CSV, Markdown, and HTML | Mixed technical/report structure, original explanation, SRD target data, and third-party comparator identifiers. Every format now carries structured legal notices. |
| Manifests and ledgers | build manifest, integrity/coverage ledgers, harness provenance | Project-authored technical structure is BSD-3-Clause; embedded source data and text retain their component boundary. Legal assets are declared and hashed build inputs. |
| Package/tool metadata | `package.json`, `package-lock.json` | The private root package points to `LICENSE.md`. All 85 locked packages retain their own metadata: 73 MIT, 4 Apache-2.0, 2 BSD-2-Clause, 2 BSD-3-Clause, 3 ISC, and 1 MIT-0. No dependency source is vendored or bundled into the browser runtime. |
| Historical release workflows | `.github/workflows/publish-v13.*.yml`, `publish-v14.0.0.yml` | Frozen snapshots remain historical records. v13.2.0 and later bundles carry the four legal assets; earlier frozen releases are documented but not silently rewritten. |

## Copyright and attribution review

The scoped project notices remain:

- `Copyright © 2026 NixNinja` for original Kinetic Vanguard content; and
- `Copyright (c) 2026, NixNinja` for project-authored software and technical implementation.

They were retained because CC licensing does not disclaim authorship or ownership and BSD redistribution depends on retaining its notice. Wording was narrowed wherever a mixed file could otherwise suggest ownership of SRD or third-party material.

`NixNinja` is used consistently as the supplied pseudonymous creator/holder. CC BY-NC-SA expressly permits a designated pseudonym in attribution. The independent ownership question is recorded under unresolved review rather than inferred from repository labels.

## License-file comparison

### BSD 3-Clause

`LICENSE-CODE` retains the holder/year substitution, redistribution clauses, no-endorsement clause, and warranty/liability disclaimer. `All rights reserved.` occurs only inside this scoped BSD notice and is not a repository-wide reservation. The existing typographic quotation marks do not change the operative words.

No software license was changed.

### CC BY-NC-SA 4.0

`LICENSE-CONTENT` is now explicitly an application notice rather than a local rewrite of the legal code. It identifies the licensed original components, points to canonical legal code, refers to the Section 5 disclaimer, and says the summary neither adds restrictions nor limits exceptions, limitations, or independently available rights. The prior categorical claim that commercial use always requires a separate license was removed because the public license summary should not purport to decide exceptions or rights available from another source.

No content license was changed.

## SRD 5.2.1 verification

The official PDF's prescribed SRD attribution remains verbatim in `NOTICE.md`, canonical YAML metadata, generated publication footers, and harness reports. The separate supplied Section 5 disclaimer reference and a specific modification marker are now retained with it.

The recorded official PDF SHA-256 is `8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87`, matching `harness/provenance/legacy-import.json`. The maintained 28-row roster identifies SRD 5.2.1, source page, and official PDF URL for every row. Its preserved historical roster SHA-256 is `dfbda8f8e51d85b898d406a1b7dff63a40899bdf460fe5bc25d73c61d1d1ca5a`.

The project CC BY-NC-SA notice expressly does not restrict or relicense SRD-derived components.

## Battle Master / Eldritch Knight boundary

The comparator audit found no reason to remove or replace the comparators:

- comparator mechanics remain absent from `KineticVanguard.yaml`;
- configuration retains only the numerical parameters, narrow scenario identifiers, and independently authored analytical-policy fields used by the benchmark; it contains no copied descriptive subclass, maneuver, spell, sourcebook, flavor, or character-building prose;
- project-authored code and structure are separated from underlying game material;
- the names are described only as unofficial reference identifiers; and
- repository and generated-report notices deny affiliation, endorsement, and any project grant of rights in non-SRD Wizards-owned material.

The official SRD contains some shared base elements used by the models but does not contain the named Battle Master or Eldritch Knight subclasses. No project notice characterizes their non-SRD material as project-owned or CC-licensed.

## Generated and mixed artifacts

Confirmed corrections:

- canonical footer metadata now includes scoped project copyright, exact SRD attribution, the supplied disclaimer reference, a modification notice, canonical license URLs, and repository notice URLs;
- the current release build manifest hashes all four legal assets;
- current promotion verifies those hashes and produces a five-file deployable bundle instead of silently dropping the legal files;
- CI/GitHub release bundles continue to ship the same legal assets;
- every harness detail, audit, and matrix CSV embeds structured notice columns; and
- matrix Markdown and HTML include a visible licensing-and-notices section.

Historical release assets and frozen branches were intentionally not rewritten. Future outputs receive the corrected boundary.

## SPDX and machine-readable disposition

A blanket SPDX identifier would be false for the mixed repository, canonical YAML, configuration, CSV, and generated HTML. `package.json` and the root lockfile entry therefore use `SEE LICENSE IN LICENSE.md`. No boilerplate header was added to every file.

The audit prefers:

- repository-level component mapping;
- declared legal-asset hashes in the build manifest;
- embedded notices for copied artifacts; and
- targeted semantic tests for required boundaries and prohibited stale wording.

## Repository search report

The maintained tree was searched case-insensitively for copyright, license/licence, Creative Commons, BSD, SRD, OGL, Wizards, comparator identifiers, endorsement/affiliation, commercial-use language, holder names, and `all rights reserved`.

Disposition:

- `All rights reserved.` remains only in `LICENSE-CODE` as part of the scoped BSD notice.
- No active OGL, obsolete SRD version, blanket whole-repository license, conflicting holder notice, or endorsement claim was found.
- The old custom “commercial use requires prior written permission” sentence existed only in a historical-normalization test fixture; it was replaced by a neutral sentinel without changing the fixture's purpose.
- The overbroad commercial sentence in `LICENSE-CONTENT` was corrected as described above.
- The malformed `LICENSE.md` heading order was corrected.
- README and harness documentation now distinguish project-authored methodology/structure from SRD-derived and third-party components.

## Intentionally unchanged

- Valid NixNinja copyright and creator notices remain.
- `LICENSE-CODE` retains the BSD terms, including its copyright and `All rights reserved.` lines.
- BSD-3-Clause, CC BY-NC-SA 4.0, and CC BY 4.0 assignments were not changed.
- The exact Wizards-prescribed SRD attribution was not rewritten or embellished.
- Battle Master and Eldritch Knight remain narrow unofficial comparators.
- Frozen historical branches, tags, releases, and publication workflows were not retroactively altered.
- No single SPDX identifier was assigned to a genuinely mixed artifact.

## Unresolved maintainer or legal review

1. Repository licensing consistently designates `NixNinja`, while Git history uses `Kyle Martin` and `kmart01123`. Repository evidence does not establish their relationship or independently prove ownership/authorization for every original contribution. The supplied pseudonymous notice was retained; the maintainer should confirm that it is the intended creator/rights-holder identity and that contributor licensing is authorized.
2. The comparator use is deliberately narrow, independently expressed, referential, and disclaimed. This audit cannot determine whether every use of non-SRD identifiers or underlying mechanics in every jurisdiction is permitted; that remains a maintainer/legal question. Notice wording cannot manufacture third-party rights.
3. This audit does not determine the copyrightability of individual game facts, numeric parameters, schemas, or database fields. It applies the conservative component boundary without claiming ownership where the answer is uncertain.

No unresolved item was treated as permission to relicense, delete attribution, or publish non-SRD material under a project license.

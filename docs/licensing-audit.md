# Repository licensing and attribution audit

Audit date: 2026-08-14
Audited base: `main` at `e5d81ab1271b305bee5b92bca22bb9acce0275e9`
Governing work order: GitHub issue #63, owner authorization comment `5289581036`, and maintainer resolution comment `5291975732`

This is repository compliance engineering, not legal advice or a claim of legal clearance. It records source evidence, component boundaries, confirmed corrections, intentionally unchanged material, and questions that repository evidence cannot resolve. Automated scans cannot prove the absence of all protectable expression, and no audit or notice guarantees that a demand letter will not be made.

## Issue #65 PR1 successor note

The dated issue #63 inventory and reference-register findings below remain a historical audit of their stated base. Issue #65 PR1 subsequently updates the nominal comparator and damage-model contracts from exact implementation base `5fcee4b94dd97d0b8b88df3449358c74bd717c7c`, under frozen contract comments `5300138781` and `5300161056`. It does not claim that the corrected worktree existed at that base commit, and no result commit or audited PR head is recorded before one exists. The accepted historical 47-target evidence remains preserved; PR1 does not perform or claim a fresh complete matrix.

## Current authoritative sources

The following official sources were retrieved and checked on 2026-08-14 UTC:

- D&D Creator FAQ, published 2025-04-22: https://www.dndbeyond.com/creator-faq
- Current SRD page, last updated 2026-03-02: https://www.dndbeyond.com/srd
- Pinned English SRD 5.2.1 PDF, published 2025-05-01: https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf
- CC BY 4.0 legal code (primary human-readable URL): https://creativecommons.org/licenses/by/4.0/legalcode
- Official CC BY 4.0 plain-text legal-code representation used for byte identity: https://creativecommons.org/licenses/by/4.0/legalcode.txt
- Creative Commons marking guidance: https://creativecommons.org/cc-license-your-work/
- Wizards Fan Content Policy, last updated 2017-11-15: https://company.wizards.com/en/legal/fancontentpolicy

The pinned PDF was fetched twice and remained 6,031,375 bytes with SHA-256 `8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87`, matching `harness/provenance/srd-creatures.json`. The current SRD page identifies SRD 5.2.1 as the latest English SRD. The PDF contains the Champion Fighter subclass and does not contain `Battle Master` or `Eldritch Knight`.

The official-source review supports these bounded conclusions:

- SRD 5.2.1, not the D&D Beyond Basic Rules, is the CC-licensed publication source. The Basic Rules are not accepted as repository provenance.
- CC BY 4.0 requires retention of supplied attribution, license and disclaimer information, a source link where practicable, and an indication of modifications. It grants no trademark rights and no permission to imply sponsorship, endorsement, connection, or official status.
- The exact supplied SRD attribution remains separate from non-SRD bibliography, project copyright, modification/disclaimer language, and no-affiliation/no-endorsement wording.
- The Creator FAQ recommends title, year, publisher, and an exact page where available for non-SRD official references. That citation practice is not a license to reproduce non-SRD expression.
- The Fan Content Policy describes a distinct, generally free and unofficial non-TRPG fan-content boundary. It is not the publishing authority for this SRD-based rules project or its comparator mechanics.
- Creative Commons marking guidance supports clear component scope. A notice cannot manufacture rights in non-SRD Wizards material.

Mutable official HTML pages are identified by URL, displayed publication/update date, and retrieval date rather than a brittle raw-HTML hash. The CC byte identity applies specifically to the official `https://creativecommons.org/licenses/by/4.0/legalcode.txt` representation, not the HTML response at the primary `/legalcode` URL: the fetched text was 18,657 bytes with SHA-256 `9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411`.

## Complete current-tree inventory

The exact audited base has 102 tracked paths. This focused change adds the nominal contract module, two maintained machine-readable contract records, and three independent test/oracle modules, producing a 108-path candidate tree. `review/wizards-ip-reference-register.json` records every path/reference-category pair derived from that candidate tree and every file recursively discovered in freshly generated prototype and authorized-release output directories. Exact set and hit-count equality make a missing entry or stale extra entry fail, but only for the declared scanner lexicon described below.

Three identities serve different purposes. The audited base commit identifies the authorized starting point. A deterministic path-set digest identifies candidate path names. A separate candidate-tree content digest, recorded as `tracked_content_sha256`, binds every scanned path and its bytes through unambiguous path/length/content framing; for the register itself, only that digest field is blanked before framing. The eventual commit that contains the register cannot be embedded in that same register without circularity, so the final commit identity must be recorded externally in the pull request or governing issue after it exists.

The register covers these current categories:

- D&D, Dungeons & Dragons, and D&D Beyond brand references;
- Wizards of the Coast corporate references and scoped rights statements;
- Battle Master and Eldritch Knight non-SRD comparator identifiers;
- Player’s Handbook, Dungeon Master’s Guide, and Monster Manual references;
- SRD and System Reference Document references;
- an expanded, bounded set of omitted or non-SRD examples identified for review: Deck of Many Things, Orb of Dragonkind, Artificer, Aasimar, Beholder, Strahd, Orcus, Tiamat, and Forgotten Realms;
- the corresponding reviewed SRD replacement-name examples Mysterious Deck and Dragon Orb;
- current comparator feat/feature terms, including Great Weapon Master, Heavy Weapon Mastery, Hew, Dueling, Relentless, Combat/Superiority Die wording, War Magic, and Precision Attack;
- Basic Rules, OGL, and Fan Content Policy references; and
- scoped affiliation, endorsement, sponsorship, official-status, ownership, and blanket-license claims.

Each entry records one required classification, matched term identities, public/private/generated surface, notice or locator, mechanical necessity, compact rationale, and whether counsel review remains. Classifications are limited to `srd_5_2_1_licensed_use`, `original_project_content`, `narrow_nominative_reference`, `independently_expressed_factual_mechanic`, `historical_reference_in_current_documentation`, `uncertain_counsel_review`, and `remove_or_rename`.

Within that lexicon, the scan found no current `remove_or_rename` disposition and no tracked private source capture, authenticated HTML, PDF, image, logo, map, screenshot, font, audio, video, or other binary Wizards brand asset. All 102 candidate paths are regular UTF-8 text with no NUL bytes or prohibited file signatures. Historical release workflows remain classified as historical current documentation; frozen branches, tags, Releases, and published assets were not rewritten.

This scanner provides complete current-tree coverage for its hardcoded official-example and current-comparator lexicon, including the expanded omitted/replacement examples above. No finite lexicon proves that all protected names, other subject matter, or protectable expression has been found, and the result does not claim broad recapture or universal IP detection. This bounded scope is accepted audit methodology, not an unresolved implementation defect.

## Maintained component boundaries

| Component category | Maintained paths | Current boundary and disposition |
| --- | --- | --- |
| Legal texts and notices | `LICENSE-CODE`, `LICENSE-CONTENT`, `LICENSE.md`, `NOTICE.md` | Existing component licenses, exact SRD attribution, project notices, and third-party boundary remain unchanged. |
| Canonical mixed authority | `KineticVanguard.yaml` | Project-authored technical structure is BSD-3-Clause; original rules/editorial expression is CC BY-NC-SA 4.0; SRD-derived components remain CC BY 4.0. No single SPDX identifier is accurate. |
| Original documentation | Root Markdown, `.github/pull_request_template.md`, `docs/*`, `policy/*`, `harness/*.md` | Original expression is CC BY-NC-SA 4.0. Embedded SRD and third-party references retain their separate source boundary. |
| Application, harness, schemas, and tests | `src/*`, Python under `harness/`, schemas, configuration, and tests | Project-authored software and technical structures are BSD-3-Clause. Embedded facts and fixtures retain their source status. |
| Comparator configuration | `harness/comparators/fighter-subclasses.json` | Frozen damage input: project-authored structure and benchmark policy plus compact independently phrased facts. No project license covers the non-SRD names or mechanics. |
| Comparator provenance | `harness/provenance/fighter-subclass-comparators.json` | Value-bound legal/source metadata covering every scalar comparator leaf. Owner-source records remain preserved; residual `unresolved_counsel` flags on non-SRD official facts are legal-use cautions, not missing-source evidence. It is a build input but never a damage evaluator or comparator-hash input. |
| SRD creature catalog, rosters, and provenance | `harness/data/srd_creatures.json`, `harness/data/srd_creature_rosters.json`, `harness/provenance/srd-creatures.json` | Selected normalized SRD facts remain CC BY 4.0 with attribution and modification marking; full stat-block and trait prose is not reproduced. |
| Reference register | `review/wizards-ip-reference-register.json` | Project-authored, content-bound audit metadata for the declared scanner lexicon. It records classifications and does not itself grant third-party rights or prove universal discovery. |
| Generated publications and bundles | Prototype/release HTML and release legal assets | Mixed publication with scoped notices; current release/deployable paths retain the four legal assets. |
| Historical release workflows | `.github/workflows/publish-v13.*.yml`, `publish-v14.0.0.yml` | Frozen snapshots remain historical records and were not modernized in place. |

Package metadata continues to use `SEE LICENSE IN LICENSE.md`; dependency licenses remain their own. A blanket SPDX identifier would be inaccurate for mixed YAML, configuration, reports, and generated HTML.

## Maintainer identity, authority, and product policy

The maintainer resolution in issue #63 comment `5291975732` states that Kyle Martin, NixNinja, and `kmart01123` are the same natural person; NixNinja is Kyle Martin’s public creator pseudonym, and `kmart01123` is his repository account. Kyle Martin states that he authored or has authority to license the project-authored contributions attributed to NixNinja. Existing public attribution remains NixNinja. No email address is published, and this resolution introduces no holder-text change, DCO, CLA, or contributor agreement.

The declared permanent product policy is noncommercial for the original Kinetic Vanguard homebrew rules and content, which remain CC BY-NC-SA 4.0. The maintainer does not intend to sell, crowdfund, commercially license, or commercially promote that homebrew content. This is not a blanket whole-repository relicense: project software remains BSD-3-Clause, SRD material remains CC BY 4.0, and third-party material remains outside the project’s licenses. The existing license files already express these component boundaries and are intentionally unchanged.

CC BY-NC-SA 4.0 does not license Wizards names or mechanics, apply to the whole repository, override BSD-3-Clause or CC BY 4.0 rights, guarantee that no legal objection will arise, or supply rights the maintainer does not own.

## Comparator field provenance result

`harness/provenance/fighter-subclass-comparators.json` now covers all 69 scalar leaves of `harness/comparators/fighter-subclasses.json` one-to-one. Stable dotted paths and array indexes identify leaves, and each row binds the current scalar through SHA-256 of its canonical JSON value. The earlier issue #63 artifact covered 65 leaves; issue #65 PR1 changes comparator values and policy identities under separate authority while preserving the accepted historical damage evidence and making no fresh complete-matrix claim.

The source model separates:

- official SRD 5.2.1 and its pinned PDF identity;
- `Wizards of the Coast LLC, Player’s Handbook, 2024`;
- accepted compact Battle Master records, including owner-source issue #52 comment `5291985967`;
- accepted compact Eldritch Knight records, including owner-source issue #50 comment `5291987976`; and
- project-authored benchmark methodology, loadout/profile assumptions, and tactical-policy decisions, with the issue #65 successor contract bound to comments `5300138781` and `5300161056` and implementation base `5fcee4b94dd97d0b8b88df3449358c74bd717c7c`.

A source-supported non-SRD official fact uses an exact print page only when personally verified; otherwise it uses a stable current-digital section or record plus owner-source attestation. No page was guessed, and no source bytes are retained. This metadata establishes a repository source chain, not legal clearance. Project-authored methodology is not mislabeled as a Player’s Handbook fact, and records contain compact facts and locators rather than copied source prose.

The three formerly open source/methodology records are resolved:

- Great Weapon Master’s Proficiency Bonus relation is owner-source verified through issue #52 comment `5291985967` and `https://www.dndbeyond.com/feats/1789149-great-weapon-master`.
- Dueling’s one-hand/no-other-weapon condition and `+2` value are owner-source verified through issue #50 comment `5291987976` and `https://www.dndbeyond.com/feats/1789131-dueling`.
- Hew’s complete official fact is owner-source verified through issue #52 comment `5291985967` and `https://www.dndbeyond.com/feats/1789149-great-weapon-master`: immediately after a Critical Hit or after reducing a target to 0 Hit Points, the character can make a Bonus Action attack with the same weapon.

Great Weapon Master, Dueling, and the decomposed Hew cadence and same-weapon leaves retain `unresolved_counsel=true` only as conservative residual-use/legal cautions, not as missing-source evidence. The configured reserved Bonus Action is separately classified as a project-authored benchmark assumption with `unresolved_counsel=false`.

The legacy once-per-round Hew comparator scalar is retired. The nominal successor records once-per-Fighter-turn cadence, a reserved Bonus Action, and a same-weapon follow-up separately. Target death is disabled in `nominal_sustained_dpr_v1`, so only the Critical Hit route is reachable; this does not claim that the official reducing-to-0-HP trigger does not exist or is modeled in PR1. The follow-up is outside the Attack action, receives no Great Weapon Master Attack-action bonus, and cannot recursively create another Hew entitlement after the turn token is spent.

Issue #65 resolves the earlier methodology fork by retaining no-target-death sustained DPR as the nominal result and naming finite-HP/kill-cleave modes separately. Those finite modes fail closed in PR1. Implementing the zero-HP trigger, target death, retargeting, or finite Ball Lightning remains a separately authorized PR2 scope and requires fresh affected comparator/evaluator review and analytical evidence. The complete 47-target matrix likewise remains a separately authorized consumable run and was not performed for this PR1 implementation.

The source classifications are `srd_5_2_1_fact`, `non_srd_official_fact`, `project_authored_benchmark_assumption`, `project_authored_tactical_policy`, and `narrow_nominative_identifier`. Expression classifications distinguish bare numeric facts, compact independently phrased relational facts, project policy, and identifiers. These labels record a conservative engineering boundary; they do not decide whether an individual mechanic is copyrightable.

## Public naming and trademark disposition

`Battle Master` and `Eldritch Knight` are retained under an accepted maintainer risk disposition only as narrow unofficial identifiers needed for benchmark intelligibility and reproducibility. The homebrew product is permanently noncommercial. These names are not branding, product titles, logos, badges, or promotional hooks; existing unofficial, no-affiliation, no-endorsement, and no-project-license boundaries remain. This is not legal clearance. Reopen the review if the distribution context changes materially; permissibility remains context- and jurisdiction-dependent.

The other explicit dispositions are:

- `D&D` and `Dungeons & Dragons`: retain only where needed to identify official sources or describe the audited boundary; no logo, trade dress, or official-status presentation.
- `D&D Beyond`: retain in official source URLs and narrow bibliographic/source references. Its Basic Rules are not an accepted publishing source.
- `Wizards of the Coast`: retain in the exact SRD attribution, separate official bibliography, legal-boundary statements, and historical records. Do not embellish the supplied attribution.
- `Player’s Handbook`: retain only as a non-SRD bibliographic title with a personally verified exact print page, or a stable current-digital section/record plus owner-source attestation; do not characterize it as CC-licensed by this project.
- `Dungeon Master’s Guide` and `Monster Manual`: current mentions are audit/search terms or boundary explanations, not project source claims.

No disposition asserts ownership of a Wizards mark, that names or mechanics are CC-licensed, or that nominative/reference treatment is guaranteed in every jurisdiction.

## SRD, Basic Rules, and non-SRD bibliography boundary

The exact Wizards-supplied SRD attribution is retained byte-for-byte in `NOTICE.md`, canonical metadata, generated publications, and harness reports. Its standalone UTF-8 identity is 319 bytes and SHA-256 `f2e3568c8377f47c48dab84d64d1fc08aed723f0efabcb8a26e91c761cb59171`. The separate supplied Section 5 sentence is 120 bytes and SHA-256 `f439d59ec753e22ce22321f3a126ebc5641bb713799c74199feecc86f927a282`. Modification marking remains present.

The D&D Beyond Basic Rules are expressly rejected as comparator, creature, or publication provenance. Current creature data remains bound to the pinned SRD PDF, source pages/order/anchors, and the existing normalized-fact modification statement. Non-SRD bibliography is metadata only and remains separate from exact SRD attribution, project copyright, and no-affiliation language. Notices do not manufacture rights in non-SRD material.

## Generated, publication, and release findings

Fresh prototype and authorized release builds were generated into temporary directories and audited without committing HTML. The relationship boundary is a combined treatment: each HTML surface carries inline no-endorsement wording, while the linked `NOTICE.md` supplies the complete no-affiliation/no-endorsement and non-SRD boundary. Neither component is described as containing the other’s full wording. Each HTML surface retained:

- project copyright and component-license boundaries;
- exact SRD attribution plus modification and disclaimer language;
- an inline statement that SRD use does not imply endorsement; and
- links to `LICENSE.md` and `NOTICE.md`, with `NOTICE.md` carrying the full no-affiliation/no-endorsement and non-SRD boundary.

The release manifest changed only because the two new maintained records were added to `build/inputs.json`. Existing promotion and publication guards still require all four legal assets: `LICENSE.md`, `LICENSE-CODE`, `LICENSE-CONTENT`, and `NOTICE.md`. No generated HTML, source PDF, private capture, or new publication asset is committed.

## Private-source boundary

The issue #63 implementation used the accepted compact GitHub records from issues #50 and #52 and did not perform a broad or narrow Player’s Handbook recapture. The candidate repository tree contains no authenticated HTML, screenshot, PDF, browser storage, cookie, session or entitlement metadata, copied feature/spell description, or other private source material. The audit makes no broader claim about material outside that candidate tree and the submitted issue #63 evidence.

The accepted locator policy uses an exact print page only when personally verified; otherwise it uses a stable current-digital section or record plus owner-source attestation. Never guess a page, and retain no source bytes. This amendment required no private recapture.

## Automated guards and limits

`tests/license-contract.test.ts` now checks:

- byte-exact SRD attribution plus modification/disclaimer notices;
- absence of a project license claim over non-SRD Wizards material;
- exact one-to-one scalar comparator/provenance coverage and canonical value identities;
- required owner-source audit records and stable digital locators for Great Weapon Master, Hew, and Dueling, no `evidence_gap` on those records, and the explicit split between Hew’s official cadence/same-weapon facts and the project-authored reserved-Bonus-Action nominal profile;
- separation of project methodology from official rules;
- deterministic keys/enums, compact single-line prose, and rejection of Basic Rules provenance;
- resolved identity and authority without a published email, retained NixNinja attribution, component-scoped noncommercial policy, narrow unofficial comparator names, bounded scanner scope, and no legal-clearance claim;
- exact tracked-tree/reference-register set and hit-count equality for the declared hardcoded lexicon, including recursively discovered generated prototype/release surfaces;
- no tracked private/authenticated capture path and no prohibited binary extension or signature;
- the combined generated boundary: inline no-endorsement plus linked `NOTICE.md` no-affiliation/no-endorsement wording; and
- continued four-asset release bundles and rejection of OGL, stale commercial permission, or blanket licensing wording.

In-memory mutations remove/add provenance rows, change a comparator scalar, remove either owner-source record, reintroduce `evidence_gap`, relabel the reserved-Bonus-Action Hew profile as an official fact, falsely claim the zero-HP trigger is reachable in nominal mode, revert identity to unknown, assert a blanket repository-wide CC BY-NC-SA license, invent a print page, substitute Basic Rules, add multiline source-like prose, add an unregistered reference, and inject synthetic PDF/logo/private-HTML signatures. The tests must reject each mutation without embedding actual Wizards text or assets.

These checks are compact-fact, provenance, asset, and regression guards; they do not establish legal clearance. A length limit or hardcoded lexicon cannot prove non-infringement, discover every protected name or protectable paraphrase, or decide trademark/copyright law. The scanner’s complete coverage of its declared lexicon and audited surfaces is accepted methodology, not an unresolved implementation defect.

Adding the comparator-provenance and reference-register records to `build/inputs.json` necessarily increased its maintained input count from 82 to 84. The corresponding `tests/architecture.test.ts` 82→84 expectation update is the documented exception to the issue’s expected-path list; it updates only manifest cardinality and does not alter a product, comparator, evaluator, damage input, or analytical boundary.

## Confirmed corrections in issue #63

- Added the original one-to-one, value-bound scalar-leaf provenance; owner-source records resolved Great Weapon Master, Dueling, and the complete Hew official fact while the then-current Hew modeling limit was recorded for the later replacement-model contract, without changing an issue #63 comparator scalar or value identity.
- Added a deterministic, content-bound reference register that is complete for the declared hardcoded official-example/current-comparator lexicon rather than a hand-selected path list; it does not claim universal protected-name or expression discovery. This bounded scope is accepted methodology, not an unresolved implementation defect.
- Added the two maintained records to the positive build-input manifest with precise non-analytical roles.
- Added focused metadata-shape, compactness, private-capture, binary-asset, generated-surface, and mutation guards, plus the necessary 82→84 architecture-count update.
- Recorded the resolved maintainer identity and authority, component-scoped permanent noncommercial product policy, and accepted narrow comparator-name risk disposition without changing holder or license text.
- Updated this audit against the exact current base and current official creator guidance.

No defect was found in the existing exact SRD attribution, component licenses, holder text, README notice boundary, harness notice boundary, or release legal-asset inventory. Those files were not rewritten for style.

## Prior audit history preserved

The 2026-08-07 audit established the component-based license index; corrected `LICENSE-CONTENT` so it did not purport to eliminate exceptions or independently available rights; corrected heading structure in `LICENSE.md`; added canonical footer metadata, disclaimer and modification notices; made build/promotion paths hash and ship all four legal assets; and embedded structured notices in benchmark reports. It also recorded the prior tree inventory, package-license mix, and the reason no blanket SPDX identifier applies.

Those accepted corrections remain in force. Historical release assets and frozen workflows were intentionally not rewritten. `All rights reserved.` still occurs only within the scoped BSD notice in `LICENSE-CODE`. No active OGL, obsolete SRD version, blanket whole-repository license, or stale custom commercial-permission wording was introduced.

## Intentionally unchanged in issue #63

The following list records the historical issue #63 amendment boundary. It is not a claim that later, separately authorized issue #65 PR1 work left the comparator or evaluator unchanged.

- `KineticVanguard.yaml`, schemas, lockfile, comparator configuration, evaluator modules, target/roster data, accepted damage provenance, and the complete generated README damage region.
- The exact Wizards-prescribed SRD attribution and existing license assignments.
- `NixNinja` creator/copyright-holder wording.
- Battle Master and Eldritch Knight labels, comparator values, project tactical policies, and damage methodology.
- README, harness documentation, release checklist, and existing license/notice files because the audit found no concrete defect requiring edits.
- Frozen branches, tags, Releases, historical workflows, and published evidence assets.
- Analytical results and evidence; no damage, control, planner, sensitivity, or Control Value benchmark was run.

## Residual risk and independent review

The following remain legal-review questions rather than engineering conclusions:

1. Whether each non-SRD comparator fact and exact subclass-name use is permissible in its full public context, including jurisdiction-specific copyright and trademark treatment.
2. Owner-source verification resolves repository provenance and the Hew source-versus-methodology classification; it is not legal clearance or attorney approval. Great Weapon Master, Dueling, and the two decomposed Hew official-fact leaves retain only residual legal-use cautions. Nominal PR1 disables target death, while the zero-HP trigger remains in the separately authorized finite-HP contract rather than being denied or silently modeled.
3. Whether another retained or future locator satisfies the accepted locator policy, whether field classifications are complete, and whether compact independent wording could be protectable expression; the locator policy itself is settled.
4. Whether material outside the declared lexicon and audited tracked/generated surfaces raises a legal issue. The scanner is complete for those declared bounds; non-universal detection is accepted methodology, not an implementation defect.
5. Whether the existing disclaimer and citation presentation is sufficient in every intended distribution context. No notice or project license supplies third-party rights.

Exact comparator permissibility can depend on jurisdiction and context. This audit deliberately leaves those legal interpretations unresolved and makes no demand-letter guarantee.

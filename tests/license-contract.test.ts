import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { access, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { extname, join, relative, resolve } from "node:path";
import { TextDecoder } from "node:util";
import { executeBuild } from "../src/build.js";
import { canonicalJson, sha256 } from "../src/canonical.js";
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

const classificationDefinitionContract={
  srd_5_2_1_licensed_use:"SRD 5.2.1 source material or required attribution used under CC BY 4.0.",
  original_project_content:"Project-authored code, policy, tests, audit language, or compact technical structure.",
  narrow_nominative_reference:"Limited unofficial reference needed to identify a source, product, publisher, or comparator.",
  independently_expressed_factual_mechanic:"Compact fact or relation expressed independently without source descriptive prose.",
  historical_reference_in_current_documentation:"Current tracked record describing frozen or superseded history without reactivating it.",
  uncertain_counsel_review:"Engineering evidence is insufficient for a legal disposition; qualified counsel review remains.",
  remove_or_rename:"Reference is not justified by the current audited purpose and should be removed or renamed."
} as const;
const termDispositionContract=[
  {term:"Battle Master",disposition:"retain_narrow_unofficial_identifier",public_use:"Benchmark labels and reproducibility references only; no branding or promotional use.",rationale:"Exact name identifies the frozen comparator; a neutral label would obscure prior evidence and methodology.",residual_counsel:true},
  {term:"D&D",disposition:"retain_narrow_source_reference",public_use:"Official-source identification and audited boundary only; no logo or official-status presentation.",rationale:"Short source name is sometimes needed for intelligibility but is not project branding.",residual_counsel:false},
  {term:"D&D Beyond",disposition:"retain_source_and_url_reference",public_use:"Official URLs and bibliography only; Basic Rules are rejected as publication provenance.",rationale:"The host identifies current official guidance and SRD downloads.",residual_counsel:false},
  {term:"Dungeons & Dragons",disposition:"retain_only_when_source_identification_requires",public_use:"Audit/search definition and necessary official-source identification only.",rationale:"No current product-branding use is needed.",residual_counsel:false},
  {term:"Eldritch Knight",disposition:"retain_narrow_unofficial_identifier",public_use:"Benchmark labels and reproducibility references only; no branding or promotional use.",rationale:"Exact name identifies the frozen comparator; a neutral label would obscure prior evidence and methodology.",residual_counsel:true},
  {term:"Player's Handbook",disposition:"retain_non_srd_bibliography",public_use:"Title, publisher, year, and exact page or accepted stable digital locator only.",rationale:"The title identifies non-SRD source records without claiming a project license.",residual_counsel:true},
  {term:"Wizards of the Coast",disposition:"retain_exact_attribution_and_bibliography",public_use:"Exact SRD attribution, separate bibliography, and scoped legal-boundary statements only.",rationale:"Publisher identification and required attribution are necessary; embellishment is prohibited.",residual_counsel:false}
] as const;
const officialSourceContract={
  cc_by_4_0:{url:"https://creativecommons.org/licenses/by/4.0/legalcode",text_url:"https://creativecommons.org/licenses/by/4.0/legalcode.txt",retrieved_on:"2026-08-14",text_sha256:"9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411"},
  cc_marking_guidance:{url:"https://creativecommons.org/cc-license-your-work/",retrieved_on:"2026-08-14"},
  creator_faq:{url:"https://www.dndbeyond.com/creator-faq",displayed_publication_date:"2025-04-22",retrieved_on:"2026-08-14"},
  fan_content_policy:{url:"https://company.wizards.com/en/legal/fancontentpolicy",displayed_update_date:"2017-11-15",retrieved_on:"2026-08-14",use_boundary:"Non-TRPG fan-content distinction only; not comparator or SRD publication authority."},
  phb_2024:{bibliography:"Wizards of the Coast LLC, Player's Handbook, 2024",boundary:"Non-SRD official bibliography only; exact pages or stable digital locators remain in accepted issue #50 and #52 audit records."},
  srd_5_2_1_page:{url:"https://www.dndbeyond.com/srd",displayed_update_date:"2026-03-02",retrieved_on:"2026-08-14"},
  srd_5_2_1_pdf:{url:"https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",published_on:"2025-05-01",retrieved_on:"2026-08-14",size_bytes:6031375,sha256:"8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87"}
} as const;

const originalSrdReferencePaths=new Set([
  "CHANGELOG.md","RELEASE_CHECKLIST.md","build/inputs.json","docs/licensing-audit.md","harness/MIGRATION.md","harness/README.md",
  "harness/config/benchmark.json","harness/config/creature-consumers.json","harness/provenance/fighter-subclass-comparators.json","review/wizards-ip-reference-register.json"
]);
const mechanicallyNecessaryReferencePaths=new Set([
  "KineticVanguard.yaml","harness/comparators/fighter-subclasses.json","harness/creature_catalog.py","harness/creature_control_projection.py",
  "harness/creature_damage_projection.py","harness/damage_harness.py","harness/damage_report.py","harness/data/srd_creature_rosters.json",
  "harness/data/srd_creatures.json","harness/model.py","harness/provenance/damage-delta-v14.1-to-v14.2.json","harness/provenance/damage-review.json",
  "harness/provenance/fighter-subclass-comparators.json","harness/provenance/srd-creatures.json","harness/readme_damage.py","src/creature-catalog.ts",
  "tests/harness-authority.test.ts","tests/readme-contract.test.ts"
]);

interface RegisterEntryMetadata{classification:string;rationale:string;required_notice_or_locator:string;mechanically_necessary:boolean;counsel_review:boolean}
function expectedRegisterMetadata(entry:DerivedReferenceEntry):RegisterEntryMetadata{
  const mechanically_necessary=mechanicallyNecessaryReferencePaths.has(entry.path)&&["srd_reference","non_srd_comparator_identifier","non_srd_feat_feature_reference","srd_replacement_name_reference"].includes(entry.category_id);
  switch(entry.category_id){
    case "srd_reference":
    case "srd_replacement_name_reference":{
      if(entry.path.startsWith(".github/workflows/publish-"))return{classification:"historical_reference_in_current_documentation",rationale:"Frozen workflow reference records superseded publication history without reactivating it.",required_notice_or_locator:"Tracked historical workflow; NOTICE.md",mechanically_necessary:false,counsel_review:false};
      const original=entry.surface==="generated"&&entry.path==="build-manifest.json"||entry.surface==="public"&&(originalSrdReferencePaths.has(entry.path)||/\.(?:ts|py)$/.test(entry.path)||entry.path.startsWith("tests/")||entry.path.startsWith("harness/tests/"));
      if(original)return{classification:"original_project_content",rationale:"Project-authored code, test, audit, manifest, or compact identifier reference; not SRD source material or required attribution.",required_notice_or_locator:"NOTICE.md; source identifier context in the recorded path",mechanically_necessary,counsel_review:false};
      return{classification:"srd_5_2_1_licensed_use",rationale:"Reference remains within the exact SRD attribution, modification, disclaimer, and CC BY 4.0 component boundary.",required_notice_or_locator:"NOTICE.md; pinned official SRD 5.2.1 PDF",mechanically_necessary,counsel_review:false};
    }
    case "basic_rules_reference":return{classification:"original_project_content",rationale:"Rejected source boundary; not an accepted publication, creature, or comparator provenance source.",required_notice_or_locator:"docs/licensing-audit.md > SRD, Basic Rules, and non-SRD bibliography boundary",mechanically_necessary:false,counsel_review:false};
    case "blanket_license_claim":return{classification:"original_project_content",rationale:"Negative scope guard; no whole-repository license or single SPDX claim is asserted.",required_notice_or_locator:"LICENSE.md; docs/licensing-audit.md",mechanically_necessary:false,counsel_review:false};
    case "brand_relationship_claim":return{classification:"original_project_content",rationale:"Project-authored or required no-affiliation, no-endorsement, sponsorship, connection, or official-status boundary.",required_notice_or_locator:"NOTICE.md > Third-party comparator references",mechanically_necessary:false,counsel_review:false};
    case "dnd_brand_reference":return{classification:"narrow_nominative_reference",rationale:"Narrow source or brand identification only; no logo, branding, affiliation, endorsement, or official status is asserted.",required_notice_or_locator:"docs/licensing-audit.md > Public naming and trademark disposition",mechanically_necessary:false,counsel_review:false};
    case "fan_content_policy_reference":return{classification:"narrow_nominative_reference",rationale:"Narrow official-policy boundary reference; the policy is not comparator or SRD publication authority.",required_notice_or_locator:"https://company.wizards.com/en/legal/fancontentpolicy",mechanically_necessary:false,counsel_review:false};
    case "non_srd_comparator_identifier":return{classification:"narrow_nominative_reference",rationale:"Retained unofficial comparator identification preserves benchmark intelligibility; the no-affiliation boundary and counsel question remain.",required_notice_or_locator:"NOTICE.md; harness/provenance/fighter-subclass-comparators.json",mechanically_necessary,counsel_review:true};
    case "non_srd_feat_feature_reference":{
      const original=entry.path==="docs/licensing-audit.md"||entry.path==="review/wizards-ip-reference-register.json"||entry.path.startsWith("tests/")||entry.path.startsWith("harness/tests/");
      return{classification:original?"original_project_content":"independently_expressed_factual_mechanic",rationale:original?"Project-authored audit or guard text names the bounded term without treating it as licensed source material.":"Compact independently expressed comparator fact or locator; no source descriptive prose is reproduced.",required_notice_or_locator:"harness/provenance/fighter-subclass-comparators.json; accepted issue #50/#52 records",mechanically_necessary,counsel_review:true};
    }
    case "bounded_omitted_name_reference":{
      const original=entry.path==="tests/license-contract.test.ts"||entry.path==="review/wizards-ip-reference-register.json";
      return{classification:original?"original_project_content":"narrow_nominative_reference",rationale:original?"Project-authored audit or guard text names the bounded omitted example without treating it as licensed source material.":"Bounded official SRD-page omitted-name example retained only for audit and regression detection.",required_notice_or_locator:"https://www.dndbeyond.com/srd; docs/licensing-audit.md",mechanically_necessary:false,counsel_review:true};
    }
    case "official_book_reference":return{classification:"narrow_nominative_reference",rationale:"Narrow non-SRD bibliography, source locator, or audit-boundary reference; no project license is asserted.",required_notice_or_locator:"harness/provenance/fighter-subclass-comparators.json; accepted issue #50/#52 records",mechanically_necessary:false,counsel_review:true};
    case "ogl_reference":return{classification:entry.path.startsWith(".github/workflows/publish-")?"historical_reference_in_current_documentation":"original_project_content",rationale:"Negative or historical open-license guard; no active grant is asserted.",required_notice_or_locator:"docs/licensing-audit.md > Prior audit history preserved",mechanically_necessary:false,counsel_review:false};
    case "wizards_corporate_reference":return{classification:"narrow_nominative_reference",rationale:"Narrow publisher, attribution, source, or legal-boundary reference; it is not project branding.",required_notice_or_locator:"NOTICE.md; exact SRD attribution or separate official bibliography",mechanically_necessary:false,counsel_review:false};
    case "wizards_rights_claim":return{classification:"original_project_content",rationale:"Project-authored scope statement limits project licensing and does not manufacture third-party rights.",required_notice_or_locator:"LICENSE.md; NOTICE.md",mechanically_necessary:false,counsel_review:false};
    default:assert.fail(`No register metadata policy for ${entry.category_id}`);
  }
}
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
const activeOglGrantPattern=/(?:\b(?:this|the)\s+(?:work|project|repository|content)\b.{0,100}\b(?:is|are|remains?)\s+(?:licensed|released|distributed|available)\s+under\s+(?:the\s+)?(?:OGL|Open Game License)\b|\b(?:OGL|Open Game License)\b.{0,80}\b(?:governs|licenses|applies\s+to)\s+(?:this|the)\s+(?:work|project|repository|content)\b)/isu;
const activeBlanketLicensePattern=/(?:(?<!not\s)\b(?:everything\s+in\s+(?:this|the)\s+(?:repository|project)|all\s+(?:(?:repository|project)\s+)?(?:content|material)\s+in\s+(?:this|the)\s+(?:repository|project)|(?:this|the)\s+(?:entire|whole)\s+(?:repository|project)|all\s+(?:repository|project)\s+(?:content|material))\b.{0,100}\b(?:is|are)\s+(?!not\b|never\b)(?:licensed|released|available)\s+under\b|(?<!not every file in )(?<!not everything in )\b(?:this|the)\s+(?:repository|project)\s+(?:is|are|remains?)\s+(?!not\b|never\b)(?:licensed|released|distributed|available)\s+under\b|(?<!not\s)\bevery\s+file\s+in\s+(?:this|the)\s+(?:repository|project)\s+(?:is|are)\s+(?!not\b|never\b)(?:licensed|released|available)\s+under\b)/isu;
const rejectedBasicRulesPattern=/(?:Basic[ _-]*Rules|(?:(?:https?:\/\/)?(?:www\.)?dndbeyond\.com\/)?sources\/dnd\/br-2024)(?![A-Za-z0-9])/iu;
const positiveBrandRelationshipPattern=/(?:\b(?:Kinetic\s+Vanguard|this\s+(?:project|work|publication)|the\s+(?:project|work|publication))\s+(?:is|are|has|claims)\s+(?!(?:not|never|no)\b|un(?:affiliat|official))(?:an?\s+)?(?:affiliated|endorsed|sponsored|connected|affiliation|endorsement|sponsorship|connection|official(?:[ -]status)?|officially(?:\s+(?:affiliated|endorsed|sponsored))?)(?:\s+(?:with|by|from|of))?.{0,40}\b(?:Wizards(?:\s+of\s+the\s+Coast)?|D&D|Dungeons\s*&\s*Dragons)\b|\b(?:Wizards(?:\s+of\s+the\s+Coast)?|D&D|Dungeons\s*&\s*Dragons)\s+(?:officially\s+)?(?:affiliates|endorses|sponsors|recognizes)\s+(?:Kinetic\s+Vanguard|this\s+(?:project|work|publication)|the\s+(?:project|work|publication))\b)/isu;
const positiveBrandBannerPattern=/^\s*(?:[#>*_`-]+\s*)*(?!(?:not|never|no)\b)(?:(?:affiliated\s+with|endorsed\s+by|sponsored\s+by|official[ -]status\s+(?:from|by|of))\s+(?:Wizards(?:\s+of\s+the\s+Coast)?|D&D|Dungeons\s*&\s*Dragons)\b|official\s+(?:D&D|Dungeons\s*&\s*Dragons)\s+(?:product|project|publication|work|content)\b)/iu;

function assertNoActiveWholeProjectGrant(content:string,path:string):void{
  assert.doesNotMatch(content,activeOglGrantPattern,`${path} must not activate OGL publication`);
  assert.doesNotMatch(content,activeBlanketLicensePattern,`${path} must not make a blanket project license claim`);
}

function assertNoPositiveBrandRelationshipClaim(content:string,path:string):void{
  assert.doesNotMatch(content,positiveBrandRelationshipPattern,`${path} must not assert a positive Wizards/D&D relationship or official status`);
  for(const line of content.split(/\r?\n/))assert.doesNotMatch(line,positiveBrandBannerPattern,`${path} must not present a positive Wizards/D&D relationship or official-status banner`);
}

function validateResolvedAuditPolicy(audit:string):void{
  assert.match(audit,/Kyle Martin, NixNinja, and `kmart01123` are the same natural person/);
  assert.match(audit,/NixNinja is Kyle Martin’s public creator pseudonym/);
  assert.match(audit,/`kmart01123` is his repository account/);
  assert.match(audit,/Kyle Martin states that he authored or has authority to license the project-authored contributions attributed to NixNinja/);
  assert.match(audit,/Existing public attribution remains NixNinja/);
  assert.match(audit,/No email address is published/);
  assert.doesNotMatch(audit,/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  assert.match(audit,/no holder-text change, DCO, CLA, or contributor agreement/i);
  assert.match(audit,/original Kinetic Vanguard homebrew rules and content[\s\S]{0,160}remain CC BY-NC-SA 4\.0/i);
  assert.match(audit,/project software remains BSD-3-Clause/);
  assert.match(audit,/SRD material remains CC BY 4\.0/);
  assert.match(audit,/third-party material remains outside the project’s licenses/);
  assertNoActiveWholeProjectGrant(audit,"docs/licensing-audit.md");
  assert.match(audit,/CC BY-NC-SA 4\.0 does not license Wizards names or mechanics/);
  assert.match(audit,/accepted maintainer risk disposition only as narrow unofficial identifiers needed for benchmark intelligibility and reproducibility/);
  assert.match(audit,/not branding, product titles, logos, badges, or promotional hooks/);
  assert.match(audit,/complete current-tree coverage for its hardcoded official-example and current-comparator lexicon/);
  assert.match(audit,/bounded scope is accepted audit methodology, not an unresolved implementation defect/);
  assert.match(audit,/not legal advice or a claim of legal clearance/);
  assert.match(audit,/This is not legal clearance/);
  assert.doesNotMatch(audit,/attorney (?:has )?approved/i);
  assert.match(audit,/Hew’s complete official fact is owner-source verified[\s\S]{0,260}immediately after a Critical Hit or after reducing a target to 0 Hit Points[\s\S]{0,100}Bonus Action attack with the same weapon/);
  assert.match(audit,/current critical-only, once-per-round representation is retained as deliberate conservative project methodology/);
  assert.match(audit,/accepted damage methodology is explicitly no-target-death and carries no remaining-HP, kill, overkill, replacement-target, or target-availability state/);
  assert.match(audit,/documented damage-methodology capability gap that must be resolved when the replacement damage model is independently confirmed/);
  assert.match(audit,/retain no-target-death sustained DPR as the nominal result and add a named finite-HP\/kill-cleave sensitivity/);
  assert.match(audit,/replace the nominal model with fair target-death and retargeting semantics applied consistently to Kinetic Vanguard, Battle Master, and Eldritch Knight/);
  assert.match(audit,/implementation of the zero-HP trigger is outside issue #63 and requires fresh comparator\/evaluator review and fresh affected analytical evidence/);
  for(const forbidden of ["waived","irrelevant","permanently excluded","fully represented"])assert.equal(audit.toLowerCase().includes(forbidden),false,`Hew zero-HP route must not be described as ${forbidden}`);
}

const comparatorSourceClassifications = new Set([
  "srd_5_2_1_fact",
  "non_srd_official_fact",
  "project_authored_benchmark_assumption",
  "project_authored_tactical_policy",
  "narrow_nominative_identifier"
]);
const comparatorExpressionClassifications = new Set([
  "bare_numeric_fact",
  "compact_independently_phrased_relational_fact",
  "project_authored_policy",
  "identifier_only"
]);
const comparatorLeafKeys = new Set([
  "field_path",
  "value_sha256",
  "comparator_id",
  "source_classification",
  "expression_classification",
  "source_id",
  "locator",
  "accepted_github_audit_record",
  "public_name_required",
  "rationale",
  "unresolved_counsel"
]);
const comparatorSourceKeys = new Set([
  "kind",
  "official_source_id",
  "repository",
  "issue_number",
  "issue_url",
  "accepted_records",
  "continuation_precedence",
  "scope",
  "title",
  "publisher",
  "year",
  "locator_policy",
  "access_boundary",
  "implementation_commit",
  "repository_locators",
  "decision_url",
  "ruleset",
  "official_page_url",
  "pinned_pdf_url",
  "pinned_pdf_sha256",
  "retrieved_on"
]);
const comparatorSourceKinds = new Set([
  "accepted_compact_github_audit",
  "official_non_srd_source",
  "project_authored_methodology",
  "project_maintainer_decision",
  "official_srd_source"
]);

interface ScalarEntry { readonly field_path:string; readonly value:null|boolean|number|string }
interface ComparatorLeaf extends Record<string,unknown> {
  field_path:string;
  value_sha256:string;
  comparator_id?:string;
  source_classification:string;
  expression_classification:string;
  source_id:string;
  locator:string;
  accepted_github_audit_record?:string;
  evidence_gap?:string;
  public_name_required:boolean;
  rationale:string;
  unresolved_counsel:boolean;
}

const officialNonSrdLeafPaths=new Set([
  "damage.battle_master.great_weapon_master_attack_action_bonus",
  "damage.battle_master.relentless_die",
  "damage.battle_master.relentless_minimum_level",
  "damage.battle_master.superiority_die_by_level.11",
  "damage.battle_master.superiority_die_by_level.15",
  "damage.battle_master.superiority_die_by_level.20",
  "damage.battle_master.superiority_die_by_level.7",
  "damage.battle_master.superiority_pool_by_level.11",
  "damage.battle_master.superiority_pool_by_level.15",
  "damage.battle_master.superiority_pool_by_level.20",
  "damage.battle_master.superiority_pool_by_level.7",
  "damage.eldritch_knight.dueling_damage_bonus",
  "damage.eldritch_knight.true_strike_uses_per_attack_action"
]);
const srdLeafPaths=new Set([
  "damage.battle_master.weapon.count",
  "damage.battle_master.weapon.damage_type",
  "damage.battle_master.weapon.sides",
  "damage.eldritch_knight.true_strike_damage_by_level.11.count",
  "damage.eldritch_knight.true_strike_damage_by_level.11.sides",
  "damage.eldritch_knight.true_strike_damage_by_level.15.count",
  "damage.eldritch_knight.true_strike_damage_by_level.15.sides",
  "damage.eldritch_knight.true_strike_damage_by_level.20.count",
  "damage.eldritch_knight.true_strike_damage_by_level.20.sides",
  "damage.eldritch_knight.true_strike_damage_by_level.7.count",
  "damage.eldritch_knight.true_strike_damage_by_level.7.sides",
  "damage.eldritch_knight.true_strike_damage_type",
  "damage.eldritch_knight.weapon.count",
  "damage.eldritch_knight.weapon.damage_type",
  "damage.eldritch_knight.weapon.sides"
]);
const relationalFactLeafPaths=new Set([
  "damage.battle_master.great_weapon_master_attack_action_bonus",
  "damage.battle_master.weapon.damage_type",
  "damage.eldritch_knight.true_strike_damage_type",
  "damage.eldritch_knight.weapon.damage_type"
]);
const resolvedComparatorLeafContract={
  "damage.battle_master.great_weapon_master_attack_action_bonus":{
    value_sha256:"20181d48feb7224a01fd863d75f587f6b18e2e2f409570db1f5ac4bb78f58770",
    source_classification:"non_srd_official_fact",expression_classification:"compact_independently_phrased_relational_fact",source_id:"phb_2024",
    locator:"2024 PHB digital > https://www.dndbeyond.com/feats/1789149-great-weapon-master > Heavy Weapon Mastery; owner-source issue #52 comment 5291985967",
    rationale:"Owner-source verifies that qualifying use with a weapon that has the Heavy property adds the attacker’s Proficiency Bonus to target damage; the relation is compact and not copied feat prose.",
    unresolved_counsel:true,comparator_id:"battle_master",accepted_github_audit_record:"https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5291985967"
  },
  "damage.battle_master.hew_critical_bonus_attack_once_per_round":{
    value_sha256:"b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
    source_classification:"project_authored_benchmark_assumption",expression_classification:"project_authored_policy",source_id:"project_comparator_methodology",
    locator:"damage.battle_master.hew_critical_bonus_attack_once_per_round; #52:5291985967; https://www.dndbeyond.com/feats/1789149-great-weapon-master; immediately after Critical Hit or reducing target to 0 Hit Points -> same-weapon Bonus Action attack",
    rationale:"Official feat has Critical Hit and reduce-to-0-HP triggers; conservative project methodology credits only Critical Hit, omits reduce-to-0-HP, and retains once-per-round. This scalar does not represent every official Hew trigger.",
    unresolved_counsel:false,comparator_id:"battle_master",accepted_github_audit_record:"https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5291985967"
  },
  "damage.eldritch_knight.dueling_damage_bonus":{
    value_sha256:"d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35",
    source_classification:"non_srd_official_fact",expression_classification:"bare_numeric_fact",source_id:"phb_2024",
    locator:"2024 PHB digital > https://www.dndbeyond.com/feats/1789131-dueling > Dueling; owner-source issue #50 comment 5291987976",
    rationale:"Owner-source verifies +2 damage while holding one melee weapon in one hand and no other weapon; the configured sword-and-board profile remains a separate project choice.",
    unresolved_counsel:true,comparator_id:"eldritch_knight",accepted_github_audit_record:"https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5291987976"
  }
} as const;
const comparatorSourceKeyContract=new Map<string,string[]>([
  ["github_issue_50_accepted_audit",["kind","official_source_id","repository","issue_number","issue_url","accepted_records","continuation_precedence","scope"]],
  ["github_issue_52_accepted_audit",["kind","official_source_id","repository","issue_number","issue_url","accepted_records","scope"]],
  ["phb_2024",["kind","title","publisher","year","locator_policy","access_boundary"]],
  ["project_comparator_methodology",["kind","issue_url","implementation_commit","repository_locators","scope"]],
  ["project_naming_disposition",["kind","decision_url","repository_locators","scope"]],
  ["srd_5_2_1",["kind","ruleset","publisher","official_page_url","pinned_pdf_url","pinned_pdf_sha256","retrieved_on"]]
]);
const comparatorSourceContract={
  github_issue_50_accepted_audit:{
    kind:"accepted_compact_github_audit",official_source_id:"phb_2024",repository:"kmart01123/kinetic-vanguard",issue_number:50,
    issue_url:"https://github.com/kmart01123/kinetic-vanguard/issues/50",
    accepted_records:[
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5239280314",
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5239280852",
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5239283977",
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5240411953",
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5240545305",
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5246155660",
      "https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5291987976"
    ],
    continuation_precedence:"Comments 5240411953, 5240545305, and 5246155660 control package/profile matters superseding the cumulative-package aspect of 5239283977.",
    scope:"Eldritch Knight source scope, delivery facts, spell inventory, and controlling approved profile continuations."
  },
  github_issue_52_accepted_audit:{
    kind:"accepted_compact_github_audit",official_source_id:"phb_2024",repository:"kmart01123/kinetic-vanguard",issue_number:52,
    issue_url:"https://github.com/kmart01123/kinetic-vanguard/issues/52",
    accepted_records:[
      "https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5246370516",
      "https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5246520863",
      "https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5246526864",
      "https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5246563926",
      "https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5247187489",
      "https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5291985967"
    ],
    scope:"Battle Master progression, resources, triggers, compact decompositions, and frozen comparator profile."
  },
  phb_2024:{kind:"official_non_srd_source",title:"Player’s Handbook",publisher:"Wizards of the Coast LLC",year:2024,locator_policy:"Use an accepted exact page when recorded; otherwise use a stable digital section or anchor plus its accepted GitHub audit record.",access_boundary:"Bibliographic identity only; no private source bytes or sourcebook prose are retained here."},
  project_comparator_methodology:{kind:"project_authored_methodology",issue_url:"https://github.com/kmart01123/kinetic-vanguard/issues/19",implementation_commit:"0732ac9912d492f58407b29145680b635ba52757",repository_locators:["harness/comparators/fighter-subclasses.json","harness/README.md > Damage comparators"],scope:"Frozen comparator build assumptions, analytical objective, observed-state policy, and compact configuration structure."},
  project_naming_disposition:{kind:"project_maintainer_decision",decision_url:"https://github.com/kmart01123/kinetic-vanguard/issues/63#issuecomment-5289581036",repository_locators:["NOTICE.md > unofficial comparator notice","docs/licensing-audit.md > Public naming and trademark disposition"],scope:"Retain the two names only as narrow unofficial benchmark identifiers with no affiliation or endorsement; counsel question remains."},
  srd_5_2_1:{kind:"official_srd_source",ruleset:"D&D SRD 5.2.1",publisher:"Wizards of the Coast LLC",official_page_url:"https://www.dndbeyond.com/srd",pinned_pdf_url:"https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",pinned_pdf_sha256:"8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",retrieved_on:"2026-08-14"}
} as const;

function codepointSort(values:string[]):string[]{return [...values].sort((a,b)=>a<b?-1:a>b?1:0);}

function scalarLeaves(value:unknown,path=""):ScalarEntry[]{
  if(value===null||typeof value!=="object")return [{field_path:path,value:value as null|boolean|number|string}];
  if(Array.isArray(value))return value.flatMap((child,index)=>scalarLeaves(child,`${path}[${index}]`));
  return codepointSort(Object.keys(value as Record<string,unknown>)).flatMap(key=>scalarLeaves((value as Record<string,unknown>)[key],path?`${path}.${key}`:key));
}

function assertCompactStrings(value:unknown,path:string):void{
  if(typeof value==="string"){
    assert.doesNotMatch(value,/\r|\n/,`${path} must be single-line`);
    if(!/^https:\/\//.test(value))assert.ok(value.length<=240,`${path} exceeds 240 characters`);
    return;
  }
  if(Array.isArray(value)){value.forEach((child,index)=>assertCompactStrings(child,`${path}[${index}]`));return;}
  if(value&&typeof value==="object")for(const [key,child] of Object.entries(value as Record<string,unknown>))assertCompactStrings(child,`${path}.${key}`);
}

function validateComparatorProvenance(comparator:unknown,provenance:any,comparatorBytes:string):void{
  assert.deepEqual(Object.keys(provenance),[
    "format_version","audit_date","audited_commit","subject_file","subject_sha256","scalar_leaf_count","value_identity","sources","leaves"
  ]);
  assert.equal(provenance.format_version,1);
  assert.equal(provenance.audit_date,"2026-08-14");
  assert.equal(provenance.audited_commit,"e5d81ab1271b305bee5b92bca22bb9acce0275e9");
  assert.equal(provenance.subject_file,"harness/comparators/fighter-subclasses.json");
  assert.equal(provenance.subject_sha256,sha256(comparatorBytes));
  assert.deepEqual(Object.keys(provenance.value_identity),["algorithm","canonicalization"]);
  assert.equal(provenance.value_identity.algorithm,"sha256");
  assert.match(provenance.value_identity.canonicalization,/canonical JSON scalar.*UTF-8/i);

  const expected=scalarLeaves(comparator),expectedByPath=new Map(expected.map(entry=>[entry.field_path,entry.value]));
  const leaves=provenance.leaves as ComparatorLeaf[];
  assert.equal(provenance.scalar_leaf_count,expected.length);
  assert.equal(leaves.length,expected.length);
  assert.deepEqual(leaves.map(leaf=>leaf.field_path),codepointSort(expected.map(entry=>entry.field_path)));
  assert.equal(new Set(leaves.map(leaf=>leaf.field_path)).size,leaves.length);

  const sourceIds=Object.keys(provenance.sources);
  assert.deepEqual(sourceIds,["github_issue_50_accepted_audit","github_issue_52_accepted_audit","phb_2024","project_comparator_methodology","project_naming_disposition","srd_5_2_1"]);
  assert.deepEqual(provenance.sources,comparatorSourceContract,"all reusable source records are exact");
  for(const [sourceId,source] of Object.entries(provenance.sources as Record<string,Record<string,unknown>>)){
    assert.ok(comparatorSourceKinds.has(String(source.kind)),`${sourceId} source kind`);
    assert.ok(Object.keys(source).every(key=>comparatorSourceKeys.has(key)),`${sourceId} has an unexpected source key`);
    assert.deepEqual(Object.keys(source),comparatorSourceKeyContract.get(sourceId),`${sourceId} source schema and order`);
    assertCompactStrings(source,`sources.${sourceId}`);
  }
  for(const issue of [50,52]){
    const source=provenance.sources[`github_issue_${issue}_accepted_audit`];
    assert.equal(source.kind,"accepted_compact_github_audit");
    assert.equal(source.official_source_id,"phb_2024");
    assert.equal(source.repository,"kmart01123/kinetic-vanguard");
    assert.equal(source.issue_number,issue);
    assert.equal(source.issue_url,`https://github.com/kmart01123/kinetic-vanguard/issues/${issue}`);
    assert.deepEqual(source.accepted_records,codepointSort(source.accepted_records));
    assert.equal(new Set(source.accepted_records).size,source.accepted_records.length);
    for(const record of source.accepted_records)assert.match(record,new RegExp(`^https://github\\.com/kmart01123/kinetic-vanguard/issues/${issue}#issuecomment-[0-9]+$`));
  }

  for(const leaf of leaves){
    const keys=Object.keys(leaf);
    assert.ok(keys.every(key=>comparatorLeafKeys.has(key)),`${leaf.field_path} has an unexpected key`);
    for(const key of ["field_path","value_sha256","source_classification","expression_classification","source_id","locator","public_name_required","rationale","unresolved_counsel"])assert.ok(keys.includes(key),`${leaf.field_path} missing ${key}`);
    assert.ok(expectedByPath.has(leaf.field_path),`${leaf.field_path} is not a comparator scalar leaf`);
    assert.equal(leaf.value_sha256,sha256(canonicalJson(expectedByPath.get(leaf.field_path))),`${leaf.field_path} value identity`);
    assert.match(leaf.value_sha256,/^[0-9a-f]{64}$/);
    assert.ok(comparatorSourceClassifications.has(leaf.source_classification),`${leaf.field_path} source classification`);
    assert.ok(comparatorExpressionClassifications.has(leaf.expression_classification),`${leaf.field_path} expression classification`);
    assert.ok(sourceIds.includes(leaf.source_id),`${leaf.field_path} source ID`);
    assertCompactStrings(leaf,`leaves.${leaf.field_path}`);

    const expectedComparatorId=leaf.field_path.startsWith("damage.battle_master.")?"battle_master"
      :leaf.field_path.startsWith("damage.eldritch_knight.")?"eldritch_knight"
      :leaf.field_path.startsWith("primary_comparator_ids[")?expectedByPath.get(leaf.field_path)
      :undefined;
    if(expectedComparatorId===undefined)assert.ok(["format_version","source_ruleset"].includes(leaf.field_path),`${leaf.field_path} is the only allowed comparator-free leaf`);
    assert.equal(leaf.comparator_id,expectedComparatorId,`${leaf.field_path} comparator ID binding`);
    const expectedKeys=[
      "field_path","value_sha256","source_classification","expression_classification","source_id","locator","public_name_required","rationale",
      "unresolved_counsel",
      ...(expectedComparatorId===undefined?[]:["comparator_id"]),...(leaf.accepted_github_audit_record===undefined?[]:["accepted_github_audit_record"])
    ];
    assert.deepEqual(keys,expectedKeys,`${leaf.field_path} leaf schema and order`);
    const expectedClassification=officialNonSrdLeafPaths.has(leaf.field_path)?"non_srd_official_fact"
      :srdLeafPaths.has(leaf.field_path)?"srd_5_2_1_fact"
      :leaf.field_path.includes(".tactical_policy.")?"project_authored_tactical_policy"
      :leaf.field_path.startsWith("primary_comparator_ids[")?"narrow_nominative_identifier"
      :"project_authored_benchmark_assumption";
    assert.equal(leaf.source_classification,expectedClassification,`${leaf.field_path} source classification binding`);
    const expectedExpression=expectedClassification==="narrow_nominative_identifier"?"identifier_only"
      :expectedClassification.startsWith("project_authored_")?"project_authored_policy"
      :relationalFactLeafPaths.has(leaf.field_path)?"compact_independently_phrased_relational_fact"
      :"bare_numeric_fact";
    assert.equal(leaf.expression_classification,expectedExpression,`${leaf.field_path} expression binding`);
    const expectedSource=expectedClassification==="srd_5_2_1_fact"?"srd_5_2_1"
      :expectedClassification==="non_srd_official_fact"?"phb_2024"
      :expectedClassification==="narrow_nominative_identifier"?"project_naming_disposition"
      :"project_comparator_methodology";
    assert.equal(leaf.source_id,expectedSource,`${leaf.field_path} source chain`);
    if(!leaf.field_path.startsWith("primary_comparator_ids["))assert.equal(leaf.public_name_required,false,`${leaf.field_path} does not require a public subclass name`);
    assert.equal(Object.hasOwn(leaf,"evidence_gap"),false,`${leaf.field_path} must not contain evidence_gap`);
    assert.equal(leaf.unresolved_counsel,expectedClassification==="non_srd_official_fact"||expectedClassification==="narrow_nominative_identifier",`${leaf.field_path} counsel binding`);

    if(leaf.accepted_github_audit_record){
      const issueSource=leaf.comparator_id==="battle_master"?provenance.sources.github_issue_52_accepted_audit
        :leaf.comparator_id==="eldritch_knight"?provenance.sources.github_issue_50_accepted_audit:undefined;
      assert.ok(issueSource,`${leaf.field_path} accepted record requires a comparator`);
      assert.ok(issueSource.accepted_records.includes(leaf.accepted_github_audit_record),`${leaf.field_path} accepted record must be declared by its comparator audit source`);
    }

    if(leaf.field_path.includes(".tactical_policy.")){
      assert.equal(leaf.source_classification,"project_authored_tactical_policy",`${leaf.field_path} is project policy`);
      assert.equal(leaf.expression_classification,"project_authored_policy",`${leaf.field_path} expression`);
      assert.equal(leaf.source_id,"project_comparator_methodology",`${leaf.field_path} methodology source`);
      assert.ok(leaf.locator.includes(`harness/comparators/fighter-subclasses.json > ${leaf.field_path}`),`${leaf.field_path} exact field locator`);
      assert.ok(leaf.locator.includes("harness/README.md > Damage comparators"),`${leaf.field_path} exact methodology heading`);
    }
    if(leaf.field_path.startsWith("primary_comparator_ids[")){
      assert.equal(leaf.source_classification,"narrow_nominative_identifier");
      assert.equal(leaf.expression_classification,"identifier_only");
      assert.equal(leaf.source_id,"project_naming_disposition");
      assert.equal(leaf.public_name_required,true);
      assert.equal(leaf.unresolved_counsel,true);
    }
    if(leaf.source_classification==="non_srd_official_fact"){
      assert.equal((provenance.sources[leaf.source_id] as {kind:string}).kind,"official_non_srd_source",`${leaf.field_path} official source`);
      assert.match(leaf.locator,/(?:\bp\.\s*\d+\b|\bdigital\s*>\s*[^>#;]+(?:\s*>\s*[^;]+|\s*>\s*#[A-Za-z0-9][A-Za-z0-9_-]*))/i,`${leaf.field_path} exact page or stable digital locator`);
      assert.ok(leaf.accepted_github_audit_record,`${leaf.field_path} accepted audit record`);
      assert.ok(["bare_numeric_fact","compact_independently_phrased_relational_fact"].includes(leaf.expression_classification),`${leaf.field_path} independent expression`);
      assert.equal(leaf.unresolved_counsel,true);
    }
  }
  for(const [fieldPath,expectedContract] of Object.entries(resolvedComparatorLeafContract)){
    const leaf=leaves.find(candidate=>candidate.field_path===fieldPath);assert.ok(leaf,fieldPath);
    assert.deepEqual({
      value_sha256:leaf.value_sha256,source_classification:leaf.source_classification,expression_classification:leaf.expression_classification,
      source_id:leaf.source_id,locator:leaf.locator,rationale:leaf.rationale,unresolved_counsel:leaf.unresolved_counsel,
      comparator_id:leaf.comparator_id,accepted_github_audit_record:leaf.accepted_github_audit_record
    },expectedContract,`${fieldPath} resolved owner-source and methodology contract`);
  }
  const dueling=leaves.find(leaf=>leaf.field_path==="damage.eldritch_knight.dueling_damage_bonus");
  assert.equal(dueling?.source_classification,"non_srd_official_fact");
  assert.equal(dueling?.unresolved_counsel,true,"Dueling retains only a residual-use legal caution, not a source gap");
  assert.doesNotMatch(JSON.stringify(provenance),rejectedBasicRulesPattern,"D&D Beyond Basic Rules are not provenance anywhere");
}

const referenceCategoryContract = [
  {id:"dnd_brand_reference",definition:"D&D, Dungeons & Dragons, and D&D Beyond names or official-domain references.",patterns:[
    {id:"dnd_abbreviation",source:"(?<![A-Za-z0-9])D&D(?![A-Za-z0-9])",flags:"giu"},
    {id:"dungeons_and_dragons",source:"Dungeons\\s*&\\s*Dragons",flags:"giu"},
    {id:"dnd_beyond_name",source:"D&D\\s+Beyond",flags:"giu"},
    {id:"dnd_beyond_domain",source:"dndbeyond\\.com",flags:"giu"}
  ]},
  {id:"wizards_corporate_reference",definition:"Wizards of the Coast identity, ownership shorthand, or official corporate-domain reference.",patterns:[
    {id:"wizards_of_the_coast",source:"Wizards\\s+of\\s+the\\s+Coast",flags:"giu"},
    {id:"wizards_owned",source:"Wizards-owned",flags:"giu"},
    {id:"wizards_domain",source:"company\\.wizards\\.com",flags:"giu"}
  ]},
  {id:"non_srd_comparator_identifier",definition:"Current non-SRD Battle Master or Eldritch Knight natural or stable machine identifier.",patterns:[
    {id:"battle_master",source:"Battle[ _-]Master",flags:"giu"},
    {id:"eldritch_knight",source:"Eldritch[ _-]Knight",flags:"giu"},
    {id:"battle_master_initialism",source:"(?<![A-Za-z0-9])B(?:M)(?![A-Za-z0-9])",flags:"giu"},
    {id:"eldritch_knight_initialism",source:"(?<![A-Za-z0-9])E(?:K)(?![A-Za-z0-9])",flags:"giu"}
  ]},
  {id:"non_srd_feat_feature_reference",definition:"Bounded current non-SRD comparator feat, feature, and maneuver names.",patterns:[
    {id:"great_weapon_master",source:"Great[ _-]+Weapon[ _-]+Master",flags:"giu"},
    {id:"heavy_weapon_mastery",source:"Heavy[ _-]+Weapon[ _-]+Mastery",flags:"giu"},
    {id:"hew",source:"(?<![A-Za-z0-9])H(?:ew)(?![A-Za-z0-9])",flags:"giu"},
    {id:"dueling",source:"(?<![A-Za-z0-9])Duel(?:ing)(?![A-Za-z0-9])",flags:"giu"},
    {id:"relentless",source:"(?<![A-Za-z0-9])Relent(?:less)(?![A-Za-z0-9])",flags:"giu"},
    {id:"combat_superiority",source:"(?:(?:Improved|Ultimate)[ _-]+)?Combat[ _-]+Superiority",flags:"giu"},
    {id:"superiority_die",source:"Superiority[ _-]+D(?:ie|ice)",flags:"giu"},
    {id:"war_magic",source:"War[ _-]+Magic",flags:"giu"},
    {id:"precision_attack",source:"Precision[ _-]+Attack",flags:"giu"},
    {id:"great_weapon_master_initialism",source:"(?<![A-Za-z0-9])G(?:WM)(?![A-Za-z0-9])",flags:"giu"}
  ]},
  {id:"bounded_omitted_name_reference",definition:"Bounded official SRD-page examples of names omitted from SRD 5.2.1.",patterns:[
    {id:"deck_of_many_things",source:"Deck\\s+of\\s+Many\\s+Things",flags:"giu"},
    {id:"orb_of_dragonkind",source:"Orb\\s+of\\s+Dragonkind",flags:"giu"},
    {id:"artificer",source:"(?<![A-Za-z0-9])Artific(?:er)(?![A-Za-z0-9])",flags:"giu"},
    {id:"aasimar",source:"(?<![A-Za-z0-9])Aasim(?:ar)(?![A-Za-z0-9])",flags:"giu"},
    {id:"beholder",source:"(?<![A-Za-z0-9])Behold(?:er)(?![A-Za-z0-9])",flags:"giu"},
    {id:"strahd",source:"(?<![A-Za-z0-9])Stra(?:hd)(?![A-Za-z0-9])",flags:"giu"},
    {id:"orcus",source:"(?<![A-Za-z0-9])Orc(?:us)(?![A-Za-z0-9])",flags:"giu"},
    {id:"tiamat",source:"(?<![A-Za-z0-9])Tia(?:mat)(?![A-Za-z0-9])",flags:"giu"},
    {id:"forgotten_realms",source:"Forgotten\\s+Realms",flags:"giu"}
  ]},
  {id:"srd_replacement_name_reference",definition:"Bounded SRD 5.2.1 replacement names identified by the official SRD page.",patterns:[
    {id:"mysterious_deck",source:"Mysterious\\s+Deck",flags:"giu"},
    {id:"dragon_orb",source:"Dragon\\s+Orb",flags:"giu"}
  ]},
  {id:"official_book_reference",definition:"Player's Handbook, Dungeon Master's Guide, Monster Manual, PHB, or DMG bibliographic reference.",patterns:[
    {id:"players_handbook",source:"Player(?:[’']s|s)\\s+Handbook|(?<![A-Za-z0-9])PHB(?![A-Za-z0-9])",flags:"giu"},
    {id:"dungeon_masters_guide",source:"Dungeon\\s+Master(?:[’']s|s)\\s+Guide|(?<![A-Za-z0-9])DMG(?![A-Za-z0-9])",flags:"giu"},
    {id:"monster_manual",source:"Monster\\s+Manual",flags:"giu"}
  ]},
  {id:"srd_reference",definition:"SRD, SRD 5.2.1, SRD machine identifier, or System Reference Document reference.",patterns:[
    {id:"srd",source:"(?<![A-Za-z0-9])SRD(?:\\s*5\\.2\\.1|_CC_v5\\.2\\.1|_?521)?(?![A-Za-z0-9])",flags:"giu"},
    {id:"system_reference_document",source:"System\\s+Reference\\s+Document",flags:"giu"}
  ]},
  {id:"basic_rules_reference",definition:"D&D Beyond Basic Rules reference, which may appear only as a rejected provenance boundary.",patterns:[
    {id:"basic_rules",source:"Basic(?:[ _-]+Rules|Rules)",flags:"giu"},
    {id:"basic_rules_url",source:"(?<![A-Za-z0-9])(?:(?:(?:https?://)?(?:www\\.)?dndbeyond\\.com/)?sources/dnd/br-2024)(?![A-Za-z0-9])",flags:"giu"}
  ]},
  {id:"ogl_reference",definition:"OGL or Open Game License reference, limited to negative or historical discussion.",patterns:[
    {id:"ogl",source:"(?<![A-Za-z0-9])OGL(?![A-Za-z0-9])",flags:"giu"},
    {id:"open_game_license",source:"Open\\s+Game\\s+License",flags:"giu"}
  ]},
  {id:"fan_content_policy_reference",definition:"Wizards Fan Content Policy name or official policy URL.",patterns:[
    {id:"fan_content_policy",source:"Fan\\s+Content\\s+Policy|company\\.wizards\\.com/en/legal/fancontentpolicy",flags:"giu"}
  ]},
  {id:"brand_relationship_claim",definition:"Affiliation, endorsement, sponsorship, connection, or official-status wording relevant to source and brand boundaries.",patterns:[
    {id:"relationship",source:"(?:Wizards|SRD|D&D|Battle[ _-]Master|Eldritch[ _-]Knight).{0,160}\\b(?:affiliat(?:e|ed|ion)|endors(?:e|ed|ement)|sponsor(?:ed|ship)|connection|official[ -]status)\\b|\\b(?:affiliat(?:e|ed|ion)|endors(?:e|ed|ement)|sponsor(?:ed|ship)|connection|official[ -]status)\\b.{0,160}(?:Wizards|SRD|D&D|Battle[ _-]Master|Eldritch[ _-]Knight)",flags:"gisu"}
  ]},
  {id:"wizards_rights_claim",definition:"Statement about project licensing, copyright, trademark, ownership, or rights in Wizards material.",patterns:[
    {id:"rights_boundary",source:"Wizards-owned|rights?\\s+in\\s+Wizards|project\\s+license.{0,120}Wizards|Wizards.{0,120}(?:copyright|trademark|ownership)",flags:"gisu"}
  ]},
  {id:"blanket_license_claim",definition:"Whole-repository, blanket-license, or single-SPDX wording requiring a scoped negative disposition.",patterns:[
    {id:"blanket_license",source:"whole[- ]repository\\s+license|blanket\\s+(?:whole[- ]repository\\s+)?license|single\\s+SPDX",flags:"giu"},
    {id:"active_blanket_license",source:"(?:(?<!not\\s)(?:everything\\s+in\\s+(?:this|the)\\s+(?:repository|project)|every\\s+file\\s+in\\s+(?:this|the)\\s+(?:repository|project)).{0,100}\\b(?:is|are)\\s+(?!not\\b|never\\b)(?:licensed|released|available)\\s+under\\b|(?<!not\\s)(?:this|the)\\s+(?:repository|project)\\s+(?:is|are|remains?)\\s+(?!not\\b|never\\b)(?:licensed|released|distributed|available)\\s+under\\b)",flags:"gisu"}
  ]}
] as const;

interface DerivedReferenceEntry {
  surface_id:string;
  path:string;
  category_id:string;
  matched_terms:string[];
  expected_hit_count:number;
  surface:"public"|"generated";
}

function deriveReferenceEntries(surfaces:Array<{surface_id:string;path:string;content:string;surface:"public"|"generated"}>):DerivedReferenceEntry[]{
  const entries:DerivedReferenceEntry[]=[];
  for(const surface of surfaces){
    const searchable=`${surface.path}\n${surface.content}`;
    for(const category of referenceCategoryContract){
      const matched_terms:string[]=[];let expected_hit_count=0;
      for(const pattern of category.patterns){
        const count=Array.from(searchable.matchAll(new RegExp(pattern.source,pattern.flags))).length;
        if(count){matched_terms.push(pattern.id);expected_hit_count+=count;}
      }
      if(expected_hit_count)entries.push({surface_id:surface.surface_id,path:surface.path,category_id:category.id,matched_terms,expected_hit_count,surface:surface.surface});
    }
  }
  return entries.sort((a,b)=>a.surface_id<b.surface_id?-1:a.surface_id>b.surface_id?1:a.category_id<b.category_id?-1:a.category_id>b.category_id?1:0);
}

function trackedStageZeroPaths():string[]{
  const raw=execFileSync("git",["ls-files","--stage","-z"],{encoding:"utf8"});const paths:string[]=[];
  for(const record of raw.split("\0").filter(Boolean)){
    const match=/^(\d{6}) [0-9a-f]+ (\d)\t(.+)$/.exec(record);assert.ok(match,record);
    assert.equal(match[1],"100644",`${match[3]} must be a regular tracked file`);
    assert.equal(match[2],"0",`${match[3]} must be a stage-zero path`);
    paths.push(match[3]!);
  }
  return codepointSort(paths);
}

const riskyAssetExtensions=new Set([".pdf",".png",".jpg",".jpeg",".gif",".webp",".svg",".svgz",".bmp",".tif",".tiff",".ico",".cur",".psd",".eps",".ai",".ttf",".otf",".eot",".woff",".woff2",".mp3",".wav",".ogg",".flac",".aac",".m4a",".mp4",".webm",".mkv",".mov",".avi",".flv",".html",".htm",".mhtml",".har",".zip",".gz",".tar",".7z",".rar"]);
const suspiciousPrivatePath=/(?:^|[\/._ -])(?:(?:storage|auth|browser|session)[\/._ -]*state|private(?:[\/._ -]+(?:evidence|source|captures?))?|authenticated|cookies?|sessions?(?:[\/._ -]+metadata)?|entitlements?|browser[\/._ -]+storage|source[\/._ -]+captures?|phb[\/._ -]+captures?)(?=$|[\/._ -])/i;

function assertNoStructuredPrivateState(content:string,path:string):void{
  let parsed:unknown;
  try{parsed=JSON.parse(content);}catch{return;}
  if(parsed===null||typeof parsed!=="object"||Array.isArray(parsed))return;
  const record=parsed as Record<string,unknown>;
  const stateKeys=[
    ["cook","ies"].join(""),["orig","ins"].join(""),["local","Storage"].join(""),["session","Storage"].join(""),
    ["storage","State"].join(""),["auth","State"].join(""),["browser","State"].join(""),["session","State"].join("")
  ];
  for(const key of stateKeys){
    const value=record[key];
    assert.equal(Array.isArray(value)||(value!==null&&typeof value==="object"),false,`${path} contains top-level private browser/auth state key ${key}`);
  }
}

function decodeApprovedAsset(path:string,bytes:Buffer,allowGeneratedHtml=false):string{
  const extension=extname(path).toLowerCase();
  assert.equal(riskyAssetExtensions.has(extension)&&!(allowGeneratedHtml&&extension===".html"),false,`${path} has an unapproved asset extension`);
  assert.doesNotMatch(path,suspiciousPrivatePath,`${path} resembles a private/authenticated capture path`);
  assert.equal(bytes.includes(0),false,`${path} contains NUL bytes and is not approved text`);
  const signatures:[string,Buffer][]=[
    ["PDF",Buffer.from("%PDF-")],["PNG",Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a])],
    ["JPEG",Buffer.from([0xff,0xd8,0xff])],["GIF",Buffer.from("GIF8")],["ZIP",Buffer.from([0x50,0x4b,0x03,0x04])],
    ["WOFF",Buffer.from("wOFF")],["WOFF2",Buffer.from("wOF2")],["OpenType",Buffer.from("OTTO")],
    ["TrueType",Buffer.from([0x00,0x01,0x00,0x00])],["RIFF media",Buffer.from("RIFF")],
    ["MP3",Buffer.from("ID3")],["Ogg media",Buffer.from("OggS")],["FLAC",Buffer.from("fLaC")],
    ["BMP",Buffer.from([0x42,0x4d])],["little-endian TIFF",Buffer.from([0x49,0x49,0x2a,0x00])],["big-endian TIFF",Buffer.from([0x4d,0x4d,0x00,0x2a])],
    ["ICO",Buffer.from([0x00,0x00,0x01,0x00])],["cursor",Buffer.from([0x00,0x00,0x02,0x00])],["EBML media",Buffer.from([0x1a,0x45,0xdf,0xa3])],
    ["gzip",Buffer.from([0x1f,0x8b])],["7z",Buffer.from([0x37,0x7a,0xbc,0xaf,0x27,0x1c])],["RAR",Buffer.from("Rar!")],
    ["Photoshop",Buffer.from("8BPS")],["Flash video",Buffer.from("FLV")],["PostScript",Buffer.from("%!PS")]
  ];
  for(const [label,signature] of signatures)assert.equal(bytes.subarray(0,signature.length).equals(signature),false,`${path} has an unapproved ${label} signature`);
  assert.equal(bytes.subarray(0,1024).indexOf(Buffer.from("%PDF-"))<0,true,`${path} has an unapproved PDF header`);
  assert.equal(bytes.length>=8&&bytes.subarray(4,8).equals(Buffer.from("ftyp")),false,`${path} has an unapproved ISO media signature`);
  let content:string;
  try{content=new TextDecoder("utf-8",{fatal:true}).decode(bytes);}catch{assert.fail(`${path} is not valid UTF-8 text`);}
  const afterPreamble=(allowXml:boolean)=>{
    let candidate=content,previous="";
    while(candidate!==previous){
      previous=candidate;candidate=candidate.replace(/^\s+/,"").replace(/^<!--[\s\S]*?-->/,"");
      if(allowXml)candidate=candidate.replace(/^<\?xml\b[\s\S]*?\?>/i,"");
    }
    return candidate;
  };
  if(!allowGeneratedHtml)assert.doesNotMatch(afterPreamble(false),/^(?:<!doctype\s+html|<html(?:\s|>))/i,`${path} resembles an HTML source capture`);
  assert.doesNotMatch(afterPreamble(true),/^<svg(?:\s|>)/i,`${path} resembles an SVG asset`);
  assert.doesNotMatch(content,/(?:^|\n)version https:\/\/git-lfs\.github\.com\/spec\/v1(?:\r?\n|$)/,`${path} is a Git LFS pointer rather than audited content`);
  assert.doesNotMatch(content,/\bdata:(?:image|audio|video|font)\/[A-Za-z0-9.+-]+(?:;[^,\s]*)?,/i,`${path} embeds an unapproved asset data URI`);
  assertNoStructuredPrivateState(content,path);
  assertNoPositiveBrandRelationshipClaim(content,path);
  return content;
}

async function recursiveFiles(root:string):Promise<string[]>{
  const files:string[]=[];
  async function visit(directory:string):Promise<void>{
    for(const entry of await readdir(directory,{withFileTypes:true})){
      const absolute=join(directory,entry.name);
      assert.equal(entry.isSymbolicLink(),false,`${relative(root,absolute)} generated symlink is not auditable content`);
      if(entry.isDirectory())await visit(absolute);
      else{assert.equal(entry.isFile(),true,`${relative(root,absolute)} generated entry must be a file`);files.push(absolute);}
    }
  }
  await visit(root);
  return files.sort((a,b)=>a<b?-1:a>b?1:0);
}

async function trackedContentSha256(paths:string[]):Promise<string>{
  const registerPath="review/wizards-ip-reference-register.json",chunks:Buffer[]=[Buffer.from("kv-tracked-content-v1\0")];
  const lengthFrame=(value:number)=>{const frame=Buffer.alloc(8);frame.writeBigUInt64BE(BigInt(value));return frame;};
  for(const path of paths){
    const pathBytes=Buffer.from(path,"utf8");let content=await readFile(path);
    if(path===registerPath){
      const canonical=JSON.parse(content.toString("utf8"));canonical.audit.tracked_content_sha256="";
      content=Buffer.from(`${JSON.stringify(canonical,null,2)}\n`);
    }
    chunks.push(lengthFrame(pathBytes.length),pathBytes,lengthFrame(content.length),content);
  }
  return sha256(Buffer.concat(chunks));
}

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
  assert.equal(notice.split(srdAttribution).length-1,1);
  assert.equal(sha256(srdAttribution),"f2e3568c8377f47c48dab84d64d1fc08aed723f0efabcb8a26e91c761cb59171");
  assert.equal(sha256(srdDisclaimer),"f439d59ec753e22ce22321f3a126ebc5641bb713799c74199feecc86f927a282");
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
  validateResolvedAuditPolicy(audit);
  const unknownIdentity=audit.replace("are the same natural person","have an unknown identity relationship");
  assert.throws(()=>validateResolvedAuditPolicy(unknownIdentity));
  const blanketNoncommercial=`${audit}\n${["Everything","in this repository","is licensed under","CC BY-NC-SA 4.0."].join(" ")}\n`;
  assert.throws(()=>validateResolvedAuditPolicy(blanketNoncommercial));

  for (const section of ["Maintained component boundaries", "Complete current-tree inventory", "Intentionally unchanged", "Residual risk and independent review"]) assert.match(audit, new RegExp(section));

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
    assertNoActiveWholeProjectGrant(content,path);
    assertNoPositiveBrandRelationshipClaim(content,path);
    if (path === "docs/licensing-audit.md") continue;
    assert.equal(content.toLowerCase().includes(staleCustomGrant.toLowerCase()), false, path);
    if (content.includes(bsdReservation)) assert.equal(path, "LICENSE-CODE");
  }
  assert.throws(()=>assertNoActiveWholeProjectGrant(["This","repository is licensed under the Open Game","License."].join(" "),"synthetic OGL grant"));
  assert.throws(()=>assertNoActiveWholeProjectGrant(["Everything","in this repository","is licensed under","CC BY-NC-SA 4.0."].join(" "),"synthetic blanket grant"));
  for(const claim of [
    ["This","repository is licensed under","MIT."].join(" "),
    ["The","project is licensed under","CC BY."].join(" "),
    ["Every","file in this","repository is licensed under","MIT."].join(" ")
  ])assert.throws(()=>assertNoActiveWholeProjectGrant(claim,"synthetic whole-project grant"));
  for(const statement of [
    ["This","repository is not licensed under","MIT."].join(" "),
    ["The","project is never licensed under","CC BY."].join(" "),
    ["Not every","file in this","repository is licensed under","MIT."].join(" ")
  ])assert.doesNotThrow(()=>assertNoActiveWholeProjectGrant(statement,"synthetic negative statement"));
  for(const claim of [
    ["Kinetic","Vanguard is affiliated with","Wizards of the Coast."].join(" "),
    ["This","project is endorsed by","Wizards."].join(" "),
    ["This","work is sponsored by","D&D."].join(" "),
    ["This","publication is an official","D&D product."].join(" "),
    ["Wizards","endorses this","project."].join(" "),
    ["Endorsed","by Wizards of the Coast."].join(" "),
    ["Official","D&D product."].join(" "),
    ["**Endorsed","by Wizards of the Coast.**"].join(" "),
    ["__Official","D&D product.__"].join(" ")
  ])assert.throws(()=>assertNoPositiveBrandRelationshipClaim(claim,"synthetic positive relationship"));
  for(const statement of [
    ["Kinetic","Vanguard is not affiliated with or endorsed by","Wizards of the Coast."].join(" "),
    ["This","project is not sponsored by","Wizards."].join(" "),
    ["This","work is not an official","D&D publication."].join(" "),
    ["Use does not imply","endorsement by Wizards."].join(" "),
    ["Not","endorsed by Wizards."].join(" "),
    ["Unofficial","D&D product."].join(" ")
  ])assert.doesNotThrow(()=>assertNoPositiveBrandRelationshipClaim(statement,"synthetic negative relationship"));
});

test("comparator provenance covers every scalar with compact independently classified source metadata", async () => {
  const [comparatorBytes,provenanceBytes,inputsBytes,damageHarness]=await Promise.all([
    readFile("harness/comparators/fighter-subclasses.json","utf8"),
    readFile("harness/provenance/fighter-subclass-comparators.json","utf8"),
    readFile("build/inputs.json","utf8"),
    readFile("harness/damage_harness.py","utf8")
  ]);
  const comparator=JSON.parse(comparatorBytes),provenance=JSON.parse(provenanceBytes);
  validateComparatorProvenance(comparator,provenance,comparatorBytes);
  assert.equal(provenanceBytes,`${JSON.stringify(provenance,null,2)}\n`,`provenance must use deterministic two-space JSON with a terminal LF`);

  const classCounts=Object.fromEntries([...comparatorSourceClassifications].map(classification=>[
    classification,(provenance.leaves as ComparatorLeaf[]).filter(leaf=>leaf.source_classification===classification).length
  ]));
  assert.deepEqual(classCounts,{
    srd_5_2_1_fact:15,
    non_srd_official_fact:13,
    project_authored_benchmark_assumption:20,
    project_authored_tactical_policy:15,
    narrow_nominative_identifier:2
  });
  assert.equal((provenance.leaves as ComparatorLeaf[]).filter(leaf=>leaf.unresolved_counsel).length,15);

  const inputRoles=new Map((JSON.parse(inputsBytes).inputs as Array<{path:string;role:string}>).map(input=>[input.path,input.role]));
  assert.equal(inputRoles.get("harness/provenance/fighter-subclass-comparators.json"),"comparator_provenance");
  assert.equal(damageHarness.includes("fighter-subclass-comparators.json"),false,"legal provenance is not a damage evaluator input");

  const missing=structuredClone(provenance);missing.leaves.pop();
  assert.throws(()=>validateComparatorProvenance(comparator,missing,comparatorBytes));
  const extra=structuredClone(provenance);extra.leaves.push({...extra.leaves[0],field_path:"invented.extra_leaf"});
  assert.throws(()=>validateComparatorProvenance(comparator,extra,comparatorBytes));
  const changedComparator=structuredClone(comparator);changedComparator.damage.battle_master.ability_modifier=4;
  assert.throws(()=>validateComparatorProvenance(changedComparator,provenance,comparatorBytes));
  const mislabeled=structuredClone(provenance);const tactical=mislabeled.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path.includes(".tactical_policy."));
  tactical.source_classification="non_srd_official_fact";tactical.source_id="phb_2024";tactical.accepted_github_audit_record="https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5239280314";
  assert.throws(()=>validateComparatorProvenance(comparator,mislabeled,comparatorBytes));
  const rejectedBasicRulesVariants=[
    ["Basic","Rules"].join(" "),["Basic","Rules"].join("_"),["Basic","Rules"].join("-"),["Basic","Rules"].join(""),
    ["https://www.dndbeyond.com/sources/dnd/","br-2024"].join(""),["sources/dnd/","br-2024"].join("")
  ];
  for(const rejected of rejectedBasicRulesVariants){
    const basicRulesSource=structuredClone(provenance);basicRulesSource.sources.phb_2024.title=`Synthetic ${rejected}`;
    assert.throws(()=>validateComparatorProvenance(comparator,basicRulesSource,comparatorBytes));
    const basicRulesLeaf=structuredClone(provenance);basicRulesLeaf.leaves.find((leaf:ComparatorLeaf)=>leaf.source_classification==="non_srd_official_fact").locator=`${rejected} > p. 1`;
    assert.throws(()=>validateComparatorProvenance(comparator,basicRulesLeaf,comparatorBytes));
  }
  const swapped=structuredClone(provenance),srdLeaf=swapped.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.weapon.count"),benchmarkLeaf=swapped.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.ability_modifier");
  for(const key of ["source_classification","expression_classification","source_id"]){const value=srdLeaf[key];srdLeaf[key]=benchmarkLeaf[key];benchmarkLeaf[key]=value;}
  assert.throws(()=>validateComparatorProvenance(comparator,swapped,comparatorBytes));
  const wrongComparator=structuredClone(provenance);wrongComparator.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.eldritch_knight.dueling_damage_bonus").comparator_id="battle_master";
  assert.throws(()=>validateComparatorProvenance(comparator,wrongComparator,comparatorBytes));
  const undeclaredAudit=structuredClone(provenance);undeclaredAudit.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.eldritch_knight.dueling_damage_bonus").accepted_github_audit_record="https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-9999999999";
  assert.throws(()=>validateComparatorProvenance(comparator,undeclaredAudit,comparatorBytes));
  const injectedAudit=structuredClone(provenance);injectedAudit.sources.github_issue_50_accepted_audit.accepted_records.push(["https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-","9999999999"].join(""));
  assert.throws(()=>validateComparatorProvenance(comparator,injectedAudit,comparatorBytes));
  const sparseSource=structuredClone(provenance);sparseSource.sources.phb_2024={kind:"official_non_srd_source"};
  assert.throws(()=>validateComparatorProvenance(comparator,sparseSource,comparatorBytes));
  for(const [sourceId,record] of [
    ["github_issue_52_accepted_audit","https://github.com/kmart01123/kinetic-vanguard/issues/52#issuecomment-5291985967"],
    ["github_issue_50_accepted_audit","https://github.com/kmart01123/kinetic-vanguard/issues/50#issuecomment-5291987976"]
  ] as const){
    const removedOwnerRecord=structuredClone(provenance);
    removedOwnerRecord.sources[sourceId].accepted_records=removedOwnerRecord.sources[sourceId].accepted_records.filter((candidate:string)=>candidate!==record);
    assert.throws(()=>validateComparatorProvenance(comparator,removedOwnerRecord,comparatorBytes));
  }
  for(const fieldPath of Object.keys(resolvedComparatorLeafContract)){
    const inventedGap=structuredClone(provenance);
    inventedGap.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path===fieldPath).evidence_gap="Synthetic unsupported gap";
    assert.throws(()=>validateComparatorProvenance(comparator,inventedGap,comparatorBytes));
  }
  const mislabeledHew=structuredClone(provenance),mislabeledHewLeaf=mislabeledHew.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.hew_critical_bonus_attack_once_per_round");
  mislabeledHewLeaf.source_classification="non_srd_official_fact";mislabeledHewLeaf.expression_classification="bare_numeric_fact";mislabeledHewLeaf.source_id="phb_2024";mislabeledHewLeaf.unresolved_counsel=true;
  assert.throws(()=>validateComparatorProvenance(comparator,mislabeledHew,comparatorBytes));
  const falselyModeledZeroHp=structuredClone(provenance);falselyModeledZeroHp.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.hew_critical_bonus_attack_once_per_round").rationale="Synthetic policy claims the reduce-to-0-HP trigger is modeled.";
  assert.throws(()=>validateComparatorProvenance(comparator,falselyModeledZeroHp,comparatorBytes));
  const inventedPrintPage=structuredClone(provenance);inventedPrintPage.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.great_weapon_master_attack_action_bonus").locator="2024 PHB p. 999 > Synthetic Great Weapon Master";
  assert.throws(()=>validateComparatorProvenance(comparator,inventedPrintPage,comparatorBytes));
  const missingComparator=structuredClone(provenance);delete missingComparator.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.ability_modifier").comparator_id;
  assert.throws(()=>validateComparatorProvenance(comparator,missingComparator,comparatorBytes));
  const reorderedLeaf=structuredClone(provenance);const reorderedTarget=reorderedLeaf.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.ability_modifier"),reorderedSourceId=reorderedTarget.source_id;delete reorderedTarget.source_id;reorderedTarget.source_id=reorderedSourceId;
  assert.throws(()=>validateComparatorProvenance(comparator,reorderedLeaf,comparatorBytes));
  const wrongTacticalHeading=structuredClone(provenance);wrongTacticalHeading.leaves.find((leaf:ComparatorLeaf)=>leaf.field_path==="damage.battle_master.tactical_policy.objective").locator="harness/comparators/fighter-subclasses.json > damage.battle_master.tactical_policy.objective; harness/README.md > Comparator policy";
  assert.throws(()=>validateComparatorProvenance(comparator,wrongTacticalHeading,comparatorBytes));
  const copiedProse=structuredClone(provenance);copiedProse.leaves[0].rationale=`line one\n${"synthetic prose ".repeat(30)}`;
  assert.throws(()=>validateComparatorProvenance(comparator,copiedProse,comparatorBytes));
});

test("tracked and generated Wizards/SRD references exactly match the classified register", async () => {
  const [registerBytes,notice]=await Promise.all([
    readFile("review/wizards-ip-reference-register.json","utf8"),readFile("NOTICE.md","utf8")
  ]);
  const register=JSON.parse(registerBytes) as any;
  const regenerate=process.env.KV_REGENERATE_REFERENCE_REGISTER==="1";
  assert.deepEqual(Object.keys(register),[
    "format_version","audit","official_sources","classification_definitions","reference_categories","term_dispositions","approved_noncode_assets","entries"
  ]);
  assert.equal(register.format_version,1);
  assert.equal(registerBytes,`${JSON.stringify(register,null,2)}\n`,`register must use deterministic two-space JSON with a terminal LF`);
  const categoryIds=referenceCategoryContract.map(category=>category.id);
  assert.equal(new Set(categoryIds).size,categoryIds.length,"reference category IDs must be unique");
  let dungeonsAndDragonsPatternCount=0;
  for(const category of referenceCategoryContract){
    const patternIds=category.patterns.map(pattern=>pattern.id);
    assert.equal(new Set(patternIds).size,patternIds.length,`${category.id} pattern IDs must be unique`);
    dungeonsAndDragonsPatternCount+=patternIds.filter(id=>id==="dungeons_and_dragons").length;
  }
  assert.equal(dungeonsAndDragonsPatternCount,1);
  assert.deepEqual(Object.keys(register.audit),["audit_date","audited_base_commit","tracked_path_count","tracked_path_sha256","tracked_content_sha256","tracked_content_self_canonicalization","scope","generated_artifact_inventory"]);
  assert.deepEqual(register.official_sources,officialSourceContract);
  assert.deepEqual(register.classification_definitions,classificationDefinitionContract);
  assert.deepEqual(register.reference_categories,referenceCategoryContract);
  assert.deepEqual(register.term_dispositions,termDispositionContract);
  assert.deepEqual(register.approved_noncode_assets,[]);
  assert.ok(registerBytes.endsWith("\n"));

  const trackedPaths=trackedStageZeroPaths();
  assert.equal(trackedPaths.length,102);
  const trackedPathBytes=`${trackedPaths.join("\n")}\n`;
  assert.equal(sha256(trackedPathBytes),"003cdfef582840a3341e3da7c99689f3cd0c197b3bcc7906600747765c6994da");
  assert.equal(register.audit.audit_date,"2026-08-14");
  assert.equal(register.audit.audited_base_commit,"e5d81ab1271b305bee5b92bca22bb9acce0275e9");
  assert.equal(register.audit.tracked_path_count,trackedPaths.length);
  assert.equal(register.audit.tracked_path_sha256,sha256(trackedPathBytes));
  assert.match(register.audit.tracked_content_sha256,/^[0-9a-f]{64}$/);
  assert.equal(register.audit.tracked_content_self_canonicalization,"SHA-256 frames every tracked candidate path and bytes after blanking only audit.tracked_content_sha256 in this register.");
  if(!regenerate)assert.equal(register.audit.tracked_content_sha256,await trackedContentSha256(trackedPaths));
  assertCompactStrings(register.audit,"audit");
  assertCompactStrings(register.official_sources,"official_sources");
  assertCompactStrings(register.term_dispositions,"term_dispositions");

  const trackedSurfaces=await Promise.all(trackedPaths.map(async path=>{
    const bytes=await readFile(path),content=decodeApprovedAsset(path,bytes);
    return {surface_id:`tracked:${path}`,path,content,surface:"public" as const};
  }));

  const temporary=await mkdtemp(join(tmpdir(),"kv-reference-register-"));
  const previousApproval=process.env.KV_RELEASE_APPROVED;
  const generatedSurfaces:Array<{surface_id:string;path:string;content:string;surface:"generated"}>=[];
  try{
    const prototypeRoot=join(temporary,"prototype"),releaseRoot=join(temporary,"release");
    const prototype=await executeBuild("prototype",prototypeRoot);
    process.env.KV_RELEASE_APPROVED="1";
    const release=await executeBuild("release",releaseRoot);
    for(const [profile,root,result] of [["prototype",prototypeRoot,prototype],["release",releaseRoot,release]] as const){
      const expectedHtml=profile==="prototype"?"KineticVanguard.prototype.html":"KineticVanguard.html";
      assert.equal(relative(root,result.htmlPath),expectedHtml);
      assert.equal(relative(root,result.manifestPath),"build-manifest.json");
      for(const absolute of await recursiveFiles(root)){
        const path=relative(root,absolute).split("\\").join("/"),bytes=await readFile(absolute);
        const content=decodeApprovedAsset(`generated:${profile}/${path}`,bytes,path===expectedHtml);
        generatedSurfaces.push({surface_id:`generated:${profile}/${path}`,path,content,surface:"generated"});
      }
    }
  }finally{
    if(previousApproval===undefined)delete process.env.KV_RELEASE_APPROVED;else process.env.KV_RELEASE_APPROVED=previousApproval;
    await rm(temporary,{recursive:true,force:true});
  }

  const generatedInventory=generatedSurfaces.map(surface=>surface.surface_id).sort();
  assert.deepEqual(register.audit.generated_artifact_inventory,generatedInventory);
  for(const surface of generatedSurfaces.filter(item=>item.path.endsWith(".html"))){
    assert.equal(surface.content.includes(srdAttribution),true,`${surface.surface_id} exact SRD attribution`);
    assert.match(surface.content,new RegExp(escaped(srdDisclaimer)));
    assert.match(surface.content,new RegExp(srdModification));
    assert.match(surface.content,/does not imply endorsement/i);
    assert.match(surface.content,/blob\/main\/NOTICE\.md/);
    assert.match(surface.content,/blob\/main\/LICENSE\.md/);
  }
  assert.match(notice,/not affiliated with or endorsed by Wizards of the Coast/i,"adjacent notice carries the full relationship boundary");

  let derived=deriveReferenceEntries([...trackedSurfaces,...generatedSurfaces]);
  if(regenerate){
    const registerPath="review/wizards-ip-reference-register.json",registerSurface=trackedSurfaces.find(surface=>surface.path===registerPath);
    assert.ok(registerSurface);let stable=false;
    for(let iteration=0;iteration<20;iteration+=1){
      register.audit.tracked_path_count=trackedPaths.length;
      register.audit.tracked_path_sha256=sha256(trackedPathBytes);
      register.audit.tracked_content_sha256="";
      register.audit.generated_artifact_inventory=generatedInventory;
      register.entries=derived.map(entry=>({...entry,...expectedRegisterMetadata(entry)}));
      await writeFile(registerPath,`${JSON.stringify(register,null,2)}\n`);
      registerSurface.content=decodeApprovedAsset(registerPath,await readFile(registerPath));
      const next=deriveReferenceEntries([...trackedSurfaces,...generatedSurfaces]);
      if(JSON.stringify(next)===JSON.stringify(derived)){stable=true;break;}
      derived=next;
    }
    assert.equal(stable,true,"reference-register self-scan must reach a fixed point");
    register.audit.tracked_content_sha256=await trackedContentSha256(trackedPaths);
    await writeFile(registerPath,`${JSON.stringify(register,null,2)}\n`);
    return;
  }
  const registered=(register.entries as any[]).map(entry=>({
    surface_id:entry.surface_id,path:entry.path,category_id:entry.category_id,matched_terms:entry.matched_terms,
    expected_hit_count:entry.expected_hit_count,surface:entry.surface
  }));
  assert.deepEqual(registered,derived,"register must have no missing or stale path/category/count entry");

  const classifications=new Set(["srd_5_2_1_licensed_use","original_project_content","narrow_nominative_reference","independently_expressed_factual_mechanic","historical_reference_in_current_documentation","uncertain_counsel_review","remove_or_rename"]);
  const expectedEntryKeys=["surface_id","path","category_id","matched_terms","expected_hit_count","surface","classification","rationale","required_notice_or_locator","mechanically_necessary","counsel_review"];
  for(const entry of register.entries as any[]){
    assert.deepEqual(Object.keys(entry),expectedEntryKeys,`${entry.surface_id} entry schema and order`);
    assert.ok(classifications.has(entry.classification),`${entry.surface_id} classification`);
    assert.ok(referenceCategoryContract.some(category=>category.id===entry.category_id),`${entry.surface_id} category`);
    assert.ok(entry.required_notice_or_locator.length>0,`${entry.surface_id} notice or locator`);
    assert.equal(typeof entry.mechanically_necessary,"boolean");assert.equal(typeof entry.counsel_review,"boolean");
    assertCompactStrings(entry,`entries.${entry.surface_id}.${entry.category_id}`);
    assert.deepEqual({classification:entry.classification,rationale:entry.rationale,required_notice_or_locator:entry.required_notice_or_locator,mechanically_necessary:entry.mechanically_necessary,counsel_review:entry.counsel_review},expectedRegisterMetadata(entry),`${entry.surface_id} ${entry.category_id} semantic metadata`);
  }
  assert.equal((register.entries as any[]).some(entry=>entry.classification==="remove_or_rename"),false);

  const missing=registered.slice(1);assert.throws(()=>assert.deepEqual(missing,derived));
  const synthetic=deriveReferenceEntries([...trackedSurfaces,...generatedSurfaces,{surface_id:"tracked:synthetic-extra.md",path:"synthetic-extra.md",content:"Battle Master",surface:"public"}]);
  assert.throws(()=>assert.deepEqual(registered,synthetic));
  const generatedExtra=deriveReferenceEntries([...trackedSurfaces,...generatedSurfaces,{surface_id:"generated:prototype/unregistered-extra.json",path:"unregistered-extra.json",content:"Battle Master",surface:"generated"}]);
  assert.throws(()=>assert.deepEqual(registered,generatedExtra));
  const wrongClassification=structuredClone((register.entries as any[]).find(entry=>entry.surface_id==="generated:prototype/build-manifest.json"&&entry.category_id==="srd_reference"));
  wrongClassification.classification="srd_5_2_1_licensed_use";
  assert.throws(()=>assert.deepEqual({classification:wrongClassification.classification,rationale:wrongClassification.rationale,required_notice_or_locator:wrongClassification.required_notice_or_locator,mechanically_necessary:wrongClassification.mechanically_necessary,counsel_review:wrongClassification.counsel_review},expectedRegisterMetadata(wrongClassification)));

  const boundedOmittedTerms=[
    ["Deck","of Many Things"].join(" "),["Orb","of Dragonkind"].join(" "),["Artific","er"].join(""),["Aasim","ar"].join(""),
    ["Behold","er"].join(""),["Stra","hd"].join(""),["Orc","us"].join(""),["Tia","mat"].join(""),["Forgotten","Realms"].join(" ")
  ];
  for(const content of boundedOmittedTerms){
    const hits=deriveReferenceEntries([{surface_id:"tracked:synthetic.md",path:"synthetic.md",content,surface:"public"}]);
    assert.ok(hits.some(entry=>entry.category_id==="bounded_omitted_name_reference"),`${content} bounded omitted-name detection`);
  }
  for(const content of [["B","M"].join(""),["E","K"].join("")]){
    const hits=deriveReferenceEntries([{surface_id:"tracked:synthetic.md",path:"synthetic.md",content,surface:"public"}]);
    assert.ok(hits.some(entry=>entry.category_id==="non_srd_comparator_identifier"),`${content} comparator initialism detection`);
  }
  for(const content of [["Mysterious","Deck"].join(" "),["Dragon","Orb"].join(" ")]){
    const hits=deriveReferenceEntries([{surface_id:"tracked:synthetic.md",path:"synthetic.md",content,surface:"public"}]);
    assert.ok(hits.some(entry=>entry.category_id==="srd_replacement_name_reference"),`${content} SRD replacement-name detection`);
  }
  const featureTerms=[["Great","Weapon","Master"].join(" "),["Heavy","Weapon","Mastery"].join(" "),["H","ew"].join(""),["Duel","ing"].join(""),["Relent","less"].join(""),["Combat","Superiority"].join(" "),["Superiority","Die"].join(" "),["War","Magic"].join(" "),["Precision","Attack"].join(" "),["G","WM"].join("")];
  for(const content of featureTerms){
    const hits=deriveReferenceEntries([{surface_id:"tracked:synthetic.md",path:"synthetic.md",content,surface:"public"}]);
    assert.ok(hits.some(entry=>entry.category_id==="non_srd_feat_feature_reference"),`${content} comparator term detection`);
  }
  for(const content of [
    ["Basic","Rules"].join(" "),["Basic","Rules"].join("_"),["Basic","Rules"].join("-"),["Basic","Rules"].join(""),
    ["https://www.dndbeyond.com/sources/dnd/","br-2024"].join(""),["sources/dnd/","br-2024"].join("")
  ]){
    const hits=deriveReferenceEntries([{surface_id:"tracked:synthetic.md",path:"synthetic.md",content,surface:"public"}]);
    assert.ok(hits.some(entry=>entry.category_id==="basic_rules_reference"),`${content} rejected Basic Rules detection`);
  }

  assert.throws(()=>decodeApprovedAsset("review/logo.bin",Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a])));
  assert.throws(()=>decodeApprovedAsset("review/source.txt",Buffer.from("%PDF-synthetic")));
  assert.throws(()=>decodeApprovedAsset("review/private-source-capture.json",Buffer.from("{\"synthetic\":true}")));
  assert.throws(()=>decodeApprovedAsset("review/logo.svg.txt",Buffer.from(["<?xml version=\"1.0\"?>","<","svg></","svg>"].join(""))));
  assert.throws(()=>decodeApprovedAsset("review/padded.html.txt",Buffer.from([" ".repeat(5000),"<","html><body></body></","html>"].join(""))));
  assert.throws(()=>decodeApprovedAsset("review/comment-padded.html.txt",Buffer.from(["<!--","x".repeat(5000),"-->","<","html><body></body></","html>"].join(""))));
  assert.throws(()=>decodeApprovedAsset("review/padded.svg.txt",Buffer.from([" ".repeat(5000),"<","svg></","svg>"].join(""))));
  assert.throws(()=>decodeApprovedAsset("review/screenshot.bin",Buffer.from([0x42,0x4d,0x01,0x02])));
  assert.throws(()=>decodeApprovedAsset("review/video.bin",Buffer.from([0x1a,0x45,0xdf,0xa3,0x01])));
  assert.throws(()=>decodeApprovedAsset("review/invalid-utf8.txt",Buffer.from([0xc3,0x28])));
  assert.throws(()=>decodeApprovedAsset("review/nul.txt",Buffer.from([0x61,0x00,0x62])));
  assert.throws(()=>decodeApprovedAsset("review/pointer.txt",Buffer.from(["version https://git-lfs.github.com/spec/","v1\n","oid sha256:synthetic\nsize 1\n"].join(""))));
  assert.throws(()=>decodeApprovedAsset("review/embedded.txt",Buffer.from([["data","image/png;base64,AA=="].join(":")," synthetic"].join(""))));
  assert.throws(()=>decodeApprovedAsset(["review/.auth/","storage","State.json"].join(""),Buffer.from("{}")));
  assert.throws(()=>decodeApprovedAsset(["review/","auth","-state.json"].join(""),Buffer.from("{}")));
  const playwrightState=JSON.stringify({[["cook","ies"].join("")]:[],[["orig","ins"].join("")]:[]});
  assert.throws(()=>decodeApprovedAsset("review/synthetic-state.txt",Buffer.from(playwrightState)));
  const cookiesOnly=JSON.stringify({[["cook","ies"].join("")]:[{name:"sid",value:"synthetic",domain:"example.invalid",path:"/"}]});
  assert.throws(()=>decodeApprovedAsset("review/state.json",Buffer.from(cookiesOnly)));
  for(const key of [["orig","ins"].join(""),["local","Storage"].join("")]){
    assert.throws(()=>decodeApprovedAsset("review/state.json",Buffer.from(JSON.stringify({[key]:[]}))));
  }
  const sessionState=JSON.stringify({[["session","Storage"].join("")]:{synthetic:"secret"}});
  assert.throws(()=>decodeApprovedAsset("review/synthetic-session.txt",Buffer.from(sessionState)));
});

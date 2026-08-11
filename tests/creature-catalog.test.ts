import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import {canonicalJson,sha256} from "../src/canonical.js";
import {loadCreatureCatalogBundle,validateCreatureCatalog,validateCreatureCatalogProvenance,validateCreatureRosters} from "../src/creature-catalog.js";

type Fixture={catalog:any;catalogBytes:Buffer;rosters:any;rosterBytes:Buffer;provenance:any};

async function fixture():Promise<Fixture>{
  const [catalogBytes,rosterBytes,provenanceBytes]=await Promise.all([
    readFile("harness/data/srd_creatures.json"),
    readFile("harness/data/srd_creature_rosters.json"),
    readFile("harness/provenance/srd-creatures.json")
  ]);
  return {catalog:JSON.parse(catalogBytes.toString("utf8")),catalogBytes,rosters:JSON.parse(rosterBytes.toString("utf8")),rosterBytes,provenance:JSON.parse(provenanceBytes.toString("utf8"))};
}

function sealProfile(profile:any):void{
  delete profile.profile_sha256;
  profile.profile_sha256=sha256(canonicalJson(profile));
}

test("lightweight creature-catalog loader binds the canonical source, roster profiles, and manifest digests",async()=>{
  const bundle=await loadCreatureCatalogBundle();
  assert.equal(bundle.catalog.creatures.length,330);
  assert.deepEqual(bundle.rosters.profiles.map(profile=>[profile.profile_id,(profile.entries as any[]).length]),[
    ["srd521_headline_source_diversity_v1",47],
    ["srd521_eligible_census_v1",93]
  ]);
  assert.equal(bundle.provenance.catalog.sha256,bundle.digests.catalogSha256);
  assert.equal(bundle.provenance.rosters.sha256,bundle.digests.rostersSha256);
  assert.match(bundle.digests.provenanceSha256,/^[0-9a-f]{64}$/);
});

test("catalog shape rejects contract drift, noncanonical ID order, and broken source order",async()=>{
  const {catalog}=await fixture();
  assert.doesNotThrow(()=>validateCreatureCatalog(catalog));
  const reject=(mutate:(value:any)=>void,pattern:RegExp)=>{const value=structuredClone(catalog);mutate(value);assert.throws(()=>validateCreatureCatalog(value),pattern);};
  reject(value=>{value.contract.version="1.0.1";},/contract is unsupported/);
  reject(value=>{[value.creatures[0],value.creatures[1]]=[value.creatures[1],value.creatures[0]];},/strictly codepoint-sorted/);
  reject(value=>{value.creatures[1].source.stat_block_order=value.creatures[0].source.stat_block_order;value.creatures[1].source.stat_block_anchor=`p${value.creatures[1].source.page}-o001`;},/source orders/);
  reject(value=>{value.creatures[0].scenario_state={position:[0,0]};},/keys are invalid/);
});

test("rosters reject catalog-binding, profile-identity, digest, order, and accounting drift without reevaluating selection",async()=>{
  const {catalog,catalogBytes,rosters}=await fixture(),validatedCatalog=validateCreatureCatalog(catalog);
  assert.doesNotThrow(()=>validateCreatureRosters(rosters,validatedCatalog,catalogBytes));
  const reject=(mutate:(value:any)=>void,pattern:RegExp)=>{const value=structuredClone(rosters);mutate(value);assert.throws(()=>validateCreatureRosters(value,validatedCatalog,catalogBytes),pattern);};
  reject(value=>{value.catalog.sha256="0".repeat(64);},/catalog SHA-256/);
  reject(value=>{value.profiles[0].profile_sha256="0".repeat(64);},/profile payload/);
  reject(value=>{value.profiles[0].profile_version="2.0.0";sealProfile(value.profiles[0]);},/identity is unsupported/);
  reject(value=>{[value.profiles[0].entries[0],value.profiles[0].entries[1]]=[value.profiles[0].entries[1],value.profiles[0].entries[0]];value.profiles[0].entries.forEach((entry:any,index:number)=>{entry.profile_order=index+1;});sealProfile(value.profiles[0]);},/source ordering/);
  reject(value=>{[value.accounting[0],value.accounting[1]]=[value.accounting[1],value.accounting[0]];},/exact catalog source order/);
  reject(value=>{value.accounting.pop();},/one row per catalog creature/);
});

test("provenance manifest rejects source identity and either data-file digest drift",async()=>{
  const {catalog,catalogBytes,rosters,rosterBytes,provenance}=await fixture(),validatedCatalog=validateCreatureCatalog(catalog),validatedRosters=validateCreatureRosters(rosters,validateCreatureCatalog(catalog),catalogBytes);
  assert.doesNotThrow(()=>validateCreatureCatalogProvenance(provenance,validatedCatalog,validatedRosters,catalogBytes,rosterBytes));
  const reject=(mutate:(value:any)=>void,pattern:RegExp)=>{const value=structuredClone(provenance);mutate(value);assert.throws(()=>validateCreatureCatalogProvenance(value,validatedCatalog,validatedRosters,catalogBytes,rosterBytes),pattern);};
  reject(value=>{value.source.official_pdf_sha256="0".repeat(64);},/pinned official SRD source/);
  reject(value=>{value.catalog.sha256="0".repeat(64);},/catalog SHA-256/);
  reject(value=>{value.rosters.sha256="0".repeat(64);},/roster SHA-256/);
  reject(value=>{value.catalog.last_source_identity="p343-o234";},/source identity bounds/);
  reject(value=>{value.extraction.trait_audit_sha256="not-a-digest";},/lowercase SHA-256/);
});

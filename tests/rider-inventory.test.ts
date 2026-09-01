import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";

const inventoryRow=/^\| `([a-z0-9_]+)` \| [^\n]+ \| `([a-z_]+)` \| [^\n]+$/gm;

test("rider-model inventory covers every concrete Subclass Feature Reference ability",async()=>{
  const [{authority},inventory]=await Promise.all([loadAuthority(),readFile("docs/rider-model-inventory.md","utf8")]);
  const reference=authority.entities.find(entity=>entity.id==="subclass_feature_reference");assert.ok(reference);
  const table=reference.content.find(block=>block.type==="table"&&block.row_references!==undefined);assert.ok(table&&table.type==="table"&&table.row_references);
  const expected=table.row_references.flatMap(row=>"entity_id" in row?[row.entity_id]:[]).sort();
  const rows=[...inventory.matchAll(inventoryRow)].map(match=>({entityId:match[1]!,disposition:match[2]!}));
  assert.equal(new Set(rows.map(row=>row.entityId)).size,rows.length);
  assert.deepEqual(rows.map(row=>row.entityId).sort(),expected);
  const allowed=new Set(["standard_rider","area_rider","standalone_activation","standalone_area","passive","mixed_passive_standalone"]);
  assert.ok(rows.every(row=>allowed.has(row.disposition)));
  assert.equal(rows.filter(row=>row.disposition==="standard_rider").length,12);
  assert.deepEqual(rows.filter(row=>row.disposition==="area_rider").map(row=>row.entityId).sort(),["electron_burst","explosion_implosion"]);
  assert.deepEqual(rows.filter(row=>row.disposition==="standalone_area").map(row=>row.entityId).sort(),["advanced_gravitic_press","advanced_improved_phase_step","advanced_phase_step","ball_lightning","frozen_ground","mass_levitation"]);
  assert.match(inventory,new RegExp(`snapshots canonical rules \\*\\*v${authority.rules_version.replaceAll(".","\\.")}\\*\\*`));
  assert.match(inventory,/KineticVanguard\.yaml` remains the sole rules authority/);
});

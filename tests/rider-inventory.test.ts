import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";

const inventoryRows=(source:string)=>source.split("\n").filter(line=>/^\| `[a-z0-9_]+` \|/.test(line)).map(line=>{const columns=line.split("|").slice(1,-1).map(value=>value.trim());return{entityId:columns[0]!.slice(1,-1),delivery:columns[3]!,topology:columns[4]!};});

test("rider-model inventory covers every concrete Subclass Feature Reference ability",async()=>{
  const [{authority},inventory]=await Promise.all([loadAuthority(),readFile("docs/rider-model-inventory.md","utf8")]);
  const reference=authority.entities.find(entity=>entity.id==="subclass_feature_reference");assert.ok(reference);
  const table=reference.content.find(block=>block.type==="table"&&block.row_references!==undefined);assert.ok(table&&table.type==="table"&&table.row_references);
  const expected=table.row_references.flatMap(row=>"entity_id" in row?[row.entity_id]:[]).sort();
  const rows=inventoryRows(inventory);
  assert.equal(new Set(rows.map(row=>row.entityId)).size,rows.length);
  assert.deepEqual(rows.map(row=>row.entityId).sort(),expected);
  assert.equal(rows.filter(row=>row.delivery==="`rider`").length,14);
  assert.deepEqual(rows.filter(row=>row.delivery==="`rider`"&&row.topology==="`area`").map(row=>row.entityId).sort(),["electron_burst","explosion_implosion"]);
  assert.deepEqual(rows.filter(row=>row.delivery==="`standalone`"&&row.topology==="`discrete_multi`").map(row=>row.entityId).sort(),["arctic_tempest","forked_lightning","mass_levitation"]);
  assert.ok(rows.every(row=>/^`(?:rider|standalone|passive|mixed)`/.test(row.delivery)));
  assert.ok(rows.every(row=>/^`(?:single|discrete_multi|area|self|none|mixed)`/.test(row.topology)));
  assert.match(inventory,new RegExp(`inventory of canonical rules \\*\\*v${authority.rules_version.replaceAll(".","\\.")}\\*\\*`));
  assert.match(inventory,/KineticVanguard\.yaml` remains the sole rules authority/);
});

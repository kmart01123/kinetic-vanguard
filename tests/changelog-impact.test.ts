import assert from "node:assert/strict";
import test from "node:test";
import {
  parseChangelogDeclaration,
  runChangelogImpactCheck,
  validateChangelogImpact,
} from "../src/changelog-impact.js";

test("updated passes when CHANGELOG.md changed", () => {
  assert.deepEqual(validateChangelogImpact("Changelog: updated", ["CHANGELOG.md"]), { kind: "updated" });
});

test("not required passes with a meaningful reason and no changelog change", () => {
  assert.deepEqual(validateChangelogImpact("Changelog: not required — internal test cleanup", []), {
    kind: "not-required",
    reason: "internal test cleanup",
  });
});

test("push events skip cleanly", () => {
  assert.equal(runChangelogImpactCheck("push"), "skipped");
});

test("missing declarations fail", () => {
  assert.throws(() => parseChangelogDeclaration("No declaration here."), /exactly one.*found 0/iu);
});

test("TODO declarations fail", () => {
  assert.throws(() => parseChangelogDeclaration("Changelog: TODO"), /Malformed/iu);
});

test("not required without a reason fails", () => {
  assert.throws(() => parseChangelogDeclaration("Changelog: not required"), /Malformed/iu);
});

test("duplicate declarations fail", () => {
  assert.throws(
    () => parseChangelogDeclaration("Changelog: updated\nChangelog: updated"),
    /exactly one.*found 2/iu,
  );
});

test("contradictory declarations fail", () => {
  assert.throws(
    () => parseChangelogDeclaration("Changelog: updated\nChangelog: not required — docs only"),
    /exactly one.*found 2/iu,
  );
});

test("updated fails when CHANGELOG.md did not change", () => {
  assert.throws(
    () => validateChangelogImpact("Changelog: updated", ["src/changelog-impact.ts"]),
    /requires CHANGELOG\.md/iu,
  );
});

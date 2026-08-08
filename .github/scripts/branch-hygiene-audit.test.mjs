import assert from "node:assert/strict";
import test from "node:test";

import { findStaleBranches, isPermanentBranch } from "./branch-hygiene-audit.mjs";

test("exempts permanent, open-PR, and young branches while flagging stale stragglers", () => {
  const branches = [
    { name: "main", sha: "1".repeat(40), committedAt: "2025-01-01T00:00:00.000Z" },
    { name: "release/14.1.0", sha: "2".repeat(40), committedAt: "2025-01-01T00:00:00.000Z" },
    { name: "feat/open-work", sha: "3".repeat(40), committedAt: "2025-01-01T00:00:00.000Z" },
    { name: "feat/young-work", sha: "4".repeat(40), committedAt: "2026-08-01T00:00:00.000Z" },
    { name: "manual/stale-work", sha: "5".repeat(40), committedAt: "2026-07-01T00:00:00.000Z" },
  ];

  const staleBranches = findStaleBranches({
    branches,
    openPullHeads: new Set(["feat/open-work"]),
    now: new Date("2026-08-08T00:00:00.000Z"),
  });

  assert.deepEqual(staleBranches.map(({ name }) => name), ["manual/stale-work"]);
});

test("recognizes only main and release namespace branches as permanent", () => {
  assert.equal(isPermanentBranch("main"), true);
  assert.equal(isPermanentBranch("release/14.1.0"), true);
  assert.equal(isPermanentBranch("release-prep/14.2.0"), false);
  assert.equal(isPermanentBranch("feat/example"), false);
});

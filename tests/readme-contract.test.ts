import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { loadAuthority } from "../src/load.js";

const parseVersion = (value: string): readonly number[] => value.split(".").map(Number);
const compareVersions = (left: string, right: string): number => {
  const a = parseVersion(left);
  const b = parseVersion(right);
  for (let index = 0; index < 3; index += 1) {
    const difference = (a[index] ?? 0) - (b[index] ?? 0);
    if (difference !== 0) return difference;
  }
  return 0;
};

test("README and release process stay synchronized with canonical development status", async () => {
  const [{ authority }, readme, checklist, pullRequestTemplate] = await Promise.all([
    loadAuthority(),
    readFile("README.md", "utf8"),
    readFile("RELEASE_CHECKLIST.md", "utf8"),
    readFile(".github/pull_request_template.md", "utf8")
  ]);

  const published = readme.match(/^- Current published release: \*\*v(\d+\.\d+\.\d+)\*\*$/m);
  assert.ok(published, "README declares the current published release");
  assert.ok(compareVersions(published[1]!, authority.rules_version) <= 0, "published release cannot be newer than canonical authority");

  const development = readme.match(/^- Current development line: \*\*(v\d+\.\d+\.\d+|None)\*\*$/m);
  assert.ok(development, "README declares the current development line");
  if (development[1] !== "None") {
    assert.equal(development[1], `v${authority.rules_version}`);
    assert.match(readme, new RegExp(`^- Development branch: \\`${authority.rules_version.replaceAll(".", "\\.")}\\`$`, "m"));
    assert.match(readme, /^- Draft pull request: /m);
  }

  for (const heading of ["Release status", "Publication interface", "Commands", "Architecture", "Licensing", "Development and release discipline"]) {
    assert.match(readme, new RegExp(`^## ${heading}$`, "m"));
  }

  assert.match(readme, /Start Here/);
  assert.match(readme, /Category and Topic browsing/);
  assert.match(readme, /Name selector/);
  assert.match(readme, /global classification filters/);
  assert.match(readme, /Subclass Feature Reference/);
  assert.match(readme, /kinetic-vanguard-v<rules_version>/);
  assert.doesNotMatch(readme, /kinetic-vanguard-v\d+\.\d+\.\d+/);
  assert.doesNotMatch(readme, /Forked Lightning needs explicit failed-save wording/);
  assert.doesNotMatch(readme, /Kinetic Vanguard \*\*v13\.0\.1\*\* is the current/);

  for (const heading of ["Start of a development line", "Before marking a release pull request ready", "Publication", "Required release assets"]) {
    assert.match(checklist, new RegExp(`^## ${heading}$`, "m"));
  }
  assert.match(checklist, /README\.md/);
  assert.match(checklist, /KineticVanguard\.yaml/);
  assert.match(checklist, /CHANGELOG\.md/);
  assert.match(checklist, /Main branch gate/);
  assert.match(checklist, /Protect main/);
  assert.match(checklist, /LICENSE\.md/);
  assert.match(checklist, /NOTICE\.md/);

  assert.match(pullRequestTemplate, /RELEASE_CHECKLIST\.md/);
  assert.match(pullRequestTemplate, /README\.md/);
  assert.match(pullRequestTemplate, /Main branch gate/);
});

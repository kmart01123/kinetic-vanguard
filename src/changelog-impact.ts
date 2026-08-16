import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

export type ChangelogDeclaration =
  | { kind: "updated" }
  | { kind: "not-required"; reason: string };

const placeholderReason = /^(?:todo|tbd|n\/?a|none)$/iu;

export function parseChangelogDeclaration(body: string): ChangelogDeclaration {
  const declarations = body
    .split(/\r?\n/u)
    .map(line => line.trim())
    .filter(line => line.startsWith("Changelog:"));

  if (declarations.length !== 1) {
    throw new Error(`Expected exactly one Changelog declaration; found ${declarations.length}.`);
  }

  const declaration = declarations[0]!;
  if (declaration === "Changelog: updated") return { kind: "updated" };

  const notRequired = /^Changelog: not required — (.+)$/u.exec(declaration);
  if (notRequired) {
    const reason = notRequired[1]!.trim();
    if (/[\p{L}\p{N}]/u.test(reason) && !placeholderReason.test(reason)) {
      return { kind: "not-required", reason };
    }
  }

  throw new Error(
    "Malformed Changelog declaration; use updated or not required with an em dash and a meaningful reason.",
  );
}

export function requiresChangelogChange(declaration: ChangelogDeclaration): boolean {
  return declaration.kind === "updated";
}

export function validateChangelogImpact(body: string, changedPaths: readonly string[]): ChangelogDeclaration {
  const declaration = parseChangelogDeclaration(body);
  if (requiresChangelogChange(declaration) && !changedPaths.includes("CHANGELOG.md")) {
    throw new Error("The updated declaration requires CHANGELOG.md in the base-to-head diff.");
  }
  return declaration;
}

type PullRequestEvent = {
  pull_request?: {
    body?: string | null;
    base?: { sha?: string };
    head?: { sha?: string };
  };
};

function requireCommit(sha: string, label: "base" | "head"): void {
  const result = spawnSync("git", ["cat-file", "-e", `${sha}^{commit}`], { stdio: "ignore" });
  if (result.status !== 0) throw new Error(`Pull request ${label} commit is unavailable locally: ${sha}`);
}

function changedPaths(baseSha: string, headSha: string): string[] {
  const result = spawnSync("git", ["diff", "--name-only", "-z", baseSha, headSha, "--"], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(`Could not compute the pull request base-to-head diff: ${result.stderr.trim()}`);
  }
  return result.stdout.split("\0").filter(Boolean);
}

export function runChangelogImpactCheck(eventName: string, eventPath?: string): "checked" | "skipped" {
  if (eventName !== "pull_request") {
    console.log(`Skipping changelog declaration check for ${eventName || "unknown"} event.`);
    return "skipped";
  }
  if (!eventPath) throw new Error("GITHUB_EVENT_PATH is required for pull_request events.");

  const event = JSON.parse(readFileSync(eventPath, "utf8")) as PullRequestEvent;
  const pullRequest = event.pull_request;
  const baseSha = pullRequest?.base?.sha;
  const headSha = pullRequest?.head?.sha;
  if (!baseSha || !headSha) throw new Error("Pull request base and head SHAs are required.");

  requireCommit(baseSha, "base");
  requireCommit(headSha, "head");
  const declaration = validateChangelogImpact(pullRequest.body ?? "", changedPaths(baseSha, headSha));
  console.log(`Validated ${declaration.kind} changelog impact for ${baseSha}..${headSha}.`);
  return "checked";
}

const entryPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (import.meta.url === entryPath) {
  try {
    runChangelogImpactCheck(process.env.GITHUB_EVENT_NAME ?? "", process.env.GITHUB_EVENT_PATH);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

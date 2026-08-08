import { appendFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

export const DEFAULT_GRACE_DAYS = 14;

export function isPermanentBranch(name) {
  return name === "main" || name.startsWith("release/");
}

export function findStaleBranches({
  branches,
  openPullHeads,
  now = new Date(),
  graceDays = DEFAULT_GRACE_DAYS,
}) {
  const cutoff = now.getTime() - graceDays * 24 * 60 * 60 * 1000;

  return branches
    .filter(({ name }) => !isPermanentBranch(name))
    .filter(({ name }) => !openPullHeads.has(name))
    .map((branch) => {
      const committedAt = new Date(branch.committedAt);
      if (Number.isNaN(committedAt.getTime())) {
        throw new Error(`Invalid head commit date for ${branch.name}`);
      }

      return {
        ...branch,
        committedAt: committedAt.toISOString(),
        ageDays: Math.floor((now.getTime() - committedAt.getTime()) / (24 * 60 * 60 * 1000)),
      };
    })
    .filter(({ committedAt }) => new Date(committedAt).getTime() < cutoff)
    .sort((left, right) => left.name.localeCompare(right.name));
}

function repositoryParts(repository) {
  const [owner, repo, ...rest] = repository.split("/");
  if (!owner || !repo || rest.length > 0) {
    throw new Error(`Invalid GITHUB_REPOSITORY value: ${repository}`);
  }
  return { owner, repo };
}

async function githubJson(path, token) {
  const response = await fetch(`https://api.github.com${path}`, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "User-Agent": "kinetic-vanguard-branch-hygiene-audit",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });

  if (!response.ok) {
    throw new Error(`GitHub API ${response.status} for ${path}: ${await response.text()}`);
  }

  return response.json();
}

async function githubPages(path, token) {
  const results = [];

  for (let page = 1; ; page += 1) {
    const separator = path.includes("?") ? "&" : "?";
    const items = await githubJson(`${path}${separator}per_page=100&page=${page}`, token);
    if (!Array.isArray(items)) {
      throw new Error(`Expected an array from GitHub API path: ${path}`);
    }
    results.push(...items);
    if (items.length < 100) {
      return results;
    }
  }
}

async function writeSummary(summaryPath, staleBranches, graceDays) {
  const lines = ["## Branch hygiene audit", ""];

  if (staleBranches.length === 0) {
    lines.push(`No stale branch candidates were found after the ${graceDays}-day grace period.`);
  } else {
    lines.push(
      `Found ${staleBranches.length} stale branch candidate${staleBranches.length === 1 ? "" : "s"}.`,
      "",
      "| Branch | Head commit | Head date (UTC) | Age (days) |",
      "| --- | --- | --- | ---: |",
      ...staleBranches.map(
        ({ name, sha, committedAt, ageDays }) =>
          `| <code>${name}</code> | <code>${sha.slice(0, 12)}</code> | ${committedAt} | ${ageDays} |`,
      ),
      "",
      "These branches were not deleted. Confirm they are not associated with open or unmerged work before removing them manually.",
    );
  }

  const summary = `${lines.join("\n")}\n`;
  if (summaryPath) {
    await appendFile(summaryPath, summary);
  }
  process.stdout.write(summary);
}

async function main() {
  const token = process.env.GITHUB_TOKEN;
  const repository = process.env.GITHUB_REPOSITORY;
  if (!token || !repository) {
    throw new Error("GITHUB_TOKEN and GITHUB_REPOSITORY are required");
  }

  const { owner, repo } = repositoryParts(repository);
  const repoPath = `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
  const [branches, openPulls] = await Promise.all([
    githubPages(`${repoPath}/branches`, token),
    githubPages(`${repoPath}/pulls?state=open`, token),
  ]);

  const openPullHeads = new Set(
    openPulls
      .filter(({ head }) => head.repo?.full_name === repository)
      .map(({ head }) => head.ref),
  );
  const nonExemptBranches = branches.filter(
    ({ name }) => !isPermanentBranch(name) && !openPullHeads.has(name),
  );
  const datedBranches = await Promise.all(
    nonExemptBranches.map(async ({ name, commit }) => {
      const headCommit = await githubJson(
        `${repoPath}/commits/${encodeURIComponent(commit.sha)}`,
        token,
      );
      const committedAt = headCommit.commit.committer?.date ?? headCommit.commit.author?.date;
      return { name, sha: commit.sha, committedAt };
    }),
  );
  const staleBranches = findStaleBranches({
    branches: datedBranches,
    openPullHeads,
  });

  await writeSummary(process.env.GITHUB_STEP_SUMMARY, staleBranches, DEFAULT_GRACE_DAYS);
  if (staleBranches.length > 0) {
    process.exitCode = 1;
  }
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}

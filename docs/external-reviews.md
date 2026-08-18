# External exact-head reviews

`tools/external_review.py` is an optional maintainer-run bridge for posting Claude Code and Grok Build reviews directly to the top-level conversation on an open GitHub pull request. It is developer tooling, not a required CI, runtime, benchmark, or release dependency.

## One-time setup

Install the official provider CLIs and authenticate them outside the repository:

```text
curl -fsSL https://claude.ai/install.sh | bash
claude auth login

curl -fsSL https://x.ai/cli/install.sh | bash
grok login --device-auth
```

The bridge uses the existing authenticated `gh` session for its one GitHub write. Provider authentication may use the providers' local OAuth or device sessions, or intentionally configured local provider secrets. Never place credentials in this repository or a review prompt.

Check the complete local setup without posting or invoking a review model:

```text
python3 tools/external_review.py doctor
```

`doctor` checks `git`, `gh`, GitHub authentication, both provider executables and versions, provider authentication, and repository context. It reports an actionable login command when authentication is missing and does not print credential material.

## Run a review

Prepare one provider-neutral Markdown prompt that states the review scope, relevant source boundaries, expected checks, and areas to challenge. Run one provider or both against the same prompt:

```text
python3 tools/external_review.py review \
  --pr 103 \
  --provider claude \
  --prompt-file /path/to/review-prompt.md

python3 tools/external_review.py review \
  --pr 103 \
  --provider grok \
  --prompt-file /path/to/review-prompt.md

python3 tools/external_review.py review \
  --pr 103 \
  --provider all \
  --prompt-file /path/to/review-prompt.md
```

The prompt file is read locally. Provider-specific temporary prompt and configuration paths are outside committed source and are removed after the command. Claude session persistence is disabled. Grok runs with an ephemeral home that retains access to the maintainer's existing authentication path but discards the review session, prompt copy, configuration, and logs after execution.

## Exact-head and identity contract

Before either provider runs, the bridge resolves the live PR number, state, base SHA, and head SHA through `gh`. It fetches missing commit objects without creating a permanent review branch and creates a temporary detached worktree at the exact head. Providers receive one common review request plus a machine-readable contract containing `pr_number`, `head_sha`, `verdict`, and `body_markdown`.

The bridge owns provider identity. Model prose is never authoritative. An explicit provider or reviewer claim that conflicts with the invoked adapter—for example, Grok returning `Reviewer: Claude`—fails validation and posts nothing. Redundant matching identity and exact-head metadata are removed from the model body so they cannot compete with the trusted comment header.

After all requested providers finish and validate, the bridge removes the detached worktree and re-queries the live PR. A closed PR or moved head is stale evidence: the command exits nonzero and posts nothing. In `--provider all` mode, both results must execute and validate before either is posted; PASS and FINDINGS are both valid verdicts and may be posted together.

Each successful result appears as a top-level PR conversation comment with a wrapper-owned provider, provider CLI version, discoverable model metadata, PR number, exact reviewed head, verdict, and review role. Claude is labeled as the Issue #98 external second-pair review; Grok is labeled as additional independent review evidence.

## Security boundary

Provider processes receive read-only repository inspection permissions. Claude is limited to repository reads and a small read-only `git` command set. Grok has the same narrow command set plus its kernel-enforced `read-only` sandbox, disabled web search, disabled subagents, and disabled memory. Before a Grok run, the bridge rejects discovered project instructions, hooks, skills, plugins, MCP servers, or permission sources so reviewed code cannot widen the adapter. The bridge verifies that the detached worktree remains clean after each provider.

The child environment removes `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, and `GITHUB_ENTERPRISE_TOKEN`, and points `GH_CONFIG_DIR` at an empty temporary directory. Providers cannot use the bridge's authenticated `gh` configuration. Only the wrapper revalidates the head and posts the final comment. Providers cannot push, merge, delete branches, mutate issues or releases, or post GitHub comments through the granted tool set.

Ordinary unit tests mock provider and GitHub interactions. They do not call provider APIs, require provider authentication, or post to GitHub.

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

`doctor` checks `git`, `gh`, GitHub authentication, both provider executables and versions, provider authentication, repository context, Grok model selection, and the exact safety-critical CLI flag spellings used for structured output, noninteractive permissions, tool restriction, sandboxing, customization isolation, web/subagent disabling, and session suppression. It reports an actionable login command when authentication is missing, fails when an installed CLI does not advertise the required invocation surface, and does not print credential material. Grok's hidden `--no-auto-update --no-memory` controls are also exercised with a harmless version lookup rather than inferred from help text.

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

The prompt file is read locally. Provider-specific temporary prompt and configuration paths are outside committed source and are removed after the command. Claude session persistence is disabled. Grok runs with an ephemeral home containing a generated sandbox profile and discards the review session, prompt copy, configuration, and logs after execution. The bridge resolves the existing Grok authentication target to a readable regular file and never copies or modifies its contents.

## Exact-head and identity contract

Before either provider runs, the bridge resolves the live PR number, state, base SHA, and head SHA through `gh`. It fetches missing commit objects without creating a permanent review branch, generates the complete base-to-head diff itself, and creates a temporary detached worktree at the exact head. Providers receive that wrapper-generated diff, one common review request, and a machine-readable contract containing `pr_number`, `head_sha`, `verdict`, `body_markdown`, and structured `findings`.

Every structured finding contains a `severity` (`BLOCKER`, `HIGH`, `MEDIUM`, or `LOW`), `title`, and `detail`. `PASS` requires an empty findings collection; `FINDINGS` requires at least one valid structured finding. The bridge never manufactures findings from prose. This prevents progress messages or other non-substantive bodies from validating as findings evidence. Structured findings are rendered into the posted comment beneath the provider's human-readable review body. Grok may return the authoritative schema object under the JSON envelope's camelCase `structuredOutput` field; the bridge prefers that object to prose fields and keeps strict JSON parsing for any fallback.

The bridge owns provider identity. Model prose is never authoritative. An explicit provider or reviewer claim that conflicts with the invoked adapter—for example, Grok returning `Reviewer: Claude` or a Claude body starting with any ATX-heading lookalike of the wrapper's `External exact-head review` title—fails validation and posts nothing. Redundant matching identity and syntactically exact PR, full-head, verdict, and review-role metadata are removed so they cannot compete with the trusted comment header. Metadata-shaped explanatory prose, short SHAs, placeholders, and extended verdict sentences are retained because they are not valid wrapper metadata claims.

After all requested providers finish and validate, the bridge removes the detached worktree and re-queries the live PR. A closed PR or moved head is stale evidence: the command exits nonzero and posts nothing. In `--provider all` mode, both results must execute and validate before either is posted; PASS and FINDINGS are both valid verdicts and may be posted together.

Each successful result appears as a top-level PR conversation comment with a wrapper-owned provider, provider CLI version, discoverable model metadata, PR number, exact reviewed head, verdict, and review role. Claude is labeled as the Issue #98 external second-pair review and explicitly requests the rolling `opus` alias; the exact resolved Claude model returned by the CLI remains recorded in the posted evidence. Grok is labeled as additional independent review evidence. Grok's model is selected explicitly: the stable `grok-build` alias is preferred when the installed CLI advertises it, otherwise the advertised default is explicitly requested. The returned metadata must still identify a Grok Build model, such as `grok-4.6-build`, or validation fails before posting. Before publication, the wrapper redacts secret-shaped content—including GitHub fine-grained `github_pat_` values—and any exact resolved Grok-auth path from provider-generated content. Wrapper-owned PR and exact-head metadata are not subject to provider-content redaction.

## Security boundary

Provider processes receive read-only repository inspection permissions and no shell tool. Claude explicitly requests the rolling Opus alias and exposes only `Read`, with an absolute rule scoped to the exact detached checkout under `dontAsk`; Grep and Glob are not enabled. The exact resolved Opus model returned by Claude remains recorded in the posted evidence. Grok exposes only Read and Grep through checkout-relative `Read(./**)` and `Grep(./**)` rules, with an explicit tool-level deny for the resolved authentication file. Bash remains denied, web search and subagents are disabled, and memory is disabled.

Grok review and configuration inspection use the same ephemeral custom sandbox profile extending `strict`. Grok Build 1.0.5 accepts only literal directories in a profile's `read_only` field, not individual files, so the narrowest supported runtime exception is the resolved authentication file's canonical parent directory. The bridge rejects filesystem root, the user's home, shared temporary and broad system directories, and any directory overlapping the detached review worktree; the supported layout is a bounded Grok-specific or dedicated credential directory. Sibling files within that accepted directory remain process-readable, but model-facing Read and Grep receive neither directory nor auth-file access. The exception exists only so the runtime can authenticate, adds no writable path, and leaves GitHub credentials outside the provider environment. Any sandbox-application warning fails closed even when the CLI returns success. The sandbox is defense in depth, not the sole confinement boundary.

Before either provider runs, the wrapper resolves every repository symlink and rejects broken links or links escaping the detached checkout; the regular linked-worktree `.git` pointer file is unaffected. The wrapper supplies the base-to-head diff, so removing provider shell access does not remove PR comparison evidence. Before a Grok run, the bridge rejects discovered project instructions, hooks, skills, plugins, MCP servers, or permission sources so reviewed code cannot widen the adapter. The bridge verifies that the detached worktree remains clean after each provider.

Safe local synthetic-sentinel probes against Claude Code 2.1.234 and Grok Build 1.0.5 confirmed that the configured file tools could read repository files but could not read a sibling file outside the checkout. The Claude probe also confirms that Grep and Glob are unavailable and records the resolved Opus model. A Grok probe using the custom auth exception additionally confirms that authentication works while model Read cannot access the auth file. `doctor` verifies the exact invocation capability surface on every setup check and each adapter repeats it before invocation. This is still dependent on the installed CLIs continuing to honor their documented permission and sandbox semantics; repeat both safe probes after a significant provider upgrade.

The child environment removes `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, and `GITHUB_ENTERPRISE_TOKEN`, and points `GH_CONFIG_DIR` at an empty temporary directory. Providers cannot use the bridge's authenticated `gh` configuration. Only the wrapper revalidates the head and posts the final comment. Providers cannot push, merge, delete branches, mutate issues or releases, or post GitHub comments through the granted tool set.

Ordinary unit tests mock provider and GitHub interactions. They do not call provider APIs, require provider authentication, or post to GitHub.

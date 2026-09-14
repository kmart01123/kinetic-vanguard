# Branching Bolt crowd requirement: review

Date: 2026-09-14. Scope: the local 3/4/5-die integration, minimum three recipients, no additional attack rolls. This is a local snapshot review, not a PR approval or CI result.

Reviewed snapshot: `be2a1e85309e58733f171ac03bde535e4cafd7d2`. Base: `d073446f3c46f8186c9fbdeecba038bce9dc04e9`. Canonical authority SHA-256: `8d2e538033a9fb601b242c34ea1c2ed193e062baa1f6eefca641804007bad50a`. The working branch remains uncommitted and unpushed; a separate detached snapshot freezes the reviewed files. No rules were changed during review.

## Codex findings

### C1 — MEDIUM: Three recipients do not require an enemy crowd

Locations: `KineticVanguard.yaml:4024`, `KineticVanguard.yaml:4032`, `docs/branching-bolt-integration.md:29`, `docs/branching-bolt-integration.md:79`.

The canonical rule requires distinct additional creatures but does not require hostility, and the minimum is dice assigned rather than damage suffered. A lone boss and two nearby allies are legal recipients for Tier-2 3/1/1: the boss receives three rider dice and each ally receives one. Lightning-immune secondary creatures can satisfy the same requirement without taking damage. Therefore the statement that this is unavailable against a lone enemy is stronger than the written rule or the homogeneous hostile-cluster benchmark establishes. This is a design/eligibility gap, not an arithmetic or allocation-enumeration defect.

Suggested disposition: Decide whether the required secondary creatures must be enemies. If friendly routing is intentional, retain the mechanics and qualify the lone-enemy claims and benchmark scope. If enemy crowds are required, add an explicit eligibility restriction without reintroducing attack rolls; that is a new design choice needing maintainer disposition.

### C2 — LOW: Calculator minimum-target instruction duplicates a canonical parameter

Locations: `ui/approved-ui-text.json:8`, `src/runtime.ts:171`, `src/runtime.ts:172`.

The allocation selector reads spec.minimum_targets, but its explanatory token always says to select at least three targets. The schema and neutral harness mutation test support other minima, including two. A valid minimum_targets:2 allocation contract would expose two-target choices beside a three-target instruction. Current Branching Bolt remains correct because its canonical minimum is three; this is a supported-authoring consistency gap.

Suggested disposition: Use a minimum-target placeholder populated from spec.minimum_targets, or omit the duplicated numeric minimum from the static instruction and display the canonical metric.

## Verified scope

The current allocation arithmetic, primary-hit-only resolution, normal original-strike Prowess/critical behavior, per-target packet defenses, and grant/tier/cost limits are consistent across the inspected canonical mechanics, Calculator and harness. The tests explicitly cover all eleven ordered Tier-2 allocations. Existing validation includes 540 local tests and the completed 12-worker native benchmark; this review inspected retained evidence and matching source hashes rather than rerunning the full benchmark.

The single-target benchmark correctly excludes Branching Bolt in its one-creature scenarios. It does not model allied recipients, so it cannot establish that Branching Bolt is unavailable whenever there is only one enemy. Numerical results remain evidence for the documented homogeneous scenarios.

## External review collection

Both providers received the same complete base-to-snapshot diff, approved design constraints, code/test inspection request, and completed benchmark verification. Provider access is read-only and isolated to separate clean detached checkouts. The common prompt SHA-256 is `1a5c841275859f827f476b04b69b6fa1e8c91dd1b118686ca57c270b4b684e6c`.

Claude has not supplied a valid completed review: the first structured-output attempt reported a `tool_use` stop reason; a fresh plain-JSON attempt returned malformed JSON. Both were rejected by the existing validation. No rejected provider output has been used as review evidence.

Grok's initial authentication failure cleared on a fresh check. Its first structured-output attempt returned INCOMPLETE with a startup description and was rejected. Its fresh plain-JSON attempt also returned malformed JSON and was rejected. Both providers' bounded attempts are now finished; neither supplied a validated completed review. No completed Claude/Grok pair is available, and no external review comments have been posted.

The plain-JSON attempts remove only the CLI structured-output transport flag. Read-only isolation, provider completion metadata checks, strict JSON/contract parsing, provider identity checks, finality validation, source-hash binding, and clean-checkout/cleanup requirements remain enforced. These are bounded fresh attempts, not replayed historical reviews or accepted partial outputs. No review-bridge production code was modified.

Review inputs, invocation scripts, sanitized failure diagnostics, and any independently validated results are retained in `artifacts/branching-bolt-crowd-review/`. Protocol field `pr_number: 1` is solely an internal local request identifier for the existing adapter contract; no GitHub PR #1 is involved.

### Fresh retry after CLI updates

At the maintainer's request, both providers were invoked again with the standard structured-output adapter after updating to Claude Code 2.1.270 and Grok 1.0.30. Authentication and safety-capability checks passed for both. All 31 source hashes and the shared prompt matched the original frozen snapshot; no previous provider output was reused.

- Claude stopped after 334.22 seconds with `stop_reason: tool_use`; completion validation rejected its partial output.
- Grok stopped after 136.10 seconds with verdict `INCOMPLETE`, reporting that it was still reading the prompt and inspecting the snapshot; contract validation rejected it.

The CLI updates did not produce a completed external review. Both temporary review checkouts were removed, neither result was accepted, and no GitHub comments were posted. These failures establish that the updated invocations still return incomplete results; they do not establish the underlying cause. Fresh scripts and sanitized diagnostics are retained separately in `artifacts/branching-bolt-crowd-review-cli-update/`. No further automatic retries were made.

## Maintainer-supplied reviews and disposition

The maintainer subsequently supplied direct Grok and Claude responses naming the reviewed snapshot above. Both readable responses report the same medium eligibility finding and low Calculator instruction finding as Codex, with no additional arithmetic or resolution defect reported. These are maintainer-supplied responses, not bridge-validated executions. Claude's attachment is truncated/garbled and its claimed test reruns were not accompanied by execution logs. Its suggestion that resistance could zero Tier-2 collateral is incorrect: Tier 2 ignores resistance; immunity can prevent the packet. The existing benchmark classifications remain valid for their modeled scenarios.

The maintainer approved both corrections. The working revision now requires every secondary creature to be hostile to the user, authors `secondary_target_eligibility: hostile` in the canonical allocation rule, carries it into the Calculator and harness projections, and rejects non-hostile secondary declarations. The primary has no new allegiance restriction, hostile immune creatures remain eligible, and the original strike remains the only attack roll. The Calculator instruction now reads `minimum_targets` from the projection.

C1 and C2 are addressed in the working revision, with regression checks for non-hostile secondaries and a synthetic two-target Calculator minimum. Validation and fresh benchmark evidence are recorded in `docs/branching-bolt-integration.md` and `artifacts/branching-bolt-hostile-review-fixes/`. The old snapshot and provider comments above remain historical evidence for the pre-fix revision; they are not external approval of these corrections.

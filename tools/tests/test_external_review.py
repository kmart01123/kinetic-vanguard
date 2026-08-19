from __future__ import annotations

import contextlib
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock

from tools import external_review as bridge


HEAD = "1" * 40
MOVED_HEAD = "2" * 40
BASE = "a" * 40
PR_NUMBER = 104
CLAUDE_HELP = " ".join(
    spelling
    for _label, spellings in bridge.REQUIRED_CLI_CAPABILITIES["claude"]
    for spelling in spellings[:1]
)
GROK_HELP = " ".join(
    spelling
    for _label, spellings in bridge.REQUIRED_CLI_CAPABILITIES["grok"]
    for spelling in spellings[:1]
)
GROK_MODELS = """You are logged in with grok.com.

Default model: grok-4.6

Available models:
  * grok-4.6 (default)
  - grok-4.5
"""


def completed(
    args: tuple[str, ...] = ("test",),
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def metadata(head: str = HEAD, state: str = "OPEN") -> bridge.PRMetadata:
    return bridge.PRMetadata(
        number=PR_NUMBER,
        state=state,
        head_sha=head,
        base_sha=BASE,
        head_ref="agent/issue-104",
        base_ref="main",
        url=f"https://github.test/pull/{PR_NUMBER}",
    )


def execution(
    provider: str,
    *,
    verdict: str = "PASS",
    body: str = "No material findings.",
    pr_number: int = PR_NUMBER,
    head: str = HEAD,
    findings: tuple[bridge.ReviewFinding, ...] | None = None,
    model_claim: str | None = None,
) -> bridge.ProviderExecution:
    if findings is None:
        findings = (
            (
                bridge.ReviewFinding(
                    severity="MEDIUM",
                    title="Material finding",
                    detail="The implementation needs a focused correction.",
                ),
            )
            if verdict == "FINDINGS"
            else ()
        )
    model_metadata = "grok-build" if provider == "grok" else "claude-model"
    return bridge.ProviderExecution(
        result=bridge.ReviewResult(
            pr_number=pr_number,
            head_sha=head,
            verdict=verdict,
            body_markdown=body,
            findings=findings,
            model_claim=model_claim,
        ),
        cli_version=f"{provider} 1.0",
        model_metadata=model_metadata,
        requested_model=model_metadata if provider == "grok" else None,
    )


class FakeGitHub:
    def __init__(self, metadata_sequence: list[bridge.PRMetadata]) -> None:
        self.metadata_sequence = metadata_sequence
        self.comments: list[str] = []

    def repository(self) -> str:
        return "owner/repository"

    def pr_metadata(self, repository: str, pr_number: int) -> bridge.PRMetadata:
        self.assert_coordinates(repository, pr_number)
        return self.metadata_sequence.pop(0)

    def assert_coordinates(self, repository: str, pr_number: int) -> None:
        if repository != "owner/repository" or pr_number != PR_NUMBER:
            raise AssertionError("unexpected GitHub coordinates")

    def post_comment(self, repository: str, pr_number: int, body: str) -> tuple[int, str]:
        self.assert_coordinates(repository, pr_number)
        self.comments.append(body)
        comment_id = 9000 + len(self.comments)
        return comment_id, f"https://github.test/comment/{comment_id}"


class FakeRepository:
    def __init__(
        self,
        symlink_error: Exception | None = None,
        clean_error_for: str | None = None,
    ) -> None:
        self.ensured: list[tuple[str, int | None]] = []
        self.cleaned = False
        self.clean_checks: list[str] = []
        self.symlink_checks = 0
        self.symlink_error = symlink_error
        self.clean_error_for = clean_error_for

    def ensure_commit(self, sha: str, *, pr_number: int | None = None) -> None:
        self.ensured.append((sha, pr_number))

    def assert_clean(self, worktree: Path, provider_name: str) -> None:
        self.clean_checks.append(provider_name)
        if provider_name == self.clean_error_for:
            raise bridge.ReviewBridgeError(
                f"{provider_name} modified the detached review worktree"
            )

    def validate_worktree_symlinks(self, worktree: Path) -> None:
        self.symlink_checks += 1
        if self.symlink_error is not None:
            raise self.symlink_error

    def base_to_head_diff(self, base_sha: str, head_sha: str) -> str:
        if (base_sha, head_sha) != (BASE, HEAD):
            raise AssertionError("unexpected diff coordinates")
        return "diff --git a/tool.py b/tool.py\n"

    @contextlib.contextmanager
    def detached_worktree(self, pr_number: int, head_sha: str):
        try:
            yield Path("/detached/exact-head")
        finally:
            self.cleaned = True


class FakeAdapter:
    def __init__(self, outcome: bridge.ProviderExecution | Exception) -> None:
        self.outcome = outcome
        self.prompts: list[str] = []

    def run(self, worktree: Path, prompt: str) -> bridge.ProviderExecution:
        self.prompts.append(prompt)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class QueueRunner:
    def __init__(self, responses: list[subprocess.CompletedProcess[str]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []
        self.grok_sandbox_profiles: list[str] = []
        self.claude_settings_payloads: list[dict[str, object]] = []
        self.claude_mcp_payloads: list[dict[str, object]] = []
        self.claude_config_paths: list[Path] = []
        self.claude_config_modes: list[int] = []

    def run(
        self,
        args,
        *,
        cwd=None,
        env=None,
        input_text=None,
        timeout=None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(
            {
                "args": tuple(args),
                "cwd": cwd,
                "env": dict(env) if env is not None else None,
                "input_text": input_text,
                "timeout": timeout,
            }
        )
        if env is not None and "GROK_HOME" in env:
            sandbox_file = Path(env["GROK_HOME"]) / "sandbox.toml"
            if sandbox_file.is_file():
                self.grok_sandbox_profiles.append(
                    sandbox_file.read_text(encoding="utf-8")
                )
        arguments = tuple(args)
        if "--settings" in arguments and "--mcp-config" in arguments:
            settings_file = Path(arguments[arguments.index("--settings") + 1])
            mcp_config_file = Path(arguments[arguments.index("--mcp-config") + 1])
            self.claude_config_paths.extend((settings_file, mcp_config_file))
            self.claude_config_modes.extend(
                (
                    settings_file.stat().st_mode & 0o777,
                    mcp_config_file.stat().st_mode & 0o777,
                )
            )
            self.claude_settings_payloads.append(
                bridge.json.loads(settings_file.read_text(encoding="utf-8"))
            )
            self.claude_mcp_payloads.append(
                bridge.json.loads(mcp_config_file.read_text(encoding="utf-8"))
            )
        if not self.responses:
            raise AssertionError(f"no queued response for {tuple(args)}")
        return self.responses.pop(0)


class ReviewBridgeTests(unittest.TestCase):
    def run_bridge(
        self,
        providers: tuple[str, ...],
        outcomes: dict[str, bridge.ProviderExecution | Exception],
        *,
        live_head: str = HEAD,
    ) -> tuple[list[bridge.PostedComment], FakeGitHub, FakeRepository]:
        github = FakeGitHub([metadata(), metadata(live_head)])
        repository = FakeRepository()
        adapters = {name: FakeAdapter(outcome) for name, outcome in outcomes.items()}
        posted = bridge.ReviewBridge(
            github, repository, adapters, emit=lambda _message: None
        ).review(PR_NUMBER, providers, "Review the implementation.")
        return posted, github, repository

    def assert_review_rejected(
        self,
        providers: tuple[str, ...],
        outcomes: dict[str, bridge.ProviderExecution | Exception],
        error: str,
        *,
        repository: FakeRepository | None = None,
        metadata_sequence: list[bridge.PRMetadata] | None = None,
    ) -> tuple[FakeGitHub, FakeRepository, dict[str, FakeAdapter]]:
        github = FakeGitHub(metadata_sequence or [metadata()])
        repository = repository or FakeRepository()
        adapters = {name: FakeAdapter(outcome) for name, outcome in outcomes.items()}
        with self.assertRaisesRegex(bridge.ReviewBridgeError, error):
            bridge.ReviewBridge(
                github, repository, adapters, emit=lambda _message: None
            ).review(PR_NUMBER, providers, "Review.")
        self.assertEqual(github.comments, [])
        return github, repository, adapters

    def test_exact_head_pass_posts_provider_owned_wrapper(self) -> None:
        cases = (
            ("claude", "Claude", "Issue #98 external second-pair review"),
            ("grok", "Grok", "additional independent review evidence"),
        )
        for provider, display_name, role in cases:
            with self.subTest(provider=provider):
                posted, github, repository = self.run_bridge(
                    (provider,), {provider: execution(provider)}
                )
                comment = github.comments[0]
                self.assertEqual(len(posted), 1)
                self.assertIn(
                    f"External exact-head review — {display_name}", comment
                )
                self.assertIn(f"`{HEAD}`", comment)
                self.assertIn("**PASS**", comment)
                self.assertIn(role, comment)
                self.assertTrue(repository.cleaned)

    def test_claude_findings_posts_findings(self) -> None:
        _posted, github, _repository = self.run_bridge(
            ("claude",),
            {"claude": execution("claude", verdict="FINDINGS", body="- Finding")},
        )
        self.assertIn("**FINDINGS**", github.comments[0])
        self.assertIn("- Finding", github.comments[0])

    def test_wrong_review_coordinates_and_verdict_are_rejected(self) -> None:
        cases = (
            (
                "wrong PR",
                execution("claude", pr_number=103),
                "returned PR #103",
            ),
            (
                "wrong or stale result head",
                execution("claude", head=MOVED_HEAD),
                "returned head",
            ),
            ("invalid verdict", execution("claude", verdict="MAYBE"), "invalid verdict"),
        )
        for label, result, error in cases:
            with self.subTest(case=label):
                self.assert_review_rejected(
                    ("claude",), {"claude": result}, error
                )

    def test_malformed_provider_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "malformed JSON"):
            bridge.extract_contract("not json", "Claude")

    def test_live_grok_envelope_precedes_text_and_validates_all_mode(self) -> None:
        envelope = {
            "modelUsage": {"grok-4.6-build": {}},
            "stopReason": "end_turn",
            "structuredOutput": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No material findings.",
                "findings": [],
            },
            "text": '{"first": true}\n{"extra": true}',
        }
        contract, model = bridge.extract_contract(
            bridge.json.dumps(envelope), "Grok"
        )
        self.assertEqual(contract, envelope["structuredOutput"])
        self.assertEqual(model, "grok-4.6-build")
        grok_execution = bridge.ProviderExecution(
            result=bridge.review_result_from_contract(contract),
            cli_version="grok 1.0.5",
            model_metadata=model,
            requested_model=model,
        )
        posted, github, _repository = self.run_bridge(
            ("claude", "grok"),
            {"claude": execution("claude"), "grok": grok_execution},
        )
        self.assertEqual(len(posted), 2)
        self.assertEqual(len(github.comments), 2)

    def test_claude_multi_model_usage_selects_opus_and_renders_evidence(self) -> None:
        envelope = {
            "modelUsage": {
                "claude-haiku-4-5-20251001": {
                    "modelCalls": 4,
                    "inputTokens": 9000,
                    "outputTokens": 2000,
                },
                "claude-opus-4-6": {
                    "modelCalls": 1,
                    "inputTokens": 4000,
                    "outputTokens": 1000,
                },
            },
            "structured_output": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No material findings.",
                "findings": [],
            },
        }
        contract, model = bridge.extract_contract(
            bridge.json.dumps(envelope), "Claude"
        )
        self.assertEqual(model, "claude-opus-4-6")
        claude_execution = bridge.ProviderExecution(
            result=bridge.review_result_from_contract(contract),
            cli_version="claude 2.1.234",
            model_metadata=model,
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",), {"claude": claude_execution}
        )
        self.assertIn("`claude-opus-4-6`", github.comments[0])

    def test_grok_multi_model_usage_prefers_build_identity(self) -> None:
        envelope = {
            "modelUsage": {
                "grok-4.5": {"modelCalls": 9, "outputTokens": 9000},
                "grok-4.7-build": {"modelCalls": 1, "outputTokens": 1000},
            },
            "structuredOutput": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No material findings.",
                "findings": [],
            },
        }
        contract, model = bridge.extract_contract(
            bridge.json.dumps(envelope), "Grok"
        )
        self.assertEqual(model, "grok-4.7-build")
        valid = bridge.ProviderExecution(
            result=bridge.review_result_from_contract(contract),
            cli_version="grok 1.0.5",
            model_metadata=model,
            requested_model=model,
        )
        posted, _github, _repository = self.run_bridge(
            ("grok",), {"grok": valid}
        )
        self.assertEqual(len(posted), 1)

    def test_flat_contract_model_claim_is_not_trusted_model_metadata(self) -> None:
        flat_contract = {
            "pr_number": PR_NUMBER,
            "head_sha": HEAD,
            "verdict": "PASS",
            "body_markdown": "No material findings.",
            "findings": [],
            "model": "claude-opus-self-claimed",
            "modelUsage": {
                "claude-opus-4-6": {"modelCalls": 1, "outputTokens": 1000}
            },
        }
        contract, model = bridge.extract_contract(
            bridge.json.dumps(flat_contract), "Claude"
        )
        self.assertIsNone(model)
        self.assertNotIn("modelUsage", contract)
        result = bridge.review_result_from_contract(contract)
        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.model_claim, "claude-opus-self-claimed")

    def test_grok_flat_contract_self_claim_cannot_establish_build_provenance(self) -> None:
        flat_contract = {
            "pr_number": PR_NUMBER,
            "head_sha": HEAD,
            "verdict": "PASS",
            "body_markdown": "No material findings.",
            "findings": [],
            "model": "grok-4.6-build",
        }
        contract, model = bridge.extract_contract(
            bridge.json.dumps(flat_contract), "Grok"
        )
        self.assertIsNone(model)
        untrusted = bridge.ProviderExecution(
            result=bridge.review_result_from_contract(contract),
            cli_version="grok 1.0.5",
            model_metadata=model,
            requested_model="grok-4.6-build",
        )
        github = FakeGitHub([metadata()])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "omitted model metadata"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"grok": FakeAdapter(untrusted)},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(github.comments, [])

    def test_explicit_outer_model_precedes_model_usage(self) -> None:
        envelope = {
            "modelId": "claude-opus-explicit",
            "modelUsage": {
                "claude-opus-auxiliary": {
                    "modelCalls": 99,
                    "outputTokens": 9999,
                }
            },
            "structuredOutput": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No material findings.",
                "findings": [],
            },
        }
        _contract, model = bridge.extract_contract(
            bridge.json.dumps(envelope), "Claude"
        )
        self.assertEqual(model, "claude-opus-explicit")

    def test_published_cli_and_model_metadata_are_single_line_table_values(self) -> None:
        hostile = bridge.ProviderExecution(
            result=execution("claude").result,
            cli_version="claude 2.1.234\n| Verdict | FINDINGS |",
            model_metadata="claude-opus-5\r\n| PR | #999 | pipe | data",
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",), {"claude": hostile}
        )
        comment = github.comments[0]
        self.assertEqual(comment.count("| PR | #104 |"), 1)
        self.assertEqual(
            comment.count(f"| Exact reviewed head | `{HEAD}` |"), 1
        )
        self.assertEqual(comment.count("| Verdict | **PASS** |"), 1)
        self.assertEqual(
            comment.count(
                "| Review role | Issue #98 external second-pair review |"
            ),
            1,
        )
        self.assertIn(
            "| Model | `claude-opus-5 \\| PR \\| #999 \\| pipe \\| data` |",
            comment,
        )
        self.assertNotIn("\r", comment)

    def test_grok_model_provenance_accepts_canonical_versions(self) -> None:
        cases = (
            ("grok-4.6", "grok-4.6", None),
            ("grok-4.6", "grok-4.6-build", None),
            ("grok-4.6-build", "grok-4.6", None),
            ("GROK-4.6", "grok-4.6-build", None),
            ("grok-build", "grok-build", None),
            ("grok-4.6", "grok-4.6-build", "  grok-4.6  "),
            ("grok-4.6", "grok-4.6-build", "grok-4.6-build"),
        )
        for requested_model, reported_model, model_claim in cases:
            with self.subTest(
                requested=requested_model,
                reported=reported_model,
                structured=model_claim,
            ):
                result = execution("grok", model_claim=model_claim)
                valid = bridge.ProviderExecution(
                    result=result.result,
                    cli_version=result.cli_version,
                    model_metadata=reported_model,
                    requested_model=requested_model,
                )
                posted, _github, _repository = self.run_bridge(
                    ("grok",), {"grok": valid}
                )
                self.assertEqual(len(posted), 1)

    def test_grok_model_provenance_failures_are_rejected(self) -> None:
        cases = (
            ("other provider", "claude-sonnet", "grok-4.6", None, "identity conflicts"),
            (
                "different version",
                "grok-4.5-build",
                "grok-4.6",
                None,
                "requested `grok-4.6`",
            ),
            ("missing reported model", None, "grok-4.6", None, "omitted model metadata"),
            ("missing requested model", "grok-4.6", None, None, "omitted the requested"),
            (
                "different structured version",
                "grok-4.6",
                "grok-4.6",
                "grok-4.5",
                "structured model claim did not match",
            ),
        )
        for label, reported, requested, claim, error in cases:
            with self.subTest(case=label):
                result = execution("grok", model_claim=claim)
                invalid = bridge.ProviderExecution(
                    result=result.result,
                    cli_version=result.cli_version,
                    model_metadata=reported,
                    requested_model=requested,
                )
                self.assert_review_rejected(
                    ("grok",), {"grok": invalid}, error
                )

    def test_provider_subprocess_failure_posts_nothing(self) -> None:
        _github, repository, _adapters = self.assert_review_rejected(
            ("claude",),
            {"claude": bridge.ReviewBridgeError("provider failed")},
            "provider failed",
        )
        self.assertTrue(repository.cleaned)

    def test_moved_head_posts_nothing(self) -> None:
        self.assert_review_rejected(
            ("claude",),
            {"claude": execution("claude")},
            "head moved",
            metadata_sequence=[metadata(), metadata(MOVED_HEAD)],
        )

    def test_all_mode_provider_failures_are_atomic(self) -> None:
        cases: tuple[
            tuple[str, bridge.ProviderExecution | Exception, str], ...
        ] = (
            ("provider output", bridge.ReviewBridgeError("bad output"), "bad output"),
            (
                "sandbox setup",
                bridge.ReviewBridgeError(
                    "Grok review could not enforce the custom Grok sandbox"
                ),
                "custom Grok sandbox",
            ),
            (
                "semantic result",
                execution(
                    "grok", verdict="FINDINGS", body="Review starting.", findings=()
                ),
                "structured findings",
            ),
        )
        for label, failure, error in cases:
            with self.subTest(case=label):
                self.assert_review_rejected(
                    ("claude", "grok"),
                    {"claude": execution("claude"), "grok": failure},
                    error,
                )

    def test_all_mode_pass_and_findings_are_both_valid(self) -> None:
        _posted, github, _repository = self.run_bridge(
            ("claude", "grok"),
            {
                "claude": execution("claude", verdict="FINDINGS", body="- Finding"),
                "grok": execution("grok", verdict="PASS"),
            },
        )
        self.assertIn("**FINDINGS**", github.comments[0])
        self.assertIn("**PASS**", github.comments[1])

    def test_wrapper_owned_matching_metadata_is_stripped_from_body(self) -> None:
        bodies = (
            (
                "## External exact-head review — Claude\n"
                "Provider: Claude\n"
                f"PR: #{PR_NUMBER}\n"
                f"Head SHA: {HEAD}\n"
                "Verdict: PASS\n"
                "Review role: Issue #98 external second-pair review"
            ),
            (
                "<h3>External exact-head review — Claude</h3>\n"
                "<h4 class=\"identity\">Provider: Claude</h4>\n"
                "<strong>Reviewer: Claude</strong>\n"
                "<b>Model: Claude Opus</b>"
            ),
        )
        for body in bodies:
            with self.subTest(form=body.splitlines()[0]):
                body = f"{body}\n\nSubstantive review remains."
                _posted, github, _repository = self.run_bridge(
                    ("claude",), {"claude": execution("claude", body=body)}
                )
                comment = github.comments[0]
                self.assertEqual(
                    comment.count("External exact-head review — Claude"), 1
                )
                self.assertEqual(
                    comment.count("Issue #98 external second-pair review"), 1
                )
                self.assertIn("Substantive review remains.", comment)

    def test_unrelated_html_is_preserved(self) -> None:
        body = (
            "<h4>Architecture notes</h4>\n"
            "<strong>Important context</strong>\n"
            "<b>Read-only behavior</b>\n"
            "<div class=\"detail\">Ordinary unrelated HTML.</div>"
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",), {"claude": execution("claude", body=body)}
        )
        for line in body.splitlines():
            self.assertIn(line, github.comments[0])

    def test_provider_content_is_redacted_in_final_posted_comment(self) -> None:
        secrets = (
            "github_pat_synthetic_secret_1234567890",
            "ghp_1234567890",
            "gho_abcdefghij",
            "sk-abcdefghijkl",
            "xai-abcdefghijkl",
            "token=visible-value",
            "password: visible-value",
            "api_key=visible-value",
        )
        body = "Provider evidence: " + " ".join(secrets)
        findings = (
            bridge.ReviewFinding(
                severity="HIGH",
                title="Leaked ghp_zzzzzzzzzz",
                detail="Remove secret=structured-value before publication.",
            ),
        )
        leaky = execution(
            "claude", verdict="FINDINGS", body=body, findings=findings
        )
        leaky = bridge.ProviderExecution(
            result=leaky.result,
            cli_version="claude ghp_cliversion123",
            model_metadata="claude-sk-modelmetadata123",
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",),
            {"claude": leaky},
        )
        comment = github.comments[0]
        for secret in secrets:
            self.assertNotIn(secret, comment)
        self.assertNotIn("ghp_zzzzzzzzzz", comment)
        self.assertNotIn("structured-value", comment)
        self.assertNotIn("ghp_cliversion123", comment)
        self.assertNotIn("sk-modelmetadata123", comment)
        self.assertGreaterEqual(comment.count("[REDACTED]"), 12)
        self.assertIn(f"`{HEAD}`", comment)

    def test_neutral_metadata_shaped_prose_is_retained(self) -> None:
        cases = (
            execution(
                "claude",
                body=(
                    "Provider: <string>\n"
                    "Model: custom-review-engine\n"
                    "Head: 1234abc (short SHA)\n"
                    "Verdict: PASS would be wrong here\n"
                    "PR number: <number>\n"
                    "Review role: the wrapper owns this value"
                ),
            ),
            execution(
                "claude",
                verdict="FINDINGS",
                body="One explanatory finding.",
                findings=(
                    bridge.ReviewFinding(
                        "LOW",
                        "Head: 1234abc (short SHA)",
                        "Verdict: PASS would be wrong here\nPR number: <number>",
                    ),
                ),
            ),
        )
        for result in cases:
            with self.subTest(verdict=result.result.verdict):
                _posted, github, _repository = self.run_bridge(
                    ("claude",), {"claude": result}
                )
                comment = github.comments[0]
                self.assertIn("Head: 1234abc (short SHA)", comment)
                self.assertIn("Verdict: PASS would be wrong here", comment)

    def test_genuine_conflicting_metadata_claims_are_rejected(self) -> None:
        cases = (
            execution("claude", body="PR: #105\n\nSubstantive review."),
            execution(
                "claude", body=f"Head SHA: {MOVED_HEAD}\n\nSubstantive review."
            ),
            execution("claude", body="Verdict: FINDINGS\n\nSubstantive review."),
            execution(
                "claude",
                body=(
                    "Review role: additional independent review evidence\n\n"
                    "Substantive review."
                ),
            ),
            execution(
                "claude",
                verdict="FINDINGS",
                body="One finding.",
                findings=(
                    bridge.ReviewFinding("LOW", "PR: #105", "Substantive detail."),
                ),
            ),
        )
        for result in cases:
            with self.subTest(body=result.result.body_markdown):
                self.assert_review_rejected(
                    ("claude",), {"claude": result}, "conflicts"
                )

    def test_conflicting_provider_claim_spellings_are_rejected(self) -> None:
        cases = (
            ("claude", "Provider: Grok"),
            ("grok", "Reviewer: Claude"),
            ("claude", "## External exact-head review — Grok"),
            ("claude", "## External exact-head review : Grok"),
            ("claude", "## External exact‑head review – Grok"),
            ("claude", "> ## External exact-head review — Grok"),
            ("claude", "External exact-head review — Grok\n==="),
            ("claude", "**External exact-head review — Grok**"),
            ("claude", "<h1>External exact-head review — Grok</h1>"),
            (
                "claude",
                '<h4 data-review="external">External exact-head review — Grok</h4>',
            ),
            ("claude", "<h6>External exact-head review — Grok</h6>"),
            ("claude", "<strong>External exact-head review — Grok</strong>"),
            ("claude", "<b>External exact-head review — Grok</b>"),
            ("claude", "<strong>Provider: Grok</strong>"),
            ("claude", "<b>Reviewer: Grok</b>"),
            ("claude", "<h6>Model: Grok Build</h6>"),
            ("claude", "1. Provider: Grok"),
            ("claude", "- Provider: Grok"),
        )
        for provider, claim in cases:
            with self.subTest(provider=provider, claim=claim.splitlines()[0]):
                self.assert_review_rejected(
                    (provider,),
                    {
                        provider: execution(
                            provider,
                            body=f"{claim}\n\nSubstantive review.",
                        )
                    },
                    "identity conflicts",
                )

    def test_fenced_markdown_examples_are_not_live_metadata_claims(self) -> None:
        body = (
            "A quoted-format example follows.\n\n"
            "```text\n"
            "Provider: Grok\n"
            "## External exact-head review — Grok\n"
            "<h6>Provider: Grok</h6>\n"
            "<strong>Reviewer: Grok</strong>\n"
            "```\n\n"
            "The example is not a live identity claim."
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",), {"claude": execution("claude", body=body)}
        )
        self.assertIn("Provider: Grok", github.comments[0])
        self.assertIn("## External exact-head review — Grok", github.comments[0])
        self.assertIn("<h6>Provider: Grok</h6>", github.comments[0])
        self.assertIn("<strong>Reviewer: Grok</strong>", github.comments[0])

    def test_structured_provider_and_reviewer_conflicts_post_nothing(self) -> None:
        for field in ("provider", "reviewer"):
            with self.subTest(field=field):
                contract = {
                    "pr_number": PR_NUMBER,
                    "head_sha": HEAD,
                    "verdict": "PASS",
                    "body_markdown": "No material findings.",
                    "findings": [],
                    field: "Grok",
                }
                invalid = bridge.ProviderExecution(
                    result=bridge.review_result_from_contract(contract),
                    cli_version="claude 2.1.234",
                    model_metadata="claude-opus-4-6",
                )
                self.assert_review_rejected(
                    ("claude",), {"claude": invalid}, "identity conflicts"
                )

    def test_verdict_and_findings_must_be_consistent(self) -> None:
        cases = (
            (
                "findings verdict without findings",
                execution(
                    "grok",
                    verdict="FINDINGS",
                    body="Starting an independent exact-head review.",
                    findings=(),
                ),
                "FINDINGS without structured findings",
            ),
            (
                "pass verdict with findings",
                execution(
                    "claude",
                    findings=(
                        bridge.ReviewFinding("LOW", "Unexpected finding", "Detail."),
                    ),
                ),
                "PASS with findings",
            ),
        )
        for label, result, error in cases:
            with self.subTest(case=label):
                provider = "grok" if result.requested_model else "claude"
                self.assert_review_rejected(
                    (provider,), {provider: result}, error
                )

    def test_non_final_review_output_is_rejected_without_retry(self) -> None:
        cases = (
            (
                "The exact-head review has not produced final evidence.",
                "  REVIEW -- in progress! ",
                "Results will follow.",
            ),
            (
                "Placeholder while the exact-head review is completed.",
                "Awaiting completion",
                "The provider has not finished.",
            ),
            (
                "The review request is being processed from the detached head.",
                "Pending result",
                "Substantive findings will follow.",
            ),
            (
                "No final evidence is available.",
                "Placeholder",
                "Awaiting review completion.",
            ),
        )
        for body, title, detail in cases:
            with self.subTest(body=body):
                invalid = execution(
                    "grok",
                    verdict="FINDINGS",
                    body=body,
                    findings=(bridge.ReviewFinding("LOW", title, detail),),
                )
                _github, _repository, adapters = self.assert_review_rejected(
                    ("grok",), {"grok": invalid}, "non-final review output"
                )
                self.assertEqual(len(adapters["grok"].prompts), 1)

    def test_legitimate_future_work_finding_is_not_a_placeholder(self) -> None:
        github = FakeGitHub([metadata(), metadata()])
        legitimate = execution(
            "grok",
            verdict="FINDINGS",
            body="The implementation is complete; one bounded hardening remains.",
            findings=(
                bridge.ReviewFinding(
                    "LOW",
                    "Future cache-key hardening",
                    "A future change should include the platform in the cache key.",
                ),
            ),
        )
        posted = bridge.ReviewBridge(
            github,
            FakeRepository(),
            {"grok": FakeAdapter(legitimate)},
            emit=lambda _message: None,
        ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(len(posted), 1)
        self.assertEqual(len(github.comments), 1)

    def test_dirty_worktree_after_valid_result_blocks_posting(self) -> None:
        github = FakeGitHub([metadata()])
        repository = FakeRepository(clean_error_for="Claude")
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "modified the detached review worktree"
        ):
            bridge.ReviewBridge(
                github,
                repository,
                {"claude": FakeAdapter(execution("claude"))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(repository.clean_checks, ["Claude"])
        self.assertEqual(github.comments, [])
        self.assertTrue(repository.cleaned)

    def test_all_mode_dirty_grok_worktree_blocks_partial_posting(self) -> None:
        github = FakeGitHub([metadata()])
        repository = FakeRepository(clean_error_for="Grok")
        claude = FakeAdapter(execution("claude"))
        grok = FakeAdapter(execution("grok"))
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "modified the detached review worktree"
        ):
            bridge.ReviewBridge(
                github,
                repository,
                {"claude": claude, "grok": grok},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude", "grok"), "Review.")
        self.assertEqual(repository.clean_checks, ["Claude", "Grok"])
        self.assertEqual(len(claude.prompts), 1)
        self.assertEqual(len(grok.prompts), 1)
        self.assertEqual(github.comments, [])
        self.assertTrue(repository.cleaned)

    def test_cleanup_failure_after_valid_result_blocks_posting(self) -> None:
        class CleanupFailureRepository(bridge.GitRepository):
            def ensure_commit(
                self, sha: str, *, pr_number: int | None = None
            ) -> None:
                return None

            def base_to_head_diff(self, base_sha: str, head_sha: str) -> str:
                return "diff --git a/tool.py b/tool.py\n"

            def validate_worktree_symlinks(self, worktree: Path) -> None:
                return None

            def assert_clean(self, worktree: Path, provider_name: str) -> None:
                return None

        runner = QueueRunner(
            [
                completed(),
                completed(returncode=1, stderr="synthetic cleanup failure"),
            ]
        )
        with tempfile.TemporaryDirectory() as parent:
            repository = CleanupFailureRepository(
                runner, Path("/repository"), temporary_parent=Path(parent)
            )
            github = FakeGitHub([metadata()])
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError,
                "detached review worktree cleanup failed",
            ):
                bridge.ReviewBridge(
                    github,
                    repository,
                    {"claude": FakeAdapter(execution("claude"))},
                    emit=lambda _message: None,
                ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_symlink_validation_failure_starts_no_provider_and_posts_nothing(self) -> None:
        github = FakeGitHub([metadata()])
        repository = FakeRepository(
            bridge.ReviewBridgeError("repository symlink escapes detached worktree")
        )
        adapter = FakeAdapter(execution("claude"))
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "symlink escapes"):
            bridge.ReviewBridge(
                github,
                repository,
                {"claude": adapter},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(adapter.prompts, [])
        self.assertEqual(github.comments, [])
        self.assertEqual(repository.symlink_checks, 1)
        self.assertTrue(repository.cleaned)

    def test_contract_enforces_well_formed_consistent_findings(self) -> None:
        base_contract: dict[str, object] = {
            "pr_number": PR_NUMBER,
            "head_sha": HEAD,
            "body_markdown": "Substantive review.",
        }
        passed = bridge.review_result_from_contract(
            dict(base_contract, verdict="PASS", findings=[])
        )
        self.assertEqual(passed.findings, ())
        one_finding = [
            {
                "severity": "HIGH",
                "title": "Credential boundary",
                "detail": "The boundary is not enforced.",
            }
        ]
        found = bridge.review_result_from_contract(
            dict(base_contract, verdict="FINDINGS", findings=one_finding)
        )
        self.assertEqual(found.findings[0].severity, "HIGH")
        invalid_cases = (
            ({"verdict": "PASS"}, "malformed findings"),
            (
                {"verdict": "PASS", "findings": [{"severity": "MEDIUM"}]},
                "empty title",
            ),
            ({"verdict": "FINDINGS", "findings": []}, "contained no findings"),
            ({"verdict": "PASS", "findings": one_finding}, "PASS.*findings"),
            (
                {
                    "verdict": "FINDINGS",
                    "findings": [
                        {
                            "severity": "URGENT",
                            "title": "Bad severity",
                            "detail": "Not in the contract enum.",
                        }
                    ],
                },
                "malformed severity",
            ),
        )
        for updates, error in invalid_cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(bridge.ReviewBridgeError, error):
                    bridge.review_result_from_contract(
                        dict(base_contract, **updates)
                    )

    def test_wrapper_prompt_contains_exact_diff_and_findings_invariants(self) -> None:
        github = FakeGitHub([metadata(), metadata()])
        adapter = FakeAdapter(execution("claude"))
        bridge.ReviewBridge(
            github, FakeRepository(), {"claude": adapter}, emit=lambda _message: None
        ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertIn("diff --git a/tool.py b/tool.py", adapter.prompts[0])
        self.assertIn("PASS requires an empty `findings` array", adapter.prompts[0])


class GrokAuthSandboxTests(unittest.TestCase):
    def test_regular_auth_file_uses_canonical_parent_directory_grant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credentials = root / "credentials"
            credentials.mkdir()
            auth_file = credentials / "auth.json"
            auth_file.write_text("synthetic-only\n", encoding="utf-8")
            resolved = bridge.resolve_grok_auth_file(
                {"GROK_AUTH_PATH": str(auth_file)}
            )
            auth_directory = bridge.validate_grok_auth_directory(
                resolved,
                {"HOME": str(root / "home")},
                root / "review-worktree",
            )
            sandbox = bridge.write_grok_sandbox_profile(
                root / "ephemeral-grok-home", resolved, auth_directory
            )
            payload = tomllib.loads(sandbox.config_file.read_text(encoding="utf-8"))
            profile = payload["profiles"][bridge.GROK_SANDBOX_PROFILE]
            self.assertEqual(resolved, auth_file.resolve())
            self.assertEqual(sandbox.auth_file, auth_file.resolve())
            self.assertEqual(sandbox.read_only_directory, credentials.resolve())
            self.assertEqual(
                profile,
                {"extends": "strict", "read_only": [str(credentials.resolve())]},
            )
            self.assertNotIn(str(root.resolve()), profile["read_only"])
            self.assertNotIn(str(auth_file.resolve()), profile["read_only"])

    def test_normal_home_grok_auth_directory_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            auth_directory = home / ".grok"
            auth_directory.mkdir(parents=True)
            auth_file = auth_directory / "auth.json"
            auth_file.write_text("synthetic-only\n", encoding="utf-8")
            self.assertEqual(
                bridge.validate_grok_auth_directory(
                    auth_file.resolve(),
                    {"HOME": str(home)},
                    root / "review-worktree",
                ),
                auth_directory.resolve(),
            )

    def test_broad_auth_directories_are_rejected(self) -> None:
        cases = (
            (Path("/auth.json"), {"HOME": "/home/reviewer"}),
            (Path("/tmp/auth.json"), {"HOME": "/home/reviewer"}),
            (Path("/var/tmp/auth.json"), {"HOME": "/home/reviewer"}),
            (Path("/etc/auth.json"), {"HOME": "/home/reviewer"}),
            (Path("/home/reviewer/auth.json"), {"HOME": "/home/reviewer"}),
        )
        for auth_file, source in cases:
            with self.subTest(parent=auth_file.parent):
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "bounded credential directory"
                ):
                    bridge.validate_grok_auth_directory(
                        auth_file, source, Path("/review/worktree")
                    )

    def test_auth_directory_and_worktree_must_not_overlap(self) -> None:
        cases = (
            (Path("/review/auth.json"), Path("/review/worktree")),
            (Path("/review/worktree/credentials/auth.json"), Path("/review/worktree")),
        )
        for auth_file, worktree in cases:
            with self.subTest(auth_file=auth_file):
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "separate from the review worktree"
                ):
                    bridge.validate_grok_auth_directory(
                        auth_file, {"HOME": "/home/reviewer"}, worktree
                    )

    def test_sandbox_profile_filesystem_error_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked_home = root / "not-a-directory"
            blocked_home.write_text("synthetic\n", encoding="utf-8")
            credentials = root / "credentials"
            credentials.mkdir()
            auth_file = credentials / "auth.json"
            auth_file.write_text("synthetic-only\n", encoding="utf-8")
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError,
                "could not create the temporary Grok sandbox profile",
            ):
                bridge.write_grok_sandbox_profile(
                    blocked_home, auth_file, credentials
                )

    def test_missing_or_broken_auth_file_fails_closed(self) -> None:
        for broken_symlink in (False, True):
            with self.subTest(broken_symlink=broken_symlink):
                with tempfile.TemporaryDirectory() as directory:
                    auth_file = Path(directory) / "auth.json"
                    if broken_symlink:
                        auth_file.symlink_to("missing-target")
                    with self.assertRaisesRegex(
                        bridge.ReviewBridgeError, "missing or unresolvable"
                    ):
                        bridge.resolve_grok_auth_file(
                            {"GROK_AUTH_PATH": str(auth_file)}
                        )

    def test_auth_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth_directory = Path(directory) / "auth.json"
            auth_directory.mkdir()
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError, "not a regular file"
            ):
                bridge.resolve_grok_auth_file(
                    {"GROK_AUTH_PATH": str(auth_directory)}
                )

    def test_resolvable_auth_symlink_uses_canonical_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "real-auth.json"
            target.write_text("synthetic-only\n", encoding="utf-8")
            link = root / "auth.json"
            link.symlink_to(target.name)
            self.assertEqual(
                bridge.resolve_grok_auth_file({"GROK_AUTH_PATH": str(link)}),
                target.resolve(),
            )


class ProviderExecutableResolutionTests(unittest.TestCase):
    @staticmethod
    def make_executable(directory: Path, name: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / name
        executable.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        executable.chmod(0o700)
        return executable

    def test_unsafe_path_entries_cannot_select_worktree_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            worktree = root / "checkout"
            trusted = root / "trusted-bin"
            fake = self.make_executable(worktree, "claude")
            real = self.make_executable(trusted, "claude")
            for unsafe in (".", "", "relative-bin"):
                with self.subTest(unsafe=repr(unsafe)):
                    source_path = os.pathsep.join((unsafe, str(trusted)))
                    resolved, safe_path = bridge.resolve_provider_executable(
                        bridge.PROVIDER_SPECS["claude"],
                        {"PATH": source_path},
                        review_worktree=worktree,
                    )
                    self.assertEqual(resolved, real.resolve())
                    self.assertEqual(safe_path, str(trusted))
                    self.assertNotEqual(resolved, fake.resolve())

    def test_absolute_worktree_provider_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory) / "checkout"
            self.make_executable(worktree, "claude")
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError, "inside the review worktree"
            ):
                bridge.resolve_provider_executable(
                    bridge.PROVIDER_SPECS["claude"],
                    {"PATH": str(worktree)},
                    review_worktree=worktree,
                )

    def test_missing_safe_provider_fails_before_any_provider_call(self) -> None:
        for provider in ("claude", "grok"):
            with self.subTest(provider=provider):
                runner = QueueRunner([])
                adapter = bridge.ProviderAdapter(
                    bridge.PROVIDER_SPECS[provider],
                    runner,
                    source_environment={"PATH": f".{os.pathsep}{os.pathsep}relative"},
                )
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "executable is unavailable"
                ):
                    adapter.run(Path("/detached"), "Review.")
                self.assertEqual(runner.calls, [])

    def test_providers_use_one_trusted_absolute_executable(self) -> None:
        cases = (
            ("claude", "2.1.234 (Claude Code)\n", CLAUDE_HELP, "claude-test", 2),
            ("grok", "grok 1.0.5\n", GROK_HELP, "grok-4.6", 3),
        )
        for provider, version, help_output, model, first_worktree_call in cases:
            with self.subTest(provider=provider):
                payload = {
                    "structured_output": {
                        "pr_number": PR_NUMBER,
                        "head_sha": HEAD,
                        "verdict": "PASS",
                        "body_markdown": "No findings.",
                        "findings": [],
                    },
                    "model": model,
                }
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    worktree = root / "checkout"
                    worktree.mkdir()
                    trusted = root / "trusted-bin"
                    executable = self.make_executable(trusted, provider).resolve()
                    source_environment = {
                        "PATH": (
                            f".{os.pathsep}{os.pathsep}relative{os.pathsep}{trusted}"
                        )
                    }
                    responses = [
                        completed(stdout=version),
                        completed(stdout=help_output),
                    ]
                    if provider == "grok":
                        credentials = root / "credentials"
                        credentials.mkdir()
                        auth_file = credentials / "auth.json"
                        auth_file.write_text("synthetic-only\n", encoding="utf-8")
                        source_environment["GROK_AUTH_PATH"] = str(auth_file)
                        responses.extend(
                            [completed(stdout=GROK_MODELS), completed(stdout="{}")]
                        )
                    responses.append(completed(stdout=bridge.json.dumps(payload)))
                    runner = QueueRunner(responses)
                    result = bridge.ProviderAdapter(
                        bridge.PROVIDER_SPECS[provider],
                        runner,
                        source_environment=source_environment,
                    ).run(worktree, "Review.")
                    self.assertEqual(
                        [call["args"][0] for call in runner.calls],
                        [str(executable)] * len(runner.calls),
                    )
                    for index, call in enumerate(runner.calls):
                        expected_cwd = worktree if index >= first_worktree_call else None
                        if expected_cwd is None:
                            self.assertNotEqual(call["cwd"], worktree)
                        else:
                            self.assertEqual(call["cwd"], expected_cwd)
                        self.assertEqual(call["env"]["PATH"], str(trusted))
                    if provider == "grok":
                        self.assertEqual(result.requested_model, "grok-4.6")
                        self.assertEqual(result.model_metadata, "grok-4.6")
                    else:
                        self.assertIsNone(result.requested_model)


class ProviderAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        executable_patch = mock.patch.object(
            bridge.shutil, "which", return_value="/usr/bin/true"
        )
        executable_patch.start()
        self.addCleanup(executable_patch.stop)

    def test_provider_child_environment_scrubs_github_credentials(self) -> None:
        provider_payload = {
            "structured_output": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No findings.",
                "findings": [],
            },
            "model": "claude-test",
        }
        runner = QueueRunner(
            [
                completed(stdout="2.1.0 (Claude Code)\n"),
                completed(stdout=CLAUDE_HELP),
                completed(stdout=bridge.json.dumps(provider_payload)),
            ]
        )
        adapter = bridge.ProviderAdapter(
            bridge.PROVIDER_SPECS["claude"],
            runner,
            source_environment={
                "PATH": "/usr/bin",
                "GH_TOKEN": "ghp_secret-token",
                "GITHUB_TOKEN": "github-secret",
                "GH_CONFIG_DIR": "/real/gh/config",
                "ANTHROPIC_API_KEY": "anthropic-local-auth",
            },
        )
        adapter.run(Path("/detached"), "Review.")
        for call in runner.calls:
            environment = call["env"]
            self.assertIsInstance(environment, dict)
            assert isinstance(environment, dict)
            self.assertNotIn("GH_TOKEN", environment)
            self.assertNotIn("GITHUB_TOKEN", environment)
            self.assertNotEqual(environment["GH_CONFIG_DIR"], "/real/gh/config")
            self.assertEqual(environment["ANTHROPIC_API_KEY"], "anthropic-local-auth")
            self.assertEqual(environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")
        provider_command = runner.calls[-1]["args"]
        assert isinstance(provider_command, tuple)
        self.assertEqual(
            provider_command[provider_command.index("--model") + 1], "opus"
        )
        self.assertFalse(
            any(
                argument.startswith("claude-opus-")
                for argument in provider_command
            )
        )
        self.assertEqual(
            provider_command[provider_command.index("--tools") + 1], "Read"
        )
        self.assertNotIn("Grep", provider_command)
        self.assertNotIn("Glob", provider_command)
        denied = set(
            provider_command[
                provider_command.index("--disallowedTools") + 1
            ].split(",")
        )
        self.assertEqual(
            denied,
            {
                "Bash",
                "Edit",
                "Write",
                "NotebookEdit",
                "WebFetch",
                "WebSearch",
                "Agent",
            },
        )
        self.assertIn(
            "Read(//detached/**)",
            provider_command[provider_command.index("--allowedTools") + 1],
        )
        self.assertEqual(
            provider_command[provider_command.index("--setting-sources") + 1],
            "user",
        )
        self.assertIn("--strict-mcp-config", provider_command)
        settings_file = Path(
            provider_command[provider_command.index("--settings") + 1]
        )
        mcp_config_file = Path(
            provider_command[provider_command.index("--mcp-config") + 1]
        )
        self.assertFalse(settings_file.is_relative_to(Path("/detached")))
        self.assertFalse(mcp_config_file.is_relative_to(Path("/detached")))
        self.assertEqual(
            runner.claude_settings_payloads,
            [{"disableAllHooks": True, "autoMemoryEnabled": False}],
        )
        self.assertEqual(runner.claude_mcp_payloads, [{"mcpServers": {}}])
        self.assertEqual(runner.claude_config_modes, [0o600, 0o600])
        self.assertNotIn("--bare", provider_command)
        self.assertFalse(settings_file.exists())
        self.assertFalse(mcp_config_file.exists())

    def test_claude_isolation_files_are_cleaned_after_provider_failure(self) -> None:
        runner = QueueRunner(
            [
                completed(stdout="2.1.234 (Claude Code)\n"),
                completed(stdout=CLAUDE_HELP),
                completed(returncode=1, stderr="synthetic provider failure\n"),
            ]
        )
        adapter = bridge.ProviderAdapter(
            bridge.PROVIDER_SPECS["claude"],
            runner,
            source_environment={"PATH": "/usr/bin"},
        )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "provider failed"):
            adapter.run(Path("/detached"), "Review.")
        self.assertEqual(len(runner.claude_config_paths), 2)
        self.assertTrue(all(not path.exists() for path in runner.claude_config_paths))

    def test_claude_isolation_setup_failure_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            blocked_root = Path(directory) / "not-a-directory"
            blocked_root.write_text("synthetic\n", encoding="utf-8")
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError,
                "could not create temporary Claude isolation configuration",
            ):
                bridge.write_claude_isolation_config(blocked_root)

    def test_claude_isolation_config_inside_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            settings = worktree / "settings.json"
            mcp = worktree / "mcp.json"
            settings.write_text("{}\n", encoding="utf-8")
            mcp.write_text('{"mcpServers":{}}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError,
                "must be outside the review worktree",
            ):
                bridge.ProviderAdapter._claude_command(
                    Path("/usr/bin/true"),
                    worktree,
                    bridge.ClaudeIsolationConfig(settings, mcp),
                )

    def test_missing_grok_auth_fails_before_any_cli_execution(self) -> None:
        runner = QueueRunner([])
        adapter = bridge.ProviderAdapter(
            bridge.PROVIDER_SPECS["grok"],
            runner,
            source_environment={
                "PATH": "/usr/bin",
                "GROK_AUTH_PATH": "/missing/synthetic-grok-auth.json",
            },
        )
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "missing or unresolvable"
        ):
            adapter.run(Path("/detached"), "Review.")
        self.assertEqual(runner.calls, [])

    def test_home_level_grok_auth_fails_before_any_cli_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            auth_file = home / "auth.json"
            auth_file.write_text("synthetic-only\n", encoding="utf-8")
            runner = QueueRunner([])
            adapter = bridge.ProviderAdapter(
                bridge.PROVIDER_SPECS["grok"],
                runner,
                source_environment={
                    "PATH": "/usr/bin",
                    "HOME": str(home),
                    "GROK_AUTH_PATH": str(auth_file),
                },
            )
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError, "bounded credential directory"
            ):
                adapter.run(Path("/detached"), "Review.")
        self.assertEqual(runner.calls, [])

    def test_grok_sandbox_warnings_fail_closed_at_each_phase(self) -> None:
        warning = "warning: sandbox could not be applied: synthetic"
        cases = (
            ("inspection", [completed(stdout="{}", stderr=warning)]),
            (
                "review",
                [completed(stdout="{}"), completed(stderr=warning)],
            ),
        )
        for phase, phase_responses in cases:
            with self.subTest(phase=phase):
                with tempfile.TemporaryDirectory() as directory:
                    auth_file = Path(directory) / "auth.json"
                    auth_file.write_text("synthetic-only\n", encoding="utf-8")
                    runner = QueueRunner(
                        [
                            completed(stdout="grok 1.0.5\n"),
                            completed(stdout=GROK_HELP),
                            completed(stdout=GROK_MODELS),
                            *phase_responses,
                        ]
                    )
                    adapter = bridge.ProviderAdapter(
                        bridge.PROVIDER_SPECS["grok"],
                        runner,
                        source_environment={
                            "PATH": "/usr/bin",
                            "GROK_AUTH_PATH": str(auth_file),
                        },
                    )
                    with self.assertRaisesRegex(
                        bridge.ReviewBridgeError,
                        "could not enforce the custom Grok sandbox",
                    ):
                        adapter.run(Path("/detached"), "Review.")
                environment = runner.calls[-1]["env"]
                assert isinstance(environment, dict)
                self.assertFalse(Path(environment["GROK_HOME"]).exists())

    def test_grok_rejects_discovered_mcp_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth_file = Path(directory) / "auth.json"
            auth_file.write_text("synthetic-only\n", encoding="utf-8")
            runner = QueueRunner(
                [
                    completed(stdout="grok 1.0.5\n"),
                    completed(stdout=GROK_HELP),
                    completed(stdout=GROK_MODELS),
                    completed(stdout='{"mcpServers":[{"name":"unsafe"}]}'),
                ]
            )
            adapter = bridge.ProviderAdapter(
                bridge.PROVIDER_SPECS["grok"],
                runner,
                source_environment={
                    "PATH": "/usr/bin",
                    "GROK_AUTH_PATH": str(auth_file),
                },
            )
            with self.assertRaisesRegex(
                bridge.ReviewBridgeError, "active review customizations"
            ):
                adapter.run(Path("/detached"), "Review.")
        self.assertEqual(len(runner.calls), 4)
        environment = runner.calls[-1]["env"]
        assert isinstance(environment, dict)
        self.assertFalse(Path(environment["GROK_HOME"]).exists())

    def test_grok_uses_ephemeral_home_with_existing_auth_path(self) -> None:
        provider_payload = {
            "structured_output": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No findings.",
                "findings": [],
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            original_grok_home = Path(directory) / "user-grok"
            original_grok_home.mkdir()
            auth_file = original_grok_home / "auth.json"
            auth_file.write_text("synthetic-only\n", encoding="utf-8")
            provider_payload["structured_output"]["body_markdown"] = (
                f"Auth path must not publish: {auth_file.resolve()}"
            )
            runner = QueueRunner(
                [
                    completed(stdout="grok 1.0.5\n"),
                    completed(stdout=GROK_HELP),
                    completed(stdout=GROK_MODELS),
                    completed(stdout="{}"),
                    completed(stdout=bridge.json.dumps(provider_payload)),
                ]
            )
            adapter = bridge.ProviderAdapter(
                bridge.PROVIDER_SPECS["grok"],
                runner,
                source_environment={
                    "PATH": "/usr/bin",
                    "HOME": "/user/home",
                    "GROK_HOME": str(original_grok_home),
                    "GH_TOKEN": "ghp_synthetic-secret",
                    "GITHUB_TOKEN": "synthetic-secret",
                    "GH_ENTERPRISE_TOKEN": "synthetic-secret",
                    "GITHUB_ENTERPRISE_TOKEN": "synthetic-secret",
                    "GH_CONFIG_DIR": "/real/gh/config",
                },
            )
            provider_execution = adapter.run(
                Path("/detached"), "Private review prompt."
            )
        for call in runner.calls:
            environment = call["env"]
            assert isinstance(environment, dict)
            self.assertNotEqual(environment["GROK_HOME"], str(original_grok_home))
            self.assertEqual(environment["GROK_AUTH_PATH"], str(auth_file.resolve()))
            self.assertEqual(environment["GROK_SESSION_REGISTRY"], "0")
            self.assertEqual(environment["GROK_SESSION_SEARCH"], "0")
            for variable in bridge.GITHUB_SECRET_VARIABLES:
                self.assertNotIn(variable, environment)
            self.assertNotEqual(environment["GH_CONFIG_DIR"], "/real/gh/config")
        provider_command = runner.calls[-1]["args"]
        assert isinstance(provider_command, tuple)
        inspect_command = runner.calls[-2]["args"]
        assert isinstance(inspect_command, tuple)
        inspect_environment = runner.calls[-2]["env"]
        provider_environment = runner.calls[-1]["env"]
        assert isinstance(inspect_environment, dict)
        assert isinstance(provider_environment, dict)
        self.assertEqual(
            inspect_environment["GROK_HOME"], provider_environment["GROK_HOME"]
        )
        self.assertEqual(
            inspect_environment["GROK_AUTH_PATH"],
            provider_environment["GROK_AUTH_PATH"],
        )
        for command in (inspect_command, provider_command):
            self.assertEqual(command[command.index("-m") + 1], "grok-4.6")
            self.assertEqual(
                command[command.index("--sandbox") + 1],
                bridge.GROK_SANDBOX_PROFILE,
            )
            self.assertIn("Read(./**)", command)
            self.assertIn("Grep(./**)", command)
            self.assertNotIn("Read", command)
            self.assertNotIn("Grep", command)
            self.assertIn(f"Read({auth_file.resolve().as_posix()})", command)
            self.assertIn(f"Grep({auth_file.resolve().as_posix()})", command)
            self.assertIn(
                f"Read({original_grok_home.resolve().as_posix()}/**)", command
            )
            self.assertIn(
                f"Grep({original_grok_home.resolve().as_posix()}/**)", command
            )
        self.assertEqual(
            provider_command[provider_command.index("--tools") + 1], "Read,Grep"
        )
        self.assertIn("Bash", provider_command)
        self.assertFalse(any("Bash(git" in argument for argument in provider_command))
        profile_payload = tomllib.loads(runner.grok_sandbox_profiles[-1])
        self.assertEqual(
            profile_payload["profiles"][bridge.GROK_SANDBOX_PROFILE],
            {
                "extends": "strict",
                "read_only": [str(original_grok_home.resolve())],
            },
        )
        environment = runner.calls[-1]["env"]
        assert isinstance(environment, dict)
        self.assertFalse(Path(environment["GROK_HOME"]).exists())
        self.assertNotIn(
            str(auth_file.resolve()), provider_execution.result.body_markdown
        )
        self.assertIn("[REDACTED]", provider_execution.result.body_markdown)
        self.assertEqual(provider_execution.requested_model, "grok-4.6")

    def test_grok_build_alias_is_preferred_and_explicit_when_available(self) -> None:
        listing = """Default model: grok-4.7
Available models:
  * grok-4.7 (default)
  - grok-build
"""
        selected = bridge.select_grok_request_model(listing)
        self.assertEqual(selected, "grok-build")
        sandbox = bridge.GrokSandboxProfile(
            name=bridge.GROK_SANDBOX_PROFILE,
            auth_file=Path("/credentials/auth.json"),
            read_only_directory=Path("/credentials"),
            config_file=Path("/ephemeral/grok-home/sandbox.toml"),
        )
        command = bridge.ProviderAdapter._grok_command(
            Path("/usr/bin/true"),
            Path("/detached"),
            Path("/prompt.md"),
            selected,
            sandbox,
        )
        self.assertEqual(command[command.index("-m") + 1], "grok-build")

    def test_grok_advertised_default_is_selected_when_build_alias_is_absent(self) -> None:
        self.assertEqual(
            bridge.select_grok_request_model(GROK_MODELS),
            "grok-4.6",
        )

    def test_grok_model_listing_requires_available_default(self) -> None:
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "omitted a default"):
            bridge.select_grok_request_model("Available models:\n  - grok-4.6\n")
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "absent from available"):
            bridge.select_grok_request_model(
                "Default model: grok-4.6\nAvailable models:\n  - grok-4.5\n"
            )

    def test_provider_model_selector_capability_is_required(self) -> None:
        for provider, help_output in (("claude", CLAUDE_HELP), ("grok", GROK_HELP)):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "explicit model selection"
                ):
                    bridge.validate_cli_capabilities(
                        provider, help_output.replace("--model", "")
                    )

    def test_claude_capability_check_requires_emitted_flag_spellings(self) -> None:
        for emitted, alias in (
            ("--allowedTools", "--allowed-tools"),
            ("--disallowedTools", "--disallowed-tools"),
        ):
            with self.subTest(emitted=emitted):
                alias_only_help = CLAUDE_HELP.replace(emitted, alias)
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "lacks required safety capabilities"
                ):
                    bridge.validate_cli_capabilities("claude", alias_only_help)

    def test_claude_isolation_capabilities_block_before_provider_call(self) -> None:
        for option in (
            "--setting-sources",
            "--settings",
            "--strict-mcp-config",
            "--mcp-config",
        ):
            with self.subTest(option=option):
                help_without_option = " ".join(
                    token for token in CLAUDE_HELP.split() if token != option
                )
                runner = QueueRunner(
                    [
                        completed(stdout="2.1.234 (Claude Code)\n"),
                        completed(stdout=help_without_option),
                    ]
                )
                adapter = bridge.ProviderAdapter(
                    bridge.PROVIDER_SPECS["claude"],
                    runner,
                    source_environment={"PATH": "/usr/bin"},
                )
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "lacks required safety capabilities"
                ):
                    adapter.run(Path("/detached"), "Review.")
                self.assertEqual(len(runner.calls), 2)
                self.assertTrue(
                    all(not path.exists() for path in runner.claude_config_paths)
                )

    def test_cli_capability_checks_reject_prefix_collisions(self) -> None:
        cases = (
            ("grok", GROK_HELP.replace("--allow", "--allowedTools")),
            ("claude", CLAUDE_HELP.replace("--model", "--model-name")),
        )
        for provider, help_output in cases:
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(
                    bridge.ReviewBridgeError, "lacks required safety capabilities"
                ):
                    bridge.validate_cli_capabilities(provider, help_output)

    def test_missing_cli_safety_capability_fails_before_provider_execution(self) -> None:
        runner = QueueRunner(
            [
                completed(stdout="2.1.0 (Claude Code)\n"),
                completed(stdout="--json-schema --output-format"),
            ]
        )
        adapter = bridge.ProviderAdapter(
            bridge.PROVIDER_SPECS["claude"],
            runner,
            source_environment={"PATH": "/usr/bin"},
        )
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "lacks required safety capabilities"
        ):
            adapter.run(Path("/detached"), "Review.")
        self.assertEqual(len(runner.calls), 2)


class WorktreeSymlinkTests(unittest.TestCase):
    def test_no_symlinks_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: /outside/admin\n", encoding="utf-8")
            (root / "file.txt").write_text("regular\n", encoding="utf-8")
            bridge.validate_worktree_symlinks(root)

    def test_internal_symlink_targets_are_accepted(self) -> None:
        for is_directory in (False, True):
            with self.subTest(target_type="directory" if is_directory else "file"):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    target = root / "target"
                    if is_directory:
                        target.mkdir()
                        (target / "file.txt").write_text("inside\n", encoding="utf-8")
                    else:
                        target.write_text("inside\n", encoding="utf-8")
                    (root / "link").symlink_to(
                        target.name, target_is_directory=is_directory
                    )
                    bridge.validate_worktree_symlinks(root)

    def test_external_symlink_targets_are_rejected(self) -> None:
        for is_directory in (False, True):
            with self.subTest(target_type="directory" if is_directory else "file"):
                with tempfile.TemporaryDirectory() as directory:
                    parent = Path(directory)
                    root = parent / "checkout"
                    root.mkdir()
                    outside = parent / "outside"
                    if is_directory:
                        outside.mkdir()
                    else:
                        outside.write_text("synthetic\n", encoding="utf-8")
                    (root / "escape").symlink_to(
                        outside, target_is_directory=is_directory
                    )
                    with self.assertRaisesRegex(
                        bridge.ReviewBridgeError, "symlink escapes"
                    ):
                        bridge.validate_worktree_symlinks(root)

    def test_broken_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken").symlink_to("missing-target")
            with self.assertRaisesRegex(bridge.ReviewBridgeError, "broken or unresolvable"):
                bridge.validate_worktree_symlinks(root)

    def test_chained_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "checkout"
            root.mkdir()
            outside = parent / "outside.txt"
            outside.write_text("synthetic\n", encoding="utf-8")
            (root / "second").symlink_to(outside)
            (root / "first").symlink_to("second")
            with self.assertRaisesRegex(bridge.ReviewBridgeError, "symlink escapes"):
                bridge.validate_worktree_symlinks(root)


class WorktreeCleanupTests(unittest.TestCase):
    def test_wrapper_generates_exact_base_to_head_diff(self) -> None:
        runner = QueueRunner([completed(stdout="exact patch")])
        repository = bridge.GitRepository(runner, Path("/repo"))
        self.assertEqual(repository.base_to_head_diff(BASE, HEAD), "exact patch")
        self.assertEqual(
            runner.calls[0]["args"],
            (
                "git",
                "diff",
                "--no-ext-diff",
                "--no-color",
                "--binary",
                "--find-renames",
                f"{BASE}...{HEAD}",
                "--",
            ),
        )

    def test_detached_worktree_is_cleaned_on_success_and_failure(self) -> None:
        def use_worktree(repository: bridge.GitRepository, fail: bool) -> None:
            if fail:
                with self.assertRaisesRegex(RuntimeError, "provider failed"):
                    with repository.detached_worktree(PR_NUMBER, HEAD):
                        raise RuntimeError("provider failed")
            else:
                with repository.detached_worktree(PR_NUMBER, HEAD):
                    pass

        for fail in (False, True):
            with self.subTest(provider_failure=fail):
                runner = QueueRunner([completed(), completed()])
                with tempfile.TemporaryDirectory() as parent:
                    repository = bridge.GitRepository(
                        runner, Path("/repo"), temporary_parent=Path(parent)
                    )
                    use_worktree(repository, fail)
                commands = [call["args"] for call in runner.calls]
                self.assertEqual(
                    commands[0][:4], ("git", "worktree", "add", "--detach")
                )
                self.assertEqual(
                    commands[1][:4], ("git", "worktree", "remove", "--force")
                )


class DoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        executable_patch = mock.patch.object(
            bridge.shutil, "which", return_value="/usr/bin/true"
        )
        executable_patch.start()
        self.addCleanup(executable_patch.stop)

    def test_doctor_does_not_expose_secret_material(self) -> None:
        secret = "ghp_super_secret_value"
        runner = QueueRunner(
            [
                completed(stdout="git version 2.50.0\n"),
                completed(stdout="gh version 2.97.0\n"),
                completed(stderr=f"authenticated token: {secret}\n"),
                completed(stdout="/repository\n"),
                completed(stdout='{"nameWithOwner":"owner/repository"}'),
                completed(stdout="2.1.0 (Claude Code)\n"),
                completed(stdout=CLAUDE_HELP),
                completed(stdout=f'{{"loggedIn":true,"token":"{secret}"}}'),
                completed(stdout="grok 1.0.5\n"),
                completed(stdout="grok 1.0.5\n"),
                completed(stdout=GROK_HELP),
                completed(stdout=GROK_MODELS, stderr=secret),
            ]
        )
        healthy, lines = bridge.doctor(runner, Path("/repository"))
        self.assertTrue(healthy)
        output = "\n".join(lines)
        self.assertNotIn(secret, output)
        self.assertNotIn("super_secret", output)
        self.assertIn("OK   git: git version 2.50.0", output)
        self.assertIn("OK   gh: gh version 2.97.0", output)
        self.assertIn("GitHub authentication: authenticated", output)
        self.assertIn("Claude authentication: authenticated", output)
        self.assertIn("Grok authentication: authenticated model access", output)
        self.assertIn("Claude safety capabilities: compatible", output)
        self.assertIn("Grok safety capabilities: compatible", output)
        self.assertIn("Grok session controls: compatible", output)
        self.assertIn(
            "Grok review model selection: explicit `grok-4.6` request", output
        )

    def test_doctor_fails_for_incompatible_provider_cli(self) -> None:
        runner = QueueRunner(
            [
                completed(stdout="git version 2.50.0\n"),
                completed(stdout="gh version 2.97.0\n"),
                completed(),
                completed(stdout="/repository\n"),
                completed(stdout='{"nameWithOwner":"owner/repository"}'),
                completed(stdout="2.1.0 (Claude Code)\n"),
                completed(stdout="--json-schema --output-format"),
                completed(stdout='{"loggedIn":true}'),
                completed(stdout="grok 1.0.5\n"),
                completed(stdout="grok 1.0.5\n"),
                completed(stdout=GROK_HELP),
                completed(stdout=GROK_MODELS),
            ]
        )
        healthy, lines = bridge.doctor(runner, Path("/repository"))
        self.assertFalse(healthy)
        self.assertIn(
            "FAIL Claude safety capabilities: Claude CLI lacks required safety capabilities",
            "\n".join(lines),
        )


if __name__ == "__main__":
    unittest.main()

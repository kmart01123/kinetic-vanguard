from __future__ import annotations

import contextlib
from pathlib import Path
import subprocess
import tempfile
import unittest

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
    return bridge.ProviderExecution(
        result=bridge.ReviewResult(
            pr_number=pr_number,
            head_sha=head,
            verdict=verdict,
            body_markdown=body,
            findings=findings,
        ),
        cli_version=f"{provider} 1.0",
        model_metadata="grok-build" if provider == "grok" else "claude-model",
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
    def __init__(self, symlink_error: Exception | None = None) -> None:
        self.ensured: list[tuple[str, int | None]] = []
        self.cleaned = False
        self.clean_checks: list[str] = []
        self.symlink_checks = 0
        self.symlink_error = symlink_error

    def ensure_commit(self, sha: str, *, pr_number: int | None = None) -> None:
        self.ensured.append((sha, pr_number))

    def assert_clean(self, worktree: Path, provider_name: str) -> None:
        self.clean_checks.append(provider_name)

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

    def test_claude_exact_head_pass_posts_one_correct_comment(self) -> None:
        posted, github, repository = self.run_bridge(
            ("claude",), {"claude": execution("claude")}
        )
        self.assertEqual(len(posted), 1)
        self.assertIn("External exact-head review — Claude", github.comments[0])
        self.assertIn(f"`{HEAD}`", github.comments[0])
        self.assertIn("**PASS**", github.comments[0])
        self.assertTrue(repository.cleaned)

    def test_claude_findings_posts_findings(self) -> None:
        _posted, github, _repository = self.run_bridge(
            ("claude",),
            {"claude": execution("claude", verdict="FINDINGS", body="- Finding")},
        )
        self.assertIn("**FINDINGS**", github.comments[0])
        self.assertIn("- Finding", github.comments[0])

    def test_grok_exact_head_pass_uses_grok_identity(self) -> None:
        _posted, github, _repository = self.run_bridge(
            ("grok",), {"grok": execution("grok")}
        )
        self.assertIn("External exact-head review — Grok", github.comments[0])
        self.assertIn("additional independent review evidence", github.comments[0])
        self.assertNotIn("External exact-head review — Claude", github.comments[0])

    def test_grok_body_claiming_claude_is_rejected_without_post(self) -> None:
        github = FakeGitHub([metadata()])
        repository = FakeRepository()
        adapter = FakeAdapter(execution("grok", body="Reviewer: Claude\n\nLooks good."))
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "identity conflicts"):
            bridge.ReviewBridge(
                github, repository, {"grok": adapter}, emit=lambda _message: None
            ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(github.comments, [])
        self.assertTrue(repository.cleaned)

    def test_claude_body_claiming_grok_is_rejected_without_post(self) -> None:
        github = FakeGitHub([metadata()])
        repository = FakeRepository()
        adapter = FakeAdapter(execution("claude", body="Provider: Grok\n\nLooks good."))
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "identity conflicts"):
            bridge.ReviewBridge(
                github, repository, {"claude": adapter}, emit=lambda _message: None
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_wrong_pr_number_is_rejected(self) -> None:
        github = FakeGitHub([metadata()])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "returned PR #103"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"claude": FakeAdapter(execution("claude", pr_number=103))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_wrong_sha_is_rejected(self) -> None:
        github = FakeGitHub([metadata()])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "returned head"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"claude": FakeAdapter(execution("claude", head=MOVED_HEAD))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_malformed_verdict_is_rejected(self) -> None:
        github = FakeGitHub([metadata()])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "invalid verdict"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"claude": FakeAdapter(execution("claude", verdict="MAYBE"))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_malformed_provider_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "malformed JSON"):
            bridge.extract_contract("not json", "Claude")

    def test_grok_camel_case_structured_output_precedes_malformed_text(self) -> None:
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

    def test_live_grok_envelope_shape_allows_all_provider_validation(self) -> None:
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
            "text": '{"valid": true}\ntrailing data',
        }
        contract, model = bridge.extract_contract(
            bridge.json.dumps(envelope), "Grok"
        )
        grok_execution = bridge.ProviderExecution(
            result=bridge.review_result_from_contract(contract),
            cli_version="grok 1.0.5",
            model_metadata=model,
        )
        posted, github, _repository = self.run_bridge(
            ("claude", "grok"),
            {
                "claude": execution("claude"),
                "grok": grok_execution,
            },
        )
        self.assertEqual(len(posted), 2)
        self.assertEqual(len(github.comments), 2)

    def test_model_identity_claiming_other_provider_is_rejected(self) -> None:
        github = FakeGitHub([metadata()])
        wrong_model = bridge.ProviderExecution(
            result=execution("grok").result,
            cli_version="grok 1.0",
            model_metadata="claude-sonnet",
        )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "model identity conflicts"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"grok": FakeAdapter(wrong_model)},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(github.comments, [])

    def test_grok_build_model_identities_are_accepted(self) -> None:
        for model in ("grok-build", "grok-4.6-build"):
            with self.subTest(model=model):
                valid = execution("grok")
                valid = bridge.ProviderExecution(
                    result=valid.result,
                    cli_version=valid.cli_version,
                    model_metadata=model,
                )
                posted, _github, _repository = self.run_bridge(
                    ("grok",), {"grok": valid}
                )
                self.assertEqual(len(posted), 1)

    def test_non_build_grok_model_is_rejected_without_post(self) -> None:
        github = FakeGitHub([metadata()])
        invalid = execution("grok")
        invalid = bridge.ProviderExecution(
            result=invalid.result,
            cli_version=invalid.cli_version,
            model_metadata="grok-4.5",
        )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "non-Build model"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"grok": FakeAdapter(invalid)},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(github.comments, [])

    def test_missing_grok_model_is_rejected_without_post(self) -> None:
        github = FakeGitHub([metadata()])
        invalid = execution("grok")
        invalid = bridge.ProviderExecution(
            result=invalid.result,
            cli_version=invalid.cli_version,
            model_metadata=None,
        )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "missing or non-Build"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"grok": FakeAdapter(invalid)},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(github.comments, [])

    def test_provider_subprocess_failure_posts_nothing(self) -> None:
        github = FakeGitHub([metadata()])
        repository = FakeRepository()
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "provider failed"):
            bridge.ReviewBridge(
                github,
                repository,
                {"claude": FakeAdapter(bridge.ReviewBridgeError("provider failed"))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])
        self.assertTrue(repository.cleaned)

    def test_moved_head_posts_nothing(self) -> None:
        github = FakeGitHub([metadata(), metadata(MOVED_HEAD)])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "head moved"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"claude": FakeAdapter(execution("claude"))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_all_mode_with_two_valid_results_posts_two(self) -> None:
        posted, github, _repository = self.run_bridge(
            ("claude", "grok"),
            {"claude": execution("claude"), "grok": execution("grok")},
        )
        self.assertEqual(len(posted), 2)
        self.assertEqual(len(github.comments), 2)

    def test_all_mode_one_failure_posts_neither(self) -> None:
        github = FakeGitHub([metadata()])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "bad output"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {
                    "claude": FakeAdapter(execution("claude")),
                    "grok": FakeAdapter(bridge.ReviewBridgeError("bad output")),
                },
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude", "grok"), "Review.")
        self.assertEqual(github.comments, [])

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
        body = (
            "## External exact-head review — Claude\n"
            "Provider: Claude\n"
            f"PR: #{PR_NUMBER}\n"
            f"Head SHA: {HEAD}\n"
            "Verdict: PASS\n"
            "Review role: Issue #98 external second-pair review\n\n"
            "Substantive review remains."
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",), {"claude": execution("claude", body=body)}
        )
        comment = github.comments[0]
        self.assertEqual(comment.count("External exact-head review — Claude"), 1)
        self.assertEqual(comment.count("Issue #98 external second-pair review"), 1)
        self.assertIn("Substantive review remains.", comment)

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

    def test_neutral_metadata_shaped_prose_is_tolerated_and_retained(self) -> None:
        body = (
            "Provider: <string>\n"
            "Model: custom-review-engine\n\n"
            "These are schema examples, not identity claims."
        )
        _posted, github, _repository = self.run_bridge(
            ("claude",), {"claude": execution("claude", body=body)}
        )
        self.assertIn("Provider: <string>", github.comments[0])
        self.assertIn("Model: custom-review-engine", github.comments[0])

    def test_mismatched_wrapper_header_is_rejected_without_post(self) -> None:
        github = FakeGitHub([metadata()])
        body = "## External exact-head review — Grok\n\nSubstantive review."
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "identity conflicts"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"claude": FakeAdapter(execution("claude", body=body))},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_findings_verdict_without_structured_findings_is_rejected(self) -> None:
        github = FakeGitHub([metadata()])
        progress_only = execution(
            "grok",
            verdict="FINDINGS",
            body="Starting an independent exact-head review.",
            findings=(),
        )
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "FINDINGS without structured findings"
        ):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"grok": FakeAdapter(progress_only)},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("grok",), "Review.")
        self.assertEqual(github.comments, [])

    def test_pass_with_structured_findings_is_rejected(self) -> None:
        github = FakeGitHub([metadata()])
        inconsistent = execution(
            "claude",
            findings=(
                bridge.ReviewFinding("LOW", "Unexpected finding", "Detail."),
            ),
        )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "PASS with findings"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {"claude": FakeAdapter(inconsistent)},
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertEqual(github.comments, [])

    def test_all_mode_semantic_failure_is_atomic(self) -> None:
        github = FakeGitHub([metadata()])
        invalid_grok = execution(
            "grok", verdict="FINDINGS", body="Review starting.", findings=()
        )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "structured findings"):
            bridge.ReviewBridge(
                github,
                FakeRepository(),
                {
                    "claude": FakeAdapter(execution("claude")),
                    "grok": FakeAdapter(invalid_grok),
                },
                emit=lambda _message: None,
            ).review(PR_NUMBER, ("claude", "grok"), "Review.")
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

    def test_contract_requires_well_formed_findings(self) -> None:
        base_contract: dict[str, object] = {
            "pr_number": PR_NUMBER,
            "head_sha": HEAD,
            "verdict": "PASS",
            "body_markdown": "No material findings.",
        }
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "malformed findings"):
            bridge.review_result_from_contract(base_contract)
        malformed = dict(base_contract, findings=[{"severity": "MEDIUM"}])
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "empty title"):
            bridge.review_result_from_contract(malformed)

    def test_contract_enforces_verdict_findings_consistency(self) -> None:
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
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "contained no findings"):
            bridge.review_result_from_contract(
                dict(base_contract, verdict="FINDINGS", findings=[])
            )
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "PASS.*findings"):
            bridge.review_result_from_contract(
                dict(base_contract, verdict="PASS", findings=one_finding)
            )
        malformed_severity = [
            {
                "severity": "URGENT",
                "title": "Bad severity",
                "detail": "Not in the contract enum.",
            }
        ]
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "malformed severity"):
            bridge.review_result_from_contract(
                dict(
                    base_contract,
                    verdict="FINDINGS",
                    findings=malformed_severity,
                )
            )

    def test_wrapper_prompt_contains_exact_diff_and_findings_invariants(self) -> None:
        _posted, _github, _repository = self.run_bridge(
            ("claude",), {"claude": execution("claude")}
        )
        github = FakeGitHub([metadata(), metadata()])
        adapter = FakeAdapter(execution("claude"))
        bridge.ReviewBridge(
            github, FakeRepository(), {"claude": adapter}, emit=lambda _message: None
        ).review(PR_NUMBER, ("claude",), "Review.")
        self.assertIn("diff --git a/tool.py b/tool.py", adapter.prompts[0])
        self.assertIn("PASS requires an empty `findings` array", adapter.prompts[0])


class ProviderAdapterTests(unittest.TestCase):
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
        provider_command = runner.calls[-1]["args"]
        assert isinstance(provider_command, tuple)
        self.assertNotIn("Bash", provider_command[provider_command.index("--tools") + 1])
        self.assertIn("Bash", provider_command[provider_command.index("--disallowedTools") + 1])
        self.assertIn(
            "Read(//detached/**)",
            provider_command[provider_command.index("--allowedTools") + 1],
        )

    def test_grok_rejects_discovered_mcp_configuration(self) -> None:
        runner = QueueRunner(
            [
                completed(stdout="grok 1.0.5\n"),
                completed(stdout=GROK_HELP),
                completed(stdout=GROK_MODELS),
                completed(stdout='{"mcpServers":[{"name":"unsafe"}]}'),
            ]
        )
        adapter = bridge.ProviderAdapter(
            bridge.PROVIDER_SPECS["grok"], runner, source_environment={"PATH": "/usr/bin"}
        )
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "active review customizations"
        ):
            adapter.run(Path("/detached"), "Review.")
        self.assertEqual(len(runner.calls), 4)

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
                "GROK_HOME": "/user/grok",
            },
        )
        adapter.run(Path("/detached"), "Private review prompt.")
        for call in runner.calls:
            environment = call["env"]
            assert isinstance(environment, dict)
            self.assertNotEqual(environment["GROK_HOME"], "/user/grok")
            self.assertEqual(environment["GROK_AUTH_PATH"], "/user/grok/auth.json")
            self.assertEqual(environment["GROK_SESSION_REGISTRY"], "0")
            self.assertEqual(environment["GROK_SESSION_SEARCH"], "0")
        provider_command = runner.calls[-1]["args"]
        assert isinstance(provider_command, tuple)
        inspect_command = runner.calls[-2]["args"]
        assert isinstance(inspect_command, tuple)
        for command in (inspect_command, provider_command):
            self.assertEqual(command[command.index("-m") + 1], "grok-4.6")
            self.assertEqual(command[command.index("--sandbox") + 1], "strict")
            self.assertIn("Read(./**)", command)
            self.assertIn("Grep(./**)", command)
            self.assertNotIn("Read", command)
            self.assertNotIn("Grep", command)
        self.assertEqual(
            provider_command[provider_command.index("--tools") + 1], "Read,Grep"
        )
        self.assertIn("Bash", provider_command)
        self.assertFalse(any("Bash(git" in argument for argument in provider_command))

    def test_grok_build_alias_is_preferred_and_explicit_when_available(self) -> None:
        listing = """Default model: grok-4.7
Available models:
  * grok-4.7 (default)
  - grok-build
"""
        selected = bridge.select_grok_request_model(listing)
        self.assertEqual(selected, "grok-build")
        command = bridge.ProviderAdapter._grok_command(
            Path("/detached"), Path("/prompt.md"), selected
        )
        self.assertEqual(command[command.index("-m") + 1], "grok-build")

    def test_grok_model_listing_requires_available_default(self) -> None:
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "omitted a default"):
            bridge.select_grok_request_model("Available models:\n  - grok-4.6\n")
        with self.assertRaisesRegex(bridge.ReviewBridgeError, "absent from available"):
            bridge.select_grok_request_model(
                "Default model: grok-4.6\nAvailable models:\n  - grok-4.5\n"
            )

    def test_grok_model_selector_capability_is_required(self) -> None:
        help_without_model_selector = GROK_HELP.replace("--model", "")
        with self.assertRaisesRegex(
            bridge.ReviewBridgeError, "explicit model selection"
        ):
            bridge.validate_cli_capabilities("grok", help_without_model_selector)

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

    def test_symlink_to_internal_file_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.txt").write_text("inside\n", encoding="utf-8")
            (root / "link.txt").symlink_to("target.txt")
            bridge.validate_worktree_symlinks(root)

    def test_symlink_to_internal_directory_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target").mkdir()
            (root / "target" / "file.txt").write_text("inside\n", encoding="utf-8")
            (root / "link").symlink_to("target", target_is_directory=True)
            bridge.validate_worktree_symlinks(root)

    def test_symlink_to_outside_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "checkout"
            root.mkdir()
            outside = parent / "outside.txt"
            outside.write_text("synthetic\n", encoding="utf-8")
            (root / "escape.txt").symlink_to(outside)
            with self.assertRaisesRegex(bridge.ReviewBridgeError, "symlink escapes"):
                bridge.validate_worktree_symlinks(root)

    def test_symlink_to_outside_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "checkout"
            root.mkdir()
            outside = parent / "outside"
            outside.mkdir()
            (root / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(bridge.ReviewBridgeError, "symlink escapes"):
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

    def test_detached_worktree_cleanup_happens_on_success(self) -> None:
        runner = QueueRunner([completed(), completed()])
        with tempfile.TemporaryDirectory() as parent:
            repository = bridge.GitRepository(
                runner, Path("/repo"), temporary_parent=Path(parent)
            )
            with repository.detached_worktree(PR_NUMBER, HEAD):
                pass
        commands = [call["args"] for call in runner.calls]
        self.assertEqual(commands[0][:4], ("git", "worktree", "add", "--detach"))
        self.assertEqual(commands[1][:4], ("git", "worktree", "remove", "--force"))

    def test_detached_worktree_cleanup_happens_on_provider_failure(self) -> None:
        runner = QueueRunner([completed(), completed()])
        with tempfile.TemporaryDirectory() as parent:
            repository = bridge.GitRepository(
                runner, Path("/repo"), temporary_parent=Path(parent)
            )
            with self.assertRaisesRegex(RuntimeError, "provider failed"):
                with repository.detached_worktree(PR_NUMBER, HEAD):
                    raise RuntimeError("provider failed")
        commands = [call["args"] for call in runner.calls]
        self.assertEqual(commands[1][:4], ("git", "worktree", "remove", "--force"))


class DoctorTests(unittest.TestCase):
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
        self.assertIn("Claude safety capabilities: compatible", output)
        self.assertIn("Grok safety capabilities: compatible", output)
        self.assertIn("Grok session controls: compatible", output)
        self.assertIn(
            "Grok Build model selection: explicit `grok-4.6` request", output
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

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
) -> bridge.ProviderExecution:
    return bridge.ProviderExecution(
        result=bridge.ReviewResult(
            pr_number=pr_number,
            head_sha=head,
            verdict=verdict,
            body_markdown=body,
        ),
        cli_version=f"{provider} 1.0",
        model_metadata=f"{provider}-model",
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
    def __init__(self) -> None:
        self.ensured: list[tuple[str, int | None]] = []
        self.cleaned = False
        self.clean_checks: list[str] = []

    def ensure_commit(self, sha: str, *, pr_number: int | None = None) -> None:
        self.ensured.append((sha, pr_number))

    def assert_clean(self, worktree: Path, provider_name: str) -> None:
        self.clean_checks.append(provider_name)

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


class ProviderAdapterTests(unittest.TestCase):
    def test_provider_child_environment_scrubs_github_credentials(self) -> None:
        provider_payload = {
            "structured_output": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No findings.",
            },
            "model": "claude-test",
        }
        runner = QueueRunner(
            [
                completed(stdout="2.1.0 (Claude Code)\n"),
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

    def test_grok_rejects_discovered_mcp_configuration(self) -> None:
        runner = QueueRunner(
            [
                completed(stdout="grok 1.0.5\n"),
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
        self.assertEqual(len(runner.calls), 2)

    def test_grok_uses_ephemeral_home_with_existing_auth_path(self) -> None:
        provider_payload = {
            "structured_output": {
                "pr_number": PR_NUMBER,
                "head_sha": HEAD,
                "verdict": "PASS",
                "body_markdown": "No findings.",
            }
        }
        runner = QueueRunner(
            [
                completed(stdout="grok 1.0.5\n"),
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


class WorktreeCleanupTests(unittest.TestCase):
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
                completed(stdout=f'{{"loggedIn":true,"token":"{secret}"}}'),
                completed(stdout="grok 1.0.5\n"),
                completed(stdout="Available models: grok-4.6\n", stderr=secret),
            ]
        )
        healthy, lines = bridge.doctor(runner, Path("/repository"))
        self.assertTrue(healthy)
        output = "\n".join(lines)
        self.assertNotIn(secret, output)
        self.assertNotIn("super_secret", output)


if __name__ == "__main__":
    unittest.main()

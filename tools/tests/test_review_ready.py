from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

from tools import review_ready


HEAD = "1" * 40
MOVED_HEAD = "2" * 40
PR_NUMBER = 107
REPOSITORY = "kmart01123/kinetic-vanguard"
BRANCH = "agent/devcontainer-resolute-refresh"
ROOT = Path(__file__).resolve().parents[2]


def completed(
    args: tuple[str, ...],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class FakeRunner:
    def __init__(
        self,
        *,
        dirty: bool = False,
        detached: bool = False,
        branch: str = BRANCH,
        no_pr: bool = False,
        pr_lookup_stderr: str | None = None,
        state: str = "OPEN",
        initial_pr_head: str = HEAD,
        final_pr_head: str = HEAD,
        initial_local_head: str = HEAD,
        final_local_head: str = HEAD,
        doctor_returncode: int = 0,
        required_checks: bool = True,
        required_probe_returncode: int = 0,
        required_watch_returncode: int = 0,
        fallback_watch_returncode: int = 0,
        review_returncode: int = 0,
    ) -> None:
        self.dirty = dirty
        self.detached = detached
        self.branch = branch
        self.no_pr = no_pr
        self.pr_lookup_stderr = pr_lookup_stderr
        self.state = state
        self.initial_pr_head = initial_pr_head
        self.final_pr_head = final_pr_head
        self.local_heads = [initial_local_head, final_local_head]
        self.doctor_returncode = doctor_returncode
        self.required_checks = required_checks
        self.required_probe_returncode = required_probe_returncode
        self.required_watch_returncode = required_watch_returncode
        self.fallback_watch_returncode = fallback_watch_returncode
        self.review_returncode = review_returncode
        self.calls: list[tuple[str, ...]] = []

    def pr_json(self, head: str, state: str = "OPEN") -> str:
        return review_ready.json.dumps(
            {
                "number": PR_NUMBER,
                "state": state,
                "headRefOid": head,
                "headRefName": self.branch,
                "url": f"https://github.test/pull/{PR_NUMBER}",
            }
        )

    @staticmethod
    def required_probe_command() -> tuple[str, ...]:
        return (
            "gh",
            "pr",
            "checks",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
            "--required",
            "--json",
            "name,state,bucket",
        )

    @staticmethod
    def required_watch_command() -> tuple[str, ...]:
        return (
            "gh",
            "pr",
            "checks",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
            "--required",
            "--watch",
            "--fail-fast",
        )

    @staticmethod
    def fallback_watch_command() -> tuple[str, ...]:
        return (
            "gh",
            "pr",
            "checks",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
            "--watch",
            "--fail-fast",
        )

    def run(
        self, args: tuple[str, ...], *, cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(args)
        self.calls.append(command)
        if command == ("git", "rev-parse", "--show-toplevel"):
            return completed(command, stdout=f"{ROOT}\n")
        if command == ("git", "status", "--porcelain"):
            output = " M README.md\n" if self.dirty else ""
            return completed(command, stdout=output)
        if command == ("git", "symbolic-ref", "--quiet", "--short", "HEAD"):
            if self.detached:
                return completed(command, returncode=1, stderr="detached HEAD")
            return completed(command, stdout=f"{self.branch}\n")
        if command == ("git", "rev-parse", "HEAD"):
            return completed(command, stdout=f"{self.local_heads.pop(0)}\n")
        if command == ("gh", "repo", "view", "--json", "nameWithOwner"):
            return completed(
                command,
                stdout=review_ready.json.dumps({"nameWithOwner": REPOSITORY}),
            )
        if command == (
            "gh",
            "pr",
            "view",
            self.branch,
            "--repo",
            REPOSITORY,
            "--json",
            review_ready.PR_FIELDS,
        ):
            if self.no_pr:
                return completed(command, returncode=1, stderr="no pull requests found")
            if self.pr_lookup_stderr is not None:
                return completed(command, returncode=1, stderr=self.pr_lookup_stderr)
            return completed(
                command, stdout=self.pr_json(self.initial_pr_head, self.state)
            )
        if command == (
            "gh",
            "pr",
            "view",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
            "--json",
            review_ready.PR_FIELDS,
        ):
            return completed(command, stdout=self.pr_json(self.final_pr_head))
        if command == ("python3", "tools/external_review.py", "doctor"):
            return completed(
                command,
                returncode=self.doctor_returncode,
                stderr="provider doctor failed" if self.doctor_returncode else "",
            )
        if command == self.required_probe_command():
            checks = (
                [{"name": "Main branch gate", "state": "SUCCESS", "bucket": "pass"}]
                if self.required_checks
                else []
            )
            return completed(
                command,
                returncode=self.required_probe_returncode,
                stdout=review_ready.json.dumps(checks),
            )
        if command == self.required_watch_command():
            return completed(
                command,
                returncode=self.required_watch_returncode,
                stderr=(
                    "required check failed" if self.required_watch_returncode else ""
                ),
            )
        if command == self.fallback_watch_command():
            return completed(
                command,
                returncode=self.fallback_watch_returncode,
                stderr=("CI check failed" if self.fallback_watch_returncode else ""),
            )
        if command[:3] == ("python3", "tools/external_review.py", "review"):
            return completed(
                command,
                returncode=self.review_returncode,
                stderr="provider review failed" if self.review_returncode else "",
            )
        raise AssertionError(f"unexpected command: {command}")


class ReviewReadyTests(unittest.TestCase):
    def invoke(
        self, runner: FakeRunner
    ) -> tuple[str, list[str], list[tuple[str, ...]]]:
        output: list[str] = []
        head = review_ready.ReviewReady(runner, ROOT, emit=output.append).run()
        return head, output, runner.calls

    def assert_blocked(self, runner: FakeRunner, pattern: str) -> None:
        with self.assertRaisesRegex(review_ready.ReviewReadyError, pattern):
            self.invoke(runner)

    @staticmethod
    def review_calls(runner: FakeRunner) -> list[tuple[str, ...]]:
        return [
            call
            for call in runner.calls
            if call[:3] == ("python3", "tools/external_review.py", "review")
        ]

    def test_dirty_worktree_is_blocked(self) -> None:
        runner = FakeRunner(dirty=True)
        self.assert_blocked(runner, "worktree is dirty")
        self.assertEqual(self.review_calls(runner), [])

    def test_local_branch_is_resolved_explicitly(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        self.assertIn(
            ("git", "symbolic-ref", "--quiet", "--short", "HEAD"), runner.calls
        )

    def test_current_pr_query_uses_explicit_slash_containing_branch(self) -> None:
        branch = "agent/topic/with-slashes"
        runner = FakeRunner(branch=branch)
        self.invoke(runner)
        self.assertIn(
            (
                "gh",
                "pr",
                "view",
                branch,
                "--repo",
                REPOSITORY,
                "--json",
                review_ready.PR_FIELDS,
            ),
            runner.calls,
        )

    def test_detached_head_is_blocked(self) -> None:
        runner = FakeRunner(detached=True)
        self.assert_blocked(runner, "HEAD is detached")
        self.assertFalse(any(call[:3] == ("gh", "pr", "view") for call in runner.calls))

    def test_no_current_pr_is_blocked(self) -> None:
        runner = FakeRunner(no_pr=True)
        self.assert_blocked(runner, "no pull request exists")
        self.assertEqual(self.review_calls(runner), [])

    def test_closed_pr_is_blocked(self) -> None:
        runner = FakeRunner(state="CLOSED")
        self.assert_blocked(runner, "only open PRs")
        self.assertEqual(self.review_calls(runner), [])

    def test_gh_error_followed_by_help_reports_concrete_error(self) -> None:
        stderr = """GraphQL: pull request lookup failed

Usage:
  gh pr view [<number> | <url> | <branch>] [flags]

Flags:
  -w, --web   Open a pull request in the browser
  -h, --help  Show help for command
"""
        runner = FakeRunner(pr_lookup_stderr=stderr)
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            self.invoke(runner)
        message = str(raised.exception)
        self.assertIn("GraphQL: pull request lookup failed", message)
        self.assertNotIn("-w, --web", message)

    def test_diagnostic_redacts_token(self) -> None:
        result = completed(
            ("gh",), returncode=1, stderr="error: token=gho_supersecretvalue"
        )
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            review_ready.require_success(result, "GitHub command")
        self.assertIn("token=[REDACTED]", str(raised.exception))
        self.assertNotIn("supersecretvalue", str(raised.exception))

    def test_local_head_mismatch_is_blocked(self) -> None:
        runner = FakeRunner(initial_local_head=MOVED_HEAD)
        self.assert_blocked(runner, "local HEAD does not match")
        self.assertEqual(self.review_calls(runner), [])

    def test_doctor_failure_is_blocked(self) -> None:
        runner = FakeRunner(doctor_returncode=1)
        self.assert_blocked(runner, "external-review doctor.*failed")
        self.assertNotIn(FakeRunner.required_probe_command(), runner.calls)
        self.assertEqual(self.review_calls(runner), [])

    def test_required_checks_use_required_watch(self) -> None:
        runner = FakeRunner(required_checks=True)
        self.invoke(runner)
        self.assertIn(FakeRunner.required_probe_command(), runner.calls)
        self.assertIn(FakeRunner.required_watch_command(), runner.calls)
        self.assertNotIn(FakeRunner.fallback_watch_command(), runner.calls)

    def test_no_required_checks_uses_all_check_fallback(self) -> None:
        runner = FakeRunner(required_checks=False, required_probe_returncode=1)
        self.invoke(runner)
        self.assertIn(FakeRunner.required_probe_command(), runner.calls)
        self.assertIn(FakeRunner.fallback_watch_command(), runner.calls)
        self.assertNotIn(FakeRunner.required_watch_command(), runner.calls)

    def test_required_check_probe_command_error_does_not_fallback(self) -> None:
        runner = FakeRunner(required_checks=False, required_probe_returncode=2)
        self.assert_blocked(runner, "required checks lookup.*failed")
        self.assertNotIn(FakeRunner.fallback_watch_command(), runner.calls)
        self.assertEqual(self.review_calls(runner), [])

    def test_required_ci_failure_is_blocked(self) -> None:
        runner = FakeRunner(required_watch_returncode=1)
        self.assert_blocked(runner, "required checks.*failed")
        self.assertEqual(self.review_calls(runner), [])

    def test_fallback_ci_failure_is_blocked(self) -> None:
        runner = FakeRunner(required_checks=False, fallback_watch_returncode=1)
        self.assert_blocked(runner, "all checks.*failed")
        self.assertEqual(self.review_calls(runner), [])

    def test_pr_head_change_while_waiting_is_blocked(self) -> None:
        runner = FakeRunner(final_pr_head=MOVED_HEAD)
        self.assert_blocked(runner, "PR head changed while waiting")
        self.assertEqual(self.review_calls(runner), [])

    def test_local_head_change_while_waiting_is_blocked(self) -> None:
        runner = FakeRunner(final_local_head=MOVED_HEAD)
        self.assert_blocked(runner, "Local HEAD changed while waiting")
        self.assertEqual(self.review_calls(runner), [])

    def test_exact_head_is_revalidated_after_either_ci_path(self) -> None:
        revalidation = (
            "gh",
            "pr",
            "view",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
            "--json",
            review_ready.PR_FIELDS,
        )
        for required_checks in (True, False):
            with self.subTest(required_checks=required_checks):
                runner = FakeRunner(required_checks=required_checks)
                self.invoke(runner)
                watch = (
                    FakeRunner.required_watch_command()
                    if required_checks
                    else FakeRunner.fallback_watch_command()
                )
                self.assertGreater(runner.calls.index(revalidation), runner.calls.index(watch))
                self.assertEqual(runner.calls.count(("git", "rev-parse", "HEAD")), 2)

    def test_unchanged_head_invokes_review_exactly_once(self) -> None:
        runner = FakeRunner()
        head, output, _calls = self.invoke(runner)
        self.assertEqual(head, HEAD)
        self.assertEqual(len(self.review_calls(runner)), 1)
        self.assertIn(f"External reviews completed for exact head {HEAD}.", output)
        self.assertIn("Human disposition is required before merge.", output)

    def test_provider_review_failure_propagates_without_success(self) -> None:
        runner = FakeRunner(review_returncode=1)
        output: list[str] = []
        with self.assertRaisesRegex(review_ready.ReviewReadyError, "external reviews failed"):
            review_ready.ReviewReady(runner, ROOT, emit=output.append).run()
        self.assertEqual(len(self.review_calls(runner)), 1)
        self.assertFalse(any("completed for exact head" in line for line in output))

    def test_checked_in_prompt_path_is_supplied(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        review_call = self.review_calls(runner)[0]
        prompt_index = review_call.index("--prompt-file") + 1
        self.assertEqual(review_call[prompt_index], review_ready.PROMPT_PATH)
        self.assertTrue((ROOT / review_ready.PROMPT_PATH).is_file())

    def test_no_merge_or_pr_mutation_command_is_invoked(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        github_calls = [call for call in runner.calls if call[0] == "gh"]
        self.assertTrue(github_calls)
        for call in github_calls:
            self.assertNotIn("merge", call)
            self.assertNotIn("ready", call)
            self.assertNotIn("edit", call)
            if call[:2] == ("gh", "pr"):
                self.assertIn(call[2], {"view", "checks"})


if __name__ == "__main__":
    unittest.main()

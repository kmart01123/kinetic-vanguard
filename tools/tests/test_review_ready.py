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


def check(name: str, state: str, bucket: str) -> dict[str, str]:
    return {
        "name": name,
        "state": state,
        "bucket": bucket,
        "workflow": "CI",
        "link": "https://github.test/check/1",
    }


PENDING = check("Main branch gate", "IN_PROGRESS", "pending")
PASS = check("Main branch gate", "SUCCESS", "pass")
FAIL = check("Main branch gate", "FAILURE", "fail")
CANCEL = check("Main branch gate", "CANCELLED", "cancel")
SKIP = check("Optional layout", "SKIPPED", "skipping")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


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
        poll_pr_heads: list[str] | None = None,
        initial_local_head: str = HEAD,
        final_local_head: str = HEAD,
        doctor_returncode: int = 0,
        doctor_stdout: str = "OK   external-review doctor: healthy\n",
        doctor_stderr: str = "",
        required_probe_checks: list[dict[str, str]] | None = None,
        required_probe_returncode: int | None = None,
        check_snapshots: list[list[dict[str, str]]] | None = None,
        check_lookup_timeout_at: int | None = None,
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
        self.poll_pr_heads = list(poll_pr_heads or [])
        self.local_heads = [initial_local_head, final_local_head]
        self.doctor_returncode = doctor_returncode
        self.doctor_stdout = doctor_stdout
        self.doctor_stderr = doctor_stderr
        self.required_probe_checks = list(
            required_probe_checks if required_probe_checks is not None else [PENDING]
        )
        self.required_probe_returncode = required_probe_returncode
        self.check_snapshots = list(
            check_snapshots if check_snapshots is not None else [[PASS]]
        )
        self.check_lookup_timeout_at = check_lookup_timeout_at
        self.review_returncode = review_returncode
        self.calls: list[tuple[str, ...]] = []
        self.streaming_calls: list[tuple[str, ...]] = []
        self.timed_calls: list[tuple[tuple[str, ...], float | None]] = []
        self.check_lookup_count = 0
        self.snapshot_index = 0

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
    def checks_command(*, required: bool) -> tuple[str, ...]:
        command = [
            "gh",
            "pr",
            "checks",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
        ]
        if required:
            command.append("--required")
        command.extend(("--json", review_ready.CHECK_FIELDS))
        return tuple(command)

    @staticmethod
    def check_returncode(snapshot: list[dict[str, str]]) -> int:
        buckets = {item["bucket"] for item in snapshot}
        if buckets & {"fail", "cancel"}:
            return 1
        if "pending" in buckets:
            return 8
        return 0

    def run(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(args)
        self.calls.append(command)
        self.timed_calls.append((command, timeout))
        if command == ("git", "rev-parse", "--show-toplevel"):
            return completed(command, stdout=f"{ROOT}\n")
        if command == ("git", "status", "--porcelain"):
            return completed(command, stdout=" M README.md\n" if self.dirty else "")
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
            head = (
                self.poll_pr_heads.pop(0)
                if self.poll_pr_heads
                else self.final_pr_head
            )
            return completed(command, stdout=self.pr_json(head))
        if command == ("python3", "tools/external_review.py", "doctor"):
            return completed(
                command,
                returncode=self.doctor_returncode,
                stdout=self.doctor_stdout,
                stderr=self.doctor_stderr,
            )
        if command[:3] == ("gh", "pr", "checks"):
            self.check_lookup_count += 1
            if self.check_lookup_count == self.check_lookup_timeout_at:
                raise subprocess.TimeoutExpired(command, timeout)
            if self.check_lookup_count == 1:
                snapshot = self.required_probe_checks
                returncode = (
                    self.required_probe_returncode
                    if self.required_probe_returncode is not None
                    else self.check_returncode(snapshot)
                )
            else:
                index = min(self.snapshot_index, len(self.check_snapshots) - 1)
                snapshot = self.check_snapshots[index]
                self.snapshot_index += 1
                returncode = self.check_returncode(snapshot)
            return completed(
                command,
                returncode=returncode,
                stdout=review_ready.json.dumps(snapshot),
            )
        raise AssertionError(f"unexpected command: {command}")

    def run_streaming(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(args)
        self.streaming_calls.append(command)
        if command[:3] != ("python3", "tools/external_review.py", "review"):
            raise AssertionError(f"unexpected streaming command: {command}")
        return completed(command, returncode=self.review_returncode)


class ReviewReadyTests(unittest.TestCase):
    def invoke(
        self,
        runner: FakeRunner,
        *,
        wait_timeout: float = 100.0,
        startup_grace: float = 30.0,
        progress_interval: float = 60.0,
    ) -> tuple[str, list[str], list[tuple[str, ...]], FakeClock]:
        output: list[str] = []
        clock = FakeClock()
        head = review_ready.ReviewReady(
            runner,
            ROOT,
            emit=output.append,
            clock=clock,
            sleeper=clock.sleep,
            check_poll_interval=10.0,
            check_wait_timeout=wait_timeout,
            check_startup_grace=startup_grace,
            check_progress_interval=progress_interval,
        ).run()
        return head, output, runner.calls, clock

    def assert_blocked(
        self, runner: FakeRunner, pattern: str, **timing: float
    ) -> None:
        with self.assertRaisesRegex(review_ready.ReviewReadyError, pattern):
            self.invoke(runner, **timing)
        self.assertEqual(self.review_calls(runner), [])

    @staticmethod
    def review_calls(runner: FakeRunner) -> list[tuple[str, ...]]:
        return [
            call
            for call in runner.streaming_calls
            if call[:3] == ("python3", "tools/external_review.py", "review")
        ]

    def test_dirty_worktree_is_blocked(self) -> None:
        self.assert_blocked(FakeRunner(dirty=True), "worktree is dirty")

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
        self.assert_blocked(FakeRunner(no_pr=True), "no pull request exists")

    def test_closed_pr_is_blocked(self) -> None:
        self.assert_blocked(FakeRunner(state="CLOSED"), "only open PRs")

    def test_gh_error_followed_by_help_reports_concrete_error(self) -> None:
        stderr = """GraphQL: pull request lookup failed

Usage:
  gh pr view [<number> | <url> | <branch>] [flags]

Flags:
  -w, --web   Open a pull request in the browser
"""
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            self.invoke(FakeRunner(pr_lookup_stderr=stderr))
        self.assertIn("GraphQL: pull request lookup failed", str(raised.exception))
        self.assertNotIn("-w, --web", str(raised.exception))

    def test_diagnostic_redacts_token(self) -> None:
        result = completed(
            ("gh",), returncode=1, stderr="error: token=gho_supersecretvalue"
        )
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            review_ready.require_success(result, "GitHub command")
        self.assertIn("token=[REDACTED]", str(raised.exception))
        self.assertNotIn("supersecretvalue", str(raised.exception))

    def test_local_head_mismatch_is_blocked(self) -> None:
        self.assert_blocked(
            FakeRunner(initial_local_head=MOVED_HEAD), "local HEAD does not match"
        )

    def test_doctor_failure_reports_all_fail_lines_from_realistic_stdout(self) -> None:
        runner = FakeRunner(
            doctor_returncode=1,
            doctor_stdout=(
                "OK   git: git version 2.55.0\n"
                "OK   gh: gh version 2.97.0\n"
                "FAIL Claude authentication: token=gho_supersecretvalue\n"
                "FAIL Grok authentication: run `grok login`\n"
            ),
        )
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            self.invoke(runner)
        message = str(raised.exception)
        self.assertIn("FAIL Claude authentication: token=[REDACTED]", message)
        self.assertIn("FAIL Grok authentication: run `grok login`", message)
        self.assertNotIn("OK   git", message)
        self.assertNotIn("supersecretvalue", message)
        self.assertEqual(runner.check_lookup_count, 0)
        self.assertEqual(self.review_calls(runner), [])

    def test_successful_doctor_emits_concise_health_status(self) -> None:
        _head, output, _calls, _clock = self.invoke(FakeRunner())
        self.assertIn("External-review doctor: healthy", output)

    def test_failed_doctor_never_uses_ok_line_as_failure_reason(self) -> None:
        runner = FakeRunner(
            doctor_returncode=1,
            doctor_stdout="OK   git: git version 2.55.0\n",
        )
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            self.invoke(runner)
        message = str(raised.exception)
        self.assertIn("external-review doctor failed with exit code 1", message)
        self.assertNotIn("OK   git", message)
        self.assertEqual(runner.check_lookup_count, 0)

    def test_pending_then_pass_invokes_review_once(self) -> None:
        runner = FakeRunner(check_snapshots=[[PENDING], [PASS]])
        head, output, _calls, clock = self.invoke(runner)
        self.assertEqual(head, HEAD)
        self.assertEqual(len(self.review_calls(runner)), 1)
        self.assertEqual(clock.sleeps, [10.0])
        self.assertTrue(any(line.startswith("CI pending:") for line in output))
        self.assertIn(f"CI passed for exact head {HEAD}.", output)

    def test_pending_then_failure_is_blocked_with_details(self) -> None:
        runner = FakeRunner(check_snapshots=[[PENDING], [FAIL]])
        with self.assertRaises(review_ready.ReviewReadyError) as raised:
            self.invoke(runner)
        self.assertIn("Main branch gate: FAILURE (fail)", str(raised.exception))
        self.assertEqual(self.review_calls(runner), [])

    def test_pending_then_cancel_is_blocked_with_details(self) -> None:
        runner = FakeRunner(check_snapshots=[[PENDING], [CANCEL]])
        self.assert_blocked(runner, r"Main branch gate: CANCELLED \(cancel\)")

    def test_pass_and_skipping_complete(self) -> None:
        runner = FakeRunner(check_snapshots=[[PASS, SKIP]])
        _head, output, _calls, _clock = self.invoke(runner)
        self.assertIn(f"CI passed for exact head {HEAD}.", output)
        self.assertEqual(len(self.review_calls(runner)), 1)

    def test_unchanged_pending_reports_periodically_without_poll_spam(self) -> None:
        runner = FakeRunner(check_snapshots=[[PENDING]])
        output: list[str] = []
        clock = FakeClock()
        gate = review_ready.ReviewReady(
            runner,
            ROOT,
            emit=output.append,
            clock=clock,
            sleeper=clock.sleep,
            check_poll_interval=10.0,
            check_wait_timeout=65.0,
            check_startup_grace=30.0,
            check_progress_interval=60.0,
        )
        with self.assertRaisesRegex(review_ready.ReviewReadyError, "Timed out waiting"):
            gate.run()
        pending_messages = [line for line in output if line.startswith("CI pending:")]
        self.assertEqual(len(pending_messages), 2)
        self.assertIn("Elapsed: 0s", pending_messages[0])
        self.assertIn("Elapsed: 1m 0s", pending_messages[1])
        self.assertEqual(self.review_calls(runner), [])

    def test_overall_wait_timeout_blocks_review(self) -> None:
        self.assert_blocked(
            FakeRunner(check_snapshots=[[PENDING]]),
            "Timed out waiting.*after 30s",
            wait_timeout=30.0,
        )

    def test_no_checks_then_check_appears_within_grace(self) -> None:
        runner = FakeRunner(
            required_probe_checks=[], check_snapshots=[[], [PASS]]
        )
        _head, output, _calls, _clock = self.invoke(runner)
        self.assertIn("Waiting for all CI checks...", output)
        self.assertIn("Waiting for CI check to appear...", output)
        self.assertIn(f"CI passed for exact head {HEAD}.", output)

    def test_no_checks_through_startup_grace_blocks_review(self) -> None:
        self.assert_blocked(
            FakeRunner(required_probe_checks=[], check_snapshots=[[]]),
            "No CI checks appeared.*within 30s",
            startup_grace=30.0,
        )

    def test_pr_head_change_during_polling_is_blocked_immediately(self) -> None:
        runner = FakeRunner(
            check_snapshots=[[PENDING]], poll_pr_heads=[MOVED_HEAD]
        )
        self.assert_blocked(runner, "PR head changed while waiting")
        self.assertEqual(runner.snapshot_index, 1)

    def test_local_head_change_before_external_review_is_blocked(self) -> None:
        self.assert_blocked(
            FakeRunner(final_local_head=MOVED_HEAD),
            "Local HEAD changed while waiting",
        )

    def test_status_lookup_timeout_has_actionable_message(self) -> None:
        self.assert_blocked(
            FakeRunner(check_lookup_timeout_at=2),
            "GitHub check status lookup timed out; external review was not started",
        )

    def test_github_queries_use_thirty_second_timeout(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        github_calls = [
            (command, timeout)
            for command, timeout in runner.timed_calls
            if command[0] == "gh"
        ]
        self.assertTrue(github_calls)
        self.assertTrue(
            all(
                timeout == review_ready.GITHUB_QUERY_TIMEOUT_SECONDS
                for _, timeout in github_calls
            )
        )

    def test_required_checks_stay_in_required_scope(self) -> None:
        runner = FakeRunner(check_snapshots=[[PASS]])
        self.invoke(runner)
        required_command = FakeRunner.checks_command(required=True)
        self.assertGreaterEqual(runner.calls.count(required_command), 2)
        self.assertNotIn(FakeRunner.checks_command(required=False), runner.calls)

    def test_empty_required_probe_falls_back_to_all_checks(self) -> None:
        runner = FakeRunner(required_probe_checks=[], check_snapshots=[[PASS]])
        self.invoke(runner)
        required_command = FakeRunner.checks_command(required=True)
        self.assertEqual(runner.calls.count(required_command), 1)
        self.assertIn(FakeRunner.checks_command(required=False), runner.calls)

    def test_required_probe_command_error_does_not_fallback(self) -> None:
        runner = FakeRunner(required_probe_checks=[], required_probe_returncode=2)
        self.assert_blocked(runner, "required checks lookup.*failed")
        self.assertNotIn(FakeRunner.checks_command(required=False), runner.calls)

    def test_check_query_requests_visible_fields_and_never_watches(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        check_calls = [
            call
            for call in runner.calls
            if call[:3] == ("gh", "pr", "checks")
        ]
        self.assertTrue(check_calls)
        for call in check_calls:
            self.assertIn(review_ready.CHECK_FIELDS, call)
            self.assertNotIn("--watch", call)
            self.assertNotIn("--fail-fast", call)

    def test_exact_head_is_revalidated_after_polling(self) -> None:
        runner = FakeRunner(check_snapshots=[[PENDING], [PASS]])
        self.invoke(runner)
        refresh = (
            "gh",
            "pr",
            "view",
            str(PR_NUMBER),
            "--repo",
            REPOSITORY,
            "--json",
            review_ready.PR_FIELDS,
        )
        self.assertEqual(runner.calls.count(refresh), 3)
        self.assertEqual(runner.calls.count(("git", "rev-parse", "HEAD")), 2)

    def test_provider_review_failure_propagates_without_success(self) -> None:
        runner = FakeRunner(review_returncode=1)
        output: list[str] = []
        with self.assertRaisesRegex(
            review_ready.ReviewReadyError, "external reviews failed"
        ):
            clock = FakeClock()
            review_ready.ReviewReady(
                runner,
                ROOT,
                emit=output.append,
                clock=clock,
                sleeper=clock.sleep,
            ).run()
        self.assertEqual(len(self.review_calls(runner)), 1)
        self.assertIn("Starting exact-head external reviews...", output)
        self.assertFalse(any("completed for exact head" in line for line in output))

    def test_external_review_uses_streaming_path_exactly_once(self) -> None:
        runner = FakeRunner()
        _head, output, _calls, _clock = self.invoke(runner)
        self.assertEqual(len(self.review_calls(runner)), 1)
        self.assertFalse(
            any(
                call[:3] == ("python3", "tools/external_review.py", "review")
                for call in runner.calls
            )
        )
        self.assertIn("Starting exact-head external reviews...", output)
        self.assertIn(f"External reviews completed for exact head {HEAD}.", output)

    def test_checked_in_prompt_and_all_providers_are_supplied(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        review_call = self.review_calls(runner)[0]
        self.assertEqual(review_call[review_call.index("--provider") + 1], "all")
        self.assertEqual(
            review_call[review_call.index("--prompt-file") + 1],
            review_ready.PROMPT_PATH,
        )
        prompt_path = ROOT / review_ready.PROMPT_PATH
        self.assertTrue(prompt_path.is_file())
        prompt = prompt_path.read_text(encoding="utf-8")
        normalized_prompt = " ".join(prompt.split())
        self.assertIn(
            "Complete the inspection before returning one final review",
            normalized_prompt,
        )
        self.assertIn("verdict PASS", normalized_prompt)
        self.assertIn("verdict FINDINGS", normalized_prompt)
        self.assertIn(
            "never return FINDINGS with an empty findings array", normalized_prompt
        )
        self.assertIn("fail instead of emitting a placeholder", normalized_prompt)

    def test_no_merge_rerun_or_pr_mutation_command_is_invoked(self) -> None:
        runner = FakeRunner()
        self.invoke(runner)
        github_calls = [call for call in runner.calls if call[0] == "gh"]
        self.assertTrue(github_calls)
        for call in github_calls:
            self.assertNotIn("merge", call)
            self.assertNotIn("rerun", call)
            self.assertNotIn("ready", call)
            self.assertNotIn("edit", call)
            if call[:2] == ("gh", "pr"):
                self.assertIn(call[2], {"view", "checks"})


if __name__ == "__main__":
    unittest.main()

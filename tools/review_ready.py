#!/usr/bin/env python3
"""Wait for current PR CI, revalidate its exact head, and run external reviews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence


SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
PR_FIELDS = "number,state,headRefOid,headRefName,url"
PROMPT_PATH = "tools/review_prompts/release-gate.md"
LOW_VALUE_DIAGNOSTIC_HEADINGS = frozenset(
    ("usage:", "flags:", "options:", "inherited flags:", "json fields:", "learn more:")
)
OPTION_LISTING_PATTERN = re.compile(r"^-{1,2}(?:[A-Za-z0-9]|,)")
SENSITIVE_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bgh[oprsu]_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"(?i)(token|secret|password|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(https?://[^/\s:@]+:)[^@\s/]+@"),
)


class ReviewReadyError(RuntimeError):
    """A concise, actionable orchestration failure."""


class Runner(Protocol):
    def run(
        self, args: Sequence[str], *, cwd: Path
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessRunner:
    def run(
        self, args: Sequence[str], *, cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(args),
                cwd=cwd,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise ReviewReadyError(
                f"required command is unavailable: {args[0]}"
            ) from error


@dataclass(frozen=True)
class PRMetadata:
    number: int
    state: str
    head_sha: str
    head_ref: str
    url: str


def require_success(
    completed: subprocess.CompletedProcess[str], description: str
) -> subprocess.CompletedProcess[str]:
    if completed.returncode != 0:
        detail = useful_diagnostic(completed)
        suffix = f": {detail[:300]}" if detail else ""
        raise ReviewReadyError(
            f"{description} failed with exit code {completed.returncode}{suffix}"
        )
    return completed


def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        if pattern.groups >= 3:
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        elif pattern.groups == 1:
            redacted = pattern.sub(r"\1[REDACTED]@", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def useful_diagnostic(completed: subprocess.CompletedProcess[str]) -> str:
    diagnostic = "\n".join(
        part for part in (completed.stderr, completed.stdout) if part.strip()
    )
    lines = [line.strip() for line in diagnostic.splitlines() if line.strip()]

    def is_low_value(line: str) -> bool:
        lowered = line.casefold()
        return (
            any(lowered.startswith(heading) for heading in LOW_VALUE_DIAGNOSTIC_HEADINGS)
            or OPTION_LISTING_PATTERN.match(line) is not None
            or (lowered.startswith("gh ") and "[flags]" in lowered)
        )

    meaningful = [line for line in lines if not is_low_value(line)]
    selected = meaningful[0] if meaningful else (lines[0] if lines else "")
    return redact_sensitive(selected)[:300]


def parse_json_object(raw: str, description: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReviewReadyError(f"{description} returned malformed JSON") from error
    if not isinstance(payload, dict):
        raise ReviewReadyError(f"{description} returned malformed JSON")
    return payload


def parse_json_list(raw: str, description: str) -> list[object]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReviewReadyError(f"{description} returned malformed JSON") from error
    if not isinstance(payload, list):
        raise ReviewReadyError(f"{description} returned malformed JSON")
    return payload


def parse_pr_metadata(raw: str, description: str) -> PRMetadata:
    payload = parse_json_object(raw, description)
    number = payload.get("number")
    state = payload.get("state")
    head_sha = payload.get("headRefOid")
    head_ref = payload.get("headRefName")
    url = payload.get("url")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ReviewReadyError(f"{description} returned a malformed PR number")
    if not all(isinstance(value, str) and value for value in (state, head_ref, url)):
        raise ReviewReadyError(f"{description} returned malformed PR metadata")
    if not isinstance(head_sha, str) or not SHA_PATTERN.fullmatch(head_sha):
        raise ReviewReadyError(f"{description} returned a malformed head SHA")
    return PRMetadata(number, state, head_sha.lower(), head_ref, url)


class ReviewReady:
    def __init__(
        self,
        runner: Runner,
        cwd: Path,
        *,
        emit: Callable[[str], None] = print,
    ) -> None:
        self.runner = runner
        self.cwd = cwd
        self.emit = emit

    def command(
        self, args: Sequence[str], description: str
    ) -> subprocess.CompletedProcess[str]:
        return require_success(self.runner.run(args, cwd=self.cwd), description)

    def repository_root(self) -> Path:
        completed = self.command(
            ("git", "rev-parse", "--show-toplevel"), "repository lookup"
        )
        root_text = completed.stdout.strip()
        if not root_text:
            raise ReviewReadyError("repository lookup returned an empty path")
        root = Path(root_text).resolve()
        if not root.is_dir():
            raise ReviewReadyError("repository root is unavailable")
        self.cwd = root
        return root

    def assert_clean(self) -> None:
        completed = self.command(
            ("git", "status", "--porcelain"), "worktree status"
        )
        if completed.stdout.strip():
            raise ReviewReadyError(
                "local worktree is dirty; commit or remove local changes before review"
            )

    def local_head(self) -> str:
        completed = self.command(("git", "rev-parse", "HEAD"), "local HEAD lookup")
        head = completed.stdout.strip().lower()
        if not SHA_PATTERN.fullmatch(head):
            raise ReviewReadyError("local HEAD lookup returned a malformed SHA")
        return head

    def local_branch(self) -> str:
        completed = self.runner.run(
            ("git", "symbolic-ref", "--quiet", "--short", "HEAD"), cwd=self.cwd
        )
        if completed.returncode != 0:
            raise ReviewReadyError(
                "HEAD is detached; check out the pull request branch before review"
            )
        branch = completed.stdout.strip()
        if not branch:
            raise ReviewReadyError("local branch lookup returned an empty name")
        return branch

    def repository_name(self) -> str:
        completed = self.command(
            ("gh", "repo", "view", "--json", "nameWithOwner"),
            "GitHub repository lookup",
        )
        payload = parse_json_object(completed.stdout, "GitHub repository lookup")
        name = payload.get("nameWithOwner")
        if not isinstance(name, str) or not re.fullmatch(r"[^/\s]+/[^/\s]+", name):
            raise ReviewReadyError(
                "GitHub repository lookup returned malformed metadata"
            )
        return name

    def current_pr(self, repository: str, branch: str) -> PRMetadata:
        completed = self.runner.run(
            (
                "gh",
                "pr",
                "view",
                branch,
                "--repo",
                repository,
                "--json",
                PR_FIELDS,
            ),
            cwd=self.cwd,
        )
        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout).lower()
            if (
                "no pull requests found" in diagnostic
                or "could not find pull request" in diagnostic
            ):
                raise ReviewReadyError(
                    "no pull request exists for the current branch; push it and open a PR"
                )
            require_success(completed, "current PR lookup")
        return parse_pr_metadata(completed.stdout, "current PR lookup")

    def required_checks_exist(self, repository: str, pr_number: int) -> bool:
        description = f"required checks lookup for PR #{pr_number}"
        completed = self.runner.run(
            (
                "gh",
                "pr",
                "checks",
                str(pr_number),
                "--repo",
                repository,
                "--required",
                "--json",
                "name,state,bucket",
            ),
            cwd=self.cwd,
        )
        if completed.returncode not in (0, 1, 8):
            require_success(completed, description)
        if completed.stdout.strip():
            checks = parse_json_list(completed.stdout, description)
            return bool(checks)
        diagnostic = useful_diagnostic(completed).casefold()
        if "no required checks" in diagnostic:
            return False
        require_success(completed, description)
        raise ReviewReadyError(f"{description} returned no check data")

    def wait_for_checks(self, repository: str, pr_number: int) -> None:
        required = self.required_checks_exist(repository, pr_number)
        arguments = [
            "gh",
            "pr",
            "checks",
            str(pr_number),
            "--repo",
            repository,
        ]
        if required:
            arguments.append("--required")
        arguments.extend(("--watch", "--fail-fast"))
        scope = "required" if required else "all"
        self.command(arguments, f"{scope} checks for PR #{pr_number}")

    def refresh_pr(self, repository: str, pr_number: int) -> PRMetadata:
        completed = self.command(
            (
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repository,
                "--json",
                PR_FIELDS,
            ),
            f"GitHub PR #{pr_number} revalidation",
        )
        return parse_pr_metadata(
            completed.stdout, f"GitHub PR #{pr_number} revalidation"
        )

    def run(self) -> str:
        self.repository_root()
        self.assert_clean()
        branch = self.local_branch()
        repository = self.repository_name()
        before_pr = self.current_pr(repository, branch)
        before_local = self.local_head()
        if before_pr.state.upper() != "OPEN":
            raise ReviewReadyError(
                f"PR #{before_pr.number} is {before_pr.state}; only open PRs can be reviewed"
            )
        if before_local != before_pr.head_sha:
            raise ReviewReadyError(
                "local HEAD does not match the current PR head:\n"
                f"  local: {before_local}\n"
                f"  PR:    {before_pr.head_sha}\n"
                "Push or update the branch before review."
            )

        self.emit("Review-ready gate")
        self.emit(f"Repository: {repository}")
        self.emit(f"PR: #{before_pr.number}")
        self.emit(f"Exact head: {before_local}")

        self.command(
            ("python3", "tools/external_review.py", "doctor"),
            "external-review doctor",
        )
        self.wait_for_checks(repository, before_pr.number)

        after_pr = self.refresh_pr(repository, before_pr.number)
        after_local = self.local_head()
        if after_pr.number != before_pr.number:
            raise ReviewReadyError("GitHub returned a different PR during revalidation")
        if after_pr.state.upper() != "OPEN":
            raise ReviewReadyError(
                f"PR #{before_pr.number} is no longer open; review was not started"
            )
        if after_pr.head_sha != before_pr.head_sha:
            raise ReviewReadyError(
                "PR head changed while waiting for CI:\n"
                f"  before: {before_pr.head_sha}\n"
                f"  after:  {after_pr.head_sha}\n"
                "Review was not started."
            )
        if after_local != before_pr.head_sha:
            raise ReviewReadyError(
                "Local HEAD changed while waiting for CI:\n"
                f"  before: {before_pr.head_sha}\n"
                f"  after:  {after_local}\n"
                "Review was not started."
            )

        self.command(
            (
                "python3",
                "tools/external_review.py",
                "review",
                "--pr",
                str(before_pr.number),
                "--provider",
                "all",
                "--prompt-file",
                PROMPT_PATH,
            ),
            "external reviews",
        )
        self.emit(f"External reviews completed for exact head {before_pr.head_sha}.")
        self.emit(f"Review comments were posted to PR #{before_pr.number}.")
        self.emit("Human disposition is required before merge.")
        return before_pr.head_sha


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Wait for current PR checks and run exact-head Claude and Grok reviews"
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    try:
        ReviewReady(SubprocessRunner(), Path.cwd()).run()
        return 0
    except ReviewReadyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

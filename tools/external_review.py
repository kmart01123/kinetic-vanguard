#!/usr/bin/env python3
"""Run provider-bound exact-head reviews and post validated PR comments."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from typing import Callable, Iterator, Mapping, Protocol, Sequence


SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SENSITIVE_PATTERNS = (
    re.compile(r"\bgh[oprsu]_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bxai-[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)(token|secret|password|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)"
    ),
)
GITHUB_SECRET_VARIABLES = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
)
VERDICTS = frozenset(("PASS", "FINDINGS"))
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "pr_number": {"type": "integer", "minimum": 1},
        "head_sha": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$"},
        "verdict": {"type": "string", "enum": sorted(VERDICTS)},
        "body_markdown": {"type": "string", "minLength": 1},
        "provider": {"type": "string"},
        "reviewer": {"type": "string"},
        "model": {"type": "string"},
    },
    "required": ["pr_number", "head_sha", "verdict", "body_markdown"],
    "additionalProperties": False,
}
REVIEW_SCHEMA_JSON = json.dumps(REVIEW_SCHEMA, separators=(",", ":"))


class ReviewBridgeError(RuntimeError):
    """A fail-closed bridge error suitable for a concise CLI diagnostic."""


class Runner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(args),
                cwd=cwd,
                env=dict(env) if env is not None else None,
                input=input_text,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise ReviewBridgeError(f"required command is unavailable: {args[0]}") from error
        except subprocess.TimeoutExpired as error:
            raise ReviewBridgeError(f"command timed out: {args[0]}") from error


@dataclass(frozen=True)
class PRMetadata:
    number: int
    state: str
    head_sha: str
    base_sha: str
    head_ref: str
    base_ref: str
    url: str


@dataclass(frozen=True)
class ReviewResult:
    pr_number: int
    head_sha: str
    verdict: str
    body_markdown: str
    provider_claim: str | None = None
    reviewer_claim: str | None = None
    model_claim: str | None = None


@dataclass(frozen=True)
class ProviderExecution:
    result: ReviewResult
    cli_version: str
    model_metadata: str | None = None


@dataclass(frozen=True)
class PostedComment:
    provider: str
    comment_id: int
    url: str


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    display_name: str
    executable: str
    review_role: str


PROVIDER_SPECS = {
    "claude": ProviderSpec(
        key="claude",
        display_name="Claude",
        executable="claude",
        review_role="Issue #98 external second-pair review",
    ),
    "grok": ProviderSpec(
        key="grok",
        display_name="Grok",
        executable="grok",
        review_role="additional independent review evidence",
    ),
}


def redact_sensitive(text: str) -> str:
    redacted = ANSI_PATTERN.sub("", text)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.groups >= 3:
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def safe_failure_detail(completed: subprocess.CompletedProcess[str]) -> str:
    lines = [
        line.strip()
        for line in redact_sensitive(completed.stderr).splitlines()
        if line.strip()
    ]
    return f": {lines[-1][:300]}" if lines else ""


def require_success(
    completed: subprocess.CompletedProcess[str], description: str
) -> subprocess.CompletedProcess[str]:
    if completed.returncode != 0:
        raise ReviewBridgeError(
            f"{description} failed with exit code {completed.returncode}"
            f"{safe_failure_detail(completed)}"
        )
    return completed


def parse_json_object(raw: str, description: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReviewBridgeError(f"{description} returned malformed JSON") from error
    if not isinstance(parsed, dict):
        raise ReviewBridgeError(f"{description} returned JSON that is not an object")
    return parsed


class GitHubClient:
    def __init__(self, runner: Runner, cwd: Path) -> None:
        self.runner = runner
        self.cwd = cwd

    def repository(self) -> str:
        completed = require_success(
            self.runner.run(
                ("gh", "repo", "view", "--json", "nameWithOwner"), cwd=self.cwd
            ),
            "GitHub repository lookup",
        )
        payload = parse_json_object(completed.stdout, "GitHub repository lookup")
        name = payload.get("nameWithOwner")
        if not isinstance(name, str) or not re.fullmatch(r"[^/\s]+/[^/\s]+", name):
            raise ReviewBridgeError("GitHub repository lookup returned malformed metadata")
        return name

    def pr_metadata(self, repository: str, pr_number: int) -> PRMetadata:
        completed = require_success(
            self.runner.run(
                (
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--repo",
                    repository,
                    "--json",
                    "number,state,headRefOid,baseRefOid,headRefName,baseRefName,url",
                ),
                cwd=self.cwd,
            ),
            f"GitHub PR #{pr_number} lookup",
        )
        payload = parse_json_object(completed.stdout, f"GitHub PR #{pr_number} lookup")
        fields = {
            "number": payload.get("number"),
            "state": payload.get("state"),
            "head_sha": payload.get("headRefOid"),
            "base_sha": payload.get("baseRefOid"),
            "head_ref": payload.get("headRefName"),
            "base_ref": payload.get("baseRefName"),
            "url": payload.get("url"),
        }
        if isinstance(fields["number"], bool) or not isinstance(fields["number"], int):
            raise ReviewBridgeError("GitHub returned a malformed PR number")
        for key in ("state", "head_sha", "base_sha", "head_ref", "base_ref", "url"):
            if not isinstance(fields[key], str) or not fields[key]:
                raise ReviewBridgeError(f"GitHub returned malformed PR metadata: {key}")
        if not SHA_PATTERN.fullmatch(str(fields["head_sha"])) or not SHA_PATTERN.fullmatch(
            str(fields["base_sha"])
        ):
            raise ReviewBridgeError("GitHub returned a malformed PR head or base SHA")
        return PRMetadata(**fields)  # type: ignore[arg-type]

    def post_comment(self, repository: str, pr_number: int, body: str) -> tuple[int, str]:
        payload = json.dumps({"body": body})
        completed = require_success(
            self.runner.run(
                (
                    "gh",
                    "api",
                    "--method",
                    "POST",
                    f"repos/{repository}/issues/{pr_number}/comments",
                    "--input",
                    "-",
                ),
                cwd=self.cwd,
                input_text=payload,
            ),
            f"GitHub PR #{pr_number} comment post",
        )
        response = parse_json_object(completed.stdout, "GitHub comment post")
        comment_id = response.get("id")
        url = response.get("html_url")
        if isinstance(comment_id, bool) or not isinstance(comment_id, int):
            raise ReviewBridgeError("GitHub comment post returned a malformed comment ID")
        if not isinstance(url, str) or not url:
            raise ReviewBridgeError("GitHub comment post returned a malformed URL")
        return comment_id, url


class GitRepository:
    def __init__(
        self,
        runner: Runner,
        cwd: Path,
        *,
        temporary_parent: Path | None = None,
    ) -> None:
        self.runner = runner
        self.cwd = cwd
        self.temporary_parent = temporary_parent or (
            Path.home() / ".cache" / "kv-external-review"
        )

    def ensure_commit(self, sha: str, *, pr_number: int | None = None) -> None:
        present = self.runner.run(
            ("git", "cat-file", "-e", f"{sha}^{{commit}}"), cwd=self.cwd
        )
        if present.returncode == 0:
            return
        fetch_target = f"pull/{pr_number}/head" if pr_number is not None else sha
        require_success(
            self.runner.run(
                ("git", "fetch", "--no-tags", "origin", fetch_target), cwd=self.cwd
            ),
            f"read-only fetch for commit {sha}",
        )
        require_success(
            self.runner.run(
                ("git", "cat-file", "-e", f"{sha}^{{commit}}"), cwd=self.cwd
            ),
            f"local commit verification for {sha}",
        )

    def assert_clean(self, worktree: Path, provider_name: str) -> None:
        completed = require_success(
            self.runner.run(("git", "status", "--porcelain"), cwd=worktree),
            f"{provider_name} review worktree status",
        )
        if completed.stdout.strip():
            raise ReviewBridgeError(
                f"{provider_name} modified the detached review worktree; posting was blocked"
            )

    @contextlib.contextmanager
    def detached_worktree(self, pr_number: int, head_sha: str) -> Iterator[Path]:
        self.temporary_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = Path(
            tempfile.mkdtemp(
                prefix=f"pr-{pr_number}-{head_sha[:12]}-", dir=self.temporary_parent
            )
        )
        checkout = root / "checkout"
        added = False
        active_error: BaseException | None = None
        try:
            require_success(
                self.runner.run(
                    ("git", "worktree", "add", "--detach", str(checkout), head_sha),
                    cwd=self.cwd,
                ),
                "detached review worktree creation",
            )
            added = True
            yield checkout
        except BaseException as error:
            active_error = error
            raise
        finally:
            cleanup_error: ReviewBridgeError | None = None
            if added:
                removed = self.runner.run(
                    ("git", "worktree", "remove", "--force", str(checkout)),
                    cwd=self.cwd,
                )
                if removed.returncode != 0:
                    cleanup_error = ReviewBridgeError(
                        "detached review worktree cleanup failed"
                        f"{safe_failure_detail(removed)}"
                    )
            shutil.rmtree(root, ignore_errors=True)
            if cleanup_error is not None:
                if active_error is not None:
                    raise cleanup_error from active_error
                raise cleanup_error


def scrub_github_environment(
    source: Mapping[str, str], gh_config_dir: Path
) -> dict[str, str]:
    child = dict(source)
    for variable in GITHUB_SECRET_VARIABLES:
        child.pop(variable, None)
    child["GH_CONFIG_DIR"] = str(gh_config_dir)
    return child


def first_output_line(text: str, fallback: str) -> str:
    for line in redact_sensitive(text).splitlines():
        if line.strip():
            return line.strip()[:160]
    return fallback


def extract_contract(output: str, provider_name: str) -> tuple[dict[str, object], str | None]:
    outer = parse_json_object(output, f"{provider_name} provider")
    model_metadata: str | None = None
    for key in ("model", "model_id", "modelId"):
        value = outer.get(key)
        if isinstance(value, str) and value.strip():
            model_metadata = value.strip()[:160]
            break
    if model_metadata is None:
        model_usage = outer.get("modelUsage")
        if isinstance(model_usage, dict) and len(model_usage) == 1:
            only_model = next(iter(model_usage))
            if isinstance(only_model, str) and only_model:
                model_metadata = only_model[:160]

    required = {"pr_number", "head_sha", "verdict", "body_markdown"}
    if required.issubset(outer):
        return outer, None

    for key in ("structured_output", "output"):
        candidate = outer.get(key)
        if isinstance(candidate, dict):
            return candidate, model_metadata
        if isinstance(candidate, str):
            parsed = parse_json_object(candidate, f"{provider_name} structured output")
            return parsed, model_metadata
    for key in ("result", "text"):
        candidate = outer.get(key)
        if isinstance(candidate, str):
            parsed = parse_json_object(candidate, f"{provider_name} structured output")
            return parsed, model_metadata
    raise ReviewBridgeError(f"{provider_name} provider JSON omitted structured review output")


def review_result_from_contract(contract: Mapping[str, object]) -> ReviewResult:
    allowed = {
        "pr_number",
        "head_sha",
        "verdict",
        "body_markdown",
        "provider",
        "reviewer",
        "model",
    }
    unexpected = sorted(set(contract) - allowed)
    if unexpected:
        raise ReviewBridgeError(
            f"provider review output contained unsupported fields: {', '.join(unexpected)}"
        )
    pr_number = contract.get("pr_number")
    head_sha = contract.get("head_sha")
    verdict = contract.get("verdict")
    body = contract.get("body_markdown")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise ReviewBridgeError("provider review output contained a malformed PR number")
    if not isinstance(head_sha, str) or not SHA_PATTERN.fullmatch(head_sha):
        raise ReviewBridgeError("provider review output contained a malformed head SHA")
    if not isinstance(verdict, str) or verdict not in VERDICTS:
        raise ReviewBridgeError("provider review output contained a malformed verdict")
    if not isinstance(body, str) or not body.strip():
        raise ReviewBridgeError("provider review output contained an empty review body")
    optional: dict[str, str | None] = {}
    for key in ("provider", "reviewer", "model"):
        value = contract.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ReviewBridgeError(f"provider review output contained a malformed {key}")
        optional[key] = value.strip() if isinstance(value, str) else None
    return ReviewResult(
        pr_number=pr_number,
        head_sha=head_sha.lower(),
        verdict=verdict,
        body_markdown=body.strip(),
        provider_claim=optional["provider"],
        reviewer_claim=optional["reviewer"],
        model_claim=optional["model"],
    )


class ProviderAdapter:
    def __init__(
        self,
        spec: ProviderSpec,
        runner: Runner,
        *,
        source_environment: Mapping[str, str] | None = None,
    ) -> None:
        self.spec = spec
        self.runner = runner
        self.source_environment = source_environment

    def run(self, worktree: Path, prompt: str) -> ProviderExecution:
        with tempfile.TemporaryDirectory(prefix=f"kv-{self.spec.key}-review-") as temp:
            temp_path = Path(temp)
            gh_config = temp_path / "empty-gh-config"
            gh_config.mkdir(mode=0o700)
            source = self.source_environment if self.source_environment is not None else os.environ
            child_env = scrub_github_environment(source, gh_config)
            if self.spec.key == "grok":
                original_home = Path(source.get("HOME", str(Path.home())))
                original_grok_home = Path(
                    source.get("GROK_HOME", str(original_home / ".grok"))
                )
                child_env["GROK_HOME"] = str(temp_path / "grok-home")
                child_env["GROK_AUTH_PATH"] = source.get(
                    "GROK_AUTH_PATH", str(original_grok_home / "auth.json")
                )
                child_env["GROK_SESSION_REGISTRY"] = "0"
                child_env["GROK_SESSION_SEARCH"] = "0"
            version = require_success(
                self.runner.run(
                    (self.spec.executable, "--version"),
                    cwd=worktree,
                    env=child_env,
                    timeout=30,
                ),
                f"{self.spec.display_name} version lookup",
            )
            cli_version = first_output_line(version.stdout or version.stderr, "unknown")
            if self.spec.key == "claude":
                command = self._claude_command()
                completed = self.runner.run(
                    command,
                    cwd=worktree,
                    env=child_env,
                    input_text=prompt,
                    timeout=3600,
                )
            else:
                self._validate_grok_configuration(worktree, child_env)
                prompt_file = temp_path / "review-prompt.md"
                prompt_file.write_text(prompt, encoding="utf-8")
                command = self._grok_command(worktree, prompt_file)
                completed = self.runner.run(
                    command,
                    cwd=worktree,
                    env=child_env,
                    timeout=3600,
                )
            if completed.returncode != 0:
                raise ReviewBridgeError(
                    f"{self.spec.display_name} provider failed with exit code "
                    f"{completed.returncode}{safe_failure_detail(completed)}"
                )
            contract, model_metadata = extract_contract(
                completed.stdout, self.spec.display_name
            )
            return ProviderExecution(
                result=review_result_from_contract(contract),
                cli_version=cli_version,
                model_metadata=model_metadata,
            )

    def _validate_grok_configuration(
        self, worktree: Path, child_env: Mapping[str, str]
    ) -> None:
        inspected = require_success(
            self.runner.run(
                (
                    "grok",
                    "--no-auto-update",
                    "--no-memory",
                    "--cwd",
                    str(worktree),
                    "inspect",
                    "--json",
                ),
                cwd=worktree,
                env=child_env,
                timeout=30,
            ),
            "Grok configuration inspection",
        )
        payload = parse_json_object(inspected.stdout, "Grok configuration inspection")
        active: list[str] = []
        for key in (
            "projectInstructions",
            "hooks",
            "skills",
            "plugins",
            "mcpServers",
        ):
            if payload.get(key):
                active.append(key)
        permissions = payload.get("permissions")
        if isinstance(permissions, dict) and permissions.get("sources"):
            active.append("permission sources")
        if active:
            raise ReviewBridgeError(
                "Grok discovered active review customizations "
                f"({', '.join(active)}); posting was blocked"
            )

    @staticmethod
    def _claude_command() -> tuple[str, ...]:
        allowed = ",".join(
            (
                "Read",
                "Grep",
                "Glob",
                "Bash(git diff *)",
                "Bash(git show *)",
                "Bash(git log *)",
                "Bash(git status *)",
                "Bash(git rev-parse *)",
                "Bash(git grep *)",
            )
        )
        return (
            "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            REVIEW_SCHEMA_JSON,
            "--permission-mode",
            "dontAsk",
            "--tools",
            "Read,Grep,Glob,Bash",
            "--allowedTools",
            allowed,
            "--disallowedTools",
            "Edit,Write,NotebookEdit,WebFetch,WebSearch,Agent",
            "--safe-mode",
            "--disable-slash-commands",
            "--no-chrome",
            "--no-session-persistence",
            "--max-turns",
            "30",
        )

    @staticmethod
    def _grok_command(worktree: Path, prompt_file: Path) -> tuple[str, ...]:
        command = [
            "grok",
            "--no-auto-update",
            "--no-memory",
            "--cwd",
            str(worktree),
            "--prompt-file",
            str(prompt_file),
            "--output-format",
            "json",
            "--json-schema",
            REVIEW_SCHEMA_JSON,
            "--permission-mode",
            "dontAsk",
            "--sandbox",
            "read-only",
            "--no-subagents",
            "--disable-web-search",
            "--max-turns",
            "30",
        ]
        for rule in (
            "Read",
            "Grep",
            "Bash(git diff *)",
            "Bash(git show *)",
            "Bash(git log *)",
            "Bash(git status *)",
            "Bash(git rev-parse *)",
            "Bash(git grep *)",
        ):
            command.extend(("--allow", rule))
        for rule in (
            "Edit",
            "MCPTool",
            "WebFetch",
            "WebSearch",
            "Bash(gh *)",
            "Bash(git push *)",
            "Bash(git fetch *)",
            "Bash(git checkout *)",
            "Bash(git switch *)",
            "Bash(git branch *)",
            "Bash(git tag *)",
            "Bash(git reset *)",
            "Bash(git clean *)",
            "Bash(git commit *)",
            "Bash(git merge *)",
            "Bash(git rebase *)",
            "Bash(git worktree *)",
        ):
            command.extend(("--deny", rule))
        return tuple(command)


KNOWN_IDENTITIES = {
    "claude": re.compile(r"(?i)(?:\bclaude\b|\banthropic\b)"),
    "grok": re.compile(r"(?i)(?:\bgrok\b|\bxai\b|\bx\.ai\b|\bspacexai\b)"),
}
HEADER_CLAIM = re.compile(
    r"^\s{0,3}#{1,6}\s+External exact-head review\s+[—-]\s+(.+?)\s*$",
    re.IGNORECASE,
)
FIELD_CLAIM = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*|__)?"
    r"(reviewer|provider|model|pr(?:\s+number)?|head(?:\s+sha)?|exact\s+reviewed\s+head|verdict|review\s+role)"
    r"(?:\*\*|__)?\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
TABLE_CLAIM = re.compile(
    r"^\s*\|\s*(reviewer|provider|model|pr(?:\s+number)?|head(?:\s+sha)?|exact\s+reviewed\s+head|verdict|review\s+role)\s*\|\s*(.*?)\s*\|\s*$",
    re.IGNORECASE,
)


def clean_claim_value(value: str) -> str:
    return value.strip().strip("`*_ ")


def validate_identity_claim(value: str, selected_provider: str, label: str) -> None:
    identities = {
        key for key, pattern in KNOWN_IDENTITIES.items() if pattern.search(value)
    }
    if identities != {selected_provider}:
        raise ReviewBridgeError(
            f"{label} identity conflicts with invoked provider {selected_provider}"
        )


def validate_model_claim(value: str, selected_provider: str) -> None:
    identities = {
        key for key, pattern in KNOWN_IDENTITIES.items() if pattern.search(value)
    }
    if identities and identities != {selected_provider}:
        raise ReviewBridgeError(
            f"model identity conflicts with invoked provider {selected_provider}"
        )


def validate_and_strip_body_claims(
    body: str,
    *,
    provider: ProviderSpec,
    pr_number: int,
    head_sha: str,
    verdict: str,
) -> str:
    kept: list[str] = []
    for line in body.splitlines():
        header = HEADER_CLAIM.match(line)
        if header:
            validate_identity_claim(header.group(1), provider.key, "reviewer")
            continue
        claim_line = line.replace("**", "").replace("__", "")
        field = FIELD_CLAIM.match(claim_line) or TABLE_CLAIM.match(claim_line)
        if not field:
            kept.append(line)
            continue
        label = re.sub(r"\s+", " ", field.group(1).lower()).strip()
        value = clean_claim_value(field.group(2))
        if label in ("reviewer", "provider"):
            validate_identity_claim(value, provider.key, label)
        elif label == "model":
            validate_model_claim(value, provider.key)
        elif label.startswith("pr"):
            if not re.fullmatch(rf"#?{pr_number}", value):
                raise ReviewBridgeError("review body PR identity conflicts with invoked PR")
        elif label in ("head", "head sha", "exact reviewed head"):
            if value.lower() != head_sha:
                raise ReviewBridgeError("review body head SHA conflicts with exact PR head")
        elif label == "verdict":
            if value.upper() != verdict:
                raise ReviewBridgeError("review body verdict conflicts with structured verdict")
        elif label == "review role":
            if value != provider.review_role:
                raise ReviewBridgeError("review body role conflicts with bridge-owned role")
        continue
    stripped = "\n".join(kept).strip()
    if not stripped:
        raise ReviewBridgeError("review body was empty after removing redundant metadata")
    return stripped


def validate_execution(
    execution: ProviderExecution,
    provider: ProviderSpec,
    expected_pr: int,
    expected_head: str,
) -> ProviderExecution:
    result = execution.result
    if result.pr_number != expected_pr:
        raise ReviewBridgeError(
            f"{provider.display_name} returned PR #{result.pr_number}; expected #{expected_pr}"
        )
    if result.head_sha.lower() != expected_head.lower():
        raise ReviewBridgeError(
            f"{provider.display_name} returned head {result.head_sha}; expected {expected_head}"
        )
    if result.verdict not in VERDICTS:
        raise ReviewBridgeError(f"{provider.display_name} returned an invalid verdict")
    if result.provider_claim:
        validate_identity_claim(result.provider_claim, provider.key, "provider")
    if result.reviewer_claim:
        validate_identity_claim(result.reviewer_claim, provider.key, "reviewer")
    if result.model_claim:
        validate_model_claim(result.model_claim, provider.key)
    if execution.model_metadata:
        validate_model_claim(execution.model_metadata, provider.key)
    body = validate_and_strip_body_claims(
        result.body_markdown,
        provider=provider,
        pr_number=expected_pr,
        head_sha=expected_head,
        verdict=result.verdict,
    )
    return replace(execution, result=replace(result, body_markdown=body))


def wrapped_prompt(prompt: str, metadata: PRMetadata) -> str:
    return f"""Perform an independent review of the exact detached pull-request head in your current working directory.

Caller-owned review coordinates:
- PR number: {metadata.number}
- Base SHA: {metadata.base_sha}
- Head SHA: {metadata.head_sha}
- Base ref: {metadata.base_ref}
- Head ref: {metadata.head_ref}

The working directory is detached at the exact head SHA. Inspect repository files and `git diff {metadata.base_sha}...{metadata.head_sha}` as needed. Do not modify files or repository state. Do not use GitHub write operations.

Apply the following provider-neutral review request:

<review-request>
{prompt.strip()}
</review-request>

Return only the requested machine-readable result. `pr_number` must be {metadata.number}; `head_sha` must be {metadata.head_sha}; `verdict` must be exactly PASS or FINDINGS; `body_markdown` must contain only the substantive review. Do not emit provider, reviewer, exact-head, verdict, or review-role headers in `body_markdown`. Provider identity is caller-owned metadata and must not be claimed or inferred in model prose.
"""


def markdown_inline_code(value: str) -> str:
    return f"`{value.replace('`', '').replace('|', r'\|')}`"


def render_comment(
    provider: ProviderSpec, metadata: PRMetadata, execution: ProviderExecution
) -> str:
    rows = [
        ("Provider", provider.display_name),
        ("Provider CLI", markdown_inline_code(execution.cli_version)),
    ]
    if execution.model_metadata:
        rows.append(("Model", markdown_inline_code(execution.model_metadata)))
    rows.extend(
        (
            ("PR", f"#{metadata.number}"),
            ("Exact reviewed head", markdown_inline_code(metadata.head_sha)),
            ("Verdict", f"**{execution.result.verdict}**"),
            ("Review role", provider.review_role),
        )
    )
    table = "\n".join(f"| {label} | {value} |" for label, value in rows)
    return (
        f"## External exact-head review — {provider.display_name}\n\n"
        "<!-- kv-external-review:v1 -->\n"
        "| Field | Value |\n|---|---|\n"
        f"{table}\n\n"
        "### Review body\n\n"
        f"{execution.result.body_markdown.strip()}\n"
    )


class Adapter(Protocol):
    def run(self, worktree: Path, prompt: str) -> ProviderExecution: ...


class Repository(Protocol):
    def ensure_commit(self, sha: str, *, pr_number: int | None = None) -> None: ...
    def assert_clean(self, worktree: Path, provider_name: str) -> None: ...
    def detached_worktree(self, pr_number: int, head_sha: str) -> contextlib.AbstractContextManager[Path]: ...


class GitHub(Protocol):
    def repository(self) -> str: ...
    def pr_metadata(self, repository: str, pr_number: int) -> PRMetadata: ...
    def post_comment(self, repository: str, pr_number: int, body: str) -> tuple[int, str]: ...


class ReviewBridge:
    def __init__(
        self,
        github: GitHub,
        repository: Repository,
        adapters: Mapping[str, Adapter],
        *,
        emit: Callable[[str], None] = print,
    ) -> None:
        self.github = github
        self.repository = repository
        self.adapters = adapters
        self.emit = emit

    def review(
        self, pr_number: int, provider_names: Sequence[str], prompt: str
    ) -> list[PostedComment]:
        repository_name = self.github.repository()
        metadata = self.github.pr_metadata(repository_name, pr_number)
        if metadata.number != pr_number:
            raise ReviewBridgeError("GitHub returned a different PR number")
        if metadata.state.upper() != "OPEN":
            raise ReviewBridgeError(
                f"PR #{pr_number} is {metadata.state}; only open PRs are supported"
            )
        self.emit(f"Exact head: {metadata.head_sha}")
        self.repository.ensure_commit(metadata.base_sha)
        self.repository.ensure_commit(metadata.head_sha, pr_number=pr_number)
        prompt_text = wrapped_prompt(prompt, metadata)
        validated: list[tuple[ProviderSpec, ProviderExecution]] = []
        with self.repository.detached_worktree(pr_number, metadata.head_sha) as worktree:
            for provider_name in provider_names:
                spec = PROVIDER_SPECS[provider_name]
                adapter = self.adapters[provider_name]
                self.emit(f"{spec.display_name}: started")
                execution = validate_execution(
                    adapter.run(worktree, prompt_text),
                    spec,
                    pr_number,
                    metadata.head_sha,
                )
                self.repository.assert_clean(worktree, spec.display_name)
                self.emit(
                    f"{spec.display_name}: completed ({execution.result.verdict})"
                )
                validated.append((spec, execution))

        live = self.github.pr_metadata(repository_name, pr_number)
        if live.state.upper() != "OPEN":
            raise ReviewBridgeError(
                f"PR #{pr_number} is no longer open; posting was blocked"
            )
        if live.head_sha.lower() != metadata.head_sha.lower():
            raise ReviewBridgeError(
                f"PR #{pr_number} head moved from {metadata.head_sha} to {live.head_sha}; "
                "stale review was not posted"
            )
        self.emit(f"Head revalidated: {metadata.head_sha}")

        posted: list[PostedComment] = []
        for spec, execution in validated:
            comment_id, url = self.github.post_comment(
                repository_name,
                pr_number,
                render_comment(spec, metadata, execution),
            )
            self.emit(f"{spec.display_name}: posted {url}")
            posted.append(
                PostedComment(provider=spec.key, comment_id=comment_id, url=url)
            )
        return posted


def doctor(runner: Runner, cwd: Path) -> tuple[bool, list[str]]:
    lines: list[str] = []
    healthy = True

    def safe_run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            return runner.run(args, cwd=cwd, timeout=30)
        except ReviewBridgeError:
            return subprocess.CompletedProcess(tuple(args), 127, "", "")

    def version_check(command: str, label: str) -> bool:
        nonlocal healthy
        completed = safe_run((command, "--version"))
        if completed.returncode != 0:
            lines.append(f"FAIL {label}: unavailable")
            healthy = False
            return False
        lines.append(
            f"OK   {label}: {first_output_line(completed.stdout or completed.stderr, 'available')}"
        )
        return True

    git_available = version_check("git", "git")
    gh_available = version_check("gh", "gh")
    gh_auth = (
        safe_run(("gh", "auth", "status"))
        if gh_available
        else subprocess.CompletedProcess(("gh",), 127, "", "")
    )
    if gh_available and gh_auth.returncode == 0:
        lines.append("OK   GitHub authentication: authenticated")
    else:
        lines.append("FAIL GitHub authentication: run `gh auth login`")
        healthy = False

    repo = (
        safe_run(("git", "rev-parse", "--show-toplevel"))
        if git_available
        else subprocess.CompletedProcess(("git",), 127, "", "")
    )
    gh_repo = (
        safe_run(("gh", "repo", "view", "--json", "nameWithOwner"))
        if gh_available and gh_auth.returncode == 0
        else subprocess.CompletedProcess(("gh",), 127, "", "")
    )
    repository_name: str | None = None
    if gh_repo.returncode == 0:
        try:
            repo_payload = json.loads(gh_repo.stdout)
        except json.JSONDecodeError:
            repo_payload = None
        if isinstance(repo_payload, dict) and isinstance(
            repo_payload.get("nameWithOwner"), str
        ):
            repository_name = repo_payload["nameWithOwner"]
    if repo.returncode == 0 and repo.stdout.strip() and repository_name:
        lines.append(
            f"OK   repository context: {repo.stdout.strip()} ({repository_name})"
        )
    else:
        lines.append("FAIL repository context: run inside a GitHub repository")
        healthy = False

    claude_available = version_check("claude", "Claude Code")
    claude_auth = (
        safe_run(("claude", "auth", "status"))
        if claude_available
        else subprocess.CompletedProcess(("claude",), 127, "", "")
    )
    if claude_available and claude_auth.returncode == 0:
        try:
            status = json.loads(claude_auth.stdout)
        except json.JSONDecodeError:
            status = None
        if isinstance(status, dict) and status.get("loggedIn") is True:
            lines.append("OK   Claude authentication: authenticated")
        else:
            lines.append("FAIL Claude authentication: run `claude auth login`")
            healthy = False
    else:
        lines.append("FAIL Claude authentication: run `claude auth login`")
        healthy = False

    grok_available = version_check("grok", "Grok Build")
    grok_auth = (
        safe_run(("grok", "--no-auto-update", "models"))
        if grok_available
        else subprocess.CompletedProcess(("grok",), 127, "", "")
    )
    grok_probe = ANSI_PATTERN.sub("", grok_auth.stdout + "\n" + grok_auth.stderr)
    grok_auth_failed = (
        not grok_available
        or grok_auth.returncode != 0
        or "not authenticated" in grok_probe.lower()
        or "no auth credentials" in grok_probe.lower()
        or "failed to fetch models" in grok_probe.lower()
        or "auth(" in grok_probe.lower()
    )
    if grok_auth_failed:
        lines.append("FAIL Grok authentication: run `grok login --device-auth`")
        healthy = False
    else:
        lines.append("OK   Grok authentication: authenticated model access")

    return healthy, [redact_sensitive(line) for line in lines]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Post provider-bound exact-head reviews to GitHub"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check local tools, auth, and repository context")
    review = subparsers.add_parser("review", help="run and post an exact-head PR review")
    review.add_argument("--pr", type=int, required=True, help="open pull request number")
    review.add_argument(
        "--provider", choices=("claude", "grok", "all"), required=True
    )
    review.add_argument(
        "--prompt-file", type=Path, required=True, help="provider-neutral review request"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = SubprocessRunner()
    cwd = Path.cwd()
    try:
        if args.command == "doctor":
            healthy, lines = doctor(runner, cwd)
            print("\n".join(lines))
            return 0 if healthy else 1
        if args.pr < 1:
            raise ReviewBridgeError("--pr must be a positive integer")
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ReviewBridgeError(
                f"could not read prompt file: {args.prompt_file}"
            ) from error
        if not prompt.strip():
            raise ReviewBridgeError("prompt file is empty")
        github = GitHubClient(runner, cwd)
        repository = GitRepository(runner, cwd)
        adapters = {
            key: ProviderAdapter(spec, runner) for key, spec in PROVIDER_SPECS.items()
        }
        providers = ("claude", "grok") if args.provider == "all" else (args.provider,)
        ReviewBridge(github, repository, adapters).review(args.pr, providers, prompt)
        return 0
    except ReviewBridgeError as error:
        print(f"error: {redact_sensitive(str(error))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

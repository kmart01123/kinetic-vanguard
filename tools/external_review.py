#!/usr/bin/env python3
"""Run provider-bound exact-head reviews and post validated PR comments."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, replace
from typing import Callable, Iterator, Mapping, Protocol, Sequence


SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SENSITIVE_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}\b"),
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
FINDING_SEVERITIES = frozenset(("BLOCKER", "HIGH", "MEDIUM", "LOW"))
GROK_BUILD_MODEL_PATTERN = re.compile(
    r"^grok(?:-[0-9]+(?:\.[0-9]+)*)?-build$", re.IGNORECASE
)
GROK_DEFAULT_MODEL_PATTERN = re.compile(
    r"^Default model:\s*([A-Za-z0-9._-]+)\s*$", re.MULTILINE
)
GROK_AVAILABLE_MODEL_PATTERN = re.compile(
    r"^\s*[*-]\s+([A-Za-z0-9._-]+)(?:\s+\(default\))?\s*$", re.MULTILINE
)
GROK_SANDBOX_PROFILE = "kv-external-review"
GROK_SANDBOX_FAILURE_PATTERN = re.compile(
    r"(?:sandbox could not be applied|failed to apply sandbox|unknown sandbox profile)",
    re.IGNORECASE,
)
NON_FINAL_REVIEW_PATTERNS = (
    re.compile(r"\b(?:the )?review(?: request)? is being processed\b"),
    re.compile(
        r"\bplaceholder(?: \w+){0,3} (?:while|until)"
        r"(?: \w+){0,8} review(?: \w+){0,3}"
        r" (?:complete|completed|completion)\b"
    ),
    re.compile(
        r"\bplaceholder(?: \w+){0,3} (?:awaiting|pending)"
        r"(?: \w+){0,4} (?:review )?completion\b"
    ),
)
BROAD_GROK_AUTH_DIRECTORIES = frozenset(
    Path(path)
    for path in (
        "/",
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/lib64",
        "/media",
        "/mnt",
        "/opt",
        "/proc",
        "/run",
        "/sbin",
        "/srv",
        "/sys",
        "/tmp",
        "/usr",
        "/var",
        "/var/tmp",
    )
)
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "pr_number": {"type": "integer", "minimum": 1},
        "head_sha": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$"},
        "verdict": {"type": "string", "enum": sorted(VERDICTS)},
        "body_markdown": {"type": "string", "minLength": 1},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": sorted(FINDING_SEVERITIES),
                    },
                    "title": {"type": "string", "minLength": 1},
                    "detail": {"type": "string", "minLength": 1},
                },
                "required": ["severity", "title", "detail"],
                "additionalProperties": False,
            },
        },
        "provider": {"type": "string"},
        "reviewer": {"type": "string"},
        "model": {"type": "string"},
    },
    "required": ["pr_number", "head_sha", "verdict", "body_markdown", "findings"],
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
class ReviewFinding:
    severity: str
    title: str
    detail: str


@dataclass(frozen=True)
class ReviewResult:
    pr_number: int
    head_sha: str
    verdict: str
    body_markdown: str
    findings: tuple[ReviewFinding, ...]
    provider_claim: str | None = None
    reviewer_claim: str | None = None
    model_claim: str | None = None


@dataclass(frozen=True)
class ProviderExecution:
    result: ReviewResult
    cli_version: str
    model_metadata: str | None = None
    requested_model: str | None = None


@dataclass(frozen=True)
class GrokSandboxProfile:
    name: str
    auth_file: Path
    read_only_directory: Path
    config_file: Path


@dataclass(frozen=True)
class ClaudeIsolationConfig:
    settings_file: Path
    mcp_config_file: Path


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

REQUIRED_CLI_CAPABILITIES = {
    "claude": (
        ("structured JSON schema output", ("--json-schema",)),
        ("machine-readable output", ("--output-format",)),
        ("noninteractive permission mode", ("--permission-mode",)),
        ("tool allow list", ("--allowedTools",)),
        ("tool deny list", ("--disallowedTools",)),
        ("tool surface restriction", ("--tools",)),
        ("customization isolation", ("--safe-mode",)),
        ("slash-command disabling", ("--disable-slash-commands",)),
        ("browser integration disabling", ("--no-chrome",)),
        ("setting-source isolation", ("--setting-sources",)),
        ("wrapper-owned settings", ("--settings",)),
        ("strict MCP isolation", ("--strict-mcp-config",)),
        ("wrapper-owned MCP configuration", ("--mcp-config",)),
        ("session persistence disabling", ("--no-session-persistence",)),
        ("explicit model selection", ("--model",)),
    ),
    "grok": (
        ("structured JSON schema output", ("--json-schema",)),
        ("machine-readable output", ("--output-format",)),
        ("noninteractive permission mode", ("--permission-mode",)),
        ("read-only sandbox", ("--sandbox",)),
        ("tool allow rules", ("--allow",)),
        ("tool deny rules", ("--deny",)),
        ("tool surface restriction", ("--tools",)),
        ("web disabling", ("--disable-web-search",)),
        ("subagent disabling", ("--no-subagents",)),
        ("prompt-file input", ("--prompt-file",)),
        ("explicit model selection", ("--model",)),
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


def validate_cli_capabilities(provider_key: str, help_output: str) -> None:
    normalized = ANSI_PATTERN.sub("", help_output)

    def has_exact_option(spelling: str) -> bool:
        return re.search(
            rf"(?<![A-Za-z0-9_-]){re.escape(spelling)}(?![A-Za-z0-9_-])",
            normalized,
        ) is not None

    missing = [
        label
        for label, spellings in REQUIRED_CLI_CAPABILITIES[provider_key]
        if not any(has_exact_option(spelling) for spelling in spellings)
    ]
    if missing:
        display_name = PROVIDER_SPECS[provider_key].display_name
        raise ReviewBridgeError(
            f"{display_name} CLI lacks required safety capabilities: "
            f"{', '.join(missing)}"
        )


def resolve_provider_executable(
    spec: ProviderSpec,
    source_environment: Mapping[str, str],
    *,
    review_worktree: Path | None = None,
) -> tuple[Path, str]:
    safe_directories = [
        entry
        for entry in source_environment.get("PATH", "").split(os.pathsep)
        if entry and Path(entry).is_absolute()
    ]
    if not safe_directories:
        raise ReviewBridgeError(
            f"safe {spec.display_name} executable is unavailable"
        )
    safe_path = os.pathsep.join(safe_directories)
    located = shutil.which(spec.executable, path=safe_path)
    if located is None:
        raise ReviewBridgeError(
            f"safe {spec.display_name} executable is unavailable"
        )
    candidate = Path(located)
    if not candidate.is_absolute():
        raise ReviewBridgeError(
            f"safe {spec.display_name} executable did not resolve absolutely"
        )
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ReviewBridgeError(
            f"safe {spec.display_name} executable is unavailable"
        ) from error
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ReviewBridgeError(
            f"safe {spec.display_name} executable is not executable"
        )
    if review_worktree is not None:
        worktree = review_worktree.resolve(strict=False)
        if resolved.is_relative_to(worktree):
            raise ReviewBridgeError(
                f"{spec.display_name} executable resolves inside the review worktree"
            )
    return resolved, safe_path


def select_grok_request_model(models_output: str) -> str:
    normalized = ANSI_PATTERN.sub("", models_output)
    available = set(GROK_AVAILABLE_MODEL_PATTERN.findall(normalized))
    if "grok-build" in available:
        return "grok-build"
    default_match = GROK_DEFAULT_MODEL_PATTERN.search(normalized)
    if default_match is None:
        raise ReviewBridgeError("Grok model listing omitted a default model")
    default_model = default_match.group(1)
    if default_model not in available:
        raise ReviewBridgeError("Grok default model was absent from available models")
    return default_model


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

    def base_to_head_diff(self, base_sha: str, head_sha: str) -> str:
        completed = require_success(
            self.runner.run(
                (
                    "git",
                    "diff",
                    "--no-ext-diff",
                    "--no-color",
                    "--binary",
                    "--find-renames",
                    f"{base_sha}...{head_sha}",
                    "--",
                ),
                cwd=self.cwd,
            ),
            "base-to-head diff generation",
        )
        return completed.stdout

    def assert_clean(self, worktree: Path, provider_name: str) -> None:
        completed = require_success(
            self.runner.run(("git", "status", "--porcelain"), cwd=worktree),
            f"{provider_name} review worktree status",
        )
        if completed.stdout.strip():
            raise ReviewBridgeError(
                f"{provider_name} modified the detached review worktree; posting was blocked"
            )

    def validate_worktree_symlinks(self, worktree: Path) -> None:
        validate_worktree_symlinks(worktree)

    @contextlib.contextmanager
    def detached_worktree(self, pr_number: int, head_sha: str) -> Iterator[Path]:
        try:
            self.temporary_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            root = Path(
                tempfile.mkdtemp(
                    prefix=f"pr-{pr_number}-{head_sha[:12]}-",
                    dir=self.temporary_parent,
                )
            )
        except OSError as error:
            raise ReviewBridgeError(
                "could not create the temporary detached review worktree"
            ) from error
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


def validate_worktree_symlinks(worktree: Path) -> None:
    try:
        root = worktree.resolve(strict=True)
    except OSError as error:
        raise ReviewBridgeError("detached review worktree is unavailable") from error

    def fail_walk(error: OSError) -> None:
        raise ReviewBridgeError(
            "detached review worktree could not be inspected safely"
        ) from error

    for directory, directory_names, file_names in os.walk(
        root, followlinks=False, onerror=fail_walk
    ):
        for name in (*directory_names, *file_names):
            candidate = Path(directory) / name
            if not candidate.is_symlink():
                continue
            try:
                target = candidate.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                relative = candidate.relative_to(root)
                raise ReviewBridgeError(
                    f"repository symlink is broken or unresolvable: {relative}"
                ) from error
            if not target.is_relative_to(root):
                relative = candidate.relative_to(root)
                raise ReviewBridgeError(
                    f"repository symlink escapes detached worktree: {relative}"
                )


def resolve_grok_auth_file(source: Mapping[str, str]) -> Path:
    original_home = Path(source.get("HOME", str(Path.home())))
    original_grok_home = Path(
        source.get("GROK_HOME", str(original_home / ".grok"))
    )
    configured = Path(
        source.get("GROK_AUTH_PATH", str(original_grok_home / "auth.json"))
    ).expanduser()
    try:
        resolved = configured.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ReviewBridgeError(
            "Grok authentication file is missing or unresolvable"
        ) from error
    if not resolved.is_file():
        raise ReviewBridgeError("Grok authentication path is not a regular file")
    if not os.access(resolved, os.R_OK):
        raise ReviewBridgeError("Grok authentication file is not readable")
    path_text = resolved.as_posix()
    if (
        path_text.strip() != path_text
        or any(character in path_text for character in "\r\n\x00)")
        or any(character in path_text for character in "*?[")
    ):
        raise ReviewBridgeError(
            "Grok authentication path cannot be represented safely in sandbox rules"
        )
    return resolved


def validate_grok_auth_directory(
    auth_file: Path,
    source: Mapping[str, str],
    worktree: Path,
) -> Path:
    auth_directory = auth_file.parent.resolve(strict=False)
    configured_home = Path(source.get("HOME", str(Path.home()))).expanduser()
    home = configured_home.resolve(strict=False)
    review_worktree = worktree.resolve(strict=False)
    if auth_directory in BROAD_GROK_AUTH_DIRECTORIES or auth_directory == home:
        raise ReviewBridgeError(
            "Grok authentication file must use a bounded credential directory"
        )
    if auth_directory.is_relative_to(review_worktree) or review_worktree.is_relative_to(
        auth_directory
    ):
        raise ReviewBridgeError(
            "Grok authentication directory must be separate from the review worktree"
        )
    return auth_directory


def write_claude_isolation_config(root: Path) -> ClaudeIsolationConfig:
    settings_file = root / "claude-review-settings.json"
    mcp_config_file = root / "claude-review-mcp.json"
    try:
        settings_file.write_text(
            json.dumps(
                {
                    "disableAllHooks": True,
                    "autoMemoryEnabled": False,
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        settings_file.chmod(0o600)
        mcp_config_file.write_text(
            json.dumps({"mcpServers": {}}, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        mcp_config_file.chmod(0o600)
    except OSError as error:
        raise ReviewBridgeError(
            "could not create temporary Claude isolation configuration"
        ) from error
    return ClaudeIsolationConfig(
        settings_file=settings_file,
        mcp_config_file=mcp_config_file,
    )


def write_grok_sandbox_profile(
    grok_home: Path, auth_file: Path, read_only_directory: Path
) -> GrokSandboxProfile:
    try:
        grok_home.mkdir(mode=0o700)
        config_file = grok_home / "sandbox.toml"
        config_file.write_text(
            f"[profiles.{GROK_SANDBOX_PROFILE}]\n"
            'extends = "strict"\n'
            f"read_only = [{json.dumps(read_only_directory.as_posix())}]\n",
            encoding="utf-8",
        )
        config_file.chmod(0o600)
    except OSError as error:
        raise ReviewBridgeError(
            "could not create the temporary Grok sandbox profile"
        ) from error
    return GrokSandboxProfile(
        name=GROK_SANDBOX_PROFILE,
        auth_file=auth_file,
        read_only_directory=read_only_directory,
        config_file=config_file,
    )


def require_grok_sandbox_applied(
    completed: subprocess.CompletedProcess[str], operation: str
) -> None:
    if GROK_SANDBOX_FAILURE_PATTERN.search(ANSI_PATTERN.sub("", completed.stderr)):
        raise ReviewBridgeError(
            f"{operation} could not enforce the custom Grok sandbox"
        )


def redact_review_result_value(result: ReviewResult, value: str) -> ReviewResult:
    def scrub(text: str | None) -> str | None:
        return text.replace(value, "[REDACTED]") if text is not None else None

    return replace(
        result,
        body_markdown=scrub(result.body_markdown) or "[REDACTED]",
        findings=tuple(
            replace(
                finding,
                title=scrub(finding.title) or "[REDACTED]",
                detail=scrub(finding.detail) or "[REDACTED]",
            )
            for finding in result.findings
        ),
        provider_claim=scrub(result.provider_claim),
        reviewer_claim=scrub(result.reviewer_claim),
        model_claim=scrub(result.model_claim),
    )


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
            return normalize_metadata_value(line)
    return fallback


def normalize_metadata_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:160]


def canonical_grok_model_identity(value: str) -> str:
    normalized = normalize_metadata_value(value).casefold()
    return normalized.removesuffix("-build")


def model_usage_score(usage: object) -> tuple[float, float, float]:
    if not isinstance(usage, dict):
        return (0.0, 0.0, 0.0)
    numeric: dict[str, float] = {}
    for key, value in usage.items():
        if (
            isinstance(key, str)
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        ):
            numeric[re.sub(r"[^a-z]", "", key.lower())] = float(value)
    calls = numeric.get("modelcalls", numeric.get("calls", 0.0))
    output = numeric.get("outputtokens", 0.0)
    total = numeric.get("totaltokens")
    if total is None:
        total = sum(
            value
            for key, value in numeric.items()
            if key.endswith("tokens") and key != "outputtokens"
        ) + output
    return (calls, output, total)


def select_model_usage(model_usage: object, provider_name: str) -> str | None:
    if not isinstance(model_usage, dict):
        return None
    candidates = {
        model: usage
        for model, usage in model_usage.items()
        if isinstance(model, str) and model.strip()
    }
    if not candidates:
        return None
    provider_key = provider_name.strip().lower()
    preferred: dict[str, object] = {}
    if provider_key == "claude":
        preferred = {
            model: usage
            for model, usage in candidates.items()
            if "opus" in model.lower()
        }
        if not preferred:
            preferred = {
                model: usage
                for model, usage in candidates.items()
                if detected_identities(model) == {"claude"}
            }
    elif provider_key == "grok":
        preferred = {
            model: usage
            for model, usage in candidates.items()
            if GROK_BUILD_MODEL_PATTERN.fullmatch(model.strip())
        }
        if not preferred:
            preferred = {
                model: usage
                for model, usage in candidates.items()
                if detected_identities(model) == {"grok"}
            }
    ranked = preferred or candidates
    selected = max(
        ranked,
        key=lambda model: (model_usage_score(ranked[model]), model.casefold()),
    )
    return normalize_metadata_value(selected)


def extract_contract(output: str, provider_name: str) -> tuple[dict[str, object], str | None]:
    outer = parse_json_object(output, f"{provider_name} provider")
    required = {"pr_number", "head_sha", "verdict", "body_markdown", "findings"}
    if required.issubset(outer):
        contract = dict(outer)
        for envelope_key in ("modelUsage", "model_id", "modelId"):
            contract.pop(envelope_key, None)
        return contract, None

    model_metadata: str | None = None
    for key in ("model", "model_id", "modelId"):
        value = outer.get(key)
        if isinstance(value, str) and value.strip():
            model_metadata = normalize_metadata_value(value)
            break
    if model_metadata is None:
        model_metadata = select_model_usage(outer.get("modelUsage"), provider_name)

    for key in ("structured_output", "structuredOutput", "output"):
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
        "findings",
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
    raw_findings = contract.get("findings")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise ReviewBridgeError("provider review output contained a malformed PR number")
    if not isinstance(head_sha, str) or not SHA_PATTERN.fullmatch(head_sha):
        raise ReviewBridgeError("provider review output contained a malformed head SHA")
    if not isinstance(verdict, str) or verdict not in VERDICTS:
        raise ReviewBridgeError("provider review output contained a malformed verdict")
    if not isinstance(body, str) or not body.strip():
        raise ReviewBridgeError("provider review output contained an empty review body")
    if not isinstance(raw_findings, list):
        raise ReviewBridgeError("provider review output contained malformed findings")
    findings: list[ReviewFinding] = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            raise ReviewBridgeError("provider review output contained malformed findings")
        unexpected_finding_fields = sorted(
            set(raw_finding) - {"severity", "title", "detail"}
        )
        if unexpected_finding_fields:
            raise ReviewBridgeError(
                "provider review finding contained unsupported fields: "
                f"{', '.join(unexpected_finding_fields)}"
            )
        severity = raw_finding.get("severity")
        title = raw_finding.get("title")
        detail = raw_finding.get("detail")
        if not isinstance(severity, str) or severity not in FINDING_SEVERITIES:
            raise ReviewBridgeError(
                "provider review finding contained a malformed severity"
            )
        if not isinstance(title, str) or not title.strip():
            raise ReviewBridgeError("provider review finding contained an empty title")
        if not isinstance(detail, str) or not detail.strip():
            raise ReviewBridgeError("provider review finding contained an empty detail")
        findings.append(
            ReviewFinding(
                severity=severity,
                title=re.sub(r"\s+", " ", title).strip(),
                detail=detail.strip(),
            )
        )
    if verdict == "PASS" and findings:
        raise ReviewBridgeError("PASS provider review output contained findings")
    if verdict == "FINDINGS" and not findings:
        raise ReviewBridgeError("FINDINGS provider review output contained no findings")
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
        findings=tuple(findings),
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
        source = (
            self.source_environment
            if self.source_environment is not None
            else os.environ
        )
        executable, safe_path = resolve_provider_executable(
            self.spec, source, review_worktree=worktree
        )
        try:
            temporary = tempfile.TemporaryDirectory(
                prefix=f"kv-{self.spec.key}-review-"
            )
        except OSError as error:
            raise ReviewBridgeError(
                f"could not create temporary {self.spec.display_name} review state"
            ) from error
        with temporary as temp:
            temp_path = Path(temp)
            gh_config = temp_path / "empty-gh-config"
            try:
                gh_config.mkdir(mode=0o700)
            except OSError as error:
                raise ReviewBridgeError(
                    "could not create temporary provider GitHub isolation"
                ) from error
            child_env = scrub_github_environment(source, gh_config)
            child_env["PATH"] = safe_path
            claude_isolation: ClaudeIsolationConfig | None = None
            grok_sandbox: GrokSandboxProfile | None = None
            requested_model: str | None = None
            if self.spec.key == "claude":
                claude_isolation = write_claude_isolation_config(temp_path)
                child_env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
            elif self.spec.key == "grok":
                auth_file = resolve_grok_auth_file(source)
                auth_directory = validate_grok_auth_directory(
                    auth_file, source, worktree
                )
                grok_sandbox = write_grok_sandbox_profile(
                    temp_path / "grok-home", auth_file, auth_directory
                )
                child_env["GROK_HOME"] = str(grok_sandbox.config_file.parent)
                child_env["GROK_AUTH_PATH"] = str(auth_file)
                child_env["GROK_SESSION_REGISTRY"] = "0"
                child_env["GROK_SESSION_SEARCH"] = "0"
            version_command = (
                (str(executable), "--no-auto-update", "--no-memory", "--version")
                if self.spec.key == "grok"
                else (str(executable), "--version")
            )
            version = require_success(
                self.runner.run(
                    version_command,
                    cwd=temp_path,
                    env=child_env,
                    timeout=30,
                ),
                f"{self.spec.display_name} version lookup",
            )
            cli_version = first_output_line(version.stdout or version.stderr, "unknown")
            help_result = require_success(
                self.runner.run(
                    (str(executable), "--help"),
                    cwd=temp_path,
                    env=child_env,
                    timeout=30,
                ),
                f"{self.spec.display_name} capability lookup",
            )
            validate_cli_capabilities(
                self.spec.key, help_result.stdout + "\n" + help_result.stderr
            )
            if self.spec.key == "claude":
                if claude_isolation is None:
                    raise ReviewBridgeError(
                        "Claude isolation configuration was not initialized"
                    )
                command = self._claude_command(
                    executable, worktree, claude_isolation
                )
                completed = self.runner.run(
                    command,
                    cwd=worktree,
                    env=child_env,
                    input_text=prompt,
                    timeout=3600,
                )
            else:
                if grok_sandbox is None:
                    raise ReviewBridgeError("Grok sandbox profile was not initialized")
                models = require_success(
                    self.runner.run(
                        (str(executable), "--no-auto-update", "models"),
                        cwd=temp_path,
                        env=child_env,
                        timeout=30,
                    ),
                    "Grok model lookup",
                )
                requested_model = select_grok_request_model(
                    models.stdout + "\n" + models.stderr
                )
                self._validate_grok_configuration(
                    executable,
                    worktree,
                    child_env,
                    requested_model,
                    grok_sandbox,
                )
                prompt_file = temp_path / "review-prompt.md"
                try:
                    prompt_file.write_text(prompt, encoding="utf-8")
                except OSError as error:
                    raise ReviewBridgeError(
                        "could not create the temporary Grok review prompt"
                    ) from error
                command = self._grok_command(
                    executable,
                    worktree,
                    prompt_file,
                    requested_model,
                    grok_sandbox,
                )
                completed = self.runner.run(
                    command,
                    cwd=worktree,
                    env=child_env,
                    timeout=3600,
                )
                require_grok_sandbox_applied(completed, "Grok review")
            if completed.returncode != 0:
                raise ReviewBridgeError(
                    f"{self.spec.display_name} provider failed with exit code "
                    f"{completed.returncode}{safe_failure_detail(completed)}"
                )
            contract, model_metadata = extract_contract(
                completed.stdout, self.spec.display_name
            )
            result = review_result_from_contract(contract)
            if grok_sandbox is not None:
                auth_path = grok_sandbox.auth_file.as_posix()
                result = redact_review_result_value(result, auth_path)
                if model_metadata is not None:
                    model_metadata = model_metadata.replace(auth_path, "[REDACTED]")
            return ProviderExecution(
                result=result,
                cli_version=cli_version,
                model_metadata=model_metadata,
                requested_model=requested_model,
            )

    def _validate_grok_configuration(
        self,
        executable: Path,
        worktree: Path,
        child_env: Mapping[str, str],
        requested_model: str,
        sandbox: GrokSandboxProfile,
    ) -> None:
        inspected = require_success(
            self.runner.run(
                (
                    str(executable),
                    "--no-auto-update",
                    "--no-memory",
                    *self._grok_safety_options(
                        worktree, requested_model, sandbox
                    ),
                    "inspect",
                    "--json",
                ),
                cwd=worktree,
                env=child_env,
                timeout=30,
            ),
            "Grok configuration inspection",
        )
        require_grok_sandbox_applied(inspected, "Grok configuration inspection")
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
    def _claude_command(
        executable: Path,
        worktree: Path,
        isolation: ClaudeIsolationConfig,
    ) -> tuple[str, ...]:
        resolved_worktree = worktree.resolve()
        worktree_path = resolved_worktree.as_posix()
        if not worktree_path.startswith("/"):
            raise ReviewBridgeError("Claude review worktree path is not absolute")
        settings_file = isolation.settings_file.resolve()
        mcp_config_file = isolation.mcp_config_file.resolve()
        if settings_file.is_relative_to(
            resolved_worktree
        ) or mcp_config_file.is_relative_to(resolved_worktree):
            raise ReviewBridgeError(
                "Claude isolation configuration must be outside the review worktree"
            )
        scoped_read = f"Read(//{worktree_path.lstrip('/')}/**)"
        return (
            str(executable),
            "-p",
            "--model",
            "opus",
            "--output-format",
            "json",
            "--json-schema",
            REVIEW_SCHEMA_JSON,
            "--permission-mode",
            "dontAsk",
            "--tools",
            "Read",
            "--allowedTools",
            scoped_read,
            "--disallowedTools",
            "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Agent",
            "--safe-mode",
            "--setting-sources",
            "user",
            "--settings",
            str(settings_file),
            "--strict-mcp-config",
            "--mcp-config",
            str(mcp_config_file),
            "--disable-slash-commands",
            "--no-chrome",
            "--no-session-persistence",
            "--max-turns",
            "30",
        )

    @staticmethod
    def _grok_safety_options(
        worktree: Path,
        requested_model: str,
        sandbox: GrokSandboxProfile,
    ) -> tuple[str, ...]:
        options = [
            "-m",
            requested_model,
            "--cwd",
            str(worktree),
            "--permission-mode",
            "dontAsk",
            "--tools",
            "Read,Grep",
            "--sandbox",
            sandbox.name,
            "--no-subagents",
            "--disable-web-search",
        ]
        for rule in ("Read(./**)", "Grep(./**)"):
            options.extend(("--allow", rule))
        auth_path = sandbox.auth_file.as_posix()
        auth_directory = sandbox.read_only_directory.as_posix()
        for rule in (
            f"Read({auth_directory}/**)",
            f"Grep({auth_directory}/**)",
            f"Read({auth_path})",
            f"Grep({auth_path})",
        ):
            options.extend(("--deny", rule))
        for rule in (
            "Bash",
            "Edit",
            "MCPTool",
            "WebFetch",
            "WebSearch",
        ):
            options.extend(("--deny", rule))
        return tuple(options)

    @classmethod
    def _grok_command(
        cls,
        executable: Path,
        worktree: Path,
        prompt_file: Path,
        requested_model: str,
        sandbox: GrokSandboxProfile,
    ) -> tuple[str, ...]:
        command = [
            str(executable),
            "--no-auto-update",
            "--no-memory",
            *cls._grok_safety_options(worktree, requested_model, sandbox),
            "--prompt-file",
            str(prompt_file),
            "--output-format",
            "json",
            "--json-schema",
            REVIEW_SCHEMA_JSON,
            "--max-turns",
            "30",
        ]
        return tuple(command)


KNOWN_IDENTITIES = {
    "claude": re.compile(r"(?i)(?:\bclaude\b|\banthropic\b)"),
    "grok": re.compile(r"(?i)(?:\bgrok\b|\bxai\b|\bx\.ai\b|\bspacexai\b)"),
}
TRUSTED_HEADER_PREFIX = re.compile(
    r"^External\s+exact-head\s+review\b(.*)$", re.IGNORECASE
)
FIELD_CLAIM = re.compile(
    r"^\s*(?:\*\*|__)?"
    r"(reviewer|provider|model|pr(?:\s+number)?|head(?:\s+sha)?|exact\s+reviewed\s+head|verdict|review\s+role)"
    r"(?:\*\*|__)?\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
MARKDOWN_FENCE = re.compile(r"^\s{0,3}(?:>\s*)*(`{3,}|~{3,})(.*)$")
SETEXT_UNDERLINE = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
HTML_HEADING = re.compile(
    r"^\s*<h([1-6])(?:\s[^>]*)?>(.*?)</h\1>\s*$", re.IGNORECASE
)
HTML_STRONG = re.compile(
    r"^\s*<(strong|b)(?:\s[^>]*)?>(.*?)</\1>\s*$", re.IGNORECASE
)
MARKDOWN_DASH_TRANSLATION = str.maketrans(
    {character: "-" for character in "\u00ad\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"}
)
TABLE_CLAIM = re.compile(
    r"^\s*\|\s*(reviewer|provider|model|pr(?:\s+number)?|head(?:\s+sha)?|exact\s+reviewed\s+head|verdict|review\s+role)\s*\|\s*(.*?)\s*\|\s*$",
    re.IGNORECASE,
)


def clean_claim_value(value: str) -> str:
    return value.strip().strip("`*_ ")


def normalize_markdown_claim_line(line: str) -> tuple[str, bool]:
    """Return visible claim text and whether Markdown presents it as a heading."""

    visible = unicodedata.normalize("NFKC", line).translate(
        MARKDOWN_DASH_TRANSLATION
    )
    heading_shaped = False
    while True:
        original = visible
        visible = re.sub(r"^\s*>\s?", "", visible, count=1)
        visible = re.sub(
            r"^\s*(?:[-+*]|\d+[.)])\s+", "", visible, count=1
        )
        atx = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", visible)
        if atx:
            visible = atx.group(1)
            heading_shaped = True
        if visible == original:
            break

    while True:
        html_heading = HTML_HEADING.match(visible)
        if html_heading:
            visible = html_heading.group(2)
            heading_shaped = True
            continue
        html_strong = HTML_STRONG.match(visible)
        if html_strong:
            visible = html_strong.group(2)
            heading_shaped = True
            continue
        bold_only = re.match(r"^\s*(\*\*|__)(.+)\1\s*$", visible)
        if bold_only:
            visible = bold_only.group(2)
            heading_shaped = True
            continue
        break

    return re.sub(r"\s+", " ", visible).strip(), heading_shaped


def detected_identities(value: str) -> set[str]:
    return {
        key for key, pattern in KNOWN_IDENTITIES.items() if pattern.search(value)
    }


def validate_identity_claim(
    value: str,
    selected_provider: str,
    label: str,
) -> None:
    identities = detected_identities(value)
    if identities != {selected_provider}:
        raise ReviewBridgeError(
            f"{label} identity conflicts with invoked provider {selected_provider}"
        )


def validate_model_claim(value: str, selected_provider: str) -> None:
    identities = detected_identities(value)
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
    lines = body.splitlines()
    active_fence: tuple[str, int] | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        fence = MARKDOWN_FENCE.match(line)
        if active_fence is not None:
            kept.append(line)
            if (
                fence
                and fence.group(1)[0] == active_fence[0]
                and len(fence.group(1)) >= active_fence[1]
                and not fence.group(2).strip()
            ):
                active_fence = None
            index += 1
            continue
        if fence:
            active_fence = (fence.group(1)[0], len(fence.group(1)))
            kept.append(line)
            index += 1
            continue

        claim_line, heading_shaped = normalize_markdown_claim_line(line)
        setext_heading = (
            index + 1 < len(lines)
            and SETEXT_UNDERLINE.fullmatch(lines[index + 1]) is not None
            and bool(claim_line)
        )
        if heading_shaped or setext_heading:
            wrapper_heading = TRUSTED_HEADER_PREFIX.match(claim_line)
            if wrapper_heading:
                remainder = wrapper_heading.group(1).strip()
                if not detected_identities(remainder):
                    raise ReviewBridgeError(
                        "review body contained an ambiguous wrapper-like heading"
                    )
                validate_identity_claim(remainder, provider.key, "reviewer")
                index += 2 if setext_heading else 1
                continue
        field = FIELD_CLAIM.match(claim_line) or TABLE_CLAIM.match(claim_line)
        if not field:
            kept.append(line)
            index += 1
            continue
        label = re.sub(r"\s+", " ", field.group(1).lower()).strip()
        value = clean_claim_value(field.group(2))
        if label in ("reviewer", "provider"):
            if not detected_identities(value):
                kept.append(line)
                index += 1
                continue
            validate_identity_claim(value, provider.key, label)
        elif label == "model":
            if not detected_identities(value):
                kept.append(line)
                index += 1
                continue
            validate_model_claim(value, provider.key)
        elif label.startswith("pr"):
            if not re.fullmatch(r"#?\d+", value):
                kept.append(line)
                index += 1
                continue
            if not re.fullmatch(rf"#?{pr_number}", value):
                raise ReviewBridgeError("review body PR identity conflicts with invoked PR")
        elif label in ("head", "head sha", "exact reviewed head"):
            if not SHA_PATTERN.fullmatch(value):
                kept.append(line)
                index += 1
                continue
            if value.lower() != head_sha:
                raise ReviewBridgeError("review body head SHA conflicts with exact PR head")
        elif label == "verdict":
            if value.upper() not in VERDICTS:
                kept.append(line)
                index += 1
                continue
            if value.upper() != verdict:
                raise ReviewBridgeError("review body verdict conflicts with structured verdict")
        elif label == "review role":
            known_roles = {spec.review_role for spec in PROVIDER_SPECS.values()}
            if value not in known_roles:
                kept.append(line)
                index += 1
                continue
            if value != provider.review_role:
                raise ReviewBridgeError("review body role conflicts with bridge-owned role")
        index += 1
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
    if result.verdict == "PASS" and result.findings:
        raise ReviewBridgeError(f"{provider.display_name} returned PASS with findings")
    if result.verdict == "FINDINGS" and not result.findings:
        raise ReviewBridgeError(
            f"{provider.display_name} returned FINDINGS without structured findings"
        )
    normalized_titles = [
        re.sub(
            r"[^a-z0-9]+",
            " ",
            unicodedata.normalize("NFKC", finding.title).casefold(),
        ).strip()
        for finding in result.findings
    ]
    finality_texts = (
        result.body_markdown,
        *(f"{finding.title}\n{finding.detail}" for finding in result.findings),
    )
    normalized_review_texts = [
        re.sub(
            r"[^a-z0-9]+",
            " ",
            unicodedata.normalize("NFKC", text).casefold(),
        ).strip()
        for text in finality_texts
    ]
    if "review in progress" in normalized_titles or any(
        pattern.search(text)
        for text in normalized_review_texts
        for pattern in NON_FINAL_REVIEW_PATTERNS
    ):
        raise ReviewBridgeError(
            f"{provider.display_name} returned non-final review output"
        )
    if result.provider_claim:
        validate_identity_claim(result.provider_claim, provider.key, "provider")
    if result.reviewer_claim:
        validate_identity_claim(result.reviewer_claim, provider.key, "reviewer")
    if result.model_claim:
        validate_model_claim(result.model_claim, provider.key)
    if execution.model_metadata:
        validate_model_claim(execution.model_metadata, provider.key)
    if provider.key == "grok":
        if execution.requested_model is None:
            raise ReviewBridgeError("Grok execution omitted the requested model")
        requested_model = normalize_metadata_value(execution.requested_model)
        if not requested_model:
            raise ReviewBridgeError("Grok execution omitted the requested model")
        validate_model_claim(requested_model, provider.key)
        if execution.model_metadata is None:
            raise ReviewBridgeError("Grok execution omitted model metadata")
        reported_model = normalize_metadata_value(execution.model_metadata)
        canonical_requested_model = canonical_grok_model_identity(requested_model)
        if canonical_grok_model_identity(reported_model) != canonical_requested_model:
            raise ReviewBridgeError(
                "Grok reported model identity "
                f"`{reported_model}`; requested `{requested_model}`"
            )
        if (
            result.model_claim is not None
            and canonical_grok_model_identity(result.model_claim)
            != canonical_requested_model
        ):
            raise ReviewBridgeError(
                "Grok structured model claim did not match the requested model"
            )
    body = validate_and_strip_body_claims(
        result.body_markdown,
        provider=provider,
        pr_number=expected_pr,
        head_sha=expected_head,
        verdict=result.verdict,
    )
    sanitized_findings: list[ReviewFinding] = []
    for finding in result.findings:
        title = validate_and_strip_body_claims(
            finding.title,
            provider=provider,
            pr_number=expected_pr,
            head_sha=expected_head,
            verdict=result.verdict,
        )
        detail = validate_and_strip_body_claims(
            finding.detail,
            provider=provider,
            pr_number=expected_pr,
            head_sha=expected_head,
            verdict=result.verdict,
        )
        sanitized_findings.append(
            replace(
                finding,
                title=redact_sensitive(title),
                detail=redact_sensitive(detail),
            )
        )
    return replace(
        execution,
        cli_version=normalize_metadata_value(
            redact_sensitive(execution.cli_version)
        ),
        model_metadata=(
            normalize_metadata_value(redact_sensitive(execution.model_metadata))
            if execution.model_metadata is not None
            else None
        ),
        result=replace(
            result,
            body_markdown=redact_sensitive(body),
            findings=tuple(sanitized_findings),
        ),
    )


def wrapped_prompt(prompt: str, metadata: PRMetadata, base_to_head_diff: str) -> str:
    return f"""Perform an independent review of the exact detached pull-request head in your current working directory.

Caller-owned review coordinates:
- PR number: {metadata.number}
- Base SHA: {metadata.base_sha}
- Head SHA: {metadata.head_sha}
- Base ref: {metadata.base_ref}
- Head ref: {metadata.head_ref}

The working directory is detached at the exact head SHA. Repository reads are confined to that checkout. The wrapper-generated complete base-to-head diff is included below because shell access is unavailable to the provider. Inspect repository files and that diff as needed. Do not modify files or repository state. Do not use GitHub operations.

<base-to-head-diff>
{base_to_head_diff}
</base-to-head-diff>

Apply the following provider-neutral review request:

<review-request>
{prompt.strip()}
</review-request>

Return only the requested machine-readable result. `pr_number` must be {metadata.number}; `head_sha` must be {metadata.head_sha}; `verdict` must be exactly PASS or FINDINGS; `body_markdown` must contain only the substantive review; `findings` must be an array of objects with `severity`, `title`, and `detail`. Use only BLOCKER, HIGH, MEDIUM, or LOW for `severity`. PASS requires an empty `findings` array. FINDINGS requires at least one substantive structured finding. Do not infer or manufacture structured findings from prose. Do not emit provider, reviewer, exact-head, verdict, or review-role headers in `body_markdown`. Provider identity is caller-owned metadata and must not be claimed or inferred in model prose.
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
    findings = ""
    if execution.result.findings:
        rendered_findings: list[str] = []
        for finding in execution.result.findings:
            detail = "\n".join(
                f"  {line}" if line else ""
                for line in finding.detail.splitlines()
            )
            rendered_findings.append(
                f"- **{finding.severity}: {finding.title}**\n\n{detail}"
            )
        findings = "\n\n### Structured findings\n\n" + "\n\n".join(rendered_findings)
    return (
        f"## External exact-head review — {provider.display_name}\n\n"
        "<!-- kv-external-review:v1 -->\n"
        "| Field | Value |\n|---|---|\n"
        f"{table}\n\n"
        "### Review body\n\n"
        f"{execution.result.body_markdown.strip()}"
        f"{findings}\n"
    )


class Adapter(Protocol):
    def run(self, worktree: Path, prompt: str) -> ProviderExecution: ...


class Repository(Protocol):
    def ensure_commit(self, sha: str, *, pr_number: int | None = None) -> None: ...
    def base_to_head_diff(self, base_sha: str, head_sha: str) -> str: ...
    def validate_worktree_symlinks(self, worktree: Path) -> None: ...
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
        base_to_head_diff = self.repository.base_to_head_diff(
            metadata.base_sha, metadata.head_sha
        )
        prompt_text = wrapped_prompt(prompt, metadata, base_to_head_diff)
        validated: list[tuple[ProviderSpec, ProviderExecution]] = []
        with self.repository.detached_worktree(pr_number, metadata.head_sha) as worktree:
            self.repository.validate_worktree_symlinks(worktree)
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

    def safe_run(
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return runner.run(args, cwd=cwd, env=env, timeout=30)
        except ReviewBridgeError:
            return subprocess.CompletedProcess(tuple(args), 127, "", "")

    def version_check(
        command: str,
        label: str,
        *,
        env: Mapping[str, str] | None = None,
    ) -> bool:
        nonlocal healthy
        completed = safe_run((command, "--version"), env=env)
        if completed.returncode != 0:
            lines.append(f"FAIL {label}: unavailable")
            healthy = False
            return False
        lines.append(
            f"OK   {label}: {first_output_line(completed.stdout or completed.stderr, 'available')}"
        )
        return True

    def capability_check(
        provider_key: str,
        executable: Path | None,
        env: Mapping[str, str] | None,
    ) -> bool:
        nonlocal healthy
        display_name = PROVIDER_SPECS[provider_key].display_name
        if executable is None:
            return False
        completed = safe_run((str(executable), "--help"), env=env)
        if completed.returncode != 0:
            lines.append(f"FAIL {display_name} safety capabilities: help unavailable")
            healthy = False
            return False
        try:
            validate_cli_capabilities(
                provider_key, completed.stdout + "\n" + completed.stderr
            )
        except ReviewBridgeError as error:
            lines.append(f"FAIL {display_name} safety capabilities: {error}")
            healthy = False
            return False
        lines.append(f"OK   {display_name} safety capabilities: compatible")
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

    provider_source = os.environ
    try:
        claude_executable, claude_path = resolve_provider_executable(
            PROVIDER_SPECS["claude"],
            provider_source,
            review_worktree=cwd,
        )
    except ReviewBridgeError as error:
        lines.append(f"FAIL Claude Code: {error}")
        healthy = False
        claude_executable = None
        claude_env = None
    else:
        claude_env = dict(provider_source)
        claude_env["PATH"] = claude_path
    claude_available = (
        version_check(str(claude_executable), "Claude Code", env=claude_env)
        if claude_executable is not None
        else False
    )
    capability_check("claude", claude_executable if claude_available else None, claude_env)
    claude_auth = (
        safe_run((str(claude_executable), "auth", "status"), env=claude_env)
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

    try:
        grok_executable, grok_path = resolve_provider_executable(
            PROVIDER_SPECS["grok"],
            provider_source,
            review_worktree=cwd,
        )
    except ReviewBridgeError as error:
        lines.append(f"FAIL Grok Build: {error}")
        healthy = False
        grok_executable = None
        grok_env = None
    else:
        grok_env = dict(provider_source)
        grok_env["PATH"] = grok_path
    grok_available = (
        version_check(str(grok_executable), "Grok Build", env=grok_env)
        if grok_executable is not None
        else False
    )
    grok_session_controls = (
        safe_run(
            (str(grok_executable), "--no-auto-update", "--no-memory", "--version"),
            env=grok_env,
        )
        if grok_available
        else subprocess.CompletedProcess(("grok",), 127, "", "")
    )
    if grok_available and grok_session_controls.returncode == 0:
        lines.append("OK   Grok session controls: compatible")
    else:
        lines.append("FAIL Grok session controls: `--no-auto-update --no-memory` unsupported")
        healthy = False
    capability_check("grok", grok_executable if grok_available else None, grok_env)
    grok_auth = (
        safe_run((str(grok_executable), "--no-auto-update", "models"), env=grok_env)
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
        try:
            requested_model = select_grok_request_model(grok_probe)
        except ReviewBridgeError as error:
            lines.append(f"FAIL Grok review model selection: {error}")
            healthy = False
        else:
            lines.append(
                f"OK   Grok review model selection: explicit `{requested_model}` request"
            )

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

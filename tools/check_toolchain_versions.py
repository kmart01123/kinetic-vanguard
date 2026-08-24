#!/usr/bin/env python3
"""Fail when duplicated development-toolchain version declarations drift."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"toolchain-version-check: {message}")


def load_json(relative_path: str) -> dict[str, object]:
    path = ROOT / relative_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"could not read {relative_path}: {error}")
    if not isinstance(payload, dict):
        fail(f"{relative_path} must contain a JSON object")
    return payload


def require_match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        fail(f"could not locate {label}")
    return match.group(1)


def require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a nonempty string")
    return value


def main() -> None:
    package = load_json("package.json")
    devcontainer = load_json(".devcontainer/devcontainer.json")
    post_create = (ROOT / ".devcontainer/post-create.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    prototype_pages = (ROOT / ".github/workflows/prototype-pages.yml").read_text(
        encoding="utf-8"
    )

    package_engines = require_mapping(package.get("engines"), "package.json engines")
    expected_node = require_string(package_engines.get("node"), "package.json engines.node")
    package_manager = require_string(package.get("packageManager"), "package.json packageManager")
    npm_match = re.fullmatch(r"npm@([0-9]+\.[0-9]+\.[0-9]+)", package_manager)
    if npm_match is None:
        fail("package.json packageManager must be an exact npm semver")
    expected_npm = npm_match.group(1)

    features = require_mapping(devcontainer.get("features"), "devcontainer features")
    python_feature = require_mapping(
        features.get("ghcr.io/devcontainers/features/python:1"),
        "devcontainer Python feature",
    )
    node_feature = require_mapping(
        features.get("ghcr.io/devcontainers/features/node:1"),
        "devcontainer Node feature",
    )
    gh_feature = require_mapping(
        features.get("ghcr.io/devcontainers/features/github-cli:1"),
        "devcontainer GitHub CLI feature",
    )

    expected_python = require_string(
        python_feature.get("version"), "devcontainer Python version"
    )
    expected_gh = require_string(
        gh_feature.get("version"), "devcontainer GitHub CLI version"
    )

    checks = (
        (
            "devcontainer Node",
            require_string(node_feature.get("version"), "devcontainer Node version"),
            expected_node,
        ),
        (
            "devcontainer npm",
            require_string(node_feature.get("npmVersion"), "devcontainer npm version"),
            expected_npm,
        ),
        (
            "post-create Node",
            require_match(
                r'^readonly EXPECTED_NODE_VERSION="v([^"]+)"$',
                post_create,
                "post-create Node version",
            ),
            expected_node,
        ),
        (
            "post-create npm",
            require_match(
                r'^readonly EXPECTED_NPM_VERSION="([^"]+)"$',
                post_create,
                "post-create npm version",
            ),
            expected_npm,
        ),
        (
            "post-create Python",
            require_match(
                r'^readonly EXPECTED_PYTHON_SERIES="([^"]+)"$',
                post_create,
                "post-create Python version",
            ),
            expected_python,
        ),
        (
            "post-create GitHub CLI",
            require_match(
                r'^readonly EXPECTED_GH_VERSION="([^"]+)"$',
                post_create,
                "post-create GitHub CLI version",
            ),
            expected_gh,
        ),
        (
            "CI Node",
            require_match(
                r'^\s*node-version:\s*"?([0-9]+\.[0-9]+\.[0-9]+)"?\s*$',
                ci,
                "CI Node version",
            ),
            expected_node,
        ),
        (
            "CI npm",
            require_match(
                r'^\s*run:\s*npm install --global npm@([0-9]+\.[0-9]+\.[0-9]+)\s*$',
                ci,
                "CI npm version",
            ),
            expected_npm,
        ),
        (
            "CI Python",
            require_match(
                r'^\s*python-version:\s*"?([0-9]+\.[0-9]+)"?\s*$',
                ci,
                "CI Python version",
            ),
            expected_python,
        ),
        (
            "prototype Pages Node",
            require_match(
                r'^\s*node-version:\s*"?([0-9]+\.[0-9]+\.[0-9]+)"?\s*$',
                prototype_pages,
                "prototype Pages Node version",
            ),
            expected_node,
        ),
        (
            "prototype Pages npm",
            require_match(
                r'^\s*run:\s*npm install --global npm@([0-9]+\.[0-9]+\.[0-9]+)\s*$',
                prototype_pages,
                "prototype Pages npm version",
            ),
            expected_npm,
        ),
    )

    mismatches = [
        f"{label}: expected {expected}, found {actual}"
        for label, actual, expected in checks
        if actual != expected
    ]
    if mismatches:
        fail("version drift detected:\n  " + "\n  ".join(mismatches))

    print(
        "toolchain versions consistent: "
        f"Node {expected_node}, npm {expected_npm}, "
        f"Python {expected_python}, gh {expected_gh}"
    )


if __name__ == "__main__":
    main()

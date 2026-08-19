#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_NODE_VERSION="v24.18.1"
readonly EXPECTED_NPM_VERSION="11.16.0"
readonly EXPECTED_PYTHON_SERIES="3.13"
readonly EXPECTED_GH_VERSION="2.97.0"
readonly CODEX_PACKAGE="@openai/codex@0.148.0"
readonly CLAUDE_PACKAGE="@anthropic-ai/claude-code@2.1.234"
readonly GROK_PACKAGE="@xai-official/grok@1.0.5"
readonly CLAUDE_CONFIG_DIRECTORY="/home/vscode/.claude"
readonly CLAUDE_CONFIG_PATH="$CLAUDE_CONFIG_DIRECTORY/.claude.json"
readonly CLAUDE_LEGACY_STATE_PATH="$CLAUDE_CONFIG_DIRECTORY/global-state.json"
readonly GITHUB_ORIGIN_URL="https://github.com/kmart01123/kinetic-vanguard.git"
readonly GITHUB_HTTPS_REWRITE_KEY='url.https://github.com/.insteadOf'

readonly -a STATE_DIRECTORIES=(
	"/home/vscode/.codex"
	"/home/vscode/.config/gh"
	"/home/vscode/.claude"
	"/home/vscode/.grok"
	"/home/vscode/.cache"
	"/home/vscode/.cache/ms-playwright"
)

fail() {
	printf 'post-create: %s\n' "$*" >&2
	exit 1
}

warn() {
	printf 'post-create: warning: %s\n' "$*" >&2
}

require_exact_version() {
	local label="$1"
	local expected="$2"
	local actual="$3"

	[[ "$actual" == "$expected" ]] || fail "$label version mismatch: expected $expected, got $actual"
}

migrate_claude_global_state() {
	if [[ -e "$CLAUDE_CONFIG_PATH" || -L "$CLAUDE_CONFIG_PATH" ]]; then
		return
	fi

	if [[ ! -e "$CLAUDE_LEGACY_STATE_PATH" && ! -L "$CLAUDE_LEGACY_STATE_PATH" ]]; then
		return
	fi

	if [[ ! -f "$CLAUDE_LEGACY_STATE_PATH" || -L "$CLAUDE_LEGACY_STATE_PATH" \
		|| ! -s "$CLAUDE_LEGACY_STATE_PATH" ]] \
		|| ! python3 -c 'import json, sys; json.load(open(sys.argv[1]))' \
			"$CLAUDE_LEGACY_STATE_PATH" >/dev/null 2>&1; then
		printf 'post-create: warning: legacy Claude global state was not migrated because it is not a nonempty regular JSON file\n' >&2
		return
	fi

	if ! mv --no-clobber -- "$CLAUDE_LEGACY_STATE_PATH" "$CLAUDE_CONFIG_PATH"; then
		printf 'post-create: warning: could not migrate legacy Claude global state\n' >&2
		return
	fi
	if [[ -e "$CLAUDE_LEGACY_STATE_PATH" || -L "$CLAUDE_LEGACY_STATE_PATH" ]]; then
		printf 'post-create: warning: legacy Claude global state was not migrated because the canonical path appeared\n' >&2
		return
	fi

	if ! chmod 0600 "$CLAUDE_CONFIG_PATH"; then
		printf 'post-create: warning: could not set private mode on migrated Claude global state\n' >&2
	fi
}

configure_github_https() {
	local rewrite
	local existing_rewrites
	local found

	if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		if git remote get-url origin >/dev/null 2>&1; then
			git remote set-url origin "$GITHUB_ORIGIN_URL" \
				|| warn "could not normalize the origin fetch URL to GitHub HTTPS"
			if git config --local --get-all remote.origin.pushurl >/dev/null 2>&1; then
				git config --local --replace-all remote.origin.pushurl "$GITHUB_ORIGIN_URL" \
					|| warn "could not normalize the origin push URL to GitHub HTTPS"
			fi
		else
			warn "GitHub HTTPS origin normalization skipped because origin is unavailable"
		fi

		existing_rewrites="$(
			git config --local --get-all "$GITHUB_HTTPS_REWRITE_KEY" 2>/dev/null || true
		)"
		for rewrite in 'git@github.com:' 'ssh://git@github.com/'; do
			found=false
			while IFS= read -r existing; do
				if [[ "$existing" == "$rewrite" ]]; then
					found=true
					break
				fi
			done <<< "$existing_rewrites"
			if [[ "$found" == false ]]; then
				if git config --local --add "$GITHUB_HTTPS_REWRITE_KEY" "$rewrite"; then
					existing_rewrites+="${existing_rewrites:+$'\n'}$rewrite"
				else
					warn "could not add GitHub HTTPS rewrite for $rewrite"
				fi
			fi
		done
	else
		warn "repository-local GitHub HTTPS normalization skipped outside a Git worktree"
	fi

	if gh auth status --hostname github.com >/dev/null 2>&1; then
		gh auth setup-git \
			|| warn "GitHub CLI could not configure the HTTPS credential helper"
	else
		warn "GitHub CLI authentication is unavailable; skipped HTTPS credential helper setup"
	fi
}

for state_directory in "${STATE_DIRECTORIES[@]}"; do
	sudo install -d -o "$(id -un)" -g "$(id -gn)" -m 0700 "$state_directory"
	sudo chown "$(id -u):$(id -g)" "$state_directory"
	chmod 0700 "$state_directory"
done

python3 tools/check_toolchain_versions.py

require_exact_version "Node" "$EXPECTED_NODE_VERSION" "$(node --version)"
require_exact_version "npm" "$EXPECTED_NPM_VERSION" "$(npm --version)"
[[ "$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "$EXPECTED_PYTHON_SERIES" ]] \
	|| fail "Python version mismatch: expected $EXPECTED_PYTHON_SERIES.x, got $(python3 --version)"
gh_version="$(gh --version)"
gh_version="${gh_version%%$'\n'*}"
gh_version="${gh_version#gh version }"
gh_version="${gh_version%% *}"
require_exact_version "GitHub CLI" "$EXPECTED_GH_VERSION" "$gh_version"

configure_github_https
migrate_claude_global_state

npm ci

node_binary_directory="$(dirname "$(command -v node)")"
sudo env \
	"PATH=$node_binary_directory:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
	DEBIAN_FRONTEND=noninteractive \
	"$(command -v npx)" playwright install-deps chromium
npx playwright install chromium

npm install --global --no-audit --no-fund \
	"$CODEX_PACKAGE" \
	"$CLAUDE_PACKAGE" \
	"$GROK_PACKAGE"

codex_version="$(codex --version)"
claude_version="$(claude --version)"
grok_version="$(grok --version)"

[[ "$codex_version" == *"0.148.0"* ]] || fail "Codex version mismatch: $codex_version"
[[ "$claude_version" == *"2.1.234"* ]] || fail "Claude version mismatch: $claude_version"
[[ "$grok_version" == "grok 1.0.5"* ]] || fail "Grok version mismatch: $grok_version"

printf '\nKinetic Vanguard development environment ready:\n'
printf '  Node:   %s\n' "$(node --version)"
printf '  npm:    %s\n' "$(npm --version)"
printf '  Python: %s\n' "$(python3 --version)"
printf '  gh:     %s\n' "$gh_version"
printf '  Codex:  %s\n' "$codex_version"
printf '  Claude: %s\n' "$claude_version"
printf '  Grok:   %s\n' "$grok_version"

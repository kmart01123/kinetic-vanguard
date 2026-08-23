"""Fail-closed adapter from the canonical TypeScript YAML loader to Python."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = PROJECT_ROOT / "KineticVanguard.yaml"


class AuthorityError(RuntimeError):
    """Raised when canonical mechanics cannot be projected safely."""


class AuthorityUnavailableError(AuthorityError):
    """Raised when a valid canonical feature or tier is unavailable at a Fighter level."""


def _projector_command(authority_path: Path) -> list[str]:
    executable = PROJECT_ROOT / "node_modules" / ".bin" / "tsx"
    if not executable.is_file():
        raise AuthorityError("TypeScript projector unavailable; run `npm ci` first")
    return [str(executable), str(PROJECT_ROOT / "src" / "harness-authority.ts"), "--authority", str(authority_path)]


def load_projection(authority_path: str | Path = DEFAULT_AUTHORITY) -> dict[str, Any]:
    path = Path(authority_path).resolve()
    if not path.is_file():
        raise AuthorityError(f"Authority file does not exist: {path}")
    completed = subprocess.run(
        _projector_command(path), cwd=PROJECT_ROOT, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        message = completed.stderr.strip() or completed.stdout.strip() or "unknown projection failure"
        raise AuthorityError(message)
    try:
        projection = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AuthorityError(f"Projector returned invalid JSON: {error}") from error
    required = {"projection_version", "authority_path", "authority_sha256", "rules_version", "progressions", "disciplines", "features"}
    missing = sorted(required - projection.keys())
    if missing:
        raise AuthorityError(f"Projection is missing required fields: {', '.join(missing)}")
    return projection


def band_value(bands: list[dict[str, int]], level: int, label: str) -> int:
    matches = [band for band in bands if band["minimum_level"] <= level <= band["maximum_level"]]
    if len(matches) != 1:
        raise AuthorityError(f"{label} has {len(matches)} bands at Fighter level {level}; expected exactly one")
    return int(matches[0]["value"])


@dataclass(frozen=True)
class AuthorityModel:
    projection: dict[str, Any]

    @classmethod
    def load(cls, authority_path: str | Path = DEFAULT_AUTHORITY) -> "AuthorityModel":
        return cls(load_projection(authority_path))

    @property
    def rules_version(self) -> str:
        return str(self.projection["rules_version"])

    @property
    def authority_sha256(self) -> str:
        return str(self.projection["authority_sha256"])

    @property
    def disciplines(self) -> dict[str, dict[str, Any]]:
        rows = self.projection["disciplines"]
        return {str(row["id"]): row for row in rows}

    @property
    def features(self) -> dict[str, dict[str, Any]]:
        rows = self.projection["features"]
        result = {str(row["entity_id"]): row for row in rows}
        if len(result) != len(rows):
            raise AuthorityError("Projection contains duplicate feature entity IDs")
        return result

    def _derived_value(self, definition: dict[str, Any], level: int, psi_modifier: int) -> int:
        components = {
            "psionic_ability_modifier": psi_modifier,
            "proficiency_bonus": self.progression("proficiency_bonus", level),
            "psionic_focus": self.progression("psionic_focus", level),
        }
        try:
            return int(definition["base"]) + sum(components[name] for name in definition["components"])
        except KeyError as error:
            raise AuthorityError(f"Unsupported canonical derived-value component: {error.args[0]}") from error

    def kv_attack_bonus(self, level: int, psi_modifier: int) -> int:
        return self._derived_value(self.projection["core"]["manifested_strike"]["attack_bonus"], level, psi_modifier)

    def kv_save_dc(self, level: int, psi_modifier: int) -> int:
        return self._derived_value(self.projection["core"]["manifested_strike"]["save_dc"], level, psi_modifier)

    def holdout_formula(self, level: int) -> dict[str, Any]:
        formulas = self.projection["core"]["manifested_strike"]["holdout"]["formulas"]
        matches = [row for row in formulas if int(row["minimum_level"]) <= level <= int(row["maximum_level"])]
        if len(matches) != 1:
            raise AuthorityError(f"Holdout has {len(matches)} formulas at Fighter level {level}; expected exactly one")
        return matches[0]

    def psionic_apex_strike_packet(self, discipline_id: str, level: int) -> dict[str, Any] | None:
        apex = self.projection["core"]["psionic_apex"]
        if level < int(apex["minimum_level"]):
            return None
        packet = apex["psychokinesis_manifested_strike_hit"]
        return packet if discipline_id == packet["discipline_id"] else None

    def blood_tax(self, level: int, tier: int) -> int:
        if tier not in {0, 1, 2}:
            raise AuthorityError(f"Unsupported Overload tier {tier}")
        rule = self.projection["core"]["overload"]["blood_tax_per_tier"]
        return int(rule["base"]) + tier * self.progression("proficiency_bonus", level) * int(rule["proficiency_bonus_multiplier"])

    def overload_payment_options(self, tax: int, mastery_remaining: int, mastery_mode: int) -> tuple[tuple[int, int, int, bool], ...]:
        """Return canonical Blood Tax choices without coupling either harness to a planner."""
        if tax < 0 or mastery_remaining < 0 or mastery_mode not in {0, 1, 2}:
            raise AuthorityError("Unsupported Overload payment state")
        if tax == 0:
            return ((0, mastery_remaining, mastery_mode, False),)
        mastery = self.projection["core"]["overload"]["mastery"]
        reduced = max(int(mastery["minimum_per_overload"]), tax // int(mastery["blood_tax_divisor"]))
        if mastery_mode == 1:
            return ((reduced, mastery_remaining, 1, False),)
        raw = (tax, mastery_remaining, 2, False)
        if mastery_mode == 0 and mastery_remaining:
            return (raw, (reduced, mastery_remaining - 1, 1, True))
        return (raw,)

    def feature(self, entity_id: str, level: int, tier: int | None = None) -> dict[str, Any]:
        feature = self.features.get(entity_id)
        if feature is None:
            raise AuthorityError(f"Unknown harness feature entity ID: {entity_id}")
        if level < int(feature["minimum_level"]):
            raise AuthorityUnavailableError(
                f"Feature {entity_id} is unavailable at Fighter level {level}"
            )
        if tier is not None:
            minimums = {int(row["tier"]): int(row["minimum_level"]) for row in self.projection["progressions"]["tier_minimum_levels"]}
            if tier not in minimums:
                raise AuthorityError(f"Unsupported Overload tier {tier}")
            if level < minimums[tier]:
                raise AuthorityUnavailableError(
                    f"Tier {tier} is unavailable at Fighter level {level}"
                )
        return feature

    def progression(self, name: str, level: int) -> int:
        bands = self.projection["progressions"].get(name)
        if not isinstance(bands, list):
            raise AuthorityError(f"Unknown progression: {name}")
        return band_value(bands, level, name)

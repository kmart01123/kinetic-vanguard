"""Exact nominal damage contract and its three closed build providers.

This module owns all damage semantics.  ``damage_harness`` is deliberately
limited to loading inputs, scheduling provider calls, aggregating exact
results, and writing reports.  Finite-HP modes are reserved for a separately
authorized successor and fail closed here.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from functools import lru_cache, wraps
from typing import Any, Callable, Iterable, Mapping, Sequence

from .authority import DamageAuthorityModel
from .creature_damage_projection import DamageTarget
from .model import level_config


NOMINAL_MODE_ID = "nominal_sustained_dpr_v1"
TARGET_KNOWLEDGE_CONTRACT_ID = "declared_static_target_knowledge_v1"
NUMERIC_REPRESENTATION_ID = "exact_fraction"
BATTLE_MASTER_PACKAGE_ID = "generic_on_hit_superiority_damage_v1"
DEFERRED_FINITE_MODE_IDS = ("finite_hp_removed_v1", "finite_hp_kill_cleave_v1")
_CANONICAL_ACTION_ID = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*\Z")


class ProviderId(str, Enum):
    KINETIC_VANGUARD = "kinetic_vanguard"
    BATTLE_MASTER = "battle_master"
    ELDRITCH_KNIGHT = "eldritch_knight"


class ActionKind(str, Enum):
    ATTACK_ACTION = "attack_action"
    ORDINARY_ATTACK = "ordinary_attack"
    MANIFESTED_STRIKE = "manifested_strike"
    RIDER_DECLARATION = "rider_declaration"
    STANDALONE_FEATURE = "standalone_feature"
    BATTLE_MASTER_ON_HIT_DIE = "battle_master_on_hit_die"
    BATTLE_MASTER_MISS_CORRECTION = "battle_master_miss_correction"
    RELENTLESS = "relentless"
    COMBAT_PROWESS = "combat_prowess"
    TRUE_STRIKE_REPLACEMENT = "true_strike_replacement"
    KINETIC_MASTERY = "kinetic_mastery"
    HEW_BONUS_ATTACK = "hew_bonus_attack"
    ATTACK_RESOLUTION = "attack_resolution"
    END_ACTION = "end_action"
    END_TURN = "end_turn"
    END_ROUND = "end_round"
    END_HORIZON = "end_horizon"
    CANONICAL_TIE_PROBE = "canonical_tie_probe"


PROVIDER_IDS = tuple(provider.value for provider in ProviderId)
ACTION_KINDS = tuple(kind.value for kind in ActionKind)


def action_kind(action_id: str) -> ActionKind:
    """Classify every canonical action ID into the closed damage vocabulary."""

    if _CANONICAL_ACTION_ID.fullmatch(action_id) is None:
        raise ValueError("Every proposal requires a stable canonical action ID")
    if action_id.startswith("tie_probe."):
        return ActionKind.CANONICAL_TIE_PROBE
    if action_id.endswith(".payment.mastery_activate"):
        return ActionKind.KINETIC_MASTERY
    if action_id == "action.attack":
        return ActionKind.ATTACK_ACTION
    if action_id.startswith("action.standalone."):
        return ActionKind.STANDALONE_FEATURE
    if action_id == "attack.ordinary":
        return ActionKind.ORDINARY_ATTACK
    if action_id in {"attack.radiant_base", "attack.weapon_normal_base"}:
        return ActionKind.TRUE_STRIKE_REPLACEMENT
    if action_id.startswith("strike."):
        return (
            ActionKind.RIDER_DECLARATION
            if ".rider." in action_id
            else ActionKind.MANIFESTED_STRIKE
        )
    if action_id.startswith("hew."):
        return ActionKind.HEW_BONUS_ATTACK
    if action_id.startswith("hit.relentless"):
        return ActionKind.RELENTLESS
    if action_id.startswith(f"hit.{BATTLE_MASTER_PACKAGE_ID}"):
        return ActionKind.BATTLE_MASTER_ON_HIT_DIE
    if action_id == "hit.weapon":
        return ActionKind.ORDINARY_ATTACK
    if action_id.startswith("miss.combat_prowess") or action_id == "precision.failure.combat_prowess":
        return ActionKind.COMBAT_PROWESS
    if action_id.startswith("miss.precision") or action_id.startswith("precision.failure"):
        return ActionKind.BATTLE_MASTER_MISS_CORRECTION
    if action_id in {"miss.graze", "miss.retain"}:
        return ActionKind.ATTACK_RESOLUTION
    if action_id in {"hit.resolve", "critical.resolve", "attack.resolve"}:
        return ActionKind.ATTACK_RESOLUTION
    if action_id == "end.attack_action":
        return ActionKind.END_ACTION
    if action_id == "end.turn":
        return ActionKind.END_TURN
    if action_id == "end.round":
        return ActionKind.END_ROUND
    if action_id == "end.horizon":
        return ActionKind.END_HORIZON
    raise ValueError(f"Action ID {action_id!r} is outside the closed damage vocabulary")


class UnsupportedDamageMode(ValueError):
    """Raised before any unsupported finite transition can be evaluated."""


def reject_unsupported_mode(mode_id: str) -> None:
    if mode_id != NOMINAL_MODE_ID:
        raise UnsupportedDamageMode(
            f"Damage mode {mode_id!r} is unsupported in Issue #65 Phase 2 PR1; "
            "finite HP requires separately authorized PR2"
        )


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return value


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_fraction(value: Any, label: str) -> None:
    if not isinstance(value, Fraction):
        raise TypeError(f"{label} must be an exact Fraction")


def _require_immutable_state(value: Any, label: str) -> None:
    """Reject mutable or inexact values before they enter a canonical DP key."""

    if value is None or isinstance(value, (str, int, bool, Fraction, Enum)):
        return
    if isinstance(value, tuple):
        for index, item in enumerate(value):
            _require_immutable_state(item, f"{label}[{index}]")
        return
    if isinstance(value, frozenset):
        for item in value:
            _require_immutable_state(item, f"{label} member")
        return
    raise TypeError(f"{label} must contain only canonical immutable exact values")


@dataclass(frozen=True, slots=True)
class TargetKnowledge:
    """The identical immutable nominal target surface given to every provider."""

    contract_id: str
    creature_id: str
    ac: int
    saves: tuple[tuple[str, int], ...]
    magic_resistance: bool
    legendary_resistance: int
    legendary_resistance_lair: int | None
    legendary_resistance_policy: str
    damage_resistances: frozenset[str]
    damage_immunities: frozenset[str]
    damage_vulnerabilities: frozenset[str]
    size: str
    creature_type: str

    def __post_init__(self) -> None:
        if self.contract_id != TARGET_KNOWLEDGE_CONTRACT_ID:
            raise ValueError("Unsupported target-knowledge contract")
        if isinstance(self.ac, bool) or not isinstance(self.ac, int) or self.ac < 0:
            raise ValueError("Target Armor Class must be a nonnegative integer")
        expected_saves = {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        }
        if (
            self.saves != tuple(sorted(self.saves))
            or len(dict(self.saves)) != len(self.saves)
            or {ability for ability, _ in self.saves} != expected_saves
            or any(isinstance(value, bool) or not isinstance(value, int) for _, value in self.saves)
        ):
            raise ValueError("Target knowledge requires six canonical, sorted save bonuses")
        if (
            isinstance(self.legendary_resistance, bool)
            or not isinstance(self.legendary_resistance, int)
            or self.legendary_resistance < 0
        ):
            raise ValueError("Legendary Resistance metadata cannot be negative")
        if self.legendary_resistance_lair is not None and (
            isinstance(self.legendary_resistance_lair, bool)
            or not isinstance(self.legendary_resistance_lair, int)
            or self.legendary_resistance_lair < 0
        ):
            raise ValueError("Lair Legendary Resistance metadata cannot be negative")
        if not isinstance(self.magic_resistance, bool):
            raise ValueError("Magic Resistance metadata must be boolean")
        if self.legendary_resistance_policy != "metadata_only":
            raise ValueError("PR1 supports Legendary Resistance metadata only")
        if not self.creature_id or not self.size or not self.creature_type:
            raise ValueError("Target knowledge identity, size, and type must be non-empty")
        for damage_types in (
            self.damage_resistances,
            self.damage_immunities,
            self.damage_vulnerabilities,
        ):
            if not isinstance(damage_types, frozenset) or any(
                not value or value != value.lower() for value in damage_types
            ):
                raise ValueError("Target damage defenses must be lowercase immutable sets")

    @classmethod
    def from_damage_target(cls, target: DamageTarget) -> "TargetKnowledge":
        target.validate_identity()
        return cls(
            contract_id=TARGET_KNOWLEDGE_CONTRACT_ID,
            creature_id=target.creature_id,
            ac=int(target.ac),
            saves=tuple(sorted((str(key), int(value)) for key, value in target.saves.items())),
            magic_resistance=bool(target.magic_resistance),
            legendary_resistance=int(target.legendary_resistance),
            legendary_resistance_lair=target.legendary_resistance_lair,
            legendary_resistance_policy=str(target.legendary_resistance_policy),
            damage_resistances=frozenset(str(value).lower() for value in target.damage_resistances),
            damage_immunities=frozenset(str(value).lower() for value in target.damage_immunities),
            damage_vulnerabilities=frozenset(str(value).lower() for value in target.damage_vulnerabilities),
            size=str(target.size),
            creature_type=str(target.creature_type),
        )

    def save_bonus(self, ability: str) -> int:
        try:
            return dict(self.saves)[ability]
        except KeyError as error:
            raise ValueError(f"Target lacks configured {ability!r} saving throw") from error

    @property
    def digest(self) -> str:
        return canonical_sha256(
            {
                "contract_id": self.contract_id,
                "creature_id": self.creature_id,
                "ac": self.ac,
                "saves": self.saves,
                "magic_resistance": self.magic_resistance,
                "legendary_resistance": self.legendary_resistance,
                "legendary_resistance_lair": self.legendary_resistance_lair,
                "legendary_resistance_policy": self.legendary_resistance_policy,
                "damage_resistances": sorted(self.damage_resistances),
                "damage_immunities": sorted(self.damage_immunities),
                "damage_vulnerabilities": sorted(self.damage_vulnerabilities),
                "size": self.size,
                "creature_type": self.creature_type,
            }
        )


def validate_distribution(distribution: Mapping[Any, Fraction]) -> None:
    if not distribution:
        raise ValueError("Exact distribution cannot be empty")
    if any(not isinstance(probability, Fraction) for probability in distribution.values()):
        raise TypeError("Every probability must be a Fraction")
    if any(probability < 0 for probability in distribution.values()):
        raise ValueError("Exact distribution contains a negative probability")
    if sum(distribution.values(), Fraction()) != 1:
        raise ValueError("Exact distribution probability mass must sum to one")


@lru_cache(maxsize=None)
def die_distribution(count: int, sides: int, minimum: int | None = None) -> tuple[tuple[int, Fraction], ...]:
    if count < 0 or sides < 2:
        raise ValueError("Dice require nonnegative count and at least two sides")
    distribution: dict[int, Fraction] = {0: Fraction(1)}
    faces = tuple(max(face, minimum) if minimum is not None else face for face in range(1, sides + 1))
    for _ in range(count):
        next_distribution: dict[int, Fraction] = defaultdict(Fraction)
        for subtotal, probability in distribution.items():
            for face in faces:
                next_distribution[subtotal + face] += probability / sides
        distribution = dict(next_distribution)
    validate_distribution(distribution)
    return tuple(sorted(distribution.items()))


def combine_dice(groups: Sequence[tuple[int, int, int | None]]) -> tuple[tuple[int, Fraction], ...]:
    distribution: dict[int, Fraction] = {0: Fraction(1)}
    for count, sides, minimum in groups:
        next_distribution: dict[int, Fraction] = defaultdict(Fraction)
        for subtotal, probability in distribution.items():
            for roll, roll_probability in die_distribution(count, sides, minimum):
                next_distribution[subtotal + roll] += probability * roll_probability
        distribution = dict(next_distribution)
    validate_distribution(distribution)
    return tuple(sorted(distribution.items()))


@lru_cache(maxsize=2)
def natural_d20_distribution(advantage: bool) -> tuple[tuple[int, Fraction], ...]:
    if not advantage:
        return tuple((natural, Fraction(1, 20)) for natural in range(1, 21))
    values: dict[int, Fraction] = defaultdict(Fraction)
    for first in range(1, 21):
        for second in range(1, 21):
            values[max(first, second)] += Fraction(1, 400)
    validate_distribution(values)
    return tuple(sorted(values.items()))


def attack_outcome_distribution(
    target: TargetKnowledge,
    attack_bonus: int,
    *,
    advantage: bool = False,
    ac_reduction: int = 0,
) -> tuple[tuple[str, Fraction], ...]:
    probabilities: dict[str, Fraction] = defaultdict(Fraction)
    effective_ac = target.ac - ac_reduction
    for natural, probability in natural_d20_distribution(advantage):
        outcome = (
            "miss"
            if natural == 1
            else "critical"
            if natural == 20
            else "hit"
            if natural + attack_bonus >= effective_ac
            else "miss"
        )
        probabilities[outcome] += probability
    validate_distribution(probabilities)
    return tuple(
        (outcome, probabilities[outcome])
        for outcome in ("miss", "hit", "critical")
        if probabilities[outcome]
    )


def studied_state_after_final_attack(
    studied_enabled: bool, *, final_hit: bool
) -> bool:
    """Consume the prior benefit, then let a new final miss establish Studied."""

    if not isinstance(studied_enabled, bool) or not isinstance(final_hit, bool):
        raise TypeError("Studied Attacks state inputs must be boolean")
    return studied_enabled and not final_hit


def save_success_probability(target: TargetKnowledge, ability: str, dc: int) -> Fraction:
    successes = 0
    total = 400 if target.magic_resistance else 20
    if target.magic_resistance:
        rolls: Iterable[int] = (
            max(first, second)
            for first in range(1, 21)
            for second in range(1, 21)
        )
    else:
        rolls = range(1, 21)
    bonus = target.save_bonus(ability)
    for natural in rolls:
        successes += natural + bonus >= dc
    return Fraction(successes, total)


def apply_defense(
    target: TargetKnowledge,
    damage_type: str,
    value: int,
    *,
    ignore_resistance: bool = False,
) -> int:
    if value < 0:
        raise ValueError("Damage cannot be negative")
    damage_type = damage_type.lower()
    if damage_type in target.damage_immunities:
        return 0
    resistant = damage_type in target.damage_resistances and not ignore_resistance
    vulnerable = damage_type in target.damage_vulnerabilities
    if resistant and vulnerable:
        return value
    if resistant:
        return value // 2
    if vulnerable:
        return value * 2
    return value


def expected_typed_packet(
    target: TargetKnowledge,
    damage_type: str,
    dice: Sequence[tuple[int, int, int | None]],
    flat: int = 0,
    *,
    ignore_resistance: bool = False,
    raw_divisor: int = 1,
) -> Fraction:
    if raw_divisor < 1:
        raise ValueError("Raw packet divisor must be positive")
    return sum(
        probability
        * apply_defense(
            target,
            damage_type,
            (roll + flat) // raw_divisor,
            ignore_resistance=ignore_resistance,
        )
        for roll, probability in combine_dice(dice)
    )


@dataclass(frozen=True, slots=True)
class ResourceCost:
    self_damage: Fraction = Fraction()
    horizon_limited: Fraction = Fraction()
    persistent_pool: Fraction = Fraction()
    refreshable: Fraction = Fraction()

    def __post_init__(self) -> None:
        for label, value in (
            ("self-damage cost", self.self_damage),
            ("horizon-limited cost", self.horizon_limited),
            ("persistent-pool cost", self.persistent_pool),
            ("refreshable cost", self.refreshable),
        ):
            _require_fraction(value, label)
            if value < 0:
                raise ValueError(f"{label} cannot be negative")

    def __add__(self, other: "ResourceCost") -> "ResourceCost":
        return ResourceCost(
            self.self_damage + other.self_damage,
            self.horizon_limited + other.horizon_limited,
            self.persistent_pool + other.persistent_pool,
            self.refreshable + other.refreshable,
        )

    def scale(self, probability: Fraction) -> "ResourceCost":
        return ResourceCost(
            self.self_damage * probability,
            self.horizon_limited * probability,
            self.persistent_pool * probability,
            self.refreshable * probability,
        )


@dataclass(frozen=True, slots=True)
class DamageValue:
    primary: Fraction = Fraction()
    aggregate: Fraction = Fraction()
    cost: ResourceCost = field(default_factory=ResourceCost)

    def __post_init__(self) -> None:
        _require_fraction(self.primary, "Primary damage")
        _require_fraction(self.aggregate, "Aggregate damage")
        if self.primary < 0 or self.aggregate < 0:
            raise ValueError("Nominal damage cannot be negative")
        if not isinstance(self.cost, ResourceCost):
            raise TypeError("Damage resource cost must be a ResourceCost")

    def __add__(self, other: "DamageValue") -> "DamageValue":
        return DamageValue(
            self.primary + other.primary,
            self.aggregate + other.aggregate,
            self.cost + other.cost,
        )

    def scale(self, probability: Fraction) -> "DamageValue":
        return DamageValue(
            self.primary * probability,
            self.aggregate * probability,
            self.cost.scale(probability),
        )


@dataclass(frozen=True, slots=True)
class ExactTransition:
    """One immutable exact chance edge from a provider-owned canonical state."""

    probability: Fraction
    reward: DamageValue
    successor_state: tuple[Any, ...] | None = None

    def __post_init__(self) -> None:
        _require_fraction(self.probability, "Transition probability")
        if not isinstance(self.reward, DamageValue):
            raise TypeError("Transition reward must be a DamageValue")
        if self.successor_state is not None:
            if not isinstance(self.successor_state, tuple):
                raise TypeError("Exact transition successor state must be an immutable tuple")
            _require_immutable_state(self.successor_state, "Transition successor state")


@dataclass(frozen=True, slots=True)
class Proposal:
    action_id: str
    value: DamageValue
    payload: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        action_kind(self.action_id)
        if not isinstance(self.value, DamageValue):
            raise TypeError("Proposal value must be a DamageValue")
        if not isinstance(self.payload, tuple):
            raise TypeError("Proposal payload must be an immutable tuple")
        _require_immutable_state(self.payload, "Proposal payload")

    @property
    def kind(self) -> ActionKind:
        return action_kind(self.action_id)


@dataclass(frozen=True, slots=True)
class KernelCacheInfo:
    hits: int
    misses: int
    states: int


class NominalKernel:
    """Shared exact transition, memoization, value, tie, and policy kernel."""

    mode_id = NOMINAL_MODE_ID

    def __init__(self, provider_id: ProviderId | str) -> None:
        self.provider_id = ProviderId(provider_id)
        self._memo: dict[tuple[str, tuple[Any, ...]], Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._policy: dict[str, tuple[str, str]] = {}
        self._selected: dict[str, _ProviderDecision] = {}

    @staticmethod
    def choose(proposals: Iterable[Proposal]) -> Proposal:
        candidates = tuple(proposals)
        if not candidates:
            raise ValueError("A nominal decision stage has no legal proposal")
        action_ids = tuple(candidate.action_id for candidate in candidates)
        for candidate in candidates:
            candidate.kind
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("A decision stage cannot emit duplicate canonical action IDs")

        def better(left: Proposal, right: Proposal) -> bool:
            left_value, right_value = left.value, right.value
            left_rank = (
                left_value.aggregate,
                left_value.primary,
                -left_value.cost.self_damage,
                -left_value.cost.horizon_limited,
                -left_value.cost.persistent_pool,
                -left_value.cost.refreshable,
            )
            right_rank = (
                right_value.aggregate,
                right_value.primary,
                -right_value.cost.self_damage,
                -right_value.cost.horizon_limited,
                -right_value.cost.persistent_pool,
                -right_value.cost.refreshable,
            )
            return left_rank > right_rank or (
                left_rank == right_rank and left.action_id < right.action_id
            )

        best = candidates[0]
        for candidate in candidates[1:]:
            if better(candidate, best):
                best = candidate
        return best

    @staticmethod
    def expectation(branches: Iterable[tuple[Fraction, DamageValue]]) -> DamageValue:
        transitions = tuple(
            ExactTransition(probability, value)
            for probability, value in branches
        )
        return NominalKernel.transition_value(transitions, lambda _state: DamageValue())

    @staticmethod
    def transition_value(
        transitions: Iterable[ExactTransition],
        continuation: Callable[[tuple[Any, ...] | None], DamageValue],
    ) -> DamageValue:
        """Coalesce identical exact edges, validate mass, and value successors."""

        grouped: dict[tuple[DamageValue, tuple[Any, ...] | None], Fraction] = defaultdict(Fraction)
        for transition in transitions:
            if not isinstance(transition.probability, Fraction):
                raise TypeError("Every transition probability must be a Fraction")
            if transition.probability < 0:
                raise ValueError("Exact transition contains a negative probability")
            if transition.successor_state is not None and not isinstance(
                transition.successor_state, tuple
            ):
                raise TypeError("Exact transition successor state must be an immutable tuple")
            grouped[(transition.reward, transition.successor_state)] += transition.probability
        validate_distribution(
            {index: probability for index, probability in enumerate(grouped.values())}
        )
        result = DamageValue()
        for (reward, successor_state), probability in grouped.items():
            result += (reward + continuation(successor_state)).scale(probability)
        return result

    def memoized_value(
        self,
        stage: str,
        state: tuple[Any, ...],
        compute: Callable[[], Any],
    ) -> Any:
        if not isinstance(state, tuple):
            raise TypeError("Memoized damage state must be an immutable tuple")
        _require_immutable_state(state, "Memoized damage state")
        key = (stage, state)
        try:
            cached = self._memo[key]
        except KeyError:
            self._cache_misses += 1
            cached = compute()
            self._memo[key] = cached
        else:
            self._cache_hits += 1
        return cached

    def cached(self, stage: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(function)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                keyword_state = tuple(sorted(kwargs.items()))
                state = (*args, keyword_state)
                return self.memoized_value(
                    stage,
                    state,
                    lambda: function(*args, **kwargs),
                )

            return wrapped

        return decorate

    def choose_provider(
        self,
        stage: str,
        state: tuple[Any, ...],
        candidates: Iterable["_ProviderDecision"],
    ) -> "_ProviderDecision":
        proposals = tuple(
            Proposal(candidate.action_id, candidate.value, candidate.payload)
            for candidate in candidates
        )
        selected = self.choose(proposals)
        key = canonical_sha256(
            (self.mode_id, self.provider_id.value, stage, state)
        )
        record = (selected.kind.value, selected.action_id)
        previous = self._policy.get(key)
        if previous is not None and previous != record:
            raise RuntimeError(
                f"Incomplete policy-state identity at {stage!r}: "
                f"{previous!r} conflicts with {record!r}"
            )
        decision = _ProviderDecision(selected.value, selected.action_id, selected.payload)
        previous_decision = self._selected.get(key)
        if previous_decision is not None and previous_decision != decision:
            raise RuntimeError(
                f"Incomplete policy-state value identity at {stage!r}"
            )
        self._policy[key] = record
        self._selected[key] = decision
        return decision

    def selected_provider(
        self, stage: str, state: tuple[Any, ...]
    ) -> "_ProviderDecision":
        """Read one already-evaluated choice for deterministic explanation tracing."""

        _require_immutable_state(state, "Policy state")
        key = canonical_sha256((self.mode_id, self.provider_id.value, stage, state))
        try:
            return self._selected[key]
        except KeyError as error:
            raise RuntimeError(
                f"Policy state {stage!r} was not evaluated before trace reconstruction"
            ) from error

    @property
    def policy_digest(self) -> str:
        return canonical_sha256(tuple(sorted(self._policy.items())))

    @property
    def policy_states(self) -> int:
        return len(self._policy)

    @property
    def cache_info(self) -> KernelCacheInfo:
        return KernelCacheInfo(self._cache_hits, self._cache_misses, len(self._memo))

    def clear(self) -> None:
        self._memo.clear()
        self._policy.clear()
        self._selected.clear()


def _provider_cached(stage: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Route a closed provider's immutable tuple state through the shared kernel."""

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapped(provider: Any, *args: Any, **kwargs: Any) -> Any:
            state = (*args, tuple(sorted(kwargs.items())))
            return provider.kernel.memoized_value(
                stage,
                state,
                lambda: function(provider, *args, **kwargs),
            )

        return wrapped

    return decorate


@dataclass(frozen=True, slots=True)
class DamageSolution:
    mode_id: str
    provider_id: str
    target_knowledge_sha256: str
    primary_dpr: Fraction
    aggregate_dpr: Fraction
    policy_digest: str
    trace: tuple[str, ...]
    stats: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if self.mode_id != NOMINAL_MODE_ID:
            raise ValueError("DamageSolution supports the nominal PR1 mode only")
        try:
            ProviderId(self.provider_id)
        except ValueError as error:
            raise ValueError(f"Unsupported damage provider {self.provider_id!r}") from error
        if not re.fullmatch(r"[0-9a-f]{64}", self.target_knowledge_sha256):
            raise ValueError("DamageSolution target knowledge identity must be a SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", self.policy_digest):
            raise ValueError("DamageSolution policy identity must be a SHA-256")
        _require_fraction(self.primary_dpr, "Primary DPR")
        _require_fraction(self.aggregate_dpr, "Aggregate DPR")
        if self.primary_dpr < 0 or self.aggregate_dpr < 0:
            raise ValueError("Nominal DPR cannot be negative")
        _require_immutable_state(self.trace, "DamageSolution trace")
        _require_immutable_state(self.stats, "DamageSolution statistics")

    @property
    def selection(self) -> str:
        return "|".join(self.trace)


@dataclass(frozen=True, slots=True)
class _ProviderDecision:
    value: DamageValue
    action_id: str
    payload: tuple[Any, ...] = ()

    @property
    def kind(self) -> ActionKind:
        return action_kind(self.action_id)


def _solution(
    provider_id: str,
    target: TargetKnowledge,
    horizon: DamageValue,
    rounds: int,
    kernel: NominalKernel,
    trace: Sequence[str],
    stats: Mapping[str, int],
) -> DamageSolution:
    if rounds != 3:
        raise ValueError("The nominal sustained-DPR horizon must be exactly three rounds")
    return DamageSolution(
        mode_id=NOMINAL_MODE_ID,
        provider_id=provider_id,
        target_knowledge_sha256=target.digest,
        primary_dpr=horizon.primary / rounds,
        aggregate_dpr=horizon.aggregate / rounds,
        policy_digest=kernel.policy_digest,
        trace=tuple(trace),
        stats=tuple(sorted((str(key), int(value)) for key, value in stats.items())),
    )


def _damage_value(primary: Fraction, aggregate: Fraction | None = None, cost: ResourceCost | None = None) -> DamageValue:
    return DamageValue(primary, primary if aggregate is None else aggregate, cost or ResourceCost())


def eldritch_knight_hit_damage(
    row: dict[str, Any],
    target: TargetKnowledge,
    level: int,
    mode: str,
    *,
    critical: bool = False,
) -> Fraction:
    """Exact confirmed-hit packet for one legal EK attack declaration."""

    weapon = row["weapon"]
    weapon_count, weapon_sides = int(weapon["count"]), int(weapon["sides"])
    weapon_minimum = 3 if bool(weapon["great_weapon_fighting"]) else None
    weapon_bonus = int(row["magic_weapon_bonus_by_level"][str(level)])
    dueling = int(row["dueling_damage_bonus"])
    multiplier = 2 if critical else 1
    if mode == "ordinary":
        ability = int(row["regular_attack_ability_modifier"])
        return expected_typed_packet(
            target,
            str(weapon["damage_type"]),
            ((weapon_count * multiplier, weapon_sides, weapon_minimum),),
            ability + weapon_bonus + dueling,
        )
    if mode not in row["true_strike_base_damage_modes"]:
        raise ValueError(f"Unsupported Eldritch Knight attack mode {mode!r}")
    ability = int(row["true_strike_ability_modifier_by_level"][str(level)])
    true_damage = row["true_strike_damage_by_level"][str(level)]
    true_count, true_sides = int(true_damage["count"]), int(true_damage["sides"])
    if mode == "radiant_base":
        return expected_typed_packet(
            target,
            str(row["true_strike_damage_type"]),
            (
                (weapon_count * multiplier, weapon_sides, weapon_minimum),
                (true_count * multiplier, true_sides, None),
            ),
            ability + weapon_bonus + dueling,
        )
    weapon_packet = expected_typed_packet(
        target,
        str(weapon["damage_type"]),
        ((weapon_count * multiplier, weapon_sides, weapon_minimum),),
        ability + weapon_bonus + dueling,
    )
    upgrade_packet = expected_typed_packet(
        target,
        str(row["true_strike_damage_type"]),
        ((true_count * multiplier, true_sides, None),),
    )
    return weapon_packet + upgrade_packet


def eldritch_knight_single_attack_expected(
    model: DamageAuthorityModel,
    row: dict[str, Any],
    target: TargetKnowledge,
    level: int,
    mode: str,
    *,
    advantage: bool = False,
) -> Fraction:
    """Exact no-Prowess value of one pre-roll EK declaration."""

    weapon_bonus = int(row["magic_weapon_bonus_by_level"][str(level)])
    ability = (
        int(row["regular_attack_ability_modifier"])
        if mode == "ordinary"
        else int(row["true_strike_ability_modifier_by_level"][str(level)])
    )
    attack_bonus = ability + model.progression("proficiency_bonus", level) + weapon_bonus
    outcomes = attack_outcome_distribution(target, attack_bonus, advantage=advantage)
    return sum(
        probability
        * (
            Fraction()
            if outcome == "miss"
            else eldritch_knight_hit_damage(
                row,
                target,
                level,
                mode,
                critical=outcome == "critical",
            )
        )
        for outcome, probability in outcomes
    )


def _eldritch_knight_solution(
    model: DamageAuthorityModel,
    config: dict[str, Any],
    row: dict[str, Any],
    target: TargetKnowledge,
    level: int,
) -> DamageSolution:
    policy = row["tactical_policy"]
    expected_policy = {
        "objective": NOMINAL_MODE_ID,
        "true_strike_choice_timing": "before_attack_roll",
        "decision_information": f"{TARGET_KNOWLEDGE_CONTRACT_ID}_and_observed_state",
        "true_strike_use_count": "zero_to_configured_maximum_per_attack_action",
    }
    if policy != expected_policy:
        raise ValueError("Unsupported Eldritch Knight tactical policy")
    progression = level_config(config, level)
    pb = model.progression("proficiency_bonus", level)
    studied_enabled = bool(progression["studied_attacks"])
    prowess_enabled = bool(progression["combat_prowess"])
    attacks = int(progression["attacks_per_action"])
    actions_by_round = tuple(int(value) for value in progression["action_slots_by_round"])
    weapon_bonus = int(row["magic_weapon_bonus_by_level"][str(level)])
    regular_ability = int(row["regular_attack_ability_modifier"])
    true_ability = int(row["true_strike_ability_modifier_by_level"][str(level)])
    true_maximum = int(row["true_strike_maximum_uses_per_attack_action"])
    if true_maximum != 1 or true_maximum > attacks:
        raise ValueError("True Strike maximum must be exactly one per Attack action")
    if row["true_strike_base_damage_modes"] != ["radiant_base", "weapon_normal_base"]:
        raise ValueError("Unsupported True Strike base-damage choices")
    kernel = NominalKernel(ProviderId.ELDRITCH_KNIGHT)

    @kernel.cached("eldritch_knight.hit_damage")
    def hit_damage(mode: str, critical: bool) -> Fraction:
        return eldritch_knight_hit_damage(row, target, level, mode, critical=critical)

    @kernel.cached("eldritch_knight.state")
    def optimize(
        round_index: int,
        action_index: int,
        attacks_remaining: int,
        true_remaining: int,
        studied: bool,
        prowess: bool,
    ) -> _ProviderDecision:
        state = (round_index, action_index, attacks_remaining, true_remaining, studied, prowess)
        if attacks_remaining == 0:
            if action_index + 1 < actions_by_round[round_index]:
                continuation = optimize(round_index, action_index + 1, attacks, true_maximum, studied, prowess)
            else:
                next_round = round_index + 1
                while next_round < len(actions_by_round) and actions_by_round[next_round] == 0:
                    next_round += 1
                if next_round == len(actions_by_round):
                    continuation = _ProviderDecision(DamageValue(), "end.horizon")
                else:
                    continuation = optimize(
                        next_round,
                        0,
                        attacks,
                        true_maximum,
                        studied if next_round == round_index + 1 else False,
                        prowess_enabled,
                    )
            return _ProviderDecision(continuation.value, "end.attack_action", continuation.payload)

        modes = ["ordinary"]
        if true_remaining:
            modes.extend(str(value) for value in row["true_strike_base_damage_modes"])
        declarations: list[_ProviderDecision] = []
        for mode in modes:
            true_strike = mode != "ordinary"
            ability = true_ability if true_strike else regular_ability
            attack_bonus = ability + pb + weapon_bonus
            next_true = true_remaining - int(true_strike)
            branches: list[tuple[Fraction, DamageValue]] = []
            for natural, natural_probability in natural_d20_distribution(studied_enabled and studied):
                critical = natural == 20
                hit = critical or (natural != 1 and natural + attack_bonus >= target.ac)
                if hit:
                    future = optimize(
                        round_index,
                        action_index,
                        attacks_remaining - 1,
                        next_true,
                        studied_state_after_final_attack(
                            studied_enabled, final_hit=True
                        ),
                        prowess,
                    ).value
                    branch = _damage_value(hit_damage(mode, critical)) + future
                else:
                    next_studied = studied_state_after_final_attack(
                        studied_enabled, final_hit=False
                    )
                    miss_future = optimize(
                        round_index,
                        action_index,
                        attacks_remaining - 1,
                        next_true,
                        next_studied,
                        prowess,
                    ).value
                    corrections = [_ProviderDecision(miss_future, "miss.retain")]
                    if prowess:
                        prowess_future = optimize(
                            round_index,
                            action_index,
                            attacks_remaining - 1,
                            next_true,
                            studied_state_after_final_attack(
                                studied_enabled, final_hit=True
                            ),
                            False,
                        ).value
                        prowess_value = (
                            _damage_value(hit_damage(mode, False), cost=ResourceCost(refreshable=Fraction(1)))
                            + prowess_future
                        )
                        corrections.append(_ProviderDecision(prowess_value, "miss.combat_prowess"))
                    branch = kernel.choose_provider(
                        "eldritch_knight.miss_correction",
                        (*state, mode, natural),
                        corrections,
                    ).value
                branches.append((natural_probability, branch))
            expected = kernel.expectation(branches)
            if true_strike:
                expected += DamageValue(cost=ResourceCost(refreshable=Fraction(1)))
            declarations.append(_ProviderDecision(expected, f"attack.{mode}", (mode,)))
        return kernel.choose_provider("eldritch_knight.attack_declaration", state, declarations)

    root = optimize(0, 0, attacks, true_maximum, False, prowess_enabled)

    def representative_trace() -> tuple[str, ...]:
        studied = False
        prowess = prowess_enabled
        rounds: list[str] = []
        for round_index, action_count in enumerate(actions_by_round):
            actions: list[str] = []
            for action_index in range(action_count):
                true_remaining = true_maximum
                declarations: list[str] = []
                for attacks_remaining in range(attacks, 0, -1):
                    state = (
                        round_index,
                        action_index,
                        attacks_remaining,
                        true_remaining,
                        studied,
                        prowess,
                    )
                    declaration = kernel.selected_provider(
                        "eldritch_knight.attack_declaration", state
                    )
                    mode = str(declaration.payload[0])
                    next_true = true_remaining - int(mode != "ordinary")
                    grouped: dict[tuple[str, bool, bool], Fraction] = defaultdict(
                        Fraction
                    )
                    for natural, probability in natural_d20_distribution(
                        studied_enabled and studied
                    ):
                        critical = natural == 20
                        ability = true_ability if mode != "ordinary" else regular_ability
                        hit = critical or (
                            natural != 1
                            and natural + ability + pb + weapon_bonus >= target.ac
                        )
                        if hit:
                            branch = (
                                "critical" if critical else "hit",
                                False,
                                prowess,
                            )
                        else:
                            correction = kernel.selected_provider(
                                "eldritch_knight.miss_correction",
                                (*state, mode, natural),
                            )
                            branch = (
                                correction.action_id,
                                False
                                if correction.action_id == "miss.combat_prowess"
                                else studied_enabled,
                                False
                                if correction.action_id == "miss.combat_prowess"
                                else prowess,
                            )
                        grouped[branch] += probability
                    resolution, studied, prowess = min(
                        grouped,
                        key=lambda item: (-grouped[item], item[0], item[1], item[2]),
                    )
                    declarations.append(f"{mode}:{resolution}")
                    true_remaining = next_true
                actions.append(f"A{action_index + 1}[{','.join(declarations)}]")
            rounds.append(f"R{round_index + 1}[{','.join(actions)}]")
            if action_count == 0:
                studied = False
            prowess = prowess_enabled
        return (*rounds, "representative=locally-modal-path", "policy=exact-observed-state")

    trace = representative_trace()
    cache = kernel.cache_info
    result = _solution(
        "eldritch_knight",
        target,
        root.value,
        len(actions_by_round),
        kernel,
        trace,
        {"expanded_states": cache.misses, "memo_hits": cache.hits, "policy_states": kernel.policy_states},
    )
    kernel.clear()
    return result


def battle_master_hit_damage(
    model: DamageAuthorityModel,
    row: dict[str, Any],
    target: TargetKnowledge,
    level: int,
    *,
    critical: bool = False,
    maneuver_sides: int = 0,
    part_of_attack_action: bool = True,
) -> Fraction:
    """Exact confirmed-hit packet for one legal Battle Master attack."""

    if not isinstance(critical, bool) or not isinstance(part_of_attack_action, bool):
        raise TypeError("Battle Master attack flags must be boolean")
    if (
        isinstance(maneuver_sides, bool)
        or not isinstance(maneuver_sides, int)
        or maneuver_sides < 0
        or maneuver_sides == 1
    ):
        raise ValueError("A maneuver die must be absent or have at least two sides")
    weapon = row["weapon"]
    multiplier = 2 if critical else 1
    dice: list[tuple[int, int, int | None]] = [
        (
            int(weapon["count"]) * multiplier,
            int(weapon["sides"]),
            3 if bool(weapon["great_weapon_fighting"]) else None,
        )
    ]
    if maneuver_sides:
        dice.append((multiplier, maneuver_sides, None))
    proficiency_bonus = model.progression("proficiency_bonus", level)
    great_weapon_master = (
        proficiency_bonus
        if row["great_weapon_master_attack_action_bonus"] == "proficiency_bonus"
        and part_of_attack_action
        else 0
    )
    flat = (
        int(row["ability_modifier"])
        + int(row["magic_weapon_bonus_by_level"][str(level)])
        + great_weapon_master
    )
    return expected_typed_packet(
        target,
        str(weapon["damage_type"]),
        tuple(dice),
        flat,
    )


def battle_master_precision_expected(
    required_correction: int,
    die_sides: int,
    corrected: DamageValue,
    failed: DamageValue,
    *,
    cost: ResourceCost,
) -> DamageValue:
    """Resolve Precision exactly while charging its die before the die result."""

    if (
        isinstance(required_correction, bool)
        or not isinstance(required_correction, int)
        or isinstance(die_sides, bool)
        or not isinstance(die_sides, int)
        or die_sides < 2
        or not 1 <= required_correction <= die_sides
    ):
        raise ValueError("Precision requires a reachable positive correction")
    if not isinstance(corrected, DamageValue) or not isinstance(failed, DamageValue):
        raise TypeError("Precision branches must be exact DamageValue instances")
    if not isinstance(cost, ResourceCost):
        raise TypeError("Precision cost must be an exact ResourceCost")
    success = Fraction(die_sides - required_correction + 1, die_sides)
    return (
        corrected.scale(success)
        + failed.scale(1 - success)
        + DamageValue(cost=cost)
    )


def _battle_master_solution(
    model: DamageAuthorityModel,
    config: dict[str, Any],
    row: dict[str, Any],
    target: TargetKnowledge,
    level: int,
) -> DamageSolution:
    policy = row["tactical_policy"]
    expected_policy = {
        "objective": NOMINAL_MODE_ID,
        "maneuver_choice_timing": "after_observed_attack_roll_result",
        "on_hit_die_effect": BATTLE_MASTER_PACKAGE_ID,
        "on_miss_die_effect": "attack_roll_bonus",
        "maneuver_die_consumption": "on_use_before_die_result",
        "maximum_maneuver_dice_per_attack": 1,
        "relentless_die_options": "same_as_superiority_die",
        "relentless_uses_per_turn": 1,
        "relentless_superiority_pool_cost": 0,
        "relentless_refresh": "start_of_next_turn",
        "hew_choice_timing": "after_observed_critical",
    }
    if policy != expected_policy:
        raise ValueError("Unsupported Battle Master tactical policy")
    if not row["hew_bonus_action_reserved"] or row["hew_follow_up_weapon"] != "same_weapon":
        raise ValueError("Nominal Hew requires the frozen reserved Bonus Action and same weapon")
    progression = level_config(config, level)
    pb = model.progression("proficiency_bonus", level)
    studied_enabled = bool(progression["studied_attacks"])
    prowess_enabled = bool(progression["combat_prowess"])
    attacks = int(progression["attacks_per_action"])
    relentless_per_turn = (
        int(policy["relentless_uses_per_turn"])
        if level >= int(row["relentless_minimum_level"])
        else 0
    )
    relentless_pool_cost = int(policy["relentless_superiority_pool_cost"])
    hew_enabled = bool(row["hew_critical_bonus_attack_once_per_fighter_turn"])
    pool = int(row["superiority_pool_by_level"][str(level)])
    prowess_after_failed_bonus = bool(
        config["fighter_mechanics"]["combat_prowess"]["eligible_after_failed_attack_roll_bonus"]
    )
    action_slots_by_round = tuple(
        int(actions_count) for actions_count in progression["action_slots_by_round"]
    )
    weapon = row["weapon"]
    weapon_bonus = int(row["magic_weapon_bonus_by_level"][str(level)])
    ability = int(row["ability_modifier"])
    attack_bonus = ability + pb + weapon_bonus
    superiority_sides = int(row["superiority_die_by_level"][str(level)])
    relentless_sides = int(row["relentless_die"])
    graze = Fraction(apply_defense(target, str(weapon["damage_type"]), int(row["graze_damage"])))
    kernel = NominalKernel(ProviderId.BATTLE_MASTER)

    @kernel.cached("battle_master.attack_damage")
    def attack_damage(critical: bool, maneuver_sides: int, part_of_action: bool) -> Fraction:
        return battle_master_hit_damage(
            model,
            row,
            target,
            level,
            critical=critical,
            maneuver_sides=maneuver_sides,
            part_of_attack_action=part_of_action,
        )

    @kernel.cached("battle_master.state")
    def optimize(
        round_index: int,
        action_index: int,
        attacks_remaining: int,
        studied: bool,
        superiority: int,
        prowess: bool,
        relentless: int,
        hew: bool,
    ) -> _ProviderDecision:
        if attacks_remaining == 0:
            if action_index + 1 < action_slots_by_round[round_index]:
                return optimize(
                    round_index,
                    action_index + 1,
                    attacks,
                    studied,
                    superiority,
                    prowess,
                    relentless,
                    hew,
                )
            next_round = round_index + 1
            while (
                next_round < len(action_slots_by_round)
                and action_slots_by_round[next_round] == 0
            ):
                next_round += 1
            if next_round == len(action_slots_by_round):
                return _ProviderDecision(DamageValue(), "end.horizon")
            return optimize(
                next_round,
                0,
                attacks,
                studied if next_round == round_index + 1 else False,
                superiority,
                prowess_enabled,
                relentless_per_turn,
                hew_enabled,
            )
        return attack_value(
            round_index,
            action_index,
            attacks_remaining - 1,
            studied,
            superiority,
            prowess,
            relentless,
            hew,
            True,
        )

    @kernel.cached("battle_master.attack")
    def attack_value(
        round_index: int,
        action_index: int,
        remaining_main_attacks: int,
        studied: bool,
        superiority: int,
        prowess: bool,
        relentless: int,
        hew: bool,
        part_of_action: bool,
    ) -> _ProviderDecision:
        state = (
            round_index,
            action_index,
            remaining_main_attacks,
            studied,
            superiority,
            prowess,
            relentless,
            hew,
            part_of_action,
        )

        def future(
            hit: bool,
            next_superiority: int,
            next_prowess: bool,
            next_relentless: int,
            next_hew: bool,
            critical: bool,
        ) -> DamageValue:
            next_studied = studied_state_after_final_attack(
                studied_enabled, final_hit=hit
            )
            continuation = optimize(
                round_index,
                action_index,
                remaining_main_attacks,
                next_studied,
                next_superiority,
                next_prowess,
                next_relentless,
                next_hew,
            ).value
            if part_of_action and critical and next_hew:
                bonus = attack_value(
                    round_index,
                    action_index,
                    remaining_main_attacks,
                    next_studied,
                    next_superiority,
                    next_prowess,
                    next_relentless,
                    False,
                    False,
                ).value + DamageValue(cost=ResourceCost(refreshable=Fraction(2)))
                return kernel.choose_provider(
                    "battle_master.hew",
                    (*state, next_superiority, next_prowess, next_relentless),
                    (
                        _ProviderDecision(continuation, "hew.decline"),
                        _ProviderDecision(bonus, "hew.use_same_weapon_bonus_action"),
                    ),
                ).value
            return continuation

        def failed_precision(next_superiority: int, next_relentless: int) -> DamageValue:
            outcomes = [
                _ProviderDecision(
                    _damage_value(graze)
                    + future(False, next_superiority, prowess, next_relentless, hew, False),
                    "precision.failure.graze",
                )
            ]
            if prowess and prowess_after_failed_bonus:
                outcomes.append(
                    _ProviderDecision(
                        _damage_value(
                            attack_damage(False, 0, part_of_action),
                            cost=ResourceCost(refreshable=Fraction(1)),
                        )
                        + future(True, next_superiority, False, next_relentless, hew, False),
                        "precision.failure.combat_prowess",
                    )
                )
            return kernel.choose_provider(
                "battle_master.failed_precision",
                (*state, next_superiority, next_relentless),
                outcomes,
            ).value

        natural_branches: list[tuple[Fraction, DamageValue]] = []
        for natural, natural_probability in natural_d20_distribution(studied_enabled and studied):
            critical = natural == 20
            hit = critical or (natural != 1 and natural + attack_bonus >= target.ac)
            choices: list[_ProviderDecision] = []
            if hit:
                choices.append(
                    _ProviderDecision(
                        _damage_value(attack_damage(critical, 0, part_of_action))
                        + future(True, superiority, prowess, relentless, hew, critical),
                        "hit.weapon",
                    )
                )
                if relentless:
                    choices.append(
                        _ProviderDecision(
                            _damage_value(
                                attack_damage(critical, relentless_sides, part_of_action),
                                cost=ResourceCost(refreshable=Fraction(1)),
                            )
                            + future(
                                True,
                                superiority - relentless_pool_cost,
                                prowess,
                                relentless - 1,
                                hew,
                                critical,
                            ),
                            "hit.relentless_damage_die",
                        )
                    )
                if superiority:
                    choices.append(
                        _ProviderDecision(
                            _damage_value(
                                attack_damage(critical, superiority_sides, part_of_action),
                                cost=ResourceCost(persistent_pool=Fraction(1)),
                            )
                            + future(True, superiority - 1, prowess, relentless, hew, critical),
                            f"hit.{BATTLE_MASTER_PACKAGE_ID}",
                        )
                    )
            else:
                choices.append(
                    _ProviderDecision(
                        _damage_value(graze)
                        + future(False, superiority, prowess, relentless, hew, False),
                        "miss.graze",
                    )
                )
                required = target.ac - (natural + attack_bonus)
                if natural != 1 and 1 <= required <= relentless_sides and relentless:
                    successful = (
                        _damage_value(attack_damage(False, 0, part_of_action))
                        + future(
                            True,
                            superiority - relentless_pool_cost,
                            prowess,
                            relentless - 1,
                            hew,
                            False,
                        )
                    )
                    failed = failed_precision(superiority - relentless_pool_cost, relentless - 1)
                    precision = battle_master_precision_expected(
                        required,
                        relentless_sides,
                        successful,
                        failed,
                        cost=ResourceCost(refreshable=Fraction(1)),
                    )
                    choices.append(_ProviderDecision(precision, "miss.precision.relentless"))
                if natural != 1 and 1 <= required <= superiority_sides and superiority:
                    successful = (
                        _damage_value(attack_damage(False, 0, part_of_action))
                        + future(True, superiority - 1, prowess, relentless, hew, False)
                    )
                    failed = failed_precision(superiority - 1, relentless)
                    precision = battle_master_precision_expected(
                        required,
                        superiority_sides,
                        successful,
                        failed,
                        cost=ResourceCost(persistent_pool=Fraction(1)),
                    )
                    choices.append(_ProviderDecision(precision, "miss.precision.superiority"))
                if prowess:
                    choices.append(
                        _ProviderDecision(
                            _damage_value(
                                attack_damage(False, 0, part_of_action),
                                cost=ResourceCost(refreshable=Fraction(1)),
                            )
                            + future(True, superiority, False, relentless, hew, False),
                            "miss.combat_prowess.weapon",
                        )
                    )
                    if relentless:
                        choices.append(
                            _ProviderDecision(
                                _damage_value(
                                    attack_damage(False, relentless_sides, part_of_action),
                                    cost=ResourceCost(refreshable=Fraction(2)),
                                )
                                + future(
                                    True,
                                    superiority - relentless_pool_cost,
                                    False,
                                    relentless - 1,
                                    hew,
                                    False,
                                ),
                                "miss.combat_prowess.relentless_damage_die",
                            )
                        )
                    if superiority:
                        choices.append(
                            _ProviderDecision(
                                _damage_value(
                                    attack_damage(False, superiority_sides, part_of_action),
                                    cost=ResourceCost(
                                        persistent_pool=Fraction(1), refreshable=Fraction(1)
                                    ),
                                )
                                + future(True, superiority - 1, False, relentless, hew, False),
                                f"miss.combat_prowess.{BATTLE_MASTER_PACKAGE_ID}",
                            )
                        )
            selected = kernel.choose_provider(
                "battle_master.observed_attack",
                (*state, natural),
                choices,
            )
            natural_branches.append((natural_probability, selected.value))
        return _ProviderDecision(kernel.expectation(natural_branches), "attack.resolve")

    root = optimize(
        0,
        0,
        attacks,
        False,
        pool,
        prowess_enabled,
        relentless_per_turn,
        hew_enabled,
    )

    def representative_attack(
        round_index: int,
        action_index: int,
        remaining_main_attacks: int,
        studied: bool,
        superiority: int,
        prowess: bool,
        relentless: int,
        hew: bool,
        part_of_action: bool,
    ) -> tuple[str, bool, int, bool, int, bool]:
        """Select one locally modal observed transition from the exact BM policy."""

        state = (
            round_index,
            action_index,
            remaining_main_attacks,
            studied,
            superiority,
            prowess,
            relentless,
            hew,
            part_of_action,
        )
        grouped: dict[
            tuple[str, bool, int, bool, int, bool, bool], Fraction
        ] = defaultdict(Fraction)

        def add(
            probability: Fraction,
            label: str,
            hit: bool,
            next_superiority: int,
            next_prowess: bool,
            next_relentless: int,
            next_hew: bool,
            use_hew: bool = False,
        ) -> None:
            grouped[
                (
                    label,
                    False if hit else studied_enabled,
                    next_superiority,
                    next_prowess,
                    next_relentless,
                    next_hew,
                    use_hew,
                )
            ] += probability

        for natural, natural_probability in natural_d20_distribution(
            studied_enabled and studied
        ):
            critical = natural == 20
            hit = critical or (
                natural != 1 and natural + attack_bonus >= target.ac
            )
            selected = kernel.selected_provider(
                "battle_master.observed_attack", (*state, natural)
            )
            action = selected.action_id
            if hit:
                if action == "hit.weapon":
                    next_superiority, next_relentless = superiority, relentless
                elif action == "hit.relentless_damage_die":
                    next_superiority = superiority - relentless_pool_cost
                    next_relentless = relentless - 1
                elif action == f"hit.{BATTLE_MASTER_PACKAGE_ID}":
                    next_superiority, next_relentless = superiority - 1, relentless
                else:
                    raise RuntimeError(
                        f"Unexpected representative Battle Master hit action {action!r}"
                    )
                next_hew = hew
                use_hew = False
                label = ("critical:" if critical else "hit:") + action
                if part_of_action and critical and hew:
                    hew_choice = kernel.selected_provider(
                        "battle_master.hew",
                        (*state, next_superiority, prowess, next_relentless),
                    )
                    use_hew = hew_choice.action_id == "hew.use_same_weapon_bonus_action"
                    next_hew = False if use_hew else hew
                    label += f"+{hew_choice.action_id}"
                add(
                    natural_probability,
                    label,
                    True,
                    next_superiority,
                    prowess,
                    next_relentless,
                    next_hew,
                    use_hew,
                )
                continue

            if action == "miss.graze":
                add(
                    natural_probability,
                    action,
                    False,
                    superiority,
                    prowess,
                    relentless,
                    hew,
                )
                continue
            if action in {"miss.precision.relentless", "miss.precision.superiority"}:
                uses_relentless = action.endswith("relentless")
                die_sides = relentless_sides if uses_relentless else superiority_sides
                required = target.ac - (natural + attack_bonus)
                success = Fraction(die_sides - required + 1, die_sides)
                next_superiority = (
                    superiority - relentless_pool_cost
                    if uses_relentless
                    else superiority - 1
                )
                next_relentless = relentless - 1 if uses_relentless else relentless
                add(
                    natural_probability * success,
                    f"{action}.success",
                    True,
                    next_superiority,
                    prowess,
                    next_relentless,
                    hew,
                )
                failure = kernel.selected_provider(
                    "battle_master.failed_precision",
                    (*state, next_superiority, next_relentless),
                )
                failure_hit = failure.action_id == "precision.failure.combat_prowess"
                add(
                    natural_probability * (1 - success),
                    f"{action}.{failure.action_id}",
                    failure_hit,
                    next_superiority,
                    False if failure_hit else prowess,
                    next_relentless,
                    hew,
                )
                continue
            if action.startswith("miss.combat_prowess"):
                next_superiority, next_relentless = superiority, relentless
                if action == "miss.combat_prowess.relentless_damage_die":
                    next_superiority -= relentless_pool_cost
                    next_relentless -= 1
                elif action == f"miss.combat_prowess.{BATTLE_MASTER_PACKAGE_ID}":
                    next_superiority -= 1
                elif action != "miss.combat_prowess.weapon":
                    raise RuntimeError(
                        f"Unexpected representative Combat Prowess action {action!r}"
                    )
                add(
                    natural_probability,
                    action,
                    True,
                    next_superiority,
                    False,
                    next_relentless,
                    hew,
                )
                continue
            raise RuntimeError(
                f"Unexpected representative Battle Master miss action {action!r}"
            )

        selected_transition = min(
            grouped,
            key=lambda item: (
                -grouped[item],
                item[0],
                item[1],
                item[2],
                item[3],
                item[4],
                item[5],
                item[6],
            ),
        )
        (
            label,
            next_studied,
            next_superiority,
            next_prowess,
            next_relentless,
            next_hew,
            use_hew,
        ) = selected_transition
        if use_hew:
            (
                bonus_label,
                next_studied,
                next_superiority,
                next_prowess,
                next_relentless,
                next_hew,
            ) = representative_attack(
                round_index,
                action_index,
                remaining_main_attacks,
                next_studied,
                next_superiority,
                next_prowess,
                next_relentless,
                False,
                False,
            )
            label += f"=>hew({bonus_label})"
        return (
            label,
            next_studied,
            next_superiority,
            next_prowess,
            next_relentless,
            next_hew,
        )

    def representative_trace() -> tuple[str, ...]:
        studied = False
        superiority = pool
        rounds: list[str] = []
        for round_index, action_count in enumerate(action_slots_by_round):
            prowess = prowess_enabled
            relentless = relentless_per_turn
            hew = hew_enabled
            actions: list[str] = []
            for action_index in range(action_count):
                entries: list[str] = []
                for attack_index in range(attacks):
                    (
                        label,
                        studied,
                        superiority,
                        prowess,
                        relentless,
                        hew,
                    ) = representative_attack(
                        round_index,
                        action_index,
                        attacks - attack_index - 1,
                        studied,
                        superiority,
                        prowess,
                        relentless,
                        hew,
                        True,
                    )
                    entries.append(label)
                actions.append(f"A{action_index + 1}[{','.join(entries)}]")
            rounds.append(f"R{round_index + 1}[{','.join(actions)}]")
            if action_count == 0:
                studied = False
        return (*rounds, "representative=locally-modal-path", "policy=exact-observed-state")

    trace = representative_trace()
    cache = kernel.cache_info
    result = _solution(
        "battle_master",
        target,
        root.value,
        len(action_slots_by_round),
        kernel,
        trace,
        {
            "expanded_states": cache.misses,
            "memo_hits": cache.hits,
            "policy_states": kernel.policy_states,
        },
    )
    kernel.clear()
    return result


@dataclass(frozen=True, slots=True)
class _EldritchKnightProvider:
    model: DamageAuthorityModel
    config: dict[str, Any]
    row: dict[str, Any]
    target: TargetKnowledge
    level: int

    provider_id = ProviderId.ELDRITCH_KNIGHT

    def solve(self) -> DamageSolution:
        return _eldritch_knight_solution(
            self.model, self.config, self.row, self.target, self.level
        )


@dataclass(frozen=True, slots=True)
class _BattleMasterProvider:
    model: DamageAuthorityModel
    config: dict[str, Any]
    row: dict[str, Any]
    target: TargetKnowledge
    level: int

    provider_id = ProviderId.BATTLE_MASTER

    def solve(self) -> DamageSolution:
        return _battle_master_solution(
            self.model, self.config, self.row, self.target, self.level
        )


def solve_comparator(
    model: DamageAuthorityModel,
    config: dict[str, Any],
    comparators: dict[str, Any],
    target: DamageTarget,
    level: int,
    provider_id: str,
    *,
    mode_id: str = NOMINAL_MODE_ID,
) -> DamageSolution:
    reject_unsupported_mode(mode_id)
    _validate_nominal_policy_contract(model, config)
    try:
        identity = ProviderId(provider_id)
    except ValueError as error:
        raise ValueError(f"Unsupported comparator provider {provider_id!r}") from error
    provider_types = {
        ProviderId.BATTLE_MASTER: _BattleMasterProvider,
        ProviderId.ELDRITCH_KNIGHT: _EldritchKnightProvider,
    }
    if identity not in provider_types:
        raise ValueError(f"Unsupported comparator provider {provider_id!r}")
    knowledge = TargetKnowledge.from_damage_target(target)
    row = comparators["damage"][identity.value]
    return provider_types[identity](model, config, row, knowledge, level).solve()


@dataclass(frozen=True, slots=True)
class _KineticPackage:
    entity_id: str | None
    tier: int
    psi: int
    blood: int

    @property
    def action_id(self) -> str:
        return "manifested_strike" if self.entity_id is None else f"rider.{self.entity_id}.t{self.tier}"


@dataclass(frozen=True, slots=True)
class _KineticStandalone:
    entity_id: str
    tier: int
    psi: int
    blood: int
    primary: Fraction
    aggregate: Fraction
    starts_zone: bool

    @property
    def action_id(self) -> str:
        return f"standalone.{self.entity_id}.t{self.tier}"


def _target_count(rule: dict[str, Any], tier: int, cluster_size: int, pb: int) -> int:
    target = next(
        (item for item in rule.get("targeting_by_tier", []) if int(item["tier"]) == tier),
        None,
    )
    if target is None:
        return 1
    kind = target["kind"]
    if kind == "fixed_additional":
        additional = int(target.get("additional_targets", 0))
    elif kind == "proficiency_bonus_additional":
        additional = pb
    elif kind == "cluster_remainder":
        additional = cluster_size - 1
    else:
        raise ValueError(f"Unsupported damage targeting kind {kind!r}")
    return 1 + min(max(0, cluster_size - 1), additional)


def cluster_signature(
    model: DamageAuthorityModel,
    config: dict[str, Any],
    discipline_id: str,
    level: int,
    cluster_size: int,
) -> tuple[tuple[str, int, int], ...]:
    """Identify clusters exposing identical provider actions and target counts."""

    profile = config["kv_profile"]
    pb = model.progression("proficiency_bonus", level)
    tier_minimum = {
        int(row["tier"]): int(row["minimum_level"])
        for row in model.projection["progressions"]["tier_minimum_levels"]
    }
    excluded = {
        item["entity_id"] for item in config["damage_matrix"]["excluded_stateful_features"]
    }
    signature: list[tuple[str, int, int]] = []
    for rule in model.features.values():
        if (
            rule["entity_id"] in excluded
            or discipline_id not in rule["discipline_ids"]
            or rule["damage_delivery"] not in {"on_hit_rider", "standalone"}
            or level < int(rule["minimum_level"])
        ):
            continue
        if profile["advanced_training_policy"] == "disabled" and rule["selectable_advanced_training"]:
            continue
        if rule.get("requires_additional_target") and cluster_size < 2:
            continue
        for tier_row in rule["damage_tiers"]:
            tier = int(tier_row["tier"])
            if level >= tier_minimum[tier]:
                signature.append(
                    (str(rule["entity_id"]), tier, _target_count(rule, tier, cluster_size, pb))
                )
    return tuple(signature)


def _raw_rule_distribution(
    damage: dict[str, Any], strike_die: int, psi_modifier: int
) -> tuple[tuple[int, Fraction], ...]:
    kind = damage["kind"]
    if kind == "none":
        return ((0, Fraction(1)),)
    if kind == "fixed":
        return ((int(damage["value"]), Fraction(1)),)
    if kind == "dice":
        return die_distribution(int(damage["count"]), int(damage["sides"]))
    if kind == "manifested_strike_dice":
        return die_distribution(int(damage["count"]), strike_die)
    if kind == "psionic_ability_modifier":
        return ((psi_modifier * int(damage.get("multiplier", 1)), Fraction(1)),)
    raise ValueError(f"Unsupported damage kind {kind!r}")


def _expected_rule_component(
    target: TargetKnowledge,
    damage: dict[str, Any],
    damage_type: str,
    strike_die: int,
    psi_modifier: int,
    save_probability: Fraction | None,
    *,
    ignore_resistance: bool = False,
) -> Fraction:
    distribution = _raw_rule_distribution(damage, strike_die, psi_modifier)
    full = sum(
        probability
        * apply_defense(
            target,
            damage_type,
            value,
            ignore_resistance=ignore_resistance,
        )
        for value, probability in distribution
    )
    resolution = damage["resolution"]
    if resolution == "always":
        return full
    if save_probability is None:
        raise ValueError("Save-gated damage lacks a canonical save")
    if resolution == "failed_save":
        return (1 - save_probability) * full
    if resolution == "half_on_success":
        half = sum(
            probability
            * apply_defense(
                target,
                damage_type,
                value // 2,
                ignore_resistance=ignore_resistance,
            )
            for value, probability in distribution
        )
        return (1 - save_probability) * full + save_probability * half
    raise ValueError(f"Unsupported damage resolution {resolution!r}")


def manifested_strike_packet_options(
    model: DamageAuthorityModel,
    target: TargetKnowledge,
    discipline_id: str,
    psi_modifier: int,
    strike_die: int,
) -> tuple[tuple[str, tuple[Fraction, Fraction, Fraction]], ...]:
    """Return all nondominated pre-roll strike type declarations."""

    discipline = model.disciplines[discipline_id]
    core = model.projection["core"]["manifested_strike"]
    normal_type = str(discipline["damage_type"])
    force_type = str(core["holdout_damage_type"])
    divisor = int(core["holdout_damage_divisor"])

    def packets(damage_type: str, holdout: bool) -> tuple[Fraction, Fraction, Fraction]:
        raw_divisor = divisor if holdout else 1
        graze = (
            Fraction(
                apply_defense(
                    target,
                    damage_type,
                    psi_modifier // raw_divisor,
                )
            )
            if discipline.get("graze_damage") == "psionic_ability_modifier"
            else Fraction()
        )
        hit = expected_typed_packet(
            target,
            damage_type,
            ((1, strike_die, None),),
            psi_modifier,
            raw_divisor=raw_divisor,
        )
        critical = expected_typed_packet(
            target,
            damage_type,
            ((int(core["critical_dice_multiplier"]), strike_die, None),),
            psi_modifier,
            raw_divisor=raw_divisor,
        )
        return graze, hit, critical

    normal = packets(normal_type, False)
    holdout = packets(force_type, True)
    if all(left >= right for left, right in zip(normal, holdout, strict=True)) and any(
        left > right for left, right in zip(normal, holdout, strict=True)
    ):
        return (("normal", normal),)
    if all(left >= right for left, right in zip(holdout, normal, strict=True)) and any(
        left > right for left, right in zip(holdout, normal, strict=True)
    ):
        return (("holdout", holdout),)
    return (("normal", normal), ("holdout", holdout))


def _kinetic_feature_values(
    model: DamageAuthorityModel,
    target: TargetKnowledge,
    discipline_id: str,
    cluster_size: int,
    level: int,
    pb: int,
    psi_modifier: int,
    strike_die: int,
    package: _KineticPackage,
) -> tuple[Fraction, Fraction]:
    if package.entity_id is None:
        return Fraction(), Fraction()
    rule = model.features[package.entity_id]
    tier_row = next(item for item in rule["damage_tiers"] if int(item["tier"]) == package.tier)
    discipline = model.disciplines[discipline_id]
    damage_type = (
        str(discipline["damage_type"])
        if rule["damage_type"] == "discipline"
        else str(rule["damage_type"])
    )
    save = tier_row.get("save")
    save_probability: Fraction | None = None
    if save:
        ability = (
            str(discipline["signature_save"])
            if save == "discipline_signature"
            else str(save)
        )
        save_probability = save_success_probability(
            target, ability, model.kv_save_dc(level, psi_modifier)
        )
    ignore_resistance = package.tier in rule.get("ignore_resistance_tiers", [])
    primary = _expected_rule_component(
        target,
        tier_row["damage"],
        damage_type,
        strike_die,
        psi_modifier,
        save_probability,
        ignore_resistance=ignore_resistance,
    )
    count = _target_count(rule, package.tier, cluster_size, pb)
    secondary_damage = tier_row.get("secondary_damage", tier_row["damage"])
    secondary = _expected_rule_component(
        target,
        secondary_damage,
        damage_type,
        strike_die,
        psi_modifier,
        save_probability,
        ignore_resistance=ignore_resistance,
    )
    return primary, primary + max(0, count - 1) * secondary


def _thermal_fracture_reduction(rule: dict[str, Any], tier: int) -> int:
    return next(
        (
            int(item["value"])
            for item in rule.get("armor_class_reduction_by_tier", [])
            if int(item["tier"]) == tier
        ),
        0,
    )


class _KineticVanguardProvider:
    provider_id = ProviderId.KINETIC_VANGUARD

    def __init__(
        self,
        model: DamageAuthorityModel,
        target: TargetKnowledge,
        packages: tuple[_KineticPackage, ...],
        rider_values: Mapping[_KineticPackage, tuple[Fraction, Fraction]],
        strike_options: tuple[tuple[str, tuple[Fraction, Fraction, Fraction]], ...],
        standalones_by_round: tuple[tuple[_KineticStandalone, ...], ...],
        attack_bonus: int,
        attacks_per_action: int,
        action_slots_by_round: tuple[int, ...],
        studied_enabled: bool,
        prowess_enabled: bool,
        psi_pool: int,
        blood_budget: int,
        mastery: dict[str, Any],
        mastery_uses: int,
        standalone_limit: int,
    ) -> None:
        self.model = model
        self.target = target
        self.packages = packages
        self.rider_values = rider_values
        self.strike_options = strike_options
        self.standalones_by_round = standalones_by_round
        self.attack_bonus = attack_bonus
        self.attacks_per_action = attacks_per_action
        self.action_slots_by_round = action_slots_by_round
        self.studied_enabled = studied_enabled
        self.prowess_enabled = prowess_enabled
        self.psi_pool = psi_pool
        self.blood_budget = blood_budget
        self.mastery = mastery
        self.mastery_uses = mastery_uses
        self.standalone_limit = standalone_limit
        limited = sorted(
            {
                str(package.entity_id)
                for package in packages
                if package.entity_id
                and model.features[package.entity_id]["repeatability"] == "once_per_attack_action"
            }
        )
        bits = {entity_id: 1 << index for index, entity_id in enumerate(limited)}
        self.package_bits = tuple(bits.get(package.entity_id, 0) for package in packages)
        self.fractures = tuple(
            _thermal_fracture_reduction(model.features[package.entity_id], package.tier)
            if package.entity_id
            else 0
            for package in packages
        )
        self.tier_two_limit = int(
            model.projection["core"]["overload"]["tier_two_limit_per_attack_action"]
        )
        self.kernel = NominalKernel(ProviderId.KINETIC_VANGUARD)

    def _mastered_tax(self, tax: int) -> int:
        return max(
            int(self.mastery["minimum_per_overload"]),
            tax // int(self.mastery["blood_tax_divisor"]),
        )

    def _payment_options(
        self, tax: int, mastery_remaining: int, mastery_mode: int
    ) -> tuple[tuple[int, int, int, bool, str], ...]:
        if tax == 0:
            return ((0, mastery_remaining, mastery_mode, False, "none"),)
        if mastery_mode == 1:
            return (
                (self._mastered_tax(tax), mastery_remaining, 1, False, "mastered"),
            )
        raw = (tax, mastery_remaining, 2, False, "raw")
        if mastery_mode == 0 and mastery_remaining:
            return (
                raw,
                (
                    self._mastered_tax(tax),
                    mastery_remaining - 1,
                    1,
                    True,
                    "mastery_activate",
                ),
            )
        return (raw,)

    @staticmethod
    def _declaration_cost(psi: int, tax: int, mastery_activated: bool) -> DamageValue:
        return DamageValue(
            cost=ResourceCost(
                self_damage=Fraction(tax),
                horizon_limited=Fraction(int(mastery_activated)),
                persistent_pool=Fraction(psi),
            )
        )

    @_provider_cached("kinetic_vanguard.round")
    def _round(
        self,
        round_index: int,
        studied: bool,
        psi: int,
        blood: int,
        mastery_remaining: int,
        zone_active: bool,
    ) -> _ProviderDecision:
        if round_index == len(self.action_slots_by_round):
            return _ProviderDecision(DamageValue(), "end.horizon")
        mastery_mode = 0 if mastery_remaining else 2
        return self._actions(
            round_index,
            self.action_slots_by_round[round_index],
            studied,
            self.prowess_enabled,
            0,
            psi,
            blood,
            mastery_remaining,
            mastery_mode,
            zone_active,
            0,
            False,
        )

    @_provider_cached("kinetic_vanguard.action_state")
    def _actions(
        self,
        round_index: int,
        action_slots_left: int,
        studied: bool,
        prowess: bool,
        ac_reduction: int,
        psi: int,
        blood: int,
        mastery_remaining: int,
        mastery_mode: int,
        zone_active: bool,
        standalone_count: int,
        attacked_this_turn: bool,
    ) -> _ProviderDecision:
        state = (
            round_index,
            action_slots_left,
            studied,
            prowess,
            ac_reduction,
            psi,
            blood,
            mastery_remaining,
            mastery_mode,
            zone_active,
            standalone_count,
            attacked_this_turn,
        )
        if action_slots_left == 0:
            carry_studied = studied if attacked_this_turn else False
            continuation = self._round(
                round_index + 1,
                carry_studied,
                psi,
                blood,
                mastery_remaining,
                zone_active,
            )
            return _ProviderDecision(continuation.value, "end.turn")
        attack = self._attacks(
            round_index,
            action_slots_left - 1,
            self.attacks_per_action,
            0,
            0,
            studied,
            prowess,
            ac_reduction,
            psi,
            blood,
            mastery_remaining,
            mastery_mode,
            zone_active,
            standalone_count,
        )
        candidates = [_ProviderDecision(attack.value, "action.attack")]
        if standalone_count < self.standalone_limit:
            for standalone_index, standalone in enumerate(
                self.standalones_by_round[round_index]
            ):
                if standalone.starts_zone and zone_active:
                    continue
                next_psi = psi + standalone.psi
                if next_psi > self.psi_pool:
                    continue
                for tax, next_mastery, next_mode, activated, payment_id in self._payment_options(
                    standalone.blood, mastery_remaining, mastery_mode
                ):
                    next_blood = blood + tax
                    if next_blood > self.blood_budget:
                        continue
                    continuation = self._actions(
                        round_index,
                        action_slots_left - 1,
                        studied,
                        prowess,
                        ac_reduction,
                        next_psi,
                        next_blood,
                        next_mastery,
                        next_mode,
                        zone_active or standalone.starts_zone,
                        standalone_count + 1,
                        attacked_this_turn,
                    ).value
                    immediate = _damage_value(standalone.primary, standalone.aggregate)
                    immediate += self._declaration_cost(standalone.psi, tax, activated)
                    candidates.append(
                        _ProviderDecision(
                            immediate + continuation,
                            f"action.{standalone.action_id}.payment.{payment_id}",
                            (
                                standalone_index,
                                tax,
                                next_mastery,
                                next_mode,
                                activated,
                            ),
                        )
                    )
        return self.kernel.choose_provider("kinetic_vanguard.action", state, candidates)

    @_provider_cached("kinetic_vanguard.attack_distribution")
    def _roll_probabilities(
        self, studied: bool, ac_reduction: int
    ) -> tuple[tuple[str, Fraction], ...]:
        return attack_outcome_distribution(
            self.target,
            self.attack_bonus,
            advantage=self.studied_enabled and studied,
            ac_reduction=ac_reduction,
        )

    def _roll_options(
        self,
        package_index: int,
        strike_index: int,
        outcome: str,
        prowess: bool,
        ac_reduction: int,
    ) -> tuple[_ProviderDecision, ...]:
        package = self.packages[package_index]
        strike = self.strike_options[strike_index][1]
        rider_primary, rider_aggregate = self.rider_values[package]
        fracture = self.fractures[package_index]
        if outcome != "miss":
            packet = strike[2 if outcome == "critical" else 1]
            value = _damage_value(packet + rider_primary, packet + rider_aggregate)
            return (
                _ProviderDecision(
                    value,
                    f"{outcome}.resolve",
                    (
                        studied_state_after_final_attack(
                            self.studied_enabled, final_hit=True
                        ),
                        prowess,
                        max(ac_reduction, fracture),
                    ),
                ),
            )
        options = [
            _ProviderDecision(
                _damage_value(strike[0]),
                "miss.graze",
                (
                    studied_state_after_final_attack(
                        self.studied_enabled, final_hit=False
                    ),
                    prowess,
                    ac_reduction,
                ),
            )
        ]
        if prowess:
            options.append(
                _ProviderDecision(
                    _damage_value(
                        strike[1] + rider_primary,
                        strike[1] + rider_aggregate,
                        ResourceCost(refreshable=Fraction(1)),
                    ),
                    "miss.combat_prowess",
                    (
                        studied_state_after_final_attack(
                            self.studied_enabled, final_hit=True
                        ),
                        False,
                        max(ac_reduction, fracture),
                    ),
                )
            )
        return tuple(options)

    def _resolve_attack_roll(
        self,
        round_index: int,
        action_slots_after: int,
        attacks_left_after: int,
        used_mask: int,
        tier_twos: int,
        package_index: int,
        strike_index: int,
        outcome: str,
        prowess: bool,
        ac_reduction: int,
        psi: int,
        blood: int,
        mastery_remaining: int,
        mastery_mode: int,
        zone_active: bool,
        standalone_count: int,
    ) -> _ProviderDecision:
        state = (
            round_index,
            action_slots_after,
            attacks_left_after,
            used_mask,
            tier_twos,
            package_index,
            strike_index,
            outcome,
            prowess,
            ac_reduction,
            psi,
            blood,
            mastery_remaining,
            mastery_mode,
            zone_active,
            standalone_count,
        )
        candidates: list[_ProviderDecision] = []
        for resolution in self._roll_options(
            package_index, strike_index, outcome, prowess, ac_reduction
        ):
            next_studied, next_prowess, next_reduction = resolution.payload
            continuation = self._attacks(
                round_index,
                action_slots_after,
                attacks_left_after,
                used_mask,
                tier_twos,
                bool(next_studied),
                bool(next_prowess),
                int(next_reduction),
                psi,
                blood,
                mastery_remaining,
                mastery_mode,
                zone_active,
                standalone_count,
            ).value
            candidates.append(
                _ProviderDecision(
                    resolution.value + continuation,
                    resolution.action_id,
                    resolution.payload,
                )
            )
        return self.kernel.choose_provider("kinetic_vanguard.attack_resolution", state, candidates)

    @_provider_cached("kinetic_vanguard.attack_state")
    def _attacks(
        self,
        round_index: int,
        action_slots_after: int,
        attacks_left: int,
        used_mask: int,
        tier_twos: int,
        studied: bool,
        prowess: bool,
        ac_reduction: int,
        psi: int,
        blood: int,
        mastery_remaining: int,
        mastery_mode: int,
        zone_active: bool,
        standalone_count: int,
    ) -> _ProviderDecision:
        state = (
            round_index,
            action_slots_after,
            attacks_left,
            used_mask,
            tier_twos,
            studied,
            prowess,
            ac_reduction,
            psi,
            blood,
            mastery_remaining,
            mastery_mode,
            zone_active,
            standalone_count,
        )
        if attacks_left == 0:
            continuation = self._actions(
                round_index,
                action_slots_after,
                studied,
                prowess,
                ac_reduction,
                psi,
                blood,
                mastery_remaining,
                mastery_mode,
                zone_active,
                standalone_count,
                True,
            )
            return _ProviderDecision(continuation.value, "end.attack_action")
        candidates: list[_ProviderDecision] = []
        for package_index, package in enumerate(self.packages):
            bit = self.package_bits[package_index]
            if bit and used_mask & bit:
                continue
            next_tier_twos = tier_twos + int(package.tier == 2)
            if next_tier_twos > self.tier_two_limit:
                continue
            next_psi = psi + package.psi
            if next_psi > self.psi_pool:
                continue
            next_mask = used_mask | bit
            for strike_index, (strike_name, _) in enumerate(self.strike_options):
                for tax, next_mastery, next_mode, activated, payment_id in self._payment_options(
                    package.blood, mastery_remaining, mastery_mode
                ):
                    next_blood = blood + tax
                    if next_blood > self.blood_budget:
                        continue
                    expected = DamageValue()
                    for outcome, probability in self._roll_probabilities(studied, ac_reduction):
                        resolution = self._resolve_attack_roll(
                            round_index,
                            action_slots_after,
                            attacks_left - 1,
                            next_mask,
                            next_tier_twos,
                            package_index,
                            strike_index,
                            outcome,
                            prowess,
                            ac_reduction,
                            next_psi,
                            next_blood,
                            next_mastery,
                            next_mode,
                            zone_active,
                            standalone_count,
                        )
                        expected += resolution.value.scale(probability)
                    expected += self._declaration_cost(package.psi, tax, activated)
                    candidates.append(
                        _ProviderDecision(
                            expected,
                            f"strike.{strike_name}.{package.action_id}.payment.{payment_id}",
                            (
                                package_index,
                                strike_index,
                                tax,
                                next_mastery,
                                next_mode,
                                activated,
                            ),
                        )
                    )
        return self.kernel.choose_provider("kinetic_vanguard.strike_declaration", state, candidates)

    def solve(self) -> tuple[DamageValue, _ProviderDecision]:
        root = self._round(0, False, 0, 0, self.mastery_uses, False)
        return root.value, root

    def representative_trace(self) -> tuple[str, ...]:
        """Reconstruct one deterministic locally modal path through the exact policy."""

        studied = False
        psi = 0
        blood = 0
        mastery_remaining = self.mastery_uses
        zone_active = False
        rounds: list[str] = []
        for round_index, initial_slots in enumerate(self.action_slots_by_round):
            prowess = self.prowess_enabled
            ac_reduction = 0
            mastery_mode = 0 if mastery_remaining else 2
            standalone_count = 0
            attacked = False
            slots = initial_slots
            entries: list[str] = []
            mastery_activated = False
            while slots:
                action = self._actions(
                    round_index,
                    slots,
                    studied,
                    prowess,
                    ac_reduction,
                    psi,
                    blood,
                    mastery_remaining,
                    mastery_mode,
                    zone_active,
                    standalone_count,
                    attacked,
                )
                if action.action_id.startswith("action.standalone."):
                    (
                        standalone_index,
                        tax,
                        mastery_remaining,
                        mastery_mode,
                        activated,
                    ) = action.payload
                    standalone = self.standalones_by_round[round_index][
                        int(standalone_index)
                    ]
                    psi += standalone.psi
                    blood += int(tax)
                    zone_active = zone_active or standalone.starts_zone
                    standalone_count += 1
                    slots -= 1
                    mastery_activated = mastery_activated or bool(activated)
                    entries.append(f"{standalone.entity_id}:T{standalone.tier}")
                    continue
                if action.action_id != "action.attack":
                    raise RuntimeError(
                        f"Unexpected representative action {action.action_id!r}"
                    )
                labels: list[str] = []
                used_mask = 0
                tier_twos = 0
                for attacks_left in range(self.attacks_per_action, 0, -1):
                    declaration = self._attacks(
                        round_index,
                        slots - 1,
                        attacks_left,
                        used_mask,
                        tier_twos,
                        studied,
                        prowess,
                        ac_reduction,
                        psi,
                        blood,
                        mastery_remaining,
                        mastery_mode,
                        zone_active,
                        standalone_count,
                    )
                    (
                        package_index,
                        strike_index,
                        tax,
                        mastery_remaining,
                        mastery_mode,
                        activated,
                    ) = declaration.payload
                    package = self.packages[int(package_index)]
                    psi += package.psi
                    blood += int(tax)
                    used_mask |= self.package_bits[int(package_index)]
                    tier_twos += int(package.tier == 2)
                    mastery_activated = mastery_activated or bool(activated)
                    grouped: dict[tuple[str, tuple[Any, ...]], Fraction] = defaultdict(
                        Fraction
                    )
                    for outcome, probability in self._roll_probabilities(
                        studied, ac_reduction
                    ):
                        resolution = self._resolve_attack_roll(
                            round_index,
                            slots - 1,
                            attacks_left - 1,
                            used_mask,
                            tier_twos,
                            int(package_index),
                            int(strike_index),
                            outcome,
                            prowess,
                            ac_reduction,
                            psi,
                            blood,
                            mastery_remaining,
                            mastery_mode,
                            zone_active,
                            standalone_count,
                        )
                        grouped[(resolution.action_id, resolution.payload)] += probability
                    resolved_action, resolved_payload = min(
                        grouped,
                        key=lambda item: (-grouped[item], item[0], repr(item[1])),
                    )
                    if resolved_action not in {
                        "hit.resolve",
                        "critical.resolve",
                        "miss.graze",
                        "miss.combat_prowess",
                    }:
                        raise RuntimeError(
                            f"Unexpected representative resolution {resolved_action!r}"
                        )
                    studied, prowess, ac_reduction = (
                        bool(resolved_payload[0]),
                        bool(resolved_payload[1]),
                        int(resolved_payload[2]),
                    )
                    if package.entity_id:
                        labels.append(f"{package.entity_id}:T{package.tier}")
                    elif self.strike_options[int(strike_index)][0] != "normal":
                        labels.append(
                            f"manifested_strike@{self.strike_options[int(strike_index)][0]}"
                        )
                entries.append(
                    "attack(" + (";".join(labels) if labels else "manifested_strike") + ")"
                )
                attacked = True
                slots -= 1
            if not attacked:
                studied = False
            marker = ";mastery" if mastery_activated else ""
            rounds.append(f"R{round_index + 1}[{','.join(entries)}{marker}]")
        return (*rounds, "representative=locally-modal-path", "policy=exact-observed-state")

    def statistics(self) -> dict[str, int]:
        cache = self.kernel.cache_info
        return {
            "expanded_states": cache.misses,
            "memo_hits": cache.hits,
            "policy_states": self.kernel.policy_states,
        }

    def clear(self) -> None:
        self.kernel.clear()


def _validate_nominal_policy_contract(model: DamageAuthorityModel, config: dict[str, Any]) -> None:
    if config.get("damage_model") != {
        "mode_id": NOMINAL_MODE_ID,
        "target_knowledge_contract_id": TARGET_KNOWLEDGE_CONTRACT_ID,
        "numeric_representation": NUMERIC_REPRESENTATION_ID,
        "finite_hp_mode": "unsupported_in_pr1",
        "provider_ids": list(PROVIDER_IDS),
    }:
        raise ValueError("Unsupported nominal damage-model identity")
    methodology = config.get("methodology", {})
    if (
        methodology.get("rounds") != 3
        or methodology.get("target_death") is not False
        or methodology.get("ally_turns") is not False
        or methodology.get("legal_positioning_assumed") is not True
        or methodology.get("legendary_resistance") != "metadata_only"
    ):
        raise ValueError("Unsupported nominal benchmark boundary")
    action_economy = model.projection["core"]["action_economy"]
    if action_economy != {
        "standalone_psionic_action_limit_per_turn": 1,
        "action_surge_allows_additional_standalone_psionic_action": False,
    }:
        raise ValueError("Unsupported standalone psionic Action policy")
    fighter = config["fighter_mechanics"]
    if fighter["studied_attacks"] != {
        "trigger": "resolved_miss_after_hit_instead_effects",
        "benefit": "advantage_on_next_attack_against_same_target",
        "expiry": "end_of_next_turn",
    }:
        raise ValueError("Unsupported Studied Attacks timing policy")
    if fighter["combat_prowess"] != {
        "trigger": "attack_roll_miss",
        "effect": "hit_instead",
        "uses_per_turn": 1,
        "reset": "start_of_next_turn",
        "activation_policy": "optimal_after_observed_miss",
        "eligible_after_failed_attack_roll_bonus": True,
    }:
        raise ValueError("Unsupported Combat Prowess timing policy")
    optimization = config["damage_matrix"]["optimization"]
    if optimization != {
        "scope": "per_target_discipline_cluster",
        "objective": [
            "aggregate_damage",
            "primary_damage",
            "least_self_damage",
            "least_horizon_limited_use",
            "least_persistent_pool_use",
            "least_refreshable_use",
            "smallest_canonical_action_id",
        ],
        "resource_cost_classes": {
            "order": [
                "self_damage",
                "horizon_limited",
                "persistent_pool",
                "refreshable",
            ],
            "kinetic_vanguard": {
                "self_damage": ["blood_tax"],
                "horizon_limited": ["overload_mastery"],
                "persistent_pool": ["psi"],
                "refreshable": ["combat_prowess"],
            },
            "battle_master": {
                "self_damage": [],
                "horizon_limited": [],
                "persistent_pool": ["superiority_die"],
                "refreshable": [
                    "relentless",
                    "combat_prowess",
                    "hew",
                    "bonus_action",
                ],
            },
            "eldritch_knight": {
                "self_damage": [],
                "horizon_limited": [],
                "persistent_pool": [],
                "refreshable": ["true_strike_replacement", "combat_prowess"],
            },
        },
        "decision_timing": {
            "pre_roll_declarations": "optimize_from_legally_observed_state",
            "unobserved_outcome_lookahead": False,
            "post_roll_decisions": [
                "battle_master_precision",
                "combat_prowess",
                "battle_master_on_hit_die",
                "hew_bonus_attack",
            ],
        },
    }:
        raise ValueError("Unsupported nominal optimization contract")
    boundary = {
        "rider_conditions_and_save_outcomes": "excluded_from_damage",
        "ally_turn_accuracy_and_damage": "excluded",
        "modeled_self_attack_exception": "thermal_fracture_ac_reduction",
    }
    if config["damage_matrix"]["non_damage_effect_boundary"] != boundary:
        raise ValueError("Unsupported non-damage effect boundary")
    if config["kv_profile"]["attack_replacement_policy"] != "all_manifested_strikes":
        raise ValueError("Unsupported Kinetic Vanguard attack replacement policy")


def solve_kinetic_vanguard(
    model: DamageAuthorityModel,
    config: dict[str, Any],
    target: DamageTarget,
    level: int,
    discipline_id: str,
    cluster_size: int,
    *,
    mode_id: str = NOMINAL_MODE_ID,
) -> DamageSolution:
    reject_unsupported_mode(mode_id)
    _validate_nominal_policy_contract(model, config)
    if discipline_id not in model.disciplines:
        raise ValueError(f"Unsupported discipline {discipline_id!r}")
    if cluster_size not in {int(value) for value in config["methodology"]["cluster_sizes"]}:
        raise ValueError(f"Unsupported cluster size {cluster_size}")
    knowledge = TargetKnowledge.from_damage_target(target)
    profile = config["kv_profile"]
    psi_modifier = int(profile["psionic_ability_modifier"])
    pb = model.progression("proficiency_bonus", level)
    strike_die = model.progression("manifested_strike_die", level)
    psi_pool = model.progression("psi_points", level)
    progression = level_config(config, level)
    attacks_per_action = int(progression["attacks_per_action"])
    action_slots = tuple(int(value) for value in progression["action_slots_by_round"])
    studied_enabled = bool(progression["studied_attacks"])
    prowess_enabled = bool(progression["combat_prowess"])
    attack_bonus = model.kv_attack_bonus(level, psi_modifier) + int(profile["archery_attack_bonus"])
    mastery = model.projection["core"]["overload"]["mastery"]
    hit_points = (
        int(profile["hit_point_model"]["first_level_base"])
        + int(profile["constitution_modifier"])
        + (level - 1)
        * (
            int(profile["hit_point_model"]["later_level_average"])
            + int(profile["constitution_modifier"])
        )
    )
    blood_budget = int(Fraction(str(profile["blood_tax_hp_fraction"])) * hit_points)
    mastery_uses = (
        int(mastery["uses_per_rest"])
        if level >= int(mastery["minimum_level"])
        else 0
    )
    exclusions = {
        item["entity_id"] for item in config["damage_matrix"]["excluded_stateful_features"]
    }
    for entity_id in exclusions:
        feature = model.features.get(entity_id)
        if (
            feature is None
            or feature.get("damage_timing") != "start_of_affected_turn_after_repeat_save"
        ):
            raise ValueError(
                f"Damage exclusion {entity_id} lacks canonical deferred timing"
            )
    tier_minimum = {
        int(row["tier"]): int(row["minimum_level"])
        for row in model.projection["progressions"]["tier_minimum_levels"]
    }
    packages = [_KineticPackage(None, 0, 0, 0)]
    for rule in model.features.values():
        if (
            discipline_id not in rule["discipline_ids"]
            or rule["damage_delivery"] != "on_hit_rider"
            or level < int(rule["minimum_level"])
        ):
            continue
        if profile["advanced_training_policy"] == "disabled" and rule["selectable_advanced_training"]:
            continue
        if rule.get("requires_additional_target") and cluster_size < 2:
            continue
        for tier_row in rule["damage_tiers"]:
            tier = int(tier_row["tier"])
            if level >= tier_minimum[tier]:
                packages.append(
                    _KineticPackage(
                        str(rule["entity_id"]),
                        tier,
                        int(rule["psi_cost"]),
                        model.blood_tax(level, tier),
                    )
                )
    package_tuple = tuple(packages)
    rider_values = {
        package: _kinetic_feature_values(
            model,
            knowledge,
            discipline_id,
            cluster_size,
            level,
            pb,
            psi_modifier,
            strike_die,
            package,
        )
        for package in package_tuple
    }
    strike_options = manifested_strike_packet_options(
        model, knowledge, discipline_id, psi_modifier, strike_die
    )
    standalones_by_round: list[tuple[_KineticStandalone, ...]] = []
    for round_index in range(len(action_slots)):
        standalones: list[_KineticStandalone] = []
        for rule in model.features.values():
            if (
                rule["entity_id"] in exclusions
                or discipline_id not in rule["discipline_ids"]
                or rule["damage_delivery"] != "standalone"
                or level < int(rule["minimum_level"])
            ):
                continue
            if profile["advanced_training_policy"] == "disabled" and rule["selectable_advanced_training"]:
                continue
            if rule.get("requires_additional_target") and cluster_size < 2:
                continue
            for tier_row in rule["damage_tiers"]:
                tier = int(tier_row["tier"])
                if level < tier_minimum[tier]:
                    continue
                package = _KineticPackage(
                    str(rule["entity_id"]),
                    tier,
                    int(rule["psi_cost"]),
                    model.blood_tax(level, tier),
                )
                primary, aggregate = _kinetic_feature_values(
                    model,
                    knowledge,
                    discipline_id,
                    cluster_size,
                    level,
                    pb,
                    psi_modifier,
                    strike_die,
                    package,
                )
                if rule.get("damage_repetition") == "remaining_round_starts":
                    repetitions = max(
                        0, int(config["methodology"]["rounds"]) - 1 - round_index
                    )
                    primary *= repetitions
                    aggregate *= repetitions
                standalones.append(
                    _KineticStandalone(
                        str(rule["entity_id"]),
                        tier,
                        package.psi,
                        package.blood,
                        primary,
                        aggregate,
                        bool(rule.get("starts_persistent_zone")),
                    )
                )
        standalones_by_round.append(tuple(standalones))
    standalone_limit = int(
        model.projection["core"]["action_economy"][
            "standalone_psionic_action_limit_per_turn"
        ]
    )
    provider = _KineticVanguardProvider(
        model,
        knowledge,
        package_tuple,
        rider_values,
        strike_options,
        tuple(standalones_by_round),
        attack_bonus,
        attacks_per_action,
        action_slots,
        studied_enabled,
        prowess_enabled,
        psi_pool,
        blood_budget,
        mastery,
        mastery_uses,
        standalone_limit,
    )
    horizon, _root = provider.solve()
    trace = provider.representative_trace()
    statistics = provider.statistics()
    result = _solution(
        "kinetic_vanguard",
        knowledge,
        horizon,
        len(action_slots),
        provider.kernel,
        trace,
        statistics,
    )
    provider.clear()
    return result

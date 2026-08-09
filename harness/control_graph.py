"""Compile Control Authority v2.1 and evaluate exact gate reliability.

This module is intentionally a consumer of :class:`ControlAuthorityV2Model`.
It neither parses the canonical YAML nor duplicates the TypeScript authority
validator.  The compiled representation is immutable, namespaces every local
authority ID by effect, and treats gate edges and typed events--never source
array position--as execution structure.

The reliability evaluator is deliberately weight-free.  It enumerates joint
worlds with :class:`fractions.Fraction`, preserving correlation within shared
gates and independence between per-target gates.  Timeline code can supply
later typed events (including repeat-save windows); this module does not invent
initiative, target membership, choices, or battlefield state.
"""

from __future__ import annotations

import json
import math
from hashlib import sha256
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from harness.authority import DEFAULT_AUTHORITY, ControlAuthorityV2Model


class ControlGraphError(ValueError):
    """Raised when validated authority cannot be compiled or evaluated safely."""


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenMap(
            tuple(
                (str(key), _deep_freeze(value[key]))
                for key in sorted(value, key=lambda item: str(item))
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ControlGraphError(f"Cannot freeze unsupported authority value {type(value).__name__}")


def _thaw(value: Any) -> Any:
    if isinstance(value, FrozenMap):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class FrozenMap(Mapping[str, Any]):
    """A small, recursively immutable mapping used by the compiled IR."""

    entries: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        keys = [key for key, _value in self.entries]
        if len(keys) != len(set(keys)):
            raise ControlGraphError("FrozenMap contains duplicate keys")

    def __getitem__(self, key: str) -> Any:
        for candidate, value in self.entries:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self)


def _frozen_map(value: Mapping[str, Any]) -> FrozenMap:
    frozen = _deep_freeze(value)
    if not isinstance(frozen, FrozenMap):  # pragma: no cover - defensive
        raise ControlGraphError("Expected an authority object")
    return frozen


def _freeze_json_value(value: Any, *, path: str) -> Any:
    """Freeze a strict JSON value without silently coercing provenance keys."""

    if isinstance(value, Mapping):
        entries: list[tuple[str, Any]] = []
        invalid_keys = [
            key for key in value
            if not isinstance(key, str) or not key
        ]
        if invalid_keys:
            raise ControlGraphError(f"{path} keys must be nonempty strings")
        for key in sorted(value):
            entries.append(
                (
                    key,
                    _freeze_json_value(value[key], path=f"{path}.{key}"),
                )
            )
        return FrozenMap(tuple(entries))
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ControlGraphError(
        f"{path} must contain only deterministic JSON-safe values; "
        f"got {type(value).__name__}"
    )


def _frozen_json_map(value: Mapping[str, Any], *, path: str) -> FrozenMap:
    frozen = _freeze_json_value(value, path=path)
    if not isinstance(frozen, FrozenMap):  # pragma: no cover - root is typed
        raise ControlGraphError(f"{path} must be a JSON object")
    return frozen


@dataclass(frozen=True, order=True)
class QualifiedId:
    namespace: str
    local_id: str

    def __str__(self) -> str:
        return f"{self.namespace}::{self.local_id}"


@dataclass(frozen=True)
class CompiledEvent:
    kind: str
    owner: str | None
    turn_anchor: str | None
    key: str
    data: FrozenMap

    @classmethod
    def compile(cls, value: Mapping[str, Any]) -> "CompiledEvent":
        copied = dict(value)
        return cls(
            kind=str(copied["kind"]),
            owner=str(copied["owner"]) if "owner" in copied else None,
            turn_anchor=str(copied["turn_anchor"]) if "turn_anchor" in copied else None,
            key=_canonical(copied),
            data=_frozen_map(copied),
        )


@dataclass(frozen=True)
class CompiledMagnitude:
    kind: str
    data: FrozenMap


CONTROL_MAGNITUDE_KINDS = frozenset(
    {
        "condition",
        "forced_movement",
        "speed_reduction",
        "speed_zero",
        "difficult_terrain",
        "persistent_elevation",
        "fall",
        "attack_disadvantage",
        "reaction_denial",
        "movement_option_denial",
        "numerical_modifier",
    }
)


def compile_magnitude(value: Mapping[str, Any]) -> CompiledMagnitude:
    """Compile one already-validated magnitude through an explicit 11-kind dispatch."""

    kind = value.get("kind")
    # Keep this explicit: adding a contract kind must produce a conscious compiler change.
    if kind == "condition":
        pass
    elif kind == "forced_movement":
        pass
    elif kind == "speed_reduction":
        pass
    elif kind == "speed_zero":
        pass
    elif kind == "difficult_terrain":
        pass
    elif kind == "persistent_elevation":
        pass
    elif kind == "fall":
        pass
    elif kind == "attack_disadvantage":
        pass
    elif kind == "reaction_denial":
        pass
    elif kind == "movement_option_denial":
        pass
    elif kind == "numerical_modifier":
        pass
    else:
        raise ControlGraphError(f"Unsupported ControlMagnitudeV2 kind: {kind!r}")
    return CompiledMagnitude(str(kind), _frozen_map(value))


@dataclass(frozen=True)
class CompiledChoice:
    choice_id: str
    qualified_id: QualifiedId
    kind: str
    timing: CompiledEvent
    resolution: str
    scope: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class CompiledArea:
    area_id: str
    qualified_id: QualifiedId
    shape: str
    placement: FrozenMap
    persistent: bool
    triggers: tuple[CompiledEvent, ...]
    exit_behavior: str
    entry_policy: FrozenMap | None
    movement: FrozenMap | None
    data: FrozenMap


@dataclass(frozen=True)
class CompiledSelector:
    selector_id: str
    qualified_id: QualifiedId
    role: str
    selection: str
    count: FrozenMap
    range: FrozenMap
    restrictions: tuple[FrozenMap, ...]
    gate_scope: str
    area: CompiledArea | None


@dataclass(frozen=True)
class CompiledStacking:
    key: str
    mode: str
    refresh: str
    replacement_group: str | None
    dominates_component_ids: tuple[str, ...]
    data: FrozenMap


@dataclass(frozen=True)
class CompiledComponent:
    component_id: str
    qualified_id: QualifiedId
    target_selector_ids: tuple[str, ...]
    magnitude: CompiledMagnitude
    duration: FrozenMap
    cadence_apply: tuple[CompiledEvent, ...]
    cadence_repeat: tuple[CompiledEvent, ...]
    cadence_end: tuple[CompiledEvent, ...]
    stacking: CompiledStacking
    choice_id: str | None
    choice_option_id: str | None

    @property
    def instantaneous(self) -> bool:
        return self.duration["kind"] == "instantaneous"


@dataclass(frozen=True)
class CompiledBranch:
    branch_id: str
    qualified_id: QualifiedId
    outcome: str
    applies: tuple[str, ...]
    replaces: tuple[str, ...]
    terminates: tuple[str, ...]
    refreshes: tuple[str, ...]
    next_gate_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompiledGate:
    gate_id: str
    qualified_id: QualifiedId
    selector_ids: tuple[str, ...]
    requires_active_component_ids: tuple[str, ...]
    trigger: CompiledEvent
    gate_scope: str
    resolution_kind: str
    ability: str | None
    role: str | None
    mode: str | None
    branches: tuple[CompiledBranch, ...]
    _branch_by_outcome: Mapping[str, CompiledBranch] = field(compare=False, hash=False, repr=False)

    def branch_for_outcome(self, outcome: str) -> CompiledBranch:
        try:
            return self._branch_by_outcome[outcome]
        except KeyError as error:
            raise ControlGraphError(f"Gate {self.gate_id!r} has no {outcome!r} branch") from error


@dataclass(frozen=True)
class CompiledRelationships:
    replacement_groups: tuple[tuple[str, tuple[str, ...]], ...]
    dominance: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class ChoiceBindings(Mapping[str, str]):
    values: tuple[tuple[str, str], ...]

    def __getitem__(self, key: str) -> str:
        for candidate, value in self.values:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self.values)

    def __len__(self) -> int:
        return len(self.values)


@dataclass(frozen=True)
class CompiledEffect:
    entity_id: str
    tier: int
    effect_id: str
    authority_sha256: str
    inheritance: FrozenMap
    policy: FrozenMap
    choices: tuple[CompiledChoice, ...]
    selectors: tuple[CompiledSelector, ...]
    components: tuple[CompiledComponent, ...]
    root_gate_ids: tuple[str, ...]
    gates: tuple[CompiledGate, ...]
    concentration: FrozenMap
    relationships: CompiledRelationships
    canonical_input: FrozenMap
    _choice_by_id: Mapping[str, CompiledChoice] = field(compare=False, hash=False, repr=False)
    _selector_by_id: Mapping[str, CompiledSelector] = field(compare=False, hash=False, repr=False)
    _component_by_id: Mapping[str, CompiledComponent] = field(compare=False, hash=False, repr=False)
    _gate_by_id: Mapping[str, CompiledGate] = field(compare=False, hash=False, repr=False)
    _gates_by_event: Mapping[str, tuple[CompiledGate, ...]] = field(compare=False, hash=False, repr=False)
    _outgoing: Mapping[str, tuple[str, ...]] = field(compare=False, hash=False, repr=False)

    def choice(self, choice_id: str) -> CompiledChoice:
        try:
            return self._choice_by_id[choice_id]
        except KeyError as error:
            raise ControlGraphError(f"Unknown choice ID {choice_id!r} in {self.effect_id}") from error

    def selector(self, selector_id: str) -> CompiledSelector:
        try:
            return self._selector_by_id[selector_id]
        except KeyError as error:
            raise ControlGraphError(f"Unknown selector ID {selector_id!r} in {self.effect_id}") from error

    def component(self, component_id: str) -> CompiledComponent:
        try:
            return self._component_by_id[component_id]
        except KeyError as error:
            raise ControlGraphError(f"Unknown component ID {component_id!r} in {self.effect_id}") from error

    def gate(self, gate_id: str) -> CompiledGate:
        try:
            return self._gate_by_id[gate_id]
        except KeyError as error:
            raise ControlGraphError(f"Unknown gate ID {gate_id!r} in {self.effect_id}") from error

    def gates_for_event(self, event: CompiledEvent | Mapping[str, Any]) -> tuple[CompiledGate, ...]:
        compiled = event if isinstance(event, CompiledEvent) else CompiledEvent.compile(event)
        return self._gates_by_event.get(compiled.key, ())

    def outgoing_gate_ids(self, gate_id: str) -> tuple[str, ...]:
        self.gate(gate_id)
        return self._outgoing[gate_id]

    def bind_choices(self, bindings: Mapping[str, str] | None = None) -> ChoiceBindings:
        supplied = dict(bindings or {})
        expected = set(self._choice_by_id)
        missing, unknown = sorted(expected - supplied.keys()), sorted(supplied.keys() - expected)
        if missing or unknown:
            raise ControlGraphError(
                f"{self.effect_id} choice bindings are incomplete; missing={missing}, unknown={unknown}"
            )
        for choice_id, option_id in supplied.items():
            if option_id not in self.choice(choice_id).options:
                raise ControlGraphError(
                    f"{self.effect_id} choice {choice_id!r} does not allow option {option_id!r}"
                )
        return ChoiceBindings(tuple(sorted(supplied.items())))


@dataclass(frozen=True)
class CompiledMastery:
    mastery_id: str
    minimum_level: int
    triggers: tuple[CompiledEvent, ...]
    component: CompiledComponent


@dataclass(frozen=True)
class CompiledExclusion:
    entity_id: str
    tier: int
    profile_id: str
    reason: str


@dataclass(frozen=True)
class CompiledAuthority:
    projection_version: str
    contract_version: str
    authority_path: str
    authority_sha256: str
    rules_version: str
    schema_version: str
    supported_level_range: tuple[int, int]
    active_profile: FrozenMap
    target_data_requirements: tuple[str, ...]
    policy_inputs: FrozenMap
    programs: tuple[CompiledEffect, ...]
    masteries: tuple[CompiledMastery, ...]
    tactical_master: FrozenMap
    exclusions: tuple[CompiledExclusion, ...]
    _program_by_id: Mapping[str, CompiledEffect] = field(compare=False, hash=False, repr=False)
    _program_by_key: Mapping[tuple[str, int], CompiledEffect] = field(compare=False, hash=False, repr=False)
    _mastery_by_id: Mapping[str, CompiledMastery] = field(compare=False, hash=False, repr=False)

    def program(self, effect_id: str) -> CompiledEffect:
        try:
            return self._program_by_id[effect_id]
        except KeyError as error:
            raise ControlGraphError(f"Unknown compiled effect ID: {effect_id}") from error

    def program_for(self, entity_id: str, tier: int) -> CompiledEffect:
        try:
            return self._program_by_key[(entity_id, tier)]
        except KeyError as error:
            raise ControlGraphError(f"No executable control program for {entity_id}:T{tier}") from error

    def mastery(self, mastery_id: str) -> CompiledMastery:
        try:
            return self._mastery_by_id[mastery_id]
        except KeyError as error:
            raise ControlGraphError(f"Unknown compiled mastery ID: {mastery_id}") from error


def _compile_choice(namespace: str, value: Mapping[str, Any]) -> CompiledChoice:
    choice_id = str(value["choice_id"])
    return CompiledChoice(
        choice_id=choice_id,
        qualified_id=QualifiedId(namespace, choice_id),
        kind=str(value["kind"]),
        timing=CompiledEvent.compile(value["timing"]),
        resolution=str(value["resolution"]),
        scope=str(value["scope"]),
        options=tuple(str(item) for item in value["options"]),
    )


def _compile_area(namespace: str, value: Mapping[str, Any]) -> CompiledArea:
    area_id = str(value["area_id"])
    return CompiledArea(
        area_id=area_id,
        qualified_id=QualifiedId(namespace, area_id),
        shape=str(value["shape"]),
        placement=_frozen_map(value["placement"]),
        persistent=bool(value["persistent"]),
        triggers=tuple(CompiledEvent.compile(item) for item in value["triggers"]),
        exit_behavior=str(value["exit_behavior"]),
        entry_policy=_frozen_map(value["entry_policy"]) if "entry_policy" in value else None,
        movement=_frozen_map(value["movement"]) if "movement" in value else None,
        data=_frozen_map(value),
    )


def _compile_selector(namespace: str, value: Mapping[str, Any]) -> CompiledSelector:
    selector_id = str(value["selector_id"])
    return CompiledSelector(
        selector_id=selector_id,
        qualified_id=QualifiedId(namespace, selector_id),
        role=str(value["role"]),
        selection=str(value["selection"]),
        count=_frozen_map(value["count"]),
        range=_frozen_map(value["range"]),
        restrictions=tuple(_frozen_map(item) for item in value["restrictions"]),
        gate_scope=str(value["gate_scope"]),
        area=_compile_area(namespace, value["area"]) if "area" in value else None,
    )


def _compile_component(namespace: str, value: Mapping[str, Any]) -> CompiledComponent:
    component_id = str(value["component_id"])
    cadence = value["cadence"]
    stacking = value["stacking"]
    requirement = value.get("choice_requirement")
    return CompiledComponent(
        component_id=component_id,
        qualified_id=QualifiedId(namespace, component_id),
        target_selector_ids=tuple(str(item) for item in value["target_selector_ids"]),
        magnitude=compile_magnitude(value["magnitude"]),
        duration=_frozen_map(value["duration"]),
        cadence_apply=tuple(CompiledEvent.compile(item) for item in cadence["apply"]),
        cadence_repeat=tuple(CompiledEvent.compile(item) for item in cadence["repeat"]),
        cadence_end=tuple(CompiledEvent.compile(item) for item in cadence["end"]),
        stacking=CompiledStacking(
            key=str(stacking["key"]),
            mode=str(stacking["mode"]),
            refresh=str(stacking["refresh"]),
            replacement_group=str(stacking["replacement_group"]) if "replacement_group" in stacking else None,
            dominates_component_ids=tuple(str(item) for item in stacking["dominates_component_ids"]),
            data=_frozen_map(stacking),
        ),
        choice_id=str(requirement["choice_id"]) if requirement is not None else None,
        choice_option_id=str(requirement["option_id"]) if requirement is not None else None,
    )


def _compile_branch(namespace: str, value: Mapping[str, Any]) -> CompiledBranch:
    branch_id = str(value["branch_id"])
    return CompiledBranch(
        branch_id=branch_id,
        qualified_id=QualifiedId(namespace, branch_id),
        outcome=str(value["outcome"]),
        applies=tuple(str(item) for item in value["applies"]),
        replaces=tuple(str(item) for item in value["replaces"]),
        terminates=tuple(str(item) for item in value["terminates"]),
        refreshes=tuple(str(item) for item in value["refreshes"]),
        next_gate_ids=tuple(str(item) for item in value["next_gate_ids"]),
    )


def _compile_gate(namespace: str, value: Mapping[str, Any]) -> CompiledGate:
    gate_id = str(value["gate_id"])
    resolution = value["resolution"]
    branches = tuple(
        sorted(
            (_compile_branch(namespace, branch) for branch in resolution["branches"]),
            key=lambda branch: branch.branch_id,
        )
    )
    return CompiledGate(
        gate_id=gate_id,
        qualified_id=QualifiedId(namespace, gate_id),
        selector_ids=tuple(str(item) for item in value["selector_ids"]),
        requires_active_component_ids=tuple(str(item) for item in value.get("requires_active_component_ids", [])),
        trigger=CompiledEvent.compile(value["trigger"]),
        gate_scope=str(value["gate_scope"]),
        resolution_kind=str(resolution["kind"]),
        ability=str(resolution["ability"]) if "ability" in resolution else None,
        role=str(resolution["role"]) if "role" in resolution else None,
        mode=str(resolution["mode"]) if "mode" in resolution else None,
        branches=branches,
        _branch_by_outcome=MappingProxyType({branch.outcome: branch for branch in branches}),
    )


def _compile_relationships(value: Mapping[str, Any]) -> CompiledRelationships:
    return CompiledRelationships(
        replacement_groups=tuple(
            (str(group["group_id"]), tuple(str(item) for item in group["component_ids"]))
            for group in value["replacement_groups"]
        ),
        dominance=tuple(
            (str(row["dominant_component_id"]), tuple(str(item) for item in row["suppressed_component_ids"]))
            for row in value["dominance"]
        ),
    )


def _compile_effect(
    entity_id: str,
    tier: int,
    value: Mapping[str, Any],
    canonical_input: Mapping[str, Any],
    authority_sha256: str,
) -> CompiledEffect:
    namespace = str(value["effect_id"])
    choices = tuple(_compile_choice(namespace, item) for item in value["choices"])
    selectors = tuple(_compile_selector(namespace, item) for item in value["target_selectors"])
    components = tuple(_compile_component(namespace, item) for item in value["components"])
    # Gate array position has no execution meaning.  Canonicalizing by stable ID makes
    # the compiled graph and equality independent of projection array order.
    gates = tuple(sorted((_compile_gate(namespace, item) for item in value["resolutions"]), key=lambda gate: gate.gate_id))
    gate_by_id = {gate.gate_id: gate for gate in gates}
    by_event: dict[str, list[CompiledGate]] = defaultdict(list)
    outgoing: dict[str, set[str]] = {gate.gate_id: set() for gate in gates}
    for gate in gates:
        by_event[gate.trigger.key].append(gate)
        for branch in gate.branches:
            outgoing[gate.gate_id].update(branch.next_gate_ids)
    return CompiledEffect(
        entity_id=entity_id,
        tier=tier,
        effect_id=namespace,
        authority_sha256=authority_sha256,
        inheritance=_frozen_map(value["inheritance"]),
        policy=_frozen_map(value["policy"]),
        choices=choices,
        selectors=selectors,
        components=components,
        root_gate_ids=tuple(str(item) for item in value["root_gate_ids"]),
        gates=gates,
        concentration=_frozen_map(value["concentration"]),
        relationships=_compile_relationships(value["relationships"]),
        canonical_input=_frozen_map(canonical_input),
        _choice_by_id=MappingProxyType({item.choice_id: item for item in choices}),
        _selector_by_id=MappingProxyType({item.selector_id: item for item in selectors}),
        _component_by_id=MappingProxyType({item.component_id: item for item in components}),
        _gate_by_id=MappingProxyType(gate_by_id),
        _gates_by_event=MappingProxyType(
            {key: tuple(sorted(items, key=lambda gate: gate.gate_id)) for key, items in by_event.items()}
        ),
        _outgoing=MappingProxyType({key: tuple(sorted(items)) for key, items in outgoing.items()}),
    )


def compile_control_authority(authority: ControlAuthorityV2Model) -> CompiledAuthority:
    """Compile one recursively validated Control Authority v2 model."""

    if not isinstance(authority, ControlAuthorityV2Model):
        raise TypeError("compile_control_authority requires ControlAuthorityV2Model")
    authority.require_benchmark_ready()
    projection = authority.projection  # one defensive snapshot; properties otherwise deepcopy on every access
    contract = projection["control_authority"]
    canonical_by_id = {
        row["entity_id"]: row for row in projection["canonical_inputs"]["entities"]
    }
    programs = tuple(
        _compile_effect(
            row["entity_id"],
            row["tier"],
            row["model"],
            canonical_by_id[row["entity_id"]],
            projection["authority_sha256"],
        )
        for row in contract["ledger"]
        if row["disposition"] == "modeled"
    )
    exclusions = tuple(
        CompiledExclusion(row["entity_id"], row["tier"], row["profile_id"], row["reason"])
        for row in contract["ledger"]
        if row["disposition"] == "excluded_by_profile"
    )
    masteries = tuple(
        CompiledMastery(
            mastery_id=row["mastery_id"],
            minimum_level=row["minimum_level"],
            triggers=tuple(CompiledEvent.compile(item) for item in row["trigger"]),
            component=_compile_component(row["mastery_id"], row["component"]),
        )
        for row in contract["masteries"]
    )
    program_by_id = {program.effect_id: program for program in programs}
    program_by_key = {(program.entity_id, program.tier): program for program in programs}
    minimum = int(projection["supported_level_range"]["minimum"])
    maximum = int(projection["supported_level_range"]["maximum"])
    return CompiledAuthority(
        projection_version=projection["projection_version"],
        contract_version=contract["contract_version"],
        authority_path=projection["authority_path"],
        authority_sha256=projection["authority_sha256"],
        rules_version=projection["rules_version"],
        schema_version=projection["schema_version"],
        supported_level_range=(minimum, maximum),
        active_profile=_frozen_map(contract["active_profile"]),
        target_data_requirements=tuple(contract["target_data_requirements"]),
        policy_inputs=_frozen_map(contract["policy_inputs"]),
        programs=programs,
        masteries=masteries,
        tactical_master=_frozen_map(contract["tactical_master"]),
        exclusions=exclusions,
        _program_by_id=MappingProxyType(program_by_id),
        _program_by_key=MappingProxyType(program_by_key),
        _mastery_by_id=MappingProxyType({mastery.mastery_id: mastery for mastery in masteries}),
    )


def load_compiled_control_authority(
    authority_path: str | Path = DEFAULT_AUTHORITY,
) -> CompiledAuthority:
    """Load the canonical v2 projection, require readiness, and compile it."""

    return compile_control_authority(
        ControlAuthorityV2Model.load(authority_path, require_benchmark_ready=True)
    )


# ---- Exact probability boundary -------------------------------------------------


ROLL_MODES = frozenset({"normal", "advantage", "disadvantage"})


def resolve_roll_mode(advantage_sources: int = 0, disadvantage_sources: int = 0) -> str:
    if isinstance(advantage_sources, bool) or not isinstance(advantage_sources, int) or advantage_sources < 0:
        raise ControlGraphError("advantage_sources must be a nonnegative integer")
    if isinstance(disadvantage_sources, bool) or not isinstance(disadvantage_sources, int) or disadvantage_sources < 0:
        raise ControlGraphError("disadvantage_sources must be a nonnegative integer")
    if advantage_sources and disadvantage_sources:
        return "normal"
    if advantage_sources:
        return "advantage"
    if disadvantage_sources:
        return "disadvantage"
    return "normal"


def _d20_probability(predicate: Any, mode: str) -> Fraction:
    if mode not in ROLL_MODES:
        raise ControlGraphError(f"Unsupported d20 roll mode: {mode!r}")
    successes = 0
    if mode == "normal":
        for roll in range(1, 21):
            successes += bool(predicate(roll))
        return Fraction(successes, 20)
    for first in range(1, 21):
        for second in range(1, 21):
            roll = max(first, second) if mode == "advantage" else min(first, second)
            successes += bool(predicate(roll))
    return Fraction(successes, 400)


def d20_attack_hit_probability(attack_bonus: int, armor_class: int, mode: str = "normal") -> Fraction:
    if isinstance(attack_bonus, bool) or not isinstance(attack_bonus, int):
        raise ControlGraphError("attack_bonus must be an integer")
    if isinstance(armor_class, bool) or not isinstance(armor_class, int):
        raise ControlGraphError("armor_class must be an integer")
    return _d20_probability(
        lambda roll: roll == 20 or (roll != 1 and roll + attack_bonus >= armor_class),
        mode,
    )


def d20_save_success_probability(save_bonus: int, dc: int, mode: str = "normal") -> Fraction:
    if isinstance(save_bonus, bool) or not isinstance(save_bonus, int):
        raise ControlGraphError("save_bonus must be an integer")
    if isinstance(dc, bool) or not isinstance(dc, int):
        raise ControlGraphError("dc must be an integer")
    return _d20_probability(lambda roll: roll + save_bonus >= dc, mode)


@dataclass(frozen=True, init=False)
class ReliabilityTarget:
    target_id: str
    armor_class: int
    saves: tuple[tuple[str, int], ...]
    condition_immunities: frozenset[str]
    magic_resistance: bool
    legendary_resistance: int

    def __init__(
        self,
        target_id: str,
        armor_class: int,
        saves: Mapping[str, int],
        *,
        condition_immunities: Iterable[str] = (),
        magic_resistance: bool = False,
        legendary_resistance: int = 0,
    ) -> None:
        if (
            not isinstance(target_id, str)
            or not target_id
            or target_id.strip() != target_id
        ):
            raise ControlGraphError("target_id must be a nonempty trimmed string")
        if isinstance(armor_class, bool) or not isinstance(armor_class, int):
            raise ControlGraphError("armor_class must be an integer")
        if not isinstance(saves, Mapping):
            raise ControlGraphError("saves must be a mapping of ability names to integer bonuses")
        invalid_abilities = [
            ability
            for ability in saves
            if (
                not isinstance(ability, str)
                or not ability
                or ability.strip() != ability
            )
        ]
        if invalid_abilities:
            raise ControlGraphError(
                "Save ability names must be nonempty trimmed strings"
            )
        normalized_saves: list[tuple[str, int]] = []
        for ability, bonus in sorted(saves.items()):
            if isinstance(bonus, bool) or not isinstance(bonus, int):
                raise ControlGraphError(f"Save bonus for {ability!r} must be an integer")
            normalized_saves.append((ability.lower(), bonus))
        normalized_abilities = [ability for ability, _bonus in normalized_saves]
        if len(normalized_abilities) != len(set(normalized_abilities)):
            raise ControlGraphError("saves contains duplicate normalized ability names")
        if isinstance(condition_immunities, (str, bytes)):
            raise ControlGraphError(
                "condition_immunities must be an iterable of condition names"
            )
        try:
            supplied_immunities = tuple(condition_immunities)
        except TypeError as error:
            raise ControlGraphError(
                "condition_immunities must be an iterable of condition names"
            ) from error
        if any(
            not isinstance(condition, str)
            or not condition
            or condition.strip() != condition
            for condition in supplied_immunities
        ):
            raise ControlGraphError(
                "Condition immunity names must be nonempty trimmed strings"
            )
        normalized_immunities = tuple(
            condition.lower() for condition in supplied_immunities
        )
        if len(normalized_immunities) != len(set(normalized_immunities)):
            raise ControlGraphError(
                "condition_immunities contains duplicate normalized condition names"
            )
        if isinstance(legendary_resistance, bool) or not isinstance(legendary_resistance, int) or legendary_resistance < 0:
            raise ControlGraphError("legendary_resistance must be a nonnegative integer")
        if not isinstance(magic_resistance, bool):
            raise ControlGraphError("magic_resistance must be boolean")
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "armor_class", armor_class)
        object.__setattr__(self, "saves", tuple(normalized_saves))
        object.__setattr__(self, "condition_immunities", frozenset(normalized_immunities))
        object.__setattr__(self, "magic_resistance", magic_resistance)
        object.__setattr__(self, "legendary_resistance", legendary_resistance)

    @classmethod
    def from_target(cls, target_id: str, target: Any) -> "ReliabilityTarget":
        return cls(
            target_id,
            target.ac,
            target.saves,
            condition_immunities=target.condition_immunities,
            magic_resistance=target.magic_resistance,
            legendary_resistance=target.legendary_resistance,
        )

    def save_bonus(self, ability: str) -> int:
        for candidate, bonus in self.saves:
            if candidate == ability:
                return bonus
        raise ControlGraphError(f"Target {self.target_id!r} has no {ability!r} save bonus")

    def canonical_record(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "armor_class": self.armor_class,
            "saves": {ability: bonus for ability, bonus in self.saves},
            "condition_immunities": sorted(self.condition_immunities),
            "magic_resistance": self.magic_resistance,
            "legendary_resistance": self.legendary_resistance,
        }


_SELECTOR_SIZE_ORDER = (
    "tiny",
    "small",
    "medium",
    "large",
    "huge",
    "gargantuan",
)


@dataclass(frozen=True, init=False)
class SelectorContext:
    """Explicit scenario facts needed to validate selector membership."""

    controller_can_see_by_target: FrozenMap
    target_size_by_id: FrozenMap
    controller_proficiency_bonus: int | None

    def __init__(
        self,
        *,
        controller_can_see_by_target: Mapping[str, bool] | None = None,
        target_size_by_id: Mapping[str, str] | None = None,
        controller_proficiency_bonus: int | None = None,
    ) -> None:
        visibility: dict[str, bool] = {}
        for target_id, visible in (
            controller_can_see_by_target or {}
        ).items():
            if not isinstance(target_id, str) or not target_id:
                raise ControlGraphError(
                    "SelectorContext visibility target IDs must be nonempty strings"
                )
            if not isinstance(visible, bool):
                raise ControlGraphError(
                    f"SelectorContext visibility for {target_id!r} "
                    "must be boolean"
                )
            visibility[target_id] = visible

        sizes: dict[str, str] = {}
        for target_id, size in (target_size_by_id or {}).items():
            if not isinstance(target_id, str) or not target_id:
                raise ControlGraphError(
                    "SelectorContext size target IDs must be nonempty strings"
                )
            if not isinstance(size, str) or not size or size.strip() != size:
                raise ControlGraphError(
                    f"SelectorContext size for {target_id!r} "
                    "must be a nonempty trimmed string"
                )
            normalized_size = size.lower()
            if normalized_size not in _SELECTOR_SIZE_ORDER:
                raise ControlGraphError(
                    f"SelectorContext size for {target_id!r} is unsupported: "
                    f"{size!r}"
                )
            sizes[target_id] = normalized_size

        if (
            controller_proficiency_bonus is not None
            and (
                isinstance(controller_proficiency_bonus, bool)
                or not isinstance(controller_proficiency_bonus, int)
                or controller_proficiency_bonus <= 0
            )
        ):
            raise ControlGraphError(
                "controller_proficiency_bonus must be a positive integer"
            )
        object.__setattr__(
            self,
            "controller_can_see_by_target",
            _frozen_map(visibility),
        )
        object.__setattr__(
            self,
            "target_size_by_id",
            _frozen_map(sizes),
        )
        object.__setattr__(
            self,
            "controller_proficiency_bonus",
            controller_proficiency_bonus,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "controller_can_see_by_target": (
                self.controller_can_see_by_target.to_dict()
            ),
            "target_size_by_id": self.target_size_by_id.to_dict(),
            "controller_proficiency_bonus": self.controller_proficiency_bonus,
        }


def validate_selector_membership(
    effect: CompiledEffect,
    *,
    target_ids: Iterable[str],
    selector_membership: Mapping[str, Sequence[str]],
    selector_context: SelectorContext = SelectorContext(),
) -> Mapping[str, tuple[str, ...]]:
    """Validate explicit membership without inferring target eligibility."""

    if not isinstance(effect, CompiledEffect):
        raise TypeError("effect must be CompiledEffect")
    if not isinstance(selector_context, SelectorContext):
        raise TypeError("selector_context must be SelectorContext")
    if isinstance(target_ids, (str, bytes)):
        raise ControlGraphError("target_ids must be an iterable of target IDs")
    known_targets = tuple(target_ids)
    if (
        any(not isinstance(target_id, str) or not target_id for target_id in known_targets)
        or len(known_targets) != len(set(known_targets))
    ):
        raise ControlGraphError(
            "target_ids must contain unique nonempty strings"
        )
    known_target_set = set(known_targets)

    expected_selectors = {
        selector.selector_id for selector in effect.selectors
    }
    unknown_selectors = sorted(
        set(selector_membership) - expected_selectors
    )
    missing_selectors = sorted(
        expected_selectors - set(selector_membership)
    )
    if unknown_selectors or missing_selectors:
        raise ControlGraphError(
            "Selector membership is incomplete; "
            f"missing={missing_selectors}, unknown={unknown_selectors}"
        )

    for fact_name, facts in (
        (
            "controller_can_see_by_target",
            selector_context.controller_can_see_by_target,
        ),
        ("target_size_by_id", selector_context.target_size_by_id),
    ):
        unknown_facts = sorted(set(facts) - known_target_set)
        if unknown_facts:
            raise ControlGraphError(
                f"SelectorContext.{fact_name} references unknown targets: "
                f"{unknown_facts}"
            )

    normalized_by_id: dict[str, tuple[str, ...]] = {}
    for selector in effect.selectors:
        values = selector_membership[selector.selector_id]
        if isinstance(values, (str, bytes)):
            raise ControlGraphError(
                f"Selector {selector.selector_id!r} membership must be an array"
            )
        normalized = tuple(values)
        if any(
            not isinstance(target_id, str) or not target_id
            for target_id in normalized
        ):
            raise ControlGraphError(
                f"Selector {selector.selector_id!r} target IDs "
                "must be nonempty strings"
            )
        if len(normalized) != len(set(normalized)):
            raise ControlGraphError(
                f"Selector {selector.selector_id!r} contains duplicate target IDs"
            )
        unknown_targets = sorted(set(normalized) - known_target_set)
        if unknown_targets:
            raise ControlGraphError(
                f"Selector {selector.selector_id!r} references unknown "
                f"targets: {unknown_targets}"
            )
        count_kind = str(selector.count["kind"])
        if count_kind == "fixed":
            required = int(selector.count["value"])
            if len(normalized) != required:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} requires exactly "
                    f"{required} target IDs"
                )
        elif count_kind == "up_to":
            maximum = int(selector.count["value"])
            if len(normalized) > maximum:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} allows at most "
                    f"{maximum} target IDs"
                )
        elif count_kind not in {
            "all_eligible",
            "up_to_proficiency_bonus",
            "weighted_slots",
        }:
            raise ControlGraphError(
                f"Selector {selector.selector_id!r} has unsupported "
                f"count semantics {count_kind!r}"
            )
        normalized_by_id[selector.selector_id] = normalized

    primary_targets = {
        target_id
        for selector in effect.selectors
        if selector.role == "primary"
        for target_id in normalized_by_id[selector.selector_id]
    }
    visibility = selector_context.controller_can_see_by_target
    sizes = selector_context.target_size_by_id
    size_rank = {
        size: index for index, size in enumerate(_SELECTOR_SIZE_ORDER)
    }
    for selector in effect.selectors:
        members = normalized_by_id[selector.selector_id]
        for restriction in selector.restrictions:
            restriction_kind = restriction.get("kind")
            if restriction_kind == "unique_targets":
                continue
            if restriction_kind == "excludes_primary_target":
                overlap = sorted(set(members) & primary_targets)
                if overlap:
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} excludes primary "
                        f"target IDs: {overlap}"
                    )
                continue
            if restriction_kind == "visibility":
                if restriction.get("requirement") != "controller_can_see":
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} has unsupported "
                        "visibility semantics"
                    )
                missing = sorted(
                    target_id
                    for target_id in members
                    if target_id not in visibility
                )
                if missing:
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} requires explicit "
                        f"controller visibility facts for: {missing}"
                    )
                hidden = sorted(
                    target_id
                    for target_id in members
                    if not visibility[target_id]
                )
                if hidden:
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} requires the "
                        f"controller to see targets: {hidden}"
                    )
                continue
            if restriction_kind == "maximum_size":
                value = restriction.get("size")
                if (
                    not isinstance(value, str)
                    or not value.endswith("_or_smaller")
                    or value.removesuffix("_or_smaller") not in size_rank
                ):
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} has unsupported "
                        "maximum-size semantics"
                    )
                maximum_size = value.removesuffix("_or_smaller")
                missing = sorted(
                    target_id for target_id in members
                    if target_id not in sizes
                )
                if missing:
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} requires explicit "
                        f"target-size facts for: {missing}"
                    )
                too_large = sorted(
                    target_id
                    for target_id in members
                    if size_rank[str(sizes[target_id])]
                    > size_rank[maximum_size]
                )
                if too_large:
                    raise ControlGraphError(
                        f"Selector {selector.selector_id!r} exceeds maximum "
                        f"size {maximum_size!r}: {too_large}"
                    )
                continue
            raise ControlGraphError(
                f"Selector {selector.selector_id!r} has unsupported "
                f"restriction semantics {restriction_kind!r}"
            )

    for selector in effect.selectors:
        members = normalized_by_id[selector.selector_id]
        count_kind = str(selector.count["kind"])
        if count_kind == "weighted_slots":
            missing = sorted(
                target_id for target_id in members
                if target_id not in sizes
            )
            if missing:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} requires explicit "
                    f"target-size facts for: {missing}"
                )
            size_costs = selector.count["size_costs"]
            unsupported_sizes = sorted(
                {
                    str(sizes[target_id])
                    for target_id in members
                    if str(sizes[target_id]) not in size_costs
                }
            )
            if unsupported_sizes:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} has no slot cost for "
                    f"target sizes: {unsupported_sizes}"
                )
            slot_cost = sum(
                int(size_costs[str(sizes[target_id])])
                for target_id in members
            )
            slots = int(selector.count["slots"])
            if slot_cost > slots:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} uses {slot_cost} "
                    f"weighted slots but allows {slots}"
                )
        elif count_kind == "up_to_proficiency_bonus" and members:
            proficiency_bonus = (
                selector_context.controller_proficiency_bonus
            )
            if proficiency_bonus is None:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} requires explicit "
                    "controller_proficiency_bonus"
                )
            if len(members) > proficiency_bonus:
                raise ControlGraphError(
                    f"Selector {selector.selector_id!r} allows at most "
                    f"{proficiency_bonus} target IDs from proficiency bonus"
                )

    return MappingProxyType(normalized_by_id)


@dataclass(frozen=True)
class ProbabilityContext:
    attack_bonus: int | None = None
    save_dc: int | None = None
    discipline_signature: str | None = None
    magical: bool = False
    attack_advantage_sources: int = 0
    attack_disadvantage_sources: int = 0
    save_advantage_sources: int = 0
    save_disadvantage_sources: int = 0

    def __post_init__(self) -> None:
        for field_name in ("attack_bonus", "save_dc"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ControlGraphError(f"{field_name} must be an integer or null")
        if self.discipline_signature is not None and (
            not isinstance(self.discipline_signature, str)
            or not self.discipline_signature
            or self.discipline_signature.strip() != self.discipline_signature
        ):
            raise ControlGraphError(
                "discipline_signature must be a nonempty trimmed string or null"
            )
        if not isinstance(self.magical, bool):
            raise ControlGraphError("magical must be boolean")
        for field_name in (
            "attack_advantage_sources",
            "attack_disadvantage_sources",
            "save_advantage_sources",
            "save_disadvantage_sources",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ControlGraphError(
                    f"{field_name} must be a nonnegative integer"
                )

    def canonical_record(self) -> dict[str, Any]:
        return {
            "attack_bonus": self.attack_bonus,
            "save_dc": self.save_dc,
            "discipline_signature": self.discipline_signature,
            "magical": self.magical,
            "attack_advantage_sources": self.attack_advantage_sources,
            "attack_disadvantage_sources": self.attack_disadvantage_sources,
            "save_advantage_sources": self.save_advantage_sources,
            "save_disadvantage_sources": self.save_disadvantage_sources,
        }


@dataclass(frozen=True, init=False)
class ProbabilityKernelIdentity:
    """Stable, immutable provenance for one exact probability kernel."""

    kernel_id: str
    version: str
    provenance: FrozenMap
    test_only: bool

    def __init__(
        self,
        kernel_id: str,
        version: str,
        provenance: Mapping[str, Any],
        *,
        test_only: bool = False,
    ) -> None:
        if (
            not isinstance(kernel_id, str)
            or not kernel_id
            or kernel_id.strip() != kernel_id
        ):
            raise ControlGraphError("kernel_id must be a nonempty trimmed string")
        if (
            not isinstance(version, str)
            or not version
            or version.strip() != version
        ):
            raise ControlGraphError("kernel version must be a nonempty trimmed string")
        if not isinstance(test_only, bool):
            raise ControlGraphError("kernel test_only marker must be boolean")
        if not isinstance(provenance, Mapping) or not provenance:
            raise ControlGraphError("kernel provenance must be a nonempty JSON object")
        frozen = _frozen_json_map(provenance, path="kernel provenance")
        if not test_only:
            algorithm = frozen.get("algorithm")
            if (
                not isinstance(algorithm, str)
                or not algorithm
                or algorithm.strip() != algorithm
            ):
                raise ControlGraphError(
                    "non-test kernel provenance algorithm must be a nonempty "
                    "trimmed string"
                )
            parameters = frozen.get("parameters")
            if not isinstance(parameters, FrozenMap) or not parameters:
                raise ControlGraphError(
                    "non-test kernel provenance parameters must be a nonempty "
                    "deterministic JSON object"
                )
        object.__setattr__(self, "kernel_id", kernel_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "provenance", frozen)
        object.__setattr__(self, "test_only", test_only)

    @classmethod
    def create(
        cls,
        kernel_id: str,
        version: str,
        provenance: Mapping[str, Any],
        *,
        test_only: bool = False,
    ) -> "ProbabilityKernelIdentity":
        return cls(
            kernel_id,
            version,
            provenance,
            test_only=test_only,
        )

    def canonical_record(self) -> dict[str, Any]:
        return {
            "kernel_id": self.kernel_id,
            "version": self.version,
            "test_only": self.test_only,
            "provenance": self.provenance.to_dict(),
        }


@runtime_checkable
class ProbabilityKernel(Protocol):
    """Caller boundary for exact gate-outcome probabilities."""

    identity: ProbabilityKernelIdentity

    def outcome_probabilities(
        self,
        gate: CompiledGate,
        target: ReliabilityTarget | None,
        context: ProbabilityContext,
    ) -> Mapping[str, Fraction]: ...


@dataclass(frozen=True)
class D20ProbabilityKernel:
    """Exact ordinary d20 kernel; it never spends Legendary Resistance."""

    identity: ProbabilityKernelIdentity = field(
        default=ProbabilityKernelIdentity.create(
            "openai.kinetic_vanguard.d20",
            "1.0.0",
            {
                "algorithm": "exact_uniform_d20_enumeration",
                "parameters": {
                    "die_faces": 20,
                    "attack_natural_1": "automatic_miss",
                    "attack_natural_20": "automatic_hit",
                    "attack_comparison": "roll_plus_bonus_greater_than_or_equal_to_ac",
                    "save_comparison": "roll_plus_bonus_greater_than_or_equal_to_dc",
                    "advantage": "maximum_of_two_independent_d20",
                    "disadvantage": "minimum_of_two_independent_d20",
                    "opposed_sources": "all_advantage_and_disadvantage_cancel_to_normal",
                    "magic_resistance": "save_advantage_only_when_context_is_magical",
                    "legendary_resistance": "metadata_only_never_spent",
                },
            },
        ),
        init=False,
    )

    def outcome_probabilities(
        self,
        gate: CompiledGate,
        target: ReliabilityTarget | None,
        context: ProbabilityContext,
    ) -> Mapping[str, Fraction]:
        if gate.resolution_kind == "no_save":
            return {"no_save": Fraction(1)}
        if gate.resolution_kind == "damage_context":
            return {"damage_context": Fraction(1)}
        if gate.resolution_kind == "other":
            return {"other": Fraction(1)}
        if target is None:
            raise ControlGraphError(f"Gate {gate.gate_id!r} requires a target")
        if gate.resolution_kind == "attack_roll":
            if context.attack_bonus is None:
                raise ControlGraphError("attack_bonus is required for attack-roll gates")
            mode = resolve_roll_mode(
                context.attack_advantage_sources,
                context.attack_disadvantage_sources,
            )
            hit = d20_attack_hit_probability(context.attack_bonus, target.armor_class, mode)
            return {"attack_hit": hit, "attack_miss": 1 - hit}
        if gate.resolution_kind != "saving_throw":  # pragma: no cover - compiled contract closes this
            raise ControlGraphError(f"Unsupported resolution kind {gate.resolution_kind!r}")
        if context.save_dc is None:
            raise ControlGraphError("save_dc is required for saving-throw gates")
        ability = gate.ability
        if ability == "discipline_signature":
            ability = context.discipline_signature
            if ability is None:
                raise ControlGraphError(
                    f"Gate {gate.gate_id!r} requires an explicit discipline_signature ability"
                )
        if ability is None:  # pragma: no cover - compiled contract closes this
            raise ControlGraphError(f"Gate {gate.gate_id!r} has no saving-throw ability")
        base_advantage = int(gate.mode == "advantage")
        base_disadvantage = int(gate.mode == "disadvantage")
        # Magic Resistance is conditional on caller-supplied magical identity.  LR is
        # metadata only and deliberately does not enter this probability.
        magic_advantage = int(context.magical and target.magic_resistance)
        mode = resolve_roll_mode(
            base_advantage + context.save_advantage_sources + magic_advantage,
            base_disadvantage + context.save_disadvantage_sources,
        )
        success = d20_save_success_probability(target.save_bonus(ability), context.save_dc, mode)
        return {"save_success": success, "save_failure": 1 - success}


# ---- Correlated joint-world reliability ----------------------------------------


@dataclass(frozen=True)
class ReliabilityEvent:
    event_id: str
    trigger: CompiledEvent
    target_ids: tuple[str, ...] = ()
    gate_ids: tuple[str, ...] = ()
    window_id: str | None = None
    expire_component_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.event_id, str)
            or not self.event_id
            or self.event_id.strip() != self.event_id
        ):
            raise ControlGraphError("ReliabilityEvent event_id must be a nonempty trimmed string")
        if not isinstance(self.trigger, CompiledEvent):
            raise ControlGraphError("ReliabilityEvent trigger must be CompiledEvent")
        if self.window_id is not None and (
            not isinstance(self.window_id, str)
            or not self.window_id
            or self.window_id.strip() != self.window_id
        ):
            raise ControlGraphError(
                "ReliabilityEvent window_id must be a nonempty trimmed string or null"
            )
        for field_name, values in (
            ("target_ids", self.target_ids),
            ("gate_ids", self.gate_ids),
            ("expire_component_ids", self.expire_component_ids),
        ):
            if len(values) != len(set(values)):
                raise ControlGraphError(
                    f"ReliabilityEvent {self.event_id!r} contains duplicate "
                    f"{field_name}"
                )
            if any(
                not isinstance(value, str)
                or not value
                or value.strip() != value
                for value in values
            ):
                raise ControlGraphError(
                    f"ReliabilityEvent {self.event_id!r} {field_name} must "
                    "contain nonempty trimmed strings"
                )

    @classmethod
    def create(
        cls,
        event_id: str,
        trigger: Mapping[str, Any] | CompiledEvent,
        *,
        target_ids: Iterable[str] = (),
        gate_ids: Iterable[str] = (),
        window_id: str | None = None,
        expire_component_ids: Iterable[str] = (),
    ) -> "ReliabilityEvent":
        return cls(
            event_id=event_id,
            trigger=trigger if isinstance(trigger, CompiledEvent) else CompiledEvent.compile(trigger),
            target_ids=tuple(target_ids),
            gate_ids=tuple(gate_ids),
            window_id=window_id,
            expire_component_ids=tuple(expire_component_ids),
        )

    def canonical_record(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger": self.trigger.data.to_dict(),
            "target_ids": list(self.target_ids),
            "gate_ids": list(self.gate_ids),
            "window_id": self.window_id,
            "expire_component_ids": list(self.expire_component_ids),
        }


@dataclass(frozen=True, init=False)
class ReliabilityScenario:
    """Canonical immutable identity for one reliability evaluation."""

    effect_id: str
    entity_id: str
    tier: int
    authority_sha256: str
    targets: tuple[ReliabilityTarget, ...]
    selector_membership: tuple[tuple[str, tuple[str, ...]], ...]
    selector_context: SelectorContext
    choice_bindings: ChoiceBindings
    probability_context: ProbabilityContext
    kernel_identity: ProbabilityKernelIdentity
    candidate_component_ids: tuple[str, ...]
    event_script: tuple[ReliabilityEvent, ...]
    initial_event_count: int
    include_initial: bool
    scenario_digest: str

    def __init__(
        self,
        *,
        effect_id: str,
        entity_id: str,
        tier: int,
        authority_sha256: str,
        targets: tuple[ReliabilityTarget, ...],
        selector_membership: tuple[tuple[str, tuple[str, ...]], ...],
        selector_context: SelectorContext,
        choice_bindings: ChoiceBindings,
        probability_context: ProbabilityContext,
        kernel_identity: ProbabilityKernelIdentity,
        candidate_component_ids: tuple[str, ...],
        event_script: tuple[ReliabilityEvent, ...],
        initial_event_count: int,
        include_initial: bool,
    ) -> None:
        if not isinstance(include_initial, bool):
            raise ControlGraphError("include_initial must be boolean")
        if (
            not isinstance(initial_event_count, int)
            or isinstance(initial_event_count, bool)
            or initial_event_count < 0
            or initial_event_count > len(event_script)
        ):
            raise ControlGraphError("initial_event_count is invalid")
        if (
            not isinstance(authority_sha256, str)
            or len(authority_sha256) != 64
            or any(character not in "0123456789abcdef" for character in authority_sha256)
        ):
            raise ControlGraphError("authority_sha256 must be a lowercase SHA-256 digest")
        event_ids = [event.event_id for event in event_script]
        if len(event_ids) != len(set(event_ids)):
            raise ControlGraphError("Duplicate reliability event ID in scenario")
        window_ids = [event.window_id or event.event_id for event in event_script]
        if not initial_event_count:
            window_ids.insert(0, "initial")
        if len(window_ids) != len(set(window_ids)):
            raise ControlGraphError("Reliability scenario contains duplicate window IDs")

        values = {
            "effect_id": effect_id,
            "entity_id": entity_id,
            "tier": tier,
            "authority_sha256": authority_sha256,
            "targets": targets,
            "selector_membership": selector_membership,
            "selector_context": selector_context,
            "choice_bindings": choice_bindings,
            "probability_context": probability_context,
            "kernel_identity": kernel_identity,
            "candidate_component_ids": candidate_component_ids,
            "event_script": event_script,
            "initial_event_count": initial_event_count,
            "include_initial": include_initial,
        }
        for field_name, value in values.items():
            object.__setattr__(self, field_name, value)
        digest = sha256(
            _canonical(self.canonical_record()).encode("utf-8")
        ).hexdigest()
        object.__setattr__(self, "scenario_digest", digest)

    @classmethod
    def create(
        cls,
        effect: CompiledEffect,
        *,
        targets: Sequence[ReliabilityTarget],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        choices: Mapping[str, str] | None,
        probability_context: ProbabilityContext,
        kernel: ProbabilityKernel,
        events: Sequence[ReliabilityEvent],
        candidate_component_ids: Iterable[str],
        include_initial: bool,
    ) -> "ReliabilityScenario":
        if not isinstance(effect, CompiledEffect):
            raise TypeError("ReliabilityScenario.create requires CompiledEffect")
        if not isinstance(selector_context, SelectorContext):
            raise TypeError("selector_context must be SelectorContext")
        if not isinstance(probability_context, ProbabilityContext):
            raise TypeError("probability_context must be ProbabilityContext")
        if not isinstance(include_initial, bool):
            raise ControlGraphError("include_initial must be boolean")
        supplied_targets = tuple(targets)
        if any(not isinstance(target, ReliabilityTarget) for target in supplied_targets):
            raise TypeError("targets must contain ReliabilityTarget values")
        ordered_targets = tuple(
            sorted(supplied_targets, key=lambda target: target.target_id)
        )
        target_ids = tuple(target.target_id for target in ordered_targets)
        if len(target_ids) != len(set(target_ids)):
            raise ControlGraphError("Reliability targets contain duplicate target IDs")
        membership = validate_selector_membership(
            effect,
            target_ids=target_ids,
            selector_membership=selector_membership,
            selector_context=selector_context,
        )
        canonical_membership = tuple(
            (selector_id, tuple(sorted(membership[selector_id])))
            for selector_id in sorted(membership)
        )
        bindings = effect.bind_choices(choices)
        if not isinstance(kernel, ProbabilityKernel):
            raise ControlGraphError(
                "kernel must provide identity provenance and implement ProbabilityKernel"
            )
        if not isinstance(kernel.identity, ProbabilityKernelIdentity):
            raise ControlGraphError(
                "kernel identity must be ProbabilityKernelIdentity"
            )
        if isinstance(events, (str, bytes)):
            raise ControlGraphError("events must be an ordered sequence")
        ordered_events = tuple(events)
        if any(not isinstance(event, ReliabilityEvent) for event in ordered_events):
            raise ControlGraphError("events must contain ReliabilityEvent values")
        if isinstance(candidate_component_ids, (str, bytes)):
            raise ControlGraphError(
                "candidate_component_ids must be an iterable of component IDs"
            )
        supplied_candidates = tuple(candidate_component_ids)
        if any(
            not isinstance(component_id, str)
            or not component_id
            or component_id.strip() != component_id
            for component_id in supplied_candidates
        ):
            raise ControlGraphError(
                "candidate_component_ids must contain nonempty trimmed strings"
            )
        if len(supplied_candidates) != len(set(supplied_candidates)):
            raise ControlGraphError("candidate_component_ids contains duplicates")
        known_components = {
            component.component_id for component in effect.components
        }
        unknown_candidates = sorted(set(supplied_candidates) - known_components)
        if unknown_candidates:
            raise ControlGraphError(
                f"Unknown candidate component IDs: {unknown_candidates}"
            )
        initial_events = (
            _implicit_initial_reliability_events(effect)
            if include_initial
            else ()
        )
        return cls(
            effect_id=effect.effect_id,
            entity_id=effect.entity_id,
            tier=effect.tier,
            authority_sha256=effect.authority_sha256,
            targets=ordered_targets,
            selector_membership=canonical_membership,
            selector_context=selector_context,
            choice_bindings=bindings,
            probability_context=probability_context,
            kernel_identity=kernel.identity,
            candidate_component_ids=tuple(sorted(supplied_candidates)),
            event_script=(*initial_events, *ordered_events),
            initial_event_count=len(initial_events),
            include_initial=include_initial,
        )

    @property
    def target_ids(self) -> tuple[str, ...]:
        return tuple(target.target_id for target in self.targets)

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(event.event_id for event in self.event_script)

    @property
    def window_ids(self) -> tuple[str, ...]:
        values = tuple(event.window_id or event.event_id for event in self.event_script)
        return values if self.initial_event_count else ("initial", *values)

    def canonical_record(self) -> dict[str, Any]:
        return {
            "program": {
                "effect_id": self.effect_id,
                "entity_id": self.entity_id,
                "tier": self.tier,
                "authority_sha256": self.authority_sha256,
            },
            "targets": [target.canonical_record() for target in self.targets],
            "selector_membership": {
                selector_id: list(target_ids)
                for selector_id, target_ids in self.selector_membership
            },
            "selector_context": self.selector_context.to_dict(),
            "choice_bindings": dict(self.choice_bindings),
            "probability_context": self.probability_context.canonical_record(),
            "probability_kernel": self.kernel_identity.canonical_record(),
            "candidate_component_ids": list(self.candidate_component_ids),
            "ordered_event_script": [
                event.canonical_record() for event in self.event_script
            ],
            "initial_event_count": self.initial_event_count,
            "include_initial": self.include_initial,
        }


@dataclass(frozen=True, order=True)
class _GateActivation:
    gate_id: str
    target_ids: tuple[str, ...]


@dataclass(frozen=True)
class _World:
    active: frozenset[tuple[str, str]] = frozenset()
    ever: frozenset[tuple[str, str]] = frozenset()
    initial: frozenset[tuple[str, str]] = frozenset()
    enabled: tuple[_GateActivation, ...] = ()


@dataclass(frozen=True)
class GateProbability:
    event_id: str
    gate_id: str
    target_ids: tuple[str, ...]
    probability: Fraction


@dataclass(frozen=True)
class BranchProbability:
    event_id: str
    gate_id: str
    branch_id: str
    outcome: str
    target_ids: tuple[str, ...]
    probability: Fraction


@dataclass(frozen=True)
class ComponentReliability:
    component_id: str
    qualified_id: QualifiedId
    target_id: str
    initially_applied: Fraction
    ever_applied: Fraction
    active_by_window: tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True)
class RepeatSurvival:
    event_id: str
    gate_id: str
    target_id: str
    probability: Fraction


@dataclass(frozen=True)
class ImmunitySuppression:
    event_id: str
    gate_id: str
    branch_id: str
    target_id: str
    component_id: str
    condition: str
    probability: Fraction


_RELIABILITY_RESULT_ISSUER = object()


@dataclass(frozen=True)
class ReliabilityResult:
    effect_id: str
    target_ids: tuple[str, ...]
    component_reliability: tuple[ComponentReliability, ...]
    gate_probabilities: tuple[GateProbability, ...]
    branch_probabilities: tuple[BranchProbability, ...]
    repeat_survival: tuple[RepeatSurvival, ...]
    immunity_suppressions: tuple[ImmunitySuppression, ...]
    any_candidate_probability: Fraction
    any_component_probability: Fraction
    any_candidate_by_target: tuple[tuple[str, Fraction], ...]
    any_component_by_target: tuple[tuple[str, Fraction], ...]
    final_world_count: int
    scenario: ReliabilityScenario | None = None
    scenario_digest: str | None = None
    _issuer: object | None = field(
        default=None,
        init=False,
        compare=False,
        hash=False,
        repr=False,
    )
    _issuance_token: object | None = field(
        default=None,
        init=False,
        compare=False,
        hash=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.scenario is None:
            if self.scenario_digest is not None:
                raise ControlGraphError(
                    "ReliabilityResult scenario_digest requires a scenario"
                )
        elif self.scenario_digest != self.scenario.scenario_digest:
            raise ControlGraphError(
                "ReliabilityResult scenario digest does not match its canonical scenario"
            )

    def component(self, component_id: str, target_id: str) -> ComponentReliability:
        matches = [
            row for row in self.component_reliability
            if row.component_id == component_id and row.target_id == target_id
        ]
        if len(matches) != 1:
            raise ControlGraphError(
                f"Expected one reliability row for {component_id!r}/{target_id!r}, got {len(matches)}"
            )
        return matches[0]

_IMMEDIATE_CONTINUATION_KINDS = frozenset({"save", "damage_context", "instantaneous_resolution"})
_FUTURE_ROOT_KINDS = frozenset({"turn", "entry", "exit", "concentration_end"})


def _implicit_initial_reliability_events(
    effect: CompiledEffect,
) -> tuple[ReliabilityEvent, ...]:
    events: list[ReliabilityEvent] = []
    for gate_id in effect.root_gate_ids:
        gate = effect.gate(gate_id)
        if gate.role in {"repeat", "recurring"} or gate.trigger.kind in _FUTURE_ROOT_KINDS:
            continue
        events.append(
            ReliabilityEvent(
                event_id=f"initial:{gate_id}",
                trigger=gate.trigger,
                gate_ids=(gate_id,),
                window_id=f"initial:{gate_id}",
            )
        )
    return tuple(events)


def reliability_result_issuance_token(result: ReliabilityResult) -> object:
    """Return the opaque same-evaluation token for an engine-issued result."""

    if not isinstance(result, ReliabilityResult):
        raise TypeError("result must be ReliabilityResult")
    if (
        result._issuer is not _RELIABILITY_RESULT_ISSUER
        or result._issuance_token is None
    ):
        raise ControlGraphError("Reliability result is not engine-issued")
    return result._issuance_token


def _issue_reliability_result(result: ReliabilityResult) -> ReliabilityResult:
    """Module-private issuance boundary used only after closed-ledger validation."""

    object.__setattr__(result, "_issuer", _RELIABILITY_RESULT_ISSUER)
    object.__setattr__(result, "_issuance_token", object())
    return result


def _merge_worlds(rows: Iterable[tuple[_World, Fraction]]) -> dict[_World, Fraction]:
    merged: dict[_World, Fraction] = defaultdict(Fraction)
    for world, probability in rows:
        if probability:
            merged[world] += probability
    return dict(merged)


def _validate_distribution(gate: CompiledGate, value: Mapping[str, Fraction]) -> dict[str, Fraction]:
    expected = {branch.outcome for branch in gate.branches}
    if set(value) != expected:
        raise ControlGraphError(
            f"Kernel outcomes for {gate.gate_id!r} are incomplete; expected={sorted(expected)}, actual={sorted(value)}"
        )
    result: dict[str, Fraction] = {}
    for outcome, probability in value.items():
        if not isinstance(probability, Fraction):
            raise ControlGraphError("ProbabilityKernel must return fractions.Fraction values")
        if probability < 0 or probability > 1:
            raise ControlGraphError(f"Invalid probability for {gate.gate_id}/{outcome}: {probability}")
        result[outcome] = probability
    if sum(result.values(), Fraction()) != 1:
        raise ControlGraphError(f"Kernel probabilities for {gate.gate_id!r} must sum exactly to 1")
    return result


def _require_exact_probability(value: Any, *, label: str) -> Fraction:
    if not isinstance(value, Fraction):
        raise ControlGraphError(f"{label} must be an exact fractions.Fraction")
    if value < 0 or value > 1:
        raise ControlGraphError(f"{label} must be between zero and one")
    return value


def _require_result_targets(
    target_ids: Any,
    *,
    known_targets: frozenset[str],
    label: str,
) -> tuple[str, ...]:
    if not isinstance(target_ids, tuple):
        raise ControlGraphError(f"{label} target IDs must be an immutable tuple")
    if len(target_ids) != len(set(target_ids)):
        raise ControlGraphError(f"{label} contains duplicate target IDs")
    if target_ids != tuple(sorted(target_ids)):
        raise ControlGraphError(
            f"{label} target IDs must use canonical scenario ordering"
        )
    unknown = sorted(set(target_ids) - known_targets)
    if unknown:
        raise ControlGraphError(f"{label} references unknown target IDs: {unknown}")
    return target_ids


def _compatible_gate_ids_by_event(
    effect: CompiledEffect,
    scenario: ReliabilityScenario,
) -> Mapping[str, frozenset[str]]:
    """Return structurally compatible gate IDs for each scripted event."""

    result: dict[str, frozenset[str]] = {}
    for event in scenario.event_script:
        if event.gate_ids:
            seeds: set[str] = set()
            for gate_id in event.gate_ids:
                gate = effect.gate(gate_id)
                if gate.trigger.key != event.trigger.key:
                    raise ControlGraphError(
                        f"Reliability event {event.event_id!r} gate {gate_id!r} "
                        "has an incompatible trigger"
                    )
                seeds.add(gate_id)
        else:
            # Future branch subscriptions and exogenous roots can both resolve
            # at a matching trigger. Reachability mass is proven by the exact
            # gate/branch distribution, while trigger compatibility is closed
            # here.
            seeds = {
                gate.gate_id
                for gate in effect.gates
                if gate.trigger.key == event.trigger.key
            }
        compatible = set(seeds)
        pending = list(seeds)
        while pending:
            gate = effect.gate(pending.pop())
            for branch in gate.branches:
                for next_gate_id in branch.next_gate_ids:
                    next_gate = effect.gate(next_gate_id)
                    if (
                        next_gate.trigger.kind in _IMMEDIATE_CONTINUATION_KINDS
                        and next_gate_id not in compatible
                    ):
                        compatible.add(next_gate_id)
                        pending.append(next_gate_id)
        result[event.event_id] = frozenset(compatible)
    return MappingProxyType(result)


def _validate_reliability_result_structure(
    effect: CompiledEffect,
    result: ReliabilityResult,
    *,
    expected_scenario_digest: str | None = None,
) -> None:
    """Module-private structural validator used before evaluator issuance."""

    if not isinstance(effect, CompiledEffect):
        raise TypeError("effect must be CompiledEffect")
    if not isinstance(result, ReliabilityResult):
        raise TypeError("result must be ReliabilityResult")
    scenario = result.scenario
    if scenario is None or result.scenario_digest is None:
        raise ControlGraphError("Reliability result has no canonical scenario provenance")
    canonical_digest = sha256(
        _canonical(scenario.canonical_record()).encode("utf-8")
    ).hexdigest()
    if scenario.scenario_digest != canonical_digest:
        raise ControlGraphError("Reliability scenario digest is stale or malformed")
    if result.scenario_digest != scenario.scenario_digest:
        raise ControlGraphError("Reliability result scenario digest mismatch")
    if (
        expected_scenario_digest is not None
        and result.scenario_digest != expected_scenario_digest
    ):
        raise ControlGraphError(
            "Reliability result belongs to a different canonical scenario"
        )
    if (
        scenario.effect_id != effect.effect_id
        or scenario.entity_id != effect.entity_id
        or scenario.tier != effect.tier
        or scenario.authority_sha256 != effect.authority_sha256
        or result.effect_id != effect.effect_id
    ):
        raise ControlGraphError(
            "Reliability result does not belong to the compiled program and authority"
        )

    target_ids = scenario.target_ids
    if result.target_ids != target_ids:
        raise ControlGraphError(
            "Reliability result target IDs do not match its canonical scenario"
        )
    known_targets = frozenset(target_ids)
    known_components = {
        component.component_id: component for component in effect.components
    }
    known_events = frozenset(scenario.event_ids)
    known_windows = frozenset(scenario.window_ids)
    compatible_gates = _compatible_gate_ids_by_event(effect, scenario)

    gate_rows: dict[tuple[str, str, tuple[str, ...]], Fraction] = {}
    for row in result.gate_probabilities:
        if row.event_id not in known_events:
            raise ControlGraphError(
                f"Gate probability references unknown event ID: {row.event_id!r}"
            )
        try:
            effect.gate(row.gate_id)
        except ControlGraphError as error:
            raise ControlGraphError(
                f"Gate probability references unknown gate ID: {row.gate_id!r}"
            ) from error
        if row.gate_id not in compatible_gates[row.event_id]:
            raise ControlGraphError(
                f"Gate {row.gate_id!r} is incompatible with reliability event "
                f"{row.event_id!r}"
            )
        scope = _require_result_targets(
            row.target_ids,
            known_targets=known_targets,
            label="Gate probability",
        )
        key = (row.event_id, row.gate_id, scope)
        if key in gate_rows:
            raise ControlGraphError(
                f"Duplicate semantic gate probability row: {key!r}"
            )
        gate_rows[key] = _require_exact_probability(
            row.probability,
            label=f"Gate probability {row.event_id}/{row.gate_id}",
        )

    branch_groups: dict[
        tuple[str, str, tuple[str, ...]],
        Fraction,
    ] = defaultdict(Fraction)
    branch_keys: set[tuple[str, str, str, tuple[str, ...]]] = set()
    for row in result.branch_probabilities:
        if row.event_id not in known_events:
            raise ControlGraphError(
                f"Branch probability references unknown event ID: {row.event_id!r}"
            )
        try:
            gate = effect.gate(row.gate_id)
        except ControlGraphError as error:
            raise ControlGraphError(
                f"Branch probability references unknown gate ID: {row.gate_id!r}"
            ) from error
        if row.gate_id not in compatible_gates[row.event_id]:
            raise ControlGraphError(
                f"Gate {row.gate_id!r} is incompatible with reliability event "
                f"{row.event_id!r}"
            )
        matching_branches = [
            branch
            for branch in gate.branches
            if branch.branch_id == row.branch_id
        ]
        if len(matching_branches) != 1:
            raise ControlGraphError(
                f"Branch {row.branch_id!r} does not belong to gate {row.gate_id!r}"
            )
        if matching_branches[0].outcome != row.outcome:
            raise ControlGraphError(
                f"Branch {row.branch_id!r} outcome does not match its compiled gate"
            )
        scope = _require_result_targets(
            row.target_ids,
            known_targets=known_targets,
            label="Branch probability",
        )
        semantic_key = (row.event_id, row.gate_id, row.branch_id, scope)
        if semantic_key in branch_keys:
            raise ControlGraphError(
                f"Duplicate semantic branch probability row: {semantic_key!r}"
            )
        branch_keys.add(semantic_key)
        probability = _require_exact_probability(
            row.probability,
            label=(
                f"Branch probability {row.event_id}/{row.gate_id}/"
                f"{row.branch_id}"
            ),
        )
        branch_groups[(row.event_id, row.gate_id, scope)] += probability

    if set(branch_groups) != set(gate_rows):
        missing = sorted(set(gate_rows) - set(branch_groups))
        unknown = sorted(set(branch_groups) - set(gate_rows))
        raise ControlGraphError(
            "Gate/branch probability groups do not match exactly; "
            f"missing={missing}, unknown={unknown}"
        )
    for key, gate_probability in gate_rows.items():
        if branch_groups[key] != gate_probability:
            raise ControlGraphError(
                f"Branch probabilities for {key!r} do not sum exactly to gate mass"
            )

    component_keys: set[tuple[str, str]] = set()
    expected_component_keys = {
        (component_id, target_id)
        for component_id in known_components
        for target_id in target_ids
    }
    for row in result.component_reliability:
        component = known_components.get(row.component_id)
        if component is None:
            raise ControlGraphError(
                f"Component reliability references unknown component ID: {row.component_id!r}"
            )
        if row.qualified_id != component.qualified_id:
            raise ControlGraphError(
                f"Component reliability has a mismatched qualified ID for {row.component_id!r}"
            )
        if row.target_id not in known_targets:
            raise ControlGraphError(
                f"Component reliability references unknown target ID: {row.target_id!r}"
            )
        semantic_key = (row.component_id, row.target_id)
        if semantic_key in component_keys:
            raise ControlGraphError(
                f"Duplicate semantic component reliability row: {semantic_key!r}"
            )
        component_keys.add(semantic_key)
        initially = _require_exact_probability(
            row.initially_applied,
            label=f"Initial component probability {semantic_key!r}",
        )
        ever = _require_exact_probability(
            row.ever_applied,
            label=f"Ever component probability {semantic_key!r}",
        )
        if initially > ever:
            raise ControlGraphError(
                f"Initial component probability exceeds ever-applied mass for {semantic_key!r}"
            )
        row_windows = tuple(window_id for window_id, _probability in row.active_by_window)
        if len(row_windows) != len(set(row_windows)):
            raise ControlGraphError(
                f"Duplicate semantic component window row for {semantic_key!r}"
            )
        if row_windows != scenario.window_ids:
            raise ControlGraphError(
                f"Component reliability windows do not match the scenario for {semantic_key!r}"
            )
        for window_id, probability in row.active_by_window:
            if window_id not in known_windows:  # pragma: no cover - tuple equality covers this
                raise ControlGraphError(
                    f"Component reliability references unknown window ID: {window_id!r}"
                )
            active = _require_exact_probability(
                probability,
                label=f"Active component probability {semantic_key!r}/{window_id}",
            )
            if active > ever:
                raise ControlGraphError(
                    f"Active component probability exceeds ever-applied mass for {semantic_key!r}"
                )
    if component_keys != expected_component_keys:
        raise ControlGraphError(
            "Component reliability rows do not cover every program component and target"
        )

    repeat_keys: set[tuple[str, str, str]] = set()
    for row in result.repeat_survival:
        if row.event_id not in known_events:
            raise ControlGraphError(
                f"Repeat survival references unknown event ID: {row.event_id!r}"
            )
        gate = effect.gate(row.gate_id)
        if gate.role != "repeat":
            raise ControlGraphError(
                f"Repeat survival gate is not a repeat gate: {row.gate_id!r}"
            )
        if row.target_id not in known_targets:
            raise ControlGraphError(
                f"Repeat survival references unknown target ID: {row.target_id!r}"
            )
        key = (row.event_id, row.gate_id, row.target_id)
        if key in repeat_keys:
            raise ControlGraphError(f"Duplicate semantic repeat survival row: {key!r}")
        repeat_keys.add(key)
        _require_exact_probability(
            row.probability,
            label=f"Repeat survival probability {key!r}",
        )

    suppression_keys: set[tuple[str, str, str, str, str, str]] = set()
    for row in result.immunity_suppressions:
        if row.event_id not in known_events:
            raise ControlGraphError(
                f"Immunity suppression references unknown event ID: {row.event_id!r}"
            )
        gate = effect.gate(row.gate_id)
        matching_branches = [
            branch for branch in gate.branches if branch.branch_id == row.branch_id
        ]
        if len(matching_branches) != 1:
            raise ControlGraphError(
                f"Immunity suppression branch does not belong to gate {row.gate_id!r}"
            )
        if row.target_id not in known_targets:
            raise ControlGraphError(
                f"Immunity suppression references unknown target ID: {row.target_id!r}"
            )
        component = known_components.get(row.component_id)
        if component is None:
            raise ControlGraphError(
                f"Immunity suppression references unknown component ID: {row.component_id!r}"
            )
        expected_condition = (
            str(component.magnitude.data["condition"])
            if component.magnitude.kind == "condition"
            else None
        )
        if row.condition != expected_condition:
            raise ControlGraphError(
                f"Immunity suppression condition does not match component {row.component_id!r}"
            )
        key = (
            row.event_id,
            row.gate_id,
            row.branch_id,
            row.target_id,
            row.component_id,
            row.condition,
        )
        if key in suppression_keys:
            raise ControlGraphError(
                f"Duplicate semantic immunity suppression row: {key!r}"
            )
        suppression_keys.add(key)
        _require_exact_probability(
            row.probability,
            label=f"Immunity suppression probability {key!r}",
        )

    any_candidate = _require_exact_probability(
        result.any_candidate_probability,
        label="Any-candidate probability",
    )
    any_component = _require_exact_probability(
        result.any_component_probability,
        label="Any-component probability",
    )
    if any_candidate > any_component:
        raise ControlGraphError(
            "Any-candidate probability exceeds any-component probability"
        )
    for label, rows in (
        ("Any-candidate by-target", result.any_candidate_by_target),
        ("Any-component by-target", result.any_component_by_target),
    ):
        row_targets = tuple(target_id for target_id, _probability in rows)
        if row_targets != target_ids:
            raise ControlGraphError(f"{label} rows do not match scenario targets")
        for target_id, probability in rows:
            _require_exact_probability(
                probability,
                label=f"{label} probability for {target_id!r}",
            )
    candidate_by_target = dict(result.any_candidate_by_target)
    component_by_target = dict(result.any_component_by_target)
    if any(
        candidate_by_target[target_id] > component_by_target[target_id]
        for target_id in target_ids
    ):
        raise ControlGraphError(
            "A by-target candidate probability exceeds component probability"
        )
    if (
        isinstance(result.final_world_count, bool)
        or not isinstance(result.final_world_count, int)
        or result.final_world_count <= 0
    ):
        raise ControlGraphError("final_world_count must be a positive integer")

def validate_reliability_result(
    effect: CompiledEffect,
    result: ReliabilityResult,
    *,
    expected_scenario_digest: str | None = None,
    expected_issuance_token: object | None = None,
) -> None:
    """Validate a closed reliability ledger and require engine issuance."""

    _validate_reliability_result_structure(
        effect,
        result,
        expected_scenario_digest=expected_scenario_digest,
    )
    token = reliability_result_issuance_token(result)
    if (
        expected_issuance_token is not None
        and token is not expected_issuance_token
    ):
        raise ControlGraphError(
            "Reliability result was issued by a different evaluation execution"
        )


class _Evaluator:
    def __init__(
        self,
        effect: CompiledEffect,
        targets: Sequence[ReliabilityTarget],
        selector_membership: Mapping[str, Sequence[str]],
        selector_context: SelectorContext,
        kernel: ProbabilityKernel,
        context: ProbabilityContext,
        choices: ChoiceBindings,
        candidate_component_ids: frozenset[str],
    ) -> None:
        self.effect = effect
        self.targets = {target.target_id: target for target in targets}
        if len(self.targets) != len(targets):
            raise ControlGraphError("Reliability targets contain duplicate target IDs")
        self.membership = dict(
            validate_selector_membership(
                effect,
                target_ids=self.targets,
                selector_membership=selector_membership,
                selector_context=selector_context,
            )
        )
        if not isinstance(kernel, ProbabilityKernel):
            raise ControlGraphError("kernel must implement ProbabilityKernel")
        self.kernel = kernel
        self.context = context
        self.choices = choices
        self.candidates = candidate_component_ids
        self.gate_stats: dict[tuple[str, str, tuple[str, ...]], Fraction] = defaultdict(Fraction)
        self.branch_stats: dict[tuple[str, str, str, str, tuple[str, ...]], Fraction] = defaultdict(Fraction)
        self.repeat_stats: dict[tuple[str, str, str], Fraction] = defaultdict(Fraction)
        self.immunity_stats: dict[tuple[str, str, str, str, str, str], Fraction] = defaultdict(Fraction)
        self.snapshots: list[tuple[str, dict[_World, Fraction]]] = []
        self.seen_event_ids: set[str] = set()

    def _component_enabled(self, component: CompiledComponent) -> bool:
        return component.choice_id is None or self.choices[component.choice_id] == component.choice_option_id

    def _gate_targets(self, gate: CompiledGate, event_targets: tuple[str, ...]) -> tuple[str, ...]:
        selected: list[str] = []
        allowed = set(event_targets) if event_targets else None
        for selector_id in gate.selector_ids:
            for target_id in self.membership[selector_id]:
                if (allowed is None or target_id in allowed) and target_id not in selected:
                    selected.append(target_id)
        return tuple(sorted(selected))

    def _activations(self, gate: CompiledGate, target_ids: tuple[str, ...]) -> tuple[_GateActivation, ...]:
        if not target_ids:
            # A deterministic shared area-activation gate may own area state before
            # any target is a member.  The sentinel never enters per-target output.
            return (_GateActivation(gate.gate_id, ()),) if gate.gate_scope == "shared" else ()
        if gate.gate_scope == "shared":
            return (_GateActivation(gate.gate_id, target_ids),)
        return tuple(_GateActivation(gate.gate_id, (target_id,)) for target_id in target_ids)

    def _eligible_targets(
        self,
        world: _World,
        gate: CompiledGate,
        activation: _GateActivation,
        *,
        guard_active: frozenset[tuple[str, str]] | None = None,
    ) -> tuple[str, ...]:
        if not gate.requires_active_component_ids:
            return activation.target_ids
        active = world.active if guard_active is None else guard_active
        return tuple(
            target_id for target_id in activation.target_ids
            if all(
                (target_id, component_id) in active
                for component_id in gate.requires_active_component_ids
            )
        )

    def _component_targets(
        self,
        component: CompiledComponent,
        activation_targets: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not activation_targets:
            return ()
        return tuple(
            target_id for target_id in activation_targets
            if any(target_id in self.membership[selector_id] for selector_id in component.target_selector_ids)
        )

    def _next_gate_targets(
        self,
        gate: CompiledGate,
        next_gate: CompiledGate,
        current_targets: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Carry same-selector targets and expand genuinely new selector roles.

        Most independent edges continue resolution for one target.  A few
        authoritative graphs deliberately fan a primary hit out to a separate
        secondary selector (Explosion/Implosion), or to a primary-plus-secondary
        selector union (Electron Burst and Static Discharge).  Restricting every
        edge to the source activation would silently drop those secondary gates;
        expanding every edge would instead correlate otherwise-independent same-
        selector targets.  Selector identity provides the exact boundary.
        """

        selected: list[str] = []
        source_selectors = set(gate.selector_ids)
        current = set(current_targets)
        for selector_id in next_gate.selector_ids:
            for target_id in self.membership[selector_id]:
                if selector_id in source_selectors and target_id not in current:
                    continue
                if target_id not in selected:
                    selected.append(target_id)
        return tuple(sorted(selected))

    def _apply_branch(
        self,
        world: _World,
        gate: CompiledGate,
        branch: CompiledBranch,
        targets: tuple[str, ...],
        *,
        event_id: str,
        initial_phase: bool,
        branch_mass: Fraction,
    ) -> _World:
        active, ever, initial = set(world.active), set(world.ever), set(world.initial)
        # Required authority transition order: terminate, replace, apply, refresh.
        for component_id in (*branch.terminates, *branch.replaces):
            component = self.effect.component(component_id)
            if not self._component_enabled(component):
                continue
            for target_id in self._component_targets(component, targets):
                active.discard((target_id, component_id))
        newly_instantaneous: set[tuple[str, str]] = set()
        for component_id in branch.applies:
            component = self.effect.component(component_id)
            if not self._component_enabled(component):
                continue
            for target_id in self._component_targets(component, targets):
                target = self.targets[target_id]
                if component.magnitude.kind == "condition":
                    condition = str(component.magnitude.data["condition"])
                    if condition in target.condition_immunities:
                        self.immunity_stats[
                            (event_id, gate.gate_id, branch.branch_id, target_id, component_id, condition)
                        ] += branch_mass
                        continue
                identity = (target_id, component_id)
                active.add(identity)
                ever.add(identity)
                if initial_phase:
                    initial.add(identity)
                if component.instantaneous:
                    newly_instantaneous.add(identity)
        # Refresh changes expiry in the timeline layer; active identity is retained.
        for component_id in branch.refreshes:
            component = self.effect.component(component_id)
            if not self._component_enabled(component):
                continue
            for target_id in self._component_targets(component, targets):
                if (target_id, component_id) in active:
                    ever.add((target_id, component_id))
        active.difference_update(newly_instantaneous)
        enabled = list(world.enabled)
        for next_gate_id in branch.next_gate_ids:
            next_gate = self.effect.gate(next_gate_id)
            next_targets = self._next_gate_targets(gate, next_gate, targets)
            for activation in self._activations(next_gate, next_targets):
                if activation not in enabled:
                    enabled.append(activation)
        return _World(
            frozenset(active),
            frozenset(ever),
            frozenset(initial),
            tuple(enabled),
        )

    def _resolve_activation(
        self,
        world: _World,
        world_mass: Fraction,
        activation: _GateActivation,
        *,
        event_id: str,
        initial_phase: bool,
        guard_active: frozenset[tuple[str, str]] | None = None,
    ) -> list[tuple[_World, Fraction]]:
        gate = self.effect.gate(activation.gate_id)
        targets = self._eligible_targets(
            world,
            gate,
            activation,
            guard_active=guard_active,
        )
        if activation.target_ids and not targets:
            return [(world, world_mass)]
        stat_targets = targets
        self.gate_stats[(event_id, gate.gate_id, stat_targets)] += world_mass
        probability_target = self.targets[targets[0]] if targets else None
        distribution = _validate_distribution(
            gate,
            self.kernel.outcome_probabilities(gate, probability_target, self.context),
        )
        rows: list[tuple[_World, Fraction]] = []
        for outcome, conditional in distribution.items():
            if not conditional:
                continue
            branch = gate.branch_for_outcome(outcome)
            branch_mass = world_mass * conditional
            self.branch_stats[(event_id, gate.gate_id, branch.branch_id, outcome, stat_targets)] += branch_mass
            updated = self._apply_branch(
                world,
                gate,
                branch,
                targets,
                event_id=event_id,
                initial_phase=initial_phase,
                branch_mass=branch_mass,
            )
            if gate.role == "repeat":
                for target_id in targets:
                    if all((target_id, component_id) in updated.active for component_id in gate.requires_active_component_ids):
                        self.repeat_stats[(event_id, gate.gate_id, target_id)] += branch_mass
            rows.append((updated, branch_mass))
        return rows

    def _drain_immediate(
        self,
        worlds: dict[_World, Fraction],
        *,
        event_id: str,
        initial_phase: bool,
        guard_active: frozenset[tuple[str, str]],
    ) -> dict[_World, Fraction]:
        # The authority graph is acyclic. Each world consumes immediate
        # activations in the order supplied by the branch edge that enabled
        # them. Guards remain pinned to the pre-event active-state snapshot.
        while True:
            found_pending = False
            expanded: list[tuple[_World, Fraction]] = []
            for world, probability in worlds.items():
                activation = next(
                    (
                        candidate
                        for candidate in world.enabled
                        if self.effect.gate(candidate.gate_id).trigger.kind
                        in _IMMEDIATE_CONTINUATION_KINDS
                    ),
                    None,
                )
                if activation is None:
                    expanded.append((world, probability))
                    continue
                found_pending = True
                reduced = replace(
                    world,
                    enabled=tuple(
                        candidate
                        for candidate in world.enabled
                        if candidate != activation
                    ),
                )
                expanded.extend(
                    self._resolve_activation(
                        reduced,
                        probability,
                        activation,
                        event_id=event_id,
                        initial_phase=initial_phase,
                        guard_active=guard_active,
                    )
                )
            if not found_pending:
                return worlds
            worlds = _merge_worlds(expanded)

    def process_event(
        self,
        worlds: dict[_World, Fraction],
        event: ReliabilityEvent,
        *,
        initial_phase: bool,
    ) -> dict[_World, Fraction]:
        if event.event_id in self.seen_event_ids:
            raise ControlGraphError(
                f"Duplicate reliability event ID: {event.event_id!r}"
            )
        self.seen_event_ids.add(event.event_id)
        unknown_targets = sorted(set(event.target_ids) - self.targets.keys())
        if unknown_targets:
            raise ControlGraphError(f"Event {event.event_id!r} references unknown targets: {unknown_targets}")
        if event.gate_ids:
            gates = tuple(self.effect.gate(gate_id) for gate_id in event.gate_ids)
            mismatched = [gate.gate_id for gate in gates if gate.trigger.key != event.trigger.key]
            if mismatched:
                raise ControlGraphError(
                    f"Event {event.event_id!r} gate triggers do not match: {mismatched}"
                )
        else:
            gates = tuple(
                self.effect.gate(gate_id)
                for gate_id in self.effect.root_gate_ids
                if self.effect.gate(gate_id).trigger.key == event.trigger.key
            )
        root_ids = set(self.effect.root_gate_ids)
        root_activations: set[_GateActivation] = set()
        explicit_activations: list[_GateActivation] = []
        for gate in gates:
            rows = self._activations(gate, self._gate_targets(gate, event.target_ids))
            explicit_activations.extend(rows)
            if gate.gate_id in root_ids:
                root_activations.update(rows)

        # Keep each source world's pre-event active set until all activations
        # for this event have resolved. Descendant transitions cannot
        # retroactively change another same-event guard.
        event_rows: list[tuple[_World, Fraction]] = []
        for guard_world, guard_probability in worlds.items():
            activations = list(explicit_activations)
            # Enabled future subscriptions follow exogenous roots in their
            # branch-declared order.
            for activation in guard_world.enabled:
                gate = self.effect.gate(activation.gate_id)
                if (
                    gate.trigger.key == event.trigger.key
                    and activation not in activations
                    and (
                        not event.target_ids
                        or set(activation.target_ids) & set(event.target_ids)
                    )
                ):
                    activations.append(activation)

            lineage: dict[_World, Fraction] = {
                guard_world: guard_probability
            }
            for activation in activations:
                expanded: list[tuple[_World, Fraction]] = []
                for world, probability in lineage.items():
                    # Non-root gates are subscriptions created by a branch
                    # edge and exist only where that edge was traversed.
                    if (
                        activation not in root_activations
                        and activation not in world.enabled
                    ):
                        expanded.append((world, probability))
                        continue
                    expanded.extend(
                        self._resolve_activation(
                            world,
                            probability,
                            activation,
                            event_id=event.event_id,
                            initial_phase=initial_phase,
                            guard_active=guard_world.active,
                        )
                    )
                lineage = _merge_worlds(expanded)
                lineage = self._drain_immediate(
                    lineage,
                    event_id=event.event_id,
                    initial_phase=initial_phase,
                    guard_active=guard_world.active,
                )
            event_rows.extend(lineage.items())
        worlds = _merge_worlds(event_rows)
        if event.expire_component_ids:
            for component_id in event.expire_component_ids:
                self.effect.component(component_id)
            affected = set(event.target_ids) if event.target_ids else set(self.targets)
            worlds = {
                replace(
                    world,
                    active=frozenset(
                        identity for identity in world.active
                        if not (identity[0] in affected and identity[1] in event.expire_component_ids)
                    ),
                ): probability
                for world, probability in worlds.items()
            }
            worlds = _merge_worlds(worlds.items())
        window_id = event.window_id or event.event_id
        if any(existing == window_id for existing, _snapshot in self.snapshots):
            raise ControlGraphError(f"Duplicate reliability window ID: {window_id!r}")
        self.snapshots.append((window_id, dict(worlds)))
        return worlds


def evaluate_reliability(
    effect: CompiledEffect,
    *,
    targets: Sequence[ReliabilityTarget],
    selector_membership: Mapping[str, Sequence[str]],
    selector_context: SelectorContext = SelectorContext(),
    kernel: ProbabilityKernel | None = None,
    context: ProbabilityContext = ProbabilityContext(),
    choices: Mapping[str, str] | None = None,
    events: Sequence[ReliabilityEvent] = (),
    candidate_component_ids: Iterable[str] | None = None,
    include_initial: bool = True,
) -> ReliabilityResult:
    """Enumerate exact joint reliability for one compiled effect invocation.

    ``selector_membership``, ``selector_context``, and ``choices`` are
    caller-supplied scenario facts rather than inferred policy. Selector facts
    are required only for selected memberships whose compiled selector needs
    them. Initial scalar root gates are evaluated by default.
    Later repeat/recurring/concentration events are supplied in exact caller
    order.  ``expire_component_ids`` on an event is the narrow handoff for a
    future timeline engine to expose active-window reliability.
    """

    if not isinstance(effect, CompiledEffect):
        raise TypeError("evaluate_reliability requires CompiledEffect")
    # Preserve choice failure precedence: incomplete semantic bindings are
    # rejected before unrelated evaluation-output configuration.
    effect.bind_choices(choices)
    if candidate_component_ids is None:
        raise ControlGraphError(
            "candidate_component_ids must be supplied explicitly"
        )
    chosen_kernel = D20ProbabilityKernel() if kernel is None else kernel
    scenario = ReliabilityScenario.create(
        effect,
        targets=targets,
        selector_membership=selector_membership,
        selector_context=selector_context,
        choices=choices,
        probability_context=context,
        kernel=chosen_kernel,
        events=events,
        candidate_component_ids=candidate_component_ids,
        include_initial=include_initial,
    )
    candidates = frozenset(scenario.candidate_component_ids)
    evaluator = _Evaluator(
        effect,
        scenario.targets,
        dict(scenario.selector_membership),
        scenario.selector_context,
        chosen_kernel,
        scenario.probability_context,
        scenario.choice_bindings,
        candidates,
    )
    worlds: dict[_World, Fraction] = {_World(): Fraction(1)}
    for event in scenario.event_script[:scenario.initial_event_count]:
        worlds = evaluator.process_event(
            worlds,
            event,
            initial_phase=True,
        )
    if not evaluator.snapshots:
        evaluator.snapshots.append(("initial", dict(worlds)))
    for event in scenario.event_script[scenario.initial_event_count:]:
        worlds = evaluator.process_event(worlds, event, initial_phase=False)
    if sum(worlds.values(), Fraction()) != 1:
        raise ControlGraphError("Joint-world probabilities do not sum exactly to 1")
    target_ids = scenario.target_ids
    component_rows: list[ComponentReliability] = []
    for component in effect.components:
        for target_id in target_ids:
            identity = (target_id, component.component_id)
            initially = sum(
                (probability for world, probability in worlds.items() if identity in world.initial),
                Fraction(),
            )
            ever = sum(
                (probability for world, probability in worlds.items() if identity in world.ever),
                Fraction(),
            )
            active_by_window = tuple(
                (
                    window_id,
                    sum(
                        (probability for world, probability in snapshot.items() if identity in world.active),
                        Fraction(),
                    ),
                )
                for window_id, snapshot in evaluator.snapshots
            )
            component_rows.append(
                ComponentReliability(
                    component.component_id,
                    component.qualified_id,
                    target_id,
                    initially,
                    ever,
                    active_by_window,
                )
            )
    any_component = sum(
        (probability for world, probability in worlds.items() if world.ever),
        Fraction(),
    )
    any_candidate = sum(
        (
            probability
            for world, probability in worlds.items()
            if any(component_id in candidates for _target_id, component_id in world.ever)
        ),
        Fraction(),
    )
    any_component_by_target = tuple(
        (
            target_id,
            sum(
                (probability for world, probability in worlds.items() if any(item[0] == target_id for item in world.ever)),
                Fraction(),
            ),
        )
        for target_id in target_ids
    )
    any_candidate_by_target = tuple(
        (
            target_id,
            sum(
                (
                    probability
                    for world, probability in worlds.items()
                    if any(item[0] == target_id and item[1] in candidates for item in world.ever)
                ),
                Fraction(),
            ),
        )
        for target_id in target_ids
    )
    result = ReliabilityResult(
        effect_id=effect.effect_id,
        target_ids=target_ids,
        component_reliability=tuple(component_rows),
        gate_probabilities=tuple(
            GateProbability(event_id, gate_id, target_scope, probability)
            for (event_id, gate_id, target_scope), probability in sorted(evaluator.gate_stats.items())
        ),
        branch_probabilities=tuple(
            BranchProbability(event_id, gate_id, branch_id, outcome, target_scope, probability)
            for (event_id, gate_id, branch_id, outcome, target_scope), probability
            in sorted(evaluator.branch_stats.items())
        ),
        repeat_survival=tuple(
            RepeatSurvival(event_id, gate_id, target_id, probability)
            for (event_id, gate_id, target_id), probability in sorted(evaluator.repeat_stats.items())
        ),
        immunity_suppressions=tuple(
            ImmunitySuppression(event_id, gate_id, branch_id, target_id, component_id, condition, probability)
            for (event_id, gate_id, branch_id, target_id, component_id, condition), probability
            in sorted(evaluator.immunity_stats.items())
        ),
        any_candidate_probability=any_candidate,
        any_component_probability=any_component,
        any_candidate_by_target=any_candidate_by_target,
        any_component_by_target=any_component_by_target,
        final_world_count=len(worlds),
        scenario=scenario,
        scenario_digest=scenario.scenario_digest,
    )
    _validate_reliability_result_structure(
        effect,
        result,
        expected_scenario_digest=scenario.scenario_digest,
    )
    issued = _issue_reliability_result(result)
    validate_reliability_result(
        effect,
        issued,
        expected_scenario_digest=scenario.scenario_digest,
        expected_issuance_token=reliability_result_issuance_token(issued),
    )
    return issued


__all__ = [
    "BranchProbability",
    "ChoiceBindings",
    "CompiledAuthority",
    "CompiledBranch",
    "CompiledComponent",
    "CompiledEffect",
    "CompiledEvent",
    "CompiledExclusion",
    "CompiledGate",
    "CompiledMagnitude",
    "CompiledMastery",
    "CONTROL_MAGNITUDE_KINDS",
    "ComponentReliability",
    "ControlGraphError",
    "D20ProbabilityKernel",
    "FrozenMap",
    "GateProbability",
    "ImmunitySuppression",
    "ProbabilityContext",
    "ProbabilityKernel",
    "ProbabilityKernelIdentity",
    "QualifiedId",
    "ReliabilityEvent",
    "ReliabilityResult",
    "ReliabilityScenario",
    "ReliabilityTarget",
    "RepeatSurvival",
    "SelectorContext",
    "compile_control_authority",
    "compile_magnitude",
    "d20_attack_hit_probability",
    "d20_save_success_probability",
    "evaluate_reliability",
    "load_compiled_control_authority",
    "resolve_roll_mode",
    "reliability_result_issuance_token",
    "validate_reliability_result",
    "validate_selector_membership",
]

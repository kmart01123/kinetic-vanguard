"""Deterministic three-round timing, area, concentration, and displacement mechanics.

This module is deliberately scenario-driven.  It creates no attacks, damage, target
positions, or tactical choices that the caller did not supply.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence


TIMELINE_ENGINE_VERSION = "1.0.0"
INITIATIVE_CONVENTIONS = ("fighter_first_v1", "target_before_fighter_v1")
AREA_RESPONSE_CONVENTIONS = ("shortest_route_v1", "fixed_occupancy_v1")
DISPLACEMENT_FUNCTIONS = ("sqrt_5ft_v1", "log2_5ft_v1", "banded_10ft_v1")
MOVEMENT_MODES = ("walk", "fly", "swim", "climb", "burrow")
ENVIRONMENTS = ("grounded", "airborne", "liquid")

_STRUCTURAL_EVENT_KINDS = {
    "round_start", "round_end", "controller_turn_start", "controller_turn_end",
    "target_turn_start", "target_turn_end", "target_active_turn_opportunity",
    "target_attack_opportunity", "target_movement_opportunity",
}
_SCRIPTED_EVENT_KINDS = {
    "controller_attack_opportunity", "reaction_window", "save_opportunity",
    "declaration", "activation", "hit", "entry", "exit", "damage_context",
    "concentration_end", "instantaneous_resolution",
}
_TARGET_PHASES = (
    "start", "before_movement", "after_movement", "after_attacks", "end",
)


class TimelineError(ValueError):
    """Raised when required scenario timing or geometry is missing or invalid."""


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise TimelineError(f"{label} must be a non-empty trimmed string")
    return value


def _identifier_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TimelineError(f"{label} must be an array of identifiers")
    result = [
        _identifier(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(result) != len(set(result)):
        raise TimelineError(f"{label} must not contain duplicates")
    return result


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise TimelineError(f"{label} must be an integer of at least {minimum}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise TimelineError(f"{label} must be a boolean")
    return value


def _json_value(value: Any, label: str) -> Any:
    try:
        json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise TimelineError(f"{label} must be JSON-serializable without non-finite numbers") from error
    return deepcopy(value)


def _fraction(value: Any, label: str, *, positive: bool = False) -> Fraction:
    if isinstance(value, bool):
        raise TimelineError(f"{label} must be a finite number or exact fraction")
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int):
        result = Fraction(value)
    elif isinstance(value, float) and math.isfinite(value):
        result = Fraction(str(value))
    elif isinstance(value, Mapping) and set(value) == {"numerator", "denominator"}:
        numerator = _integer(value["numerator"], f"{label}.numerator", 0)
        denominator = _integer(value["denominator"], f"{label}.denominator", 1)
        result = Fraction(numerator, denominator)
    else:
        raise TimelineError(f"{label} must be a finite number or exact fraction")
    if result < 0 or (positive and result == 0):
        qualifier = "positive" if positive else "non-negative"
        raise TimelineError(f"{label} must be {qualifier}")
    return result


def _fraction_record(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _number(value: Fraction) -> int | float:
    return value.numerator if value.denominator == 1 else float(value)


@dataclass(frozen=True)
class TimelineEvent:
    event_id: str
    sequence: int
    round: int
    kind: str
    turn_id: str | None
    turn_owner: str | None
    actor_id: str | None = None
    target_id: str | None = None
    window_id: str | None = None
    reaction_interval_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "round": self.round,
            "kind": self.kind,
            "turn_id": self.turn_id,
            "turn_owner": self.turn_owner,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "window_id": self.window_id,
            "reaction_interval_id": self.reaction_interval_id,
            "payload": deepcopy(dict(self.payload)),
        }


@dataclass(frozen=True)
class ReactionInterval:
    interval_id: str
    window_id: str | None
    target_id: str
    round: int
    start_event_id: str
    end_before_event_id: str
    initially_available: bool | None
    horizon_entry_partial: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_id": self.interval_id,
            "window_id": self.window_id,
            "target_id": self.target_id,
            "round": self.round,
            "start_event_id": self.start_event_id,
            "end_before_event_id": self.end_before_event_id,
            "initially_available": self.initially_available,
            "horizon_entry_partial": self.horizon_entry_partial,
        }


@dataclass(frozen=True)
class TimelineSchedule:
    convention: str
    rounds: int
    target_ids: tuple[str, ...]
    events: tuple[TimelineEvent, ...]
    reaction_intervals: tuple[ReactionInterval, ...]

    def event(self, event_id: str) -> TimelineEvent:
        matches = [event for event in self.events if event.event_id == event_id]
        if len(matches) != 1:
            raise TimelineError(f"Schedule event ID must resolve exactly once: {event_id!r}")
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_engine_version": TIMELINE_ENGINE_VERSION,
            "initiative_convention": self.convention,
            "rounds": self.rounds,
            "target_ids": list(self.target_ids),
            "events": [event.to_dict() for event in self.events],
            "reaction_intervals": [interval.to_dict() for interval in self.reaction_intervals],
        }


def _round_rows(value: Mapping[int | str, Sequence[Mapping[str, Any]]] | None, label: str) -> dict[int, list[Mapping[str, Any]]]:
    if value is None:
        return {round_number: [] for round_number in range(1, 4)}
    if not isinstance(value, Mapping):
        raise TimelineError(f"{label} must be an object keyed by round")
    result: dict[int, list[Mapping[str, Any]]] = {}
    for round_number in range(1, 4):
        raw = value.get(round_number, value.get(str(round_number), []))
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise TimelineError(f"{label}.{round_number} must be an array")
        result[round_number] = list(raw)
    unknown = {str(key) for key in value if str(key) not in {"1", "2", "3"}}
    if unknown:
        raise TimelineError(f"{label} has unsupported rounds: {sorted(unknown)}")
    return result


def _attack_counts(value: Any, target_id: str) -> dict[int, int]:
    label = f"target_attack_counts.{target_id}"
    if isinstance(value, int) and not isinstance(value, bool):
        count = _integer(value, label)
        return {round_number: count for round_number in range(1, 4)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != 3:
            raise TimelineError(f"{label} must contain exactly three round counts")
        return {index + 1: _integer(count, f"{label}[{index}]") for index, count in enumerate(value)}
    if isinstance(value, Mapping):
        rows: dict[int, int] = {}
        for round_number in range(1, 4):
            if round_number in value:
                raw = value[round_number]
            elif str(round_number) in value:
                raw = value[str(round_number)]
            else:
                raise TimelineError(f"{label} must supply round {round_number}")
            rows[round_number] = _integer(raw, f"{label}.{round_number}")
        if {str(key) for key in value} != {"1", "2", "3"}:
            raise TimelineError(f"{label} must supply exactly rounds 1, 2, and 3")
        return rows
    raise TimelineError(f"{label} must explicitly supply three target attack counts")


def _script_descriptor(value: Mapping[str, Any], label: str, *, target: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TimelineError(f"{label} must be an object")
    allowed = {"kind", "payload", "target_id", "window_id"} | ({"phase"} if target else set())
    unknown = set(value) - allowed
    if unknown:
        raise TimelineError(f"{label} has unknown fields: {sorted(unknown)}")
    kind = _identifier(value.get("kind"), f"{label}.kind")
    if kind not in _SCRIPTED_EVENT_KINDS:
        if kind in _STRUCTURAL_EVENT_KINDS:
            raise TimelineError(f"{label}.kind {kind!r} is schedule-owned and cannot be scripted")
        raise TimelineError(f"{label}.kind is unsupported: {kind!r}")
    phase = value.get("phase", "start") if target else "controller"
    if target and phase not in _TARGET_PHASES:
        raise TimelineError(f"{label}.phase is unsupported: {phase!r}")
    payload = value.get("payload", {})
    if not isinstance(payload, Mapping):
        raise TimelineError(f"{label}.payload must be an object")
    return {
        "kind": kind,
        "phase": phase,
        "payload": _json_value(dict(payload), f"{label}.payload"),
        "target_id": _identifier(value["target_id"], f"{label}.target_id") if value.get("target_id") is not None else None,
        "window_id": _identifier(value["window_id"], f"{label}.window_id") if value.get("window_id") is not None else None,
    }


def build_schedule(
    convention: str,
    target_ids: Sequence[str],
    *,
    controller_events_by_round: Mapping[int | str, Sequence[Mapping[str, Any]]] | None = None,
    target_events_by_round: Mapping[str, Mapping[int | str, Sequence[Mapping[str, Any]]]] | None = None,
    target_attack_counts: Mapping[str, Any],
    initial_reaction_availability: Mapping[str, bool] | None = None,
    rounds: int = 3,
) -> TimelineSchedule:
    """Build one exact three-round schedule without inventing caller opportunities."""

    if convention not in INITIATIVE_CONVENTIONS:
        raise TimelineError(f"Unsupported initiative convention: {convention!r}")
    if rounds != 3:
        raise TimelineError("The maintained timeline horizon is exactly three rounds")
    if not isinstance(target_ids, Sequence) or isinstance(target_ids, (str, bytes)):
        raise TimelineError("target_ids must be an array")
    targets = tuple(_identifier(value, f"target_ids[{index}]") for index, value in enumerate(target_ids))
    if len(targets) != len(set(targets)):
        raise TimelineError("target_ids must be unique")
    if initial_reaction_availability is None:
        initial_reactions = {target_id: None for target_id in targets}
    elif not isinstance(initial_reaction_availability, Mapping) or set(initial_reaction_availability) != set(targets):
        raise TimelineError(
            "initial_reaction_availability must explicitly cover every and only supplied target"
        )
    elif not all(isinstance(value, bool) for value in initial_reaction_availability.values()):
        raise TimelineError("initial_reaction_availability values must be booleans")
    else:
        initial_reactions = dict(initial_reaction_availability)
    if not isinstance(target_attack_counts, Mapping) or set(target_attack_counts) != set(targets):
        raise TimelineError("target_attack_counts must explicitly cover every and only supplied target")
    attacks = {target_id: _attack_counts(target_attack_counts[target_id], target_id) for target_id in targets}
    controller_rows = _round_rows(controller_events_by_round, "controller_events_by_round")
    target_source = {} if target_events_by_round is None else target_events_by_round
    if not isinstance(target_source, Mapping) or set(target_source) - set(targets):
        raise TimelineError("target_events_by_round may contain only supplied target IDs")
    target_rows = {
        target_id: _round_rows(target_source.get(target_id), f"target_events_by_round.{target_id}")
        for target_id in targets
    }

    events: list[TimelineEvent] = []
    current_reaction_interval_ids = {
        target_id: f"horizon:target:{target_id}:reaction_interval"
        for target_id in targets
    }

    def append(
        *, event_id: str, round_number: int, kind: str, turn_id: str | None,
        turn_owner: str | None, actor_id: str | None = None, target_id: str | None = None,
        window_id: str | None = None, reaction_interval_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            event_id=event_id, sequence=len(events), round=round_number, kind=kind,
            turn_id=turn_id, turn_owner=turn_owner, actor_id=actor_id, target_id=target_id,
            window_id=window_id, reaction_interval_id=reaction_interval_id,
            payload=_json_value(dict(payload or {}), f"{event_id}.payload"),
        )
        events.append(event)
        return event

    def scripted(descriptor: Mapping[str, Any], label: str, round_number: int, turn_id: str, turn_owner: str, actor_id: str, default_target: str | None, index: int, reaction_id: str | None = None) -> None:
        row = _script_descriptor(descriptor, label, target=turn_owner == "target")
        target_id = row["target_id"] or default_target
        if row["target_id"] is not None and row["target_id"] not in targets:
            raise TimelineError(f"{label}.target_id is not a supplied target")
        semantic = f"r{round_number}:{turn_owner}:{actor_id}:script:{index:03d}:{row['kind']}"
        window_id = row["window_id"]
        if row["kind"] in {"controller_attack_opportunity", "reaction_window", "save_opportunity"} and window_id is None:
            window_id = semantic + ":window"
        effective_reaction_id = reaction_id
        if row["kind"] == "reaction_window":
            if target_id is None:
                raise TimelineError(f"{label}.target_id is required for a reaction window")
            effective_reaction_id = current_reaction_interval_ids[target_id]
            if effective_reaction_id.startswith("horizon:") and initial_reactions[target_id] is None:
                raise TimelineError(
                    f"{label} requires initial_reaction_availability for target {target_id!r}"
                )
        append(
            event_id=semantic, round_number=round_number, kind=row["kind"], turn_id=turn_id,
            turn_owner=turn_owner, actor_id=actor_id, target_id=target_id, window_id=window_id,
            reaction_interval_id=effective_reaction_id, payload=row["payload"],
        )

    def controller_turn(round_number: int) -> None:
        turn_id = f"r{round_number}:controller:turn"
        append(event_id=turn_id + ":start", round_number=round_number, kind="controller_turn_start", turn_id=turn_id, turn_owner="controller", actor_id="controller")
        for index, descriptor in enumerate(controller_rows[round_number]):
            scripted(descriptor, f"controller_events_by_round.{round_number}[{index}]", round_number, turn_id, "controller", "controller", None, index)
        append(event_id=turn_id + ":end", round_number=round_number, kind="controller_turn_end", turn_id=turn_id, turn_owner="controller", actor_id="controller")

    def target_turn(round_number: int, target_id: str) -> None:
        turn_id = f"r{round_number}:target:{target_id}:turn"
        reaction_id = f"r{round_number}:target:{target_id}:reaction_interval"
        reaction_window_id = f"r{round_number}:target:{target_id}:reaction_window"
        current_reaction_interval_ids[target_id] = reaction_id
        append(event_id=turn_id + ":start", round_number=round_number, kind="target_turn_start", turn_id=turn_id, turn_owner="target", actor_id=target_id, target_id=target_id, reaction_interval_id=reaction_id)
        append(event_id=reaction_window_id, round_number=round_number, kind="reaction_window", turn_id=turn_id, turn_owner="target", actor_id=target_id, target_id=target_id, window_id=reaction_window_id, reaction_interval_id=reaction_id, payload={"availability_interval": True})
        descriptors = [
            _script_descriptor(item, f"target_events_by_round.{target_id}.{round_number}[{index}]", target=True)
            for index, item in enumerate(target_rows[target_id][round_number])
        ]

        def phase(name: str) -> None:
            for index, row in enumerate(descriptors):
                if row["phase"] != name:
                    continue
                scripted(row, f"target_events_by_round.{target_id}.{round_number}[{index}]", round_number, turn_id, "target", target_id, target_id, index, reaction_id)

        # Target-start scripts and pre-movement gates/repeat saves resolve before
        # the one legal movement/standing/area response.  Its immediate exit or
        # state-transition hooks resolve before the active and attack windows.
        # After-attack and end hooks form the remaining caller-scripted block.
        phase("start")
        phase("before_movement")
        append(event_id=turn_id + ":movement", round_number=round_number, kind="target_movement_opportunity", turn_id=turn_id, turn_owner="target", actor_id=target_id, target_id=target_id, window_id=turn_id + ":movement:window", reaction_interval_id=reaction_id)
        phase("after_movement")
        append(event_id=turn_id + ":active_turn", round_number=round_number, kind="target_active_turn_opportunity", turn_id=turn_id, turn_owner="target", actor_id=target_id, target_id=target_id, window_id=turn_id + ":active_turn:window", reaction_interval_id=reaction_id)
        for attack_index in range(1, attacks[target_id][round_number] + 1):
            append(event_id=f"{turn_id}:attack:{attack_index:03d}", round_number=round_number, kind="target_attack_opportunity", turn_id=turn_id, turn_owner="target", actor_id=target_id, target_id=target_id, window_id=f"{turn_id}:attack:{attack_index:03d}:window", reaction_interval_id=reaction_id, payload={"attack_index": attack_index})
        phase("after_attacks")
        phase("end")
        append(event_id=turn_id + ":end", round_number=round_number, kind="target_turn_end", turn_id=turn_id, turn_owner="target", actor_id=target_id, target_id=target_id, reaction_interval_id=reaction_id)

    for round_number in range(1, 4):
        append(event_id=f"r{round_number}:round:start", round_number=round_number, kind="round_start", turn_id=None, turn_owner=None, payload={"previous_round": round_number - 1 or None})
        if convention == "fighter_first_v1":
            controller_turn(round_number)
            for target_id in targets:
                target_turn(round_number, target_id)
        else:
            for target_id in targets:
                target_turn(round_number, target_id)
            controller_turn(round_number)
        append(event_id=f"r{round_number}:round:end", round_number=round_number, kind="round_end", turn_id=None, turn_owner=None, payload={"next_round": round_number + 1 if round_number < 3 else None})

    event_ids = [event.event_id for event in events]
    if len(event_ids) != len(set(event_ids)):
        raise TimelineError("Schedule generated duplicate semantic event IDs")
    window_ids = [event.window_id for event in events if event.window_id is not None]
    if len(window_ids) != len(set(window_ids)):
        raise TimelineError("Schedule contains duplicate window IDs")
    intervals: list[ReactionInterval] = []
    for target_id in targets:
        starts = [event for event in events if event.kind == "target_turn_start" and event.target_id == target_id]
        intervals.append(ReactionInterval(
            interval_id=f"horizon:target:{target_id}:reaction_interval",
            window_id=None,
            target_id=target_id,
            round=1,
            start_event_id="r1:round:start",
            end_before_event_id=starts[0].event_id,
            initially_available=initial_reactions[target_id],
            horizon_entry_partial=True,
        ))
        for index, start in enumerate(starts):
            end_before = starts[index + 1].event_id if index + 1 < len(starts) else "r3:round:end"
            intervals.append(ReactionInterval(
                interval_id=f"r{start.round}:target:{target_id}:reaction_interval",
                window_id=f"r{start.round}:target:{target_id}:reaction_window",
                target_id=target_id, round=start.round, start_event_id=start.event_id,
                end_before_event_id=end_before,
                initially_available=True,
                horizon_entry_partial=False,
            ))
    intervals.sort(key=lambda row: (0 if row.horizon_entry_partial else row.round, targets.index(row.target_id)))
    return TimelineSchedule(convention, rounds, targets, tuple(events), tuple(intervals))


def typed_event_matches(event: TimelineEvent, specification: Mapping[str, Any], *, target_id: str | None = None, triggering_turn_id: str | None = None) -> bool:
    """Match an authority event descriptor against one normalized schedule event."""

    if not isinstance(specification, Mapping) or "kind" not in specification:
        raise TimelineError("typed event specification must be an object with kind")
    kind = specification["kind"]
    if kind == "save":
        if set(specification) != {"kind"}:
            raise TimelineError("save event has unknown fields")
        return event.kind == "save_opportunity" and (
            target_id is None or event.target_id == target_id
        )
    if kind in {"declaration", "activation", "hit", "damage_context", "concentration_end", "instantaneous_resolution"}:
        if set(specification) != {"kind"}:
            raise TimelineError(f"{kind} event has unknown fields")
        if event.kind != kind:
            return False
        if kind in {"hit", "damage_context"}:
            return target_id is None or event.target_id == target_id
        return True
    if kind == "turn":
        if set(specification) != {"kind", "owner", "turn_anchor"}:
            raise TimelineError("turn event must contain exactly kind, owner, and turn_anchor")
        owner, anchor = specification["owner"], specification["turn_anchor"]
        if owner not in {"controller", "target", "triggering_turn"} or anchor not in {"start", "end", "during"}:
            raise TimelineError("turn event owner or anchor is unsupported")
        if owner == "triggering_turn":
            if anchor != "end":
                raise TimelineError("triggering_turn event must use end")
            return triggering_turn_id is not None and event.turn_id == triggering_turn_id and event.kind in {"controller_turn_end", "target_turn_end"}
        if owner == "controller":
            expected = {"start": "controller_turn_start", "end": "controller_turn_end"}.get(anchor)
            return event.turn_owner == "controller" and (event.kind == expected if expected else event.kind not in {"controller_turn_start", "controller_turn_end"})
        expected = {"start": "target_turn_start", "end": "target_turn_end"}.get(anchor)
        return event.turn_owner == "target" and (target_id is None or event.target_id == target_id) and (event.kind == expected if expected else event.kind not in {"target_turn_start", "target_turn_end"})
    if kind in {"entry", "exit"}:
        expected = {"entry": {"kind", "owner", "turn_anchor"}, "exit": {"kind", "owner", "turn_anchor"}}[kind]
        if set(specification) != expected:
            raise TimelineError(f"{kind} event has invalid fields")
        required = ("any_creature", "during_turn") if kind == "entry" else ("target", "during_turn")
        if (specification["owner"], specification["turn_anchor"]) != required:
            raise TimelineError(f"{kind} event owner or anchor is unsupported")
        return event.kind == kind and (target_id is None or event.target_id == target_id)
    raise TimelineError(f"Unsupported typed event kind: {kind!r}")


def resolve_expiry_index(schedule: TimelineSchedule, applied_event_id: str, duration: Mapping[str, Any], *, target_id: str | None = None) -> int | None:
    """Return the exact schedule sequence where a duration ends, or ``None`` for state-driven duration."""

    applied = schedule.event(applied_event_id)
    if not isinstance(duration, Mapping):
        raise TimelineError("duration must be an object")
    kind = duration.get("kind")
    if kind == "instantaneous":
        if set(duration) != {"kind"}:
            raise TimelineError("instantaneous duration has unknown fields")
        return applied.sequence
    if kind == "while_in_area":
        if set(duration) != {"kind", "area_id"}:
            raise TimelineError("while_in_area duration requires exactly area_id")
        _identifier(duration["area_id"], "duration.area_id")
        return None
    if kind == "concentration":
        if set(duration) != {"kind", "maximum_value", "unit"}:
            raise TimelineError("concentration duration requires maximum_value and unit")
        maximum_value = _integer(
            duration["maximum_value"],
            "duration.maximum_value",
            1,
        )
        round_multipliers = {"round": 1, "minute": 10, "hour": 600}
        if duration["unit"] not in round_multipliers:
            raise TimelineError("duration.unit is unsupported")
        duration_rounds = maximum_value * round_multipliers[duration["unit"]]
        expiry_round = applied.round + duration_rounds
        if expiry_round > schedule.rounds:
            return None

        anchor_owners = {
            "controller_turn_start": "controller",
            "controller_turn_end": "controller",
            "target_turn_start": "target",
            "target_turn_end": "target",
        }
        owner = anchor_owners.get(applied.kind)
        if owner is None:
            raise TimelineError(
                "In-horizon concentration expiry requires a canonical "
                "controller/target turn start or end anchor"
            )
        resolved_target = applied.target_id
        if owner == "target":
            if resolved_target is None:
                raise TimelineError(
                    "Target concentration anchor is missing its target identity"
                )
            if target_id is not None and target_id != resolved_target:
                raise TimelineError(
                    "target_id does not match the applied target turn anchor"
                )
        matches = [
            event
            for event in schedule.events
            if event.round == expiry_round
            and event.kind == applied.kind
            and (
                owner == "controller"
                or event.target_id == resolved_target
            )
        ]
        if len(matches) != 1:
            raise TimelineError(
                "In-horizon concentration expiry anchor must resolve exactly once"
            )
        return matches[0].sequence
    if kind != "relative" or set(duration) != {"kind", "owner", "anchor", "offset_turns"}:
        raise TimelineError("relative duration has an invalid shape")
    owner, anchor = duration["owner"], duration["anchor"]
    offset = _integer(duration["offset_turns"], "duration.offset_turns")
    if owner == "triggering_turn":
        if anchor != "end_turn" or offset != 0 or applied.turn_id is None:
            raise TimelineError("triggering_turn duration requires end_turn, zero offset, and an owning turn")
        if applied.kind in {"controller_turn_end", "target_turn_end"}:
            return applied.sequence
        for event in schedule.events[applied.sequence + 1:]:
            if event.turn_id == applied.turn_id and event.kind in {"controller_turn_end", "target_turn_end"}:
                return event.sequence
        raise TimelineError("triggering turn has no end boundary")
    if owner not in {"controller", "target"} or anchor not in {"start_turn", "end_turn"}:
        raise TimelineError("relative duration owner or anchor is unsupported")
    if target_id is not None:
        _identifier(target_id, "target_id")
    resolved_target = target_id or applied.target_id
    if owner == "target" and resolved_target is None:
        raise TimelineError("target-relative duration requires target_id")
    if owner == "target" and resolved_target not in schedule.target_ids:
        raise TimelineError("target-relative duration target_id is not in the schedule")
    start_kind = "controller_turn_start" if owner == "controller" else "target_turn_start"
    end_kind = "controller_turn_end" if owner == "controller" else "target_turn_end"
    starts = [event for event in schedule.events if event.kind == start_kind and (owner == "controller" or event.target_id == resolved_target)]
    current_start = next((event for event in reversed(starts) if event.sequence <= applied.sequence and event.turn_id == applied.turn_id), None)
    if current_start is not None:
        desired_index = starts.index(current_start) + offset
    else:
        first_future = next((index for index, event in enumerate(starts) if event.sequence > applied.sequence), None)
        if first_future is None:
            return None
        desired_index = first_future + max(0, offset - 1)
    if desired_index >= len(starts):
        return None
    desired_turn_id = starts[desired_index].turn_id
    desired_kind = start_kind if anchor == "start_turn" else end_kind
    return next(event.sequence for event in schedule.events if event.turn_id == desired_turn_id and event.kind == desired_kind)


def prone_movement_response(*, target_id: str, prone: bool, current_speed_ft: int, movement_denied: bool = False) -> dict[str, Any]:
    target_id = _identifier(target_id, "target_id")
    prone = _boolean(prone, "prone")
    speed = _integer(current_speed_ft, "current_speed_ft")
    denied = _boolean(movement_denied, "movement_denied")
    if not prone:
        return {"target_id": target_id, "was_prone": False, "stood": False, "standing_cost_ft": 0, "remaining_movement_ft": speed, "prone_after": False, "reason": "not_prone"}
    if speed == 0 or denied:
        return {"target_id": target_id, "was_prone": True, "stood": False, "standing_cost_ft": 0, "remaining_movement_ft": 0, "prone_after": True, "reason": "speed_zero" if speed == 0 else "movement_denied"}
    cost = speed // 2
    return {"target_id": target_id, "was_prone": True, "stood": True, "standing_cost_ft": cost, "remaining_movement_ft": speed - cost, "prone_after": False, "reason": "first_legal_movement_opportunity"}


def effective_movement_speeds(
    base_speeds_ft: Mapping[str, int], *, flat_reductions_ft: Mapping[str, int] | None = None,
    fractional_multipliers: Mapping[str, Any] | None = None, denied_modes: Iterable[str] = (), speed_zero: bool = False,
    mixed_operation_order: Sequence[str] | None = None,
) -> dict[str, int]:
    """Apply typed Speed operations, requiring caller order for a mixed operation."""

    if not isinstance(base_speeds_ft, Mapping):
        raise TimelineError("base_speeds_ft must be an object")
    _boolean(speed_zero, "speed_zero")
    if flat_reductions_ft is not None and not isinstance(flat_reductions_ft, Mapping):
        raise TimelineError("flat_reductions_ft must be an object")
    if fractional_multipliers is not None and not isinstance(fractional_multipliers, Mapping):
        raise TimelineError("fractional_multipliers must be an object")
    denied = set(denied_modes)
    if denied - set(MOVEMENT_MODES):
        raise TimelineError(f"Unknown denied movement modes: {sorted(denied - set(MOVEMENT_MODES))}")
    reductions = {} if flat_reductions_ft is None else flat_reductions_ft
    multipliers = {} if fractional_multipliers is None else fractional_multipliers
    if set(base_speeds_ft) - set(MOVEMENT_MODES) or set(reductions) - set(MOVEMENT_MODES) or set(multipliers) - set(MOVEMENT_MODES):
        raise TimelineError("Movement speed inputs contain an unsupported movement mode")
    has_flat = any(
        _integer(value, f"flat_reductions_ft.{mode}") > 0
        for mode, value in reductions.items()
    )
    has_fraction = any(
        _fraction(value, f"fractional_multipliers.{mode}") != 1
        for mode, value in multipliers.items()
    )
    operation_order = tuple(mixed_operation_order or ())
    allowed_orders = {("flat", "fraction"), ("fraction", "flat")}
    if mixed_operation_order is not None and operation_order not in allowed_orders:
        raise TimelineError(
            "mixed_operation_order must be flat/fraction or fraction/flat"
        )
    if has_flat and has_fraction and operation_order not in allowed_orders:
        raise TimelineError(
            "Mixed flat and fractional Speed changes require explicit operation order"
        )
    if not operation_order:
        operation_order = ("flat", "fraction")
    result: dict[str, int] = {}
    for mode in MOVEMENT_MODES:
        if mode not in base_speeds_ft:
            continue
        base = _integer(base_speeds_ft[mode], f"base_speeds_ft.{mode}")
        reduction = _integer(reductions.get(mode, 0), f"flat_reductions_ft.{mode}")
        multiplier = _fraction(multipliers.get(mode, 1), f"fractional_multipliers.{mode}")
        if speed_zero or mode in denied:
            result[mode] = 0
            continue
        speed = Fraction(base)
        for operation in operation_order:
            if operation == "flat":
                speed = max(Fraction(), speed - reduction)
            else:
                speed = max(Fraction(), speed * multiplier)
        result[mode] = math.floor(speed)
    return result


def _route(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TimelineError(f"{label} must be an object")
    expected = {"route_id", "mode", "distance_to_exit_ft", "compatible", "movement_cost_multiplier", "environment"}
    if set(value) != expected:
        raise TimelineError(f"{label} keys are invalid; missing={sorted(expected - set(value))}, unknown={sorted(set(value) - expected)}")
    route_id = _identifier(value["route_id"], f"{label}.route_id")
    mode = value["mode"]
    if mode not in MOVEMENT_MODES:
        raise TimelineError(f"{label}.mode is unsupported: {mode!r}")
    environment = value["environment"]
    if environment not in ENVIRONMENTS:
        raise TimelineError(f"{label}.environment is unsupported: {environment!r}")
    return {
        "route_id": route_id, "mode": mode,
        "distance": _fraction(value["distance_to_exit_ft"], f"{label}.distance_to_exit_ft"),
        "compatible": _boolean(value["compatible"], f"{label}.compatible"),
        "multiplier": _fraction(value["movement_cost_multiplier"], f"{label}.movement_cost_multiplier", positive=True),
        "environment": environment,
    }


def area_response(
    convention: str, *, target_id: str, membership: bool, effect_active: bool,
    routes: Sequence[Mapping[str, Any]] | None = None, effective_speeds_ft: Mapping[str, int] | None = None,
    denied_modes: Iterable[str] = (), speed_zero: bool = False, prone: bool = False,
    while_in_area_component_ids: Sequence[str] = (), independent_component_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Resolve one caller-supplied legal area response opportunity."""

    if convention not in AREA_RESPONSE_CONVENTIONS:
        raise TimelineError(f"Unsupported area-response convention: {convention!r}")
    target_id = _identifier(target_id, "target_id")
    _boolean(membership, "membership");_boolean(effect_active, "effect_active");_boolean(speed_zero, "speed_zero");_boolean(prone, "prone")
    while_ids = [_identifier(item, "while_in_area_component_ids item") for item in while_in_area_component_ids]
    independent_ids = [_identifier(item, "independent_component_ids item") for item in independent_component_ids]
    if not membership:
        return {"convention": convention, "target_id": target_id, "membership_before": False, "membership_after": False, "exited": False, "selected_route": None, "ended_component_ids": [], "retained_component_ids": independent_ids, "events": [], "reason": "not_in_area"}
    if not effect_active:
        return {"convention": convention, "target_id": target_id, "membership_before": True, "membership_after": False, "exited": True, "selected_route": None, "ended_component_ids": while_ids, "retained_component_ids": independent_ids, "events": [{"kind": "exit", "owner": "target", "turn_anchor": "during_turn", "reason": "effect_end"}], "reason": "effect_ended"}
    if convention == "fixed_occupancy_v1":
        return {"convention": convention, "target_id": target_id, "membership_before": True, "membership_after": True, "exited": False, "selected_route": None, "ended_component_ids": [], "retained_component_ids": independent_ids, "events": [], "reason": "fixed_occupancy"}
    if routes is None or not isinstance(routes, Sequence) or isinstance(routes, (str, bytes)) or not routes:
        raise TimelineError("shortest_route_v1 requires at least one typed route")
    if effective_speeds_ft is None or not isinstance(effective_speeds_ft, Mapping):
        raise TimelineError("shortest_route_v1 requires effective movement-mode speeds")
    parsed = [_route(value, f"routes[{index}]") for index, value in enumerate(routes)]
    route_ids = [row["route_id"] for row in parsed]
    if len(route_ids) != len(set(route_ids)):
        raise TimelineError("routes contain duplicate route_id values")
    denied = set(denied_modes)
    if denied - set(MOVEMENT_MODES):
        raise TimelineError("denied_modes contains an unsupported movement mode")
    speeds: dict[str, int] = {}
    for mode, value in effective_speeds_ft.items():
        if mode not in MOVEMENT_MODES:
            raise TimelineError(f"effective_speeds_ft contains unsupported mode {mode!r}")
        speeds[mode] = _integer(value, f"effective_speeds_ft.{mode}")
    for row in parsed:
        if row["mode"] not in speeds:
            raise TimelineError(f"Missing effective speed for route mode {row['mode']!r}")

    candidates: list[tuple[int, Fraction, str, dict[str, Any], dict[str, Any]]] = []
    standing_options: list[tuple[int, str, dict[str, Any]]] = []
    for mode, speed in sorted(speeds.items()):
        response = prone_movement_response(
            target_id=target_id,
            prone=prone,
            current_speed_ft=0 if speed_zero or mode in denied else speed,
            movement_denied=mode in denied,
        )
        if response["stood"]:
            standing_options.append(
                (-response["remaining_movement_ft"], mode, response)
            )
    blocked_reasons: list[str] = []
    for row in parsed:
        speed = 0 if speed_zero or row["mode"] in denied else speeds[row["mode"]]
        response = prone_movement_response(target_id=target_id, prone=prone, current_speed_ft=speed, movement_denied=row["mode"] in denied)
        available = Fraction(response["remaining_movement_ft"])
        if not row["compatible"]:
            blocked_reasons.append(f"{row['route_id']}:incompatible")
            continue
        if available <= 0:
            blocked_reasons.append(f"{row['route_id']}:no_effective_speed")
            continue
        progress = available / row["multiplier"]
        if progress <= 0:
            blocked_reasons.append(f"{row['route_id']}:no_progress")
            continue
        remaining = max(Fraction(0), row["distance"] - progress)
        future_full_progress = Fraction(speed) / row["multiplier"]
        turns = 1 if remaining == 0 else 1 + (math.ceil(remaining / future_full_progress) if future_full_progress else 10**9)
        candidates.append((turns, remaining, row["route_id"], row, response))
    if not candidates:
        stand = min(standing_options) if standing_options else None
        stand_mode = stand[1] if stand is not None else None
        prone_response = stand[2] if stand is not None else None
        events = []
        if prone_response is not None:
            events.append({
                "kind": "stand",
                "owner": "target",
                "turn_anchor": "during_turn",
                "movement_mode": stand_mode,
                "standing_cost_ft": prone_response["standing_cost_ft"],
                "remaining_movement_ft": prone_response["remaining_movement_ft"],
            })
        result = {
            "convention": convention,
            "target_id": target_id,
            "membership_before": True,
            "membership_after": True,
            "exited": False,
            "selected_route": None,
            "ended_component_ids": [],
            "retained_component_ids": independent_ids,
            "events": events,
            "reason": "movement_unavailable",
            "blocked_routes": sorted(blocked_reasons),
            "prone_after": (
                prone_response["prone_after"]
                if prone_response is not None else prone
            ),
        }
        if prone_response is not None:
            result["prone_response"] = prone_response
        return result
    _, remaining, _, selected, prone_response = min(candidates, key=lambda item: (item[0], item[1], item[2]))
    distance = selected["distance"]
    progress = distance - remaining
    exited = remaining == 0
    route_record = {
        "route_id": selected["route_id"], "mode": selected["mode"], "environment": selected["environment"],
        "movement_cost_multiplier": _number(selected["multiplier"]), "movement_cost_multiplier_exact": _fraction_record(selected["multiplier"]),
        "distance_before_ft": _number(distance), "distance_before_exact": _fraction_record(distance),
        "progress_ft": _number(progress), "progress_exact": _fraction_record(progress),
        "remaining_distance_ft": _number(remaining), "remaining_distance_exact": _fraction_record(remaining),
        "prone_response": prone_response,
    }
    return {
        "convention": convention, "target_id": target_id, "membership_before": True,
        "membership_after": not exited, "exited": exited, "selected_route": route_record,
        "ended_component_ids": while_ids if exited else [], "retained_component_ids": independent_ids,
        "events": [{"kind": "exit", "owner": "target", "turn_anchor": "during_turn", "route_id": selected["route_id"]}] if exited else [],
        "reason": "shortest_legal_route", "prone_after": prone_response["prone_after"],
    }


def area_entry(
    *, target_id: str, turn_id: str, was_member: bool, is_member: bool,
    caused_by_area_movement: bool, moved_area_counts_as_entry: bool,
    frequency: str, prior_trigger_turn_ids: Iterable[str] = (),
) -> dict[str, Any]:
    target_id = _identifier(target_id, "target_id")
    turn_id = _identifier(turn_id, "turn_id")
    was_member = _boolean(was_member, "was_member")
    is_member = _boolean(is_member, "is_member")
    caused_by_area_movement = _boolean(caused_by_area_movement, "caused_by_area_movement")
    moved_area_counts_as_entry = _boolean(moved_area_counts_as_entry, "moved_area_counts_as_entry")
    if isinstance(prior_trigger_turn_ids, (str, bytes)):
        raise TimelineError("prior_trigger_turn_ids must be an iterable of identifiers")
    try:
        prior_items = list(prior_trigger_turn_ids)
    except TypeError as error:
        raise TimelineError("prior_trigger_turn_ids must be an iterable of identifiers") from error
    if frequency not in {"once_per_turn", "unlimited"}:
        raise TimelineError(f"Unsupported entry frequency: {frequency!r}")
    prior = {
        _identifier(item, f"prior_trigger_turn_ids[{index}]")
        for index, item in enumerate(prior_items)
    }
    transition = not was_member and is_member
    trigger = transition and (moved_area_counts_as_entry or not caused_by_area_movement)
    reason = "entry"
    if not transition:reason = "no_membership_transition"
    elif caused_by_area_movement and not moved_area_counts_as_entry:reason = "moved_area_does_not_count"
    elif frequency == "once_per_turn" and turn_id in prior:trigger = False;reason = "once_per_turn_already_triggered"
    updated = sorted(prior | ({turn_id} if trigger and frequency == "once_per_turn" else set()))
    return {"target_id": target_id, "turn_id": turn_id, "triggered": trigger, "reason": reason, "triggered_turn_ids": updated, "event": {"kind": "entry", "owner": "any_creature", "turn_anchor": "during_turn"} if trigger else None}


def repeat_save_survival(failure_probability: Any, repeat_count: int) -> dict[str, Any]:
    failure = _fraction(failure_probability, "failure_probability")
    if failure > 1:
        raise TimelineError("failure_probability must not exceed one")
    count = _integer(repeat_count, "repeat_count")
    survival = Fraction(1)
    records = []
    for index in range(1, count + 1):
        before = survival;survival *= failure
        records.append({"repeat_index": index, "active_before": _fraction_record(before), "save_failure_probability": _fraction_record(failure), "active_after": _fraction_record(survival)})
    return {"repeat_count": count, "survival_probability": _fraction_record(survival), "records": records}


def concentration_dc(damage: int | float) -> int:
    if isinstance(damage, bool) or not isinstance(damage, (int, float)) or not math.isfinite(damage) or damage < 0:
        raise TimelineError("damage must be a non-negative finite number")
    return min(30, max(10, math.floor(damage / 2)))


def _concentration_probabilities(dc: int, save_bonus: int, success_probability: Any | None, roll_kernel: Sequence[Mapping[str, Any]] | None) -> tuple[Fraction, dict[str, Any]]:
    if (success_probability is None) == (roll_kernel is None):
        raise TimelineError("Supply exactly one branch probability or exact roll kernel")
    if success_probability is not None:
        success = _fraction(success_probability, "success_probability")
        if success > 1:raise TimelineError("success_probability must not exceed one")
        return success, {"kind": "branch_probability", "success_probability": _fraction_record(success)}
    if not isinstance(roll_kernel, Sequence) or isinstance(roll_kernel, (str, bytes)) or not roll_kernel:
        raise TimelineError("roll_kernel must be a non-empty array")
    total = success = Fraction(0);rows = []
    seen_rolls: set[int] = set()
    for index, item in enumerate(roll_kernel):
        if not isinstance(item, Mapping) or set(item) != {"roll", "probability"}:
            raise TimelineError(f"roll_kernel[{index}] must contain exactly roll and probability")
        roll = _integer(item["roll"], f"roll_kernel[{index}].roll", 1)
        if roll > 20:
            raise TimelineError(f"roll_kernel[{index}].roll must be between 1 and 20")
        if roll in seen_rolls:
            raise TimelineError(f"roll_kernel contains duplicate roll {roll}")
        seen_rolls.add(roll)
        probability = _fraction(item["probability"], f"roll_kernel[{index}].probability")
        total += probability
        if roll + save_bonus >= dc:success += probability
        rows.append({"roll": roll, "probability": _fraction_record(probability)})
    if total != 1:raise TimelineError("roll_kernel probabilities must sum exactly to one")
    return success, {"kind": "exact_roll_kernel", "rows": rows}


class ConcentrationTracker:
    """One explicit controller concentration slot with an append-only audit record."""

    def __init__(self, *, save_bonus: int) -> None:
        self.save_bonus = _integer(save_bonus, "save_bonus", -10_000)
        self.active_effect_id: str | None = None
        self._active_metadata: dict[str, Any] = {}
        self.records: list[dict[str, Any]] = []

    def start(
        self, effect_id: str, *, event_id: str, startup_blood_tax: int = 0,
        concentration_component_ids: Sequence[str] = (), area_ids: Sequence[str] = (),
        fall_target_ids: Sequence[str] = (), maximum_duration: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        effect = _identifier(effect_id, "effect_id")
        event = _identifier(event_id, "event_id")
        tax = _integer(startup_blood_tax, "startup_blood_tax")
        component_ids = _identifier_list(concentration_component_ids, "concentration_component_ids")
        area_ids_record = _identifier_list(area_ids, "area_ids")
        fall_targets = _identifier_list(fall_target_ids, "fall_target_ids")
        if maximum_duration is not None and not isinstance(maximum_duration, Mapping):
            raise TimelineError("maximum_duration must be an object")
        maximum = (
            _json_value(dict(maximum_duration), "maximum_duration")
            if maximum_duration is not None
            else None
        )
        if self.active_effect_id is not None:
            self.end(reason="new_concentration_replacement", event_id=event)
        self.active_effect_id = effect
        self._active_metadata = {
            "concentration_component_ids": component_ids,
            "area_ids": area_ids_record,
            "fall_target_ids": fall_targets,
            "maximum_duration": maximum,
        }
        record = {"kind": "concentration_start", "event_id": event, "effect_id": effect, "startup_blood_tax": tax, "check_required": False, "reason": "startup_blood_tax_exemption" if tax else "activation"}
        self.records.append(record);return deepcopy(record)

    def check(
        self, *, amount: int | float, source: str, event_id: str, outcome: str,
        success_probability: Any | None = None, roll_kernel: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self.active_effect_id is None:raise TimelineError("No active concentration effect")
        if source not in {"damage", "later_blood_tax"}:raise TimelineError(f"Unsupported concentration-check source: {source!r}")
        if outcome not in {"success", "failure"}:raise TimelineError("outcome must be success or failure")
        dc = concentration_dc(amount)
        success, kernel = _concentration_probabilities(dc, self.save_bonus, success_probability, roll_kernel)
        selected_probability = success if outcome == "success" else 1 - success
        if selected_probability == 0:
            raise TimelineError(
                f"Selected concentration outcome {outcome!r} has zero probability"
            )
        record = {
            "kind": "concentration_check", "event_id": _identifier(event_id, "event_id"),
            "effect_id": self.active_effect_id, "source": source, "amount": amount, "dc": dc,
            "save_bonus": self.save_bonus, "success_probability": _fraction_record(success),
            "failure_probability": _fraction_record(1 - success), "kernel": kernel, "outcome": outcome,
        }
        self.records.append(record)
        if outcome == "failure":self.end(reason="failed_concentration_save", event_id=record["event_id"])
        return deepcopy(record)

    def end(self, *, reason: str, event_id: str) -> dict[str, Any]:
        if reason not in {"new_concentration_replacement", "voluntary_end", "duration_expiry", "controller_incapacitated", "controller_death", "failed_concentration_save"}:
            raise TimelineError(f"Unsupported concentration end reason: {reason!r}")
        event = _identifier(event_id, "event_id")
        if self.active_effect_id is None:
            record = {"kind": "concentration_end", "event_id": event, "effect_id": None, "reason": reason, "changed": False}
            self.records.append(record);return deepcopy(record)
        record = {
            "kind": "concentration_end", "event_id": event, "effect_id": self.active_effect_id,
            "reason": reason, "changed": True,
            "ended_component_ids": list(self._active_metadata["concentration_component_ids"]),
            "ended_area_ids": list(self._active_metadata["area_ids"]),
            "execute_concentration_end_gates": True,
            "fall_transitions": [
                {"target_id": target_id, "kind": "fall_transition", "origin": "current_position", "damage": None, "altitude_ft": None, "reason": "concentration_end"}
                for target_id in self._active_metadata["fall_target_ids"]
            ],
        }
        self.records.append(record);self.active_effect_id = None;self._active_metadata = {};return deepcopy(record)

    def to_dict(self) -> dict[str, Any]:
        return {"active_effect_id": self.active_effect_id, "save_bonus": self.save_bonus, "records": deepcopy(self.records)}


def airborne_fall_transition(
    *, target_id: str, airborne: bool, can_hover: bool, prone: bool = False,
    incapacitated: bool = False, fly_speed_ft: int | None = None,
    explicit_prevents_fall: bool = False, structured_fall: bool = False,
    source_component_id: str | None = None,
) -> dict[str, Any]:
    target_id = _identifier(target_id, "target_id")
    if source_component_id is not None:
        source_component_id = _identifier(source_component_id, "source_component_id")
    for value, label in ((airborne, "airborne"), (can_hover, "can_hover"), (prone, "prone"), (incapacitated, "incapacitated"), (explicit_prevents_fall, "explicit_prevents_fall"), (structured_fall, "structured_fall")):_boolean(value, label)
    if fly_speed_ft is not None:_integer(fly_speed_ft, "fly_speed_ft")
    trigger = structured_fall or prone or incapacitated or fly_speed_ft == 0
    prevented = not structured_fall and (can_hover or explicit_prevents_fall)
    falls = airborne and trigger and not prevented
    reason = "structured_fall" if structured_fall else "prone" if prone else "incapacitated" if incapacitated else "fly_speed_zero" if fly_speed_ft == 0 else "no_fall_trigger"
    if not airborne:reason = "not_airborne"
    elif prevented:reason = "hover_or_explicit_prevention"
    return {"target_id": target_id, "falls": falls, "reason": reason, "origin": "current_position" if falls else None, "damage": None, "altitude_ft": None, "source_component_id": source_component_id}


def displacement_function(function_id: str, distance_ft: float) -> float:
    if function_id not in DISPLACEMENT_FUNCTIONS:raise TimelineError(f"Unsupported displacement function: {function_id!r}")
    if isinstance(distance_ft, bool) or not isinstance(distance_ft, (int, float)) or not math.isfinite(distance_ft) or distance_ft < 0:raise TimelineError("distance_ft must be non-negative and finite")
    units = distance_ft / 5
    if function_id == "sqrt_5ft_v1":return math.sqrt(units)
    if function_id == "log2_5ft_v1":return math.log2(1 + units)
    return 0.0 if distance_ft == 0 else float(math.ceil(distance_ft / 10))


def vertical_displacement_vector(distance_ft: int | float, *, upward: bool = True) -> tuple[float, float, float]:
    if isinstance(distance_ft, bool) or not isinstance(distance_ft, (int, float)) or not math.isfinite(distance_ft) or distance_ft < 0:raise TimelineError("distance_ft must be non-negative and finite")
    return (0.0, 0.0, float(distance_ft) * (1 if upward else -1))


@dataclass
class _DisplacementState:
    epoch: int = 1
    net: tuple[float, float, float] = (0.0, 0.0, 0.0)
    maximum_ft: float = 0.0


class DisplacementEpochs:
    def __init__(self) -> None:
        self._states: dict[str, _DisplacementState] = {}
        self.records: list[dict[str, Any]] = []

    @staticmethod
    def _vector(value: Sequence[int | float]) -> tuple[float, float, float]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) not in {2, 3}:raise TimelineError("displacement vector must contain two or three numeric feet components")
        rows = []
        for index, part in enumerate(value):
            if isinstance(part, bool) or not isinstance(part, (int, float)) or not math.isfinite(part):raise TimelineError(f"displacement vector component {index} must be finite")
            rows.append(float(part))
        if len(rows) == 2:rows.append(0.0)
        return rows[0], rows[1], rows[2]

    def apply(self, *, target_id: str, vector_ft: Sequence[int | float], source_component_id: str) -> dict[str, Any]:
        target = _identifier(target_id, "target_id");source = _identifier(source_component_id, "source_component_id");vector = self._vector(vector_ft)
        state = self._states.setdefault(target, _DisplacementState())
        net = tuple(left + right for left, right in zip(state.net, vector, strict=True));raw_net = math.sqrt(sum(part * part for part in net));previous = state.maximum_ft;new = max(previous, raw_net)
        increments = {function_id: displacement_function(function_id, new) - displacement_function(function_id, previous) for function_id in DISPLACEMENT_FUNCTIONS}
        record = {"kind": "forced_displacement", "target_id": target, "epoch": state.epoch, "raw_vector_ft": list(vector), "net_vector_ft": list(net), "raw_net_feet": raw_net, "previous_epoch_maximum_feet": previous, "new_epoch_maximum_feet": new, "functions": [{"function_id": function_id, "version": "1.0.0", "incremental_value": increments[function_id]} for function_id in DISPLACEMENT_FUNCTIONS], "source_component_id": source}
        state.net = net;state.maximum_ft = new;self.records.append(record);return deepcopy(record)

    def self_movement_opportunity(self, *, target_id: str, legal: bool, speed_zero: bool = False, movement_denied: bool = False) -> dict[str, Any]:
        target = _identifier(target_id, "target_id");_boolean(legal, "legal");_boolean(speed_zero, "speed_zero");_boolean(movement_denied, "movement_denied")
        state = self._states.setdefault(target, _DisplacementState());reset = legal and not speed_zero and not movement_denied
        previous_epoch = state.epoch
        if reset:state.epoch += 1;state.net = (0.0, 0.0, 0.0);state.maximum_ft = 0.0
        record = {"kind": "displacement_epoch_boundary", "target_id": target, "previous_epoch": previous_epoch, "new_epoch": state.epoch, "reset": reset, "reason": "legal_self_movement_response" if reset else "speed_zero" if speed_zero else "movement_denied" if movement_denied else "no_legal_response"}
        self.records.append(record);return deepcopy(record)

    def to_dict(self) -> dict[str, Any]:
        return {"records": deepcopy(self.records), "states": {target: {"epoch": state.epoch, "net_vector_ft": list(state.net), "maximum_feet": state.maximum_ft} for target, state in sorted(self._states.items())}}

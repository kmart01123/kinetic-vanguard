from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from harness.authority import AuthorityError, load_control_projection_v2, validate_control_projection_v2
from harness.control_targets import DEFAULT_CONTROL_PROVENANCE, DEFAULT_CONTROL_SUPPLEMENT, load_control_targets


CORPUS_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "control-authority-v2-parity.json"
)


def _decode_special_numbers(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_special_numbers(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"special_number"}:
            return {
                "nan": float("nan"),
                "positive_infinity": float("inf"),
                "negative_infinity": float("-inf"),
            }[value["special_number"]]
        return {key: _decode_special_numbers(item) for key, item in value.items()}
    return value


def _resolve_target(authority: dict[str, Any], descriptor: dict[str, Any]) -> Any:
    kind = descriptor["kind"]
    if kind == "authority":
        return authority
    if kind == "model":
        matches = [
            row["model"]
            for row in authority["ledger"]
            if row.get("disposition") == "modeled"
            and row.get("model", {}).get("effect_id") == descriptor["effect_id"]
        ]
    elif kind == "mastery":
        matches = [
            mastery
            for mastery in authority["masteries"]
            if mastery.get("mastery_id") == descriptor["mastery_id"]
        ]
    else:
        raise AssertionError(f"Unsupported parity target kind: {kind!r}")
    if len(matches) != 1:
        raise AssertionError(f"Parity target must resolve exactly once: {descriptor!r}")
    return matches[0]


def _resolve_path(target: Any, path: list[str | int]) -> Any:
    current = target
    for segment in path:
        current = current[segment]
    return current


def _assign(container: Any, key: str | int, value: Any) -> None:
    container[key] = value


def _apply_operation(target: Any, operation: dict[str, Any]) -> None:
    op = operation["op"]
    path = operation["path"]
    if op in {"set", "delete"}:
        if not path:
            raise AssertionError(f"{op} requires a nonempty path")
        parent = _resolve_path(target, path[:-1])
        key = path[-1]
        if op == "set":
            _assign(parent, key, _decode_special_numbers(operation["value"]))
        elif isinstance(parent, list):
            parent.pop(key)
        else:
            del parent[key]
        return
    destination = _resolve_path(target, path)
    if not isinstance(destination, list):
        raise AssertionError(f"{op} path must resolve to an array")
    if op == "append":
        destination.append(_decode_special_numbers(operation["value"]))
    elif op == "remove_index":
        destination.pop(operation["index"])
    elif op == "reverse":
        destination.reverse()
    else:
        raise AssertionError(f"Unsupported parity operation: {op!r}")


class ControlAuthorityV2ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projection = load_control_projection_v2()
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        cls.supplement = json.loads(DEFAULT_CONTROL_SUPPLEMENT.read_text(encoding="utf-8"))
        cls.provenance = json.loads(DEFAULT_CONTROL_PROVENANCE.read_text(encoding="utf-8"))
        if cls.corpus.get("version") != 1 or not isinstance(cls.corpus.get("cases"), list):
            raise AssertionError("Control-authority parity corpus must use version 1 with a cases array")

    def test_shared_typescript_python_mutation_corpus(self) -> None:
        for case in self.corpus["cases"]:
            with self.subTest(case=case["id"]):
                if case["target"]["kind"] == "control_targets":
                    wrapper = {"supplement": deepcopy(self.supplement), "provenance": deepcopy(self.provenance)}
                    for operation in case["operations"]:
                        _apply_operation(wrapper, operation)
                    try:
                        with tempfile.TemporaryDirectory() as directory:
                            temporary = Path(directory)
                            supplement_path = DEFAULT_CONTROL_SUPPLEMENT
                            provenance_path = DEFAULT_CONTROL_PROVENANCE
                            if wrapper["supplement"] != self.supplement:
                                supplement_path = temporary / "srd_control_targets.json"
                                supplement_path.write_text(json.dumps(wrapper["supplement"]), encoding="utf-8")
                            if wrapper["provenance"] != self.provenance:
                                provenance_path = temporary / "srd-control-targets.json"
                                provenance_path.write_text(json.dumps(wrapper["provenance"]), encoding="utf-8")
                            load_control_targets(
                                supplement_path=supplement_path,
                                provenance_path=provenance_path,
                            )
                    except ValueError:
                        actual_valid = False
                    else:
                        actual_valid = True
                    self.assertEqual(
                        actual_valid,
                        case["expected_valid"],
                        f"Python control-target acceptance diverged for shared parity case {case['id']!r}",
                    )
                    continue
                projection = deepcopy(self.projection)
                target = _resolve_target(projection["control_authority"], case["target"])
                for operation in case["operations"]:
                    _apply_operation(target, operation)
                try:
                    validate_control_projection_v2(projection)
                except AuthorityError:
                    actual_valid = False
                else:
                    actual_valid = True
                self.assertEqual(
                    actual_valid,
                    case["expected_valid"],
                    f"Python acceptance diverged for shared parity case {case['id']!r}",
                )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock

from tools import check_toolchain_versions


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FILES = (
    "package.json",
    ".devcontainer/devcontainer.json",
    ".devcontainer/post-create.sh",
    ".github/workflows/ci.yml",
    ".github/workflows/prototype-pages.yml",
)


class CheckToolchainVersionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for relative_path in REQUIRED_FILES:
            source = ROOT / relative_path
            destination = self.root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_check(self) -> str:
        output = io.StringIO()
        with mock.patch.object(check_toolchain_versions, "ROOT", self.root):
            with redirect_stdout(output):
                check_toolchain_versions.main()
        return output.getvalue()

    def mutate_pages(self, old: str, new: str) -> None:
        path = self.root / ".github/workflows/prototype-pages.yml"
        source = path.read_text(encoding="utf-8")
        self.assertEqual(source.count(old), 1)
        path.write_text(source.replace(old, new), encoding="utf-8")

    def expected_versions(self) -> tuple[str, str]:
        package = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
        return package["engines"]["node"], package["packageManager"].removeprefix("npm@")

    def drifted_patch_version(self, version: str) -> str:
        major, minor, patch = version.split(".")
        return f"{major}.{minor}.{int(patch) + 1}"

    def test_current_pages_node_and_npm_versions_pass(self) -> None:
        self.assertIn("toolchain versions consistent", self.run_check())

    def test_pages_node_drift_fails_with_pages_declaration(self) -> None:
        expected_node, _ = self.expected_versions()
        drifted_node = self.drifted_patch_version(expected_node)
        self.mutate_pages(
            f"node-version: {expected_node}", f"node-version: {drifted_node}"
        )

        with self.assertRaisesRegex(
            SystemExit,
            re.escape(
                f"prototype Pages Node: expected {expected_node}, found {drifted_node}"
            ),
        ):
            self.run_check()

    def test_pages_npm_drift_fails_with_pages_declaration(self) -> None:
        _, expected_npm = self.expected_versions()
        drifted_npm = self.drifted_patch_version(expected_npm)
        self.mutate_pages(f"npm@{expected_npm}", f"npm@{drifted_npm}")

        with self.assertRaisesRegex(
            SystemExit,
            re.escape(
                f"prototype Pages npm: expected {expected_npm}, found {drifted_npm}"
            ),
        ):
            self.run_check()


if __name__ == "__main__":
    unittest.main()

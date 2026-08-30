#!/usr/bin/env python
"""Installing the method into a project that already exists.

The greenfield path is covered by every other suite, because the template *is*
a fresh project. This covers the other one: a repository with its own README,
licence, changelog, CI, agent instructions, and code, which must survive
adoption unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

TEMPLATE = Path(__file__).resolve().parents[2]
INSTALLER = TEMPLATE / "scripts/install.py"

SPEC = importlib.util.spec_from_file_location("install_under_test", INSTALLER)
assert SPEC is not None and SPEC.loader is not None
install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install)
roach = install.ROACH


def remove_tree(path: Path) -> None:
    def clear_readonly(func, target, _exc):  # type: ignore[no-untyped-def]
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onexc=clear_readonly)


class ExistingProject(unittest.TestCase):
    """A repository that predates Roach and has its own opinions."""

    OWN_FILES: ClassVar[dict[str, str]] = {
        "README.md": "# WidgetShop\n\nAn online widget store. Started 2024.\n",
        "LICENSE": "Copyright (c) 2024 Someone Else. All rights reserved.\n",
        "CHANGELOG.md": "# Changelog\n\n## 1.4.0\n- Added checkout\n",
        "AGENTS.md": "# Agent notes\n\nAlways run `npm test`.\nNever touch src/legacy_billing.js.\n",
        ".gitignore": "node_modules/\ndist/\n",
        "package.json": '{"name":"widgetshop","version":"1.4.0"}\n',
        "src/checkout.js": 'export const checkout = () => "ok";\n',
        "src/legacy_billing.js": 'export const legacyBilling = () => "keep";\n',
        ".github/workflows/ci.yml": "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo build\n",
    }

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.project = self.dir / "widgetshop"
        self.project.mkdir()
        for rel, text in self.OWN_FILES.items():
            path = self.project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@t.t")
        self.git("config", "user.name", "t")
        self.git("config", "core.autocrlf", "false")
        self.git("add", "-A")
        self.git("commit", "-qm", "existing project")

    def tearDown(self) -> None:
        remove_tree(self.dir)

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.project, text=True, capture_output=True)

    def run_installer(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), "--into", str(self.project), *args],
            text=True, capture_output=True,
        )

    def roach(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/roach.py", *args],
            cwd=self.project, text=True, capture_output=True,
        )

    def read(self, rel: str) -> str:
        return (self.project / rel).read_text(encoding="utf-8")

    # ---- the promise ------------------------------------------------------

    def test_check_writes_nothing(self) -> None:
        before = self.git("status", "--porcelain").stdout
        result = self.run_installer("--check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Nothing was written", result.stdout)
        self.assertEqual(before, self.git("status", "--porcelain").stdout)

    def test_the_project_s_own_files_are_never_written(self) -> None:
        """The whole reason this is safe to run."""
        self.assertEqual(0, self.run_installer().returncode)
        for rel in ("README.md", "LICENSE", "CHANGELOG.md", "package.json",
                    "src/checkout.js", "src/legacy_billing.js", ".github/workflows/ci.yml"):
            self.assertEqual(self.OWN_FILES[rel], self.read(rel), f"{rel} was modified")

    def test_existing_agent_instructions_survive(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        agents = self.read("AGENTS.md")
        self.assertIn("Never touch src/legacy_billing.js", agents,
                      "a deliberate instruction must not be deleted by adoption")
        self.assertIn(roach.MANAGED_BEGIN, agents)
        self.assertIn("Roach Method Agent Contract", agents)

    def test_brownfield_is_detected_and_recorded(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        adoption = json.loads(self.read(".agent/STATE.json"))["adoption"]
        self.assertEqual("brownfield", adoption["mode"])
        self.assertTrue(adoption["baseline_commit"],
                        "a worker must be able to tell which history predates the method")

    def test_the_first_task_asks_what_this_already_is(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        task = json.loads(self.read(".agent/tasks/T000.json"))
        self.assertEqual("discovery", task["kind"])
        self.assertIn("repo-read", task["requires"], "recovering intent means reading the code")
        self.assertIn("existing", task["title"].lower())

    def test_installed_state_passes_check(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        result = self.roach("check")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_gitignore_is_appended_not_replaced(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        ignored = self.read(".gitignore")
        self.assertIn("node_modules/", ignored, "their entries must survive")
        self.assertIn(".roach-reconcile/", ignored)

    def test_their_ci_is_left_alone_and_roach_ci_added_beside_it(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        self.assertEqual(self.OWN_FILES[".github/workflows/ci.yml"],
                         self.read(".github/workflows/ci.yml"))
        added = self.read(".github/workflows/roach-check.yml")
        self.assertNotIn("run_template_tests", added,
                         "a project must not be made to run the method's own test suite")

    def test_no_workflow_is_added_where_actions_are_not_used(self) -> None:
        remove_tree(self.project / ".github")
        self.assertEqual(0, self.run_installer().returncode)
        self.assertFalse((self.project / ".github/workflows/roach-check.yml").exists(),
                         "adding CI uninvited spends somebody else's build minutes")

    def test_vercel_protection_is_opt_in(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        self.assertFalse((self.project / "vercel.json").exists())
        remove_tree(self.project / ".agent")
        self.assertEqual(0, self.run_installer("--with-vercel").returncode)
        self.assertTrue((self.project / "vercel.json").exists())

    def test_reinstalling_over_project_state_is_refused(self) -> None:
        self.assertEqual(0, self.run_installer().returncode)
        again = self.run_installer()
        self.assertNotEqual(0, again.returncode)
        self.assertIn("upgrade", again.stdout + again.stderr,
                      "the refusal must name the command that does what they meant")

    def test_upgrade_keeps_project_text_and_replaces_only_the_block(self) -> None:
        """The failure this is here to prevent ate a real instruction once."""
        self.assertEqual(0, self.run_installer().returncode)
        self.git("add", "-A")
        self.git("commit", "-qm", "adopt roach")

        upstream = self.dir / "template"
        shutil.copytree(TEMPLATE, upstream, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.pyc", ".roach-reconcile"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=upstream, check=True)
        for args in (("config", "user.email", "t@t.t"), ("config", "user.name", "t"),
                     ("config", "core.autocrlf", "false")):
            subprocess.run(["git", *args], cwd=upstream, check=True)
        agents = upstream / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8") + "\nUPSTREAM-CHANGE\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=upstream, check=True)
        subprocess.run(["git", "commit", "-qm", "upstream"], cwd=upstream, check=True)

        result = self.roach("upgrade", "--source", str(upstream))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        merged = self.read("AGENTS.md")
        self.assertIn("Never touch src/legacy_billing.js", merged,
                      "upgrade must not delete instructions the project wrote")
        self.assertIn("UPSTREAM-CHANGE", merged, "the upstream change must still arrive")
        self.assertEqual(1, merged.count(roach.MANAGED_BEGIN),
                         "repeated upgrades must not stack duplicate blocks")


class GreenfieldStillWorks(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.project = self.dir / "fresh"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.project, check=True)

    def tearDown(self) -> None:
        remove_tree(self.dir)

    def test_an_empty_repository_is_greenfield(self) -> None:
        result = subprocess.run(
            [sys.executable, str(INSTALLER), "--into", str(self.project)],
            text=True, capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("mode: greenfield", result.stdout)
        state = json.loads((self.project / ".agent/STATE.json").read_text(encoding="utf-8"))
        self.assertEqual("greenfield", state["adoption"]["mode"])
        task = json.loads((self.project / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        self.assertEqual("Define product with owner", task["title"],
                         "a new project is still asked what it should be")


class InstallerAndUpgradeAgree(unittest.TestCase):
    """Anything the installer puts in a project must be upgradeable later.

    The two lists live in different files for good reasons -- the installer also
    seeds project state, the upgrader must never touch it -- but a file that one
    knows about and the other does not is frozen at its install-time version
    forever, with nothing to say so.
    """

    def test_everything_installed_can_be_upgraded(self) -> None:
        orphans = sorted(set(install.TEMPLATE_OWNED) - set(roach.TEMPLATE_OWNED))
        self.assertEqual([], orphans, "installed but never upgraded")

    def test_merged_files_agree(self) -> None:
        self.assertEqual(tuple(install.MERGED), tuple(roach.TEMPLATE_MERGED))

    def test_project_state_is_never_upgraded(self) -> None:
        overlap = sorted(set(install.PROJECT_STATE) & set(roach.TEMPLATE_OWNED))
        self.assertEqual([], overlap, "an upgrade would overwrite the project's own thinking")

    def test_every_installed_file_exists_in_the_template(self) -> None:
        missing = [rel for rel in install.TEMPLATE_OWNED + install.PROJECT_STATE
                   if not (TEMPLATE / rel).exists()]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python
"""Behavioural tests for adopt, integrate, doctor, migrate, and product validation.

These use a real git repository but no remote, so they cover the local half of
each command: stale claims, merges that fail verification, and state validation.
Anything involving `origin` -- publishing, shared claims, divergence diagnosis --
lives in test_roach_remote.py, which builds a real remote and two clones.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import types
import unittest
from datetime import timedelta
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2]


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.mkdtemp()
        self.root = Path(self.dir) / "project"
        self.root.mkdir()
        for rel in (".agent", "scripts"):
            shutil.copytree(TEMPLATE / rel, self.root / rel)
        shutil.rmtree(self.root / ".agent" / "tests", ignore_errors=True)
        for name in ("AGENTS.md", "CLAUDE.md", "vercel.json"):
            if (TEMPLATE / name).exists():
                shutil.copy2(TEMPLATE / name, self.root / name)
        (self.root / ".agents/skills/project-continuity").mkdir(parents=True)
        (self.root / ".agents/skills/project-continuity/SKILL.md").write_text("x", encoding="utf-8")
        (self.root / ".claude/skills/project-continuity").mkdir(parents=True)
        (self.root / ".claude/skills/project-continuity/SKILL.md").write_text("x", encoding="utf-8")
        (self.root / "app.txt").write_text("v1\n", encoding="utf-8")

        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@t.t")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "initial")

        self.roach = self.load_roach()

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def load_roach(self):
        spec = importlib.util.spec_from_file_location(
            f"roach_{id(self)}", self.root / "scripts" / "roach.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def ns(self, **kwargs):
        return types.SimpleNamespace(**kwargs)

    def claim_t000(self, who: str = "worker-one"):
        self.roach.cmd_claim(self.ns(
            task="T000", cap=["repo-write", "user-dialogue"], worker=who,
            lease_minutes=120, branch=None, publish=False,
        ))

    def expire_claim(self, task_id: str = "T000") -> None:
        path = self.root / ".agent" / "tasks" / f"{task_id}.json"
        task = json.loads(path.read_text(encoding="utf-8"))
        past = self.roach.iso(self.roach.now() - timedelta(hours=9))
        task["claim"]["lease_expires_at"] = past
        task["claim"]["claimed_at"] = past
        path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")

    # ---- adopt -------------------------------------------------------------

    def test_adopt_refuses_while_claim_is_live(self) -> None:
        self.claim_t000("worker-one")
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_adopt(self.ns(
                task="T000", worker="worker-two", lease_minutes=120, branch=None, publish=False,
            ))
        self.assertIn("still live", str(ctx.exception))

    def test_adopt_takes_over_a_stale_claim_and_records_predecessor(self) -> None:
        self.claim_t000("worker-one")
        self.expire_claim()
        self.roach.cmd_adopt(self.ns(
            task="T000", worker="worker-two", lease_minutes=120, branch=None, publish=False,
        ))
        task = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        self.assertEqual("worker-two", task["claim"]["worker"])
        self.assertEqual("worker-one", task["claim"]["adopted_from"])
        self.assertEqual("roach/T000-worker-two", task["claim"]["branch"])

    def test_adopt_refuses_an_unclaimed_task(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_adopt(self.ns(
                task="T000", worker="worker-two", lease_minutes=120, branch=None, publish=False,
            ))
        self.assertIn("not claimed", str(ctx.exception))

    def test_claim_routes_stale_ownership_through_adopt(self) -> None:
        self.claim_t000("worker-one")
        self.expire_claim()
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_claim(self.ns(
                task="T000", cap=["repo-write", "user-dialogue"], worker="worker-two",
                lease_minutes=120, branch=None, publish=False,
            ))
        self.assertIn("use `roach.py adopt T000", str(ctx.exception))

    # ---- integrate ---------------------------------------------------------

    def prepare_branch(self, content: str) -> None:
        self.claim_t000("worker-one")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "claim")
        git(self.root, "checkout", "-q", "-b", "roach/T000-worker-one")
        (self.root / "app.txt").write_text(content, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "work")
        git(self.root, "checkout", "-q", "main")

    def set_verify(self, command: str) -> None:
        path = self.root / ".agent" / "VERIFY.json"
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["commands"]["full"] = command
        cfg["required_level"] = "full"
        path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "verify config")

    def test_integrate_rolls_back_when_verification_fails(self) -> None:
        self.set_verify("exit 1")
        self.prepare_branch("broken\n")
        before = git(self.root, "rev-parse", "HEAD").stdout.strip()
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_integrate(self.ns(
                task="T000", worker="worker-one", branch=None, level="full", push=False,
            ))
        self.assertIn("rolled back", str(ctx.exception))
        self.assertEqual(before, git(self.root, "rev-parse", "HEAD").stdout.strip())
        self.assertEqual("v1\n", (self.root / "app.txt").read_text(encoding="utf-8"))

    def test_integrate_keeps_merge_when_verification_passes(self) -> None:
        self.set_verify("exit 0")
        self.prepare_branch("v2\n")
        before = git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.roach.cmd_integrate(self.ns(
            task="T000", worker="worker-one", branch=None, level="full", push=False,
        ))
        self.assertNotEqual(before, git(self.root, "rev-parse", "HEAD").stdout.strip())
        self.assertEqual("v2\n", (self.root / "app.txt").read_text(encoding="utf-8"))

    def test_integrate_refuses_a_dirty_tree(self) -> None:
        self.set_verify("exit 0")
        self.prepare_branch("v2\n")
        (self.root / "stray.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_integrate(self.ns(
                task="T000", worker="worker-one", branch=None, level="full", push=False,
            ))
        self.assertIn("clean working tree", str(ctx.exception))

    def test_integrate_requires_ownership(self) -> None:
        self.set_verify("exit 0")
        self.prepare_branch("v2\n")
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_integrate(self.ns(
                task="T000", worker="someone-else", branch=None, level="full", push=False,
            ))
        self.assertIn("not owned", str(ctx.exception))

    # ---- completion gate ---------------------------------------------------

    def write_verification(self, commit: str) -> None:
        verify_path = self.root / ".agent" / "VERIFY.json"
        verify = json.loads(verify_path.read_text(encoding="utf-8"))
        required = verify.get("required_level", "full")
        verify["commands"][required] = "true"
        verify_path.write_text(json.dumps(verify, indent=2) + "\n", encoding="utf-8")
        state_path = self.root / ".agent" / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["verification"] = {
            "status": "passed", "level": required, "command": "true",
            "notes": "exit 0", "verified_at": self.roach.iso(), "commit": commit,
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def test_verification_on_an_old_commit_does_not_satisfy_completion(self) -> None:
        self.write_verification("0" * 40)
        errors = self.roach.completion_errors()
        self.assertTrue(
            any("re-run verification against current code" in e for e in errors),
            f"expected stale-commit error, got: {errors}",
        )

    def test_verification_on_the_current_commit_satisfies_the_gate(self) -> None:
        self.write_verification(git(self.root, "rev-parse", "HEAD").stdout.strip())
        errors = self.roach.completion_errors()
        self.assertFalse(
            any("verification" in e for e in errors),
            f"verification should be satisfied, got: {errors}",
        )

    def test_changed_verification_command_requires_a_fresh_pass(self) -> None:
        self.write_verification(git(self.root, "rev-parse", "HEAD").stdout.strip())
        verify_path = self.root / ".agent" / "VERIFY.json"
        verify = json.loads(verify_path.read_text(encoding="utf-8"))
        verify["commands"][verify["required_level"]] = "python -m unittest"
        verify_path.write_text(json.dumps(verify, indent=2) + "\n", encoding="utf-8")

        errors = self.roach.completion_errors()

        self.assertTrue(any("command changed" in error for error in errors), errors)
        findings = self.roach.doctor_findings()
        self.assertTrue(any("command changed" in problem for problem, _ in findings), findings)

    # ---- task creation ----------------------------------------------------

    def test_create_requires_acceptance_criteria_before_writing_a_task(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_create(self.ns(
                id=None, title="A vague task", kind="implementation", priority="normal",
                area=None, depends_on=None, requirement=None, requires=None, prefers=None,
                acceptance=None, publish=False,
            ))
        self.assertIn("acceptance", str(ctx.exception))
        self.assertFalse((self.root / ".agent/tasks/T001.json").exists())

    def test_create_rejects_unknown_requirement_before_writing_a_task(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.roach.cmd_create(self.ns(
                id=None, title="Build an unapproved feature", kind="implementation",
                priority="normal", area=None, depends_on=None, requirement=["FR-999"],
                requires=["repo-write"], prefers=None, acceptance=["feature works"],
                publish=False,
            ))
        self.assertIn("Unknown or invalid active requirements", str(ctx.exception))
        self.assertFalse((self.root / ".agent/tasks/T001.json").exists())

    # ---- deployment protection --------------------------------------------

    def test_check_flags_deployment_protection_that_was_unwired(self) -> None:
        (self.root / "vercel.json").write_text(
            json.dumps({"buildCommand": "npm run build"}) + "\n", encoding="utf-8"
        )
        problems = [p for p, _ in self.roach.deployment_findings()]
        self.assertTrue(any("no longer runs" in p for p in problems), problems)

    def test_intact_deployment_protection_is_silent(self) -> None:
        self.assertEqual([], self.roach.deployment_findings())

    # ---- doctor / migrate --------------------------------------------------

    def test_doctor_reports_a_stale_claim_with_an_actionable_fix(self) -> None:
        self.claim_t000("worker-one")
        self.expire_claim()
        findings = self.roach.doctor_findings()
        self.assertTrue(any("stale claim" in p for p, _ in findings), findings)
        self.assertTrue(any("adopt T000" in f for _, f in findings), findings)

    def test_migrate_upgrades_an_older_protocol_version(self) -> None:
        state_path = self.root / ".agent" / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["protocol_version"] = "0.3"
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        self.roach.cmd_migrate(self.ns())
        updated = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(self.roach.PROTOCOL_VERSION, updated["protocol_version"])

    # ---- product substance -------------------------------------------------

    def write_product(self, section_body: str) -> None:
        sections = [
            "Vision", "Goals", "Non-Goals", "Users / Audience", "Core Experience",
            "Requirements", "Constraints", "Success Criteria", "Open Questions",
        ]
        parts = ["# Product", "", "Status: DRAFT", ""]
        for name in sections:
            parts.append(f"## {name}")
            parts.append("")
            if name == "Requirements":
                parts.append("- **FR-001**: The product MUST do the thing it exists to do.")
            else:
                parts.append(section_body)
            parts.append("")
        (self.root / ".agent" / "PRODUCT.md").write_text("\n".join(parts), encoding="utf-8")
        (self.root / ".agent" / "PROJECT.md").write_text(
            "# Project\n\n## Summary\n\nA real summary of the project.\n", encoding="utf-8"
        )

    def test_filler_sections_do_not_pass_product_validation(self) -> None:
        self.write_product("TBD")
        errors = self.roach.product_structure_errors()
        self.assertTrue(any("filler" in e for e in errors), errors)

    def test_one_word_sections_do_not_pass_product_validation(self) -> None:
        self.write_product("Stuff.")
        errors = self.roach.product_structure_errors()
        self.assertTrue(any("characters of content" in e for e in errors), errors)

    def test_terse_but_real_sections_are_accepted(self) -> None:
        self.write_product("Solo note-takers who work offline on one laptop.")
        errors = self.roach.product_structure_errors()
        self.assertEqual(
            [], [e for e in errors if "filler" in e or "characters of content" in e], errors
        )

    # ---- worker identity ---------------------------------------------------

    def test_over_long_worker_ids_are_rejected_not_truncated(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.roach.worker("w" * 60)
        self.assertIn("too long", str(ctx.exception))
        self.assertEqual("short-id", self.roach.worker("short-id"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

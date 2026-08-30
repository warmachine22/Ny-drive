from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("roach_under_test", REPO / "scripts" / "roach.py")
roach = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(roach)


def configure_root(path: Path) -> None:
    roach.ROOT = path
    roach.AGENT = path / ".agent"
    roach.TASKS = roach.AGENT / "tasks"
    roach.STATE_PATH = roach.AGENT / "STATE.json"
    roach.VERIFY_PATH = roach.AGENT / "VERIFY.json"
    roach.PRODUCT_PATH = roach.AGENT / "PRODUCT.md"
    roach.PROJECT_PATH = roach.AGENT / "PROJECT.md"
    roach.PLAN_PATH = roach.AGENT / "PLAN.md"


VALID_PRODUCT = """# Product

Status: DRAFT — DISCOVERY IN PROGRESS

## Vision
A local tool that helps one person save and recover notes reliably.

## Goals
- Make saving obvious and dependable.

## Non-Goals
- No collaboration in the first version.

## Users / Audience
A single desktop user.

## Core Experience
Create a note, save it, close the app, and recover it later.

## Requirements
- **FR-001**: The user MUST be able to create and save a note.
- **FR-002**: The user MUST be able to reopen a saved note.
- **QR-001**: Saving a local note MUST complete within one second under normal use.

## Constraints
The first version is local-first and offline.

## Success Criteria
A user can complete the core create-save-reopen flow without losing data.

## Open Questions
None that block planning.

## Future / Possibilities
Cloud sync may be considered later.
"""

READY_PLAN = """# Plan

Status: READY

## Technical Approach
Use Python with a small local desktop UI and JSON-backed persistence because the product is local-first.

## Architecture / Components
Separate note domain logic, persistence, and UI so saving/reopening can be tested independently.

## Project Structure
Keep application code under src/, application tests under app_tests/, and data access behind a repository module.

## Dependencies / Integrations
Prefer the standard library where practical; no network integrations are required for the first version.

## Verification Strategy
Quick runs focused unit tests, full runs all application tests, and smoke exercises the create-save-reopen flow.

## Risks / Unknowns
File corruption and atomic-write behavior are the main risks and will be addressed in persistence tasks.

## Requirement Coverage
Implementation and verification tasks cover FR-001, FR-002, and QR-001 explicitly.
"""


class TempProject(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        configure_root(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()
        configure_root(REPO)

    def copy_template_core(self) -> None:
        for rel in [
            "AGENTS.md",
            "CLAUDE.md",
            ".agent/PROJECT.md",
            ".agent/PRODUCT.md",
            ".agent/STATE.json",
            ".agent/VERIFY.json",
            ".agent/tasks/README.md",
            ".agent/tasks/T000.json",
            ".agents/skills/project-continuity/SKILL.md",
            ".claude/skills/project-continuity/SKILL.md",
        ]:
            src = REPO / rel
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def write_json(self, rel: str, value: dict) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def write_valid_product(self) -> None:
        (self.root / ".agent/PRODUCT.md").write_text(VALID_PRODUCT, encoding="utf-8")
        (self.root / ".agent/PROJECT.md").write_text(
            "# Project\n\n## Summary\n\nA local note tool focused on reliable save/reopen.\n",
            encoding="utf-8",
        )

    def claim_t000(self, worker: str = "agent-discovery") -> None:
        roach.cmd_claim(
            types.SimpleNamespace(
                task="T000",
                cap=["repo-write", "user-dialogue"],
                worker=worker,
                lease_minutes=120,
                branch=None,
                publish=False,
            )
        )

    def accept_product(self, worker: str = "agent-discovery") -> None:
        self.write_valid_product()
        self.claim_t000(worker)
        roach.cmd_transition(types.SimpleNamespace(phase="discovery", allow_live_work=False))
        roach.cmd_accept_product(
            types.SimpleNamespace(worker=worker, verification="owner confirmed product intent")
        )

    def make_ready_for_execution(self) -> None:
        self.accept_product()
        (self.root / ".agent/PLAN.md").write_text(READY_PLAN, encoding="utf-8")
        self.write_json(
            ".agent/VERIFY.json",
            {
                "version": 1,
                "required_level": "quick",
                "commands": {"quick": "true", "full": None, "smoke": None},
                "notes": "test",
            },
        )
        roach.cmd_claim(
            types.SimpleNamespace(
                task="T001",
                cap=["repo-write"],
                worker="agent-plan",
                lease_minutes=120,
                branch=None,
                publish=False,
            )
        )
        roach.cmd_create(
            types.SimpleNamespace(
                id=None,
                title="Implement save/reopen",
                kind="implementation",
                priority="high",
                area=["persistence"],
                depends_on=["T001"],
                requirement=["FR-001", "FR-002", "QR-001"],
                requires=["repo-write"],
                prefers=["shell"],
                acceptance=["save and reopen work"],
                publish=False,
            )
        )
        roach.cmd_finish(
            types.SimpleNamespace(
                task="T001",
                worker="agent-plan",
                verification="plan and backlog complete",
                publish=False,
            )
        )

    def complete_project(self) -> None:
        self.make_ready_for_execution()
        roach.cmd_transition(types.SimpleNamespace(phase="execution", allow_live_work=False, publish=False))
        roach.cmd_claim(
            types.SimpleNamespace(
                task="T002", cap=["repo-write"], worker="agent-build",
                lease_minutes=120, branch=None, publish=False,
            )
        )
        roach.cmd_finish(
            types.SimpleNamespace(
                task="T002", worker="agent-build", verification="tests passed", publish=False,
            )
        )
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        state["verification"] = {
            "status": "passed", "level": "quick", "command": "true", "notes": "exit 0",
            "verified_at": "2026-08-13T08:00:00Z", "commit": None,
        }
        self.write_json(".agent/STATE.json", state)
        roach.cmd_transition(types.SimpleNamespace(phase="complete", allow_live_work=False, publish=False))


class TemplateValidationTests(TempProject):
    def test_fresh_template_metadata_is_valid(self) -> None:
        self.copy_template_core()
        self.assertEqual([], roach.validate())

    def test_accept_product_requires_owned_discovery_claim(self) -> None:
        self.copy_template_core()
        self.write_valid_product()
        with self.assertRaises(SystemExit):
            roach.cmd_accept_product(
                types.SimpleNamespace(worker="agent-discovery", verification="owner confirmed")
            )

    def test_accept_product_rejects_missing_core_sections(self) -> None:
        self.copy_template_core()
        self.claim_t000()
        (self.root / ".agent/PRODUCT.md").write_text(
            "# Product\n\nStatus: DRAFT\n\n## Goals\n- Save things.\n\n"
            "## Requirements\n- **FR-001**: The user MUST save things.\n",
            encoding="utf-8",
        )
        (self.root / ".agent/PROJECT.md").write_text(
            "# Project\n\nA real project.\n", encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as ctx:
            roach.cmd_accept_product(
                types.SimpleNamespace(worker="agent-discovery", verification="owner confirmed")
            )
        self.assertIn("Vision", str(ctx.exception))

    def test_accept_product_atomically_completes_discovery_and_opens_planning(self) -> None:
        self.copy_template_core()
        self.accept_product()
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        t000 = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        t001 = json.loads((self.root / ".agent/tasks/T001.json").read_text(encoding="utf-8"))
        self.assertEqual("planning", state["phase"])
        self.assertEqual("accepted", state["product_definition"]["status"])
        self.assertEqual("done", t000["status"])
        self.assertIsNone(t000["claim"])
        self.assertEqual(["T000"], t001["depends_on"])
        self.assertTrue((self.root / ".agent/PLAN.md").exists())
        self.assertEqual("DRAFT", roach.plan_status_line())
        self.assertEqual("ACCEPTED", roach.product_status_line())
        self.assertEqual([], roach.validate())

    def test_product_status_and_state_must_agree(self) -> None:
        self.copy_template_core()
        self.accept_product()
        text = (self.root / ".agent/PRODUCT.md").read_text(encoding="utf-8")
        (self.root / ".agent/PRODUCT.md").write_text(
            text.replace("Status: ACCEPTED", "Status: DRAFT"), encoding="utf-8"
        )
        self.assertTrue(any("Status must be ACCEPTED" in error for error in roach.validate()))


class WorkerAndTaskStateTests(TempProject):
    def test_mutating_claim_requires_stable_worker_identity(self) -> None:
        self.copy_template_core()
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                roach.cmd_claim(
                    types.SimpleNamespace(
                        task="T000",
                        cap=["repo-write", "user-dialogue"],
                        worker=None,
                        lease_minutes=120,
                        branch=None,
                        publish=False,
                    )
                )
        self.assertIn("Stable worker identity required", str(ctx.exception))

    def test_finish_requires_claim_ownership(self) -> None:
        self.copy_template_core()
        with self.assertRaises(SystemExit):
            roach.cmd_finish(
                types.SimpleNamespace(task="T000", worker="agent-x", verification="done", publish=False)
            )

    def test_block_unblock_and_cancel_have_explicit_semantics(self) -> None:
        self.copy_template_core()
        self.claim_t000()
        roach.cmd_block(
            types.SimpleNamespace(
                task="T000",
                worker="agent-discovery",
                reason="owner access required",
                publish=False,
            )
        )
        task = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        self.assertEqual("blocked", task["status"])
        self.assertIsNone(task["claim"])
        self.assertIn("owner access required", task["handoff"])
        roach.cmd_unblock(types.SimpleNamespace(task="T000", publish=False))
        task = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        self.assertEqual("planned", task["status"])
        self.assertIsNone(task["handoff"])
        roach.cmd_cancel(
            types.SimpleNamespace(
                task="T000",
                worker=None,
                reason="project abandoned before discovery",
                publish=False,
            )
        )
        task = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        self.assertEqual("cancelled", task["status"])
        self.assertIn("project abandoned", task["verification"])

    def test_claim_status_shape_is_validated(self) -> None:
        self.copy_template_core()
        task = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        task["status"] = "active"
        task["claim"] = None
        self.write_json(".agent/tasks/T000.json", task)
        self.assertTrue(any("requires a claim" in error for error in roach.validate()))


class CapabilityAndProjectStatusTests(TempProject):
    def test_hard_capabilities_filter_task(self) -> None:
        self.copy_template_core()
        task = {
            "id": "T010",
            "kind": "implementation",
            "status": "planned",
            "depends_on": [],
            "areas": [],
            "requires": ["repo-write", "shell"],
            "prefers": [],
        }
        ok, reason = roach.eligible(task, [task], {"repo-write"}, phase="execution", project_status="active")
        self.assertFalse(ok)
        self.assertIn("shell", reason or "")
        ok, reason = roach.eligible(
            task, [task], {"repo-write", "shell"}, phase="execution", project_status="active"
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_paused_project_is_valid_but_offers_no_work(self) -> None:
        self.copy_template_core()
        roach.cmd_project_status(
            types.SimpleNamespace(status="paused", reason="owner requested pause", publish=False)
        )
        self.assertEqual([], roach.validate())
        task = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        ok, reason = roach.eligible(
            task,
            [task],
            {"repo-write", "user-dialogue"},
            phase="uninitialized",
            project_status="paused",
        )
        self.assertFalse(ok)
        self.assertEqual("project is paused", reason)

    def test_preferred_capabilities_break_ties(self) -> None:
        first = {"id": "T010", "priority": "normal", "prefers": []}
        second = {"id": "T011", "priority": "normal", "prefers": ["vision"]}
        ordered = sorted([first, second], key=lambda task: roach.task_sort_key(task, {"vision"}))
        self.assertEqual("T011", ordered[0]["id"])


class GraphAndRequirementTests(TempProject):
    def test_dependency_cycle_is_rejected(self) -> None:
        self.copy_template_core()
        for tid, dep in (("T010", "T011"), ("T011", "T010")):
            self.write_json(
                f".agent/tasks/{tid}.json",
                {
                    "id": tid,
                    "kind": "research",
                    "title": tid,
                    "status": "planned",
                    "priority": "normal",
                    "depends_on": [dep],
                    "areas": [],
                    "requirements": [],
                    "requires": [],
                    "prefers": [],
                    "acceptance": ["research complete"],
                    "verification": None,
                    "claim": None,
                    "handoff": None,
                },
            )
        self.assertTrue(any("dependency cycle" in error for error in roach.validate()))

    def test_active_unknown_requirement_is_invalid_but_historical_done_link_is_allowed(self) -> None:
        self.copy_template_core()
        self.accept_product()
        self.write_json(
            ".agent/tasks/T009.json",
            {
                "id": "T009",
                "kind": "implementation",
                "title": "Historical removed feature",
                "status": "done",
                "priority": "low",
                "depends_on": [],
                "areas": [],
                "requirements": ["FR-999"],
                "requires": [],
                "prefers": [],
                "acceptance": ["historical"],
                "verification": "completed before requirement retired",
                "claim": None,
                "handoff": None,
            },
        )
        self.assertFalse(any("T009 references unknown" in error for error in roach.validate()))
        historical = json.loads((self.root / ".agent/tasks/T009.json").read_text(encoding="utf-8"))
        historical["status"] = "planned"
        historical["verification"] = None
        self.write_json(".agent/tasks/T009.json", historical)
        self.assertTrue(any("T009 references unknown active requirement" in error for error in roach.validate()))

    def test_cancelled_dependency_is_rejected_for_live_work(self) -> None:
        self.copy_template_core()
        t000 = json.loads((self.root / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
        t000["status"] = "cancelled"
        t000["verification"] = "cancelled: no project"
        self.write_json(".agent/tasks/T000.json", t000)
        self.write_json(
            ".agent/tasks/T001.json",
            {
                "id": "T001",
                "kind": "planning",
                "title": "Plan",
                "status": "planned",
                "priority": "normal",
                "depends_on": ["T000"],
                "areas": [],
                "requirements": [],
                "requires": [],
                "prefers": [],
                "acceptance": ["plan"],
                "verification": None,
                "claim": None,
                "handoff": None,
            },
        )
        self.assertTrue(any("depends on cancelled task T000" in error for error in roach.validate()))


class LifecycleTests(TempProject):
    def test_later_pivot_creates_new_discovery_task(self) -> None:
        self.copy_template_core()
        self.accept_product()
        roach.cmd_transition(types.SimpleNamespace(phase="discovery", allow_live_work=False))
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        tasks = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((self.root / ".agent/tasks").glob("T*.json"))]
        new_discovery = [task for task in tasks if task["kind"] == "discovery" and task["status"] == "planned"]
        self.assertEqual("discovery", state["phase"])
        self.assertEqual("draft", state["product_definition"]["status"])
        self.assertEqual(1, len(new_discovery))
        self.assertNotEqual("T000", new_discovery[0]["id"])

    def test_readiness_requires_ready_plan_and_requirement_coverage(self) -> None:
        self.copy_template_core()
        self.accept_product()
        errors = roach.readiness_errors()
        self.assertTrue(any("PLAN.md status must be READY" in error for error in errors))
        self.assertTrue(any("required verification command" in error for error in errors))

    def test_ready_and_execution_transition(self) -> None:
        self.copy_template_core()
        self.make_ready_for_execution()
        self.assertEqual([], roach.readiness_errors())
        roach.cmd_transition(types.SimpleNamespace(phase="execution", allow_live_work=False))
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        self.assertEqual("execution", state["phase"])
        self.assertEqual([], roach.validate())

    def test_completion_is_gated_by_open_work_and_required_verification(self) -> None:
        self.copy_template_core()
        self.make_ready_for_execution()
        roach.cmd_transition(types.SimpleNamespace(phase="execution", allow_live_work=False))
        with self.assertRaises(SystemExit):
            roach.cmd_transition(types.SimpleNamespace(phase="complete", allow_live_work=False))
        roach.cmd_claim(
            types.SimpleNamespace(
                task="T002",
                cap=["repo-write"],
                worker="agent-build",
                lease_minutes=120,
                branch=None,
                publish=False,
            )
        )
        roach.cmd_finish(
            types.SimpleNamespace(
                task="T002",
                worker="agent-build",
                verification="tests passed",
                publish=False,
            )
        )
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        state["verification"] = {
            "status": "passed",
            "level": "quick",
            "command": "true",
            "notes": "exit 0",
            "verified_at": "2026-08-13T08:00:00Z",
            "commit": None,
        }
        self.write_json(".agent/STATE.json", state)
        self.assertEqual([], roach.completion_errors())
        roach.cmd_transition(types.SimpleNamespace(phase="complete", allow_live_work=False))
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        self.assertEqual("complete", state["project_status"])
        self.assertEqual("complete", state["phase"])
        self.assertEqual([], roach.validate())

    def test_completed_project_can_return_directly_to_execution(self) -> None:
        self.copy_template_core()
        self.complete_project()

        roach.cmd_transition(types.SimpleNamespace(
            phase="execution", allow_live_work=False, publish=False,
        ))

        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        self.assertEqual("active", state["project_status"])
        self.assertEqual("execution", state["phase"])
        self.assertEqual([], roach.validate())

    def test_review_preserves_completed_task_and_reactivates_project(self) -> None:
        self.copy_template_core()
        self.complete_project()

        roach.cmd_review(types.SimpleNamespace(
            task="T002", title=None, priority="high", requires=None, prefers=None,
            acceptance=None, publish=False,
        ))

        original = json.loads((self.root / ".agent/tasks/T002.json").read_text(encoding="utf-8"))
        review = json.loads((self.root / ".agent/tasks/T003.json").read_text(encoding="utf-8"))
        state = json.loads((self.root / ".agent/STATE.json").read_text(encoding="utf-8"))
        self.assertEqual("done", original["status"])
        self.assertEqual("T002", review["review_of"])
        self.assertEqual(["T002"], review["depends_on"])
        self.assertEqual("verification", review["kind"])
        self.assertEqual(["repo-read"], review["requires"])
        self.assertEqual("active", state["project_status"])
        self.assertEqual("execution", state["phase"])
        self.assertEqual([], roach.validate())

    def test_correction_links_to_review_without_rewriting_it(self) -> None:
        self.copy_template_core()
        self.complete_project()
        roach.cmd_review(types.SimpleNamespace(
            task="T002", title=None, priority="high", requires=None, prefers=None,
            acceptance=None, publish=False,
        ))
        roach.cmd_claim(types.SimpleNamespace(
            task="T003", cap=["repo-read", "shell"], worker="agent-review",
            lease_minutes=120, branch=None, publish=False,
        ))
        roach.cmd_finish(types.SimpleNamespace(
            task="T003", worker="agent-review",
            verification="independent review found save corruption", publish=False,
        ))

        roach.cmd_correct(types.SimpleNamespace(
            task="T003", title="Fix save corruption found in review", kind="implementation",
            priority="high", requires=["shell"], prefers=None,
            acceptance=["interrupted saves preserve the last valid note"], publish=False,
        ))

        review = json.loads((self.root / ".agent/tasks/T003.json").read_text(encoding="utf-8"))
        correction = json.loads((self.root / ".agent/tasks/T004.json").read_text(encoding="utf-8"))
        self.assertEqual("done", review["status"])
        self.assertEqual("T003", correction["correction_of"])
        self.assertEqual(["T003"], correction["depends_on"])
        self.assertEqual(["repo-write", "shell"], correction["requires"])
        self.assertEqual([], roach.validate())

    def test_claiming_completed_work_explains_review_and_revision_paths(self) -> None:
        self.copy_template_core()
        self.complete_project()

        with self.assertRaises(SystemExit) as ctx:
            roach.cmd_claim(types.SimpleNamespace(
                task="T002", cap=["repo-write"], worker="agent-review",
                lease_minutes=120, branch=None, publish=False,
            ))
        self.assertIn("roach.py review T002", str(ctx.exception))

        with self.assertRaises(SystemExit) as ctx:
            roach.cmd_claim(types.SimpleNamespace(
                task="T000", cap=["repo-write", "user-dialogue"], worker="agent-review",
                lease_minutes=120, branch=None, publish=False,
            ))
        self.assertIn("transition discovery", str(ctx.exception))


class RequirementParsingTests(TempProject):
    """PRODUCT.md is written in free-form markdown by a language model.

    Recognising only `- **FR-001**: text` meant a Requirements section written
    any other way produced no requirements at all -- and said nothing about it.
    Linking a task was then rejected as unknown, coverage passed against
    whatever subset happened to parse, and completion gated on that subset.
    """

    def product(self, requirements: str) -> None:
        (self.root / ".agent").mkdir(parents=True, exist_ok=True)
        (self.root / ".agent/PRODUCT.md").write_text(
            "# Product\n\n## Requirements\n\n" + requirements + "\n", encoding="utf-8")

    def test_the_original_list_form_still_parses(self) -> None:
        self.product("- **FR-001**: The user can save a note.\n"
                     "- QR-001: Saving completes within one second.")
        self.assertEqual(
            [("FR-001", "The user can save a note."),
             ("QR-001", "Saving completes within one second.")],
            roach.product_requirements(),
        )

    def test_a_markdown_table_parses(self) -> None:
        self.product(
            "| ID | Requirement |\n| --- | --- |\n"
            "| FR-001 | The user can save a note. |\n"
            "| FR-002 | The user can reopen a note. |"
        )
        self.assertEqual(
            {"FR-001", "FR-002"}, roach.requirement_ids(),
            "a table is ordinary markdown and must not silently vanish",
        )

    def test_requirements_under_a_subheading_are_still_in_the_section(self) -> None:
        self.product("### Functional\n\n- **FR-001**: The user can save a note.\n\n"
                     "### Quality\n\n- **QR-001**: Saving completes within one second.")
        self.assertEqual({"FR-001", "QR-001"}, roach.requirement_ids())

    def test_em_dash_and_heading_declarations_parse(self) -> None:
        self.product("- **FR-001** — The user can save a note.\n"
                     "#### QR-001: Saving completes within one second.")
        self.assertEqual({"FR-001", "QR-001"}, roach.requirement_ids())

    def test_a_declaration_without_text_is_reported_not_dropped(self) -> None:
        self.product("- **FR-001**: The user can save a note.\n- FR-002")
        problems = roach.requirement_format_problems()
        self.assertTrue(any("FR-002" in problem for problem in problems),
                        "silently ignoring a malformed requirement is the failure mode")

    def test_prose_mentioning_another_requirement_is_not_flagged(self) -> None:
        self.product("- **FR-001**: The user can save a note.\n\n"
                     "This section supersedes the earlier FR-009 scope.")
        self.assertEqual([], roach.requirement_format_problems())


class SafetyGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        configure_root(REPO)
        # origin is refreshed once per process; these tests drive several
        # independent scenarios through that one process.
        roach.reset_remote_cache()

    def test_fetch_failure_never_silently_uses_stale_remote(self) -> None:
        ok = types.SimpleNamespace(returncode=0, stdout="origin-url\n", stderr="")
        fail = types.SimpleNamespace(returncode=1, stdout="", stderr="network down")

        def fake_git(*args: str):
            if args[:2] == ("remote", "get-url"):
                return ok
            if args and args[0] == "fetch":
                return fail
            return ok

        with patch.object(roach, "git", side_effect=fake_git):
            with self.assertRaises(SystemExit) as ctx:
                roach.fetch_remote()
        self.assertIn("stale remote state", str(ctx.exception))

    def base_state(self, ahead: str = "", behind: str = "") -> dict:
        """Mocked git responses describing a base branch ahead of/behind origin."""
        blank = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        return {
            ("branch", "--show-current"): types.SimpleNamespace(returncode=0, stdout="main\n", stderr=""),
            ("remote", "get-url", "origin"): types.SimpleNamespace(returncode=0, stdout="git@example/repo\n", stderr=""),
            ("fetch", "origin", "--prune"): blank,
            ("rev-parse", "--verify", "refs/remotes/origin/main"): blank,
            ("rev-list", "refs/remotes/origin/main..HEAD"): types.SimpleNamespace(returncode=0, stdout=ahead, stderr=""),
            ("rev-list", "HEAD..refs/remotes/origin/main"): types.SimpleNamespace(returncode=0, stdout=behind, stderr=""),
        }

    def run_publish(self, responses: dict):
        def fake_git(*args: str):
            return responses.get(args, types.SimpleNamespace(returncode=0, stdout="", stderr=""))

        with patch.object(roach, "git", side_effect=fake_git):
            return roach.safe_publish("test")

    def test_publish_refuses_unpushed_local_commits(self) -> None:
        """The dangerous case: a coordination publish must not carry other commits."""
        with self.assertRaises(SystemExit) as ctx:
            self.run_publish(self.base_state(ahead="abc123\n"))
        self.assertIn("commit(s) that origin/main does not", str(ctx.exception))

    def test_publish_fast_forwards_a_base_that_is_only_behind(self) -> None:
        """Being behind is the steady state with several workers, not an error.

        Refusing it made every worker wait on a manual git pull after anybody
        else published, and turned an ordinary collision into a dead end.
        """
        responses = self.base_state(behind="def456\n")
        merged: list[tuple[str, ...]] = []

        def fake_git(*args: str):
            if args[:2] == ("merge", "--ff-only"):
                merged.append(args)
            return responses.get(args, types.SimpleNamespace(returncode=0, stdout="", stderr=""))

        with patch.object(roach, "git", side_effect=fake_git):
            roach.safe_publish("test")
        self.assertTrue(merged, "a base that is merely behind must fast-forward, not refuse")

    def test_publish_routes_a_colliding_fast_forward_to_reconcile(self) -> None:
        responses = self.base_state(behind="def456\n")
        responses[("merge", "--ff-only", "refs/remotes/origin/main")] = types.SimpleNamespace(
            returncode=1, stdout="", stderr="local changes would be overwritten",
        )
        with self.assertRaises(SystemExit) as ctx:
            self.run_publish(responses)
        self.assertIn("reconcile", str(ctx.exception))

    def test_invalid_stale_minutes_is_reported_cleanly(self) -> None:
        with patch.dict("os.environ", {"ROACH_STALE_MINUTES": "abc"}, clear=False):
            with self.assertRaises(SystemExit):
                roach.stale_minutes()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python
"""Coordination tests against a real remote and two independent clones.

Everything Roach exists to do -- publishing coordination state, resolving a
claim, diagnosing divergence -- only has meaning when `origin` exists and more
than one worker can see it. The other suites deliberately avoid git (one points
ROOT at a non-repository temp directory, the other never adds a remote), so the
whole shared-state surface went untested. These tests drive `roach.py` as a
subprocess, the way an agent actually calls it.
"""

from __future__ import annotations

import datetime
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

VALID_PRODUCT = """# Product

Status: DRAFT

## Vision
A tiny local note tool that a single person can trust to never lose a note.

## Goals
- Saving a note is obvious and dependable.

## Non-Goals
- No collaboration, sync, or accounts in the first version.

## Users / Audience
One solo desktop user working offline on a single laptop.

## Core Experience
Create a note, save it, quit the app, reopen it later and find it intact.

## Requirements
- **FR-001**: The user MUST be able to create and save a note.
- **FR-002**: The user MUST be able to reopen a previously saved note.

## Constraints
Local-first, offline, standard library only, runs on Windows and Linux.

## Success Criteria
The owner can complete create-save-quit-reopen fifty times with zero data loss.

## Open Questions
None that block planning.
"""

READY_PLAN = """# Plan

Status: READY

## Technical Approach
Pure Python standard library with a small CLI, because the product is offline and local-first.

## Architecture / Components
A notes store module owning atomic writes, and a thin CLI that calls it.

## Project Structure
Application code in src/, tests in app_tests/, notes persisted under a user data directory.

## Dependencies / Integrations
Standard library only. No network, no third-party packages, no platform services.

## Verification Strategy
Quick runs the unit tests. Full runs unit tests plus the durability test.

## Risks / Unknowns
Atomic replace semantics differ between Windows and Linux; covered by a dedicated task.

## Requirement Coverage
T002 covers FR-001 and FR-002.
"""

PROJECT_SUMMARY = "# Project\n\n## Summary\n\nA local-first single-user note tool focused on never losing a saved note.\n"

TEMPLATE_PATHS = (
    ".agent", ".agents", ".claude", "scripts",
    "AGENTS.md", "CLAUDE.md", "vercel.json", ".gitignore",
)


class RemoteProject(unittest.TestCase):
    """A bare origin plus two clones, each acting as an independent worker.

    Building that from scratch costs an init, a commit, a push, and two clones;
    driving a project to execution costs another dozen coordinator invocations,
    each spawning Python and touching git. Paid per test, across a suite this
    size, it ran past ten minutes -- and a suite nobody waits for is a suite
    nobody runs.

    So each expensive starting point is built once and copied afterwards.
    Correctness is unaffected: every test still gets its own private origin and
    clones, and a snapshot is only ever restored, never shared live.
    """

    _snapshots: ClassVar[dict[str, Path]] = {}
    _snapshot_root: ClassVar[Path | None] = None

    @staticmethod
    def remove_tree(path: Path) -> None:
        """Delete a tree containing a git repository.

        Git marks objects read-only, and Windows refuses to unlink a read-only
        file. A plain rmtree(ignore_errors=True) therefore leaves the directory
        half-present, which then fails the copy that follows it -- and leaks
        temp directories on every run.
        """
        def clear_readonly(func, target, _exc):  # type: ignore[no-untyped-def]
            os.chmod(target, stat.S_IWRITE)
            func(target)

        if path.exists():
            shutil.rmtree(path, onexc=clear_readonly)

    @classmethod
    def snapshot_root(cls) -> Path:
        if RemoteProject._snapshot_root is None:
            RemoteProject._snapshot_root = Path(tempfile.mkdtemp(prefix="roach-snapshots-"))
        return RemoteProject._snapshot_root

    @classmethod
    def tearDownClass(cls) -> None:
        root = RemoteProject._snapshot_root
        if root is not None and cls is RemoteProject:
            cls.remove_tree(root)

    def save_snapshot(self, name: str) -> None:
        target = self.snapshot_root() / name
        if target.exists():
            return
        shutil.copytree(self.dir, target)
        RemoteProject._snapshots[name] = target

    def restore_snapshot(self, name: str) -> bool:
        source = RemoteProject._snapshots.get(name)
        if source is None or not source.exists():
            return False
        self.remove_tree(self.dir)
        shutil.copytree(source, self.dir, dirs_exist_ok=True)
        # Clones record the origin path they were created from, which pointed
        # at the snapshot rather than at this test's private copy.
        for name_ in ("alpha", "beta"):
            self.git(self.dir / name_, "remote", "set-url", "origin", str(self.origin))
        return True

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.origin = self.dir / "origin.git"
        self.alpha = self.dir / "alpha"
        self.beta = self.dir / "beta"
        if self.restore_snapshot("pristine"):
            return

        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(self.origin)], check=True)
        seed = self.dir / "seed"
        seed.mkdir()
        for rel in TEMPLATE_PATHS:
            src = TEMPLATE / rel
            if not src.exists():
                continue
            dst = seed / rel
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(src, dst)
        shutil.rmtree(seed / ".agent" / "tests", ignore_errors=True)
        (seed / "app_tests").mkdir()
        (seed / "app_tests" / "test_smoke.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self.configure(seed)
        self.git(seed, "add", "-A")
        self.git(seed, "commit", "-qm", "template")
        self.git(seed, "push", "-q", "origin", "main")

        self.clone("alpha")
        self.clone("beta")
        self.save_snapshot("pristine")

    def tearDown(self) -> None:
        self.remove_tree(self.dir)

    # ---- plumbing ----------------------------------------------------------

    def configure(self, root: Path) -> None:
        if not (root / ".git").exists():
            self.git(root, "init", "-q", "-b", "main")
            self.git(root, "remote", "add", "origin", str(self.origin))
        self.git(root, "config", "user.email", "t@t.t")
        self.git(root, "config", "user.name", "t")
        self.git(root, "config", "core.autocrlf", "false")
        self.git(root, "config", "commit.gpgsign", "false")

    def clone(self, name: str) -> Path:
        root = self.dir / name
        # Pin autocrlf at checkout time. Inheriting the machine's global setting
        # would rewrite line endings during clone and leave a "modified" file in
        # a freshly cloned tree, which every publish assertion would then trip on.
        subprocess.run(
            ["git", "-c", "core.autocrlf=false", "clone", "-q", str(self.origin), str(root)],
            check=True, capture_output=True, text=True,
        )
        self.configure(root)
        return root

    def git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)

    def roach(self, root: Path, *args: str, worker: str | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.pop("ROACH_BASE_BRANCH", None)
        if worker:
            env["ROACH_WORKER"] = worker
        else:
            env.pop("ROACH_WORKER", None)
        return subprocess.run(
            [sys.executable, "scripts/roach.py", *args],
            cwd=root, text=True, capture_output=True, env=env,
        )

    def ok(self, result: subprocess.CompletedProcess[str], why: str = "") -> subprocess.CompletedProcess[str]:
        if result.returncode != 0:
            self.fail(f"{why or 'command failed'}\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return result

    def output(self, result: subprocess.CompletedProcess[str]) -> str:
        return result.stdout + result.stderr

    # ---- repository helpers ------------------------------------------------

    def read_task(self, root: Path, task_id: str) -> dict:
        return json.loads((root / ".agent/tasks" / f"{task_id}.json").read_text(encoding="utf-8"))

    def read_state(self, root: Path) -> dict:
        return json.loads((root / ".agent/STATE.json").read_text(encoding="utf-8"))

    def origin_file(self, path: str) -> str | None:
        out = self.git(self.alpha, "show", f"origin/main:{path}")
        return out.stdout if out.returncode == 0 else None

    def origin_task(self, task_id: str) -> dict | None:
        raw = self.origin_file(f".agent/tasks/{task_id}.json")
        return json.loads(raw) if raw else None

    def commit_all(self, root: Path, message: str) -> None:
        self.git(root, "add", "-A")
        self.git(root, "commit", "-qm", message)
        self.ok(self.git(root, "push", "-q", "origin", "main"), "seed push failed")

    def write_product(self, root: Path) -> None:
        (root / ".agent/PRODUCT.md").write_text(VALID_PRODUCT, encoding="utf-8")
        (root / ".agent/PROJECT.md").write_text(PROJECT_SUMMARY, encoding="utf-8")

    # The interpreter running the tests, quoted for the shell that
    # run_verification uses. Hardcoding "python" passes on Windows and fails on
    # runners where only "python3" exists.
    UNIT_TESTS = f'"{sys.executable}" -m unittest discover -s app_tests -q'

    def set_verify(self, root: Path, quick: str | None = None) -> None:
        command = self.UNIT_TESTS if quick is None else quick
        path = root / ".agent/VERIFY.json"
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["required_level"] = "quick"
        cfg["commands"]["quick"] = command
        cfg["commands"]["full"] = command
        path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    def seed_planning(self, worker: str = "alpha-1") -> None:
        """Drive the discovery cycle on alpha and publish the result."""
        if self.restore_snapshot(f"planning-{worker}"):
            return
        self._seed_planning(worker)
        self.save_snapshot(f"planning-{worker}")

    def _seed_planning(self, worker: str) -> None:
        self.ok(self.roach(self.alpha, "claim", "T000", "--cap", "repo-write",
                           "--cap", "user-dialogue", worker=worker))
        self.ok(self.roach(self.alpha, "transition", "discovery"))
        self.write_product(self.alpha)
        self.ok(self.roach(self.alpha, "accept-product", "--verification",
                           "owner confirmed product intent", worker=worker))

    def seed_execution(self, worker: str = "alpha-1") -> None:
        """Take the project all the way to execution phase, published."""
        if self.restore_snapshot(f"execution-{worker}"):
            return
        self.seed_planning(worker)
        self._seed_execution(worker)
        self.save_snapshot(f"execution-{worker}")

    def _seed_execution(self, worker: str) -> None:
        self.commit_all(self.alpha, "product: accept intent")
        self.ok(self.roach(self.alpha, "claim", "T001", "--cap", "repo-write", worker=worker))
        (self.alpha / ".agent/PLAN.md").write_text(READY_PLAN, encoding="utf-8")
        self.set_verify(self.alpha)
        self.ok(self.roach(
            self.alpha, "create", "--title", "Implement save and reopen",
            "--kind", "implementation", "--requirement", "FR-001", "--requirement", "FR-002",
            "--requires", "repo-write", "--area", "persistence",
            "--acceptance", "a note can be saved and reopened", worker=worker,
        ))
        self.ok(self.roach(self.alpha, "finish", "T001", "--verification",
                           "plan ready and backlog created", worker=worker))
        self.ok(self.roach(self.alpha, "transition", "execution"))
        self.commit_all(self.alpha, "state: enter execution")
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        self.ok(self.git(self.beta, "reset", "-q", "--hard", "origin/main"))

    def seed_complete(self, worker: str = "alpha-1") -> None:
        """Publish a mechanically complete project that can later be reviewed.

        The implementation task does real work on its branch and integrates it,
        because that is what completing a project means. A fixture that finished
        an implementation task with no commits anywhere was describing a project
        that could not exist.
        """
        if self.restore_snapshot(f"complete-{worker}"):
            return
        self._seed_complete(worker)
        self.save_snapshot(f"complete-{worker}")

    def _seed_complete(self, worker: str) -> None:
        self.seed_execution(worker)
        self.ok(self.roach(
            self.alpha, "claim", "T002", "--cap", "repo-write", "--publish", worker=worker,
        ))
        self.work_on_branch(self.alpha, "T002", worker)
        self.ok(self.roach(self.alpha, "integrate", "T002", "--push", worker=worker))
        self.ok(self.roach(
            self.alpha, "finish", "T002", "--verification", "implementation checks passed",
            "--publish", worker=worker,
        ))
        self.ok(self.roach(self.alpha, "verify", "quick"))
        self.ok(self.roach(self.alpha, "transition", "complete", "--publish"))

    def work_on_branch(self, root: Path, task_id: str, worker: str, content: str = "v2\n") -> str:
        """Commit and push real work on the task's claimed branch."""
        branch = self.read_task(root, task_id)["claim"]["branch"]
        self.git(root, "checkout", "-q", "-b", branch)
        (root / "src").mkdir(exist_ok=True)
        (root / "src" / f"{task_id}.py").write_text(content, encoding="utf-8")
        self.git(root, "add", "-A")
        self.git(root, "commit", "-qm", f"wip({task_id}): work")
        self.ok(self.git(root, "push", "-q", "-u", "origin", branch))
        self.git(root, "checkout", "-q", "main")
        return branch


class PublishTests(RemoteProject):
    """--publish must succeed for the commands whose own edits it must carry."""

    def test_accept_product_publishes_the_project_summary_it_requires(self) -> None:
        # accept-product refuses a PROJECT.md placeholder, so it must publish the
        # replacement it just demanded.
        self.ok(self.roach(self.alpha, "claim", "T000", "--cap", "repo-write",
                           "--cap", "user-dialogue", worker="alpha-1"))
        self.ok(self.roach(self.alpha, "transition", "discovery"))
        self.write_product(self.alpha)
        result = self.roach(self.alpha, "accept-product", "--verification",
                            "owner confirmed", "--publish", worker="alpha-1")
        self.ok(result, "accept-product --publish must not refuse its own edits")
        self.assertIn("Summary", self.origin_file(".agent/PROJECT.md") or "")
        self.assertEqual("accepted", json.loads(
            self.origin_file(".agent/STATE.json") or "{}"
        )["product_definition"]["status"])

    def test_transition_execution_publishes_plan_and_backlog(self) -> None:
        self.seed_planning()
        self.commit_all(self.alpha, "product: accept intent")
        self.ok(self.roach(self.alpha, "claim", "T001", "--cap", "repo-write", worker="alpha-1"))
        (self.alpha / ".agent/PLAN.md").write_text(READY_PLAN, encoding="utf-8")
        self.set_verify(self.alpha)
        self.ok(self.roach(
            self.alpha, "create", "--title", "Implement save and reopen",
            "--kind", "implementation", "--requirement", "FR-001", "--requirement", "FR-002",
            "--requires", "repo-write", "--acceptance", "save and reopen work", worker="alpha-1",
        ))
        self.ok(self.roach(self.alpha, "finish", "T001", "--verification", "plan ready", worker="alpha-1"))
        result = self.roach(self.alpha, "transition", "execution", "--publish")
        self.ok(result, "entering execution must publish the plan and backlog it gates on")
        self.assertIn("Status: READY", self.origin_file(".agent/PLAN.md") or "")
        self.assertIsNotNone(self.origin_task("T002"), "the new backlog must reach origin")

    def test_review_atomically_reactivates_a_completed_project(self) -> None:
        self.seed_complete()

        result = self.roach(self.alpha, "review", "T002", "--publish")

        self.ok(result, "review must publish the new task and reactivated state together")
        state = json.loads(self.origin_file(".agent/STATE.json") or "{}")
        review = self.origin_task("T003") or {}
        self.assertEqual("active", state.get("project_status"))
        self.assertEqual("execution", state.get("phase"))
        self.assertEqual("T002", review.get("review_of"))
        self.assertEqual("planned", review.get("status"))
        self.assertEqual("done", (self.origin_task("T002") or {}).get("status"))

    def test_publish_command_recovers_unpublished_coordination_state(self) -> None:
        """A failed publish must be retryable without hand-committing."""
        self.seed_planning()
        result = self.roach(self.alpha, "publish")
        self.ok(result, "roach.py publish must commit and push pending coordination state")
        self.assertEqual("accepted", json.loads(
            self.origin_file(".agent/STATE.json") or "{}"
        )["product_definition"]["status"])
        self.assertEqual([], [
            line for line in self.git(self.alpha, "status", "--porcelain").stdout.splitlines()
            if line.strip()
        ])

    def test_publish_refuses_unrelated_application_changes(self) -> None:
        """Widening the allowed set must not let publish carry product code."""
        self.seed_planning()
        (self.alpha / "src").mkdir(exist_ok=True)
        (self.alpha / "src" / "stray.py").write_text("print('unrelated')\n", encoding="utf-8")
        result = self.roach(self.alpha, "publish")
        self.assertNotEqual(0, result.returncode, "publish must refuse non-coordination changes")
        self.assertIn("src/stray.py", self.output(result))


class IntegrateTests(RemoteProject):
    def test_integrate_then_finish_publish_is_the_documented_sequence(self) -> None:
        # integrate prints `Next: ... finish ...`; that sequence must work.
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.work_on_branch(self.alpha, "T002", "alpha-1")
        self.ok(self.roach(self.alpha, "integrate", "T002", "--push", worker="alpha-1"))
        result = self.roach(self.alpha, "finish", "T002", "--verification",
                            "unit tests pass", "--publish", worker="alpha-1")
        self.ok(result, "finish --publish must not trip over integrate's own verification record")
        self.assertEqual("done", (self.origin_task("T002") or {}).get("status"))

    def test_failed_integrate_records_the_failure_it_rolled_back(self) -> None:
        self.seed_execution()
        self.set_verify(self.alpha, "exit 1")
        self.commit_all(self.alpha, "verify: failing command")
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.work_on_branch(self.alpha, "T002", "alpha-1")
        before = self.git(self.alpha, "rev-parse", "HEAD").stdout.strip()
        result = self.roach(self.alpha, "integrate", "T002", worker="alpha-1")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, self.git(self.alpha, "rev-parse", "HEAD").stdout.strip(),
                         "the merge must still be rolled back")
        self.assertEqual("failed", self.read_state(self.alpha)["verification"]["status"],
                         "rolling back the merge must not erase the evidence it failed")


class ClaimIntegrityTests(RemoteProject):
    def test_claiming_off_the_base_branch_is_refused(self) -> None:
        """Otherwise the claim is committed to the task branch and lost on checkout."""
        self.seed_execution()
        self.git(self.alpha, "checkout", "-q", "-b", "roach/T002-alpha-1")
        result = self.roach(self.alpha, "claim", "T002", "--cap", "repo-write", worker="alpha-1")
        self.assertNotEqual(0, result.returncode, "claiming off base strands the claim on the branch")
        self.assertIn("main", self.output(result))

    def test_a_locally_created_task_can_be_claimed_before_it_is_published(self) -> None:
        self.seed_execution()
        self.ok(self.roach(
            self.alpha, "create", "--title", "Follow-up discovered while working",
            "--kind", "implementation", "--requires", "repo-write",
            "--acceptance", "the follow-up is done", worker="alpha-1",
        ))
        result = self.roach(self.alpha, "claim", "T003", "--cap", "repo-write", worker="alpha-1")
        self.ok(result, "a task this worker just created must be claimable")

    def test_a_stale_local_copy_cannot_mask_a_live_remote_claim(self) -> None:
        """The guard that makes local tasks visible must not hide origin's truth."""
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        # beta's checkout predates the claim, which is the normal stale-worktree case.
        result = self.roach(self.beta, "claim", "T002", "--cap", "repo-write", worker="beta-1")
        self.assertNotEqual(0, result.returncode, "beta must not claim a task alpha holds")

    def test_cancel_refuses_a_task_live_claimed_on_origin(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        result = self.roach(self.beta, "cancel", "T002", "--reason",
                            "beta thinks this is obsolete", worker="beta-1")
        self.assertNotEqual(0, result.returncode, "cancel must respect another worker's live claim")
        self.assertNotEqual("cancelled", self.read_task(self.beta, "T002")["status"])

    def test_block_refuses_a_task_live_claimed_on_origin(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        result = self.roach(self.beta, "block", "T002", "--reason", "needs owner input", worker="beta-1")
        self.assertNotEqual(0, result.returncode, "block must respect another worker's live claim")

    def test_cancelling_an_unclaimed_task_still_works_without_a_worker(self) -> None:
        self.seed_execution()
        result = self.roach(self.beta, "cancel", "T002", "--reason", "superseded by new intent")
        self.ok(result, "unclaimed work must remain cancellable without a worker id")

    def test_adopt_force_takes_over_a_live_claim_and_records_why(self) -> None:
        """The owner knows the session died; waiting out the lease is not recovery."""
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        self.ok(self.git(self.beta, "reset", "-q", "--hard", "origin/main"))
        refused = self.roach(self.beta, "adopt", "T002", worker="beta-1")
        self.assertNotEqual(0, refused.returncode, "adopt must still refuse a live claim by default")
        forced = self.roach(self.beta, "adopt", "T002", "--force", "--reason",
                            "alpha session crashed", worker="beta-1")
        self.ok(forced, "--force must provide a recorded override")
        claim = self.read_task(self.beta, "T002")["claim"]
        self.assertEqual("beta-1", claim["worker"])
        self.assertEqual("alpha-1", claim["adopted_from"])
        self.assertIn("crashed", json.dumps(claim))

    def stale_claim_on_origin(self, task_id: str, holder: str) -> None:
        """Publish an expired claim, so every checkout agrees the task is abandoned."""
        expired = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        path = self.alpha / ".agent/tasks" / f"{task_id}.json"
        task = json.loads(path.read_text(encoding="utf-8"))
        task["status"] = "claimed"
        task["claim"] = {
            "worker": holder, "claimed_at": expired, "lease_expires_at": expired,
            "branch": f"roach/{task_id}-{holder}",
        }
        path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        self.ok(self.roach(self.alpha, "publish"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        self.ok(self.git(self.beta, "reset", "-q", "--hard", "origin/main"))

    def test_adopt_refuses_a_claim_that_is_live_only_on_origin(self) -> None:
        """A stale checkout must not be able to answer "is the owner gone?".

        adopt is the one command whose whole job is contested handover. Reading
        the local copy alone let a worker one commit behind take a task another
        worker had just legitimately adopted, with no --force and no warning.
        """
        self.seed_execution()
        self.stale_claim_on_origin("T002", "ghost-0")
        # alpha legitimately takes the abandoned task and publishes a fresh claim.
        self.ok(self.roach(self.alpha, "adopt", "T002", "--publish", worker="alpha-2"))
        # beta never pulled, so its copy still shows the expired ghost-0 claim.
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        self.assertEqual("ghost-0", self.read_task(self.beta, "T002")["claim"]["worker"])

        refused = self.roach(self.beta, "adopt", "T002", worker="beta-1")
        self.assertNotEqual(0, refused.returncode, "adopt must consult origin, not the stale local copy")
        self.assertIn("alpha-2", self.output(refused), "the refusal must name the owner origin knows")
        self.assertEqual("ghost-0", self.read_task(self.beta, "T002")["claim"]["worker"],
                         "a refused adopt must not rewrite the local record")

    def test_forced_adopt_records_the_predecessor_origin_knows_about(self) -> None:
        """adopted_from must name the real previous owner, not a stale one."""
        self.seed_execution()
        self.stale_claim_on_origin("T002", "ghost-0")
        self.ok(self.roach(self.alpha, "adopt", "T002", "--publish", worker="alpha-2"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))

        forced = self.roach(self.beta, "adopt", "T002", "--force", "--reason",
                            "alpha-2 session confirmed dead", worker="beta-1")
        self.ok(forced, "a deliberate override must still be available")
        claim = self.read_task(self.beta, "T002")["claim"]
        self.assertEqual("beta-1", claim["worker"])
        self.assertEqual("alpha-2", claim["adopted_from"],
                         "the handover must record who actually held the task")

    def test_forced_adopt_still_requires_a_reason(self) -> None:
        self.seed_execution()
        self.stale_claim_on_origin("T002", "ghost-0")
        self.ok(self.roach(self.alpha, "adopt", "T002", "--publish", worker="alpha-2"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        result = self.roach(self.beta, "adopt", "T002", "--force", worker="beta-1")
        self.assertNotEqual(0, result.returncode, "an unexplained override is not an override")
        self.assertIn("--reason", self.output(result))


class DoctorTests(RemoteProject):
    def test_doctor_reports_uncommitted_coordination_state(self) -> None:
        self.seed_planning()
        result = self.roach(self.alpha, "doctor")
        self.assertNotEqual(0, result.returncode,
                            "unpublished product acceptance is invisible to every other worker")
        self.assertIn("publish", self.output(result).lower())

    def test_doctor_reports_a_base_branch_behind_origin(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        result = self.roach(self.beta, "doctor")
        self.assertNotEqual(0, result.returncode, "a stale base branch must be reported")
        self.assertIn("behind", self.output(result).lower())

    def test_doctor_reports_unpushed_commits_that_also_touch_code(self) -> None:
        """--publish refuses either way, so the diagnosis must not depend on the diff."""
        self.seed_execution()
        (self.alpha / "src").mkdir(exist_ok=True)
        (self.alpha / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        task = self.alpha / ".agent/tasks/T002.json"
        task.write_text(task.read_text(encoding="utf-8").replace(
            "Implement save and reopen", "Implement save and reopen (edited)"
        ), encoding="utf-8")
        self.git(self.alpha, "add", "-A")
        self.git(self.alpha, "commit", "-qm", "mixed change")
        result = self.roach(self.alpha, "doctor")
        self.assertNotEqual(0, result.returncode, "unpushed commits block publishing regardless of diff")
        self.assertIn("unpushed", self.output(result).lower())

    def test_doctor_reports_a_task_record_that_diverges_from_origin(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write", worker="alpha-1"))
        self.git(self.alpha, "add", "-A")
        self.git(self.alpha, "commit", "-qm", "claim T002 locally only")
        result = self.roach(self.alpha, "doctor")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("T002", self.output(result))

    def test_doctor_is_silent_on_a_healthy_synchronised_repository(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "doctor"), "a clean synchronised repo must report no problems")

    def test_coordination_commits_do_not_invalidate_a_verification_run(self) -> None:
        """Otherwise every claim would demand a re-run, and completion could never pass."""
        self.seed_execution()
        self.ok(self.roach(self.alpha, "verify", "quick"))
        self.ok(self.roach(self.alpha, "publish"))
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        result = self.roach(self.alpha, "doctor")
        self.assertNotIn("verification", self.output(result).lower())
        self.ok(result, "publishing a claim must not invalidate verification")

    def test_a_product_code_change_does_invalidate_a_verification_run(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "verify", "quick"))
        self.ok(self.roach(self.alpha, "publish"))
        (self.alpha / "src").mkdir(exist_ok=True)
        (self.alpha / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        self.git(self.alpha, "add", "-A")
        self.git(self.alpha, "commit", "-qm", "product change")
        self.ok(self.git(self.alpha, "push", "-q", "origin", "main"))
        result = self.roach(self.alpha, "doctor")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("verification", self.output(result).lower())


class EvidenceTests(RemoteProject):
    """Roach cannot judge whether --verification text is true. It can check that
    something happened -- and the task record already holds the data to do it."""

    def test_finishing_an_implementation_task_with_no_work_is_refused(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        result = self.roach(self.alpha, "finish", "T002", "--verification",
                            "it works, trust me", worker="alpha-1")
        self.assertNotEqual(0, result.returncode,
                            "a complete-looking project containing nothing is the failure to prevent")
        self.assertIn("no work", self.output(result))
        self.assertEqual("claimed", self.read_task(self.alpha, "T002")["status"])

    def test_work_on_the_task_branch_counts_as_evidence(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.work_on_branch(self.alpha, "T002", "alpha-1")
        result = self.roach(self.alpha, "finish", "T002", "--verification",
                            "unit tests pass on the branch", worker="alpha-1")
        self.ok(result, "pushed work on the claimed branch is evidence")
        self.assertIn("commit(s) on", self.output(result))

    def test_a_task_with_no_repository_change_can_be_waived_on_the_record(self) -> None:
        """Some work legitimately produces nothing. It must be stated, not assumed."""
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.ok(self.roach(self.alpha, "finish", "T002", "--verification",
                           "owner confirmed no change was needed", "--no-work", worker="alpha-1"))
        evidence = self.read_task(self.alpha, "T002")["evidence"]
        self.assertTrue(evidence["work_waived"], "the waiver must be visible in the record")

    def test_non_code_kinds_do_not_require_commits(self) -> None:
        self.seed_execution()
        self.ok(self.roach(
            self.alpha, "create", "--title", "Check the layout by eye", "--kind", "verification",
            "--requires", "repo-read", "--acceptance", "the layout was inspected", worker="alpha-1",
        ))
        self.ok(self.roach(self.alpha, "claim", "T003", "--cap", "repo-read",
                           "--publish", worker="alpha-1"))
        self.ok(self.roach(self.alpha, "finish", "T003", "--verification",
                           "inspected at 1280x800; no overlap", worker="alpha-1"),
                "a review that produces a finding rather than a commit is normal")

    def test_integrate_stamps_the_merge_onto_the_task(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.work_on_branch(self.alpha, "T002", "alpha-1")
        self.ok(self.roach(self.alpha, "integrate", "T002", "--push", worker="alpha-1"))
        integration = self.read_task(self.alpha, "T002")["integration"]
        self.assertTrue(integration["merge_commit"], "the merge is the durable link to the work")
        self.assertEqual("quick", integration["level"])
        result = self.ok(self.roach(self.alpha, "finish", "T002", "--verification",
                                    "merged and verified", worker="alpha-1"))
        self.assertIn("merged as", self.output(result))

    def test_a_failing_task_check_blocks_completion(self) -> None:
        self.seed_execution()
        guard = f'"{sys.executable}" -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'src/T003.py\').exists() else 1)"'
        self.ok(self.roach(
            self.alpha, "create", "--title", "Guarded work", "--kind", "implementation",
            "--requires", "repo-write", "--acceptance", "the guard passes",
            "--verify", guard, worker="alpha-1",
        ))
        self.ok(self.roach(self.alpha, "claim", "T003", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        # Commit something unrelated: work evidence exists, but the task's own check fails.
        branch = self.read_task(self.alpha, "T003")["claim"]["branch"]
        self.git(self.alpha, "checkout", "-q", "-b", branch)
        (self.alpha / "unrelated.txt").write_text("x\n", encoding="utf-8")
        self.git(self.alpha, "add", "-A")
        self.git(self.alpha, "commit", "-qm", "wip(T003): not the thing")
        self.ok(self.git(self.alpha, "push", "-q", "-u", "origin", branch))
        self.git(self.alpha, "checkout", "-q", "main")

        refused = self.roach(self.alpha, "finish", "T003", "--verification", "done", worker="alpha-1")
        self.assertNotEqual(0, refused.returncode, "a task's own failing check must block it")
        self.assertIn("check", self.output(refused))

        self.work_on_branch(self.alpha, "T003", "alpha-1")
        passed = self.roach(self.alpha, "finish", "T003", "--verification", "guard satisfied",
                            worker="alpha-1")
        self.ok(passed, "the same task must finish once its own check passes")
        self.assertEqual("passed", self.read_task(self.alpha, "T003")["evidence"]["task_check"])


class ReconcileTests(RemoteProject):
    """The loser of a coordination race must have a way forward.

    Two workers creating a task from the same base both compute the same free
    id. Publishing then refused because the base was behind, and pulling
    refused because the incoming commit wanted the same path -- and doctor
    recommended exactly those two commands.
    """

    def create_on(self, root: Path, title: str, area: str, worker: str) -> None:
        self.ok(self.roach(
            root, "create", "--title", title, "--kind", "implementation",
            "--requires", "repo-write", "--area", area,
            "--acceptance", f"{title} is done", worker=worker,
        ))

    def test_publish_fast_forwards_instead_of_refusing_a_stale_base(self) -> None:
        self.seed_execution()
        self.create_on(self.alpha, "Alpha work", "alpha-area", "alpha-1")
        self.ok(self.roach(self.alpha, "publish"))
        # beta's base is now behind, with an unrelated pending edit of its own.
        self.create_on(self.beta, "Beta work", "beta-area", "beta-1")
        result = self.roach(self.beta, "publish")
        self.ok(result, "a base that is merely behind must fast-forward and publish")
        self.assertIn("Fast-forwarded", self.output(result))

    def test_reconcile_renumbers_the_task_that_lost_the_id_race(self) -> None:
        self.seed_execution()
        self.create_on(self.alpha, "Alpha second", "alpha-area", "alpha-1")
        self.create_on(self.beta, "Beta second", "beta-area", "beta-1")
        contested = sorted(p.stem for p in (self.beta / ".agent/tasks").glob("T*.json"))[-1]
        self.ok(self.roach(self.alpha, "publish"), "alpha wins the race")

        wedged = self.roach(self.beta, "publish")
        self.assertNotEqual(0, wedged.returncode)
        self.assertIn("reconcile", self.output(wedged), "the refusal must name the way out")

        result = self.roach(self.beta, "reconcile")
        self.ok(result, "reconcile must resolve the documented id race")
        self.assertIn("Renumbered", self.output(result))
        self.ok(self.roach(self.beta, "publish"), "the replayed task must publish cleanly")

        # origin_file() reads through alpha's remote-tracking ref, which does not
        # know about beta's push until alpha fetches.
        self.ok(self.git(self.alpha, "fetch", "-q", "origin"))
        titles = {}
        for name in self.git(self.alpha, "ls-tree", "-r", "--name-only", "origin/main",
                             ".agent/tasks").stdout.splitlines():
            if name.endswith(".json"):
                record = json.loads(self.origin_file(name) or "{}")
                titles[record.get("title")] = record.get("id")
        self.assertIn("Alpha second", titles, "the winner's task must survive")
        self.assertIn("Beta second", titles, "the loser's task must survive under a new id")
        self.assertNotEqual(titles["Alpha second"], titles["Beta second"])
        self.assertEqual(titles["Alpha second"], contested,
                         "the worker that published first keeps the contested id")

    def test_reconcile_keeps_an_edit_it_cannot_replay(self) -> None:
        """A contested ownership edit must be preserved, never silently dropped."""
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        # beta claimed the same task from its older base, without publishing.
        self.ok(self.git(self.beta, "fetch", "-q", "origin"))
        beta_task = self.beta / ".agent/tasks/T002.json"
        record = json.loads(beta_task.read_text(encoding="utf-8"))
        record["status"] = "claimed"
        record["claim"] = {
            "worker": "beta-1", "claimed_at": "2026-01-01T00:00:00Z",
            "lease_expires_at": "2099-01-01T00:00:00Z", "branch": "roach/T002-beta-1",
        }
        beta_task.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

        result = self.roach(self.beta, "reconcile")
        self.ok(result)
        self.assertIn("Set aside", self.output(result))
        self.assertEqual("alpha-1", self.read_task(self.beta, "T002")["claim"]["worker"],
                         "shared ownership must win over a stale local edit")
        parked = self.beta / ".roach-reconcile/.agent/tasks/T002.json"
        self.assertTrue(parked.exists(), "the discarded edit must remain readable")
        self.assertEqual("beta-1", json.loads(parked.read_text(encoding="utf-8"))["claim"]["worker"])

    def test_reconcile_leaves_a_synchronised_repository_alone(self) -> None:
        self.seed_execution()
        result = self.roach(self.beta, "reconcile")
        self.ok(result, "reconcile must be safe to run when nothing is wrong")
        self.assertIn("Already level", self.output(result))

    def test_doctor_points_at_reconcile_for_the_wedge(self) -> None:
        self.seed_execution()
        self.create_on(self.alpha, "Alpha second", "alpha-area", "alpha-1")
        self.create_on(self.beta, "Beta second", "beta-area", "beta-1")
        self.ok(self.roach(self.alpha, "publish"))
        output = self.output(self.roach(self.beta, "doctor"))
        self.assertIn("reconcile", output)
        self.assertNotIn("git pull --ff-only", output,
                         "recommending a pull that the pending edit blocks is the original dead end")


class ResilienceTests(RemoteProject):
    """The commands that explain a broken repository must survive one.

    check and doctor used to abort on the first unreadable file, reporting one
    problem and hiding every other -- exactly when the worker has least context
    to reason without them.
    """

    def corrupt(self, root: Path, task_id: str) -> None:
        (root / ".agent/tasks" / f"{task_id}.json").write_text("{ not json", encoding="utf-8")

    def test_doctor_reports_an_unreadable_task_record_and_keeps_going(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        self.corrupt(self.alpha, "T002")
        result = self.roach(self.alpha, "doctor")
        output = self.output(result)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("T002.json", output, "doctor must name the file it could not read")
        self.assertIn("fix:", output, "an unreadable record needs an actionable fix like every other finding")
        self.assertIn("Found", output, "doctor must still produce its normal report")

    def test_check_reports_a_corrupt_record_alongside_other_errors(self) -> None:
        self.seed_execution()
        self.corrupt(self.alpha, "T002")
        result = self.roach(self.alpha, "check")
        output = self.output(result)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Roach state INVALID", output, "check must report, not abort")
        self.assertIn("T002.json", output)

    def test_a_corrupt_record_does_not_hide_a_second_problem(self) -> None:
        self.seed_execution()
        self.corrupt(self.alpha, "T002")
        state = self.alpha / ".agent/STATE.json"
        broken = json.loads(state.read_text(encoding="utf-8"))
        broken["protocol_version"] = "0.1"
        state.write_text(json.dumps(broken, indent=2) + "\n", encoding="utf-8")
        output = self.output(self.roach(self.alpha, "check"))
        self.assertIn("T002.json", output)
        self.assertIn("protocol_version", output,
                      "the first bad file must not suppress every later finding")


class HygieneTests(RemoteProject):
    def test_build_artifacts_do_not_block_publishing(self) -> None:
        self.seed_execution()
        cache = self.alpha / "app_tests" / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "test_smoke.cpython-313.pyc").write_bytes(b"\x00")
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"),
                "a stray build artifact must not wedge every publish")

    def test_status_output_is_ascii_safe(self) -> None:
        self.seed_execution()
        self.ok(self.roach(self.alpha, "claim", "T002", "--cap", "repo-write",
                           "--publish", worker="alpha-1"))
        result = self.ok(self.roach(self.alpha, "status", "--cap", "repo-write"))
        result.stdout.encode("ascii")


if __name__ == "__main__":
    unittest.main(verbosity=2)

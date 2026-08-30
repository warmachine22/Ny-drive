#!/usr/bin/env python3
"""Roach Method v0.5 deterministic coordination helper."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterable

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / ".agent"
TASKS = AGENT / "tasks"
STATE_PATH = AGENT / "STATE.json"
VERIFY_PATH = AGENT / "VERIFY.json"
PRODUCT_PATH = AGENT / "PRODUCT.md"
PROJECT_PATH = AGENT / "PROJECT.md"
PLAN_PATH = AGENT / "PLAN.md"

PROTOCOL_VERSION = "0.5"
MIGRATABLE_VERSIONS = {"0.3", "0.4", PROTOCOL_VERSION}

# Section text that is present but says nothing. Approving a product full of
# these locks in an empty definition that every later decision inherits.
FILLER_TEXT = {
    "tbd", "todo", "to do", "n/a", "na", "none", "nothing", "unknown", "tba",
    "?", "-", "x", "coming soon", "later", "decide later", "fill in",
}
# Deliberately low. Filler detection above catches the real failure mode; this
# is only a floor against one-word sections. Set it high enough to reject
# genuinely terse but real content and the check does more harm than good.
MIN_SECTION_CHARS = 16

TASK_RE = re.compile(r"^T(\d{3,})$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
STATUSES = {"planned", "claimed", "active", "blocked", "verify", "done", "cancelled"}
ACTIVE_CLAIM_STATUSES = {"claimed", "active", "verify"}
TERMINAL_STATUSES = {"done", "cancelled"}
PRIORITY = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
PROJECT_STATUSES = {"active", "blocked", "paused", "complete"}
PHASES = {"uninitialized", "discovery", "planning", "execution", "complete"}
STANDARD_CAPABILITIES = (
    "user-dialogue", "repo-read", "repo-write", "shell", "git", "network",
    "web-research", "browser-interaction", "computer-use", "vision", "image-generation",
)
STALE_MINUTES = 120

PRODUCT_REQUIRED_SECTIONS = (
    "Vision", "Goals", "Non-Goals", "Users / Audience", "Core Experience",
    "Requirements", "Constraints", "Success Criteria", "Open Questions",
)
PRODUCT_PLACEHOLDERS = (
    "Describe the product in plain language:",
    "Replace with concrete goals discovered with the owner.",
    "Record important scope boundaries so future workers do not silently expand the product.",
    "Describe the primary user, player, operator, or audience",
    "Describe the most important journeys, workflows, interactions, or gameplay loop",
    "Examples only — replace or remove these during discovery:",
    "Record only constraints that materially affect the product or implementation:",
    "Define how the owner and future workers will know the product is succeeding.",
    "Track unresolved questions that could materially change product behavior",
)
PLAN_REQUIRED_SECTIONS = (
    "Technical Approach", "Architecture / Components", "Project Structure",
    "Dependencies / Integrations", "Verification Strategy", "Risks / Unknowns",
    "Requirement Coverage",
)
PLAN_PLACEHOLDERS = (
    "Replace with the chosen implementation approach",
    "Replace with the major components",
    "Replace with the expected source/test/runtime structure",
    "Replace with consequential dependencies",
    "Replace with how quick/full/smoke checks prove project health",
    "Replace with unresolved technical risks",
    "Replace with a concise explanation of how accepted requirements map",
)
PLAN_SKELETON = """# Plan

Status: DRAFT

This is the current implementation strategy for the accepted product intent in `PRODUCT.md`. Keep it current when consequential technical strategy changes. Do not use it as a progress diary.

## Technical Approach

Replace with the chosen implementation approach, including language/framework/runtime choices and why they fit the product constraints.

## Architecture / Components

Replace with the major components, boundaries, data flows, and responsibilities future workers need to understand.

## Project Structure

Replace with the expected source/test/runtime structure and where major responsibilities live.

## Dependencies / Integrations

Replace with consequential dependencies, integrations, storage choices, platform services, and important version/compatibility constraints.

## Verification Strategy

Replace with how quick/full/smoke checks prove project health and what capability-dependent validation remains task-specific.

## Risks / Unknowns

Replace with unresolved technical risks, assumptions, experiments, or external uncertainties that could materially affect implementation.

## Requirement Coverage

Replace with a concise explanation of how accepted requirements map into the task graph, including any important sequencing or brownfield verification evidence.

When the plan and initial backlog are coherent, change `Status: DRAFT` to `Status: READY`, finish the planning task, run `roach.py ready`, perform the semantic PRODUCT → PLAN → task consistency pass, and then transition to execution.
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def base_branch() -> str:
    return os.environ.get("ROACH_BASE_BRANCH", "main").strip() or "main"


def stale_minutes() -> int:
    raw = os.environ.get("ROACH_STALE_MINUTES")
    if raw is None:
        return STALE_MINUTES
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit("ROACH_STALE_MINUTES must be an integer") from None
    if value < 0:
        raise SystemExit("ROACH_STALE_MINUTES must not be negative")
    return max(value, 15)


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a JSON object, returning (value, error) instead of exiting.

    `check` and `doctor` exist to explain a repository nobody can make sense
    of, so they must survive the thing most likely to be wrong with it. Dying
    on the first unreadable file reported one problem and hid every other.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"Missing {path.relative_to(ROOT).as_posix()}"
    except OSError as exc:
        return None, f"Cannot read {path.relative_to(ROOT).as_posix()}: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {path.relative_to(ROOT).as_posix()}: {exc}"
    if not isinstance(value, dict):
        return None, f"{path.relative_to(ROOT).as_posix()} must contain a JSON object"
    return value, None


def load(path: Path) -> dict[str, Any]:
    """Read a JSON object or abort. Use read_json where continuing is better."""
    value, error = read_json(path)
    if error is not None:
        raise SystemExit(error)
    assert value is not None
    return value


def save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    except OSError as exc:
        # No git on PATH, or ROOT is gone. Every caller already handles a
        # non-zero return, so degrade instead of raising out of a command that
        # has other useful work to do.
        return subprocess.CompletedProcess(["git", *args], 1, "", str(exc))


def git_text(*args: str) -> str:
    out = git(*args)
    if out.returncode:
        raise SystemExit((out.stderr or out.stdout or f"git {' '.join(args)} failed").strip())
    return out.stdout.strip()


def has_origin() -> bool:
    return git("remote", "get-url", "origin").returncode == 0


_FETCHED = False


def reset_remote_cache() -> None:
    """Forget that origin was refreshed. Tests drive many scenarios in one process."""
    global _FETCHED
    _FETCHED = False


def fetch_remote(force: bool = False) -> None:
    """Refresh `origin` at most once per process.

    A single command can consult shared state several times -- `adopt` reads the
    remote claim, then loads the task, then publishes. Each of those used to pay
    for its own round trip, which on a slow link is the difference between a
    coordination command feeling instant and feeling broken. One invocation is
    short enough that a single refresh is still current at the end of it; pass
    `force` where a genuinely fresh read matters, such as after a push.
    """
    global _FETCHED
    if not has_origin():
        return
    if _FETCHED and not force:
        return
    out = git("fetch", "origin", "--prune")
    if not out.returncode:
        _FETCHED = True
    if out.returncode:
        detail = (out.stderr or out.stdout).strip()
        raise SystemExit(
            "Unable to refresh origin; refusing to make coordination decisions from stale remote state."
            + (f"\n{detail}" if detail else "")
        )


def remote_base_exists() -> bool:
    return has_origin() and git("rev-parse", "--verify", f"refs/remotes/origin/{base_branch()}").returncode == 0


def json_from_ref(ref: str, path: str) -> dict[str, Any] | None:
    out = git("show", f"{ref}:{path}")
    if out.returncode:
        return None
    try:
        value = json.loads(out.stdout)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def task_path(task_id: str) -> Path:
    if not TASK_RE.fullmatch(task_id):
        raise SystemExit("Task id must look like T001")
    return TASKS / f"{task_id}.json"


def clean_task(task: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in task.items() if not k.startswith("_")}


def task_files() -> list[Path]:
    return sorted(TASKS.glob("T*.json")) if TASKS.exists() else []


def local_tasks() -> list[dict[str, Any]]:
    result = []
    for path in task_files():
        task = load(path)
        task["_path"], task["_source"] = path, "local"
        result.append(task)
    return result


def local_tasks_tolerant() -> tuple[list[dict[str, Any]], list[str]]:
    """Every readable local task, plus one error per file that would not load.

    Diagnostic commands use this so a single corrupt record degrades their
    output instead of replacing it.
    """
    tasks: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in task_files():
        task, error = read_json(path)
        if error is not None or task is None:
            errors.append(error or f"Unreadable {path.relative_to(ROOT).as_posix()}")
            continue
        task["_path"], task["_source"] = path, "local"
        tasks.append(task)
    return tasks, errors


def shared_tasks(refresh: bool = False) -> list[dict[str, Any]]:
    if refresh:
        fetch_remote()
    if remote_base_exists():
        ref = f"origin/{base_branch()}"
        out = git("ls-tree", "-r", "--name-only", ref, ".agent/tasks")
        if not out.returncode:
            result = []
            for rel in sorted(x for x in out.stdout.splitlines() if x.endswith(".json")):
                task = json_from_ref(ref, rel)
                if task is not None:
                    task["_path"], task["_source"] = ROOT / rel, ref
                    result.append(task)
            return result
    return local_tasks()


def create_universe() -> list[dict[str, Any]]:
    combined = {str(t.get("id")): t for t in shared_tasks(refresh=True) if isinstance(t.get("id"), str)}
    combined.update({str(t.get("id")): t for t in local_tasks() if isinstance(t.get("id"), str)})
    return list(combined.values())


def by_id(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(t["id"]): t for t in tasks if isinstance(t.get("id"), str)}


def tokens(values: Iterable[str] | None) -> set[str]:
    return {x.strip().lower() for raw in values or [] for x in raw.split(",") if x.strip()}


def as_mapping(value: Any) -> dict[str, Any]:
    """`value` when it is a JSON object, an empty mapping otherwise.

    Coordination records come from files any worker may have written, so every
    nested object is `dict | something else`. Reading them through this keeps
    the callers free of repeated isinstance dances.
    """
    return value if isinstance(value, dict) else {}


def claim_of(task: dict[str, Any]) -> dict[str, Any]:
    """The task's claim, or an empty mapping when it holds none."""
    return as_mapping(task.get("claim"))


def task_caps(task: dict[str, Any], key: str) -> set[str]:
    value = task.get(key, [])
    return {str(x).lower() for x in value} if isinstance(value, list) else set()


def local_state() -> dict[str, Any]:
    return load(STATE_PATH)


def coordination_state(refresh: bool = False) -> dict[str, Any]:
    if refresh:
        fetch_remote()
    if remote_base_exists():
        state = json_from_ref(f"origin/{base_branch()}", ".agent/STATE.json")
        if state is not None:
            return state
    return local_state()


def branch_activity(task: dict[str, Any]) -> datetime | None:
    claim = claim_of(task)
    if not claim or not has_origin():
        return None
    branch = claim.get("branch")
    if not isinstance(branch, str):
        return None
    ref = f"refs/remotes/origin/{branch}"
    if git("rev-parse", "--verify", ref).returncode:
        return None
    out = git("log", "-1", "--format=%cI", ref)
    activity = parse_time(out.stdout.strip()) if not out.returncode else None
    claimed = parse_time(claim.get("claimed_at"))
    return activity if activity and (not claimed or activity >= claimed) else None


def claim_liveness(task: dict[str, Any]) -> tuple[bool, str]:
    claim = task.get("claim")
    if not isinstance(claim, dict):
        return False, "unclaimed"
    activity = branch_activity(task)
    if activity and now() - activity <= timedelta(minutes=stale_minutes()):
        return True, "recent remote branch activity"
    expiry = parse_time(claim.get("lease_expires_at"))
    if expiry and expiry > now():
        return True, f"lease until {claim.get('lease_expires_at')}"
    return False, "stale"


def live_claim(task: dict[str, Any]) -> bool:
    return claim_liveness(task)[0]


def phase_allows(kind: str, phase: str) -> bool:
    if phase in {"uninitialized", "discovery"}:
        return kind == "discovery"
    if phase == "planning":
        return kind in {"planning", "research", "design", "verification"}
    return phase == "execution"


def eligible(task: dict[str, Any], tasks: list[dict[str, Any]], capabilities: set[str] | None = None,
             phase: str | None = None, project_status: str | None = None,
             who: str | None = None) -> tuple[bool, str | None]:
    status = task.get("status")
    if status in TERMINAL_STATUSES:
        return False, str(status)
    state = None
    if phase is None or project_status is None:
        try:
            state = local_state()
        except SystemExit:
            state = {}
    phase = phase or str((state or {}).get("phase", "execution"))
    project_status = project_status or str((state or {}).get("project_status", "active"))
    if project_status != "active":
        return False, f"project is {project_status}"
    if status in ACTIVE_CLAIM_STATUSES:
        claim = claim_of(task)
        owner = claim.get("worker", "unknown")
        live, detail = claim_liveness(task)
        if who is not None and owner == who:
            # Telling a worker to forcibly adopt its own task is how a confused
            # session ends up fighting itself.
            return False, f"already claimed by you ({owner}, {detail})"
        if live:
            return False, (
                f"claimed by {owner} ({detail}); if that session is confirmed gone, "
                f"use `roach.py adopt {task.get('id')} --worker <your-id> --force --reason \"...\"`"
            )
        return False, (
            f"stale claim by {owner}; use `roach.py adopt {task.get('id')} --worker <your-id>` "
            "so the takeover remains recorded"
        )
    if not phase_allows(str(task.get("kind", "implementation")), phase):
        return False, "project is still planning" if phase == "planning" else f"project phase {phase} does not permit this work"
    index = by_id(tasks)
    for dep in task.get("depends_on", []):
        if dep not in index or index[dep].get("status") != "done":
            return False, f"waiting on {dep}"
    areas = set(task.get("areas", []))
    for other in tasks:
        if other.get("id") == task.get("id") or not live_claim(other):
            continue
        shared_areas = areas.intersection(other.get("areas", []))
        if shared_areas:
            # An area is exclusive while a claim is live, not a soft hint. Say
            # who holds it and how to proceed deliberately: a planner who tags a
            # whole backlog with two broad areas will otherwise watch it
            # serialise to one worker with no explanation.
            holder = claim_of(other).get("worker", "another worker")
            return False, (
                f"area {', '.join(sorted(shared_areas))} is held by {other.get('id')} ({holder}); "
                "wait, pick different work, or claim with --allow-area-overlap if the two "
                "genuinely do not touch the same files"
            )
    if status == "blocked":
        return False, "blocked"
    missing = task_caps(task, "requires") - (capabilities or set())
    if missing:
        return False, "missing capabilities: " + ", ".join(sorted(missing))
    return True, None


def task_sort_key(task: dict[str, Any], capabilities: set[str] | None = None) -> tuple[int, int, int]:
    priority = PRIORITY.get(str(task.get("priority", "normal")), 2)
    preferred = -len(task_caps(task, "prefers").intersection(capabilities or set()))
    match = TASK_RE.fullmatch(str(task.get("id", "")))
    return priority, preferred, int(match.group(1)) if match else 999999


def next_id(tasks: list[dict[str, Any]]) -> str:
    nums = [int(m.group(1)) for t in tasks if (m := TASK_RE.fullmatch(str(t.get("id", ""))))]
    return f"T{max(nums, default=-1) + 1:03d}"


MAX_WORKER_ID = 48


def sanitize(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    if not clean:
        return "agent"
    if len(clean) > MAX_WORKER_ID:
        raise SystemExit(
            f"Worker identity is too long ({len(clean)} > {MAX_WORKER_ID} characters after normalization). "
            "Truncating could silently merge two workers, so pick a shorter stable ID."
        )
    return clean


def deployment_findings() -> list[tuple[str, str]]:
    """Confirm the push-triggered-deploy protection is still wired up.

    The protection is two files pointing at each other. Replacing vercel.json
    wholesale when adding framework settings silently removes it, and nothing
    else would notice until the host bill did.
    """
    config, script = ROOT / "vercel.json", ROOT / "scripts" / "vercel-ignore.sh"
    if not config.exists():
        return []
    try:
        cfg = json.loads(config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [("vercel.json is unreadable, so deploy protection cannot be confirmed",
                 "fix the file; see docs/DEPLOYMENT.md")]
    if not script.exists():
        return [("vercel.json exists but scripts/vercel-ignore.sh is missing",
                 "restore the script from the template; see docs/DEPLOYMENT.md")]
    if "vercel-ignore.sh" not in str(cfg.get("ignoreCommand", "")):
        return [("vercel.json no longer runs scripts/vercel-ignore.sh, so every push will deploy",
                 'restore "ignoreCommand": "bash scripts/vercel-ignore.sh"; see docs/DEPLOYMENT.md')]
    return []


def head_sha() -> str | None:
    out = git("rev-parse", "HEAD")
    return out.stdout.strip() if out.returncode == 0 else None


def verification_still_applies(recorded: str | None) -> bool:
    """Does a verification run against `recorded` still describe HEAD?

    Publishing a claim or a finished task moves HEAD without touching a line of
    product code. Treating that as invalidation would demand a re-run after
    every coordination commit, and would block completion permanently, because
    recording the final task is itself a commit.
    """
    current = head_sha()
    if not recorded or not current or recorded == current:
        return True
    if git("rev-parse", "--verify", f"{recorded}^{{commit}}").returncode:
        return False
    touched = [f for f in git("diff", "--name-only", recorded, current).stdout.splitlines() if f]
    return all(is_coordination_path(f) for f in touched)


def worker(value: str | None) -> str:
    candidate = value or os.environ.get("ROACH_WORKER")
    if not candidate:
        raise SystemExit("Stable worker identity required. Pass --worker <id> or set ROACH_WORKER for this session.")
    return sanitize(candidate)


def optional_worker(value: str | None) -> str | None:
    """Worker identity when one is available, for commands that do not require it."""
    candidate = value or os.environ.get("ROACH_WORKER")
    return sanitize(candidate) if candidate else None


def require_base_branch(action: str) -> None:
    """Refuse a coordination change made from a task branch.

    Task records are tracked files. A claim made on a task branch is committed
    to that branch and silently reverts when the worker checks the base out
    again: shared state never sees the claim, the base advertises the task as
    free, and the worker cannot finish or integrate its own work.
    """
    if git("rev-parse", "--git-dir").returncode:
        return
    branch = git("branch", "--show-current").stdout.strip()
    expected = base_branch()
    if branch and branch != expected:
        raise SystemExit(
            f"{action} must run from {expected!r}; current branch is {branch!r}. "
            "Shared coordination changes made on a task branch can disappear on checkout. "
            f"Run `git checkout {expected}` first."
        )


def remote_task(task_id: str) -> dict[str, Any] | None:
    """The task as shared state sees it, or None when there is no shared state."""
    if not has_origin():
        return None
    return by_id(shared_tasks(refresh=True)).get(task_id)


UNFETCHED = object()


def refuse_if_claimed_elsewhere(task_id: str, who: str | None, force: bool, action: str,
                                remote: Any = UNFETCHED) -> None:
    """Stop a state change to work another worker still holds.

    A local task record can be arbitrarily stale, so `origin` decides. Without
    this, a worker whose checkout predates a claim could cancel, block, or
    adopt work somebody else is actively doing.

    Pass `remote` when the caller has already fetched the shared record, so one
    command does not pay for two round trips to the remote.
    """
    if remote is UNFETCHED:
        remote = remote_task(task_id)
    if not isinstance(remote, dict):
        return
    claim = remote.get("claim")
    if not isinstance(claim, dict) or not live_claim(remote):
        return
    owner = claim.get("worker")
    if who is not None and owner == who:
        return
    if force:
        return
    raise SystemExit(
        f"{task_id} is live-claimed by {owner} on origin/{base_branch()}; refusing to {action} it. "
        "Coordinate with its owner, wait for the claim to go stale, or pass --force deliberately."
    )


COORDINATION_ROOT = ".agent"
# Test suites live under .agent/ in this template but are product code, not
# coordination state: they must not ride along in a claim or heartbeat commit.
COORDINATION_EXCLUDED = (f"{COORDINATION_ROOT}/tests/",)


def is_coordination_path(rel: str) -> bool:
    return rel.startswith(f"{COORDINATION_ROOT}/") and not rel.startswith(COORDINATION_EXCLUDED)


def working_tree_changes() -> tuple[list[str], list[str]]:
    """Split uncommitted changes into coordination state and everything else.

    Publishing used to name one exact file, which meant a command could refuse
    to publish the very edits it had just required -- `accept-product` demands a
    real PROJECT.md and then called it an unrelated change. Coordination state
    is one unit; the boundary that matters is `.agent/` versus product code.
    """
    coordination: list[str] = []
    unrelated: list[str] = []
    for line in git("status", "--porcelain", "--untracked-files=all").stdout.splitlines():
        if not line.strip():
            continue
        rel = line[3:]
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        rel = rel.strip().strip('"')
        target = coordination if is_coordination_path(rel) else unrelated
        target.append(rel)
    return sorted(set(coordination)), sorted(set(unrelated))


def base_divergence(expected: str | None = None) -> tuple[int, int]:
    """(ahead, behind) commit counts for the local base against origin/<base>."""
    expected = expected or base_branch()
    ref = f"refs/remotes/origin/{expected}"
    ahead = [c for c in git("rev-list", f"{ref}..HEAD").stdout.splitlines() if c]
    behind = [c for c in git("rev-list", f"HEAD..{ref}").stdout.splitlines() if c]
    return len(ahead), len(behind)


def align_base_with_origin(expected: str) -> None:
    """Bring the local base up to origin, or refuse for a reason worth refusing for.

    Publishing used to require the local base to equal origin exactly, and to
    refuse otherwise. But "behind" is the normal steady state when two or three
    workers are publishing claims and heartbeats: every push by anyone else put
    everyone else into the refusing state until a human ran git by hand. The
    condition worth refusing is *ahead* -- local commits that a coordination
    publish must never carry along. Purely behind, with nothing local to lose,
    is a fast-forward and should simply happen.
    """
    if not has_origin() or not remote_base_exists():
        return
    ahead, behind = base_divergence(expected)
    if ahead:
        raise SystemExit(
            f"--publish refused: local {expected} has {ahead} commit(s) that origin/{expected} does not. "
            "A coordination publish must never carry unrelated local commits into shared history. "
            f"Push or reset them deliberately (`git push origin {expected}`), then retry."
        )
    if not behind:
        return
    out = git("merge", "--ff-only", f"refs/remotes/origin/{expected}")
    if out.returncode:
        raise SystemExit(
            f"local {expected} is {behind} commit(s) behind origin/{expected}, and your pending "
            "coordination edits collide with what another worker published, so it cannot "
            "fast-forward.\nRun `python scripts/roach.py reconcile` to rebase your pending "
            "coordination state onto current shared state."
        )
    print(f"Fast-forwarded {expected} to origin/{expected} ({behind} commit(s)).")


def safe_publish(message: str) -> None:
    """Commit and push pending coordination state, or refuse without side effects."""
    branch = git("branch", "--show-current").stdout.strip()
    expected = base_branch()
    if branch != expected:
        raise SystemExit(f"--publish requires branch {expected!r}; current branch is {branch!r}.")
    if has_origin():
        fetch_remote()
        align_base_with_origin(expected)
    coordination, unrelated = working_tree_changes()
    if unrelated:
        raise SystemExit(
            "Refusing to publish because the working tree also contains changes outside "
            f"{COORDINATION_ROOT}/: " + ", ".join(unrelated)
            + "\nCommit those separately, or add generated files to .gitignore."
        )
    if not coordination:
        print("Nothing to publish; coordination state is already committed.")
        return
    add = git("add", "-A", "--", *coordination)
    if add.returncode:
        raise SystemExit((add.stderr or add.stdout).strip())
    commit = git("commit", "-m", message)
    if commit.returncode:
        raise SystemExit((commit.stderr or commit.stdout).strip())
    if has_origin():
        out = git("push", "origin", expected)
        if out.returncode:
            # Another worker moved the base, or the network failed. Try to integrate
            # once, then push again.
            pull = git("pull", "--rebase", "origin", expected)
            if pull.returncode:
                git("rebase", "--abort")
            else:
                out = git("push", "origin", expected)
        if out.returncode:
            # Never leave the base branch ahead of origin. A stranded local commit
            # makes the up-to-date precondition above fail forever, which would wedge
            # every later coordination command for every worker in this repository.
            if git("rev-parse", "--verify", "HEAD~1").returncode == 0:
                git("reset", "--soft", "HEAD~1")
            else:
                git("update-ref", "-d", "HEAD")
            raise SystemExit(
                f"Push failed, so the local coordination commit was rolled back. "
                f"{expected} still matches origin/{expected} and your change is staged and intact. "
                "Resolve connectivity/permissions or an upstream conflict, then run "
                "`python scripts/roach.py publish` to retry."
            )
        fetch_remote(force=True)
    print("Published: " + ", ".join(coordination))


def try_publish(args: argparse.Namespace, message: str) -> None:
    """Publish when asked, and say how to finish the job when publishing fails.

    The state change has already been written by the time this runs. A command
    that mutated state and then died on a publish error used to leave no way
    forward, because re-running it hits a precondition it has itself satisfied.
    """
    if not getattr(args, "publish", False):
        return
    try:
        safe_publish(message)
    except SystemExit as exc:
        raise SystemExit(
            f"{exc}\n\nThe state change itself succeeded and is in your working tree. "
            "Resolve the above, then run `python scripts/roach.py publish` -- "
            "do not re-run this command."
        ) from None


ATTIC = ".roach-reconcile"


def pending_coordination_entries() -> tuple[list[tuple[str, bool]], list[str]]:
    """Pending `.agent/` paths as (path, was_untracked), plus unrelated dirty paths."""
    coordination: list[tuple[str, bool]] = []
    unrelated: list[str] = []
    for line in git("status", "--porcelain", "--untracked-files=all").stdout.splitlines():
        if not line.strip():
            continue
        code, rel = line[:2], line[3:]
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        rel = rel.strip().strip('"')
        if is_coordination_path(rel):
            coordination.append((rel, code == "??"))
        else:
            unrelated.append(rel)
    return coordination, sorted(set(unrelated))


def committed_blob(rel: str) -> str | None:
    out = git("show", f"HEAD:{rel}")
    return out.stdout if out.returncode == 0 else None


def park_in_attic(rel: str, content: str, note: str) -> str:
    """Keep a coordination edit that could not be replayed, outside `.agent/`.

    It must land outside the coordination root: anything under `.agent/` would
    be swept into the next publish, which is precisely the state reconcile
    exists to get the worker out of.
    """
    target = ROOT / ATTIC / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"{ATTIC}/{rel} ({note})"


def is_task_record(rel: str) -> bool:
    return rel.startswith(f"{COORDINATION_ROOT}/tasks/") and bool(
        TASK_RE.fullmatch(Path(rel).stem)
    )


def cmd_reconcile(args: argparse.Namespace) -> None:
    """Replay pending coordination edits on top of current shared state.

    Two workers creating a task from the same base both compute the same free
    ID. The push race catches it, and the loser was then wedged: `publish`
    refused because the base was behind, and `git pull` refused because the
    incoming commit wanted the same path. `doctor` recommended exactly those
    two commands. This is the missing third option -- and the same wedge occurs
    whenever any pending coordination edit collides with a published one.

    Nothing is discarded silently. An edit that cannot be replayed is parked
    outside `.agent/` and named in the report.
    """
    expected = base_branch()
    require_base_branch("reconcile")
    if not has_origin():
        raise SystemExit("reconcile needs an origin; there is no shared state to reconcile against.")
    fetch_remote()
    if not remote_base_exists():
        raise SystemExit(f"origin has no {expected} branch yet; there is nothing to reconcile against.")

    pending, unrelated = pending_coordination_entries()
    if unrelated:
        raise SystemExit(
            "Refusing to reconcile while the working tree also contains changes outside "
            f"{COORDINATION_ROOT}/: " + ", ".join(unrelated)
            + "\nCommit or stash those separately first."
        )
    ahead, behind = base_divergence(expected)
    if ahead:
        raise SystemExit(
            f"local {expected} has {ahead} commit(s) origin does not, so this is a divergence, "
            "not a stale checkout. Push or reset those commits deliberately, then reconcile."
        )
    if not behind:
        print("Already level with origin/" + expected + "; nothing to reconcile."
              + (" Run `publish` to share your pending coordination state." if pending else ""))
        return

    # Snapshot every pending edit, plus the committed version it was based on,
    # so a file upstream also changed can be told apart from one it did not.
    snapshot: dict[str, tuple[str | None, bool, str | None]] = {}
    for rel, untracked in pending:
        path = ROOT / rel
        content = path.read_text(encoding="utf-8") if path.exists() else None
        snapshot[rel] = (content, untracked, None if untracked else committed_blob(rel))

    def restore_snapshot() -> None:
        for rel_, (content_, _untracked, _base) in snapshot.items():
            if content_ is None:
                continue
            target = ROOT / rel_
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content_, encoding="utf-8")

    for rel, untracked in pending:
        if untracked:
            (ROOT / rel).unlink(missing_ok=True)
        else:
            git("checkout", "--", rel)

    merged = git("merge", "--ff-only", f"refs/remotes/origin/{expected}")
    if merged.returncode:
        restore_snapshot()
        raise SystemExit(
            f"Could not fast-forward {expected} even with coordination edits set aside; "
            "your edits were restored and nothing was lost.\n"
            + (merged.stderr or merged.stdout).strip()
        )

    known = {str(t.get("id")) for t in local_tasks() if isinstance(t.get("id"), str)}
    replayed: list[str] = []
    renumbered: list[str] = []
    parked: list[str] = []
    renames: dict[str, str] = {}

    for rel, (content, untracked, based_on) in sorted(snapshot.items()):
        if content is None:
            parked.append(f"{rel} (deleted locally; upstream version kept)")
            continue
        path = ROOT / rel
        if untracked:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                replayed.append(rel)
                continue
            if not is_task_record(rel):
                parked.append(park_in_attic(rel, content, "another worker published this path first"))
                continue
            # The documented ID race: two workers picked the same free number.
            old_id = Path(rel).stem
            new_id = next_id([{"id": i} for i in known])
            while new_id in known or task_path(new_id).exists():
                known.add(new_id)
                new_id = next_id([{"id": i} for i in known])
            record = json.loads(content)
            record["id"] = new_id
            save(task_path(new_id), record)
            known.add(new_id)
            renames[old_id] = new_id
            renumbered.append(f"{old_id} -> {new_id}  {record.get('title', '')}".rstrip())
            continue
        upstream_now = committed_blob(rel)
        if upstream_now == based_on:
            path.write_text(content, encoding="utf-8")
            replayed.append(rel)
            continue
        reason = "another worker changed this file; shared state kept"
        if is_task_record(rel):
            remote_record = read_json(path)[0] or {}
            claim = as_mapping(remote_record.get("claim"))
            if claim:
                reason = (
                    f"origin now shows it {remote_record.get('status')} under "
                    f"{claim.get('worker')}; shared state kept"
                )
        parked.append(park_in_attic(rel, content, reason))

    # A renumbered task may be referenced by another edit replayed alongside it.
    if renames:
        for task_file in task_files():
            record, error = read_json(task_file)
            if error is not None or record is None:
                continue
            changed = False
            for key in ("review_of", "correction_of"):
                if record.get(key) in renames:
                    record[key] = renames[record[key]]
                    changed = True
            deps = record.get("depends_on")
            if isinstance(deps, list) and any(d in renames for d in deps):
                record["depends_on"] = [renames.get(d, d) for d in deps]
                changed = True
            if changed:
                save(task_file, record)

    print(f"Fast-forwarded {expected} to origin/{expected} ({behind} commit(s)).")
    for label, items in (("Replayed", replayed), ("Renumbered", renumbered), ("Set aside", parked)):
        for item in items:
            print(f"  {label}: {item}")
    if renumbered:
        print("\nThe renumbered task(s) above kept their content and took a free id.")
    if parked:
        print(
            f"\nEdits under {ATTIC}/ could not be replayed without overwriting shared state. "
            "Read them, then re-run the original command if the change is still wanted."
        )
    if replayed or renumbered:
        print("\nNext: python scripts/roach.py publish")
    elif not parked:
        print("Nothing pending to replay.")


def cmd_publish(args: argparse.Namespace) -> None:
    """Commit and push whatever coordination state is pending.

    This is the retry path for every `--publish` that failed after its state
    change landed, and the recovery path `doctor` points at.
    """
    pending = working_tree_changes()[0]
    summary = ", ".join(Path(rel).name for rel in pending[:3]) or "coordination state"
    safe_publish(args.message or f"state: publish pending {summary}")


def cmd_capabilities(args: argparse.Namespace) -> None:
    if wants_json(args):
        emit_json({"standard": list(STANDARD_CAPABILITIES), "custom_tokens_allowed": True,
                   "token_pattern": TOKEN_RE.pattern})
        return
    print("Standard Roach capabilities:")
    for item in STANDARD_CAPABILITIES:
        print(f"  {item}")
    print("Custom lowercase capability tokens are also allowed.")


def wants_json(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_status(args: argparse.Namespace) -> None:
    tasks = shared_tasks(refresh=True)
    state = coordination_state()
    phase = str(state.get("phase", "execution"))
    project_status = str(state.get("project_status", "active"))
    caps = tokens(args.cap)
    counts = {s: sum(t.get("status") == s for t in tasks) for s in STATUSES}
    source = tasks[0].get("_source") if tasks else "local"
    claims = []
    for task in sorted((t for t in tasks if isinstance(t.get("claim"), dict)), key=task_sort_key):
        live, reason = claim_liveness(task)
        claims.append({
            "id": task.get("id"), "title": task.get("title"),
            "worker": task["claim"].get("worker"), "live": live, "reason": reason,
        })
    candidates: list[dict[str, Any]] = []
    if project_status == "active" and caps:
        eligible_tasks = sorted(
            (t for t in tasks if eligible(t, tasks, caps, phase, project_status)[0]),
            key=lambda t: task_sort_key(t, caps),
        )
        candidates = [{"id": t.get("id"), "title": t.get("title")} for t in eligible_tasks]

    if wants_json(args):
        emit_json({
            "source": source, "project_status": project_status, "phase": phase,
            "blocked": state.get("blocked"), "counts": counts, "claims": claims,
            "capabilities": sorted(caps),
            "next": candidates[0]["id"] if candidates else None,
            "eligible": [c["id"] for c in candidates],
        })
        return

    print(f"Roach status ({source})")
    print(f"  project_status:{project_status} | phase:{phase}")
    if state.get("blocked"):
        print(f"  reason:{state.get('blocked')}")
    print("  " + " | ".join(f"{s}:{counts[s]}" for s in ("planned", "claimed", "active", "blocked", "verify", "done", "cancelled")))
    for claim in claims:
        # ASCII only: this is console output, and the default Windows code page
        # renders anything else as a replacement character.
        print(f"  {claim['id']} {claim['title']} | {claim['worker']} "
              f"[{'LIVE' if claim['live'] else 'STALE'}: {claim['reason']}]")
    if project_status != "active":
        print(f"Next: none (project is {project_status})")
    elif caps:
        print("Next: " + (candidates[0]["id"] if candidates else "none; run `roach.py next --cap ... --explain`"))
    else:
        print("Next: inventory capabilities, then run `roach.py next --cap ...`.")


def cmd_next(args: argparse.Namespace) -> None:
    tasks = shared_tasks(refresh=True)
    state = coordination_state()
    phase, project_status, caps = str(state.get("phase", "execution")), str(state.get("project_status", "active")), tokens(args.cap)
    who = optional_worker(getattr(args, "worker", None))
    candidates = sorted((t for t in tasks if eligible(t, tasks, caps, phase, project_status)[0]), key=lambda t: task_sort_key(t, caps))

    def blockers() -> list[dict[str, Any]]:
        out = []
        for task in sorted(tasks, key=lambda t: task_sort_key(t, caps)):
            if task.get("status") in TERMINAL_STATUSES:
                continue
            ok, reason = eligible(task, tasks, caps, phase, project_status, who=who)
            if not ok:
                out.append({"id": task.get("id"), "reason": reason or "not eligible"})
        return out

    if wants_json(args):
        emit_json({
            "capabilities": sorted(caps), "phase": phase, "project_status": project_status,
            "candidates": [{
                "id": t.get("id"), "title": t.get("title", ""),
                "kind": t.get("kind", "implementation"),
                "preferred_match": sorted(task_caps(t, "prefers").intersection(caps)),
            } for t in candidates[: args.limit]],
            "blocked": blockers() if (args.explain or not candidates) else [],
        })
        return

    if not candidates:
        print("NONE")
        if args.explain:
            for entry in blockers():
                print(f"{entry['id']}\t{entry['reason']}")
        return
    for task in candidates[: args.limit]:
        matched = sorted(task_caps(task, "prefers").intersection(caps))
        suffix = f"\tpreferred-match={','.join(matched)}" if matched else ""
        print(f"{task['id']}\t{task.get('title','')}\t{task.get('kind','implementation')}{suffix}")


def make_task(*, task_id: str, kind: str, title: str, status: str = "planned", priority: str = "normal",
              depends_on: Iterable[str] = (), areas: Iterable[str] = (), requirements: Iterable[str] = (),
              requires: Iterable[str] = (), prefers: Iterable[str] = (), acceptance: Iterable[str] = (),
              verification: str | None = None, claim: dict[str, Any] | None = None,
              handoff: str | None = None, review_of: str | None = None,
              correction_of: str | None = None, verify: str | None = None) -> dict[str, Any]:
    return {
        "id": task_id, "kind": kind, "title": title, "status": status, "priority": priority,
        "depends_on": list(dict.fromkeys(depends_on)), "areas": list(dict.fromkeys(areas)),
        "requirements": list(dict.fromkeys(requirements)), "requires": sorted(set(requires)),
        "prefers": sorted(set(prefers)), "acceptance": list(dict.fromkeys(acceptance)),
        # An optional executable check for this task specifically. Project health
        # lives in VERIFY.json; this is the evidence that *this* work happened,
        # and it runs with the same privileges -- see docs/SECURITY.md.
        "verify": verify,
        "verification": verification, "claim": claim, "handoff": handoff,
        "review_of": review_of, "correction_of": correction_of,
        # Written by the coordinator, not by hand.
        "integration": None, "evidence": None, "completed_at": None, "commit": None,
    }


# Kinds whose work normally lands in the repository. A finished task of one of
# these with no commits anywhere is far more likely to be a mistake than a
# legitimately code-free result, so it must be waived explicitly.
CODE_PRODUCING_KINDS = {"implementation", "correction", "fix", "refactor", "spike"}


def in_git_repo() -> bool:
    return git("rev-parse", "--git-dir").returncode == 0


def branch_ref(branch: str) -> str | None:
    for ref in (f"refs/remotes/origin/{branch}", f"refs/heads/{branch}"):
        if git("rev-parse", "--verify", ref).returncode == 0:
            return ref
    return None


def work_evidence(task: dict[str, Any]) -> tuple[bool, str]:
    """Can the repository show that this task produced anything?

    Roach cannot check whether `--verification` prose is true -- that is stated
    plainly in AGENTS.md and is not going to change. It can check the cheaper,
    more basic question the record already has the data for: did any work
    actually land? A task could be claimed and finished with a confident
    sentence, no branch, and no commits, and the project would then pass its
    completion gate containing nothing.
    """
    if not in_git_repo():
        return True, "no git repository available to check"
    integration = task.get("integration")
    if isinstance(integration, dict) and integration.get("merge_commit"):
        return True, f"merged as {str(integration['merge_commit'])[:8]}"
    base = base_branch()
    claim = claim_of(task)
    branch = claim.get("branch")
    if isinstance(branch, str) and branch:
        ref = branch_ref(branch)
        if ref:
            commits = [c for c in git("rev-list", f"{base}..{ref}").stdout.splitlines() if c]
            if commits:
                return True, f"{len(commits)} unintegrated commit(s) on {branch}"
    # Work committed straight to the base branch since the claim was taken. Not
    # the recommended shape, but real work all the same.
    since = claim.get("base_commit")
    if isinstance(since, str) and since and git("rev-parse", "--verify", f"{since}^{{commit}}").returncode == 0:
        touched = [f for f in git("diff", "--name-only", since, "HEAD").stdout.splitlines() if f]
        product = [f for f in touched if not is_coordination_path(f)]
        if product:
            return True, f"{len(product)} file(s) changed on {base} since the claim"
    return False, "no commits on the claimed branch and no product change since the claim"


def run_task_verify(task: dict[str, Any]) -> tuple[str, int | None]:
    """Run a task's own check, if it declared one. Returns (outcome, exit code)."""
    command = task.get("verify")
    if command is None or (isinstance(command, str) and not command.strip()):
        return "none", None
    print(f"Running task check: {describe_command(command)}")
    returncode = run_command(command)
    return ("passed" if returncode == 0 else "failed"), returncode


def active_requirement_links(task: dict[str, Any]) -> list[str]:
    """Keep follow-up work linked only to requirements that are still current."""
    current = requirement_ids()
    return [req for req in task.get("requirements", []) if req in current]


def reactivate_completed_project(action: str) -> bool:
    """Move a coherent completed project back to execution without an invalid intermediate state."""
    state = load(STATE_PATH)
    status, phase = state.get("project_status"), state.get("phase")
    if status in {"blocked", "paused"}:
        raise SystemExit(
            f"Cannot {action} while the project is {status}. Resolve the reason, then run "
            "`roach.py project-status active --publish`."
        )
    if status == "complete" and phase == "complete":
        errors = readiness_errors(require_active=False)
        if errors:
            raise SystemExit(f"Cannot {action} from completed state:\n- " + "\n- ".join(errors))
        state["project_status"], state["phase"], state["blocked"] = "active", "execution", None
        state["updated_at"] = iso()
        save(STATE_PATH, state)
        return True
    if status != "active":
        raise SystemExit(f"Cannot {action} while project_status is {status!r}.")
    if phase not in {"planning", "execution"}:
        raise SystemExit(
            f"Cannot {action} during phase {phase!r}. Finish the current product-discovery cycle first."
        )
    return False


def terminal_claim_guidance(task: dict[str, Any]) -> str:
    task_id, status, kind = task.get("id"), task.get("status"), task.get("kind")
    if status == "cancelled":
        return (
            f"{task_id} is cancelled and remains immutable history. Create a replacement task if the work is wanted again."
        )
    if kind == "discovery":
        return (
            f"{task_id} is completed product history and is not reopened. "
            "Run `roach.py transition discovery --publish` to create a new product-revision cycle."
        )
    if kind == "planning":
        return (
            f"{task_id} is completed planning history and is not reopened. "
            "Run `roach.py transition planning --publish` to create a new planning cycle."
        )
    return (
        f"{task_id} is completed and remains immutable history. "
        f"Run `roach.py review {task_id} --publish` for an independent review, or "
        f"`roach.py correct {task_id} --title \"...\" --acceptance \"...\" --publish` for known corrective work."
    )


def cmd_create(args: argparse.Namespace) -> None:
    tasks = create_universe()
    index = by_id(tasks)
    if args.id:
        task_id = args.id
        if task_id in index:
            raise SystemExit(f"Task {task_id} already exists")
    else:
        # Skip ids already taken locally or on origin. This does NOT make
        # concurrent creation safe: two workers at the same base still compute
        # the same free number. The push race is what catches that -- the second
        # worker reconciles and recreates. See docs/MULTI_AGENT.md.
        task_id = next_id(tasks)
        while task_id in index or task_path(task_id).exists():
            task_id = next_id([*tasks, {"id": task_id}])
    if not TASK_RE.fullmatch(task_id):
        raise SystemExit("--id must look like T001")
    title = args.title.strip()
    if not title:
        raise SystemExit("--title must contain a meaningful task name")
    kind = args.kind.strip()
    if not TOKEN_RE.fullmatch(kind):
        raise SystemExit("--kind must be a lowercase capability-style token such as implementation or product-feedback")
    acceptance = [item.strip() for item in args.acceptance or [] if item.strip()]
    if not acceptance:
        raise SystemExit(
            "At least one --acceptance criterion is required so future workers know what done means."
        )
    depends_on = args.depends_on or []
    invalid_dependencies = [dep for dep in depends_on if dep == task_id or dep not in index]
    if invalid_dependencies:
        raise SystemExit("Unknown or invalid dependencies: " + ", ".join(invalid_dependencies))
    requirements = args.requirement or []
    known_requirements = requirement_ids()
    invalid_requirements = [
        req for req in requirements
        if not re.fullmatch(r"(?:FR|QR)-\d{3,}", req) or req not in known_requirements
    ]
    if invalid_requirements:
        raise SystemExit(
            "Unknown or invalid active requirements: " + ", ".join(invalid_requirements)
            + ". Define current scope in .agent/PRODUCT.md before linking a task to it."
        )
    required_caps, preferred_caps = tokens(args.requires), tokens(args.prefers)
    invalid_caps = sorted(cap for cap in required_caps | preferred_caps if not TOKEN_RE.fullmatch(cap))
    if invalid_caps:
        raise SystemExit("Invalid capability tokens: " + ", ".join(invalid_caps))
    task = make_task(
        task_id=task_id, kind=kind, title=title, priority=args.priority,
        depends_on=depends_on, areas=args.area or [], requirements=requirements,
        requires=required_caps, prefers=preferred_caps, acceptance=acceptance,
        verify=(getattr(args, "verify", None) or "").strip() or None,
    )
    save(task_path(task_id), task)
    print(f"Created {task_id}: {title}")
    try_publish(args, f"task({task_id}): publish new work")


def cmd_review(args: argparse.Namespace) -> None:
    """Create an independently claimable review without rewriting completed history."""
    require_base_branch("review")
    tasks = create_universe()
    target = by_id(tasks).get(args.task)
    if target is None:
        raise SystemExit(f"Unknown task {args.task}")
    if target.get("status") != "done":
        raise SystemExit(f"{args.task} must be done before an independent review is created")
    existing = next((
        task for task in tasks
        if task.get("review_of") == args.task and task.get("status") not in TERMINAL_STATUSES
    ), None)
    if existing:
        raise SystemExit(
            f"{existing.get('id')} already reviews {args.task}; claim or complete that review instead of duplicating it"
        )
    task_id = next_id(tasks)
    title = (args.title or f"Review {args.task}: {target.get('title', 'completed work')}").strip()
    if not title:
        raise SystemExit("--title must contain a meaningful review name")
    acceptance = [item.strip() for item in args.acceptance or [] if item.strip()] or [
        f"independently verify {args.task} against its recorded acceptance criteria and current linked requirements",
        "record concrete review evidence and clearly identify every confirmed defect for linked correction work",
    ]
    required = tokens(args.requires) or {"repo-read"}
    preferred = task_caps(target, "prefers") | tokens(args.prefers)
    invalid_caps = sorted(cap for cap in required | preferred if not TOKEN_RE.fullmatch(cap))
    if invalid_caps:
        raise SystemExit("Invalid capability tokens: " + ", ".join(invalid_caps))
    reactivated = reactivate_completed_project(f"review {args.task}")
    review = make_task(
        task_id=task_id, kind="verification", title=title, priority=args.priority,
        depends_on=[args.task], areas=target.get("areas", []),
        requirements=active_requirement_links(target), requires=required, prefers=preferred,
        acceptance=acceptance, review_of=args.task,
    )
    save(task_path(task_id), review)
    prefix = "Reactivated the completed project and created" if reactivated else "Created"
    print(f"{prefix} {task_id} to review {args.task}. Claim {task_id}; do not reopen {args.task}.")
    try_publish(args, f"review({task_id}): independently verify {args.task}")


def cmd_correct(args: argparse.Namespace) -> None:
    """Create corrective work linked to a completed task or completed review."""
    require_base_branch("correct")
    tasks = create_universe()
    target = by_id(tasks).get(args.task)
    if target is None:
        raise SystemExit(f"Unknown task {args.task}")
    if target.get("status") != "done":
        raise SystemExit(
            f"{args.task} must be done before correction work is created. Finish the review with evidence first."
        )
    task_id = next_id(tasks)
    title = args.title.strip()
    if not title:
        raise SystemExit("--title must contain a meaningful correction name")
    kind = args.kind.strip()
    if not TOKEN_RE.fullmatch(kind):
        raise SystemExit("--kind must be a lowercase capability-style token such as implementation or verification")
    acceptance = [item.strip() for item in args.acceptance or [] if item.strip()]
    if not acceptance:
        raise SystemExit("At least one --acceptance criterion is required for corrective work")
    required = {"repo-write"} | tokens(args.requires)
    preferred = task_caps(target, "prefers") | tokens(args.prefers)
    invalid_caps = sorted(cap for cap in required | preferred if not TOKEN_RE.fullmatch(cap))
    if invalid_caps:
        raise SystemExit("Invalid capability tokens: " + ", ".join(invalid_caps))
    reactivated = reactivate_completed_project(f"correct {args.task}")
    correction = make_task(
        task_id=task_id, kind=kind, title=title, priority=args.priority,
        depends_on=[args.task], areas=target.get("areas", []),
        requirements=active_requirement_links(target), requires=required, prefers=preferred,
        acceptance=acceptance, correction_of=args.task,
    )
    save(task_path(task_id), correction)
    prefix = "Reactivated the completed project and created" if reactivated else "Created"
    print(f"{prefix} {task_id} to correct findings from {args.task}.")
    try_publish(args, f"correct({task_id}): address findings from {args.task}")


def cmd_claim(args: argparse.Namespace) -> None:
    require_base_branch("claim")
    tasks = shared_tasks(refresh=True)
    state, caps = coordination_state(), tokens(args.cap)
    task = by_id(tasks).get(args.task)
    if task is None:
        # A task this worker created but has not published yet is invisible in
        # shared state. Fall back to the local record only when origin has never
        # seen the task, so a stale local copy can never mask a live remote claim.
        task = by_id(local_tasks()).get(args.task)
        if task is None:
            raise SystemExit(f"Unknown task {args.task}")
        tasks = [*tasks, task]
    if task.get("status") in TERMINAL_STATUSES:
        raise SystemExit(terminal_claim_guidance(task))
    who = worker(args.worker)
    ok, reason = eligible(task, tasks, caps, str(state.get("phase", "execution")),
                          str(state.get("project_status", "active")), who=who)
    if not ok and not (getattr(args, "allow_area_overlap", False) and "area " in str(reason)):
        raise SystemExit(f"{args.task} is not claimable: {reason}")
    clean = clean_task(task)
    clean["status"], clean["verification"] = "claimed", None
    clean["claim"] = {
        "worker": who, "claimed_at": iso(),
        "lease_expires_at": iso(now() + timedelta(minutes=args.lease_minutes)),
        "branch": args.branch or f"roach/{args.task}-{who}",
        # Where the base stood when this work started. Finishing uses it to tell
        # "nothing happened" apart from "work landed straight on the base".
        "base_commit": head_sha(),
    }
    clean["handoff"] = None
    save(task_path(args.task), clean)
    print(f"Claimed {args.task} as {who}; branch {clean['claim']['branch']}.")
    try_publish(args, f"claim({args.task}): publish task ownership")


def require_owner(task: dict[str, Any], who: str) -> dict[str, Any]:
    claim = task.get("claim")
    if not isinstance(claim, dict) or claim.get("worker") != who:
        raise SystemExit(f"{task.get('id')} is not owned by {who}")
    return claim


def mutable_task(task_id: str, who: str | None = None) -> dict[str, Any]:
    """Load a task for a state change, refusing when shared state has moved on.

    A local record can be arbitrarily stale: a worker may have been idle long
    enough for its lease to expire and another worker to take the task. Acting
    on the local copy alone would silently overwrite that. Only shared state
    that positively contradicts this worker is treated as authoritative --
    an unpublished local claim is normal and must keep working offline.
    """
    local = load(task_path(task_id))
    if not has_origin():
        return local
    remote = by_id(shared_tasks(refresh=True)).get(task_id)
    if remote is None:
        return local
    if remote.get("status") in TERMINAL_STATUSES and local.get("status") not in TERMINAL_STATUSES:
        raise SystemExit(
            f"{task_id} is already {remote.get('status')} on origin/{base_branch()}. "
            "Refresh this worktree before changing it further."
        )
    remote_claim = claim_of(remote)
    owner = remote_claim.get("worker")
    if who is not None and owner and owner != who and live_claim(remote):
        raise SystemExit(
            f"{task_id} is now owned by {owner} on origin/{base_branch()} (your local copy is stale). "
            "Re-sync and pick different work rather than overwriting a live claim."
        )
    return local


def cmd_heartbeat(args: argparse.Namespace) -> None:
    who = worker(args.worker)
    task = mutable_task(args.task, who)
    claim = require_owner(task, who)
    claim["lease_expires_at"] = iso(now() + timedelta(minutes=args.lease_minutes))
    if task.get("status") == "claimed":
        task["status"] = "active"
    save(task_path(args.task), task)
    print(f"Refreshed {args.task} lease for {who}.")
    try_publish(args, f"heartbeat({args.task}): refresh task ownership")


def cmd_release(args: argparse.Namespace) -> None:
    who = worker(args.worker)
    task = mutable_task(args.task, who)
    if not task.get("claim"):
        raise SystemExit(f"{args.task} is not currently claimed")
    require_owner(task, who)
    task["claim"] = None
    if task.get("status") in ACTIVE_CLAIM_STATUSES:
        task["status"] = "planned"
    if args.handoff:
        task["handoff"] = args.handoff.strip()
    save(task_path(args.task), task)
    print(f"Released {args.task}.")
    try_publish(args, f"release({args.task}): release task ownership")


def cmd_finish(args: argparse.Namespace) -> None:
    who = worker(args.worker)
    task = mutable_task(args.task, who)
    if task.get("status") not in ACTIVE_CLAIM_STATUSES:
        raise SystemExit(f"{args.task} must be claimed/active/verify before it can be finished")
    require_owner(task, who)
    verification = args.verification.strip()
    if not verification:
        raise SystemExit("--verification is required")

    found, detail = work_evidence(task)
    waived = getattr(args, "no_work", False)
    kind = str(task.get("kind", "implementation"))
    if not found and kind in CODE_PRODUCING_KINDS and not waived:
        raise SystemExit(
            f"{args.task} is a {kind} task but the repository shows no work for it: {detail}.\n"
            "Roach cannot check whether --verification text is true, but it can check that "
            "something happened. Push the task branch and run "
            f"`python scripts/roach.py integrate {args.task} --worker {who} --push` first, or pass "
            "--no-work if this task genuinely produced no repository change."
        )

    outcome, code = ("skipped", None) if getattr(args, "skip_task_check", False) else run_task_verify(task)
    if outcome == "failed":
        raise SystemExit(
            f"{args.task} declares its own check and it failed (exit {code}); refusing to mark it done.\n"
            f"  {task.get('verify')}\n"
            "Fix the work, or pass --skip-task-check deliberately if the check itself is wrong."
        )

    task.update(status="done", verification=verification, claim=None, handoff=None,
                completed_at=iso(), commit=head_sha())
    task["evidence"] = {
        "work": detail,
        "work_waived": bool(not found and waived),
        "task_check": outcome,
    }
    save(task_path(args.task), task)
    summary = "no repository change, waived" if (not found and waived) else detail
    print(f"Marked {args.task} done ({summary}"
          + (f"; task check {outcome}" if outcome != "none" else "") + ").")
    try_publish(args, f"finish({args.task}): record task completion")


def cmd_block(args: argparse.Namespace) -> None:
    refuse_if_claimed_elsewhere(args.task, optional_worker(args.worker), getattr(args, "force", False), "block")
    task = mutable_task(args.task)
    if task.get("status") in TERMINAL_STATUSES:
        raise SystemExit(f"{args.task} is already {task.get('status')}")
    reason = args.reason.strip()
    if not reason:
        raise SystemExit("--reason is required")
    if task.get("claim"):
        require_owner(task, worker(args.worker))
    task.update(status="blocked", claim=None, verification=None, handoff=f"BLOCKED: {reason}")
    save(task_path(args.task), task)
    print(f"Blocked {args.task}: {reason}")
    try_publish(args, f"block({args.task}): record blocker")


def cmd_unblock(args: argparse.Namespace) -> None:
    task = mutable_task(args.task)
    if task.get("status") != "blocked":
        raise SystemExit(f"{args.task} is not blocked")
    task.update(status="planned", claim=None, verification=None, handoff=None)
    save(task_path(args.task), task)
    print(f"Unblocked {args.task}.")
    try_publish(args, f"unblock({args.task}): clear blocker")


def cmd_cancel(args: argparse.Namespace) -> None:
    refuse_if_claimed_elsewhere(args.task, optional_worker(args.worker), getattr(args, "force", False), "cancel")
    task = mutable_task(args.task)
    if task.get("status") in TERMINAL_STATUSES:
        raise SystemExit(f"{args.task} is already {task.get('status')}")
    reason = args.reason.strip()
    if not reason:
        raise SystemExit("--reason is required")
    if task.get("claim"):
        require_owner(task, worker(args.worker))
    task.update(status="cancelled", claim=None, handoff=None, verification=f"cancelled: {reason}")
    save(task_path(args.task), task)
    print(f"Cancelled {args.task}: {reason}")
    try_publish(args, f"cancel({args.task}): retire work")


def markdown_sections(text: str) -> dict[str, str]:
    """Map heading text to its body, at any heading level.

    A body runs to the next heading of the same or a higher level, so
    sub-headings stay inside their parent: a Requirements section split into
    `### Functional` and `### Quality` is still one Requirements section. Only
    `##` used to be recognised, which meant a PRODUCT.md written with `###`
    headings had no required sections at all -- and said so in a way that
    pointed at the content rather than at the heading level.
    """
    matches = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", text, re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        level, start, end = len(match.group(1)), match.end(), len(text)
        for later in matches[index + 1:]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        sections[match.group(2).strip().casefold()] = text[start:end].strip()
    return sections


REQ_ID_RE = re.compile(r"(?:FR|QR)-\d{3,}")
LIST_MARKER_RE = re.compile(r"^(?:[-*+]\s+|#{1,6}\s+|\d+[.)]\s+)")
# The class deliberately contains the characters a linter calls ambiguous --
# colon, pipe, en dash, em dash, hyphen -- because authors type all of them as
# the separator between a requirement id and its text.
REQ_SEPARATOR_RE = re.compile(r"^\s*[:|–—-]?\s*")  # noqa: RUF001


def strip_emphasis(text: str) -> str:
    return re.sub(r"[*_`]", "", text).strip()


def parse_requirement_line(line: str) -> tuple[str, str] | None:
    """Read one requirement from a list item, table row, or heading.

    Requirements used to be recognised only as `- **FR-001**: text`. A section
    written as a markdown table produced no requirements at all, silently:
    linking a task to one was then rejected as unknown, coverage checks passed
    against whatever subset happened to parse, and completion gated on that
    same subset. The most important file in the method deserves a reader that
    copes with ordinary markdown.
    """
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("|"):
        cells = [strip_emphasis(cell) for cell in stripped.strip().strip("|").split("|")]
        position = next((i for i, cell in enumerate(cells) if REQ_ID_RE.fullmatch(cell)), None)
        if position is None:
            return None
        description = " ".join(cell for i, cell in enumerate(cells) if i != position and cell)
        return cells[position], description.strip()
    body = strip_emphasis(LIST_MARKER_RE.sub("", stripped))
    match = REQ_ID_RE.match(body)
    if match is None:
        return None
    return match.group(0), REQ_SEPARATOR_RE.sub("", body[match.end():]).strip()


def requirement_lines() -> list[str]:
    return markdown_sections(product_text()).get("requirements", "").splitlines()


def requirement_format_problems() -> list[str]:
    """Structural lines that name a requirement but could not be read as one.

    Only lines already shaped like a declaration -- a list item, table row, or
    heading -- are considered, so prose that mentions another requirement in
    passing is not mistaken for a malformed one.
    """
    problems = []
    for line in requirement_lines():
        stripped = line.strip()
        structural = stripped.startswith("|") or bool(LIST_MARKER_RE.match(stripped))
        if not structural or not REQ_ID_RE.search(stripped):
            continue
        parsed = parse_requirement_line(line)
        if parsed is None:
            problems.append(f"cannot read a requirement from: {stripped[:70]}")
        elif not parsed[1]:
            problems.append(f"{parsed[0]} has no requirement text")
    return problems


def product_text() -> str:
    return PRODUCT_PATH.read_text(encoding="utf-8") if PRODUCT_PATH.exists() else ""


def product_status_line() -> str | None:
    match = re.search(r"^Status:\s*(.+?)\s*$", product_text(), re.M)
    return match.group(1).strip() if match else None


def product_requirements() -> list[tuple[str, str]]:
    parsed = (parse_requirement_line(line) for line in requirement_lines())
    return [entry for entry in parsed if entry is not None]


def requirement_ids() -> set[str]:
    return {req for req, _ in product_requirements()}


def duplicate_requirement_ids() -> list[str]:
    counts = Counter(req for req, _ in product_requirements())
    return sorted(req for req, count in counts.items() if count > 1)


def section_shortfall(body: str) -> str | None:
    """Describe why a section says nothing, or None when it has real content."""
    text = " ".join(re.sub(r"[`*_#>\-\[\]()]", " ", body).split())
    if not text:
        return "is empty"
    if text.lower().strip(" .!") in FILLER_TEXT:
        return f"contains only filler ({text.strip()!r})"
    if len(text) < MIN_SECTION_CHARS:
        return f"has {len(text)} characters of content; needs at least {MIN_SECTION_CHARS}"
    return None


def product_structure_errors() -> list[str]:
    if not PRODUCT_PATH.exists():
        return ["missing .agent/PRODUCT.md"]
    text, sections, errors = product_text(), markdown_sections(product_text()), []
    for section in PRODUCT_REQUIRED_SECTIONS:
        body = sections.get(section.casefold())
        if body is None:
            errors.append(f"PRODUCT.md missing required section: {section}")
        else:
            shortfall = section_shortfall(body)
            if shortfall:
                errors.append(f"PRODUCT.md section {section!r} {shortfall}")
    for marker in PRODUCT_PLACEHOLDERS:
        if marker in text:
            errors.append(f"PRODUCT.md still contains template placeholder: {marker}")
    reqs = product_requirements()
    if not reqs:
        errors.append(
            "PRODUCT.md defines no active FR-### or QR-### requirements. Declare each one on its "
            "own line, as a list item (`- **FR-001**: ...`), a table row, or a heading."
        )
    errors.extend(f"PRODUCT.md Requirements: {problem}" for problem in requirement_format_problems())
    duplicates = duplicate_requirement_ids()
    if duplicates:
        errors.append("PRODUCT.md contains duplicate requirement IDs: " + ", ".join(duplicates))
    if not PROJECT_PATH.exists() or "UNINITIALIZED TEMPLATE" in PROJECT_PATH.read_text(encoding="utf-8"):
        errors.append("PROJECT.md still has the uninitialized summary placeholder")
    return errors


def set_product_status(status: str) -> None:
    text, line = product_text(), f"Status: {status}"
    if re.search(r"^Status:", text, re.M):
        text = re.sub(r"^Status:.*$", line, text, count=1, flags=re.M)
    else:
        text = text.replace("# Product\n", f"# Product\n\n{line}\n", 1)
    PRODUCT_PATH.write_text(text, encoding="utf-8")


def ensure_plan_skeleton() -> None:
    if not PLAN_PATH.exists():
        PLAN_PATH.write_text(PLAN_SKELETON, encoding="utf-8")


def plan_status_line() -> str | None:
    if not PLAN_PATH.exists():
        return None
    match = re.search(r"^Status:\s*(.+?)\s*$", PLAN_PATH.read_text(encoding="utf-8"), re.M)
    return match.group(1).strip() if match else None


def set_plan_status(status: str) -> None:
    if not PLAN_PATH.exists():
        ensure_plan_skeleton()
    text, line = PLAN_PATH.read_text(encoding="utf-8"), f"Status: {status}"
    if re.search(r"^Status:", text, re.M):
        text = re.sub(r"^Status:.*$", line, text, count=1, flags=re.M)
    else:
        text = text.replace("# Plan\n", f"# Plan\n\n{line}\n", 1)
    PLAN_PATH.write_text(text, encoding="utf-8")


def plan_errors() -> list[str]:
    if not PLAN_PATH.exists():
        return ["missing .agent/PLAN.md"]
    text, sections, errors = PLAN_PATH.read_text(encoding="utf-8"), markdown_sections(PLAN_PATH.read_text(encoding="utf-8")), []
    if (plan_status_line() or "").upper() != "READY":
        errors.append("PLAN.md status must be READY")
    for section in PLAN_REQUIRED_SECTIONS:
        body = sections.get(section.casefold())
        if body is None:
            errors.append(f"PLAN.md missing required section: {section}")
        elif not body.strip():
            errors.append(f"PLAN.md section is empty: {section}")
    for marker in PLAN_PLACEHOLDERS:
        if marker in text:
            errors.append(f"PLAN.md still contains template placeholder: {marker}")
    return errors


def discovery_acceptance(task_id: str) -> list[str]:
    return [
        ".agent/PRODUCT.md captures the owner's accepted product intent with no critical open questions that block planning",
        ".agent/PROJECT.md contains a concise orientation summary instead of the template placeholder",
        ".agent/STATE.json records product_definition.status as accepted and phase as planning",
        f"a planning task depends on {task_id} and will produce PLAN.md, VERIFY.json, and the initial execution backlog",
    ]


def ensure_discovery_task() -> str:
    tasks = create_universe()
    open_task = next((t for t in tasks if t.get("kind") == "discovery" and t.get("status") not in TERMINAL_STATUSES), None)
    if open_task:
        return str(open_task["id"])
    task_id = next_id(tasks)
    save(task_path(task_id), make_task(
        task_id=task_id, kind="discovery", title="Clarify changed product intent with owner", priority="urgent",
        areas=["product-definition"], requires=["repo-write", "user-dialogue"], prefers=["web-research"],
        acceptance=discovery_acceptance(task_id),
    ))
    return task_id


def ensure_planning_task(after_task_id: str | None = None, title: str = "Plan product implementation") -> str:
    tasks = create_universe()
    existing = next((
        t for t in tasks
        if t.get("kind") == "planning" and t.get("status") not in TERMINAL_STATUSES
        and (after_task_id is None or after_task_id in t.get("depends_on", []))
    ), None)
    if existing:
        return str(existing["id"])
    task_id = next_id(tasks)
    save(task_path(task_id), make_task(
        task_id=task_id, kind="planning", title=title, priority="urgent",
        depends_on=[after_task_id] if after_task_id else [], areas=["project-planning"],
        requires=["repo-write"], prefers=["shell", "web-research"],
        acceptance=[
            ".agent/PLAN.md defines the current technical approach and required core planning sections",
            ".agent/VERIFY.json contains the required practical project-health command",
            "the initial execution backlog covers every active accepted requirement",
            "python3 scripts/roach.py ready reports READY after the planning task is finished",
        ],
    ))
    return task_id


def current_owned_discovery_task(who: str) -> dict[str, Any] | None:
    return next((
        task for task in local_tasks()
        if task.get("kind") == "discovery" and task.get("status") in ACTIVE_CLAIM_STATUSES
        and isinstance(task.get("claim"), dict) and task["claim"].get("worker") == who
    ), None)


def cmd_accept_product(args: argparse.Namespace) -> None:
    state = load(STATE_PATH)
    if state.get("project_status") != "active":
        raise SystemExit("Product acceptance requires project_status active.")
    if state.get("phase") not in {"uninitialized", "discovery"}:
        raise SystemExit("Product acceptance is only valid during uninitialized/discovery.")
    who = worker(args.worker)
    discovery = current_owned_discovery_task(who)
    if discovery is None:
        raise SystemExit("accept-product requires an actively claimed discovery task owned by this worker")
    errors = product_structure_errors()
    if errors:
        raise SystemExit("Cannot accept product intent:\n- " + "\n- ".join(errors))
    verification = args.verification.strip()
    if not verification:
        raise SystemExit("--verification is required")
    discovery = clean_task(discovery)
    discovery.update(status="done", verification=verification, claim=None, handoff=None)
    save(task_path(str(discovery["id"])), discovery)
    state["product_definition"] = {"status": "accepted", "accepted_at": iso()}
    state["phase"], state["updated_at"] = "planning", iso()
    save(STATE_PATH, state)
    set_product_status("ACCEPTED")
    ensure_plan_skeleton()
    planning_id = ensure_planning_task(str(discovery["id"]))
    print(f"Accepted product intent, completed {discovery['id']}, moved to planning, and ensured planning task {planning_id}.")
    try_publish(args, f"product: accept intent, close {discovery['id']}, open {planning_id}")


def task_graph_errors(tasks: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    index = by_id(tasks)
    active_ids = {str(t.get("id")) for t in tasks if t.get("status") != "cancelled" and isinstance(t.get("id"), str)}
    graph: dict[str, list[str]] = {}
    for task in tasks:
        tid = str(task.get("id"))
        if tid not in active_ids:
            continue
        deps = []
        for dep in task.get("depends_on", []):
            if dep in index and index[dep].get("status") == "cancelled":
                errors.append(f"{tid} depends on cancelled task {dep}")
            elif dep in active_ids:
                deps.append(dep)
        graph[tid] = deps
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
        body = cycle[:-1]
        rotations = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        chosen = min(rotations)
        return (*chosen, chosen[0])

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in stack:
                i = stack.index(node)
                cyc = canonical_cycle([*stack[i:], node])
                if cyc not in seen_cycles:
                    seen_cycles.add(cyc)
                    errors.append("dependency cycle: " + " -> ".join(cyc))
            return
        visiting.add(node)
        stack.append(node)
        for dep in graph.get(node, []):
            visit(dep)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return errors


def readiness_errors(require_active: bool = True) -> list[str]:
    errors: list[str] = []
    state, state_error = read_json(STATE_PATH)
    if state_error is not None or state is None:
        return [state_error or "unreadable .agent/STATE.json"]
    if require_active and state.get("project_status") != "active":
        errors.append(f"project_status is {state.get('project_status')}, not active")
    if state.get("product_definition", {}).get("status") != "accepted":
        errors.append("product definition is not accepted")
    errors.extend(product_structure_errors())
    errors.extend(plan_errors())
    verify, verify_error = read_json(VERIFY_PATH)
    if verify_error is not None or verify is None:
        errors.append(verify_error or "unreadable .agent/VERIFY.json")
        verify = {}
    required, commands = verify.get("required_level"), verify.get("commands", {})
    if required not in {"quick", "full", "smoke"} or not isinstance(commands, dict) or not commands.get(required):
        errors.append("VERIFY.json required verification command is not configured")
    tasks, unreadable = local_tasks_tolerant()
    errors.extend(unreadable)
    errors.extend(task_graph_errors(tasks))
    substantive = [t for t in tasks if t.get("kind") not in {"discovery", "planning"} and t.get("status") != "cancelled"]
    if not substantive:
        errors.append("no post-planning work exists")
    if [t for t in tasks if t.get("kind") == "planning" and t.get("status") not in TERMINAL_STATUSES]:
        errors.append("planning task is not done/cancelled")
    known = requirement_ids()
    coverage_tasks = [t for t in tasks if t.get("kind") not in {"discovery", "planning"} and t.get("status") != "cancelled"]
    referenced = {r for t in coverage_tasks for r in t.get("requirements", []) if isinstance(r, str)}
    active_referenced = {r for t in coverage_tasks if t.get("status") not in TERMINAL_STATUSES for r in t.get("requirements", []) if isinstance(r, str)}
    unknown, uncovered = active_referenced - known, known - referenced
    if unknown:
        errors.append("active tasks reference unknown requirements: " + ", ".join(sorted(unknown)))
    if uncovered:
        errors.append("accepted requirements have no task coverage: " + ", ".join(sorted(uncovered)))
    # Coverage is a name appearing in a list, which any task can satisfy by
    # accident. Requiring acceptance criteria on linked tasks does not make it
    # semantic, but it does stop a bare ID from counting as coverage.
    for task in coverage_tasks:
        if task.get("requirements") and not [a for a in task.get("acceptance", []) if str(a).strip()]:
            errors.append(
                f"{task.get('id')} links requirements but defines no acceptance criteria; "
                "state what satisfying them looks like"
            )
    return list(dict.fromkeys(errors))


def completion_errors() -> list[str]:
    errors: list[str] = []
    state, state_error = read_json(STATE_PATH)
    if state_error is not None or state is None:
        return [state_error or "unreadable .agent/STATE.json"]
    if state.get("project_status") not in {"active", "complete"}:
        errors.append(f"project_status is {state.get('project_status')}")
    if state.get("product_definition", {}).get("status") != "accepted":
        errors.append("product definition is not accepted")
    errors.extend(product_structure_errors())
    errors.extend(plan_errors())
    tasks, unreadable = local_tasks_tolerant()
    errors.extend(unreadable)
    errors.extend(task_graph_errors(tasks))
    open_tasks = [str(t.get("id")) for t in tasks if t.get("status") not in TERMINAL_STATUSES]
    if open_tasks:
        errors.append("unfinished tasks remain: " + ", ".join(sorted(open_tasks)))
    known = requirement_ids()
    completed_refs = {
        r for t in tasks if t.get("status") == "done" and t.get("kind") not in {"discovery", "planning"}
        for r in t.get("requirements", []) if isinstance(r, str)
    }
    missing = known - completed_refs
    if missing:
        errors.append("accepted requirements lack completed evidence: " + ", ".join(sorted(missing)))
    verify_cfg, verify_error = read_json(VERIFY_PATH)
    if verify_error is not None or verify_cfg is None:
        errors.append(verify_error or "unreadable .agent/VERIFY.json")
        verify_cfg = {}
    required, verification = verify_cfg.get("required_level"), state.get("verification")
    commands = verify_cfg.get("commands", {})
    configured_command = commands.get(required) if isinstance(commands, dict) else None
    if not configured_command:
        errors.append("VERIFY.json required verification command is not configured")
    if not isinstance(verification, dict) or verification.get("status") != "passed" or verification.get("level") != required or not parse_time(verification.get("verified_at")):
        errors.append("required project verification has not passed at the configured level")
    elif verification.get("command") != configured_command:
        errors.append(
            "required verification command changed after the recorded pass; re-run verification with the current command"
        )
    else:
        # Passing tests on an older commit proves nothing about the code being
        # declared complete -- unless everything since then was coordination
        # bookkeeping, which cannot change what the tests exercised.
        recorded, current_head = verification.get("commit"), head_sha()
        if not verification_still_applies(recorded):
            errors.append(
                f"required verification passed on commit {str(recorded)[:8]}, but product code has "
                f"changed since (HEAD is {str(current_head)[:8]}); re-run verification against current code"
            )
    return list(dict.fromkeys(errors))


def evaluated_view() -> str:
    """Describe the state these gates just judged, and flag it when it is stale.

    `status`, `next`, and `claim` read `origin/<base>`; `check`, `ready`, and the
    transitions read the working tree. Both are defensible, but a gate that
    reports READY without saying which repository it looked at will happily give
    two workers different answers about the same project.
    """
    expected = base_branch()
    if not has_origin():
        return "local working tree; no origin configured"
    try:
        fetch_remote()
    except SystemExit:
        return "local working tree; could not refresh origin, so this may not reflect shared state"
    if not remote_base_exists():
        return f"local working tree; origin has no {expected} yet"
    current = git("branch", "--show-current").stdout.strip()
    if current and current != expected:
        return f"local working tree on branch {current!r}, not shared state on origin/{expected}"
    ahead, behind = base_divergence(expected)
    if behind and ahead:
        return f"local working tree; {expected} has diverged from origin/{expected} (+{ahead}/-{behind})"
    if behind:
        return (f"local working tree; {expected} is {behind} commit(s) BEHIND origin/{expected}, "
                "so this verdict may not describe current shared state")
    if ahead:
        return f"local working tree; {expected} has {ahead} unpublished commit(s)"
    return f"local working tree, level with origin/{expected}"


def cmd_ready(args: argparse.Namespace) -> None:
    errors = readiness_errors()
    view = evaluated_view()
    if wants_json(args):
        emit_json({"ready": not errors, "view": view, "errors": errors})
        raise SystemExit(1 if errors else 0)
    if errors:
        print(f"NOT READY ({view})")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"READY ({view})")


def live_non_discovery_claims() -> list[str]:
    return [str(t.get("id")) for t in shared_tasks(refresh=True) if t.get("kind") != "discovery" and live_claim(t)]




def cmd_transition(args: argparse.Namespace) -> None:
    state, target = load(STATE_PATH), args.phase
    current = str(state.get("phase", "uninitialized"))
    if target == "discovery":
        active = live_non_discovery_claims()
        if active and not args.allow_live_work:
            raise SystemExit(
                "Cannot enter discovery while non-discovery claims are live: " + ", ".join(sorted(active))
                + ". Finish/release them first or pass --allow-live-work deliberately."
            )
        state["product_definition"] = {"status": "draft", "accepted_at": None}
        if PRODUCT_PATH.exists():
            set_product_status("DRAFT — DISCOVERY IN PROGRESS")
        if state.get("project_status") == "complete":
            state["project_status"], state["blocked"] = "active", None
        discovery_id = ensure_discovery_task()
        state["phase"], state["updated_at"] = "discovery", iso()
        save(STATE_PATH, state)
        print(f"Project phase is now discovery; discovery task: {discovery_id}.")
        try_publish(args, f"state: enter discovery ({discovery_id})")
        return
    if target == "planning":
        if current in {"uninitialized", "discovery"}:
            raise SystemExit("Use accept-product to leave discovery; it records owner acceptance and closes the discovery task.")
        if state.get("product_definition", {}).get("status") != "accepted":
            raise SystemExit("Cannot enter planning before product intent is accepted.")
        if state.get("project_status") == "complete":
            state["project_status"], state["blocked"] = "active", None
        ensure_plan_skeleton()
        set_plan_status("DRAFT")
        planning_id = ensure_planning_task(None, "Re-plan product implementation")
        state["phase"], state["updated_at"] = "planning", iso()
        save(STATE_PATH, state)
        print(f"Project phase is now planning; planning task: {planning_id}.")
        try_publish(args, f"state: enter planning ({planning_id})")
        return
    if target == "execution":
        resuming_complete = state.get("project_status") == "complete" and current == "complete"
        errors = readiness_errors(require_active=not resuming_complete)
        if errors:
            raise SystemExit("Cannot enter execution:\n- " + "\n- ".join(errors))
        if state.get("project_status") == "complete":
            state["project_status"], state["blocked"] = "active", None
        state["phase"], state["updated_at"] = "execution", iso()
        save(STATE_PATH, state)
        print("Project phase is now execution.")
        try_publish(args, "state: enter execution")
        return
    if target == "complete":
        errors = completion_errors()
        if errors:
            raise SystemExit("Cannot mark project complete:\n- " + "\n- ".join(errors))
        state["project_status"], state["phase"], state["blocked"], state["updated_at"] = "complete", "complete", None, iso()
        save(STATE_PATH, state)
        print("Project is now complete.")
        try_publish(args, "state: mark project complete")
        return
    raise SystemExit(f"Unsupported transition target {target}")


def cmd_project_status(args: argparse.Namespace) -> None:
    state, target = load(STATE_PATH), args.status
    if target == "active":
        state["project_status"], state["blocked"] = "active", None
    elif target in {"blocked", "paused"}:
        reason = (args.reason or "").strip()
        if not reason:
            raise SystemExit(f"--reason is required when project_status is {target}")
        state["project_status"], state["blocked"] = target, reason
    else:
        raise SystemExit("Use `transition complete` to mark a project complete.")
    state["updated_at"] = iso()
    save(STATE_PATH, state)
    print(f"Project status is now {target}.")
    try_publish(args, f"state: set project status {target}")


def run_command(command: str | list[str]) -> int:
    """Run a repository-supplied command, as a shell line or as an argv list.

    A string goes through the platform shell, which is `cmd.exe` on Windows and
    `/bin/sh` elsewhere -- so `python3 -m pytest && ruff check` is convenient
    and not portable. A list is executed directly with no shell involved, which
    is both portable and safer, and is the better default for a project that
    may be opened on more than one operating system.

    Either way this is repository-supplied executable text; see docs/SECURITY.md.
    """
    if isinstance(command, list):
        return subprocess.run([str(part) for part in command], cwd=ROOT).returncode
    return subprocess.run(command, cwd=ROOT, shell=True).returncode


def describe_command(command: str | list[str]) -> str:
    return " ".join(str(part) for part in command) if isinstance(command, list) else str(command)


def valid_command(command: Any) -> bool:
    if isinstance(command, str):
        return bool(command.strip())
    if isinstance(command, list):
        return bool(command) and all(isinstance(part, str) and part for part in command)
    return False


def run_verification(level: str) -> int:
    """Run the configured health command for `level` and record the result.

    The command text comes from the repository, so it runs with the privileges
    of whoever invoked Roach -- see docs/SECURITY.md before running this in a
    repository you did not write.
    """
    cfg = load(VERIFY_PATH)
    command = cfg.get("commands", {}).get(level)
    if not command:
        raise SystemExit(f"No {level!r} verification command configured")
    returncode = run_command(command)
    state = load(STATE_PATH)
    state["verification"] = {
        "status": "passed" if returncode == 0 else "failed", "level": level,
        "command": command, "notes": f"exit {returncode}", "verified_at": iso(),
        "commit": head_sha(),
    }
    state["updated_at"] = iso()
    save(STATE_PATH, state)
    return returncode


def cmd_verify(args: argparse.Namespace) -> None:
    raise SystemExit(run_verification(args.level))


def cmd_adopt(args: argparse.Namespace) -> None:
    """Take over a task whose owner is gone.

    Sessions are told to use fresh identities, so a crashed worker's claim
    cannot be released by its successor. Without this, the task stays locked
    until the lease expires -- the most common real event in the workflow.
    """
    who = worker(args.worker)
    force = getattr(args, "force", False)
    # Shared state decides ownership. `adopt` is the one command whose entire
    # purpose is contested handover, so answering "is the current owner gone?"
    # from a possibly stale local copy is how two workers end up holding the
    # same task, each believing the other had abandoned it.
    remote = remote_task(args.task)
    refuse_if_claimed_elsewhere(args.task, who, force, "adopt", remote=remote)
    task = mutable_task(args.task)
    # Prefer origin's view of the claim: a local copy can show an expired lease
    # for a claim that has since been renewed, or name a predecessor who was
    # already replaced.
    authority = remote if isinstance(remote, dict) and isinstance(remote.get("claim"), dict) else task
    claim = authority.get("claim")
    if not isinstance(claim, dict):
        raise SystemExit(f"{args.task} is not claimed; use claim instead")
    previous = str(claim.get("worker", "unknown"))
    if previous == who:
        raise SystemExit(f"{args.task} is already owned by {who}")
    live, reason = claim_liveness(authority)
    override = (getattr(args, "reason", None) or "").strip()
    if live and not force:
        raise SystemExit(
            f"{args.task} is still live ({reason}); refusing to steal it. "
            "Wait for the claim to go stale, coordinate with its owner, or -- if you know that "
            "session is gone -- pass --force --reason \"...\"."
        )
    if live and not override:
        raise SystemExit("--force requires --reason explaining why a live claim is being overridden")
    task["claim"] = {
        "worker": who, "claimed_at": iso(),
        "lease_expires_at": iso(now() + timedelta(minutes=args.lease_minutes)),
        "branch": args.branch or f"roach/{args.task}-{who}",
        "adopted_from": previous,
    }
    if override:
        task["claim"]["adopted_reason"] = override
    if task.get("status") not in ACTIVE_CLAIM_STATUSES:
        task["status"] = "claimed"
    save(task_path(args.task), task)
    print(f"Adopted {args.task} from {previous} as {who} ({reason}); branch {task['claim']['branch']}.")
    try_publish(args, f"adopt({args.task}): take over stale claim from {previous}")


def cmd_integrate(args: argparse.Namespace) -> None:
    """Merge a finished task branch into the base branch, verifying the result.

    This is the one operation that can destroy shared work, and it was the only
    one with no tooling. A merge that fails verification is rolled back.
    """
    who = worker(args.worker)
    task = mutable_task(args.task, who)
    claim = require_owner(task, who)
    source = args.branch or claim.get("branch")
    if not source:
        raise SystemExit(f"{args.task} has no recorded branch; pass --branch")
    expected = base_branch()
    current = git("branch", "--show-current").stdout.strip()
    if current != expected:
        raise SystemExit(f"integrate must run from {expected!r}; current branch is {current!r}.")
    dirty = [line for line in git("status", "--porcelain").stdout.splitlines() if line.strip()]
    if dirty:
        raise SystemExit("integrate requires a clean working tree; commit or stash first.")
    if has_origin():
        fetch_remote()
        if remote_base_exists() and git_text("rev-parse", "HEAD") != git_text(
                "rev-parse", f"refs/remotes/origin/{expected}"):
            raise SystemExit(
                f"local {expected} does not match origin/{expected}; fast-forward before integrating."
            )
        if git("rev-parse", "--verify", f"refs/remotes/origin/{source}").returncode == 0:
            source = f"origin/{source}"
    if git("rev-parse", "--verify", source).returncode:
        raise SystemExit(f"Cannot resolve branch {source!r}.")
    before = head_sha()
    merge = git("merge", "--no-ff", source, "-m", f"merge({args.task}): integrate verified work")
    if merge.returncode:
        git("merge", "--abort")
        raise SystemExit(
            f"Merge of {source} conflicts with {expected}. Resolve on the task branch, then retry."
        )
    level = args.level or load(VERIFY_PATH).get("required_level") or "full"
    print(f"Merged {source}; running {level} verification on the merged result...")
    code = run_verification(str(level))
    record = load(STATE_PATH).get("verification")
    if code != 0:
        if before:
            # Resetting the merge away also reverts the record run_verification
            # just wrote. A merge that failed verification is exactly the thing
            # the next worker needs to know about, so write it back afterwards.
            git("reset", "--hard", before)
            state = load(STATE_PATH)
            state["verification"], state["updated_at"] = record, iso()
            save(STATE_PATH, state)
        raise SystemExit(
            f"{level} verification failed on the merged result (exit {code}); the merge was rolled back. "
            f"{expected} is unchanged, and the failure is recorded in .agent/STATE.json. "
            "Fix the task branch, then integrate again."
        )
    print(f"{level} verification passed on the merged result.")
    # Stamp the merge onto the task. This is the one durable, mechanical link
    # between a completed task and the work it produced, and `finish` reads it.
    merged_task = load(task_path(args.task))
    merged_task["integration"] = {
        "branch": source,
        "merge_commit": head_sha(),
        "level": str(level),
        "verified_at": iso(),
    }
    save(task_path(args.task), merged_task)
    # Commit the evidence with the merge it describes. Leaving it uncommitted
    # made the very next command -- `finish --publish` -- refuse.
    pending = working_tree_changes()[0]
    if pending:
        git("add", "-A", "--", *pending)
        git("commit", "-m", f"verify({args.task}): record {level} pass on the merged result")
    if getattr(args, "push", False) and has_origin():
        out = git("push", "origin", expected)
        if out.returncode:
            raise SystemExit(
                "Merge verified locally but push failed; resolve and push manually. "
                f"Nothing was rolled back because {expected} is verified."
            )
        print(f"Pushed {expected}.")
    print(f"Next: python scripts/roach.py finish {args.task} --worker {who} --verification \"...\"")


# Files the template owns. A project may edit them, but an upgrade replaces
# them wholesale, so local changes here belong upstream instead.
#
# Everything else is the project's: PRODUCT, PLAN, PROJECT, STATE, VERIFY,
# DECISIONS, task records, README, and all application code. An upgrade must
# never touch those -- that boundary is the whole reason this is safe to run.
TEMPLATE_OWNED = (
    "scripts/roach.py",
    "scripts/roach_check.py",
    "scripts/install.py",
    "scripts/vercel-ignore.sh",
    ".agents/skills/project-continuity/SKILL.md",
    ".claude/skills/project-continuity/SKILL.md",
    ".agent/tasks/README.md",
    "schemas/task.schema.json",
    "schemas/state.schema.json",
    "schemas/verify.schema.json",
    "templates/PRODUCT.brownfield.md",
    "templates/roach-project.yml",
    "docs/PROTOCOL.md",
    "docs/ADOPTING.md",
    "docs/MULTI_AGENT.md",
    "docs/DEPLOYMENT.md",
    "docs/SECURITY.md",
    "docs/LIMITATIONS.md",
    "docs/EXAMPLE.md",
    "docs/CHANGELOG.md",
)

# A project that adopted Roach into an existing repository usually already had
# its own agent instructions. Replacing these files wholesale would delete
# somebody's deliberate "never touch this module" note, so in a brownfield
# project only the region between these markers is replaced.
TEMPLATE_MERGED = ("AGENTS.md", "CLAUDE.md")
MANAGED_BEGIN = "<!-- BEGIN ROACH METHOD (managed by roach.py upgrade; edits inside are overwritten) -->"
MANAGED_END = "<!-- END ROACH METHOD -->"


def managed_block(body: str) -> str:
    return MANAGED_BEGIN + "\n\n" + body.strip() + "\n\n" + MANAGED_END + "\n"


def merge_managed(existing: str, incoming: str) -> str:
    """Replace the managed region, or append one when the file has none."""
    block = managed_block(incoming)
    start, end = existing.find(MANAGED_BEGIN), existing.find(MANAGED_END)
    if start != -1 and end != -1 and end > start:
        return existing[:start] + block.rstrip("\n") + existing[end + len(MANAGED_END):]
    return existing.rstrip("\n") + "\n\n" + block


def adoption_mode() -> str:
    """greenfield when the project was created from the template, else brownfield.

    It decides whether AGENTS.md and CLAUDE.md belong to the template or to the
    project. A project created from the template owns neither; a project that
    adopted Roach later almost certainly wrote its own.
    """
    state, error = read_json(STATE_PATH)
    if error is not None or state is None:
        return "greenfield"
    return str(as_mapping(state.get("adoption")).get("mode") or "greenfield")

TEMPLATE_REMOTE = "template"


def upgrade_source(explicit: str | None) -> str:
    if explicit:
        return explicit
    out = git("remote", "get-url", TEMPLATE_REMOTE)
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip()
    raise SystemExit(
        "No upgrade source. Pass --source <url-or-path>, or record it once:\n"
        f"  git remote add {TEMPLATE_REMOTE} https://github.com/<owner>/<template>.git\n"
        f"Then `roach.py upgrade` uses the {TEMPLATE_REMOTE!r} remote."
    )


def cmd_upgrade(args: argparse.Namespace) -> None:
    """Pull template-owned files from upstream, leaving project state alone.

    Roach is distributed by copying, so every project forks the coordinator at
    whatever revision it was created from and keeps that version forever. A fix
    to a coordination bug would otherwise never reach the projects that already
    exist -- `migrate` upgrades state, but nothing upgraded the coordinator.
    """
    if not in_git_repo():
        raise SystemExit("upgrade needs a git repository.")
    source, ref = upgrade_source(args.source), args.ref or "HEAD"
    print(f"Fetching template from {source} ({ref})...")
    fetched = git("fetch", "--depth=1", source, ref)
    if fetched.returncode:
        raise SystemExit(
            f"Could not fetch {ref!r} from {source}.\n" + (fetched.stderr or fetched.stdout).strip()
        )

    changed: list[str] = []
    added: list[str] = []
    merged: list[str] = []
    unchanged = 0
    brownfield = adoption_mode() == "brownfield"

    def upstream(rel: str) -> str | None:
        out = git("show", f"FETCH_HEAD:{rel}")
        # Not present upstream. A removal is never applied automatically.
        return None if out.returncode else out.stdout

    for rel in TEMPLATE_OWNED:
        incoming = upstream(rel)
        if incoming is None:
            continue
        local = ROOT / rel
        if not local.exists():
            added.append(rel)
        elif local.read_text(encoding="utf-8") == incoming:
            unchanged += 1
            continue
        else:
            changed.append(rel)
        if not args.check:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text(incoming, encoding="utf-8")

    for rel in TEMPLATE_MERGED:
        incoming = upstream(rel)
        if incoming is None:
            continue
        local = ROOT / rel
        if not local.exists():
            added.append(rel)
            result = managed_block(incoming) if brownfield else incoming
        elif brownfield:
            # The project owns this file; only the managed region is ours.
            existing = local.read_text(encoding="utf-8")
            result = merge_managed(existing, incoming)
            if result == existing:
                unchanged += 1
                continue
            merged.append(rel)
        else:
            existing = local.read_text(encoding="utf-8")
            if existing == incoming:
                unchanged += 1
                continue
            changed.append(rel)
            result = incoming
        if not args.check:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text(result, encoding="utf-8")

    if not changed and not added and not merged:
        print(f"Already current: {unchanged} template file(s) match {source}.")
        return
    for rel in changed:
        print(f"  {'Would update' if args.check else 'Updated'}: {rel}")
    for rel in merged:
        print(f"  {'Would merge' if args.check else 'Merged'}: {rel} (managed block only; your own text kept)")
    for rel in added:
        print(f"  {'Would add' if args.check else 'Added'}: {rel}")
    print(f"  Unchanged: {unchanged}")
    if args.check:
        print("\nNothing was written. Re-run without --check to apply.")
        return
    print(
        "\nProject state was not touched: PRODUCT, PLAN, PROJECT, STATE, VERIFY, DECISIONS,"
        "\ntask records, and application code are all as they were."
        "\n\nNext:"
        "\n  git diff                              # review what changed"
        "\n  python scripts/roach.py migrate       # bring state to the new protocol"
        "\n  python scripts/roach.py check         # confirm"
    )


def cmd_migrate(_: argparse.Namespace) -> None:
    """Bring an older project's coordination state up to the current protocol."""
    changes: list[str] = []
    state = load(STATE_PATH)
    version = str(state.get("protocol_version", ""))
    if version == PROTOCOL_VERSION:
        print(f"Already at protocol {PROTOCOL_VERSION}; nothing to migrate.")
        return
    if version and version not in MIGRATABLE_VERSIONS:
        raise SystemExit(f"Unsupported protocol version {version!r}; migrate manually.")
    state["protocol_version"] = PROTOCOL_VERSION
    changes.append(f"protocol_version -> {PROTOCOL_VERSION}")
    if state.get("project_status") not in PROJECT_STATUSES:
        state["project_status"] = "active"
        changes.append("project_status -> active")
    if state.get("phase") not in PHASES:
        state["phase"] = "uninitialized"
        changes.append("phase -> uninitialized")
    if not isinstance(state.get("product_definition"), dict):
        state["product_definition"] = {"status": "draft", "accepted_at": None}
        changes.append("product_definition -> draft")
    if not isinstance(state.get("adoption"), dict):
        # A project migrating from an older protocol predates the installer, so
        # it can only have come from the template.
        state["adoption"] = {"mode": "greenfield", "adopted_at": None, "baseline_commit": None}
        changes.append("adoption -> greenfield")
    state.setdefault("blocked", None)
    state["updated_at"] = iso()
    save(STATE_PATH, state)
    # Fields the coordinator writes. An older record simply lacks them; adding
    # them as nulls keeps every task the same shape as a freshly created one,
    # which is what the schema and `check` both expect.
    added: dict[str, Any] = {
        "requirements": [], "verify": None, "integration": None,
        "evidence": None, "completed_at": None, "commit": None,
    }
    for path in task_files():
        task = load(path)
        missing = [key for key in added if key not in task]
        if missing:
            for key in missing:
                task[key] = added[key]
            save(path, task)
            changes.append(f"{path.stem}: added {', '.join(missing)}")
    print("Migrated:")
    for change in changes:
        print(f"- {change}")
    print("\nRun `python scripts/roach.py check` to confirm.")


def divergence_findings() -> list[tuple[str, str]]:
    """Report every way this checkout disagrees with shared coordination state.

    This is the diagnosis the method's premise depends on: a worker whose
    coordination state has not reached `origin` is invisible to everyone else,
    and a worker reading a stale base is deciding from a past that no longer
    exists. Neither shows up in `check`, because both halves are individually
    well-formed.
    """
    findings: list[tuple[str, str]] = []
    expected = base_branch()
    coordination, _unrelated = working_tree_changes()
    pending_summary = f"{', '.join(coordination[:4])}{', ...' if len(coordination) > 4 else ''}"
    if coordination and not has_origin():
        findings.append((
            f"uncommitted coordination state in the working tree ({pending_summary}); "
            "no other worker can see it",
            "run `python scripts/roach.py publish`",
        ))
    if not has_origin():
        return findings
    try:
        fetch_remote()
    except SystemExit as exc:
        return [*findings, (f"cannot refresh origin, so shared state is unknown: {exc}",
                            "restore network/credentials before making coordination decisions")]
    if not remote_base_exists():
        return findings
    current = git("branch", "--show-current").stdout.strip()
    if current != expected:
        # Divergence from the base is normal and expected on a task branch.
        if coordination:
            findings.append((
                f"uncommitted coordination state on task branch {current!r} ({pending_summary}); "
                "coordination edits made off the base branch never reach shared state",
                f"`git checkout {expected}` and redo the coordination command there",
            ))
        return findings
    ahead, behind = base_divergence(expected)
    if ahead:
        # Any unpushed commit on the base blocks every later --publish, whether
        # or not it happens to touch product code as well as coordination state.
        findings.append((
            f"{ahead} unpushed commit(s) on {expected}; publishing will refuse until resolved",
            f"`git push origin {expected}`",
        ))
    # Pending edits and a stale base interact: recommending them separately is
    # what produced two fixes that each refused because of the other.
    if coordination and behind:
        findings.append((
            f"uncommitted coordination state ({pending_summary}) on a {expected} that is "
            f"{behind} commit(s) behind origin/{expected}; publishing refuses because the base "
            "is stale, and pulling can refuse because your edits are in the way",
            "run `python scripts/roach.py reconcile` to replay your edits onto current shared state",
        ))
    elif coordination:
        findings.append((
            f"uncommitted coordination state in the working tree ({pending_summary}); "
            "no other worker can see it",
            "run `python scripts/roach.py publish`",
        ))
    elif behind:
        findings.append((
            f"{expected} is {behind} commit(s) behind origin/{expected}; "
            "work selection here is based on stale shared state",
            f"`git pull --ff-only origin {expected}`",
        ))
    remote_index = by_id(shared_tasks())
    for task in local_tasks_tolerant()[0]:
        tid = str(task.get("id"))
        shared = remote_index.get(tid)
        if shared is None:
            if task.get("status") != "planned" or task.get("claim"):
                findings.append((
                    f"{tid} exists only in this checkout and has already been worked on",
                    "run `python scripts/roach.py publish` so other workers can see it",
                ))
            continue
        local_claim = claim_of(task)
        shared_claim = claim_of(shared)
        if task.get("status") != shared.get("status") or local_claim.get("worker") != shared_claim.get("worker"):
            problem = (
                f"{tid} is {task.get('status')!r} here but {shared.get('status')!r} on origin/{expected}"
                + (f" (owner {local_claim.get('worker')} vs {shared_claim.get('worker')})"
                   if local_claim.get("worker") != shared_claim.get("worker") else "")
            )
            # "Publish if yours is newer" is the wrong instinct when origin holds
            # a live claim: the local record is newer *and* illegitimate, and
            # publishing it would overwrite work somebody else is doing.
            if live_claim(shared) and shared_claim.get("worker") != local_claim.get("worker"):
                findings.append((
                    problem + " -- shared state holds a live claim, so this checkout is wrong, not merely stale",
                    f"discard the local record (`git checkout -- .agent/tasks/{tid}.json`) and re-sync; "
                    "coordinate with its owner or use `adopt --force --reason \"...\"` if that session is gone",
                ))
            else:
                findings.append((
                    problem,
                    "run `python scripts/roach.py reconcile` to replay your edit onto shared state, "
                    f"or `git checkout -- .agent/tasks/{tid}.json` to drop it",
                ))
    return findings


def doctor_findings() -> list[tuple[str, str]]:
    """Return (problem, fix) pairs for states the repository cannot self-explain."""
    findings = divergence_findings()
    for problem in local_tasks_tolerant()[1]:
        findings.append((
            problem,
            "restore the file from Git history (`git checkout -- <path>`), "
            "or delete it if the task was never published",
        ))
    state, state_error = read_json(STATE_PATH)
    if state_error is not None or state is None:
        return [*findings, (state_error or "unreadable .agent/STATE.json",
                            "restore .agent/STATE.json from Git history")]
    if str(state.get("protocol_version", "")) != PROTOCOL_VERSION:
        findings.append((
            f"protocol_version is {state.get('protocol_version')!r}, expected {PROTOCOL_VERSION!r}",
            "run `python scripts/roach.py migrate`",
        ))
    verification = state.get("verification")
    if isinstance(verification, dict) and verification.get("status") == "passed":
        try:
            verify_cfg = load(VERIFY_PATH)
            required = verify_cfg.get("required_level")
            commands = verify_cfg.get("commands", {})
            configured = commands.get(required) if isinstance(commands, dict) else None
            if verification.get("level") == required and verification.get("command") != configured:
                findings.append((
                    "the configured verification command changed after the last passing run",
                    f"re-run `python scripts/roach.py verify {required}`",
                ))
        except SystemExit as exc:
            findings.append((str(exc), "restore .agent/VERIFY.json from Git history"))
        recorded = verification.get("commit")
        if not verification_still_applies(recorded):
            findings.append((
                f"product code changed since the last passing verification on {str(recorded)[:8]} "
                f"(HEAD is {str(head_sha())[:8]})",
                f"re-run `python scripts/roach.py verify {verification.get('level', 'full')}`",
            ))
    for task in local_tasks_tolerant()[0]:
        tid = str(task.get("id"))
        claim = task.get("claim")
        if isinstance(claim, dict) and not live_claim(task):
            findings.append((
                f"{tid} holds a stale claim by {claim.get('worker')}",
                f"run `python scripts/roach.py adopt {tid} --worker <your-id>` to take it over",
            ))
    findings.extend((problem, fix) for problem, fix in deployment_findings())
    return findings


def cmd_doctor(args: argparse.Namespace) -> None:
    findings = doctor_findings()
    if wants_json(args):
        emit_json({
            "ok": not findings,
            "findings": [{"problem": problem, "fix": fix} for problem, fix in findings],
        })
        raise SystemExit(1 if findings else 0)
    if not findings:
        print("No problems found.")
        return
    print(f"Found {len(findings)} problem(s):\n")
    for problem, fix in findings:
        print(f"- {problem}\n  fix: {fix}\n")
    raise SystemExit(1)


def duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate() -> list[str]:
    errors: list[str] = []
    for path in (
        ROOT / "AGENTS.md", ROOT / "CLAUDE.md", PROJECT_PATH, PRODUCT_PATH, STATE_PATH, VERIFY_PATH,
        TASKS / "README.md", TASKS / "T000.json", ROOT / ".agents/skills/project-continuity/SKILL.md",
        ROOT / ".claude/skills/project-continuity/SKILL.md",
    ):
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT).as_posix()}")
    state: dict[str, Any] = {}
    try:
        state = load(STATE_PATH)
        if state.get("protocol_version") != PROTOCOL_VERSION:
            errors.append(f"STATE.json protocol_version must be {PROTOCOL_VERSION}")
        if state.get("project_status") not in PROJECT_STATUSES:
            errors.append("STATE.json project_status is invalid")
        if state.get("phase") not in PHASES:
            errors.append("STATE.json phase is invalid")
        product = state.get("product_definition")
        if not isinstance(product, dict) or product.get("status") not in {"draft", "accepted"}:
            errors.append("STATE.json product_definition is invalid")
        elif product.get("status") == "accepted" and not parse_time(product.get("accepted_at")):
            errors.append("accepted product definition requires accepted_at")
        if state.get("phase") in {"planning", "execution", "complete"} and (not isinstance(product, dict) or product.get("status") != "accepted"):
            errors.append(f"phase {state.get('phase')} requires accepted product intent")
        if (state.get("phase") == "complete") != (state.get("project_status") == "complete"):
            errors.append("complete phase/status must agree")
        adoption = state.get("adoption")
        if adoption is not None:
            if not isinstance(adoption, dict) or adoption.get("mode") not in {"greenfield", "brownfield"}:
                errors.append("STATE.json adoption.mode must be 'greenfield' or 'brownfield'")
            elif adoption.get("mode") == "brownfield" and not adoption.get("baseline_commit"):
                errors.append(
                    "brownfield adoption requires baseline_commit so a worker can tell which "
                    "history predates the method"
                )
        blocked = state.get("blocked")
        if state.get("project_status") in {"blocked", "paused"}:
            if not isinstance(blocked, str) or not blocked.strip():
                errors.append(f"project_status {state.get('project_status')} requires a reason in STATE.json blocked")
        elif blocked not in {None, ""}:
            errors.append("STATE.json blocked must be null unless project is blocked/paused")
        verification = state.get("verification")
        if not isinstance(verification, dict):
            errors.append("STATE.json verification must be an object")
        else:
            vstatus = verification.get("status")
            if vstatus not in {"not_run", "passed", "failed"}:
                errors.append("STATE.json verification.status is invalid")
            if vstatus in {"passed", "failed"}:
                if verification.get("level") not in {"quick", "full", "smoke"}:
                    errors.append("STATE.json completed verification requires a valid level")
                if not parse_time(verification.get("verified_at")):
                    errors.append("STATE.json completed verification requires verified_at")
    except SystemExit as exc:
        errors.append(str(exc))
    try:
        verify = load(VERIFY_PATH)
        if verify.get("version") != 1 or verify.get("required_level") not in {"quick", "full", "smoke"}:
            errors.append("VERIFY.json schema is invalid")
        if not isinstance(verify.get("commands"), dict) or any(k not in verify["commands"] for k in ("quick", "full", "smoke")):
            errors.append("VERIFY.json commands must include quick/full/smoke")
    except SystemExit as exc:
        errors.append(str(exc))
    if state.get("product_definition", {}).get("status") == "accepted":
        errors.extend(product_structure_errors())
        if product_status_line() != "ACCEPTED":
            errors.append("PRODUCT.md Status must be ACCEPTED when STATE.json product definition is accepted")
    elif product_status_line() == "ACCEPTED":
        errors.append("PRODUCT.md says ACCEPTED while STATE.json product definition is draft")
    tasks, unreadable = local_tasks_tolerant()
    errors.extend(unreadable)
    index = by_id(tasks)
    for task in tasks:
        tid = task.get("id")
        if not isinstance(tid, str) or not TASK_RE.fullmatch(tid):
            errors.append("invalid task id")
            continue
        if isinstance(task.get("_path"), Path) and task["_path"].stem != tid:
            errors.append(f"task file does not match id {tid}")
        status = task.get("status")
        if status not in STATUSES or task.get("priority", "normal") not in PRIORITY:
            errors.append(f"{tid} has invalid status/priority")
        title, kind = task.get("title"), task.get("kind", "implementation")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{tid}.title must be non-empty")
        if not isinstance(kind, str) or not TOKEN_RE.fullmatch(kind):
            errors.append(f"{tid}.kind is invalid")
        for key in ("depends_on", "areas", "requirements", "requires", "prefers", "acceptance"):
            value = task.get(key, [])
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                errors.append(f"{tid}.{key} must be an array of strings")
                continue
            duplicates = duplicate_values(value)
            if duplicates:
                errors.append(f"{tid}.{key} contains duplicates: {', '.join(duplicates)}")
        for relation, expected_kind in (("review_of", "verification"), ("correction_of", None)):
            related = task.get(relation)
            if related is None:
                continue
            if not isinstance(related, str) or not TASK_RE.fullmatch(related) or related == tid or related not in index:
                errors.append(f"{tid}.{relation} must reference another existing task")
            elif status not in TERMINAL_STATUSES and index[related].get("status") != "done":
                errors.append(f"{tid}.{relation} target {related} must be done before this work becomes active")
            if expected_kind and kind != expected_kind:
                errors.append(f"{tid}.{relation} requires task kind {expected_kind}")
        if status != "cancelled" and not task.get("acceptance"):
            errors.append(f"{tid}.acceptance must not be empty")
        for key in ("requires", "prefers"):
            for value in task.get(key, []):
                if not TOKEN_RE.fullmatch(value):
                    errors.append(f"{tid}.{key} has invalid capability {value!r}")
        for dep in task.get("depends_on", []):
            if dep == tid or dep not in index:
                errors.append(f"{tid} has invalid dependency {dep}")
        for req in task.get("requirements", []):
            if not re.fullmatch(r"(?:FR|QR)-\d{3,}", req):
                errors.append(f"{tid} has invalid requirement id {req}")
            elif status not in TERMINAL_STATUSES and req not in requirement_ids():
                errors.append(f"{tid} references unknown active requirement {req}")
        claim = task.get("claim")
        if claim is not None:
            if not isinstance(claim, dict) or any(not claim.get(k) for k in ("worker", "claimed_at", "lease_expires_at", "branch")):
                errors.append(f"{tid}.claim is invalid")
            else:
                claimed, expiry = parse_time(claim.get("claimed_at")), parse_time(claim.get("lease_expires_at"))
                if not claimed or not expiry or expiry <= claimed:
                    errors.append(f"{tid}.claim timestamps are invalid")
        if status in ACTIVE_CLAIM_STATUSES and not isinstance(claim, dict):
            errors.append(f"{tid} status {status} requires a claim")
        if status not in ACTIVE_CLAIM_STATUSES and claim is not None:
            errors.append(f"{tid} status {status} must not retain a claim")
        if status == "blocked" and not (isinstance(task.get("handoff"), str) and task.get("handoff", "").strip()):
            errors.append(f"{tid} blocked state requires a durable reason in handoff")
        if status in TERMINAL_STATUSES and (not task.get("verification") or task.get("claim") or task.get("handoff")):
            errors.append(f"{tid} {status}-state metadata is invalid")
        if status == "planned" and task.get("verification"):
            errors.append(f"{tid} planned task must not retain verification evidence")
        verify_command = task.get("verify")
        if verify_command is not None and not valid_command(verify_command):
            errors.append(f"{tid}.verify must be a non-empty command string, an argv array, or null")
        for key in ("integration", "evidence"):
            value = task.get(key)
            if value is not None and not isinstance(value, dict):
                errors.append(f"{tid}.{key} must be an object or null")
        integration = task.get("integration")
        if isinstance(integration, dict) and not integration.get("merge_commit"):
            errors.append(f"{tid}.integration must record the merge_commit it describes")
        completed = task.get("completed_at")
        if completed is not None and not parse_time(completed):
            errors.append(f"{tid}.completed_at must be a timestamp or null")
    if "T000" not in index or index["T000"].get("kind") != "discovery":
        errors.append("reserved T000 discovery task is missing/invalid")
    elif not {"repo-write", "user-dialogue"}.issubset(task_caps(index["T000"], "requires")):
        errors.append("T000 must require repo-write and user-dialogue")
    errors.extend(task_graph_errors(tasks))
    errors.extend(problem for problem, _ in deployment_findings())
    phase = state.get("phase")
    if phase == "execution":
        errors.extend(readiness_errors(require_active=False))
    elif phase == "complete":
        errors.extend(completion_errors())
    return list(dict.fromkeys(errors))


def cmd_check(args: argparse.Namespace) -> None:
    errors = validate()
    view = evaluated_view()
    if wants_json(args):
        emit_json({"ok": not errors, "view": view, "errors": errors,
                   "protocol_version": PROTOCOL_VERSION})
        raise SystemExit(1 if errors else 0)
    if errors:
        print(f"Roach state INVALID ({view}):")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Roach state OK ({view})")


def add_caps(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cap", action="append", default=[], help="capability present in this session; repeat or comma-separate")


def add_publish(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--publish", action="store_true", help=f"commit only this coordination change from a clean/up-to-date {base_branch()} and push it")


def add_json(parser: argparse.ArgumentParser) -> None:
    """Machine-readable output for the read-only commands.

    Agents are the primary caller. Making them scrape prose that exists for
    humans is how a coordination protocol acquires a parsing bug.
    """
    parser.add_argument("--json", action="store_true", help="emit a JSON object instead of prose")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Roach Method v0.5 coordination helper")
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("capabilities"); add_json(x); x.set_defaults(func=cmd_capabilities)
    x = sub.add_parser("status"); add_caps(x); add_json(x); x.set_defaults(func=cmd_status)
    x = sub.add_parser("next"); add_caps(x); x.add_argument("--limit", type=int, default=5); x.add_argument("--explain", action="store_true"); x.add_argument("--worker", help="report your own claims as yours rather than as a conflict"); add_json(x); x.set_defaults(func=cmd_next)
    x = sub.add_parser("create"); x.add_argument("--id"); x.add_argument("--title", required=True); x.add_argument("--kind", default="implementation"); x.add_argument("--priority", choices=list(PRIORITY), default="normal"); x.add_argument("--area", action="append"); x.add_argument("--depends-on", action="append"); x.add_argument("--requirement", action="append"); x.add_argument("--requires", action="append"); x.add_argument("--prefers", action="append"); x.add_argument("--acceptance", action="append", required=True, help="observable condition that means the task is done; repeat as needed"); x.add_argument("--verify", help="shell command proving this task specifically; run by finish"); add_publish(x); x.set_defaults(func=cmd_create)
    x = sub.add_parser("review", help="create an independent verification task for completed work"); x.add_argument("task"); x.add_argument("--title"); x.add_argument("--priority", choices=list(PRIORITY), default="high"); x.add_argument("--requires", action="append"); x.add_argument("--prefers", action="append"); x.add_argument("--acceptance", action="append"); add_publish(x); x.set_defaults(func=cmd_review)
    x = sub.add_parser("correct", help="create corrective work linked to a completed task or review"); x.add_argument("task"); x.add_argument("--title", required=True); x.add_argument("--kind", default="implementation"); x.add_argument("--priority", choices=list(PRIORITY), default="high"); x.add_argument("--requires", action="append"); x.add_argument("--prefers", action="append"); x.add_argument("--acceptance", action="append", required=True); add_publish(x); x.set_defaults(func=cmd_correct)
    x = sub.add_parser("claim"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--lease-minutes", type=int, default=120); x.add_argument("--branch"); x.add_argument("--allow-area-overlap", action="store_true", help="claim despite an area held by another live claim, when the two do not touch the same files"); add_caps(x); add_publish(x); x.set_defaults(func=cmd_claim)
    x = sub.add_parser("heartbeat"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--lease-minutes", type=int, default=120); add_publish(x); x.set_defaults(func=cmd_heartbeat)
    x = sub.add_parser("release"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--handoff"); add_publish(x); x.set_defaults(func=cmd_release)
    x = sub.add_parser("finish"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--verification", required=True); x.add_argument("--no-work", action="store_true", help="record that this task legitimately produced no repository change"); x.add_argument("--skip-task-check", action="store_true", help="do not run the task's own verify command"); add_publish(x); x.set_defaults(func=cmd_finish)
    x = sub.add_parser("block"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--reason", required=True); x.add_argument("--force", action="store_true", help="override a live claim held by another worker"); add_publish(x); x.set_defaults(func=cmd_block)
    x = sub.add_parser("unblock"); x.add_argument("task"); add_publish(x); x.set_defaults(func=cmd_unblock)
    x = sub.add_parser("cancel"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--reason", required=True); x.add_argument("--force", action="store_true", help="override a live claim held by another worker"); add_publish(x); x.set_defaults(func=cmd_cancel)
    x = sub.add_parser("accept-product"); x.add_argument("--worker"); x.add_argument("--verification", default="owner confirmed product intent; PRODUCT.md accepted"); add_publish(x); x.set_defaults(func=cmd_accept_product)
    x = sub.add_parser("ready"); add_json(x); x.set_defaults(func=cmd_ready)
    x = sub.add_parser("transition"); x.add_argument("phase", choices=["discovery", "planning", "execution", "complete"]); x.add_argument("--allow-live-work", action="store_true"); add_publish(x); x.set_defaults(func=cmd_transition)
    x = sub.add_parser("project-status"); x.add_argument("status", choices=["active", "blocked", "paused"]); x.add_argument("--reason"); add_publish(x); x.set_defaults(func=cmd_project_status)
    x = sub.add_parser("verify"); x.add_argument("level", choices=["quick", "full", "smoke"]); x.set_defaults(func=cmd_verify)
    x = sub.add_parser("adopt"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--lease-minutes", type=int, default=120); x.add_argument("--branch"); x.add_argument("--force", action="store_true", help="take over a claim that is still live"); x.add_argument("--reason", help="why a live claim is being overridden; required with --force"); add_publish(x); x.set_defaults(func=cmd_adopt)
    x = sub.add_parser("integrate"); x.add_argument("task"); x.add_argument("--worker"); x.add_argument("--branch"); x.add_argument("--level", choices=["quick", "full", "smoke"]); x.add_argument("--push", action="store_true"); x.set_defaults(func=cmd_integrate)
    x = sub.add_parser("publish", help="commit and push pending .agent/ coordination state"); x.add_argument("--message"); x.set_defaults(func=cmd_publish)
    x = sub.add_parser("reconcile", help="replay pending coordination edits on top of current shared state"); x.set_defaults(func=cmd_reconcile)
    x = sub.add_parser("migrate"); x.set_defaults(func=cmd_migrate)
    x = sub.add_parser("upgrade", help="pull template-owned files from upstream without touching project state"); x.add_argument("--source", help="template repository url or path; defaults to the 'template' git remote"); x.add_argument("--ref", help="branch or tag to take (default HEAD)"); x.add_argument("--check", action="store_true", help="report what would change without writing"); x.set_defaults(func=cmd_upgrade)
    x = sub.add_parser("doctor"); add_json(x); x.set_defaults(func=cmd_doctor)
    x = sub.add_parser("check"); add_json(x); x.set_defaults(func=cmd_check)
    return p


def main() -> None:
    args = parser().parse_args()
    if getattr(args, "lease_minutes", 5) < 5:
        raise SystemExit("Lease must be at least 5 minutes")
    if getattr(args, "limit", 1) < 1:
        raise SystemExit("--limit must be at least 1")
    args.func(args)


if __name__ == "__main__":
    main()

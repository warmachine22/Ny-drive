#!/usr/bin/env python3
"""Install the Roach Method into a project — new or already under way.

The template's original path is "Use this template" on GitHub, which only works
for a project that does not exist yet. This installs the same method into a
repository that already has code, history, and its own opinions about what
lives at the root.

    git clone --depth 1 <template-url> /tmp/roach
    python /tmp/roach/scripts/install.py --into /path/to/project --check
    python /tmp/roach/scripts/install.py --into /path/to/project

The distinction that makes this safe is which files belong to whom. The
coordinator, the agent contract, the skills, the schemas, and the method's docs
are the template's, and are installed and later upgraded. Everything else --
your README, your licence, your changelog, your CI, your build config, your
code -- is yours and is never written. The method's own test suite and lint
configuration stay upstream entirely: they test `roach.py`, which your project
consumes rather than develops.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]


def _coordinator():  # type: ignore[no-untyped-def]
    """Load the coordinator this installer ships, for the constants they share.

    The managed-block markers must be byte-identical in both files: the
    installer writes them and `roach.py upgrade` looks for them years later. A
    copy in each file is a silent drift waiting to eat somebody's AGENTS.md.
    """
    spec = importlib.util.spec_from_file_location("roach_template", SOURCE / "scripts/roach.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load {SOURCE / 'scripts/roach.py'}; is this a Roach template?")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROACH = _coordinator()

# Replaced on every install and every later `roach.py upgrade`. Editing these in
# a project is pointless: the next upgrade overwrites them.
TEMPLATE_OWNED = (
    "scripts/roach.py",
    "scripts/roach_check.py",
    ".agent/tasks/README.md",
    ".agents/skills/project-continuity/SKILL.md",
    ".claude/skills/project-continuity/SKILL.md",
    "schemas/task.schema.json",
    "schemas/state.schema.json",
    "schemas/verify.schema.json",
    "docs/PROTOCOL.md",
    "docs/MULTI_AGENT.md",
    "docs/DEPLOYMENT.md",
    "docs/SECURITY.md",
    "docs/LIMITATIONS.md",
    "docs/EXAMPLE.md",
    "docs/ADOPTING.md",
    "docs/CHANGELOG.md",
)

# Written once, then owned by the project. An upgrade never touches these,
# because after the first session they contain the project's own thinking.
PROJECT_STATE = (
    ".agent/PROJECT.md",
    ".agent/PRODUCT.md",
    ".agent/STATE.json",
    ".agent/VERIFY.json",
    ".agent/DECISIONS.md",
    ".agent/tasks/T000.json",
)

# Merged into whatever the project already has, inside markers, so a project
# with its own agent instructions keeps them. Shared with the coordinator, which
# has to find the same markers on every later upgrade.
MANAGED_BEGIN = ROACH.MANAGED_BEGIN
MANAGED_END = ROACH.MANAGED_END
MERGED = ROACH.TEMPLATE_MERGED

GITIGNORE_LINES = (
    "# Coordination edits reconcile could not replay, kept for review.",
    ".roach-reconcile/",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    except OSError as exc:
        return subprocess.CompletedProcess(["git", *args], 1, "", str(exc))


def is_git_repo(root: Path) -> bool:
    return git(root, "rev-parse", "--git-dir").returncode == 0


def tracked_files(root: Path) -> list[str]:
    out = git(root, "ls-files")
    return [line for line in out.stdout.splitlines() if line.strip()] if out.returncode == 0 else []


def ours() -> set[str]:
    return set(TEMPLATE_OWNED) | set(PROJECT_STATE) | set(MERGED) | {
        "README.md", "LICENSE", ".gitignore", "vercel.json", "scripts/vercel-ignore.sh",
    }


def detect_mode(root: Path) -> str:
    """Does this project already exist?

    Brownfield is not merely "has files" -- a freshly created repo has a README.
    It is "has content this method did not put there", which is what changes the
    first discovery task from "define the product" into "work out what this
    already is".
    """
    mine = ours()
    if [f for f in tracked_files(root) if f not in mine]:
        return "brownfield"
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.relative_to(root).as_posix() not in mine:
            return "brownfield"
    return "greenfield"


# A project with its own AGENTS.md has reasons for it. Replacing the file would
# delete instructions somebody wrote on purpose; appending blindly would
# duplicate the block on every upgrade. Markers make the region replaceable and
# leave everything around it alone. Shared with the coordinator so that install
# and upgrade can never disagree about where that boundary is.
managed_block = ROACH.managed_block
merge_managed = ROACH.merge_managed


def brownfield_state(baseline: str | None) -> dict:
    state = json.loads((SOURCE / ".agent/STATE.json").read_text(encoding="utf-8"))
    # Why the history before this point does not follow the method. A fresh
    # worker would otherwise wonder why hundreds of commits reference no task.
    state["adoption"] = {
        "mode": "brownfield",
        "adopted_at": now_iso(),
        "baseline_commit": baseline,
    }
    state["updated_at"] = now_iso()
    return state


def brownfield_t000() -> dict:
    task = json.loads((SOURCE / ".agent/tasks/T000.json").read_text(encoding="utf-8"))
    task["title"] = "Recover product intent from the existing project with the owner"
    task["requires"] = ["repo-read", "repo-write", "user-dialogue"]
    task["prefers"] = ["shell"]
    task["acceptance"] = [
        ".agent/PRODUCT.md distinguishes what this project already does from what the owner now wants",
        "existing behaviour the owner wants kept is written as active FR-###/QR-### requirements",
        "accidental or abandoned behaviour is deliberately excluded rather than enshrined as a requirement",
        ".agent/PROJECT.md orients a fresh worker to the existing codebase in under a minute",
        "roach.py accept-product records the owner's confirmation without a separate finish step",
    ]
    return task


def as_json(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install the Roach Method into a project, new or existing.")
    parser.add_argument("--into", default=".", help="project directory (default: current)")
    parser.add_argument("--mode", choices=["auto", "greenfield", "brownfield"], default="auto",
                        help="auto-detects from whether the project already has content")
    parser.add_argument("--check", action="store_true",
                        help="report what would change and write nothing")
    parser.add_argument("--with-ci", action="store_true", help="install the Roach GitHub Actions check")
    parser.add_argument("--no-ci", action="store_true", help="do not install any workflow")
    parser.add_argument("--with-vercel", action="store_true",
                        help="install push-triggered-deploy protection (see docs/DEPLOYMENT.md)")
    parser.add_argument("--force", action="store_true",
                        help="reinstall over an existing .agent/ (prefer roach.py upgrade)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    target = Path(args.into).resolve()
    if not target.is_dir():
        raise SystemExit(f"No such directory: {target}")
    if target == SOURCE:
        raise SystemExit("Refusing to install the template into itself.")

    if (target / ".agent/STATE.json").exists() and not args.force:
        raise SystemExit(
            f"{target} already has .agent/STATE.json, so Roach is already installed.\n"
            "To update the coordinator without touching project state, run there:\n"
            "  python scripts/roach.py upgrade --check\n"
            "Pass --force only to deliberately reinitialise coordination state."
        )

    repo = is_git_repo(target)
    mode = detect_mode(target) if args.mode == "auto" else args.mode
    baseline = None
    if repo:
        head = git(target, "rev-parse", "HEAD")
        baseline = head.stdout.strip() if head.returncode == 0 else None

    actions: list[tuple[str, str, str]] = []
    writes: list[tuple[Path, str]] = []

    for rel in TEMPLATE_OWNED:
        source = SOURCE / rel
        if not source.exists():
            continue
        destination, text = target / rel, source.read_text(encoding="utf-8")
        if destination.exists() and destination.read_text(encoding="utf-8") == text:
            continue
        actions.append(("update" if destination.exists() else "add", rel, "template-owned"))
        writes.append((destination, text))

    for rel in MERGED:
        source = SOURCE / rel
        if not source.exists():
            continue
        destination, incoming = target / rel, source.read_text(encoding="utf-8")
        if not destination.exists():
            actions.append(("add", rel, ""))
            writes.append((destination, managed_block(incoming) if mode == "brownfield" else incoming))
            continue
        existing = destination.read_text(encoding="utf-8")
        merged = merge_managed(existing, incoming)
        if merged == existing:
            continue
        note = "replace managed block" if MANAGED_BEGIN in existing else "keep yours, append Roach block"
        actions.append(("merge", rel, note))
        writes.append((destination, merged))

    for rel in PROJECT_STATE:
        destination = target / rel
        if destination.exists() and not args.force:
            actions.append(("keep", rel, "yours already"))
            continue
        if rel == ".agent/STATE.json":
            text = as_json(brownfield_state(baseline) if mode == "brownfield"
                           else json.loads((SOURCE / rel).read_text(encoding="utf-8")))
        elif rel == ".agent/tasks/T000.json" and mode == "brownfield":
            text = as_json(brownfield_t000())
        elif rel == ".agent/PRODUCT.md" and mode == "brownfield":
            text = (SOURCE / "templates/PRODUCT.brownfield.md").read_text(encoding="utf-8")
        else:
            text = (SOURCE / rel).read_text(encoding="utf-8")
        actions.append(("seed", rel, f"{mode} starting point"))
        writes.append((destination, text))

    gitignore = target / ".gitignore"
    if gitignore.exists():
        current = gitignore.read_text(encoding="utf-8")
        if [line for line in GITIGNORE_LINES if line not in current]:
            actions.append(("append", ".gitignore", "add .roach-reconcile/"))
            writes.append((gitignore, current.rstrip("\n") + "\n\n" + "\n".join(GITIGNORE_LINES) + "\n"))
    else:
        actions.append(("add", ".gitignore", ""))
        writes.append((gitignore, (SOURCE / ".gitignore").read_text(encoding="utf-8")))

    # Default to installing a workflow only where the project already uses
    # Actions. Adding one uninvited spends somebody else's build minutes.
    workflows = target / ".github/workflows"
    want_ci = args.with_ci or (not args.no_ci and workflows.is_dir())
    ci_target = workflows / "roach-check.yml"
    if want_ci and not ci_target.exists():
        actions.append(("add", ".github/workflows/roach-check.yml",
                        "validates state and runs your health command"))
        writes.append((ci_target, (SOURCE / "templates/roach-project.yml").read_text(encoding="utf-8")))
    elif want_ci:
        actions.append(("keep", ".github/workflows/roach-check.yml", "yours already"))
    elif not args.no_ci:
        actions.append(("skip", "CI workflow", "no .github/workflows/ here; --with-ci adds one"))

    if args.with_vercel:
        for rel in ("vercel.json", "scripts/vercel-ignore.sh"):
            destination = target / rel
            if destination.exists():
                actions.append(("keep", rel, "yours already"))
                continue
            actions.append(("add", rel, "push-triggered-deploy protection"))
            writes.append((destination, (SOURCE / rel).read_text(encoding="utf-8")))

    print(f"Roach Method install into {target}")
    print(f"  mode: {mode}" + ("" if repo else "   (not a git repository -- coordination needs one)"))
    print()
    if not actions:
        print("  Nothing to do; this project is already current.")
        return 0

    width = max(len(verb) for verb, _, _ in actions)
    for verb, path, note in actions:
        print(f"  {verb:<{width}}  {path}" + (f"  -- {note}" if note else ""))

    if args.check:
        print("\nNothing was written. Re-run without --check to apply.")
        return 0

    for destination, text in writes:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")

    if repo and git(target, "remote", "get-url", "template").returncode != 0:
        url = git(SOURCE, "remote", "get-url", "origin").stdout.strip()
        if url:
            git(target, "remote", "add", "template", url)
            print(f"\n  Recorded template remote: {url}")
            print("  Later: python scripts/roach.py upgrade --check")

    print("\nNothing outside the list above was touched -- not your README, licence,")
    print("changelog, build config, CI, or any application code.")
    print("\nNext:")
    print("  git diff                              # review it")
    print("  python scripts/roach.py check         # confirm coordination state")
    if mode == "brownfield":
        print("  git add -A && git commit -m 'chore: adopt the Roach Method'")
        print("\nThen open the project with an agent and say:")
        print("  Use the Roach Method in this repository. Claim T000 and work out")
        print("  with me what this project is and what I want next.")
    else:
        print("  git add -A && git commit -m 'chore: add the Roach Method'")
        print("\nThen describe the product you want to an agent, and it will claim T000.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

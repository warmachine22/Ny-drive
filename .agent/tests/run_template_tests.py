from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / ".agent" / "tests" / "fixtures" / "template"

STATIC_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
    "vercel.json",
    "docs/DEPLOYMENT.md",
    ".agent/tests/test_roach.py",
    ".agent/tests/test_roach_commands.py",
    ".agent/tests/test_roach_remote.py",
    ".agent/tests/test_schemas.py",
    ".agent/tests/test_install.py",
    ".agent/tasks/README.md",
    ".agent/DECISIONS.md",
    ".agents/skills/project-continuity/SKILL.md",
    ".claude/skills/project-continuity/SKILL.md",
    "scripts/roach.py",
    "scripts/roach_check.py",
    "scripts/install.py",
    "scripts/vercel-ignore.sh",
    "docs/PROTOCOL.md",
    "docs/ADOPTING.md",
    "docs/CHANGELOG.md",
    "docs/MULTI_AGENT.md",
    "docs/SECURITY.md",
    "docs/LIMITATIONS.md",
    "docs/EXAMPLE.md",
    "templates/PRODUCT.brownfield.md",
    "templates/roach-project.yml",
    "schemas/task.schema.json",
    "schemas/state.schema.json",
    "schemas/verify.schema.json",
]

FRESH_TEMPLATE_FILES = {
    "PROJECT.md": ".agent/PROJECT.md",
    "PRODUCT.md": ".agent/PRODUCT.md",
    "STATE.json": ".agent/STATE.json",
    "VERIFY.json": ".agent/VERIFY.json",
    "T000.json": ".agent/tasks/T000.json",
}

TEST_SUITES = [
    ".agent/tests/test_roach.py",
    ".agent/tests/test_roach_commands.py",
    ".agent/tests/test_roach_remote.py",
    ".agent/tests/test_schemas.py",
    ".agent/tests/test_install.py",
]


def copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


# The remote suite drives real git repositories through a subprocess per
# command, so it takes minutes where the others take seconds. It also covers the
# shared-state paths where the coordinator's real defects live, so it is never
# skipped in CI -- only when a developer wants a fast local answer.
SLOW_SUITES = {".agent/tests/test_roach_remote.py"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fast = "--fast" in argv
    if "--help" in argv or "-h" in argv:
        print(__doc__ or "")
        print("usage: run_template_tests.py [--fast]\n")
        print("  --fast   skip the slow remote-coordination suite")
        return 0

    suites = [s for s in TEST_SUITES if not (fast and s in SLOW_SUITES)]
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp) / "roach-template"

        for rel in STATIC_FILES:
            copy_file(REPO / rel, sandbox / rel)

        for fixture_name, destination in FRESH_TEMPLATE_FILES.items():
            copy_file(FIXTURES / fixture_name, sandbox / destination)

        exit_code = 0
        for suite in suites:
            result = subprocess.run(
                [sys.executable, suite, "-v"],
                cwd=sandbox,
                check=False,
            )
            exit_code = exit_code or result.returncode

        if fast:
            print("\nSkipped the remote-coordination suite (--fast). "
                  "Run without --fast before publishing coordinator changes.")
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

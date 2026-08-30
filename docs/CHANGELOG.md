# Changelog

Roach's distribution model is "copy the template", so a project forks the
coordinator at whatever revision it was created from. This file plus
`roach.py upgrade` are how a fix reaches a project that already exists.

The version in `STATE.json` is the **protocol** version. It changes when the
shape of coordination state changes, which is what `roach.py migrate` acts on.

## 0.6.0

Roach could only be born, not adopted. "Use this template" needs a project that
does not exist yet, which ruled out every repository that already had code.

### Added

- **`scripts/install.py`** installs the method into an existing repository. It
  splits the tree by ownership and only writes its own half: the coordinator,
  skills, schemas, templates, and method docs. Your README, licence, changelog,
  build config, existing CI, and application code are never touched. `--check`
  prints the plan and writes nothing.
- **A brownfield discovery cycle.** An adopted project gets a `PRODUCT.md` and a
  T000 written for the question it actually faces — *what is this already, and
  what do you want next?* — instead of a blank template asking what to build.
  The first worker reads the code and brings the owner a summary to correct.
- **`adoption` in `STATE.json`**, recording `greenfield` or `brownfield` and the
  `baseline_commit` Roach arrived at. That answers the question every future
  worker in an adopted project would otherwise ask: why do hundreds of commits
  reference no task? Because they predate the method.
- **`docs/ADOPTING.md`** — the procedure, the prompt to hand an agent, how to
  cover existing code without inventing fake work, the no-shell path, and how to
  back the whole thing out.
- **A project-appropriate CI workflow** (`templates/roach-project.yml`) that
  validates coordination state and runs *your* health command. It never runs the
  method's own test suite; those test `roach.py`, which a project consumes
  rather than develops. Added automatically only where `.github/workflows/`
  already exists, so adoption never spends build minutes uninvited.

### Fixed

- **`upgrade` no longer overwrites a project's own agent instructions.** In a
  brownfield project `AGENTS.md` and `CLAUDE.md` belong to the project, and only
  the region between `BEGIN ROACH METHOD` / `END ROACH METHOD` markers is
  replaced. Before this, upgrading an adopted project silently deleted notes
  like "never touch the billing module" — reproduced, then fixed and tested.

### Changed

- The method's changelog moved to `docs/CHANGELOG.md` so it cannot collide with
  the changelog an adopting project already has.
- `scripts/install.py`, `templates/`, and `docs/ADOPTING.md` are template-owned,
  so an adopted project receives improvements to adoption itself.

## 0.5.0

Protocol change. Run `python scripts/roach.py upgrade` then
`python scripts/roach.py migrate` in an existing project.

### Fixed

- **`adopt` now resolves ownership from `origin`.** It was the only
  ownership-changing command that never consulted shared state: it read the
  local record, so a worker one commit behind could take a task another worker
  had just legitimately claimed — no `--force`, no warning, and the new record
  named the wrong predecessor. `AGENTS.md` and `docs/SECURITY.md` both
  described this as refused.
- **`check` and `doctor` survive an unreadable file.** They aborted on the
  first unparseable JSON, reporting one problem and hiding every other, in the
  one situation where the rest of the diagnosis matters most.
- **The coordination-race dead end is gone.** Two workers creating a task from
  the same base both compute the same free id. The loser could not publish (the
  base was behind) and could not pull (the pending record wanted the same
  path), and `doctor` recommended exactly those two commands.

### Added

- **`roach.py reconcile`** replays pending coordination edits on top of current
  shared state: a task that lost the id race is renumbered and keeps its
  content, with dependency references rewritten; an edit that would overwrite
  shared state is preserved under `.roach-reconcile/` and reported.
- **`roach.py upgrade`** pulls template-owned files from an upstream template
  and leaves project state alone, so coordinator fixes reach existing projects.
- **Work evidence on `finish`.** A code-producing task must show commits on its
  claimed branch, a merge recorded by `integrate`, or product files changed on
  the base since the claim. `--no-work` waives it and records the waiver.
- **Per-task `verify` commands**, run by `finish` and required to pass.
- **`integration` on task records**, stamped by `integrate` — the durable link
  between a completed task and the work it produced.
- **`--json` on `status`, `next`, `check`, `ready`, `doctor`, `capabilities`.**
- **`schemas/`** — JSON Schema for task records, `STATE.json`, and `VERIFY.json`.
- **`docs/PROTOCOL.md`** — the normative specification, written for a worker
  reproducing Roach through a repository API without a shell.
- **`docs/EXAMPLE.md`** — one project from empty template to complete, with
  real command output.
- **Verification commands may be argv arrays** as well as shell strings, so a
  project that runs on more than one operating system can express a portable
  command.
- **`claim --allow-area-overlap`** for a deliberate, recorded exception.
- **`next --worker`** so your own claim is reported as yours rather than as a
  conflict to force past.
- Windows CI matrix, `ruff`, `mypy --strict`, and a schema-drift test.

### Changed

- **Publishing distinguishes ahead from behind.** Being behind is the ordinary
  state with several workers; it now fast-forwards instead of refusing and
  demanding a manual `git pull`. A base carrying unpushed local commits is
  still refused, which was the case worth refusing for.
- **`PRODUCT.md` requirements parse from list items, table rows, and headings**,
  at any heading level, with sub-headings staying inside their parent section.
  Previously only `- **FR-001**: text` was recognised and everything else
  vanished silently. A declaration that cannot be read is now an error.
- **`check` and `ready` report which view they judged**, so a verdict from a
  checkout that is behind shared state says so.
- **`doctor`** recognises the publish/pull wedge as one finding with one fix,
  distinguishes a stale checkout from one contradicting a live claim, and
  notices coordination edits stranded on a task branch.
- **`areas` are documented as what they are** — exclusive while a claim is
  live, not advisory hints.
- Task records gain `verify`, `integration`, `evidence`, `completed_at`, and
  `commit`; claims gain `base_commit`. `migrate` fills these in.
- `origin` is refreshed at most once per invocation instead of up to three times.
- The remote test suite builds its expensive starting points once and copies
  them: 500s to under 300s, with `--fast` for a 40-second local answer.

## 0.4.0

The field-tested baseline this fork started from: product discovery before
implementation, autonomous planning after one owner checkpoint,
capability-aware work selection, and mechanical coordination safety —
`adopt`, `integrate`, `doctor`, `migrate`, gated completion, review and
correction of completed work, and pre-wired protection against a
push-triggered deploy host exhausting its free tier.

See `docs/MIGRATING_V0_3.md` for moving a 0.3 project forward.

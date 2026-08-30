# Multi-Agent Coordination Guide

Roach Method v0.5 is optimized for a small number of independent, **heterogeneous** agent sessions—typically 1 to 3—working against the same repository.

The repository performs four jobs:

1. **Product memory** — durable owner intent survives every chat/session.
2. **Continuity** — a fresh worker can recover without conversation history.
3. **Coordination** — workers see ownership, dependencies, overlap, capability requirements, blockers, and WIP branches.
4. **Convergence** — verified work returns to the shared base quickly so everyone builds on the newest known-good product.

Roach deliberately does not require a daemon, dashboard, database, queue server, or permanent orchestrator.

## Lifecycle before parallel execution

A fresh template does not immediately fan out into coding:

```text
uninitialized
    ↓
T000 discovery claim
    ↓
owner + discovery worker define PRODUCT.md
    ↓
product-intent checkpoint
    ↓
accept-product (atomic discovery completion + planning start)
    ↓
PLAN.md + VERIFY.json + initial capability-tagged task graph
    ↓
readiness/consistency gate
    ↓
execution
```

T000 is a normal claimed task, so only one worker owns the initial owner conversation.

Later major product pivots return to discovery through a **new discovery task**. Roach normally refuses that transition while non-discovery claims are still live so a product pivot does not silently invalidate concurrent implementation.

## Project status gates work

Lifecycle phase is not the same thing as whether the project should currently run.

`project_status` values:

- `active` — task selection is allowed;
- `blocked` — project-wide blocker; task selection stops;
- `paused` — intentional suspension; task selection stops;
- `complete` — all current work is terminal and required verification has passed.

Status/phase separation lets a project remain, for example, `paused + planning` without losing where work should resume.

## Stable worker identity

Every ownership-changing worker must use one stable ID across command invocations, such as `codex-a31f`. Use `--worker` or `ROACH_WORKER`.

Roach intentionally does not derive worker identity from PID or process invocation because separate commands from one session would otherwise look like different workers.

## Capability-aware workflow

Before selecting work, each worker inventories capabilities actually present in its current environment, for example:

```text
repo-read
repo-write
shell
git
web-research
vision
```

Hard task `requires` filter impossible work; `prefers` help rank otherwise eligible work.

A browser/vision worker may be a better fit for UI verification. A shell/repo worker may be a better fit for implementation. A research-capable worker can investigate an integration. Roach describes abilities, not vendor/model identities.

If an agent has GitHub/repository write tools but no shell, it may reproduce Roach coordination through the repository API only if it can preserve the same safety invariants. The CLI is the reference semantics, not a reason to pretend a no-shell worker is useless.

That equivalence has a hard edge. The single-file coordination commands — `claim`, `finish`, `create`, `block`, `cancel` — can be reproduced through a repository API. `integrate` cannot, because it needs a real merge plus command execution, and `verify` cannot, because it runs a shell command by definition. A no-shell worker can therefore claim, implement, and publish, but cannot converge its own work to the base branch or produce executable verification evidence. Plan for a shell-capable worker to integrate it, or scope no-shell workers to research, design, and documentation tasks. See `docs/LIMITATIONS.md`.

## Normal parallel workflow

```text
fetch/sync
  ↓
recover PRODUCT / PLAN / state
  ↓
establish stable worker ID
  ↓
inventory current capabilities
  ↓
roach.py status / next --cap ...
  ↓
choose suitable eligible non-overlapping task
  ↓
roach.py claim --worker ... --cap ... --publish
  ↓
short-lived task branch/worktree
  ↓
implement/research/verify + checkpoint + push
  ↓
sync latest base
  ↓
re-test affected behavior
  ↓
integrate to base, then finish task
  ↓
inventory/select again
```

## Shared state and stale worktrees

A worker may spend hours on a task branch, so local task records can lag behind the shared base. `status`, `next`, and claim eligibility read shared task records from `origin/<base>` when available.

When an origin exists, Roach refreshes it before coordination decisions. If fetch fails, the helper stops instead of silently treating stale remote state as current.

The base branch defaults to `main`. Repositories that intentionally rename it can set `ROACH_BASE_BRANCH`.

## Safe coordination publication

Coordination changes are published from a safe base worktree with `--publish`.

The helper requires:

- current branch exactly equals the configured base;
- a successful origin refresh;
- no local commits on the base that `origin` has not seen;
- no working-tree changes outside `.agent/`;
- normal push semantics with no force.

This closes an important race/safety hole: a claim operation must never accidentally push unrelated local commits that happened to already exist on base.

A base that is merely **behind** is different, and is not refused. With two or three workers publishing claims and heartbeats, every push by anyone puts everyone else behind; treating that as an error made a manual `git pull` a precondition of nearly every coordination command. Publishing fast-forwards a base that is only behind and continues. If a pending coordination edit collides with what was published — the same file, the same task id — the fast-forward cannot happen, and the helper names `reconcile` rather than failing.

Publication covers all pending `.agent/` state rather than one named file. Coordination state is one unit, and a command that requires an edit — `accept-product` demands a real `PROJECT.md`, entering execution demands a READY `PLAN.md` and a backlog — must be able to publish the edit it demanded. Product code is the boundary that matters, and it stays out.

If another worker moves the base after the preflight fetch, the push fails normally. Reconcile and retry; never force.

### When publishing fails after the state change

State changes are written before they are published, so a publish failure leaves the change in the working tree. Re-running the original command will not work — it refuses a precondition it has itself already satisfied. Fix the cause, then:

```bash
python scripts/roach.py publish
```

`doctor` detects this state and points at the same command.

### When a pending edit collides with a published one

```bash
python scripts/roach.py reconcile
```

`reconcile` sets pending `.agent/` edits aside, fast-forwards the base, and replays them on top of current shared state:

- a task that lost the id race is **renumbered**, keeping its title, acceptance criteria, and every other field, and any dependency reference to its old id is rewritten;
- an edit that would overwrite what another worker published — most often a claim on a task somebody else now owns — is **set aside** under `.roach-reconcile/` and named in the report. Shared state wins; nothing is deleted.

It refuses when the base is *ahead* of origin, because that is a real divergence rather than a stale checkout, and it is safe to run when nothing is wrong.

This replaces the previous dead end, where publishing refused because the base was behind and `git pull` refused because the pending edit was in the way.

### Claim from the base, then branch

Task records are tracked files. A claim made from a task branch is committed to that branch and reverts when the worker checks the base out again: shared state never sees the claim, the base advertises the task as free, and the worker cannot finish or integrate its own work. Roach refuses a claim made from anywhere but the base branch.

## Dependencies, areas, capabilities, and cancellation

Task records can declare:

- `depends_on` — prerequisite tasks;
- `areas` — coarse collision labels, exclusive while a claim is live;
- `requires` — capabilities the worker must have;
- `prefers` — capabilities that improve suitability;
- `requirements` — current `FR-###`/`QR-###` intent links.

Roach validates dependency existence, self-dependencies, dependencies on cancelled prerequisites, and multi-task dependency cycles.

`cancelled` is a first-class terminal task state for work that is intentionally retired/superseded. Do not mark obsolete work `done` just to clear the backlog.

Historical terminal tasks may retain requirement IDs later retired from current PRODUCT; current unfinished work may not reference retired IDs.

## Blocking

A task-level blocker uses:

```bash
python scripts/roach.py block T024 \
  --worker agent-a31f \
  --reason "requires owner OAuth approval"
```

Blocking releases the task claim and stores the reason in `handoff`. This avoids an inaccessible task monopolizing an area/lease while still making the blocker durable.

When resolved:

```bash
python scripts/roach.py unblock T024
```

A project-wide blocker or deliberate pause belongs in STATE using `project-status`, not by blocking every task individually.

## Liveness

A newly published claim receives an initial lease. After work begins, **pushed task-branch commits** are the normal heartbeat.

A claim is stale only when both its lease and recent remote branch activity are stale.

Default recent threshold is two hours. `ROACH_STALE_MINUTES` can change it, with a 15-minute minimum. Invalid values are rejected.

A pushed checkpoint therefore does two jobs at once:

- preserves useful work for recovery;
- proves to other workers that the task is still alive.

## No compatible work

A worker with no compatible eligible task should not weaken task requirements or create unrelated make-work.

Use:

```bash
python scripts/roach.py next --cap ... --explain
```

The explanation distinguishes missing capabilities, dependencies, lifecycle phase, project pause/block, and ownership conflicts.

If the project genuinely requires another environment, surface the missing ability concisely with `NEED YOU:`.

## Planning can delegate

Planning may create research/design/verification tasks before execution when a capability gap prevents a reliable technical decision.

If another worker needs to see such a task immediately, publish the new task record from a clean/up-to-date base worktree with `create --publish`. This publishes only the task coordination record; unfinished planning work remains isolated.

Concurrent task creation can still race on numeric IDs at the small scale Roach targets. Normal merge/push protection wins; reconcile and rename/recreate the conflicting new task rather than overwriting another worker's record.

## Product changes during parallel work

Clear owner changes update PRODUCT and propagate into PLAN/tasks.

For a large ambiguous pivot:

1. finish/release live non-discovery work where practical;
2. enter discovery;
3. claim the new discovery task;
4. clarify intent and obtain the new product checkpoint;
5. use `accept-product` to atomically close that discovery cycle and open planning;
6. re-plan, cancelling/superseding obsolete current tasks explicitly.

`transition discovery` normally refuses while non-discovery claims are live. An explicit `--allow-live-work` override exists for exceptional cases where the caller deliberately accepts that coordination risk.

Completed discovery and planning tasks are never reopened. A Product Bible revision uses a new discovery cycle; a design/architecture revision uses `transition planning`. This preserves what was previously accepted while making the current PRODUCT or PLAN editable again.

## Independent review and correction

`done` prevents history rewriting; it does not mean another worker must trust the original worker's evidence. Review uses a new task:

```bash
python scripts/roach.py review T012 --publish
```

The review task is linked by `review_of`, depends on T012, and inherits its active requirements and collision area. This lets a different capability-compatible worker claim it normally without changing T012.

When a review confirms a defect, finish the review with concrete evidence and create correction work linked to that completed review:

```bash
python scripts/roach.py correct T013 \
  --title "Fix save corruption found in review" \
  --acceptance "interrupted saves preserve the last valid file" \
  --publish
```

Known defects may link correction directly to a completed implementation task. If the project is complete, `review` and `correct` atomically set status to active, phase to execution, and create the new task in one coordination publication. `transition execution` also supports explicit owner-requested new work from completed state.

This is deliberately append-only: T012 records the original claim, T013 records the independent finding, and the correction task records the fix. Requirement coverage and completion gates then include the new work normally.

## Verification and completion

Each project defines required executable health in `.agent/VERIFY.json`. `roach.py verify` records result, level, timestamp, and current commit when available.

Completion is gated. A project cannot be marked complete while tasks remain planned/claimed/active/blocked/verify, while current requirements lack completed evidence, while PLAN is not READY, or while the configured required verification has not passed.

This keeps `complete` from becoming a cosmetic state that hides unfinished work.

## Merge races

If two workers finish concurrently, one updates the base first. The other fetches, integrates current base, resolves conflicts, reruns affected checks, and retries normally. Never force-push shared history.

Use `roach.py integrate <task> --push` rather than a hand-rolled merge, and run it **before** `finish`: `integrate` requires the live claim that `finish` releases. It refuses unless the base is clean and matches `origin`, runs the configured verification on the merged result, and hard-resets the merge away if that fails — recording the failure so the next worker knows the branch is broken rather than rediscovering it.

## Diagnosing divergence

`check` answers whether coordination state is well-formed. `doctor` answers whether it is *shared* — uncommitted coordination state, a base ahead of or behind `origin`, task records disagreeing with shared state, stale claims, verification recorded against another commit.

Both halves can be individually valid while the repository is incoherent, which is the failure a fresh worker is least equipped to reason about. Run `doctor` after any interrupted session.

## Success condition

Roach is working when fresh workers with different toolsets can make cumulative progress without duplicate work, hidden chat dependencies, stale coordination, capability mismatches, dependency deadlocks, accidental shared-history publication, or continuous human project management.

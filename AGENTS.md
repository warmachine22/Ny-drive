# Roach Method Agent Contract

This repository uses **Roach Method v0.5**: Git is durable memory, product intent is durable first-class state, workers are disposable, and work selection depends on the capabilities actually available in the current session.

**Reading order for a fresh worker.** This file is authoritative and sufficient. Read it, then `.agent/` state. `README.md` is written for humans evaluating the method and restates this file — agents should skip it. Read `docs/` only when a task touches that subject: `MULTI_AGENT.md` for branch and race behaviour, `DEPLOYMENT.md` before connecting a deploy host, `SECURITY.md` before running verification in a repository you did not write, `LIMITATIONS.md` before proposing a change to `scripts/roach.py` or when something behaves in a way this file does not explain, `PROTOCOL.md` if you have no shell and must reproduce coordination through a repository API.

## Core rules

1. **Repository over chat.** Recover from Git and `.agent/`; never require previous conversation history.
2. **Know both status and phase.** Read `.agent/STATE.json` before choosing work. `project_status` answers whether work should proceed; `phase` answers what kind of work is appropriate.
3. **Product intent is authoritative.** `.agent/PRODUCT.md` is the durable statement of what the owner wants. Do not silently rewrite intent to match existing code.
4. **Discovery is legitimate human interaction.** During initial discovery or a major ambiguous pivot, asking focused product questions is the work. Ask one meaningful question at a time and update PRODUCT incrementally.
5. **One product-intent checkpoint.** When critical product ambiguity is resolved, summarize the intended product and obtain the owner's confirmation. The active discovery-task owner then uses `roach.py accept-product`; routine technical planning/implementation after that is autonomous.
6. **Human = product owner, not engineering manager.** Outside discovery, do not ask for routine technical approval when a reasonable reversible decision is available.
7. **Inventory capabilities before selecting work.** Inspect the tools/environment of this session. Never infer abilities from model/vendor/interface names.
8. **Hard requirements are real.** Do not claim a task without everything in `requires`. `prefers` only affects suitability/ranking.
9. **Use a stable worker identity.** Establish one session worker ID and reuse it for claim/heartbeat/release/finish/acceptance. Pass `--worker` or set `ROACH_WORKER`; do not rely on a process/PID identity.
10. **Sync before coordination.** Refresh the configured remote before choosing/claiming shared work. If refresh fails, do not pretend stale `origin` state is current.
11. **Claim before substantial work.** Make ownership visible before implementation/research/design begins.
12. **One task, isolated implementation.** Prefer a short-lived `roach/<task>-<worker>` branch/worktree. Avoid overlapping live task areas when independent work exists.
13. **Small recoverable slices.** Verify/checkpoint/push coherent progress often enough that context loss does not erase meaningful work.
14. **Main converges quickly.** Verified completed work should integrate promptly. Never force-push shared history or merge known-broken WIP into the base branch.
15. **Executable evidence beats prose.** Use `.agent/VERIFY.json` for project health and task-specific evidence for experiential/capability-dependent validation.
16. **Trace current work to current intent.** Active implementation/verification/design work should reference stable active `FR-###`/`QR-###` IDs when applicable.
17. **Cancel obsolete work explicitly.** Product changes can retire tasks. Use `cancel` rather than falsely marking superseded work done; never leave live tasks depending on cancelled prerequisites.
18. **Completed history is immutable, not unquestionable.** Never reopen or rewrite a done task. Independently check it with `roach.py review`; address defects with linked `roach.py correct` work. A completed project may return to execution when the owner requests review, correction, or new work.
19. **Block explicitly.** A blocked task has a durable reason and no live claim. A blocked/paused project offers no new work until reactivated.
20. **Documentation has a budget.** Product intent may be detailed because losing it is expensive. Do not store transcripts, routine progress diaries, or technical facts cheaply recoverable from code/tests/Git.
21. **Coordination pushes must not trigger deploys.** Roach pushes far more often than a human would, because pushes are checkpoints and heartbeats rather than releases. Any connected continuous-deployment host must be configured so only real base-branch application changes deploy. Vercel ships pre-configured via `vercel.json` and `scripts/vercel-ignore.sh`; preserve them when adding framework settings, and configure any other host in-repo before its first push. Verify on the live host immediately after connecting. See `docs/DEPLOYMENT.md`.

## What is actually enforced

Roach prevents drift, forgetting, and races between cooperating agents. It does not prevent a worker from misreporting. Knowing which is which keeps trust calibrated.

**Mechanically enforced** — the coordinator will refuse:

- claiming work whose dependencies, phase, project status, capabilities, or area overlap do not permit it;
- claiming from anywhere but the base branch, where the claim would be committed to a task branch and lost;
- acting on a task owned by a different live worker, or one already terminal on the base branch. Every ownership-changing command answers "who holds this?" from `origin`, never from a possibly stale local copy — `block`, `cancel`, and `adopt` consult it directly, and `claim`, `finish`, `release`, and `heartbeat` refuse when shared state shows a different live owner;
- publishing coordination changes from a task branch, from a base branch carrying unpushed local commits, or by force-pushing;
- publishing anything outside `.agent/`;
- leaving the base branch ahead of origin after a failed push;
- marking a project complete with open tasks, uncovered requirements, or verification that passed on a different commit;
- accepting a product whose required sections are missing, filler, or one-word;
- integrating a merge that fails verification.

`--force` on `adopt`, `block`, and `cancel` deliberately overrides the live-claim refusal and records why. It is an override, not a bypass: the reason is stored in the task record.

- finishing a code-producing task with no work anywhere in the repository — no commits on its claimed branch, no product change on the base since the claim, no recorded merge. `--no-work` waives it deliberately and records the waiver on the task;
- finishing a task whose own `verify` command fails.

**Not enforced — depends on the worker being honest:**

- the text of `--verification`. It is a free-form note, not evidence. A task can be marked done with a sentence that describes work nobody did.
- requirement coverage. Roach checks that a requirement ID appears on a task with acceptance criteria; it cannot check that the task genuinely satisfies it.
- whether the commits it can see are the *right* work. Evidence proves something happened, not that it was correct.
- whether `PLAN.md` describes what the code actually does.
- whether a capability inventory is truthful.

Treat completed-task notes as claims by their author, not as proof. Where proof matters, make it executable: `.agent/VERIFY.json` for project health, a task's own `verify` command for that task.

## Human interruption gate

Outside discovery, ask the human only when progress truly requires:

- credentials, login, MFA/OAuth, account access, or permissions only they can provide;
- a meaningful irreversible/high-impact external action;
- an inaccessible resource or required capability no available worker can supply;
- a consequential product decision that cannot reasonably be inferred.

Use:

`NEED YOU: <one clear action>`

For useful subjective testing, use:

`TEST THIS: <simple real-world steps>`

Do not send routine progress essays or ask "should I continue?".

## Recovery

A fresh worker should:

1. inspect Git status/remotes/current branch/recent commits;
2. fetch the remote when available without discarding local work;
3. read `.agent/PROJECT.md`, `.agent/STATE.json`, `.agent/PRODUCT.md`, `.agent/VERIFY.json`, relevant tasks, `.agent/PLAN.md` when present, and only relevant durable decisions;
4. run `python scripts/roach.py check` when a shell is available;
5. establish a stable worker ID;
6. inventory actual current-session capabilities;
7. route by project status/phase before selecting work.

Commands are written as `python scripts/roach.py ...`. On systems where `python` is not on `PATH` (some Linux distributions), `python3` works identically — the script supports both. Do not assume one interpreter name works everywhere; check once at session start and use whichever resolves.

If a shell is unavailable but repository/GitHub API tools can safely read/write the repo, `roach.py` is the reference semantics rather than an absolute transport requirement. **`docs/PROTOCOL.md` is the specification written for you** — the exact liveness, eligibility, claim, publish, and reconcile rules, stated precisely enough to implement. `schemas/` carries the machine-readable shapes.

Two commands cannot be reproduced without a shell: `verify` runs a command by definition, and `integrate` needs a real merge plus verification of the merged result. A no-shell worker can claim, implement, and publish, but a shell-capable worker must converge its work. If the environment cannot preserve the invariants in `docs/PROTOCOL.md`, do not claim shared work — a worker that half-implements the protocol is worse than one that abstains, because the others trust the records it writes.

## Project status

`project_status` is separate from lifecycle phase:

- `active` — normal work may proceed;
- `blocked` — project-wide blocker; no new work should be claimed;
- `paused` — intentionally suspended; no new work should be claimed;
- `complete` — all current work is terminal and required verification passed.

Use `roach.py project-status blocked|paused --reason ...` and `project-status active` rather than editing state casually. `complete` is only entered through the gated completion transition.

## How this project got here

`.agent/STATE.json` records an `adoption` block. `greenfield` means the project was created from the template and has followed the method from its first commit. `brownfield` means Roach was installed into a repository that already existed, and `baseline_commit` is where that happened.

In a brownfield project, **history at or before `baseline_commit` predates the method**. Those commits reference no task and were never meant to. Do not try to retrofit them, and do not treat their absence from the task graph as a defect.

Brownfield also changes who owns `AGENTS.md` and `CLAUDE.md`: the project does. Only the region between the `BEGIN ROACH METHOD` / `END ROACH METHOD` markers belongs to the template, and `roach.py upgrade` replaces only that region. Put project-specific instructions outside the markers, where they will survive.

## Fresh template / discovery

A new template starts with:

- `project_status: active`;
- phase `uninitialized`;
- draft `.agent/PRODUCT.md`;
- reserved `T000 — Define product with owner`.

A worker with `user-dialogue` + `repo-write` may claim T000, then transition to discovery. It should brainstorm/clarify with the owner, update PRODUCT after meaningful decisions, and replace the PROJECT summary placeholder. Do **not** start implementation merely because the repository is empty.

PRODUCT has a required core: Vision, Goals, Non-Goals, Users/Audience, Core Experience, Requirements, Constraints, Success Criteria, and Open Questions. Add domain-specific sections when useful.

Only requirements in PRODUCT's active `## Requirements` section are current mechanical scope. Never recycle a retired requirement ID for a different meaning. Historical done/cancelled tasks may retain retired IDs.

When the product is understood well enough to plan:

1. present a concise product-intent checkpoint;
2. incorporate corrections;
3. after owner confirmation, run:

```bash
python scripts/roach.py accept-product \
  --worker <stable-worker-id> \
  --verification "owner confirmed product intent"
```

`accept-product` validates PRODUCT/PROJECT, verifies that this worker owns the active discovery task, marks that discovery task done, records product acceptance, initializes `.agent/PLAN.md`, moves to planning, and creates/ensures the planning task. **Do not separately finish the discovery task.** Keeping this transition together avoids a recovery deadlock.

## Later product changes

For a clear owner-requested change, update PRODUCT and propagate consequences into PLAN/tasks.

For a large ambiguous pivot:

- finish/release conflicting live non-discovery work first when practical;
- `roach.py transition discovery` creates/reuses a new discovery task rather than reopening T000;
- clarify the changed intent and obtain a new product-intent checkpoint;
- the new discovery owner runs `accept-product`, which creates a planning task depending on that discovery cycle.

`transition discovery` normally refuses while non-discovery claims are live; use `--allow-live-work` only as a deliberate exception after considering the coordination risk.

Do not try to reclaim T000 or another completed discovery task. Those records prove what was accepted at the time. A new discovery cycle makes the Bible editable as a draft, obtains a fresh owner checkpoint, and preserves both versions in Git/task history.

## Planning

Planning owns **how to build the accepted product** and normally does not request technical approval.

`accept-product` initializes `.agent/PLAN.md` with required sections. The planner fills and keeps these recognizable:

- Technical Approach;
- Architecture / Components;
- Project Structure;
- Dependencies / Integrations;
- Verification Strategy;
- Risks / Unknowns;
- Requirement Coverage.

The planner must also:

- populate `.agent/VERIFY.json` with the required practical health command;
- create the initial task graph;
- link current work to active requirements;
- assign only genuinely necessary hard capabilities;
- add optional design/research/spec files only when complexity justifies them;
- use bounded research/design/verification tasks if the current environment lacks a capability needed for reliable planning.

A requirement already satisfied in a brownfield project can be covered by a done verification/implementation record with concise evidence. Ideas not yet committed to current scope stay in PRODUCT Future/Possibilities rather than becoming uncovered active requirements.

Before execution:

1. change PLAN status from `DRAFT` to `READY` after the required sections are actually filled;
2. finish the planning task;
3. run `python scripts/roach.py ready`;
4. resolve mechanical gaps, including dependency cycles/cancelled dependencies/current requirement coverage;
5. perform a semantic PRODUCT → PLAN → tasks consistency pass;
6. run `python scripts/roach.py transition execution`.

A later deliberate technical re-plan may use `transition planning`, which creates/ensures a new planning task and returns PLAN status to DRAFT.

Do not reclaim a completed planning task. `transition planning --publish` is the supported design/architecture revision path, including after project completion.

## Capability-aware execution

When `project_status` is active and phase is execution:

```bash
python scripts/roach.py status --cap ...
python scripts/roach.py next --cap ... --limit 5
```

If nothing is eligible:

```bash
python scripts/roach.py next --cap ... --explain
```

Roach filters project status/phase, dependencies, live claims, area overlap, and hard capabilities. It ranks by priority, preferred-capability match, and task number. The helper determines eligibility; the worker determines suitability.

Pass `--worker <your-id>` to `next --explain` so your own claims are reported as yours rather than as a conflict to force your way past.

Every read-only command takes `--json` — `status`, `next`, `check`, `ready`, `doctor`, `capabilities`. Parse that rather than the prose, which exists for humans and is free to change:

```bash
python scripts/roach.py next --cap repo-write --cap shell --json
python scripts/roach.py doctor --json
```

Exit codes are unchanged: `check`, `ready`, and `doctor` still exit non-zero when they have something to report.

Claim with the same capability inventory and stable worker ID:

```bash
python scripts/roach.py claim T012 \
  --worker codex-a31f \
  --cap repo-write \
  --cap shell \
  --publish
```

Claim from the base branch, publish, and only then create the task branch. Task records are tracked files, so a claim made on a task branch is committed to that branch and reverts on checkout — the claim never reaches shared state and the worker cannot finish its own work. Roach refuses this rather than letting it happen silently.

`--publish` is intentionally conservative: it runs only from the base branch, refreshes `origin`, refuses any working-tree change outside `.agent/`, commits pending coordination state as one commit, and never force-pushes. The base branch defaults to `main`; set `ROACH_BASE_BRANCH` only if the repository intentionally uses another shared base.

## Publishing, reconciling, and retrying

`--publish` carries all pending `.agent/` state, because coordination state is one unit — a command that required you to edit `PROJECT.md` must be able to publish it.

Being **behind** `origin` is the normal steady state when two or three workers are publishing claims and heartbeats, so publishing fast-forwards a base that is only behind and carries on. What it refuses is a base that is **ahead**: unpushed local commits must never ride along inside a coordination publish. Push or reset those deliberately first.

Three distinct situations, three different answers:

| Situation | Command |
| --- | --- |
| State change succeeded, publish failed | `roach.py publish` |
| Pending coordination edit collides with one another worker already published | `roach.py reconcile` |
| Base branch carries unpushed commits of your own | `git push origin <base>`, then publish |

When a command's state change succeeds but publishing fails, the change is already in the working tree. **Do not re-run the command**; it will refuse a precondition it has itself satisfied. Fix the cause and run `roach.py publish`.

When two workers create a task from the same base they compute the same free id, and the loser's edit then blocks its own fast-forward. `reconcile` is the way out: it sets pending coordination edits aside, fast-forwards, and replays them — renumbering a task that lost the id race, and keeping its content. Anything it cannot replay without overwriting shared state is preserved under `.roach-reconcile/` and named in the report, never dropped silently. Review those, then re-run the original command if the change is still wanted.

`doctor` distinguishes these cases and names the right one.

## Task state changes

Normal states are managed with the helper:

```bash
python scripts/roach.py heartbeat T012 --worker codex-a31f
python scripts/roach.py release T012 --worker codex-a31f --handoff "..."
python scripts/roach.py block T012 --worker codex-a31f --reason "..."
python scripts/roach.py unblock T012
python scripts/roach.py cancel T012 --reason "..."
python scripts/roach.py finish T012 --worker codex-a31f --verification "..."
```

Finishing requires a live ownership record; unclaimed planned work cannot simply be declared done. Blocking releases ownership and preserves a reason. Cancelling is terminal and records why the work was retired.

Finishing also requires **evidence that work happened**. For a code-producing kind — `implementation`, `correction`, `fix`, `refactor`, `spike` — Roach looks for commits on the claimed branch, a recorded merge from `integrate`, or product files changed on the base since the claim. It cannot tell whether your `--verification` sentence is true, but it can tell that nothing at all landed, which is the more common mistake. Work that genuinely produces no repository change — a review finding, an owner conversation, a decision — passes `--no-work`, and the waiver is stored on the task.

A task may also declare its own executable check:

```bash
python scripts/roach.py create --title "Add save browser" \
  --requirement FR-021 --requires repo-write \
  --acceptance "saved games can be listed, opened, and deleted" \
  --verify "npm test -- save-browser"
```

`finish` runs it and refuses when it fails. This is where task-level proof belongs, rather than in prose. It is repository-supplied shell text with the same trust boundary as `.agent/VERIFY.json` — see `docs/SECURITY.md`.

These commands reconcile against `origin/<base>` first and refuse when shared state shows a different live owner, or a task already terminal there. An unpublished local claim keeps working offline.

## Reviewing and correcting completed work

`done` is an immutable historical statement, not a ban on independent review. Never change a done task back to planned or overwrite its evidence.

Create a linked verification task:

```bash
python scripts/roach.py review T012 --publish
```

The new task inherits T012's current requirement links, areas, and useful preferred capabilities, while T012 remains done. Claim and execute the new review normally. Record concrete evidence when finishing it.

If the review confirms a defect, finish the review with the findings, then create linked corrective work:

```bash
python scripts/roach.py correct T013 \
  --title "Fix save corruption found in review" \
  --acceptance "interrupted saves preserve the last valid file" \
  --publish
```

Here T013 is the completed review task. Corrective work may also link directly to a completed implementation task when the defect is already known and an independent review is unnecessary.

When `project_status` and phase are both `complete`, `review` and `correct` atomically return the project to active execution while creating the new task. `transition execution --publish` also supports explicit owner-requested reopening for other new work. Completion remains gated until every new task is terminal and required project verification passes again when product code changed.

## Taking over abandoned work

A session that dies mid-task leaves a claim its successor cannot release, because the successor uses a different worker ID. Once the claim is provably stale — lease expired and no recent pushed task-branch activity — adopt it.

"Provably stale" is decided from `origin`, not from your checkout. A worker whose copy predates a claim would otherwise see an expired lease for ownership that has since been renewed, and quietly take a task somebody is actively working on. `adopt` refuses that, and names the owner shared state actually knows about.

```bash
python scripts/roach.py adopt T012 --worker <new-worker-id> --publish
```

`adopt` refuses while a claim is still live. When you positively know that session is gone rather than merely quiet, override it deliberately:

```bash
python scripts/roach.py adopt T012 --worker <new-id> --force --reason "prior session crashed"
```

It records `adopted_from`, and `adopted_reason` when forced, so the handover stays visible. Do not hand-edit a task record to clear ownership.

A claim's lease is what makes an abandoned task wait; `ROACH_STALE_MINUTES` governs branch-activity liveness, not the lease. Claim with `--lease-minutes` if a shorter recovery window suits the session.

## Integrating finished work

Merging into the base branch is the one operation that can destroy shared work, so it has its own command:

```bash
python scripts/roach.py integrate T012 --worker <worker-id> --push
python scripts/roach.py finish T012 --worker <worker-id> --verification "..." --publish
```

**Integrate before finishing.** `integrate` requires a live claim and `finish` releases it, so the reverse order cannot work.

`integrate` requires a clean base branch matching `origin`, merges the claimed task branch, runs the configured verification on the **merged result**, and hard-resets the merge away if verification fails — recording the failure in `.agent/STATE.json` so the next worker knows the branch is broken. A passing run commits its own verification record with the merge. Prefer this over a hand-rolled merge.

## Diagnosing a confused repository

```bash
python scripts/roach.py doctor
```

Reports states the repository cannot otherwise explain, each with the command that fixes it:

- coordination state sitting uncommitted, invisible to every other worker;
- a base branch ahead of or behind `origin`, which blocks publishing or bases work selection on a stale past;
- pending edits on a stale base — the wedge where publishing and pulling each refuse because of the other, which `reconcile` resolves;
- coordination edits stranded on a task branch, where they can never reach shared state;
- task records whose status or owner disagrees with shared state, distinguishing a merely stale checkout from one contradicting a live claim;
- stale claims that should be adopted;
- verification that passed on a different commit;
- coordination files that will not parse;
- protocol drift, and deployment protection that has been unwired.

`check` and `doctor` report an unreadable file as one finding among the others rather than aborting on it. A repository with a corrupt task record is exactly when you need the rest of the diagnosis.

`check` validates that state is well-formed; `doctor` validates that it is *shared*. Both halves can be individually valid while the repository is incoherent, so run `doctor` when something is stuck and after any interrupted session.

`check` and `ready` judge the working tree, while `status`, `next`, and `claim` read `origin/<base>`. Both print which view they used, so a `READY` from a checkout that is behind shared state says so rather than reading as a verdict about the project.

Use `python scripts/roach.py migrate` to bring an older project's state up to the current protocol version.

## Liveness and handoff

Pushed task-branch activity is the normal heartbeat. A claim is live while either its lease is valid or the claimed remote task branch has recent pushed activity. Default recent threshold is two hours, configurable through `ROACH_STALE_MINUTES` with a 15-minute minimum.

Before disappearing with unfinished work, commit/push a coherent WIP checkpoint, store only essential continuation context in `handoff`, and release if the worker is not expected to return. Never merge known-broken WIP to the base branch.

## Continuous deployment hosting

Roach's push rate is deliberately high. Coordination commits, WIP checkpoints, and heartbeat pushes all reach the remote. A host that builds on every push (Vercel, Netlify, Cloudflare Pages, and similar) will interpret each one as a release request and can exhaust free-tier build/deployment allowances, producing failed or cancelled deployments unrelated to code quality.

The worker that connects such a host owns this configuration. Do not connect a deployment host without it.

Required outcomes, whatever the host:

- pushes to `roach/*` task branches do not produce deployments;
- commits touching only `.agent/` coordination state do not produce deployments;
- only the base branch deploys to production;
- exactly one deployment trigger exists — never combine host CLI deploys with Git-integration deploys for the same commit.

Prefer in-repo configuration over dashboard settings. In-repo config is durable memory under Rule 1: a fresh worker can read it, reason about it, and revert it. A dashboard toggle is invisible to recovery and violates the method's core premise.

Dashboard/API-only settings are an owner action. Surface them with `NEED YOU:` rather than changing account settings autonomously.

Concrete Vercel configuration, host comparison, and background live in `docs/DEPLOYMENT.md`.

## Verification and completion

Project health commands live in `.agent/VERIFY.json`:

- `quick` — inexpensive frequent health check;
- `full` — broader integration-quality test/lint/build;
- `smoke` — automatable user-flow/end-to-end check when useful.

`roach.py verify <level>` records pass/fail, timestamp, and current commit when available in STATE. Task-specific visual/computer-use/subjective checks belong in task verification evidence.

`transition complete` is gated. Completion requires:

- accepted coherent PRODUCT;
- READY coherent PLAN;
- every task terminal (`done` or deliberately `cancelled`);
- every current accepted requirement backed by completed non-planning task evidence;
- required project verification passed at the configured level.

Do not use completion as a manual label for an unfinished backlog.

## Detailed procedure

- `.agents/skills/project-continuity/SKILL.md` — canonical detailed procedure.
- `.agent/PRODUCT.md` — authoritative product intent.
- `.agent/PLAN.md` — current technical strategy once planning begins.
- `.agent/tasks/README.md` — task/capability/state schema.
- `docs/EXAMPLE.md` — one project from empty template to complete, with real command output.
- `docs/ADOPTING.md` — installing the method into a repository that already exists.
- `docs/PROTOCOL.md` — normative rules, for a worker reproducing them without a shell.
- `schemas/` — JSON Schema for task records, `STATE.json`, and `VERIFY.json`.
- `docs/MULTI_AGENT.md` — coordination and branch/worktree behavior.
- `docs/DEPLOYMENT.md` — continuous-deployment host configuration and why it is required.
- `docs/SECURITY.md` — what running verification executes, and what Roach does not defend against.
- `docs/LIMITATIONS.md` — known limitations and deliberate non-goals; read before changing the coordinator.
- `python scripts/roach.py --help` — deterministic coordinator reference.

If detailed documents conflict with this file, follow this file plus explicit user instructions and safety requirements.

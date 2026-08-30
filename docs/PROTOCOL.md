# Roach protocol v0.5 — normative reference

`scripts/roach.py` is the reference implementation. This document is the
*specification*, written for a worker that cannot run it: an agent with
repository or GitHub API tools but no shell.

`AGENTS.md` has always said such a worker may reproduce Roach coordination "if
it can preserve the same invariants". This is that list, stated precisely
enough to implement. Machine-readable shapes live in `schemas/`.

Where this document and `scripts/roach.py` disagree, the script is correct and
this document is a bug.

## 0. What a no-shell worker can and cannot do

Reproducible through a repository API:

| Operation | Reproducible | Notes |
| --- | --- | --- |
| `status`, `next` | yes | read-only; §3 and §4 |
| `create` | yes | §5 |
| `claim`, `heartbeat`, `release` | yes | §6 |
| `block`, `unblock`, `cancel` | yes | §7 |
| `adopt` | yes | §8 |
| `finish` | partly | §9 — evidence rules apply; a task `verify` command cannot run |
| `publish` | yes | §10 — one commit, no force |
| `reconcile` | yes | §11 |
| `verify` | **no** | needs command execution by definition |
| `integrate` | **no** | needs a real merge plus verification of the merged result |

A no-shell worker can therefore claim work, implement it, and publish
coordination state, but cannot converge its own work to the base branch or
produce executable verification evidence. Plan for a shell-capable worker to
integrate it, or scope no-shell workers to research, design, and documentation.

If you cannot preserve every invariant below, do not claim shared work. A
worker that half-implements this protocol is worse than one that abstains,
because the other workers trust the records it writes.

## 1. Vocabulary

- **base branch** — the shared branch. `main` unless `ROACH_BASE_BRANCH` says otherwise.
- **shared state** — the contents of `.agent/` on `origin/<base>`. This, not your checkout, is the answer to every ownership question.
- **worker id** — one stable string per session, matching `[A-Za-z0-9._-]{1,48}` after normalisation. Never derived from a process id: separate invocations from one session must be recognisable as the same worker.
- **coordination path** — any path under `.agent/` except `.agent/tests/`.

## 2. Time

All timestamps are UTC ISO-8601 with second precision and a `Z` suffix:
`2026-08-17T04:29:34Z`. Parse a missing timezone as UTC.

## 3. Liveness

This is the rule most worth getting exactly right, because it decides whether
two workers can hold the same task.

A claim is **live** if either condition holds:

1. **Recent branch activity.** The claimed branch exists as `refs/remotes/origin/<branch>`, its last commit date is not earlier than `claim.claimed_at`, and that date is within `STALE_MINUTES` of now.
2. **Valid lease.** `claim.lease_expires_at` is in the future.

Otherwise the claim is **stale**.

`STALE_MINUTES` is 120, overridden by the `ROACH_STALE_MINUTES` environment
variable, clamped to a minimum of 15. A non-integer value is an error, not a
fallback to the default.

Note the asymmetry: the lease governs how long an *unworked* claim holds, while
pushed branch activity is the normal heartbeat once work starts. A pushed
checkpoint therefore does two jobs — it preserves work and proves liveness.

## 4. Eligibility

A task is claimable only when **all** of these hold, evaluated against shared
state:

1. `status` is not `done` or `cancelled`;
2. `project_status` is `active`;
3. `status` is not `claimed`, `active`, or `verify` — or if it is, the claim is stale (and then the correct operation is `adopt`, not `claim`);
4. `status` is not `blocked`;
5. the phase permits this `kind`:
   - `uninitialized` or `discovery` → only `discovery`;
   - `planning` → `planning`, `research`, `design`, `verification`;
   - `execution` → any kind;
   - `complete` → nothing;
6. every id in `depends_on` exists and has status `done`;
7. no other task with a **live** claim shares an entry in `areas`;
8. the worker's capability inventory is a superset of `requires`.

Ranking among eligible tasks, in order: `priority` (`urgent`, `high`, `normal`,
`low`), then the number of `prefers` entries the worker has (more first), then
the numeric part of the task id (lower first).

`requires` is a hard gate. `prefers` never excludes.

## 5. Creating a task

- Choose the lowest unused `T###` across both local records and shared state. This does not make concurrent creation safe — two workers at the same base compute the same number. The push race catches it; §11 resolves it.
- At least one non-empty `acceptance` entry is required.
- Every id in `requirements` must appear in the active Requirements section of `.agent/PRODUCT.md`.
- Every id in `depends_on` must already exist and must not be the task itself.
- `kind` and every capability token must match `^[a-z0-9][a-z0-9._:-]*$`.
- Write the full record shape from `schemas/task.schema.json`, including the coordinator fields as `null`.

## 6. Claiming

Preconditions:

1. you are on the base branch — a claim committed to a task branch reverts on checkout, so shared state never sees it and you cannot finish your own work;
2. refresh `origin` successfully; a failed refresh means stop, not proceed on stale state;
3. the task is eligible per §4 **in shared state**;
4. you have a stable worker id.

Then set `status` to `claimed` and write a claim:

```json
{
  "worker": "<your id>",
  "claimed_at": "<now>",
  "lease_expires_at": "<now + lease minutes, default 120, minimum 5>",
  "branch": "roach/<task-id>-<your id>",
  "base_commit": "<base branch HEAD>"
}
```

Also set `verification` and `handoff` to `null`.

Publish (§10) **before** creating the task branch.

`heartbeat` extends `lease_expires_at` and promotes `claimed` to `active`.
`release` clears the claim and returns `claimed`/`active`/`verify` to `planned`.

## 7. Blocking and cancelling

Both consult shared state first and refuse when another worker holds a live
claim, unless deliberately forced with a recorded reason.

- `block`: status `blocked`, claim `null`, `verification` `null`, `handoff` set to `BLOCKED: <reason>`. A blocked task must carry a durable reason.
- `unblock`: status `planned`, claim `null`, `handoff` `null`.
- `cancel`: status `cancelled`, claim `null`, `handoff` `null`, `verification` set to `cancelled: <reason>`. Terminal and immutable.

A non-cancelled task must never depend on a cancelled one.

## 8. Adopting

`adopt` transfers ownership of an abandoned task. Ownership is decided from
**shared state**, never from your checkout: a stale copy shows an expired lease
for a claim that may since have been renewed.

1. Read the task from `origin/<base>`.
2. If its claim is live and held by another worker, refuse — unless the caller explicitly forces the takeover *and* supplies a reason.
3. Write a new claim as in §6, plus `adopted_from` naming the previous owner, plus `adopted_reason` when forced.
4. If status was not already `claimed`/`active`/`verify`, set it to `claimed`.

Never hand-edit a record to clear ownership. The handover must stay visible.

## 9. Finishing

Preconditions: status is `claimed`, `active`, or `verify`; the claim names you;
`verification` text is non-empty.

**Evidence.** Before marking a task done, establish that work exists:

1. an `integration.merge_commit` recorded by `integrate`; or
2. commits on `refs/remotes/origin/<claim.branch>` that are not reachable from the base; or
3. non-coordination files changed between `claim.base_commit` and the base HEAD.

If none hold and `kind` is one of `implementation`, `correction`, `fix`,
`refactor`, `spike`, refuse. Work that legitimately produces no repository
change is finished with the waiver recorded as `evidence.work_waived: true`.

**Task check.** If the task declares `verify`, run it and refuse on failure. A
no-shell worker cannot do this: do not finish a task that declares one.

Then set `status` to `done`, clear `claim` and `handoff`, and write
`completed_at`, `commit`, and `evidence`.

A `done` task is immutable. Never reopen it. Scrutinise it with a new
`verification` task linked by `review_of`, and correct it with a new task
linked by `correction_of`.

## 10. Publishing

One commit containing **only** coordination paths.

1. You must be on the base branch.
2. Refresh `origin`.
3. If the base has commits `origin` does not, refuse. A coordination publish must never carry unrelated local commits.
4. If the base is only behind, fast-forward it. Being behind is the normal state with several workers, not an error.
5. If the working tree contains any change outside `.agent/`, refuse.
6. Commit all pending coordination paths as one commit and push.
7. On push rejection, integrate normally and retry. **Never force-push.** If the push still fails, roll the local commit back so the base never sits ahead of `origin` — a stranded local commit blocks every later publish for every worker in the repository.

## 11. Reconciling

When a pending coordination edit collides with one another worker already
published, the base cannot fast-forward and the publish cannot proceed.

1. Refuse if the base is *ahead* of origin — that is a divergence, not a stale checkout.
2. Snapshot every pending coordination edit, along with the committed version it was based on.
3. Restore those paths and fast-forward the base.
4. Replay each edit:
   - a **new task record** whose id is now taken by a different task takes the next free id, keeping all other content; rewrite `depends_on`, `review_of`, and `correction_of` references to the old id;
   - an edit whose upstream version **did not change** is reapplied verbatim;
   - an edit whose upstream version **did change** is set aside, unmodified, outside `.agent/`, and reported. Shared state wins.
5. Never discard an edit silently.

## 12. Lifecycle transitions

Phase and project status are independent. `transition` moves the phase;
`project-status` moves the status. Neither may be set by editing `STATE.json`
casually — the gates below are the point.

### `accept-product`

The one atomic step out of discovery. It exists as a single operation because
splitting acceptance from discovery completion created a recovery deadlock:
phase became `planning` while an unfinished discovery task still blocked the
planning dependency.

Preconditions: `project_status` is `active`; phase is `uninitialized` or
`discovery`; the caller owns a live discovery task; `PRODUCT.md` passes §13.

In one publication: mark that discovery task `done`; set
`product_definition` to `{"status": "accepted", "accepted_at": now}`; set phase
to `planning`; set the PRODUCT `Status:` line to `ACCEPTED`; create `PLAN.md`
from the skeleton if absent; create a planning task depending on the discovery
task. Do **not** separately finish the discovery task.

### `transition discovery`

For a large, ambiguous product pivot. Refuses while non-discovery claims are
live unless deliberately overridden. Sets `product_definition` back to draft,
sets the PRODUCT `Status:` line to a draft marker, and creates or reuses a
**new** discovery task. Never reopen T000 or any completed discovery task —
those records prove what was accepted at the time.

### `transition planning`

For a technical re-plan that preserves product intent. Requires accepted
product intent. Returns `PLAN.md` to `Status: DRAFT` and creates or ensures a
planning task. Never reclaim a completed planning task.

### `transition execution`

Requires everything in §13 to pass. Also reactivates a completed project when
the owner asks for new work.

### `transition complete`

Requires, in addition to §13: every task terminal (`done` or `cancelled`);
every active requirement referenced by a **completed** non-planning task; and
the required verification recorded as passed, at the configured level, with the
currently configured command, on a commit whose difference from HEAD touches
only coordination paths.

That last clause matters: publishing a claim moves HEAD without touching
product code, so treating any new commit as invalidation would make completion
unreachable — recording the final task is itself a commit.

Completion is a checkpoint, not a freeze. `review`, `correct`, and
`transition execution` each reopen it without rewriting history.

### `project-status`

`active` clears the blocker. `blocked` and `paused` each require a non-empty
reason stored in `STATE.blocked`. `complete` is reachable only through the
gated completion transition. A blocked or paused project offers no claimable
work (§4).

## 13. Readiness

`ready` reports whether the project may enter execution. Every condition:

- `product_definition.status` is `accepted`;
- `PRODUCT.md` contains all of Vision, Goals, Non-Goals, Users / Audience, Core Experience, Requirements, Constraints, Success Criteria, Open Questions — each with real content, not template placeholder text, not filler such as "TBD", and not a single word;
- `PROJECT.md` no longer holds the uninitialized placeholder;
- at least one active `FR-###` or `QR-###` requirement parses, with no duplicate ids and no malformed declarations;
- `PLAN.md` is `Status: READY`, contains Technical Approach, Architecture / Components, Project Structure, Dependencies / Integrations, Verification Strategy, Risks / Unknowns, and Requirement Coverage, and retains no template placeholder text;
- `VERIFY.json` configures a command for `required_level`;
- the planning task is terminal;
- at least one non-discovery, non-planning task exists;
- every active requirement is referenced by such a task, and every task referencing a requirement declares acceptance criteria;
- no live task references an unknown requirement;
- the dependency graph is acyclic and no live task depends on a cancelled one.

## 14. Diagnostics

`check` answers whether coordination state is **well-formed**, judged against
the working tree. `doctor` answers whether it is **shared**, judged against
`origin`. Both halves can be individually valid while the repository is
incoherent, which is the state a fresh worker is least equipped to reason
about, so both report which view they used.

Neither may abort on the first unreadable file. A repository with a corrupt
record is precisely when the rest of the diagnosis is needed: report it as one
finding among the others and continue.

`migrate` brings an older project's `STATE.json` and task records up to the
current protocol version, adding coordinator-written fields as `null`.

`upgrade` pulls template-owned files from an upstream template — the
coordinator, the agent contract, the skills, the schemas, and `docs/` — and
leaves project state untouched. That boundary is what makes it safe to run:
`PRODUCT.md`, `PLAN.md`, `PROJECT.md`, `STATE.json`, `VERIFY.json`,
`DECISIONS.md`, task records, `README.md`, and all application code belong to
the project and are never rewritten. A file removed upstream is left in place
rather than deleted. Run `migrate` and `check` afterwards.

Because Roach is distributed by copying, a project otherwise keeps whatever
coordinator revision it was created from forever, and a fix to a coordination
bug never reaches it.

`capabilities` lists the standard vocabulary: `user-dialogue`, `repo-read`,
`repo-write`, `shell`, `git`, `network`, `web-research`, `browser-interaction`,
`computer-use`, `vision`, `image-generation`. Project-specific lowercase tokens
are allowed. Capabilities describe abilities, never model or vendor identity —
the same model has different abilities in a CLI, a browser, and an IDE.

## 15. What the protocol does not enforce

Stated plainly so trust stays calibrated:

- the truth of `verification` text — it is a claim by its author;
- whether the commits it can see are the *right* work — evidence proves that something happened, not that it was correct;
- whether a task genuinely satisfies the requirement it references;
- whether `PLAN.md` describes what the code does;
- whether a capability inventory is honest.

Where proof matters, make it executable: `.agent/VERIFY.json` for project
health, a task's `verify` command for that task.

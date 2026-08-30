# One project, start to finish

A complete walkthrough of a small project using Roach: empty template to
`complete`. Every command and every output below is real, captured from a
sandbox run against this template.

This is the document to read if you want to know what using Roach actually
*looks like*, rather than what it promises. `README.md` describes the method;
this shows a project going through it.

The product is deliberately tiny — a command-line note taker — so the Roach
mechanics stay visible instead of being buried under application code.

---

## Before anything

Create a repository from the template, give it a remote, and open it in an
agent environment. The owner then says something like:

> Use the Roach Method in this repository. Help me define and build a little
> command line tool for saving notes.

Everything below is the agent's work. The owner appears twice more: once to
confirm the product, once if something needs their hands.

## 1. The worker orients itself

```console
$ export ROACH_WORKER=agent-alpha
$ python scripts/roach.py status
Roach status (origin/main)
  project_status:active | phase:uninitialized
  planned:1 | claimed:0 | active:0 | blocked:0 | verify:0 | done:0 | cancelled:0
Next: inventory capabilities, then run `roach.py next --cap ...`.
```

Note what `status` refuses to do: it will not recommend work until the worker
says what it can actually do. Capabilities are never inferred from the model or
the product name.

```console
$ python scripts/roach.py next --cap repo-write --cap user-dialogue
T000    Define product with owner       discovery
```

A worker *without* `user-dialogue` gets told why it cannot help yet:

```console
$ python scripts/roach.py next --cap shell --explain
NONE
T000    missing capabilities: repo-write, user-dialogue
```

## 2. Claim the conversation, then have it

```console
$ python scripts/roach.py claim T000 --cap repo-write --cap user-dialogue --publish
Claimed T000 as agent-alpha; branch roach/T000-agent-alpha.
Published: .agent/tasks/T000.json

$ python scripts/roach.py transition discovery --publish
Project phase is now discovery; discovery task: T000.
Published: .agent/PRODUCT.md, .agent/STATE.json
```

T000 is a normal claimed task, so exactly one worker owns the owner
conversation. Discovery is the one phase where asking questions *is* the work.
The worker asks one thing at a time and writes each answer into `PRODUCT.md`
as it goes, so a crashed session loses the chat but not the decisions.

Roach will not accept a product that is still the template:

```console
$ python scripts/roach.py accept-product --verification "owner confirmed"
Cannot accept product intent:
- PRODUCT.md still contains template placeholder: Describe the product in plain language:
- PRODUCT.md still contains template placeholder: Replace with concrete goals discovered with the owner.
- PRODUCT.md still contains template placeholder: Describe the primary user, player, operator, or audience
- PROJECT.md still has the uninitialized summary placeholder
```

It also rejects sections that are present but say nothing — "TBD", "N/A", a
single word. An empty product definition is inherited by every later decision,
so it is caught here rather than three days later.

## 3. The one checkpoint

The worker summarises what it believes the owner wants and asks for
confirmation. That is the **only** approval gate in the whole lifecycle.
After it, technical decisions are the agent's.

```console
$ python scripts/roach.py accept-product --verification "owner confirmed product intent" --publish
Accepted product intent, completed T000, moved to planning, and ensured planning task T001.
Published: .agent/PLAN.md, .agent/PRODUCT.md, .agent/PROJECT.md, .agent/STATE.json,
           .agent/tasks/T000.json, .agent/tasks/T001.json
```

One command did six things, and deliberately so: acceptance and discovery
completion in separate steps could crash in between and deadlock the project.

Requirements may be written however suits the product — a list, a table, under
sub-headings:

```markdown
## Requirements

| ID | Requirement |
| --- | --- |
| FR-001 | The user MUST be able to add a note from the command line. |
| FR-002 | The user MUST be able to list previously saved notes. |

### Quality

- **QR-001**: Adding a note MUST complete in under 200ms on a normal laptop.
```

All three parse. A line that *looks* like a requirement but cannot be read is
reported rather than silently ignored:

```console
$ python scripts/roach.py check
Roach state INVALID (local working tree, level with origin/main):
- PRODUCT.md Requirements: FR-003 has no requirement text
```

## 4. Planning

The planner claims T001, fills in `PLAN.md`, configures the health commands in
`VERIFY.json`, and creates the backlog.

```console
$ python scripts/roach.py claim T001 --cap repo-write --publish
$ python scripts/roach.py create --title "Add note command" \
    --requirement FR-001 --requirement QR-001 \
    --requires repo-write --area cli \
    --acceptance "notes add stores a note and exits 0"
Created T002: Add note command

$ python scripts/roach.py create --title "List notes command" \
    --requirement FR-002 --requires repo-write --area listing \
    --acceptance "notes list prints every saved note"
Created T003: List notes command

$ python scripts/roach.py finish T001 --verification "plan ready, backlog created" --publish
Marked T001 done (no repository change, waived).
```

`create` refuses a requirement that is not in `PRODUCT.md`, and refuses a task
with no acceptance criteria. Neither is bureaucracy: an unlinked task drifts
from intent, and a task with no definition of done cannot be reviewed later.

The readiness gate is mechanical, and it lists everything at once:

```console
$ python scripts/roach.py ready
NOT READY (local working tree, level with origin/main)
- PLAN.md status must be READY
- PLAN.md still contains template placeholder: Replace with the chosen implementation approach
- VERIFY.json required verification command is not configured
- no post-planning work exists
- planning task is not done/cancelled
- accepted requirements have no task coverage: FR-001, FR-002, QR-001
```

Once each is addressed:

```console
$ python scripts/roach.py ready
READY (local working tree, level with origin/main)

$ python scripts/roach.py transition execution --publish
Project phase is now execution.
```

## 5. Execution

```console
$ python scripts/roach.py next --cap repo-write --cap shell --limit 5
T002    Add note command        implementation
T003    List notes command      implementation

$ python scripts/roach.py claim T002 --cap repo-write --cap shell --publish
Claimed T002 as agent-alpha; branch roach/T002-agent-alpha.
```

Claim first, publish, *then* branch. Task records are tracked files: a claim
made on a task branch is committed to that branch and vanishes on checkout, so
shared state never sees it. Roach refuses that rather than letting it happen.

Now the actual work, on the task branch, pushed as it goes — each push is both
a recovery checkpoint and proof to other workers that the task is still alive.

```console
$ git checkout -b roach/T002-agent-alpha
$ ... write notes.py and app_tests/test_notes.py ...
$ git commit -qm "wip(T002): add note storage" && git push -u origin roach/T002-agent-alpha
```

## 6. Converge, then finish

Merging into the shared base is the one operation that can destroy other
people's work, so it has its own command — and it verifies the *merged result*,
not the branch in isolation:

```console
$ git checkout main
$ python scripts/roach.py integrate T002 --push
Merged origin/roach/T002-agent-alpha; running quick verification on the merged result...
.
----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
quick verification passed on the merged result.
Pushed main.
Next: python scripts/roach.py finish T002 --worker agent-alpha --verification "..."
```

If verification had failed, the merge would have been rolled back and the
failure recorded in `STATE.json`, so the next worker learns the branch is
broken instead of rediscovering it.

**Integrate before finish** — `integrate` needs the live claim that `finish`
releases.

```console
$ python scripts/roach.py finish T002 --verification "quick suite passed on merged result" --publish
Marked T002 done (merged as 0d025a0b).
```

That `merged as 0d025a0b` is the point. Finishing requires evidence that work
exists. Try it without:

```console
$ python scripts/roach.py finish T003 --verification "it works, trust me"
T003 is a implementation task but the repository shows no work for it: no commits
on the claimed branch and no product change since the claim.
Roach cannot check whether --verification text is true, but it can check that
something happened. Push the task branch and run
`python scripts/roach.py integrate T003 --worker agent-alpha --push` first, or pass
--no-work if this task genuinely produced no repository change.
```

Roach still cannot tell whether the sentence is honest. It can tell that
nothing landed, which is the more common mistake.

## 7. Two workers at once

A second session joins. It sees shared state, not its own checkout:

```console
$ python scripts/roach.py next --cap repo-write --cap shell --explain
NONE
T002    area cli is held by T003 (agent-alpha); wait, pick different work, or claim
        with --allow-area-overlap if the two genuinely do not touch the same files
```

Both workers create a task from the same base and land on the same id. The
loser is told exactly what to do:

```console
$ python scripts/roach.py publish
local main is 1 commit(s) behind origin/main, and your pending coordination edits
collide with what another worker published, so it cannot fast-forward.
Run `python scripts/roach.py reconcile` to rebase your pending coordination state
onto current shared state.

$ python scripts/roach.py reconcile
Fast-forwarded main to origin/main (1 commit(s)).
  Renumbered: T003 -> T004  Beta second

The renumbered task(s) above kept their content and took a free id.

Next: python scripts/roach.py publish
```

Both tasks survive. Nothing was hand-edited, and nothing was lost.

When a session dies mid-task, its successor cannot release the claim — it has a
different worker id. Once the claim is provably stale, judged from `origin`
rather than from a possibly stale checkout:

```console
$ python scripts/roach.py adopt T004 --worker agent-beta --publish
Adopted T004 from agent-alpha as agent-beta (stale); branch roach/T004-agent-beta.
```

While the claim is still live, that is refused — the takeover needs
`--force` *and* a recorded reason.

## 8. When something is confusing

```console
$ python scripts/roach.py doctor
Found 1 problem(s):

- uncommitted coordination state (.agent/tasks/T005.json) on a main that is 1
  commit(s) behind origin/main; publishing refuses because the base is stale, and
  pulling can refuse because your edits are in the way
  fix: run `python scripts/roach.py reconcile` to replay your edits onto current shared state
```

`check` answers "is this state well-formed?". `doctor` answers "is it actually
*shared*?". Both halves can be individually fine while the repository is
incoherent, which is the situation a fresh worker is least able to reason
about. Run `doctor` after any interrupted session.

## 9. Completion is earned

```console
$ python scripts/roach.py transition complete --publish
Cannot mark project complete:
- unfinished tasks remain: T003
- accepted requirements lack completed evidence: FR-002
```

Once every task is terminal, every requirement is backed by completed work, and
the required verification has passed on current code:

```console
$ python scripts/roach.py verify quick
$ python scripts/roach.py transition complete --publish
Project is now complete.
```

Completion is a known-good checkpoint, not a freeze. The owner can ask for an
independent review of any finished task, and it never rewrites history:

```console
$ python scripts/roach.py review T002 --publish
Reactivated the completed project and created T006 to review T002. Claim T006; do not reopen T002.

$ python scripts/roach.py correct T006 --title "Fix save corruption found in review" \
    --acceptance "interrupted saves preserve the last valid file" --publish
Created T007 to correct findings from T006.
```

T002 stays `done`. T006 records what the reviewer found. T007 records the fix.
The audit trail only ever grows.

---

## What the owner actually did

1. Described the idea in ordinary language.
2. Answered focused product questions.
3. Confirmed one summary of what was being built.

That is the whole intended human workload. Everything else above was mechanical
or autonomous. If a worker needs credentials, an account, or a judgement only a
person can make, it says so in one line — `NEED YOU:` — and stops. If it wants
a human opinion on how something feels, it says `TEST THIS:` and describes
exactly what to look at.

## What to read next

- `AGENTS.md` — the contract every worker follows.
- `docs/MULTI_AGENT.md` — how two or three sessions stay out of each other's way.
- `docs/PROTOCOL.md` — the normative rules, for a worker with no shell.
- `docs/LIMITATIONS.md` — what Roach deliberately does not do, and why.

---
name: project-continuity
description: Recover, discover, plan, coordinate, execute, verify, checkpoint, and hand off Roach Method v0.5 work without relying on previous chat context.
---

# Project Continuity — Roach Method v0.5

Use this whenever you enter a Roach repository, start or resume work, approach a
context limit, or prepare a handoff.

**`AGENTS.md` is the contract; this is the procedure.** Where a rule needs
justifying, it is justified there, not repeated here. Read `AGENTS.md` first.

The repository is durable memory: product intent in `PRODUCT.md`, technical
strategy in `PLAN.md`, implementation history in Git, coordination semantics in
`roach.py`. Chat memory is not evidence for any of them.

---

## 1. Recover

1. Inspect Git status, remotes, current branch, worktrees, recent commits.
2. Fetch the remote. Never discard local work to sync. If the fetch fails, stop — do not treat stale `origin` as current.
3. Read `.agent/PROJECT.md`, `STATE.json`, `PRODUCT.md`, `VERIFY.json`, relevant task records, `PLAN.md` if present, and only the `DECISIONS.md` entries that bear on your work.
4. Run `python scripts/roach.py check`, and `doctor` after any interrupted session.
5. Choose one stable worker id for the whole session (`export ROACH_WORKER=codex-a31f`). Never derive it from a process id.
6. Inventory the capabilities **this session actually has**. Never infer them from the model, vendor, or interface name.

Read-only commands accept `--json`; parse that, not the prose.

Without a shell, `docs/PROTOCOL.md` is the specification to implement against,
and `schemas/` holds the record shapes. `verify` and `integrate` cannot be
reproduced that way — plan for a shell-capable worker to converge your work.

## 2. Route

`project_status` says whether to work at all; `phase` says what kind of work.
They are independent.

| `project_status` | Action |
| --- | --- |
| `active` | proceed |
| `blocked` / `paused` | claim nothing; this is valid durable state, not an error to work around |
| `complete` | invent no work; see §7 |

| `phase` | Your job |
| --- | --- |
| `uninitialized` / `discovery` | §3 — product discovery only. Do **not** start implementing because the repository looks empty. |
| `planning` | §4 |
| `execution` | §5 |
| `complete` | §7 |

## 3. Discovery

The one phase where asking the owner questions **is** the work.

Claim the discovery task (T000 in a fresh template) with `user-dialogue` +
`repo-write`, then `roach.py transition discovery`.

**If `STATE.json` says `adoption.mode` is `brownfield`**, this project existed
before Roach. The question is not "what should this be?" but "what is this
already, and what do you want next?" Read the code, the README, and the history
first; draft `PRODUCT.md` from what you find; then bring the owner a summary to
correct rather than a questionnaire. Separate what it does from what it was
meant to do, deliberate behaviour from accidents, and kept scope from abandoned
scope. See `docs/ADOPTING.md`.

Then:

- start from the owner's idea, not a generic questionnaire;
- ask one meaningful question at a time, highest-impact ambiguity first;
- offer choices and a recommendation when that reduces owner effort;
- separate committed scope from future possibilities;
- turn vague quality words into observable expectations where they matter;
- **write each decision into `PRODUCT.md` as it is made** — a lost session must cost the conversation, not the conclusions;
- checkpoint and push on the discovery branch.

Required core: Vision, Goals, Non-Goals, Users / Audience, Core Experience,
Requirements, Constraints, Success Criteria, Open Questions. Add
domain-specific sections when they earn their place.

Requirements may be list items, table rows, or headings — one per line, each
with real text. Only `FR-###` / `QR-###` in the active Requirements section are
current scope. Never recycle a retired id.

Do not pick a stack or start implementing. A small experiment needed to answer
a *product* question is bounded research, not a phase change.

When critical ambiguity no longer blocks planning, present **one** concise
product-intent checkpoint. The owner validates *what is being built*, not how.
After confirmation, the discovery-task owner runs:

```bash
python scripts/roach.py accept-product --worker <id> --verification "owner confirmed product intent"
```

Do **not** separately `finish` the discovery task — that split is what used to
deadlock recovery.

For a later ambiguous pivot, `transition discovery` opens a **new** discovery
cycle. Never reclaim a completed discovery task; those records prove what was
accepted at the time.

## 4. Planning

Turn accepted intent into executable work, without asking for routine technical
approval.

Fill `PLAN.md`: Technical Approach, Architecture / Components, Project
Structure, Dependencies / Integrations, Verification Strategy, Risks /
Unknowns, Requirement Coverage.

Also:

- inspect existing code if brownfield;
- populate `VERIFY.json` with a real health command (an argv array travels across operating systems better than a shell string);
- create the initial task graph and link work to active requirements;
- assign only genuinely necessary `requires`; use `prefers` for real advantages;
- use `depends_on` for sequencing and `areas` for collision — an area is **exclusive while a claim is live**, so coarse areas serialise the backlog;
- give tasks a `verify` command wherever proof can execute;
- create design/research/spec artifacts only when complexity justifies them;
- if a capability is missing for a reliable decision, create a bounded research task rather than guessing;
- plan deployment-host configuration explicitly if one will be connected — `docs/DEPLOYMENT.md`.

A brownfield requirement already satisfied may be covered by a done
verification record with concise evidence. Deferred ideas belong in PRODUCT
Future / Possibilities, not as uncovered requirements.

Then: set `Status: READY`, finish the planning task, run `roach.py ready`, fix
every mechanical error, perform the semantic PRODUCT → PLAN → tasks pass
yourself, and `roach.py transition execution`.

A later technical re-plan uses `transition planning`. Never reclaim a completed
planning task.

## 5. Execution loop

```bash
python scripts/roach.py next --cap ... --limit 5          # add --explain when nothing is eligible
python scripts/roach.py claim T012 --cap ... --publish    # from the base branch, before branching
git checkout -b roach/T012-<worker>
# work, committing and pushing coherent slices
git checkout main
python scripts/roach.py integrate T012 --push             # merges, verifies the merged result
python scripts/roach.py finish T012 --verification "..." --publish
```

The helper decides **eligibility**; you decide **suitability** from PRODUCT,
PLAN, acceptance criteria, and the current code.

Claim from the base branch and publish *before* creating the task branch — a
claim committed to a task branch reverts on checkout and never reaches shared
state.

Push often. A pushed checkpoint both preserves work and proves liveness;
`heartbeat` is the explicit alternative when you are working without pushing.

Integrate **before** finishing: `integrate` needs the live claim `finish`
releases. Finishing requires evidence that work exists — pass `--no-work` only
when the task genuinely produced no repository change, and it will be recorded.

Make reasonable reversible decisions yourself. Do not silently rewrite PRODUCT
because implementation would be easier another way; if intent must change, see
§3 for an ambiguous change, or update PLAN and DECISIONS for a technical one.

Create bounded tasks for useful out-of-scope discoveries. Use
`create --publish` when another worker needs to see one immediately.

## 6. When something goes wrong

| Symptom | Command |
| --- | --- |
| state change succeeded, publish failed | `roach.py publish` — do **not** re-run the original command |
| pending edit collides with a published one | `roach.py reconcile` |
| a task's owner is provably gone | `roach.py adopt T012 --worker <id>` (`--force --reason "..."` only when you know the session is dead) |
| work is genuinely stuck on something external | `roach.py block T012 --reason "..."` |
| the work is obsolete | `roach.py cancel T012 --reason "..."` — never mark it done |
| something is wrong and the error is unclear | `roach.py doctor` |
| an older project on a previous protocol | `roach.py upgrade` then `roach.py migrate` |

Never hand-edit task JSON to escape one of these. Never force-push shared
history. Never weaken a lock because it is inconvenient.

## 7. Completion and after

Completion is gated: every task terminal, every active requirement backed by
completed work, PLAN READY, required verification passed on current code.

A `complete` project is a checkpoint, not a freeze. Do not invent new work.
On owner request: `review T012` for an independent check, `correct T0xx` for a
known defect, `transition execution` for unrelated new work. Each opens a new
auditable cycle; none rewrites history. A `done` task is never reopened.

## 8. Handoff and context limits

Before disappearing with unfinished work:

- keep the work on the task branch;
- commit as `wip(T###)` and push;
- put only what a successor cannot cheaply infer into `handoff`;
- release the claim if you will not return.

A useful handoff says what works, what does not, the last check and its result,
the likely next action, and the files that matter. Nothing else.

## 9. Talking to the owner

Outside discovery, ask first: *can I choose a reasonable reversible default and
continue?* Usually yes.

`NEED YOU:` for credentials, access, an irreversible external action, a missing
capability no available worker has, or a genuinely consequential product
ambiguity.

`TEST THIS:` for a subjective judgement worth a human — say where to go, what
to do, and what to notice.

Never send progress essays. Never ask "should I continue?".

## 10. Memory discipline

Git holds implementation history. `.agent/` holds intent, strategy,
verification, and coordination. PRODUCT may grow substantial when the product
is substantial — but never into transcripts, progress diaries, or facts already
recoverable from the code.

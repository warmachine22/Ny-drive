# Roach Task Records

Roach Method v0.5 stores one JSON file per task. Tasks are not limited to coding: discovery, planning, research, design, implementation, verification, and product-feedback work can all be represented.

Humans normally do not edit task JSON. When a shell is available, agents should prefer `python scripts/roach.py ...` for deterministic coordination. If an environment has repository/GitHub write tools but no shell, it may perform the equivalent repository edits only when it can preserve the same safety invariants: fresh shared state, stable worker identity, visible ownership before work, no force-push, and no unrelated changes hidden inside coordination commits.

## Shape

```json
{
  "id": "T012",
  "kind": "implementation",
  "title": "Add settings screen",
  "status": "planned",
  "priority": "normal",
  "depends_on": [],
  "areas": ["settings-ui"],
  "requirements": ["FR-014"],
  "requires": ["repo-write", "shell"],
  "prefers": ["vision"],
  "acceptance": ["settings can be opened and saved"],
  "verify": null,
  "verification": null,
  "claim": null,
  "handoff": null,
  "review_of": null,
  "correction_of": null,
  "integration": null,
  "evidence": null,
  "completed_at": null,
  "commit": null
}
```

Authored fields are everything down to `verify`. The four after `correction_of` are written by the coordinator and should not be edited by hand:

- `integration` — `{branch, merge_commit, level, verified_at}`, stamped by `integrate`. This is the durable link between a completed task and the work it produced.
- `evidence` — `{work, work_waived, task_check}`, stamped by `finish`: how the repository knows work happened, whether that was waived, and the result of the task's own check.
- `completed_at` / `commit` — when the task was finished, and where the base branch stood at that moment.

A `claim` additionally records `base_commit`, so finishing can tell "nothing happened" apart from "work landed directly on the base".

Statuses: `planned`, `claimed`, `active`, `blocked`, `verify`, `done`, `cancelled`.

Priorities: `urgent`, `high`, `normal`, `low`.

Common kinds: `discovery`, `planning`, `research`, `design`, `implementation`, `verification`, `product-feedback`. Custom lowercase kinds are allowed when useful.

`done` means the work was completed and must contain verification evidence. `cancelled` is also terminal, but means the work was intentionally retired/superseded and its verification field records why. A non-cancelled task must not depend on a cancelled task; revise the dependency graph instead.

Completed tasks are immutable history, not permanently trusted work. Independent review and later correction use new linked tasks:

- `review_of: "T012"` identifies a verification task that independently reviews completed T012;
- `correction_of: "T013"` identifies work that corrects findings recorded by completed T013 (or directly corrects a completed implementation task).

Use the coordinator rather than editing these links manually:

```bash
python scripts/roach.py review T012 --publish
python scripts/roach.py correct T013 \
  --title "Fix save corruption found in review" \
  --acceptance "interrupted saves preserve the last valid file" \
  --publish
```

`review` inherits the completed task's active requirement links, areas, and useful preferred capabilities. `correct` does the same and requires repository write access. If the project was complete, either command atomically returns it to active execution while creating the follow-up task. The original task remains done so the audit trail stays truthful.

## Executable task evidence

`verify` is an optional shell command that proves *this* task specifically, the way `.agent/VERIFY.json` proves project health:

```bash
python scripts/roach.py create --title "Add settings screen" \
  --requirement FR-014 --requires repo-write \
  --acceptance "settings can be opened and saved" \
  --verify "npm test -- settings"
```

`finish` runs it and refuses to mark the task done if it fails. Prefer this over describing a check in `--verification` prose. It executes with the privileges of whoever runs Roach — the same trust boundary as `VERIFY.json`, described in `docs/SECURITY.md`.

`finish` also requires evidence that work happened: commits on the claimed branch, a merge recorded by `integrate`, or product files changed on the base since the claim. Code-producing kinds — `implementation`, `correction`, `fix`, `refactor`, `spike` — are refused without it. Work that legitimately produces no repository change passes `--no-work`, which records the waiver in `evidence`.

Capability-dependent checks that cannot be scripted — visual inspection, computer-use, subjective judgement — still belong in `--verification` text, honestly labelled as what they are.

## Requirement links

`requirements` contains stable IDs from the **active Requirements section** of `.agent/PRODUCT.md`, normally `FR-###` or `QR-###`.

Declare each on its own line. A list item, a table row, or a heading all work:

```markdown
- **FR-001**: The user MUST be able to save a note.

| FR-002 | The user MUST be able to reopen a saved note. |

#### QR-001 — Saving completes within one second.
```

A line shaped like a declaration that cannot be read as one is reported by `check` rather than silently ignored.

Current work must reference current requirement IDs. Completed/cancelled historical tasks may retain IDs that were later retired so Git/task history stays truthful. Never recycle a retired ID for a different meaning.

Every active accepted requirement must have credible non-planning task coverage before execution. If a brownfield project already satisfies a requirement, create/retain a done verification or implementation record with concise evidence rather than inventing unfinished implementation work. Speculative/deferred ideas that are not current scope belong in PRODUCT Future/Possibilities, not as uncovered active requirements.

## Capabilities

`requires` is a hard gate: a worker must inventory those capabilities in its **current session** before claiming the task.

`prefers` means the task is still valid without those capabilities, but workers that have them are generally better matches.

Standard capability names are:

- `user-dialogue`
- `repo-read`
- `repo-write`
- `shell`
- `git`
- `network`
- `web-research`
- `browser-interaction`
- `computer-use`
- `vision`
- `image-generation`

Project-specific tokens such as `android-emulator`, `unity-editor`, or `google-calendar` are allowed. Describe abilities, not model/vendor names.

## Stable worker identity

Before the first ownership-changing command, establish one worker ID for the session, for example `codex-a31f`. Pass it with `--worker` or set `ROACH_WORKER` in the shell. Roach deliberately refuses to invent a PID-based identity because separate CLI invocations must still be recognized as the same worker.

## Capability-aware selection

After recovery and capability inventory:

```bash
python scripts/roach.py next \
  --cap repo-read \
  --cap repo-write \
  --cap shell \
  --limit 5
```

If nothing is eligible, use `--explain` to see the mechanical reason for remaining tasks.

The helper filters project status/phase, dependencies, live claims, area overlap, and hard capability requirements. It ranks by priority, preferred-capability matches, and task number. The agent still applies judgment before claiming.

Claim with the same inventory and stable worker ID:

```bash
python scripts/roach.py claim T012 \
  --worker codex-a31f \
  --cap repo-write \
  --cap shell \
  --publish
```

## Publishing shared coordination

`--publish` is available on coordination edits such as create/review/correct/claim/release/finish/block/unblock/cancel. It is intentionally conservative:

- it runs only from the configured base branch (`main` by default; override with `ROACH_BASE_BRANCH`);
- it refreshes `origin` and refuses stale remote state;
- the base must carry no local commits `origin` has not seen;
- unrelated dirty files are refused;
- only pending coordination state is committed;
- normal push races fail rather than force-push.

This prevents a claim publication from accidentally carrying unrelated local commits or stale state into shared history.

A base that is only *behind* fast-forwards rather than refusing. When a pending edit collides with one another worker published, use `roach.py reconcile`.

## Bootstrap discovery

A new template contains reserved `T000 — Define product with owner`. Its job is product discovery, not implementation.

Once the owner confirms the product-intent checkpoint, the **T000 owner** runs:

```bash
python scripts/roach.py accept-product \
  --worker codex-a31f \
  --verification "owner confirmed product intent"
```

This single transition validates PRODUCT/PROJECT, marks the active discovery task done, records product acceptance, initializes `PLAN.md`, moves the project to planning, and creates the planning task. Do not separately `finish T000`; atomic acceptance avoids a recovery deadlock between those operations.

Later major pivots use a new discovery task rather than reopening T000.

The same append-only rule applies to planning: use `roach.py transition planning --publish` to create a new planning cycle rather than reclaiming a completed planning task.

## Blocking, cancelling, and project pause

Use explicit states instead of editing JSON ad hoc:

```bash
python scripts/roach.py block T012 --worker codex-a31f --reason "waiting for owner OAuth access"
python scripts/roach.py unblock T012
python scripts/roach.py cancel T012 --reason "superseded by FR-020 redesign"
python scripts/roach.py project-status paused --reason "owner paused the project"
python scripts/roach.py project-status active
```

Blocking a claimed task releases ownership and stores a durable blocker in `handoff`. Cancelling is terminal and stores the reason in `verification`.

A project whose `project_status` is `blocked` or `paused` offers no claimable work until reactivated.

## Claims and liveness

A live claim contains `worker`, `claimed_at`, `lease_expires_at`, and `branch`. `claimed`/`active`/`verify` tasks must have a claim; planned/blocked/done/cancelled tasks must not.

The default lease is two hours. Pushed activity on the claimed remote task branch is the normal long-running heartbeat; a task is stale only when both the lease and recent remote branch activity are stale. `ROACH_STALE_MINUTES` changes the recent-activity threshold (minimum 15 minutes).

Do not reclaim a stale ownership record with `claim`; use `adopt` so the predecessor and takeover remain visible. If the lease still appears live but the owner knows the prior session is gone, use `adopt --force --reason "..."` deliberately.

## Dependencies and areas

`depends_on` lists prerequisite task IDs. Dependencies must exist, cannot self-reference, cannot point at cancelled prerequisites for live work, and the graph must be acyclic.

`areas` are coarse subsystem labels, and they are **exclusive while a claim is live**: a task is not eligible while another live claim shares one of its areas. Choose them at the granularity at which two workers would actually conflict. Tagging a whole backlog with two broad areas serialises it to one worker. `claim --allow-area-overlap` is the deliberate exception when two tasks share a label but not a file.

## Handoffs

`handoff` should normally be null. Use it only for unfinished context another worker cannot cheaply infer from code, tests, or Git. Blocked tasks use it for the blocker reason. Done/cancelled tasks must not retain stale handoff text.

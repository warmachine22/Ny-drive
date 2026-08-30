# Migrating Roach v0.3 projects to v0.4

Roach v0.5 changes lifecycle and task metadata enough that migration should be deliberate. Existing repositories created from an older GitHub template do not inherit these changes automatically.

## What changed

- authoritative product intent moves into `.agent/PRODUCT.md`;
- `STATE.json` adds separate `project_status`, lifecycle `phase`, product acceptance, blocker state, and richer verification evidence;
- tasks add `kind`, `requirements`, `requires`, `prefers`, plus terminal `cancelled` semantics;
- selection/claiming becomes capability-aware and project-status-aware;
- worker identity must be stable across ownership commands;
- product acceptance atomically closes the active discovery task and opens planning;
- `PLAN.md` has required core sections and a READY state before execution;
- planning/execution validates requirement coverage and dependency cycles;
- completion is mechanically gated;
- coordination publication refuses stale remote state, unrelated dirty paths, or unrelated unpushed base commits.

## Recommended migration

For an existing v0.3 project:

1. Keep existing code and Git history.
2. Create `.agent/PRODUCT.md` from current owner intent, distinguishing intended product from implemented reality.
3. Preserve the required PRODUCT core sections: Vision, Goals, Non-Goals, Users/Audience, Core Experience, Requirements, Constraints, Success Criteria, Open Questions.
4. Assign stable `FR-###`/`QR-###` IDs only to **current active requirements**. Do not reconstruct or invent historical requirements merely for ceremony.
5. Create/update `.agent/PLAN.md` with the required v0.4 planning sections and set `Status: READY` only when the current strategy/backlog is coherent.
6. Change `STATE.json` to protocol `0.4`, choose an appropriate `project_status` and `phase`, and mark product intent accepted only after reviewing PRODUCT against actual owner intent.
7. Add `kind`, `requirements`, `requires`, and `prefers` to current tasks. Keep acceptance criteria meaningful.
8. Add `T000` as a completed discovery task if the product definition is already established, with concise verification such as `migrated existing accepted product intent`.
9. For requirements already satisfied by the brownfield codebase, use done implementation/verification task evidence rather than creating fake unfinished implementation work.
10. For work no longer desired, use terminal `cancelled` semantics with a reason instead of marking it done. Revise any non-cancelled task that depends on a cancelled task.
11. If old completed tasks reference requirements no longer active, they may keep those historical IDs; do not reuse those IDs for new meanings.
12. Configure `.agent/VERIFY.json` with the required practical project-health command.
13. Run `python scripts/roach.py check` and repair structural/task-graph errors.
14. If entering execution, run `python scripts/roach.py ready`, perform the semantic PRODUCT → PLAN → task consistency pass, then `transition execution`.
15. Run the configured required verification before marking an already-finished migrated project complete.

## Worker identity

v0.4 no longer treats a generated PID as a safe default worker identity. For command-line workers either:

```bash
export ROACH_WORKER=codex-a31f
```

or pass `--worker codex-a31f` consistently to ownership-changing commands.

## Existing blocked/paused projects

Use STATE deliberately:

- `project_status: blocked` with a non-empty `blocked` reason for a project-wide blocker;
- `project_status: paused` with a reason for an intentional suspension;
- `project_status: active` with `blocked: null` when work may proceed.

Do not encode a project-wide pause by leaving arbitrary task claims stale.

## Base branch and remote safety

Roach assumes `main` as the shared base unless `ROACH_BASE_BRANCH` is set. If the project intentionally uses another shared base, configure it consistently for workers.

When an origin exists, Roach refuses coordination decisions if the remote cannot refresh. `--publish` also refuses a base branch carrying local commits `origin` has not seen, so tiny coordination operations cannot accidentally publish unrelated local commits. A base that is merely behind fast-forwards instead.

## Do not invent history

Migration should optimize for accurate **current** intent and recoverable continuity, not reconstructed ceremony. Git already contains the implementation history. Use PRODUCT/PLAN/tasks to make the current state understandable and executable from here forward.

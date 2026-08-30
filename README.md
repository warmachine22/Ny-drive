# Roach Method

> ### 👉 Just want to use it? → **[START-HERE.md](START-HERE.md)**
>
> That file is nothing but the exact text to paste into an AI agent — one block
> for adding this to a project you already have, one for starting a new project.
> Everything below is background.

**Repository-native product memory, planning, continuity, and coordination for disposable AI workers.**

Roach Method v0.5 makes the Git repository—not an individual chat—the durable source of truth for both **what the owner wants** and **how work should continue**. A fresh agent can discover a new product with the owner, another can plan it, and later workers with different toolsets can select suitable tasks and continue without reconstructing previous conversations.

Roach is designed for personal games and applications with roughly 1–3 simultaneous agent sessions. It deliberately avoids servers, dashboards, databases, permanent orchestrators, and other infrastructure that would be harder to maintain than the projects themselves.

> Preserve intent and progress, not conversations.

## Quick start for project owners

There are two ways in, and you do not need to learn any commands for either.

### A new project

1. On GitHub, choose **Use this template** → **Create a new repository**. This gives the new project its own history and shared `origin` for coordination.
2. Open that new repository in your coding-agent environment.
3. Describe the product you want in ordinary language. A useful first prompt is: `Use the Roach Method in this repository. Help me define and build [your idea].`
4. Answer the agent's focused product questions, then confirm its one product-intent summary. After that checkpoint, agents plan and carry out routine technical work autonomously.

### A project that already exists

Open it with your agent and give it this:

> Adopt the Roach Method in this repository.
>
> 1. Clone `https://github.com/warmachine22/roachmethod3` into a temporary directory.
> 2. Run `python <clone>/scripts/install.py --into . --check` and show me the plan.
> 3. If it looks right, run it without `--check`, then run `python scripts/roach.py check`.
> 4. Read `AGENTS.md` and follow it from then on.
> 5. Claim T000 and work out with me what this project is and what I want next.

The installer adds the method beside your project rather than on top of it. Your README, licence, changelog, build config, existing CI, and every line of code are never written. If you already have an `AGENTS.md`, your instructions are kept and the Roach contract is added below them inside markers, so later upgrades replace only the managed region.

Step 5 is the part that matters. Instead of asking what you want to build, the agent reads what you already built, drafts a product definition from it, and brings you a summary to correct. `docs/ADOPTING.md` has the full detail, including how to cover existing code without inventing fake work, and how to back the whole thing out.

### Either way

The `roach.py` commands below are primarily for agents and advanced troubleshooting. As the owner, your normal jobs are explaining what you want, supplying access only when needed, and testing experiences that require human judgment.

## Core model

Roach v0.5 combines four repository-native concerns:

1. **Product discovery before implementation.** A new template starts `uninitialized` with reserved `T000 — Define product with owner` and a draft `.agent/PRODUCT.md`.
2. **Autonomous planning after one product checkpoint.** The owner confirms what is being built; the planning worker decides how to build it.
3. **Capability-aware work selection.** Workers inventory actual current-session abilities. Tasks declare hard `requires` and soft `prefers`.
4. **Mechanical coordination safety.** Claims, dependencies, liveness, task state, product/plan readiness, and completion have deterministic checks.

## Lifecycle and project status

Lifecycle phase and project status are separate:

```text
project_status: active | blocked | paused | complete
phase:          uninitialized | discovery | planning | execution | complete
```

A project can therefore be paused while planning or blocked during execution without losing its lifecycle context.

Normal new-project flow:

```text
NEW TEMPLATE
phase: uninitialized
T000 available
        ↓
capability inventory + stable worker ID
        ↓
DISCOVERY
owner + agent refine PRODUCT.md
        ↓
PRODUCT INTENT CHECKPOINT
        ↓
accept-product
  - validates PRODUCT/PROJECT
  - completes discovery task
  - records accepted intent
  - initializes PLAN.md
  - creates planning task
        ↓
PLANNING
PLAN.md + VERIFY.json + task graph
        ↓
roach.py ready + semantic consistency pass
        ↓
EXECUTION
capability-aware workers claim/verify/integrate
        ↓
all work done/cancelled + required verification passed
        ↓
COMPLETE
```

Large later product pivots may deliberately return to discovery, but they use a **new discovery task** rather than reopening T000.

## What the repository remembers

- `.agent/PROJECT.md` — one-minute orientation/index.
- `.agent/PRODUCT.md` — authoritative living owner intent.
- `.agent/PLAN.md` — current technical strategy once product intent is accepted.
- `.agent/STATE.json` — protocol version, project status, lifecycle phase, product acceptance, blockers, and latest verification evidence.
- `.agent/VERIFY.json` — executable quick/full/smoke project-health commands.
- `.agent/tasks/` — compact work records with dependencies, ownership, requirement links, and capability metadata.
- `.agent/DECISIONS.md` — durable non-obvious rationale not cheaply recoverable elsewhere.
- Git — detailed implementation history and recoverable WIP.

Roach does **not** store chat transcripts or long progress diaries.

## Starting a new project

Create a repository from this template and open it in an environment that can at least persist repository changes and converse with the owner.

Two things carry over from the template and should be cleaned up in the new repository:

- **`README.md` and `docs/` describe the Roach Method itself**, not your product. Replace or delete them. Keep `docs/DEPLOYMENT.md` if you will connect a deployment host, and `docs/LIMITATIONS.md` if you want the coordinator's known limits to travel with the project.
- **Give the new repository its own remote before the first session.** Coordination between workers happens through `origin`; without one, `--publish` has nowhere to go and a second session cannot see the first.

`AGENTS.md`, `CLAUDE.md`, `.agent/`, `.agents/`, `.claude/`, `scripts/`, and `.gitignore` are the template proper and should stay.

You can start vague:

> I want to make a management game about running a space mining company. Help me figure out what it should be.

or more developed:

> Build a local-first personal finance app for couples with shared budgets and private notes.

A fresh worker should recover state, establish a stable worker ID, inventory actual capabilities, and select T000 if it has `user-dialogue` + `repo-write`.

During T000, focused product dialogue is expected. The worker updates PRODUCT incrementally so discovery survives context loss.

If the project will be deployed to a push-triggered host such as Vercel, read `docs/DEPLOYMENT.md` before connecting it. Roach pushes far more often than a human workflow does, and an unconfigured host will exhaust free-tier deployment allowances.

## The product Bible

`PRODUCT.md` is the authoritative statement of current owner intent. Its required core is:

- Vision
- Goals
- Non-Goals
- Users / Audience
- Core Experience
- Requirements
- Constraints
- Success Criteria
- Open Questions

Project-specific sections are encouraged when they add value.

Active requirements live only in PRODUCT's `## Requirements` section:

- `FR-###` — functional requirement
- `QR-###` — quality/non-functional requirement

IDs are stable. If intent changes and a requirement is retired, do not recycle its ID for a different meaning. Historical done/cancelled tasks may retain retired IDs; current work must reference current active requirements.

Future possibilities that are not current scope stay in the Future/Possibilities section rather than creating uncovered active requirements.

## Product acceptance is atomic

When product intent is sufficiently clear, the discovery worker presents one concise checkpoint. After owner confirmation:

```bash
python scripts/roach.py accept-product \
  --worker codex-a31f \
  --verification "owner confirmed product intent"
```

This one command validates the required product structure, confirms the caller owns the active discovery task, marks that discovery task done, records accepted intent, initializes a DRAFT `PLAN.md`, moves to planning, and creates the planning task.

There is deliberately **no separate `finish T000` step** after acceptance. Keeping acceptance and discovery completion together removes a crash/recovery deadlock between those state changes.

## Planning

Planning decides **how to build the accepted product** without routine technical approval.

`PLAN.md` must contain and fill these recognizable sections:

- Technical Approach
- Architecture / Components
- Project Structure
- Dependencies / Integrations
- Verification Strategy
- Risks / Unknowns
- Requirement Coverage

The planning worker also configures `.agent/VERIFY.json`, creates the initial task graph, assigns capability requirements/preferences, and creates optional design/research/spec artifacts only when project complexity justifies them.

If planning needs research or tooling the current environment lacks, it creates a bounded capability-tagged research/design/verification task rather than guessing.

When planning is coherent, set `PLAN.md` to `Status: READY`, finish the planning task, then run:

```bash
python scripts/roach.py ready
```

Mechanical readiness checks include:

- accepted coherent PRODUCT;
- READY PLAN with required sections and no untouched placeholders;
- configured required verification command;
- planning task terminal;
- active requirement/task coverage;
- valid dependency graph with no cycles;
- no live work depending on cancelled prerequisites.

Then perform the semantic consistency pass across PRODUCT → PLAN → tasks and enter execution:

```bash
python scripts/roach.py transition execution
```

## Stable worker identity

Ownership-changing commands require a stable worker identity. Use one ID for the session, such as `codex-a31f`:

```bash
export ROACH_WORKER=codex-a31f
```

or pass `--worker codex-a31f` each time.

Roach no longer invents a PID-based fallback, because separate command invocations would appear to be different workers and make heartbeat/release/finish unreliable.

## Capability-aware workers

Standard capability vocabulary:

```text
user-dialogue
repo-read
repo-write
shell
git
network
web-research
browser-interaction
computer-use
vision
image-generation
```

Projects may use custom lowercase tokens such as `android-emulator`, `unity-editor`, or `google-calendar`.

Capabilities describe **abilities**, not product/model identities. The same model can have different abilities in a CLI, browser chat, desktop app, IDE, or agent harness.

A task can declare:

```json
{
  "requires": ["repo-write", "shell"],
  "prefers": ["web-research", "vision"]
}
```

`requires` is a hard gate. `prefers` improves ranking but does not exclude otherwise valid workers.

Select candidates:

```bash
python scripts/roach.py next \
  --cap repo-read \
  --cap repo-write \
  --cap shell \
  --limit 5
```

If none are eligible:

```bash
python scripts/roach.py next --cap repo-write --explain
```

Roach explains mechanical blockers such as missing capabilities, dependencies, phase, project pause, or active claims.

## Workers without a shell

`roach.py` is the **reference coordinator**, not a requirement that every agent interface expose a terminal.

`docs/PROTOCOL.md` is the normative specification written for exactly that worker: the liveness rule, the eligibility rule, and the claim, finish, publish, and reconcile procedures, stated precisely enough to implement against a repository API. `schemas/` carries the machine-readable shapes, and every read-only command takes `--json`.

A worker with repository/GitHub API read/write tools but no shell may perform equivalent coordination only if it can preserve the same invariants:

- refresh/read current shared base state;
- use a stable worker identity;
- apply the same capability/dependency/phase/status rules;
- publish visible ownership before substantial work;
- keep coordination edits isolated from unrelated changes;
- let normal race/non-fast-forward protection win;
- never force-push shared history;
- record durable verification evidence.

If an environment cannot preserve those invariants, it should not claim shared work. This keeps capability-awareness meaningful across CLI, IDE, desktop, web, and connector-based agents.

## Task states

Example task:

```json
{
  "id": "T012",
  "kind": "implementation",
  "title": "Add save-game browser",
  "status": "planned",
  "priority": "high",
  "depends_on": [],
  "areas": ["save-system"],
  "requirements": ["FR-021", "QR-004"],
  "requires": ["repo-write", "shell"],
  "prefers": ["vision"],
  "acceptance": ["saved games can be listed, opened, and deleted"],
  "verify": "npm test -- save-browser",
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

`verify` is an optional executable check for this task specifically; `finish` runs it and refuses when it fails. The last four fields are written by the coordinator: `integration` records the merge `integrate` produced, and `evidence` records how the repository knows work happened.

Statuses:

- `planned` — eligible when phase/dependencies/capabilities allow;
- `claimed` / `active` / `verify` — owned work, must contain a claim;
- `blocked` — cannot proceed; stores a durable blocker and has no claim;
- `done` — completed with verification evidence;
- `cancelled` — intentionally retired/superseded with a recorded reason.

A non-cancelled task cannot depend on a cancelled prerequisite. Dependency cycles are invalid.

Completed tasks stay immutable so later workers cannot rewrite history. They can still be independently reviewed and corrected through new linked tasks.

## Review and correction after completion

To have another agent independently check completed T012:

```bash
python scripts/roach.py review T012 --publish
```

Roach creates a separate verification task with T012's current requirements and work area. T012 remains done. The reviewer claims the new task, checks the actual work and original acceptance criteria, and records concrete evidence.

If the review confirms a defect, finish the review with those findings and create linked corrective work:

```bash
python scripts/roach.py correct T013 \
  --title "Fix save corruption found in review" \
  --acceptance "interrupted saves preserve the last valid file" \
  --publish
```

Here T013 is the completed review task. A known defect can instead be corrected directly from its completed implementation task. If the project was already marked complete, either command automatically returns it to active execution while creating the follow-up task; there is no manual unlock step.

## Blocking and cancellation

```bash
python scripts/roach.py block T012 \
  --worker codex-a31f \
  --reason "waiting for owner OAuth access"

python scripts/roach.py unblock T012

python scripts/roach.py cancel T012 \
  --reason "superseded by redesigned requirement"
```

Blocking releases ownership and stores the reason. Cancelling is terminal and keeps history truthful without pretending obsolete work was completed.

Project-wide suspension is separate:

```bash
python scripts/roach.py project-status paused --reason "owner paused project"
python scripts/roach.py project-status blocked --reason "required account unavailable"
python scripts/roach.py project-status active
```

Paused/blocked projects offer no new claimable work.

## Claims, publication, and race safety

Claim with the same capability inventory used for selection:

```bash
python scripts/roach.py claim T012 \
  --worker codex-a31f \
  --cap repo-write \
  --cap shell \
  --publish
```

Claim from the base branch, publish, and only then create the task branch. Task records are tracked files, so a claim made on a task branch is committed to that branch and reverts on checkout — shared state never sees it and the worker cannot finish its own work. Roach refuses that rather than letting it happen silently.

`--publish` is intentionally strict:

- only the configured base branch may publish (`main` by default; `ROACH_BASE_BRANCH` can override);
- `origin` must refresh successfully;
- the base must carry no local commits `origin` has not seen;
- any working-tree change outside `.agent/` is refused;
- push races fail normally; force-push is never used.

This prevents a tiny claim operation from accidentally publishing unrelated local commits or acting on stale shared state.

A base that is merely *behind* is fast-forwarded rather than refused. With several workers publishing coordination commits, being behind is the ordinary state; treating it as an error would make a manual `git pull` a precondition of nearly every command.

When a pending edit collides with one another worker already published — the classic case being two workers creating a task and computing the same free id — the fast-forward cannot happen. That is what `reconcile` is for:

```bash
python scripts/roach.py reconcile
```

It sets pending coordination edits aside, fast-forwards, and replays them: the task that lost the id race is renumbered and keeps its content, and anything that would overwrite shared state is preserved under `.roach-reconcile/` and reported rather than dropped.

Publication covers all pending `.agent/` state rather than one named file, because coordination state is one unit: a command that requires an edit must be able to publish the edit it required. Product code stays out.

The same publication option is available for create/release/finish/block/unblock/cancel/adopt coordination edits.

A state change is written before it is published, so a failed publish leaves the change in the working tree. Re-running the original command will not work — it refuses a precondition it has itself satisfied. Fix the cause and run `python scripts/roach.py publish`; `doctor` points at the same command.

## Liveness

A new claim receives an initial lease. After implementation starts, **pushed task-branch commits** are the normal heartbeat.

A claim is live while either:

- its lease is valid; or
- the claimed remote task branch has recent pushed activity.

Default recent threshold: two hours. `ROACH_STALE_MINUTES` adjusts it, with a 15-minute minimum. Invalid values are rejected rather than silently falling back.

A pushed checkpoint therefore both preserves work and proves liveness.

## Verification and known-good base

Planning configures `.agent/VERIFY.json`:

- `quick` — cheap frequent health check;
- `full` — broader integration-quality tests/lint/build;
- `smoke` — automatable user-flow/end-to-end check.

Run:

```bash
python scripts/roach.py verify quick
```

STATE records pass/fail, level, command, timestamp, and current commit when available.

A task can also carry its own `verify` command, which `finish` runs and requires to pass. That is where task-level proof belongs.

Finishing a code-producing task additionally requires evidence that work happened — commits on the claimed branch, a recorded merge, or product files changed on the base since the claim. Roach cannot judge whether a `--verification` sentence is true, but it can tell that nothing landed at all, which is the more common failure. Work that legitimately produces no repository change passes `--no-work`, recording the waiver on the task.

Capability-dependent checks such as visual/UI inspection belong in task verification evidence rather than pretending they are shell checks.

The target meaning of the shared base remains:

> **latest known-good integrated product**

not merely the newest code someone pushed.

## Completion is gated

`transition complete` cannot simply hide unfinished work. It requires:

- accepted coherent PRODUCT;
- READY coherent PLAN;
- every task terminal (`done` or deliberately `cancelled`);
- every current accepted requirement backed by completed non-planning task evidence;
- required project verification passed at the configured level.

Then:

```bash
python scripts/roach.py transition complete
```

Completion is a known-good checkpoint, not a permanent freeze. An explicit owner request may reopen execution, review completed work, revise product intent, or re-plan without modifying prior task history.

## Later pivots and replanning

For a major ambiguous product pivot, `transition discovery` creates/reuses a **new** discovery task and normally refuses the transition while non-discovery claims are still live. After the new product checkpoint, `accept-product` creates a planning task tied to that discovery cycle.

For a substantial technical re-plan that preserves product intent, `transition planning` returns PLAN to DRAFT and creates/ensures a planning task without reopening product discovery.

Do not reclaim the original discovery or planning task. Their completed state records what was accepted previously; the new cycle makes PRODUCT or PLAN editable and preserves the revision history.

## Mechanical helper

Useful commands:

```bash
python scripts/roach.py capabilities
python scripts/roach.py status --cap repo-read --cap repo-write
python scripts/roach.py next --cap repo-write --cap shell --limit 5
python scripts/roach.py next --cap repo-write --explain
python scripts/roach.py create --title "Add save browser" --requirement FR-021 --requires repo-write --acceptance "saved games can be listed and opened" --publish
python scripts/roach.py review T012 --publish
python scripts/roach.py correct T013 --title "Fix review finding" --acceptance "the defect no longer reproduces" --publish
python scripts/roach.py claim T012 --worker codex-a31f --cap repo-write --cap shell --publish
python scripts/roach.py heartbeat T012 --worker codex-a31f
python scripts/roach.py release T012 --worker codex-a31f
python scripts/roach.py block T012 --worker codex-a31f --reason "..."
python scripts/roach.py unblock T012
python scripts/roach.py cancel T012 --reason "..."
python scripts/roach.py finish T012 --worker codex-a31f --verification "full tests passed"
python scripts/roach.py accept-product --worker codex-a31f
python scripts/roach.py ready
python scripts/roach.py transition discovery
python scripts/roach.py transition planning
python scripts/roach.py transition execution
python scripts/roach.py transition complete
python scripts/roach.py project-status paused --reason "..."
python scripts/roach.py verify quick
python scripts/roach.py check
```

Converging finished work, recovering, and diagnosing:

```bash
python scripts/roach.py integrate T012 --worker codex-a31f --push   # merge + verify, before finish
python scripts/roach.py publish                                     # retry a publish that failed
python scripts/roach.py reconcile                                   # replay pending edits onto shared state
python scripts/roach.py adopt T012 --worker codex-b42a              # take over a stale claim
python scripts/roach.py doctor                                      # diagnose a confused repository
python scripts/roach.py migrate                                     # upgrade an older project's state
python scripts/roach.py upgrade                                     # pull coordinator fixes from the template
```

`integrate` runs **before** `finish`: it needs the live claim that `finish` releases.

`check` answers whether coordination state is well-formed. `doctor` answers whether it is shared — both halves can be valid while the repository is incoherent.

Humans normally do not need to run these commands.

## Human interaction policy

During discovery, product dialogue is expected.

After product intent is accepted, workers make routine reversible technical choices themselves and should not repeatedly ask which library to use, whether to refactor, whether to continue, or whether a routine technical plan is approved.

Legitimate interruption examples:

> **NEED YOU:** Sign in to the service and approve OAuth access.

> **NEED YOU:** Remaining eligible work requires computer-use and vision; open this repository in an environment with those capabilities and say `Continue.`

Useful subjective feedback:

> **TEST THIS:** Open the settings screen, resize the window, and tell me whether the layout feels crowded.

## Agent portability

- `AGENTS.md` — universal controlling contract.
- `.agents/skills/project-continuity/SKILL.md` — canonical detailed procedure.
- `CLAUDE.md` and `.claude/skills/...` — Claude adapter pointing back to the same rules.
- other capable agents follow AGENTS, the canonical skill, repository state, and the coordinator semantics.

The method describes capabilities, not model/vendor identities.

## Seeing it work

`docs/EXAMPLE.md` walks one small project from empty template to `complete`, with real command output at every step — including the two-worker race, a stale claim being adopted, and completion being refused until it was earned. It is the shortest way to understand what using Roach feels like.

## Keeping a project current

A project forks the coordinator at whatever revision it was created from, so fixes do not arrive on their own. Record the template once:

```bash
git remote add template https://github.com/<owner>/<template>.git
```

Then, whenever you want the newest coordinator:

```bash
python scripts/roach.py upgrade --check   # see what would change
python scripts/roach.py upgrade
python scripts/roach.py migrate
python scripts/roach.py check
```

`upgrade` replaces template-owned files — the coordinator, `AGENTS.md`, the skills, `schemas/`, `docs/` — and never touches `PRODUCT.md`, `PLAN.md`, `PROJECT.md`, `STATE.json`, `VERIFY.json`, `DECISIONS.md`, task records, or your application code.

`docs/CHANGELOG.md` records what changed in each protocol version.

## Migration from v0.3

Existing repositories do not automatically inherit template changes. See `docs/MIGRATING_V0_3.md`.

## Design boundary

Roach is intentionally not a fleet scheduler. GitHub plus a few durable repository files, capability-tagged tasks, and deterministic coordination should be enough for the intended personal-project workflow.

If a project eventually requires dozens of simultaneous workers, centralized scheduling may make sense. That remains outside Roach's target.

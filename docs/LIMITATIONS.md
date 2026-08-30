# Known limitations and deliberate non-goals

Things a worker would otherwise rediscover by hitting them. Each entry says what
the limit is, what it costs, and whether it is worth fixing.

Read this before proposing a change to `scripts/roach.py`: several of the
entries below are decisions, not oversights.

## Template self-tests must not read mutable project state

The coordinator tests exercise the lifecycle starting from a pristine template:
T000 is planned, product intent is draft, PLAN does not exist yet, and VERIFY is
unconfigured. Once a real project uses Roach, those files legitimately change.

A field test in Pictag exposed the failure mode: the test suites copied
`.agent/STATE.json`, PRODUCT, PROJECT, VERIFY, and T000 from the live project and
then asserted fresh-template behaviour. As soon as discovery/planning completed,
tests failed with messages such as `T000 is not claimable: done` even though the
project was healthy.

The template now keeps immutable pristine fixtures under
`.agent/tests/fixtures/template/` and `run_template_tests.py` builds a throwaway
sandbox from them before running every coordinator suite. Keep those fixtures in
sync with intentional template-schema changes. Do not "simplify" the tests back
to copying mutable live project state.

## Fresh-checkout CI preparation is project-specific

`.agent/VERIFY.json` can optionally define `setup`, a shell command the Roach
continuity workflow runs before the required project-health command in a fresh
CI checkout. This exists because a valid health command may depend on packages,
generated assets, or other preparation that is present in a developer worktree
but absent on a clean runner.

Roach does not infer this preparation. Planning must set it when needed, for
example `npm ci --ignore-scripts`. Normal local `roach.py verify` and `integrate`
do not run `setup`; they assume the worker has already prepared its environment.
This keeps frequent local verification fast and avoids reinstalling dependencies
on every integration attempt.

The setup command is repository-supplied executable code and has the same trust
boundary as verification itself; see `docs/SECURITY.md`.

## Coordination state lives in the working tree

`.agent/` holds ordinary tracked files, so coordination state inherits branch,
checkout, and merge semantics. Two consequences follow, and both are guarded
rather than eliminated:

- a claim made from a task branch would be committed to that branch and revert
  on checkout, so `claim` refuses to run anywhere but the base branch;
- task records can conflict when two branches touch the same task.

The structural alternative is to read and write coordination state through git
plumbing against the base ref, never through the working tree. That removes the
class of problem entirely and makes each mutation atomic, at the cost of the
working copy of `.agent/` becoming a mirror that is stale on a task branch.

This was evaluated and deliberately deferred: the guards cover the known cases,
and the refactor is large. Revisit it if task-record merge conflicts start
happening in practice.

## Concurrent task creation races on numeric IDs

Two workers at the same base both compute the same next free ID and create
different tasks with that number. `create` skips IDs already visible locally or
on `origin`, which is not the same as making concurrent creation safe.

The push race is still what catches it. What changed is the recovery: the loser
runs `roach.py reconcile`, which sets the pending record aside, fast-forwards,
and replays it under a free id, rewriting any dependency reference to the old
one. Both tasks survive with their content intact.

This used to be a dead end. Publishing refused because the base was behind,
`git pull` refused because the untracked record wanted the same path, and
`doctor` recommended exactly those two commands. Recovery required knowing git
well enough to move the file by hand -- in a method whose premise is that a
fresh worker recovers without a human.

Worker-scoped IDs (`T004-alpha`) or a hash suffix would prevent the collision
rather than resolve it, at the cost of changing the ID format everywhere. Still
not worth it below roughly three sessions creating tasks simultaneously, now
that the collision has a one-command answer.

## Workers without a shell cannot converge

`AGENTS.md` says `roach.py` is reference semantics rather than an absolute
transport requirement. That holds for the single-file coordination commands --
`claim`, `finish`, `create`, `block`, `cancel` -- which a repository API can
reproduce.

It does **not** hold for two operations:

- `integrate` needs a real merge plus command execution;
- `verify` needs a shell by definition.

So a repository-API-only worker can claim work, edit files, and publish
coordination state, but cannot merge to the base branch or produce executable
verification evidence. Plan for a shell-capable worker to converge its work, or
scope such a worker to research, design, and documentation tasks.

A hosted Git provider with merge-result CI can potentially reproduce these
semantics remotely, but Roach v0.5 does not yet define that as a first-class
protocol. Treat it as a future portability improvement rather than silently
substituting a plain API merge for `integrate`.

## Creating a task from a task branch delays its visibility

`create` is permitted from a task branch, unlike `claim`. The new record is
committed to that branch and reaches the base branch when the work is
integrated -- it is not lost, but no other worker sees it until then.

Use `create --publish` from the base worktree when a delegated task must be
visible immediately. This asymmetry is deliberate: a claim is time-sensitive
coordination, a new task record usually is not.

## Product-template placeholder detection is literal

`PRODUCT_PLACEHOLDERS` in `scripts/roach.py` matches exact strings from the
`PRODUCT.md` template, including punctuation. Editing that punctuation in the
template silently stops the corresponding placeholder from being detected --
there is no error, only weaker validation.

If you edit `.agent/PRODUCT.md`'s template prose, update the matching entry in
`scripts/roach.py`.

## Verification text is not evidence

`--verification` is free-form. Requirement coverage checks that an ID appears on
a task with acceptance criteria, not that the task satisfies it. Capability
inventories are self-reported.

This is inherent to a protocol with no runtime, and is stated in full under
*What is actually enforced* in `AGENTS.md`. Put proof where it executes:
`.agent/VERIFY.json` for project health, a task's own `verify` command for that
task.

What Roach *can* check, and now does, is the cheaper question underneath:
did anything happen at all? A code-producing task must show commits on its
claimed branch, a recorded merge, or product files changed on the base since
the claim. This does not make the prose trustworthy -- a worker can still
commit the wrong thing and describe it well. It does close the case where a
task was claimed and finished with a confident sentence and no work anywhere,
after which the completion gate passed on a project containing nothing.

`--no-work` waives the check for work that legitimately produces no repository
change, and records the waiver on the task so the gap is visible rather than
assumed.

The same trust boundary applies to review tasks. `review_of` and `correction_of`
make the audit chain explicit and keep a completed project reopenable, but Roach
cannot determine whether a reviewer genuinely reproduced the original checks or
whether a reported correction fixes the defect. Use executable project health
commands and capability-appropriate evidence rather than treating the link
itself as proof.

## Deliberate non-goals

**The default claim lease stays at 120 minutes.** Shortening it would let a
claim expire during legitimate quiet work, which is worse than waiting out a
dead session. Use `--lease-minutes` at claim time for a shorter window, and
`adopt --force --reason "..."` when a session is known to be dead.
`ROACH_STALE_MINUTES` governs branch-activity liveness, not the lease.

**`vercel.json` ships with every project.** It costs a few lines, and `check`
only fails when the protection has been *unwired* -- the drift that
`docs/DEPLOYMENT.md` records from a real incident. Delete both `vercel.json` and
`scripts/vercel-ignore.sh` together if the project will never use a
push-triggered host.

**The template's `.agent/VERIFY.json` commands and setup stay `null`.** Planning
fills them per project. Defaults would push the wrong runtime/install/test
commands into every new repository. CI runs the Roach suites directly and runs
project health only after planning has configured the required command.

## Test suite

`.agent/tests/test_roach_remote.py` builds a bare origin and two clones and
drives `roach.py` as a subprocess, so it takes a couple of minutes rather than
seconds. That cost buys coverage of the shared-state paths -- publishing,
claims, divergence diagnosis -- where the coordinator's real defects live.

If the local runtime becomes a problem, cache one seeded bare repository across
tests instead of rebuilding per test. CI is unaffected.

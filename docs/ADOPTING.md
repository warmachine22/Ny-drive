# Adopting Roach in a project that already exists

The template's original path — **Use this template** on GitHub — only works for
a project that does not exist yet. This is the other path: installing the same
method into a repository that already has code, history, a README you like, and
a licence that is not this one.

Both paths produce the same thing afterwards. The difference is only how the
first discovery cycle begins: a new project asks the owner *what should this
be?*, while an existing one asks *what is this already, and what do you want
next?* Those are different conversations, and the installer sets up the right
one.

---

## The short version

Give your agent this, with the template URL filled in:

> Adopt the Roach Method in this repository.
>
> 1. Clone `https://github.com/warmachine22/roachmethod3` into a temporary directory.
> 2. Run `python <clone>/scripts/install.py --into . --check` and show me the plan.
> 3. If it looks right, run it without `--check`, then run `python scripts/roach.py check`.
> 4. Read `AGENTS.md` and follow it from then on.
> 5. Claim T000 and work out with me what this project is and what I want next.

That is the whole setup. Step 5 is the part that matters — the rest is copying
files.

If you would rather run it yourself first:

```bash
git clone --depth 1 https://github.com/warmachine22/roachmethod3 /tmp/roach
python /tmp/roach/scripts/install.py --into . --check    # show the plan
python /tmp/roach/scripts/install.py --into .            # do it
python scripts/roach.py check
git add -A && git commit -m "chore: adopt the Roach Method"
```

`--check` writes nothing. Run it first; the plan is short enough to read.

## What it touches, and what it will not

The installer divides your repository in two, and the division is the reason it
is safe to run.

**The method's, installed and updated on every later `roach.py upgrade`:**

`scripts/roach.py`, `scripts/install.py`, `scripts/roach_check.py`,
`.agents/skills/`, `.claude/skills/`, `.agent/tasks/README.md`, `schemas/`,
`templates/`, and the method's own `docs/`.

**Yours, seeded once and never written again:**

`.agent/PRODUCT.md`, `.agent/PLAN.md`, `.agent/PROJECT.md`, `.agent/STATE.json`,
`.agent/VERIFY.json`, `.agent/DECISIONS.md`, and your task records. After the
first session these hold your thinking, and nothing upstream may overwrite them.

**Yours, never touched at all:**

`README.md`, `LICENSE`, `CHANGELOG.md`, `package.json`, `pyproject.toml`, your
existing CI workflows, and every line of application code. The installer has no
opinion about them.

**Merged, because you probably already had one:**

`AGENTS.md` and `CLAUDE.md`. If you already have them, your text is kept and the
Roach contract is added below it inside markers:

```markdown
<!-- BEGIN ROACH METHOD (managed by roach.py upgrade; edits inside are overwritten) -->
...
<!-- END ROACH METHOD -->
```

Later upgrades replace only what is between those markers. Your own
instructions — "always run `npm test` before pushing", "never touch the billing
module" — survive every upgrade. Put your own notes *outside* the block.

Two things are opt-in because they cost you something:

- `--with-ci` installs a GitHub Actions workflow that validates coordination state and runs your project's health command. It is added automatically only if you already have `.github/workflows/`, on the assumption that you already use Actions. It never runs the method's own test suite — those test `roach.py`, which your project consumes rather than develops.
- `--with-vercel` installs protection against a push-triggered deploy host burning its free tier on coordination commits. Roach pushes far more than a human workflow does, so read `docs/DEPLOYMENT.md` before connecting any such host, whether or not you use this flag.

## What happens in the first session

The installer seeds `T000 — Recover product intent from the existing project
with the owner`, and a `PRODUCT.md` written for that job rather than a blank
one.

A worker with `repo-read`, `repo-write`, and `user-dialogue` claims it, reads
your code and history, and drafts a product definition. Then it brings you a
summary to correct. **You are not filling in a questionnaire** — you already
know what your project is. You are checking that the agent does, and saying what
you want next.

Three distinctions decide whether that draft is any good, and they are worth
pushing on:

- **What the project does** versus **what it was meant to do.** Where they differ, say which is now correct.
- **Deliberate behaviour** versus **accidents nobody removed.** An accident must not become a requirement.
- **Kept scope** versus **abandoned scope.** Half-finished features are normal; say which ones you still want.

Once you confirm the summary, `accept-product` records it and the project moves
to planning exactly as a new one would.

### Covering code that already works

Planning has to account for behaviour that is already built. Roach expects every
active requirement to be covered by a task — but for an existing project, most
coverage is a **done verification task with concise evidence**, not invented
implementation work:

```bash
python scripts/roach.py create \
  --title "Confirm checkout flow satisfies FR-003" \
  --kind verification --requirement FR-003 \
  --requires repo-read --requires shell \
  --acceptance "the existing checkout flow is exercised end to end and passes" \
  --verify "npm test -- checkout"
```

Claim it, actually run the check, and finish it. That is honest — the work
exists, and now the evidence does too. Do not create fake implementation tasks
for features that shipped last year, and do not write a requirement for every
function that happens to exist. Requirements are what the owner wants kept.

### Your existing backlog

Roach does not import issues from a tracker, and should not. Bring across only
the work you actually intend to do next; leave the rest where it is. A task
graph that mirrors a stale backlog is worse than no task graph, because
`roach.py ready` will demand coverage for all of it.

### `baseline_commit`

The installer records the commit the project was at when Roach arrived:

```json
"adoption": {
  "mode": "brownfield",
  "adopted_at": "2026-08-22T05:33:13Z",
  "baseline_commit": "bb71c399c7a6b2ed9a92a0be33473e9b5f70d45d"
}
```

That answers a question every future worker will otherwise ask: why do hundreds
of commits reference no task? Because they predate the method. Nothing before
that commit is expected to follow it, and nobody should try to retrofit it.

## Without a shell

An agent with repository write access but no terminal can do the same thing by
hand. Copy the template-owned files listed above, then:

1. Write `.agent/STATE.json` from `schemas/state.schema.json`, with `adoption.mode` set to `brownfield` and `baseline_commit` set to current HEAD.
2. Write `.agent/tasks/T000.json` as a `discovery` task requiring `repo-read`, `repo-write`, and `user-dialogue`.
3. Copy `templates/PRODUCT.brownfield.md` to `.agent/PRODUCT.md`.
4. Copy `.agent/VERIFY.json`, `.agent/PROJECT.md`, and `.agent/DECISIONS.md` from the template.
5. Add the Roach block to `AGENTS.md` inside the markers above.

Then read `docs/PROTOCOL.md`, which is the normative specification written for
exactly this situation. Note its hard edge: `verify` and `integrate` cannot be
reproduced without a shell, so plan for a shell-capable worker to converge work.

## Keeping current

The installer records the template as a git remote, so later:

```bash
python scripts/roach.py upgrade --check
python scripts/roach.py upgrade
python scripts/roach.py migrate
python scripts/roach.py check
```

`upgrade` replaces template-owned files, merges only the managed block in
`AGENTS.md` and `CLAUDE.md`, and never touches project state. `migrate` brings
`STATE.json` and task records to the current protocol version.
`docs/CHANGELOG.md` says what changed.

## Backing out

Roach adds files; it does not modify your code. To remove it:

```bash
rm -rf .agent .agents .claude schemas templates docs/PROTOCOL.md \
       scripts/roach.py scripts/install.py scripts/roach_check.py
```

Then delete the managed block from `AGENTS.md` and `CLAUDE.md`, and remove
`.github/workflows/roach-check.yml` if the installer added it. Your history,
your code, and everything you wrote are untouched — which is the point of the
ownership split.

## Reinstalling

The installer refuses to run over an existing `.agent/STATE.json`, because that
is where the project's accumulated intent lives. Use `roach.py upgrade` to
update the coordinator. `--force` reinitialises coordination state and is only
correct when you genuinely want to discard it.

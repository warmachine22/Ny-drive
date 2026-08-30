# Continuous deployment hosting

> **Status: verified end to end against a live Vercel project, 2026-08-14.**
>
> `scripts/vercel-ignore.sh` is covered by `.agent/tests/test_vercel_ignore.sh` (11 commit shapes, run with `bash .agent/tests/test_vercel_ignore.sh`), and the whole arrangement was then confirmed on a real Hobby-tier project. Four pushes produced exactly the intended outcomes:
>
> | Push | Vercel result |
> | --- | --- |
> | Commit touching `.agent/` and one unrelated file | built (mixed commits must build) |
> | Commit touching only `.agent/` | **Canceled** in 888ms |
> | `roach/*` branch carrying deliberately broken HTML | **Canceled**, never built |
> | Real change to `index.html` on `main` | built and served |
>
> Setup required no human action. See *Autonomous setup* below.

## The problem in one paragraph

Roach pushes to the remote far more often than a human developer does. Pushes are not releases here — they are checkpoints and liveness heartbeats. Hosts like Vercel, Netlify, and Cloudflare Pages assume the opposite: every push is a request to build and deploy. Connect the two without configuration and a single Roach session can generate dozens of deployments, most of them meaningless, until the account's free-tier allowance is exhausted and deployments start failing.

## Why Roach generates so many pushes

Four separate mechanisms compound:

1. **Per-task branches** (Rule 12). Each task runs on `roach/<task>-<worker>`. Every push to one creates a preview deployment.
2. **Frequent checkpoints** (Rule 13). Workers commit and push partial progress throughout a task.
3. **Pushed activity is the heartbeat** (see *Liveness*, `docs/MULTI_AGENT.md`). Pushing is how a worker proves it is still alive. The default staleness threshold is two hours, so long silent stretches risk losing the claim. Push frequency is therefore a protocol requirement, not an accident.
4. **Coordination commits go straight to the base branch.** `--publish` is available on `create`, `claim`, `heartbeat`, `release`, `finish`, `block`, `unblock`, `cancel`, and `project-status`. Each publishes a `.agent/` JSON change directly to base — which a connected host reads as a production release, despite zero application code changing.

Rough arithmetic for one task: 1 claim push + ~4 checkpoints + 1 merge + 1 finish push ≈ 7 deployments, of which 3 hit production and 1 reflects real completed work. Five tasks in a session lands near 35 deployments where a human workflow would have produced 5.

## How that presents as failure

The symptoms do not obviously point at push volume, which is what makes this worth documenting:

- **Rate-limit rejections.** Free tiers cap deployments created per day. Past the cap, deployments are refused outright.
- **Cancelled builds.** Free tiers typically allow one concurrent build. Rapid successive pushes queue, and a newer push supersedes a queued older one — which cancels it. Cancellations frequently arrive as "failed" notifications.
- **Genuinely failing builds.** Roach explicitly endorses pushing `wip(T###)` commits that are not green. That is correct behaviour on a task branch, but the host tries to build them anyway and they fail.
- **Exhausted build minutes.** Coordination-only deployments consume the same build time as real ones, because the host has no idea the diff was irrelevant.

## Required outcomes

Whatever the host, the configuration must ensure:

- pushes to `roach/*` task branches produce no deployment;
- commits touching only `.agent/` produce no deployment;
- only the base branch deploys to production;
- exactly one deployment trigger exists — never combine host CLI deploys with Git-integration deploys for the same commit.

## In-repo configuration is mandatory, dashboard settings are not durable

Prefer configuration committed to the repository. Under Rule 1 the repository is durable memory: a fresh worker can read an in-repo config, understand why it exists, and revert it through Git. A setting toggled in a web dashboard is invisible to recovery, absent from every diff, and unrevertable by `git revert`. It also cannot be inherited by the next project created from this template.

Where a host offers only a dashboard or API setting, that is an owner action under the human interruption gate — surface it with `NEED YOU:` rather than changing account settings autonomously.

## Vercel

### 1. Both pieces already ship with the template

`scripts/vercel-ignore.sh` decides per-commit whether a build should run, and the root `vercel.json` already wires it up:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "ignoreCommand": "bash scripts/vercel-ignore.sh"
}
```

Nothing needs creating. A project inheriting this template is protected from its first push.

### 2. Keep `ignoreCommand` when adding framework settings

Framework projects will need `buildCommand`, `outputDirectory`, and similar in the same file. Add them alongside `ignoreCommand` — do not replace the file wholesale, which is the easiest way to silently lose this protection.

A project that does not deploy to Vercel can leave `vercel.json` in place; it is inert.

Exit code semantics are inverted from the intuitive reading: **exit 0 aborts the build, exit 1 proceeds.**

### 2a. System environment variables

The script identifies task branches through `VERCEL_GIT_COMMIT_REF`. Vercel's documentation describes system environment variables as gated behind an **Enable access to System Environment Variables** checkbox, which suggested an unavoidable owner action.

Live testing showed otherwise: on a freshly created project with that box untouched, the ignore command received the branch name correctly and logged `skip: Roach task branch (roach/T000-test-agent-01)`. The variable is available to the Ignored Build Step regardless of the checkbox, which governs exposure to the application build and runtime.

The script still falls back to `git` and prints a `WARNING:` line if the branch cannot be determined, so a future platform change would be visible in the build log rather than silently letting task branches deploy. If that warning ever appears, enabling the checkbox is the first thing to try.

### 2b. "Canceled" is the success signal

A skipped deployment appears in the dashboard as **Canceled**, and Vercel logs `The Deployment has been canceled as a result of running the command defined in the "Ignored Build Step" setting.`

This matters because cancelled deployments are what the original failure looked like too. Distinguish them by duration and log content: an intentional skip finishes in under a second and its log contains a `skip:` line from this script. A cancellation caused by queue supersession or a rate limit does not.

### 3. Know what `ignoreCommand` does and does not fix

`ignoreCommand` runs *after* the deployment enters the `BUILDING` state. Exit 0 aborts the build and marks the deployment `CANCELED`. This saves build minutes, but a deployment record is still created — so it does **not** by itself reduce the count against a per-day deployment rate limit.

The verification run confirmed both halves of that: four pushes produced four deployment records, but the two skipped ones finished in 888ms and 2s without installing dependencies or building. Build-minute consumption drops to near zero; the record count does not change.

If deployment *count* is the binding limit rather than build minutes, the stronger control is `git.deploymentEnabled`, which prevents the deployment being created at all:

```json
{
  "git": {
    "deploymentEnabled": {
      "some-branch": false
    }
  }
}
```

Important limitation: `git.deploymentEnabled` keys are exact branch names and **do not support glob patterns**. Because Roach generates a new branch name per task (`roach/T012-codex-a31f`), this cannot be used to blanket-disable task branches. That is precisely why `ignoreCommand` is the primary mechanism here despite the cancelled-deployment caveat.

If a project still exceeds deployment counts after this, the remaining lever is the project-level setting disabling preview deployments for non-production branches. That is dashboard/API-only — treat it as an owner action.

### 4. Do not double-deploy

If the environment has an authenticated Vercel CLI, note that `vercel deploy` / `vercel --prod` is a **separate** deployment path from the Git integration. Running it in addition to pushing produces two deployments per change. Pick one trigger. For Roach projects, the Git integration is the correct one, because it keeps deployment behaviour described by in-repo config rather than by whatever an individual worker decided to run.

## Autonomous setup

A worker with an authenticated `gh` and `vercel` CLI can do the entire setup without owner involvement. This sequence was used for the verification run:

```bash
# 1. Configuration must exist before the host is connected.
#    scripts/vercel-ignore.sh ships with the template; add vercel.json.

# 2. Create the repository and push.
gh repo create <name> --private --source=. --remote=origin --push

# 3. Create the Vercel project and connect it to the repository.
vercel link --yes --project <name> --scope <team-id>
```

`vercel link` reads `vercel.json`, reports `Ignore Command: bash scripts/vercel-ignore.sh`, and connects the GitHub repository automatically — it printed `Connecting GitHub repository: ... Connected` with no dashboard step and no OAuth prompt, because the Vercel GitHub app was already installed on the account.

Two cautions learned in that run:

- `vercel link` appends `.vercel` to `.gitignore`. Commit that separately, or the next commit becomes a mixed commit and correctly builds when a pure coordination commit was intended.
- Do not follow this with `vercel deploy`. The Git connection is now the trigger; adding a CLI deploy doubles every deployment.

If the Vercel GitHub app is **not** yet installed on the account, `vercel link` cannot connect the repository and the install is a one-time owner action. Surface it with `NEED YOU:` rather than attempting it.

## Other hosts

The same four required outcomes apply; only the mechanism differs.

- **Netlify** — `netlify.toml` supports an `ignore` command per context, with the same exit-code convention. Branch deploys can be restricted to specific branches in `netlify.toml`.
- **Cloudflare Pages** — supports branch include/exclude rules for automatic builds, configured per project. Exclusion patterns do support wildcards, so `roach/*` can be excluded directly.
- **GitHub Pages / Actions-based deploys** — narrow the workflow trigger: `on: push: branches: [main]` plus a `paths-ignore: ['.agent/**']` filter.

Confirm current behaviour against host documentation before relying on any of the above; these APIs change.

## Setup checklist for the worker connecting a host

1. Confirm the host configuration is present **before** connecting the host. For Vercel this ships with the template; verify `vercel.json` still contains `ignoreCommand`.
2. Run `bash .agent/tests/test_vercel_ignore.sh` to confirm the decision logic.
3. Record the host and its configuration in `.agent/PLAN.md` under Dependencies / Integrations.
4. Record any owner-performed dashboard setting in `.agent/DECISIONS.md`, since it is otherwise invisible to recovery.
5. **Verify on the live host immediately after connecting.** Push one coordination-only commit and confirm the host cancelled it, before doing real work:

   ```bash
   vercel ls --scope <team-id>
   vercel inspect --logs <deployment-url> --scope <team-id>
   ```

   A correct skip shows `Canceled`, a sub-second duration, and a `skip:` line in the log. Anything else means the configuration is not active — stop and fix it before the allowance is spent.
6. After the first real session, check the deployment list again and confirm builds correspond to real changes rather than push count.

## Background

Recorded 2026-08-14, after a real Hobby-tier Vercel project built with this template hit repeated deployment failures. The owner's prior workflow — infrequent manual pushes from a single human — had never approached the limits. The failure was not caused by application code; it was caused by the mismatch between Roach's push semantics and the host's push semantics.

The design conclusion worth preserving: **Roach should not push less.** Push frequency is load-bearing for multi-agent coordination and crash recovery. The correct fix is teaching the host which pushes are actually releases.

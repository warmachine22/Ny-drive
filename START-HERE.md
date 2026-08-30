# Start here — the prompts to copy

This file has one job: give you the exact text to paste into an AI agent.
Nothing here needs to be understood, edited, or run by you. Copy a block, paste
it, done.

There are two situations. Pick the one you are in.

---

## 1. I want to add this to a project I already have

Open your existing project with your AI agent and paste this:

```text
Adopt the Roach Method in this repository.

1. Clone https://github.com/warmachine22/roachmethod3 into a temporary directory.
2. Run `python <clone>/scripts/install.py --into . --check` and show me the plan.
3. If it looks right, run it without `--check`, then run `python scripts/roach.py check`.
4. Read AGENTS.md and follow it from then on.
5. Claim T000 and work out with me what this project is and what I want next.
```

**What will happen.** The agent installs the method, then reads your existing
code and writes up what it thinks your project is and does. It shows you that
summary and asks you to correct it. Once you confirm, it follows the Roach rules
for everything after that.

**Your files are safe.** Your README, licence, code, and existing setup are not
touched — the method is added alongside them. Step 2 prints the full list of
what it would change *before* anything is written, so you can look first.

Full detail, if you ever want it: [docs/ADOPTING.md](docs/ADOPTING.md).

---

## 2. I want to start a brand-new project

There are two ways, depending on how you make the new repository.

### 2a. Made from this template (the original way)

On GitHub, click **Use this template** → **Create a new repository**. The method
is already in it, so there is nothing to install. Open that new repository with
your AI agent and paste this, with your idea filled in:

```text
Use the Roach Method in this repository. Help me define and build
[describe what you want to make, in plain language].
```

### 2b. An empty repository you made some other way

If the repository already exists but is empty — you created it on GitHub
normally, or ran `git init` on your machine — paste this instead:

```text
Set up the Roach Method in this repository.

1. Clone https://github.com/warmachine22/roachmethod3 into a temporary directory.
2. Run `python <clone>/scripts/install.py --into .` and then `python scripts/roach.py check`.
3. Read AGENTS.md and follow it from then on.

Then help me define and build
[describe what you want to make, in plain language].
```

It is the same installer as section 1. It notices the repository is empty and
sets up the new-project starting point instead of the adopt-an-existing-project
one.

**What will happen, either way.** The agent asks you focused questions about
what you want, one at a time, and writes the answers down as it goes. When it
understands enough, it shows you a summary to confirm. After that it plans and
builds on its own, and only comes back to you when it genuinely needs you.

---

## 3. I want the newest version of the method in a project that already uses it

Paste this into the project:

```text
Run `python scripts/roach.py upgrade --check` and show me what would change.
If it looks right, apply it, then run `roach.py migrate` and `roach.py check`.
```

This updates the method itself and leaves everything about your project alone.

---

## What you will be asked to do, ever

Three things, and nothing else:

1. **Describe what you want**, in ordinary language.
2. **Confirm or correct one summary** of what is being built.
3. **Do things only you can do** — sign in somewhere, approve access, or look at
   something and say whether it feels right.

If an agent asks you which library to use or whether to keep going, it is not
following the method. Point it at `AGENTS.md`.

---

## What everything else in this repository is

You do not need any of it. It is here for the agents, and for anyone who wants
to check how the method works.

| File | Who it is for |
| --- | --- |
| `START-HERE.md` | You. This file. |
| `README.md` | Anyone evaluating whether to use the method. |
| `docs/EXAMPLE.md` | You, if you want to see a whole project run start to finish. |
| `docs/ADOPTING.md` | You or your agent, for adding this to an existing project. |
| `AGENTS.md` | The agents. The rules they follow. |
| `scripts/`, `schemas/`, `.agent/`, `docs/` (the rest) | The agents and the machinery. |

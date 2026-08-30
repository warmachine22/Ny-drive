# Security notes

Roach is a coordination protocol, not a sandbox. Two properties are worth knowing before you run it against a repository you did not write.

## Verification commands run with your privileges

`.agent/VERIFY.json` holds shell commands, and `roach.py verify` executes them:

```bash
python scripts/roach.py verify quick
```

The optional `setup` field is also executable shell text. The continuity CI workflow runs it before project verification when a fresh checkout needs dependency installation, generated assets, or other preparation.

A task record's optional `verify` field is executable shell text too, and `roach.py finish` runs it. It has exactly the same trust boundary: read it before finishing a task in a repository you did not write, the same way you would read `.agent/VERIFY.json` before running `verify`.

The command text comes from the repository. Cloning someone else's Roach project and running verification — or allowing its continuity workflow to run with secrets/privileged runners — therefore executes their code with whatever access that environment has.

This is the same risk profile as a `Makefile`, an npm `postinstall`, or a CI config — but Roach is explicitly designed to be copied between projects and driven by autonomous agents, so it is stated plainly here rather than assumed.

**Before running `verify` in an unfamiliar repository, read `.agent/VERIFY.json`.** It is short by design. Review both `setup` and the selected verification command.

The same applies to `roach.py integrate`, which runs verification on the merged result.

## Agents act on repository contents

The method's premise is that a fresh agent recovers its instructions from files in the repository — `AGENTS.md`, `PRODUCT.md`, `PLAN.md`, task records. That is the feature, and it is also the attack surface: anything written into those files is read by an agent as direction.

For a repository you own, this is fine. For one you cloned, or one where another party can open pull requests, review changes to `.agent/` and `AGENTS.md` with the same care you would apply to changes in CI configuration. A malicious task record is a prompt-injection vector.

Roach does not attempt to defend against this. It assumes the repository is trusted.

## What Roach does protect

Within a trusted repository, the coordinator does enforce real invariants: it never force-pushes, never publishes unrelated local commits, refuses to overwrite another worker's live claim, rolls back a coordination commit that could not be pushed, and rolls back a merge that fails verification.

Those protect against accident and race conditions between cooperating agents. They are not a defence against a hostile one — see *What is actually enforced* in `AGENTS.md`.

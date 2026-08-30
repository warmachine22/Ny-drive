@AGENTS.md

# Claude Code adapter

Use the repository-wide Roach Method v0.5 rules in `AGENTS.md` as the controlling development protocol.

For discovery, planning, starting, resuming, checkpointing, or handing off work, use the `project-continuity` skill in `.claude/skills/project-continuity/` when available.

Do not duplicate long project context here. Recover product intent from `.agent/PRODUCT.md`, technical strategy from `.agent/PLAN.md` when present, and current coordination from `.agent/` plus Git.

#!/usr/bin/env bash
# Vercel "Ignored Build Step" for Roach Method repositories.
#
# Roach pushes constantly: task branches, WIP checkpoints, and coordination
# commits are all normal. Vercel treats every push as a release request, which
# exhausts free-tier allowances and produces failed/cancelled deployments.
# This script decides which pushes are actually worth building.
#
# Wire it up in vercel.json:
#   { "ignoreCommand": "bash scripts/vercel-ignore.sh" }
#
# Exit code semantics are inverted from the intuitive reading:
#   exit 0 -> abort the build   (deployment is marked CANCELED)
#   exit 1 -> continue the build
#
# See docs/DEPLOYMENT.md for background and limitations.

set -uo pipefail

# Determine the branch. VERCEL_GIT_COMMIT_REF is the documented source. Live
# testing on 2026-08-14 confirmed it is available to the Ignored Build Step even
# when application/runtime access to Vercel system environment variables has
# not been enabled. Fall back to git anyway, and say so loudly if neither works
# so a future platform change cannot silently let task branches build.
branch="${VERCEL_GIT_COMMIT_REF:-}"
if [ -z "$branch" ]; then
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [ "$branch" = "HEAD" ] && branch=""
  if [ -z "$branch" ]; then
    echo "WARNING: branch name unavailable. Enable 'System Environment Variables'"
    echo "WARNING: in Vercel project settings, or roach/* branches will build."
  else
    echo "note: VERCEL_GIT_COMMIT_REF empty, using git branch '$branch'"
  fi
fi

# Roach task branches carry unfinished work by design. Never build them.
case "$branch" in
  roach/*)
    echo "skip: Roach task branch ($branch)"
    exit 0
    ;;
esac

# Coordination commits change only .agent/ bookkeeping and cannot affect the
# built application. If the diff touches nothing outside .agent/, skip.
#
# git diff --quiet exits 0 when there are NO differences. A failure here
# (for example a shallow clone with no HEAD^) is non-zero and falls through
# to building, which is the safe default.
if git diff --quiet HEAD^ HEAD -- . ':(exclude).agent' 2>/dev/null; then
  echo "skip: coordination-only change (.agent/ bookkeeping)"
  exit 0
fi

echo "build: real application change on ${branch:-unknown branch}"
exit 1

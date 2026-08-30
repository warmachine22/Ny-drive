#!/usr/bin/env bash
# Exercise scripts/vercel-ignore.sh against realistic Roach commit shapes.
# exit 0 = Vercel skips the build, exit 1 = Vercel builds.

set -uo pipefail

SCRIPT="${1:-$(cd "$(dirname "$0")/../.." && pwd)/scripts/vercel-ignore.sh}"
if [ ! -f "$SCRIPT" ]; then
  echo "cannot find vercel-ignore.sh at: $SCRIPT" >&2
  exit 2
fi
WORK="$(mktemp -d)"
PASS=0
FAIL=0

cd "$WORK"
git init -q -b main .
git config user.email t@t.t
git config user.name t

run_case() {
  local name="$1" branch="$2" want="$3"
  local got
  VERCEL_GIT_COMMIT_REF="$branch" bash "$SCRIPT" >/dev/null 2>&1
  got=$?
  local want_word="build" got_word="build"
  [ "$want" -eq 0 ] && want_word="skip"
  [ "$got" -eq 0 ] && got_word="skip"
  if [ "$got" -eq "$want" ]; then
    printf '  PASS  %-52s -> %s\n' "$name" "$got_word"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %-52s -> %s (wanted %s)\n' "$name" "$got_word" "$want_word"
    FAIL=$((FAIL + 1))
  fi
}

mkdir -p .agent/tasks src

# --- base history -----------------------------------------------------------
echo "app v1" > src/app.js
echo '{"phase":"execution"}' > .agent/STATE.json
git add -A && git commit -qm "initial app"

echo "== A. first commit, no parent (must fail safe -> build) =="
run_case "no HEAD^ available" "main" 1

echo
echo "== B. coordination-only commits (must skip) =="
echo '{"phase":"planning"}' > .agent/STATE.json
git add -A && git commit -qm "chore: coordination"
run_case "top-level .agent/STATE.json only" "main" 0

echo '{"id":"T001"}' > .agent/tasks/T001.json
git add -A && git commit -qm "chore: new task record"
run_case "nested .agent/tasks/T001.json only" "main" 0

echo
echo "== C. real application changes (must build) =="
echo "app v2" > src/app.js
git add -A && git commit -qm "feat: real change"
run_case "src/app.js only" "main" 1

echo
echo "== D. mixed commit: app + coordination (must build) =="
echo "app v3" > src/app.js
echo '{"phase":"execution"}' > .agent/STATE.json
git add -A && git commit -qm "feat: app plus coordination"
run_case "src/ and .agent/ together" "main" 1

echo
echo "== E. Roach task branches (must always skip) =="
git checkout -q -b roach/T012-codex-a31f
echo "wip broken (" > src/app.js
git add -A && git commit -qm "wip(T012): broken checkpoint"
run_case "roach/T012-codex-a31f, broken WIP" "roach/T012-codex-a31f" 0
run_case "roach/T007-claude-9f2b, same commit" "roach/T007-claude-9f2b" 0

echo
echo "== F. merge of finished task back to main (must build) =="
echo "app v4 good" > src/app.js
git add -A && git commit -qm "fix(T012): make it work"
git checkout -q main
git merge -q --no-ff roach/T012-codex-a31f -m "merge T012"
run_case "merge commit carrying app changes" "main" 1

echo
echo "== G. non-Roach branch with app change (preview, must build) =="
git checkout -q -b feature/human-experiment
echo "app v5" > src/app.js
git add -A && git commit -qm "human experiment"
run_case "feature/human-experiment" "feature/human-experiment" 1

echo
echo "== H. env var unavailable, git fallback (system env vars unchecked) =="
run_noenv() {
  local name="$1" want="$2" got got_word="build" want_word="build"
  ( unset VERCEL_GIT_COMMIT_REF; bash "$SCRIPT" ) >/dev/null 2>&1
  got=$?
  [ "$want" -eq 0 ] && want_word="skip"
  [ "$got" -eq 0 ] && got_word="skip"
  if [ "$got" -eq "$want" ]; then
    printf '  PASS  %-52s -> %s\n' "$name" "$got_word"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %-52s -> %s (wanted %s)\n' "$name" "$got_word" "$want_word"
    FAIL=$((FAIL + 1))
  fi
}
run_noenv "no env var, git says feature/* -> build" 1
git checkout -q roach/T012-codex-a31f
run_noenv "no env var, git says roach/* -> skip" 0
git checkout -q feature/human-experiment

echo
echo "---------------------------------------------"
echo "passed: $PASS   failed: $FAIL"
cd / && rm -rf "$WORK"
[ "$FAIL" -eq 0 ]

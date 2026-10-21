#!/usr/bin/env bash
# Deploy one project to Agent Studio: push it to its AS branch, then merge that branch
# into the AS parent branch.
#
# Usage: deploy-project.sh push|merge|all
# Run from the repo root, with the ADK's virtual environment active.
#
# Env:
#   PROJECT        account/project
#   PROJECT_DIR    the project's files to deploy (default agents/$PROJECT)
#   AS_BRANCH      the AS branch, named after the git branch
#   PARENT_BRANCH  the AS and git branch merged into (default main)
#   push:  BASE_SHA     the git parent-branch commit PROJECT_DIR was built on
#          BRANCH_REF   a git ref holding the branch's pyproject.toml
#          PR_NUMBER    the PR, to read its skip-as-sync-check label (needs GH_TOKEN)
#          RETRY_HINT   what to do after fixing a failure, e.g. "Re-queue the PR"
#   merge: MERGE_MESSAGE
set -euo pipefail

MODE="$1"
PROJECT_DIR="${PROJECT_DIR:-agents/$PROJECT}"
PARENT_BRANCH="${PARENT_BRANCH:-main}"
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/poly_adk_scripts"

# Runs a check script and prints its exit code: 0 and 1 are answers, anything else fails.
check() {
  local code=0
  python "$@" >&2 || code=$?
  if [ "$code" -gt 1 ]; then
    echo "::error::$(basename "$1") failed for $PROJECT" >&2
    exit 1
  fi
  echo "$code"
}

push() {
  python "$SCRIPTS/check_poly_adk_version_protection.py" \
    "$(jq -cn --arg p "$PROJECT" '[$p]')" "$AS_BRANCH" --branch-ref "$BRANCH_REF"

  local missing matches
  missing=$(check "$SCRIPTS/check_branch_exists.py" "$PROJECT_DIR" "$AS_BRANCH")
  if [ "$missing" = 1 ]; then
    echo "Branch $AS_BRANCH does not exist — checking if AS $PARENT_BRANCH is already in sync"
    matches=$(check "$SCRIPTS/check_as_parent_matches_local.py" "$PROJECT_DIR")
    if [ "$matches" = 0 ]; then
      echo "AS $PARENT_BRANCH already matches merged(git $PARENT_BRANCH, git branch), nothing to do"
      return
    fi
  fi

  # The AS merge can clobber Studio-side changes on the AS parent branch that a sync
  # hasn't pulled back into git yet. Compare the AS parent against the git base commit via
  # a disposable worktree. "In sync" means a Sync Projects run would commit nothing: on a
  # hash mismatch the script applies the sync's own pull+format pipeline to the worktree
  # and asks git, so formatting-only divergence does not block. A skip-as-sync-check
  # label on the PR bypasses the check for known drift.
  if [ -n "${PR_NUMBER:-}" ] && gh pr view "$PR_NUMBER" --json labels -q '.labels[].name' | grep -qx "skip-as-sync-check"; then
    echo "skip-as-sync-check label on PR #$PR_NUMBER — skipping AS parent sync check"
  else
    if ! git cat-file -e "$BASE_SHA:agents/$PROJECT/project.yaml" 2>/dev/null; then
      git fetch --depth=1 --no-tags origin "$BASE_SHA"
    fi
    if git cat-file -e "$BASE_SHA:agents/$PROJECT/project.yaml" 2>/dev/null; then
      # Prettier is the only tool the sync's format hook needs that isn't in the venv.
      # Pin the same version sync_projects.yml installs — a mismatch shows up as false drift.
      command -v prettier >/dev/null || npm install -g prettier@3.1.0
      local worktree="${RUNNER_TEMP:-/tmp}/parent-check"
      git worktree add "$worktree" "$BASE_SHA"
      local code
      code=$(check "$SCRIPTS/check_parent_in_sync.py" "$worktree/agents/$PROJECT" --branch "$PARENT_BRANCH")
      git worktree remove --force "$worktree"
      if [ "$code" = 1 ]; then
        echo "::error::AS branch $PARENT_BRANCH is not in sync with git $PARENT_BRANCH for $PROJECT."
        echo "Run the Sync Projects workflow for this project. $RETRY_HINT."
        echo "To bypass, add the skip-as-sync-check label. $RETRY_HINT."
        exit 1
      fi
      echo "AS $PARENT_BRANCH is in sync with git $PARENT_BRANCH for $PROJECT"
    else
      echo "agents/$PROJECT does not exist at the base commit (new project) — nothing to clobber"
    fi
  fi

  # push_to_branch.py force-overwrites the whole project, so content built on a base that
  # is behind the parent branch for this project would revert those commits in Agent
  # Studio. Runs immediately before the push to keep the race window minimal.
  local parent_sha
  parent_sha=$(git ls-remote origin "refs/heads/$PARENT_BRANCH" | cut -f1)
  if [ -z "$parent_sha" ]; then
    echo "Could not resolve origin/$PARENT_BRANCH"
    exit 1
  fi
  if [ "$parent_sha" != "$BASE_SHA" ]; then
    git fetch --depth=1 --no-tags origin "$BASE_SHA" "$parent_sha"
    if ! git diff --quiet "$BASE_SHA" "$parent_sha" -- "agents/$PROJECT"; then
      echo "agents/$PROJECT changed on $PARENT_BRANCH after this deploy was built."
      echo "  base:            $BASE_SHA"
      echo "  current $PARENT_BRANCH: $parent_sha"
      echo ""
      echo "  Pushing this checkout would revert those changes in Agent Studio."
      echo "  Changed files:"
      git diff --name-only "$BASE_SHA" "$parent_sha" -- "agents/$PROJECT" | sed 's/^/    /'
      echo ""
      echo "  $RETRY_HINT: the rebuilt deploy will include them."
      exit 1
    fi
    echo "$PARENT_BRANCH advanced to $parent_sha but left agents/$PROJECT untouched"
  fi

  python "$SCRIPTS/push_to_branch.py" "$PROJECT_DIR" "$AS_BRANCH"
}

merge() {
  local missing
  missing=$(check "$SCRIPTS/check_branch_exists.py" "$PROJECT_DIR" "$AS_BRANCH")
  if [ "$missing" = 1 ]; then
    echo "Nothing to merge for $PROJECT: AS $PARENT_BRANCH already matches"
    return
  fi
  python "$SCRIPTS/merge_branch.py" "$PROJECT_DIR" "$AS_BRANCH" "$MERGE_MESSAGE"
  missing=$(check "$SCRIPTS/check_branch_exists.py" "$PROJECT_DIR" "$AS_BRANCH")
  if [ "$missing" = 0 ]; then
    echo "Branch $AS_BRANCH still exists after merge"
    exit 1
  fi
  echo "Branch $AS_BRANCH successfully deleted"
}

case "$MODE" in
  push) push ;;
  merge) merge ;;
  all)
    push
    merge
    ;;
  *)
    echo "Usage: deploy-project.sh push|merge|all" >&2
    exit 2
    ;;
esac

#!/usr/bin/env bash
# Check out the merge of a PR into its base branch, like the merge queue's merge group.
#
# Usage: checkout-merge.sh <dir>
# Env:   BASE_SHA, HEAD_SHA and MERGE_BASE, as the gate recorded them. The same three commits
#        always give the same tree, so every job deploys the same content.
set -euo pipefail

dir="$1"

git fetch --depth=1 --no-tags origin "$BASE_SHA" "$HEAD_SHA" "$MERGE_BASE"

if ! result=$(git merge-tree --write-tree --name-only --merge-base="$MERGE_BASE" "$BASE_SHA" "$HEAD_SHA"); then
  echo "::error::The PR conflicts with its base branch:"
  sed -n '2,/^$/p' <<<"$result"
  exit 1
fi

merged=$(git -c user.name=merge-command -c user.email=merge-command@localhost \
  commit-tree "$(head -n 1 <<<"$result")" -p "$BASE_SHA" -p "$HEAD_SHA" -m "Merge $HEAD_SHA into $BASE_SHA")
git worktree add --detach "$dir" "$merged"

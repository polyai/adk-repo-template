#!/bin/bash
# Sync CI/CD infrastructure files from the adk-repo-template template repo.
#
# Usage:
#   .github/scripts/sync-from-template.sh            # preview changes
#   .github/scripts/sync-from-template.sh --apply     # apply and commit
#   .github/scripts/sync-from-template.sh --ref v1.2  # sync from a specific ref
#
# Synced paths (infrastructure, meant to be identical across repos):
#   .github/workflows/, .github/scripts/, .github/assets/
#   .pre-commit-config.yaml
#
# NOT synced (repo-specific):
#   pyproject.toml, README.md, .gitignore
#   CODEOWNERS, SECURITY.md, .github/ISSUE_TEMPLATE/ (the template repo's own)
#   agents/ (project content)

set -e

TEMPLATE_REPO="https://github.com/polyai/adk-repo-template.git"
TEMPLATE_REMOTE="template-upstream"
TEMPLATE_REF="main"
APPLY=false

SYNC_PATHS=(
  ".github/workflows"
  ".github/scripts"
  ".github/assets"
  ".pre-commit-config.yaml"
)

while [[ $# -gt 0 ]]; do
  case $1 in
    --apply) APPLY=true; shift ;;
    --ref) TEMPLATE_REF="$2"; shift 2 ;;
    --repo) TEMPLATE_REPO="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^$/s/^# //p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Add/update the template remote
if git remote get-url "$TEMPLATE_REMOTE" &>/dev/null; then
  git remote set-url "$TEMPLATE_REMOTE" "$TEMPLATE_REPO"
else
  git remote add "$TEMPLATE_REMOTE" "$TEMPLATE_REPO"
fi

echo "Fetching $TEMPLATE_REF from $TEMPLATE_REPO..."
git fetch "$TEMPLATE_REMOTE" "$TEMPLATE_REF" --quiet

# Checkout template files into the working tree
for path in "${SYNC_PATHS[@]}"; do
  echo "Syncing: $path"
  git checkout "$TEMPLATE_REMOTE/$TEMPLATE_REF" -- "$path" 2>/dev/null || {
    echo "  Warning: $path not found in template, skipping"
  }
done

# Show what changed
echo ""
if git diff --cached --quiet && git diff --quiet; then
  echo "Already up to date — no changes from template."
  exit 0
fi

echo "=== Changes from template ==="
git diff --stat
git diff --cached --stat
echo ""

if [ "$APPLY" = true ]; then
  git add "${SYNC_PATHS[@]}"
  git commit -m "chore: Sync infrastructure from adk-repo-template

Synced from $TEMPLATE_REMOTE/$TEMPLATE_REF"
  echo "Committed. Review with 'git show' then push."
else
  echo "Preview only. Run with --apply to commit, or review and stage manually."
  echo "To undo: git checkout -- ${SYNC_PATHS[*]}"
fi

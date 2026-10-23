#!/usr/bin/env bash
# Pre-commit entry point: runs format-project.sh on every project with a staged
# file, so a commit gets exactly the formatting a sync from Dialog Studio applies.
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)

# agents/<account>/<project>/<file> -> agents/<account>/<project>
projects=$(printf '%s\n' "$@" | awk -F/ '$1 == "agents" && NF > 3 { print $1 "/" $2 "/" $3 }' | sort -u)

status=0
for project in $projects; do
  [ -f "$project/project.yaml" ] || continue
  "$script_dir/format-project.sh" "$project" || status=1
done
exit "$status"

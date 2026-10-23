#!/usr/bin/env bash
# Lint, format-check, type-check and test Dialog Studio projects.
#
# Usage: lint-and-test.sh '<projects json>'   e.g. '["account/project"]'
# Run from the root of the checkout to check, with its virtual environment active and
# prettier installed.
set -euo pipefail

scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

PATHS=()
YAML=()
while IFS= read -r dir; do
  [ -z "$dir" ] && continue
  PATHS+=("agents/$dir")
  YAML+=("agents/$dir/**/*.{yaml,yml}")
done < <(jq -r '.[]' <<<"$1")

if [ ${#PATHS[@]} -eq 0 ]; then
  echo "No projects to check"
  exit 0
fi

echo "== Lint with ruff"
ruff check "${PATHS[@]}"

echo "== Format check with ruff"
ruff format --check "${PATHS[@]}"

echo "== Format check YAML with prettier"
prettier --check "${YAML[@]}"

echo "== Type check with ty"
uvx ty check "${PATHS[@]}"

echo "== Run tests"
"$scripts_dir/run-tests.sh" "$1"

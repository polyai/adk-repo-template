#!/bin/bash
# Run tests for changed project directories
# Usage: run-tests.sh '["project-a", "project-b"]'

set -e

CHANGED_DIRS="${1:-[]}"

if [ "$CHANGED_DIRS" == "[]" ] || [ -z "$CHANGED_DIRS" ]; then
  echo "No project directories were changed, skipping tests"
  exit 0
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

while read -r dir; do
  PROJECT_PATH="agents/$dir"
  if [ -d "$PROJECT_PATH" ]; then
    echo "Running tests for $PROJECT_PATH"
    set +e
    pytest "$PROJECT_PATH" -v --tb=short --color=no
    EXIT_CODE=$?
    set -e
    if [ $EXIT_CODE -ne 0 ] && [ $EXIT_CODE -ne 5 ]; then
      exit $EXIT_CODE
    fi
    if [ $EXIT_CODE -eq 5 ]; then
      echo "No tests found in $PROJECT_PATH, skipping"
    fi
  else
    echo "Warning: Directory $PROJECT_PATH does not exist"
  fi
done < <(echo "$CHANGED_DIRS" | jq -r '.[]')

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

FAILED_PROJECTS=()

while read -r dir; do
  PROJECT_PATH="agents/$dir"
  if [ -d "$PROJECT_PATH" ]; then
    echo "Running tests for $PROJECT_PATH"
    set +e
    # CI-friendly pytest options: quiet (progress dots rather than a line per
    # passing test), no header, short tracebacks, no colour, and a short summary
    # of everything that did not pass.
    pytest "$PROJECT_PATH" -q --no-header --tb=short --color=no -ra
    EXIT_CODE=$?
    set -e
    # Exit code 5 means no tests were collected, which is OK
    if [ $EXIT_CODE -eq 5 ]; then
      echo "No tests found in $PROJECT_PATH, skipping"
    elif [ $EXIT_CODE -ne 0 ]; then
      # Record and carry on, so one failing project does not hide the rest.
      echo "::error::Tests failed for $PROJECT_PATH"
      FAILED_PROJECTS+=("$PROJECT_PATH")
    fi
  else
    echo "Warning: Directory $PROJECT_PATH does not exist"
  fi
done < <(echo "$CHANGED_DIRS" | jq -r '.[]')

if [ ${#FAILED_PROJECTS[@]} -gt 0 ]; then
  echo "Tests failed for ${#FAILED_PROJECTS[@]} project(s):"
  printf '  %s\n' "${FAILED_PROJECTS[@]}"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### Projects with failing tests"
      echo
      printf -- '- `%s`\n' "${FAILED_PROJECTS[@]}"
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 1
fi

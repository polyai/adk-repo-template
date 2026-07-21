#!/bin/bash
# Detect changed directories under a given prefix
#
# Usage:
#   detect-changed-dirs.sh --prefix agents --depth 2 --range BASE HEAD --merge-base
#   detect-changed-dirs.sh --prefix agents --depth 1 --range BASE HEAD

set -e

PREFIX=""
DEPTH=1
FORMAT="json"
MODE=""
BASE_SHA=""
HEAD_SHA=""
REMOTE_NAME="origin"
USE_MERGE_BASE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --prefix) PREFIX="$2"; shift 2 ;;
    --depth) DEPTH="$2"; shift 2 ;;
    --staged) MODE="staged"; shift ;;
    --range) MODE="range"; BASE_SHA="$2"; HEAD_SHA="$3"; shift 3 ;;
    --merge-base) USE_MERGE_BASE=true; shift ;;
    --format) FORMAT="$2"; shift 2 ;;
    *)
      if [ -z "$MODE" ]; then
        MODE="upstream"
        REMOTE_NAME="$1"
      fi
      shift
      ;;
  esac
done

if [ -z "$PREFIX" ]; then
  echo "Error: --prefix is required" >&2
  exit 1
fi

MODE="${MODE:-upstream}"

SED_PATTERN=""
for ((i=1; i<=DEPTH; i++)); do
  if [ $i -eq 1 ]; then
    SED_PATTERN="[^/]\\+"
  else
    SED_PATTERN="${SED_PATTERN}/[^/]\\+"
  fi
done

case $MODE in
  staged)
    CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACDMRT | grep "^${PREFIX}/" || true)
    ;;
  range)
    if [ "$BASE_SHA" == "0000000000000000000000000000000000000000" ]; then
      BASE_SHA="4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    fi
    if [ "$USE_MERGE_BASE" = true ]; then
      DIFF_RANGE="${BASE_SHA}...${HEAD_SHA}"
    else
      DIFF_RANGE="${BASE_SHA}..${HEAD_SHA}"
    fi
    CHANGED_FILES=$(git diff --name-only --diff-filter=ACDMRT ${DIFF_RANGE} 2>/dev/null | grep "^${PREFIX}/" || true)
    ;;
  upstream)
    REMOTE_REF=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "")
    if [ -z "$REMOTE_REF" ]; then
      if git rev-parse --verify "${REMOTE_NAME}/main" >/dev/null 2>&1; then
        BASE_SHA="${REMOTE_NAME}/main"
      elif git rev-parse --verify "${REMOTE_NAME}/master" >/dev/null 2>&1; then
        BASE_SHA="${REMOTE_NAME}/master"
      else
        if [ "$FORMAT" == "json" ]; then echo "[]"; fi
        exit 0
      fi
    else
      BASE_SHA="$REMOTE_REF"
    fi
    CHANGED_FILES=$(git diff --name-only --diff-filter=ACDMRT ${BASE_SHA}..HEAD 2>/dev/null | grep "^${PREFIX}/" || true)
    ;;
esac

if [ -z "$CHANGED_FILES" ]; then
  if [ "$FORMAT" == "json" ]; then echo "[]"; fi
  exit 0
fi

CHANGED_DIRS=$(echo "$CHANGED_FILES" | sed -n "s|^${PREFIX}/\\(${SED_PATTERN}\\)/.*|\\1|p" | sort -u)

CHANGED_DIRS=$(echo "$CHANGED_DIRS" | while IFS= read -r rel_dir; do
  [ -z "$rel_dir" ] && continue
  if [ -f "${PREFIX}/${rel_dir}/project.yaml" ] || [ -f "${PREFIX}/${rel_dir}/pyproject.toml" ]; then
    echo "$rel_dir"
  fi
done | sort -u)

if [ -z "$CHANGED_DIRS" ]; then
  if [ "$FORMAT" == "json" ]; then echo "[]"; fi
  exit 0
fi

case $FORMAT in
  json) echo "$CHANGED_DIRS" | jq -R -s -c 'split("\n") | map(select(length > 0))' ;;
  lines) echo "$CHANGED_DIRS" ;;
  paths) echo "$CHANGED_DIRS" | sed "s|^|${PREFIX}/|" ;;
esac

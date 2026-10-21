#!/usr/bin/env bash
# THE definition of this repo's post-pull formatting pass, applied to one
# project directory (the single argument): the ADK's own formatting
# (poly format), then ruff and prettier. Called by sync_projects.yml and
# check_parent_in_sync.py — "in sync with Dialog Studio" means a pull followed
# by this script changes nothing, so any formatter change must happen here and
# nowhere else, or the merge-time sync check reports formatting as drift.
#
# Contract with callers: formatter exit codes are tolerated; a missing tool is
# not — silently skipping a formatter skews the comparison basis. Callers
# treat a non-zero exit as an error, never as project drift.
set -u

command -v poly >/dev/null || { echo "format-project: poly not found" >&2; exit 1; }
command -v ruff >/dev/null || { echo "format-project: ruff not found" >&2; exit 1; }
command -v prettier >/dev/null || { echo "format-project: prettier not found" >&2; exit 1; }

cd "$1"
poly format --path . || true
ruff format . || true
ruff check . --fix || true
prettier --write "**/*.{yaml,yml}" || true

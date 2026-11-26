#!/usr/bin/env python3
"""Write the projects Sync Projects syncs to $GITHUB_OUTPUT.

Outputs `projects` (paths relative to agents/, sorted), `has_projects`, and
`shards`: the runners to share them across, one per SYNC_PROJECTS_PER_SHARD
projects, at most SYNC_MAX_SHARDS.

INPUT_ACCOUNT_ID and INPUT_PROJECT_ID filter them ("*" or empty for all).
Finding none is an error only when a filter named the projects to sync.
"""

import json
import math
import os
import sys
from pathlib import Path

import yaml


def main() -> int:
    account_filter = os.environ.get("INPUT_ACCOUNT_ID", "*")
    project_filter = os.environ.get("INPUT_PROJECT_ID", "*")
    filter_account = account_filter not in ("", "*")
    filter_project = project_filter not in ("", "*")
    if filter_account:
        print(f"Filtering by account_id: {account_filter}")
    if filter_project:
        print(f"Filtering by project_id: {project_filter}")

    projects = []
    for path in sorted(Path("agents").rglob("project.yaml")):
        if len(path.relative_to("agents").parts) > 3:
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            print(f"::warning::Skipping {path}: invalid YAML ({exc})")
            continue
        if filter_account and data.get("account_id") != account_filter:
            continue
        if filter_project and data.get("project_id") != project_filter:
            continue
        projects.append(path.parent.relative_to("agents").as_posix())

    if not projects and (filter_account or filter_project):
        print("::error::No projects found matching filters")
        return 1

    per_shard = int(os.environ.get("SYNC_PROJECTS_PER_SHARD", "40"))
    max_shards = int(os.environ.get("SYNC_MAX_SHARDS", "16"))
    shards = list(range(min(max_shards, math.ceil(len(projects) / per_shard))))
    if projects:
        print(f"Found {len(projects)} project(s), sharing them across {len(shards)} runner(s)")
    else:
        print("::notice::No projects found")

    lines = (
        f"projects={json.dumps(projects, separators=(',', ':'))}\n"
        f"has_projects={'true' if projects else 'false'}\n"
        f"shards={json.dumps(shards, separators=(',', ':'))}\n"
    )
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a") as fh:
            fh.write(lines)
    else:
        print(lines, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())

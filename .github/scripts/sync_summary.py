#!/usr/bin/env python3
"""Summarize a Sync Projects run from its shards' result files.

Usage: sync_summary.py RESULTS_DIR

Every project in $PROJECTS_JSON should have a line in one of RESULTS_DIR's
*.jsonl files; one without is reported as failed, because its shard died
before reaching it. Writes the summary to $GITHUB_STEP_SUMMARY (or stdout) and
exits 1 if any project failed.
"""

import json
import os
import sys
from pathlib import Path

SECTIONS = (
    ("failed", "❌ Failed", "Error"),
    ("committed", "✅ Committed", "Commit"),
    ("superseded", "⏭️ Left for the next sync", "Reason"),
    ("skipped", "⏭️ Skipped", "Reason"),
)


def load(results_dir: Path, projects: list[str]) -> dict[str, dict]:
    results = {}
    for path in sorted(results_dir.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                result = json.loads(line)
                results[result["project"]] = result
    for project in projects:
        results.setdefault(
            project,
            {
                "project": project,
                "status": "failed",
                "message": "no result: its shard did not finish",
            },
        )
    return results


def summarize(results: dict[str, dict]) -> str:
    lines = ["## Sync Projects", ""]
    for status, title, column in SECTIONS:
        rows = [r for r in results.values() if r["status"] == status]
        if rows:
            lines += [f"### {title} ({len(rows)})", "", f"| Project | {column} |", "|---|---|"]
            for r in sorted(rows, key=lambda r: r["project"]):
                message = r.get("message", "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{r['project']}` | {message} |")
            lines.append("")
    unchanged = sum(r["status"] == "no_change" for r in results.values())
    lines.append(f"➖ {unchanged} project(s) unchanged")
    return "\n".join(lines) + "\n"


def main() -> int:
    results = load(Path(sys.argv[1]), json.loads(os.environ["PROJECTS_JSON"]))
    summary = summarize(results)
    print(summary)
    if summary_file := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_file, "a") as fh:
            fh.write(summary)
    failed = sum(r["status"] == "failed" for r in results.values())
    if failed:
        print(f"::error::{failed} project(s) failed to sync — see the run summary")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

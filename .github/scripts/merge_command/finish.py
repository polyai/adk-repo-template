"""Finish a /poly-merge run: merge in git if everything deployed, and report on the PR.

If Dialog Studio main may have the PR's changes but git main doesn't, it dispatches
Sync Projects for the run's projects so git catches up.
"""

import json
import os
import subprocess
import sys

from lib import (
    FAILURE,
    STUDIO_ONLY,
    SUCCESS,
    TITLE_DEPLOYED,
    gh,
    is_deployed,
    repo,
    report,
    set_check,
    set_waiting,
)


def main() -> int:
    env = os.environ
    pr = int(env["PR_NUMBER"])
    head_sha = env["HEAD_SHA"]
    projects = json.loads(env["PROJECTS"])
    deploy = env["DEPLOY"] == "true"
    comment_again = "Comment `/poly-merge`"
    fix_then = "Fix the failure then comment `/poly-merge`"
    results = {"failure": "failed", "cancelled": "cancelled", "skipped": "skipped"}

    if env["GITHUB_RUN_ATTEMPT"] != "1":
        report(pr, FAILURE, "Re-runs not supported", comment_again)
        if deploy and not is_deployed(head_sha):
            set_waiting(head_sha, projects)
        return 0

    def stopped(reason: str, next_step: str = fix_then) -> int:
        report(pr, FAILURE, f"{reason}. Nothing published", next_step)
        if deploy:
            set_waiting(head_sha, projects)
        return 0

    if env["WAIT_RESULT"] != "success":
        result = env["WAIT_RESULT"]
        return stopped(f"Waiting for its turn {results.get(result, result)}", comment_again)
    if env["RECHECK_PROCEED"] != "true":
        if deploy:
            set_waiting(head_sha, projects)  # the gate has already reported why
        return 0

    reached_agent_studio = False
    if deploy:
        for job, label in (("LINT", "Lint and test"), ("PUSH", "Push to Dialog Studio")):
            result = env[f"{job}_RESULT"]
            if result != "success":
                return stopped(f"{label} {results.get(result, result)}")
        if env["HEAD_MOVED"] == "true":
            return stopped("New commits pushed during deploy", comment_again)
        if env["HEAD_MOVED"] != "false":
            result = env["VERIFY_RESULT"]
            return stopped(f"Head check {results.get(result, result)}")
        reached_agent_studio = True
        if env["MERGE_RESULT"] != "success":
            result = env["MERGE_RESULT"]
            report(
                pr,
                FAILURE,
                f"Dialog Studio merge {results.get(result, result)}. Projects that merged sync to `main`",
                fix_then,
            )
            set_waiting(head_sha, projects)
            dispatch_syncs(env["IDS"])
            return 0
        set_check(
            head_sha,
            TITLE_DEPLOYED,
            projects,
            "Projects:",
            status="completed",
            conclusion="success",
            details_url=env["RUN_URL"],
        )

    def not_merged(reason: str, next_step: str) -> int:
        report(pr, STUDIO_ONLY if reached_agent_studio else FAILURE, reason, next_step)
        if reached_agent_studio:
            dispatch_syncs(env["IDS"])
        return 0

    def head_moved() -> int:
        if reached_agent_studio:
            return not_merged(
                f"New commits pushed after `{head_sha[:7]}` deployed. Git merge skipped. "
                f"`{head_sha[:7]}` reaches `main` via sync",
                "Update the branch then comment `/poly-merge`",
            )
        return not_merged("New commits pushed", comment_again)

    current = gh(repo(f"/pulls/{pr}"))
    if current["merged"]:
        report(pr, SUCCESS, "PR was already merged")
        return 0
    if not projects:
        # deploy-check counts every project folder the PR touches; when the merge with main
        # changes none of them, nothing else sets the check before the merge.
        set_check(
            head_sha,
            "No project changes",
            [],
            "No deploy needed.",
            status="completed",
            conclusion="success",
        )
    if current["head"]["sha"] != head_sha:
        return head_moved()

    trailer = f"Merged-by: @{env['COMMENTER']} via /poly-merge ({env['RUN_URL']})"
    body = "\n\n".join(filter(None, [(current["body"] or "").strip(), trailer]))
    subject = f"{current['title']} (#{pr})"
    merge = subprocess.run(
        ["gh", "pr", "merge", str(pr), "--repo", env["GITHUB_REPOSITORY"], "--squash"]
        + ["--match-head-commit", head_sha, "--subject", subject, "--body", body],
        capture_output=True,
        text=True,
    )
    if merge.returncode == 0:
        if deploy:
            report(pr, SUCCESS)
        else:
            report(pr, f"{SUCCESS} ({'already on Studio' if projects else 'no Studio changes'})")
        return 0
    if gh(repo(f"/pulls/{pr}"))["head"]["sha"] != head_sha:
        return head_moved()
    # gh adds hints about --auto and --admin after the first line; only the first is the reason.
    error = next((line for line in merge.stderr.splitlines() if line.strip()), "unknown error")
    refused = f"Git merge refused: {error.strip().removeprefix('X ').rstrip('.')}"
    if reached_agent_studio:
        refused += ". Deployed changes reach `main` via sync"
    return not_merged(
        refused,
        "Fix it then press Merge (`poly/deploy` stays green) or comment `/poly-merge`"
        if deploy
        else "Fix it then comment `/poly-merge`",
    )


def dispatch_syncs(ids_json: str) -> None:
    for ids in json.loads(ids_json):
        gh(
            "-X",
            "POST",
            repo("/actions/workflows/sync_projects.yml/dispatches"),
            data={"ref": "main", "inputs": ids},
            token=os.environ["ACTIONS_TOKEN"],
        )
        print(f"Started a sync for {ids['account_id']}/{ids['project_id']}")


if __name__ == "__main__":
    sys.exit(main())

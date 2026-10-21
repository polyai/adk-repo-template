"""Decide whether a /poly-merge comment may go ahead, before anything touches Dialog Studio.

MODE=first runs when the comment arrives. MODE=recheck runs again once it's this run's
turn, and refuses if anything changed meanwhile. The gate is as strict as the ruleset:
once Dialog Studio has the PR's changes, a sync brings them into git whether or not the
git merge is allowed.
"""

import json
import os
import re
import subprocess
import sys

from lib import (
    DEPLOY_CHECK,
    FAILURE,
    GhError,
    gh,
    is_deployed,
    repo,
    report,
    set_check,
    set_output,
)

PASSING = {"SUCCESS", "NEUTRAL", "SKIPPED"}

PR_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewDecision
      reviewThreads(first: 100) { nodes { isResolved } }
      latestReviews(first: 100) { nodes { state commit { oid } } }
      commits(last: 1) {
        nodes {
          commit {
            statusCheckRollup {
              contexts(first: 100) {
                nodes {
                  __typename
                  ... on CheckRun { name status conclusion }
                  ... on StatusContext { context state }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check)


COMMENT = "comment `/poly-merge`"
STATE_WORDS = {"FAILURE": "failed", "TIMED_OUT": "timed out", "STARTUP_FAILURE": "failed to start"}


def approval_problems(pr_data: dict, pr_rule: dict, head_sha: str) -> list[tuple[str, str]]:
    """(reason, next step) for each approval the ruleset still needs."""
    problems = []
    decision = pr_data.get("reviewDecision")
    if decision == "CHANGES_REQUESTED":
        problems.append(("Changes requested", f"Address the review then {COMMENT}"))
    elif decision == "REVIEW_REQUIRED":
        problems.append(("Approval required", f"Get an approval then {COMMENT}"))
    if pr_rule.get("require_last_push_approval") and not any(
        r["state"] == "APPROVED" and (r.get("commit") or {}).get("oid") == head_sha
        for r in pr_data["latestReviews"]["nodes"]
    ):
        problems.append(
            ("Latest commit not approved", f"Get the latest commit approved then {COMMENT}")
        )
    if pr_rule.get("required_review_thread_resolution") and not all(
        t["isResolved"] for t in pr_data["reviewThreads"]["nodes"]
    ):
        problems.append(("Unresolved review threads", f"Resolve review threads then {COMMENT}"))
    return problems


def check_problems(rollup: list[dict], required: list[str]) -> list[tuple[str, str]]:
    """(reason, next step) for each of the ruleset's required checks, other than poly/deploy."""
    states = {}
    for node in rollup:
        if node["__typename"] == "CheckRun":
            states[node["name"]] = (
                node["conclusion"] if node["status"] == "COMPLETED" else "RUNNING"
            )
        else:
            states[node["context"]] = "RUNNING" if node["state"] == "PENDING" else node["state"]
    problems = []
    for name in sorted(set(required) - {DEPLOY_CHECK}):
        state = states.get(name)
        if state is None:
            problems.append((f"Check `{name}` not reported", f"Wait for checks then {COMMENT}"))
        elif state == "RUNNING":
            problems.append((f"Check `{name}` running", f"Wait for checks then {COMMENT}"))
        elif state not in PASSING:
            word = STATE_WORDS.get(state, state.lower().replace("_", " "))
            problems.append((f"Check `{name}` {word}", f"Fix failing checks then {COMMENT}"))
    return problems


def project_ids(files: list[str], tree: str) -> dict[str, dict]:
    """Map each project the files belong to ("account/project") to its IDs at tree.

    A project only counts while it still has a project.yaml, so deleting a project
    doesn't need a deploy.
    """
    found = {}
    for project in sorted(
        {
            "/".join(f.split("/")[1:3])
            for f in files
            if f.startswith("agents/") and f.count("/") >= 3
        }
    ):
        show = git("show", f"{tree}:agents/{project}/project.yaml", check=False)
        if show.returncode:
            continue
        ids = {
            k: re.search(rf"^{k}:\s*['\"]?([^'\"\s]+)", show.stdout, re.M)
            for k in ("account_id", "project_id")
        }
        found[project] = {k: m.group(1) for k, m in ids.items() if m}
    return found


def main() -> int:
    env = os.environ
    mode = env.get("MODE", "first")
    pr_number = int(env["PR_NUMBER"])
    commenter = env["COMMENTER"]
    set_output("proceed", "false")

    if mode == "first":
        if (env.get("COMMENT_BODY") or "").strip() != "/poly-merge":
            return 0
        try:
            gh(
                "-X",
                "POST",
                repo(f"/issues/comments/{env['COMMENT_ID']}/reactions"),
                "-f",
                "content=eyes",
            )
        except GhError:
            pass

    problems: list[tuple[str, str]] = []
    if env["GITHUB_RUN_ATTEMPT"] != "1":
        problems.append(("Re-runs not supported", COMMENT.capitalize()))
    try:
        can_push = gh(repo(f"/collaborators/{commenter}/permission"))["user"]["permissions"]["push"]
    except GhError:
        can_push = False
    if not can_push:
        problems.append(
            (f"No write access: @{commenter}", f"Ask someone with write access to {COMMENT}")
        )

    pr = gh(repo(f"/pulls/{pr_number}"))
    head_sha, base_ref = pr["head"]["sha"], pr["base"]["ref"]
    if pr["state"] != "open":
        problems.append(("PR not open", f"Reopen the PR then {COMMENT}"))
    if pr["draft"]:
        problems.append(("PR is a draft", f"Mark the PR ready then {COMMENT}"))
    if (pr["head"]["repo"] or {}).get("full_name") != env["GITHUB_REPOSITORY"]:
        problems.append(("PR is from a fork", "Open the PR from a branch in this repo"))
    default_branch = pr["base"]["repo"]["default_branch"]
    if base_ref != default_branch:
        problems.append(
            (f"PR targets `{base_ref}`, not `{default_branch}`", f"Retarget the PR then {COMMENT}")
        )
    if mode == "recheck" and head_sha != env["EXPECT_HEAD"]:
        problems.append(("New commits pushed while waiting", COMMENT.capitalize()))

    rules = gh(repo(f"/rules/branches/{base_ref}"))
    required = [
        c["context"]
        for r in rules
        if r["type"] == "required_status_checks"
        for c in r["parameters"]["required_status_checks"]
    ]
    pr_rule = next((r["parameters"] for r in rules if r["type"] == "pull_request"), {})
    strict = any(
        r["parameters"].get("strict_required_status_checks_policy")
        for r in rules
        if r["type"] == "required_status_checks"
    )
    if any(r["type"] == "merge_queue" for r in rules):
        problems.append(
            ("Merge queue is on", "Merge through the queue, or remove its rule (see SETUP.md)")
        )
    if "squash" not in pr_rule.get("allowed_merge_methods", ["squash"]):
        problems.append(("Squash merges not allowed", "Allow squash merges in the ruleset"))
    owner, name = env["GITHUB_REPOSITORY"].split("/")
    data = gh(
        "graphql",
        "-f",
        f"query={PR_QUERY}",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
        "-F",
        f"number={pr_number}",
    )["data"]["repository"]["pullRequest"]
    problems += approval_problems(data, pr_rule, head_sha)
    rollup = (data["commits"]["nodes"][0]["commit"]["statusCheckRollup"] or {}).get("contexts", {})
    problems += check_problems(rollup.get("nodes", []), required)

    # Deploy rebuilds this merge from these three commits, so it pushes what the squash
    # merge will put on the base branch, as the merge queue does.
    git("fetch", "--no-tags", "origin", base_ref, f"refs/pull/{pr_number}/head")
    base_sha = git("rev-parse", f"origin/{base_ref}").stdout.strip()
    merge_base = git("merge-base", base_sha, head_sha).stdout.strip()
    merge = git(
        "merge-tree",
        "--write-tree",
        "--name-only",
        f"--merge-base={merge_base}",
        base_sha,
        head_sha,
        check=False,
    )
    projects = {}
    if merge.returncode:
        conflicts = merge.stdout.split("\n\n")[0].splitlines()[1:]
        problems.append(
            (
                f"Conflict with `{base_ref}`: {', '.join(f'`{c}`' for c in conflicts)}",
                f"Resolve conflict then {COMMENT}",
            )
        )
    else:
        tree = merge.stdout.split()[0]
        projects = project_ids(git("diff", "--name-only", base_sha, tree).stdout.split(), tree)
        for project, ids in projects.items():
            if len(ids) != 2:
                problems.append(
                    (
                        f"`agents/{project}/project.yaml` has no `account_id` or `project_id`",
                        f"Fix project.yaml then {COMMENT}",
                    )
                )
    if strict and merge_base != base_sha:
        problems.append(
            (f"Branch not up to date with `{base_ref}`", f"Update the branch then {COMMENT}")
        )

    deploy = bool(projects) and not is_deployed(head_sha)
    title = re.sub(
        r"^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)\([^)]+\)!?:",
        r"\1:",
        pr["title"],
    )
    for key, value in {
        "head_sha": head_sha,
        "head_ref": pr["head"]["ref"],
        "base_sha": base_sha,
        "merge_base": merge_base,
        "projects": json.dumps(list(projects)),
        "ids": json.dumps(list(projects.values())),
        "deploy": "true" if deploy else "false",
        "as_merge_message": f"{title} (#{pr_number})",
    }.items():
        set_output(key, value)

    if problems:
        steps = {step for _, step in problems}
        next_step = steps.pop() if len(steps) == 1 else f"Fix the above then {COMMENT}"
        report(pr_number, FAILURE, [reason for reason, _ in problems], next_step)
        return 0

    if mode == "first" and deploy:
        set_check(
            head_sha,
            "Deploying to Dialog Studio",
            list(projects),
            "Projects:",
            status="in_progress",
            details_url=env["RUN_URL"],
        )
    set_output("proceed", "true")
    return 0


if __name__ == "__main__":
    sys.exit(main())

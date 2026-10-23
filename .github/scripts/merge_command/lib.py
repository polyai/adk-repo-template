"""Shared helpers for the /poly-merge scripts: the GitHub API through `gh`, and the deploy check."""

import json
import os
import secrets
import subprocess

DEPLOY_CHECK = "poly/deploy"
TITLE_DEPLOYED = "Deployed to Dialog Studio"


class GhError(Exception):
    pass


def gh(*args: str, data: dict | None = None, token: str | None = None):
    """Run `gh api` with these arguments and return its JSON output (None if empty)."""
    cmd = ["gh", "api", *args] + (["--input", "-"] if data is not None else [])
    proc = subprocess.run(
        cmd,
        input=json.dumps(data) if data is not None else None,
        capture_output=True,
        text=True,
        env={**os.environ, "GH_TOKEN": token} if token else None,
    )
    if proc.returncode:
        raise GhError(proc.stderr.strip())
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def repo(path: str) -> str:
    return f"repos/{os.environ['GITHUB_REPOSITORY']}{path}"


def comment(pr: int, body: str) -> None:
    gh("-X", "POST", repo(f"/issues/{pr}/comments"), data={"body": body})


SUCCESS = "Success"
STUDIO_ONLY = "Success on Studio, Failure on Git"
FAILURE = "Failure"


def report(
    pr: int, merge: str, reasons: str | list[str] | None = None, next_step: str = ""
) -> None:
    """Post the run's result on the PR as a short list of fields."""
    reasons = [reasons] if isinstance(reasons, str) else list(reasons or [])
    lines = [f"**Merge:** {merge}"]
    if len(reasons) == 1:
        lines.append(f"**Reason:** {reasons[0]}")
    elif reasons:
        lines += ["**Reason:**", *(f"- {r}" for r in reasons), ""]
    if next_step:
        lines.append(f"**Next:** {next_step}")
    lines += [f"**By:** @{os.environ['COMMENTER']}", f"**Run:** {os.environ['RUN_URL']}"]
    comment(pr, "\n".join(lines))


def set_output(name: str, value: str) -> None:
    """Write a step output in the delimiter form, so no value can add another output."""
    delimiter = f"EOF_{secrets.token_hex(8)}"
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def set_check(sha: str, title: str, projects: list[str], intro: str, **fields) -> None:
    """Create a new poly/deploy run on sha; the latest run is the check's result."""
    summary = intro + "\n\n" + "\n".join(f"- `{p}`" for p in projects)
    gh(
        "-X",
        "POST",
        repo("/check-runs"),
        data={
            "name": DEPLOY_CHECK,
            "head_sha": sha,
            "output": {"title": title, "summary": summary},
            **fields,
        },
    )


def set_waiting(sha: str, projects: list[str]) -> None:
    set_check(
        sha,
        "Awaiting /poly-merge",
        projects,
        "Projects to deploy:",
        status="queued",
    )


def is_deployed(sha: str) -> bool:
    """Whether the merge App's latest poly/deploy run on sha says it's deployed."""
    runs = gh(
        "-X",
        "GET",
        repo(f"/commits/{sha}/check-runs"),
        "-f",
        f"check_name={DEPLOY_CHECK}",
        "-f",
        f"app_id={os.environ['MERGE_APP_ID']}",
    )
    latest = max(runs["check_runs"], key=lambda r: r["id"], default=None)
    return bool(
        latest and latest["conclusion"] == "success" and latest["output"]["title"] == TITLE_DEPLOYED
    )

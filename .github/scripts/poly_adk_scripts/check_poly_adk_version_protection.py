"""Check Poly ADK version protection for new projects.

For each project: if the Poly ADK version in the branch differs from main, and the project
does not exist in main, fail with instructions to merge main and re-init with up-to-date Poly ADK.
"""

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_PREFIX = "agents"


def get_poly_adk_version_from_git(ref: str, repo_root: Path) -> str | None:
    """Get Poly ADK version from pyproject.toml at a git ref."""
    result = subprocess.run(
        ["git", "show", f"{ref}:pyproject.toml"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    data = tomllib.loads(result.stdout)
    deps = data.get("project", {}).get("dependencies", [])
    for dep in deps:
        if "polyai-adk" in dep or "local_agent_studio" in dep:
            part = dep.split("@")[-1]
            return part.removeprefix("v").strip()
    return None


def project_exists_in_main(project_path: str, branch_name: str, repo_root: Path) -> bool:
    """Check if the project exists in the main branch."""
    if branch_name == "main":
        return True
    full_path = f"{PROJECT_PREFIX}/{project_path}/project.yaml"
    result = subprocess.run(
        ["git", "show", f"origin/main:{full_path}"],
        cwd=repo_root,
        capture_output=True,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Poly ADK version protection for new projects."
    )
    parser.add_argument(
        "projects",
        type=str,
        help="JSON array of project paths (e.g. '[\"account/project\"]')",
    )
    parser.add_argument(
        "branch_name",
        type=str,
        help="Current branch name",
    )
    parser.add_argument(
        "--branch-ref",
        type=str,
        required=True,
        help="Git ref for branch version (e.g. origin/branch).",
    )
    args = parser.parse_args()

    try:
        projects = json.loads(args.projects)
    except json.JSONDecodeError:
        print("::error::Invalid projects JSON", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[3]

    branch_version = get_poly_adk_version_from_git(args.branch_ref, repo_root)
    main_version = get_poly_adk_version_from_git("origin/main", repo_root)

    if branch_version is None:
        print("::error::Could not find polyai-adk in pyproject.toml", file=sys.stderr)
        return 1

    if main_version is None:
        print("::error::Could not read pyproject.toml from origin/main", file=sys.stderr)
        return 1

    version_differs = branch_version != main_version

    if not version_differs:
        return 0

    errors = []
    for project_path in projects:
        if not project_exists_in_main(project_path, args.branch_name, repo_root):
            errors.append(
                f"Project {project_path} (branch Poly ADK v{branch_version}) differs from main "
                f"(Poly ADK v{main_version}) and the project does not exist in main. "
                "Merge main into your branch and re-init the project with up-to-date Poly ADK."
            )

    if errors:
        for err in errors:
            print(f"::error::{err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

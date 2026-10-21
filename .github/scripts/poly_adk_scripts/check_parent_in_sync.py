import argparse
import subprocess
import sys
from pathlib import Path

from load_project import fetch_project_state
from poly.project import AgentStudioProject

# Exit codes follow check_as_parent_matches_local.py: a non-zero code below 2 is
# a state, 2 is an error. (Note pull_project.py uses 2 for "no changes" — different.)
EXIT_IN_SYNC = 0
EXIT_OUT_OF_SYNC = 1
EXIT_ERROR = 2

# The repo's post-pull formatting pass — the same script sync_projects.yml runs,
# resolved from this checkout (the pipeline's current policy), not the worktree
# under comparison. A repo without the hook gets a raw pull+diff comparison.
DEFAULT_FORMAT_HOOK = Path(__file__).resolve().parents[1] / "format-project.sh"


def _sync_would_change_git(
    project: AgentStudioProject, base_path: str, projection: dict, format_hook: Path
) -> bool:
    """Apply the sync pipeline (pull + format hook) to base_path and ask git if anything changed.

    base_path must be inside a disposable git worktree — the pull force-overwrites
    the project files on disk.
    """
    project.pull_project(force=True, format=True, projection_json=projection)

    if format_hook.exists():
        # The hook tolerates formatter exit codes itself; a non-zero exit means
        # the formatting pass could not run, which makes the comparison basis
        # unreliable — propagate as an error, never as drift.
        subprocess.run([str(format_hook), base_path], check=True)
    else:
        print(f"No format hook at {format_hook} — comparing the pull result as-is")

    # _gen/ is derived from project content + the installed ADK runtime, not
    # Studio-authored state — the merge can't clobber anything through it, and
    # regeneration skew (e.g. an ADK version difference) is sync_projects.yml's
    # business (FORCE_PULL on ADK bumps), not this guard's.
    porcelain = subprocess.run(
        ["git", "status", "--porcelain", "--", ".", ":(exclude)_gen"],
        cwd=base_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if porcelain.strip():
        print("Changes a sync would commit:")
        print(porcelain, end="")
        return True
    return False


def check_parent_in_sync(
    base_path: str, branch: str = "main", format_hook: Path = DEFAULT_FORMAT_HOOK
) -> int:
    """Check whether an Dialog Studio branch is in sync with the checkout at base_path.

    branch is the DS branch being merged into (the parent — today always main).
    base_path must point at the project dir inside a DISPOSABLE checkout of the
    matching parent git ref (e.g. a worktree of the merge-group base) — NOT the
    merged PR content, and not a working tree anyone keeps: the format-aware
    fallback writes into it.

    "In sync" means a sync would commit nothing to git: resource hashes are
    compared first (YAML hashes canonicalized dicts, so YAML formatting never
    registers), and on a mismatch the sync pipeline itself — pull, then the
    repo's format hook — is applied to the checkout and the result diffed with
    git. Content that only differs by formatting (e.g. a Python function ruff
    reformatted on a previous sync, never pushed back to DS) is therefore not
    drift: the Sync Projects run the failure message prescribes would be a
    no-op and could never unblock the merge.

    Returns EXIT_IN_SYNC, EXIT_OUT_OF_SYNC or EXIT_ERROR.
    """
    try:
        # Strict fetch: a named branch that doesn't exist is a hard error —
        # no silent fallback to main.
        project, projection = fetch_project_state(base_path, branch=branch)

        conflicts, modified_files, new_files, deleted_files = project.project_status()
        if not any([conflicts, modified_files, new_files, deleted_files]):
            print(f"✓ DS {branch} is in sync with {base_path}")
            return EXIT_IN_SYNC

        print("Resource hashes differ, checking whether a sync would commit anything:")
        for label, files in (
            ("conflicts", conflicts),
            ("modified", modified_files),
            ("new", new_files),
            ("deleted", deleted_files),
        ):
            for file in files:
                print(f"  {label}: {file}")

        if not _sync_would_change_git(project, base_path, projection, format_hook):
            print(
                f"✓ DS {branch} matches {base_path} after formatting (formatting-only divergence)"
            )
            return EXIT_IN_SYNC

        print(f"✗ DS {branch} differs from {base_path}")
        return EXIT_OUT_OF_SYNC
    except Exception as e:
        print(f"Error checking sync state: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check whether an Dialog Studio branch is in sync with a git checkout "
        "of the parent branch, ignoring divergence a sync's formatting pass would erase."
    )
    parser.add_argument(
        "base_path",
        type=str,
        help="Path to the project dir inside a disposable checkout of the parent git ref "
        "(the format-aware comparison writes into it).",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Dialog Studio parent branch being merged into (default: main).",
    )
    parser.add_argument(
        "--format-hook",
        type=Path,
        default=DEFAULT_FORMAT_HOOK,
        help="Formatting script run on the project dir after the pull; skipped if the "
        "path does not exist (default: this repo's format-project.sh).",
    )

    args = parser.parse_args()
    sys.exit(check_parent_in_sync(args.base_path, branch=args.branch, format_hook=args.format_hook))

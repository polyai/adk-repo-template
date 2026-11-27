import argparse
import sys

from load_project import fetch_project_state


def check_as_parent_matches_local(base_path: str, branch: str = "main") -> bool:
    """Check whether the branch's parent already matches the local project state.

    Args:
        base_path: The file path to the Dialog Studio project.
        branch: The DS branch the PR merges into. A named branch that does not
            exist raises, rather than falling back to main.

    Returns:
        True if the parent has no outstanding new/modified/deleted files relative
        to what's on disk (i.e. it already reflects merged git parent + PR branch),
        False otherwise.
    """
    project, _ = fetch_project_state(base_path, branch=branch)

    conflicts, modified_files, new_files, deleted_files = project.project_status()
    return not any([conflicts, modified_files, new_files, deleted_files])


def main() -> None:
    """Main entry point for the check DS parent matches local script."""
    parser = argparse.ArgumentParser(
        description=(
            "Check if the branch's parent already matches the local (merged) project state."
        )
    )
    parser.add_argument(
        "base_path",
        type=str,
        help="The file path to the Dialog Studio project.",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="DS parent branch the PR merges into (default: main).",
    )

    args = parser.parse_args()
    try:
        matches = check_as_parent_matches_local(args.base_path, branch=args.branch)
        if matches:
            print(f"DS parent ({args.branch}) already matches the local project state.")
        else:
            print(f"DS parent ({args.branch}) differs from the local project state.")
        sys.exit(0 if matches else 1)
    except Exception as e:
        print(f"Error comparing DS parent to local project state: {e}", file=sys.stderr)
        sys.exit(2)  # Exit code 2 indicates an error (vs 1 for not matching)


if __name__ == "__main__":
    main()

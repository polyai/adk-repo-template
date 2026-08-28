import argparse
import sys

from load_project import load_local_agent_studio_project


def check_as_parent_matches_local(base_path: str) -> bool:
    """Check whether the branch's parent (main) already matches the local project state.

    Args:
        base_path: The file path to the Agent Studio project.

    Returns:
        True if main has no outstanding new/modified/deleted files relative to
        what's on disk (i.e. main already reflects merged git main + PR branch),
        False otherwise.
    """
    # Always compare against main (the parent), not whatever branch
    # load_local_agent_studio_project would otherwise switch to — this check's
    # whole purpose is fixed to main.
    project = load_local_agent_studio_project(base_path, "main")

    conflicts, modified_files, new_files, deleted_files = project.project_status()
    return not any([conflicts, modified_files, new_files, deleted_files])


def main() -> None:
    """Main entry point for the check AS parent matches local script."""
    parser = argparse.ArgumentParser(
        description=(
            "Check if the branch's parent (main) already matches the local (merged) "
            "project state."
        )
    )
    parser.add_argument(
        "base_path",
        type=str,
        help="The file path to the Agent Studio project.",
    )

    args = parser.parse_args()
    try:
        matches = check_as_parent_matches_local(args.base_path)
        if matches:
            print("AS parent (main) already matches the local project state.")
        else:
            print("AS parent (main) differs from the local project state.")
        sys.exit(0 if matches else 1)
    except Exception as e:
        print(f"Error comparing AS parent to local project state: {e}", file=sys.stderr)
        sys.exit(2)  # Exit code 2 indicates an error (vs 1 for not matching)


if __name__ == "__main__":
    main()

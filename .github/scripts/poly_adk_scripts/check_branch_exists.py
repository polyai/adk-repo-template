import argparse
import sys

from poly.project import AgentStudioProject


def check_branch_exists(base_path: str, branch_name: str) -> bool:
    """Check if an Agent Studio branch exists.

    Args:
        base_path: The file path to the Agent Studio project.
        branch_name: The branch name to check if it exists.

    Returns:
        True if the branch exists, False otherwise.
    """
    project = AgentStudioProject.from_file_path(base_path)
    # Force branch id to be main
    project.branch_id = "main"
    _, branches = project.get_branches()
    print(f"Branches found: {branches}")
    return branch_name in branches


def main() -> None:
    """Main entry point for the check branch exists script."""
    parser = argparse.ArgumentParser(description="Check if an Agent Studio branch exists.")
    parser.add_argument(
        "base_path",
        type=str,
        help="The file path to the Agent Studio project.",
    )
    parser.add_argument(
        "branch_name",
        type=str,
        help="The branch name to check if it exists.",
    )

    args = parser.parse_args()
    try:
        exists = check_branch_exists(args.base_path, args.branch_name)
        sys.exit(0 if exists else 1)
    except Exception as e:
        print(f"Error checking branch existence: {e}", file=sys.stderr)
        sys.exit(2)  # Exit code 2 indicates an error (vs 1 for branch not existing)


if __name__ == "__main__":
    main()

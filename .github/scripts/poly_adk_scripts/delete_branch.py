"""Delete an Dialog Studio branch."""

import argparse
import sys

from poly.project import AgentStudioProject


def delete_branch(base_path: str, branch_name: str) -> tuple[bool, str]:
    """Delete a branch in Dialog Studio if it exists.

    Args:
        base_path: The file path to the Dialog Studio project.
        branch_name: The branch name to delete.

    Returns:
        A tuple of (success, message).
    """
    project = AgentStudioProject.from_file_path(base_path)
    project.branch_id = "main"
    _, branches = project.get_branches()

    branch_id = branches.get(branch_name)
    if not branch_id:
        return True, f"Branch '{branch_name}' does not exist, nothing to delete"

    success = project.delete_branch(branch_name)
    if not success:
        return False, f"Failed to delete branch '{branch_name}'"
    return True, f"Deleted branch '{branch_name}'"


def main() -> None:
    """Main entry point for the delete branch script."""
    parser = argparse.ArgumentParser(
        description="Delete an Dialog Studio branch (e.g. when a PR is closed)."
    )
    parser.add_argument(
        "base_path",
        type=str,
        help="The file path to the Dialog Studio project.",
    )
    parser.add_argument(
        "branch_name",
        type=str,
        help="The branch name to delete.",
    )

    args = parser.parse_args()
    try:
        success, message = delete_branch(args.base_path, args.branch_name)
        print(message)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error deleting branch: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

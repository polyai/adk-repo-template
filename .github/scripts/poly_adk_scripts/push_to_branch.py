import argparse
import sys

from load_project import load_local_agent_studio_project

RED_START = "\033[91m"
GREEN_START = "\033[92m"
COLOUR_END = "\033[0m"


def push_to_branch(base_path: str, branch_name: str) -> tuple[bool, str]:
    """Push changes to a branch in Agent Studio.

    Args:
        base_path: The file path to the Agent Studio project.
        branch_name: The branch name to push changes to.

    Returns:
        A tuple of (success, message) where:
        - success: True if the push was successful, False otherwise.
        - message: The error message if the push failed, or "No changes detected" if no changes were detected.
    """
    project = load_local_agent_studio_project(base_path, branch_name)

    conflicts, modified_files, new_files, deleted_files = project.project_status()

    print(f'Pushing changes to branch "{branch_name}"\n')

    if conflicts:
        print("\nFiles with merge conflicts:")
        for file_name in conflicts:
            print(f"- {RED_START}{file_name}{COLOUR_END}")

    if new_files:
        print("\nNew files:")
        for file_name in new_files:
            print(f"- {GREEN_START}{file_name}{COLOUR_END}")

    if deleted_files:
        print("\nDeleted files:")
        for file_name in deleted_files:
            print(f"- {RED_START}{file_name}{COLOUR_END}")

    if modified_files:
        print("\nModified files:")
        for file_name in modified_files:
            print(f"- {GREEN_START}{file_name}{COLOUR_END}")

    success, error, _commands = project.push_project(force=True, skip_validation=True)
    return success, error


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Push local Agent Studio project changes to the specified branch."
    )
    parser.add_argument("base_path", type=str, help="The file path to the Agent Studio project.")
    parser.add_argument("branch_name", type=str, help="The branch name to push changes to.")
    args = parser.parse_args()
    success, message = push_to_branch(args.base_path, args.branch_name)
    if success:
        print("Push successful.")
        sys.exit(0)
    elif message == "No changes detected":
        print("No changes detected.")
        sys.exit(0)
    else:
        print(f"Push failed: {message}")
        sys.exit(1)

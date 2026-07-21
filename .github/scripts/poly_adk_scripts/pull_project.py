import argparse
import sys

from poly.project import AgentStudioProject


def pull_project(base_path: str) -> bool:
    """Pull changes from main in Agent Studio.

    Args:
        base_path: The file path to the Agent Studio project.

    Returns:
       True if the pull was successful, False otherwise.
    """
    try:
        project = AgentStudioProject.from_file_path(base_path)
        project.branch_id = "main"
        project.pull_project(force=True, format=True)
        return True
    except Exception as exc:
        print(f"Pull failed: {exc}")
        if "API Error 401" in str(exc) or "Unauthorized" in str(exc):
            print(
                "Unauthorized. Please check the POLY_ADK_KEY has read permissions to the project."
            )
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull Poly ADK/Agent Studio project changes from main."
    )
    parser.add_argument("base_path", type=str, help="The file path to the Agent Studio project.")

    args = parser.parse_args()
    success = pull_project(args.base_path)
    if success:
        print("Pull successful.")
        sys.exit(0)
    else:
        print("Pull failed")
        sys.exit(1)

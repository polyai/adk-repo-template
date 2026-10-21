import argparse
import sys

from load_project import load_local_agent_studio_project


def validate_project(base_path: str, branch_name: str) -> tuple[bool, list[str]]:
    """Validate a local Dialog Studio project on the specified branch.

    Args:
        base_path: The file path to the Dialog Studio project.
        branch_name: The branch name to validate the project on.

    Returns:
        A tuple of (is_valid, errors) where:
        - is_valid: True if the project is valid, False otherwise.
        - errors: List of error messages (empty if valid).
    """
    project = load_local_agent_studio_project(base_path, branch_name)
    errors = project.validate_project()
    return len(errors) == 0, errors


def main() -> None:
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(
        description="Validate local Dialog Studio project on the specified branch."
    )
    parser.add_argument(
        "base_path",
        type=str,
        help="The file path to the Dialog Studio project.",
    )
    parser.add_argument(
        "branch_name",
        type=str,
        help="The branch name to validate the project on.",
    )

    args = parser.parse_args()
    is_valid, errors = validate_project(args.base_path, args.branch_name)

    if is_valid:
        print("Project is valid.")
        sys.exit(0)
    else:
        print("Project validation failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()

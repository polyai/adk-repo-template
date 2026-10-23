import argparse
import sys

from load_project import fetch_project_state

# Exit codes. A non-zero code here is a state rather than an error, mirroring
# check_branch_exists.py and check_as_parent_matches_local.py. (Note
# check_parent_in_sync.py uses 2 for errors — different.)
EXIT_PULLED = 0
EXIT_FAILED = 1
EXIT_NO_CHANGES = 2


def pull_project(base_path: str, force: bool = False) -> int:
    """Pull changes from main in Dialog Studio, skipping the pull when nothing changed.

    Fetches the remote projection first, which updates the tracked state without
    touching any working-tree files, and compares it against what is on disk. Only
    if they differ is the projection applied — the fetched projection is handed
    straight to the pull, so the check costs no extra API calls.

    Args:
        base_path: The file path to the Dialog Studio project.
        force: Skip the comparison and always apply the pull. Used when the pull
            has side effects the comparison cannot see (e.g. regenerating _gen
            after a Poly ADK version bump).

    Returns:
        EXIT_PULLED, EXIT_NO_CHANGES or EXIT_FAILED.
    """
    try:
        # Fetch only: updates the tracked remote state, leaves local files alone.
        project, projection = fetch_project_state(base_path)

        if not force:
            conflicts, modified_files, new_files, deleted_files = project.project_status()
            if not any([conflicts, modified_files, new_files, deleted_files]):
                return EXIT_NO_CHANGES

        project.pull_project(force=True, format=True, projection_json=projection)
        return EXIT_PULLED
    except Exception as exc:
        print(f"Pull failed: {exc}")
        if "API Error 401" in str(exc) or "Unauthorized" in str(exc):
            print(
                "Unauthorized. Please check the POLY_ADK_KEY has read permissions to the project."
            )
        return EXIT_FAILED


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull Poly ADK/Dialog Studio project changes from main."
    )
    parser.add_argument("base_path", type=str, help="The file path to the Dialog Studio project.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Pull even when Dialog Studio main already matches the local project state.",
    )

    args = parser.parse_args()
    result = pull_project(args.base_path, force=args.force)
    if result == EXIT_PULLED:
        print("Pull successful.")
    elif result == EXIT_NO_CHANGES:
        print("No Dialog Studio changes, skipping pull.")
    else:
        print("Pull failed")
    sys.exit(result)

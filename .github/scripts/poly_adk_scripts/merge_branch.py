import argparse
import sys
import time

from load_project import load_local_agent_studio_project

# Format: AS resource paths
# * wildcard for that subfolder
# ** wildcard for any subfolder
SUPPORTED_CONFLICT_RESOLUTIONS = [
    ["knowledgeBase", "**"],
    ["functions", "**"],
    ["specialFunctions", "**"],
    ["agentSettings", "**"],
    ["flows", "**"],
    ["sms", "**"],
    ["entities", "**"],
    ["experimentalConfig", "**"],
    ["variantManagement", "**"],
    ["handoff", "**"],
    ["channels", "voice", "asrSettings", "**"],
    ["channels", "voice", "config", "greeting", "**"],
    ["channels", "voice", "config", "stylePrompt", "**"],
    ["channels", "voice", "config", "safetyFilters", "**"],
    ["channels", "voice", "disclaimer", "isEnabled"],
    ["channels", "voice", "disclaimer", "message"],
    ["channels", "voice", "disclaimer", "languageCode"],
    ["channels", "voice", "disclaimer", "updatedAt"],
    ["channels", "voice", "disclaimer", "updatedBy"],
    ["channels", "webChat", "config", "greeting", "**"],
    ["channels", "webChat", "config", "stylePrompt", "**"],
    ["channels", "webChat", "config", "safetyFilters", "**"],
    ["keyphraseBoosting", "**"],
    ["pronunciations", "**"],
    ["transcriptCorrections", "**"],
    ["variables", "**"],
    ["stopKeywords", "**"],
    ["apiIntegrations", "**"],
    ["languages", "**"],
    ["translations", "**"],
    ["contentFilterSettings", "**"],
    ["testing", "**"],
]


def _build_lookup_tree(supported_resolutions: list[list[str]]) -> dict:
    lookup_tree = {}
    for resolution in supported_resolutions:
        current_level = lookup_tree
        for part in resolution:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]
    return lookup_tree


SUPPORTED_CONFLICT_LOOKUP_TREE = _build_lookup_tree(SUPPORTED_CONFLICT_RESOLUTIONS)


def _is_supported_conflict(lookup_tree: dict, conflict_path: list[str]) -> bool:
    current_level = lookup_tree
    for part in conflict_path:
        if part in current_level:
            current_level = current_level[part]
        elif "**" in current_level:
            return True
        elif "*" in current_level:
            current_level = current_level["*"]
        else:
            return False
    return True


def _get_error_message(error: dict) -> str:
    return str(error.get("message", error.get("error", error)))


def _get_conflict_path(conflict: dict) -> list[str]:
    return conflict["path"]


def generate_messages(conflicts: list[dict], errors: list[dict]) -> list[str]:
    """Render conflicts and errors from a merge attempt as human-readable lines."""
    messages = []
    for conflict in conflicts:
        messages.append(f"Conflict: {_get_conflict_path(conflict)}")

    for error in errors:
        message = f"Error: {_get_error_message(error)}"
        if error_path := error.get("path"):
            message += f" - {error_path}"
        messages.append(message)

    return messages


SEQUENCE_MISMATCH_RETRY_DELAYS = (2, 5, 10)


def _is_sequence_mismatch(errors: list[dict]) -> bool:
    messages = (_get_error_message(error).lower() for error in errors)
    return any("sequence mismatch" in m or "sequence_mismatch" in m for m in messages)


def _merge_with_retry(project, message: str, conflict_resolutions: list[dict] | None = None):
    """Merge, retrying when the branch sequence moved underneath us.

    A draft deployment finishing mid-merge appends an event to the branch and the API
    rejects the merge with SEQUENCE_MISMATCH. The ADK refetches the sequence on each
    call, so a plain retry picks up the new value.
    """
    attempts = len(SEQUENCE_MISMATCH_RETRY_DELAYS)
    for attempt, delay in enumerate(SEQUENCE_MISMATCH_RETRY_DELAYS, start=1):
        try:
            success, conflicts, errors = project.merge_branch(
                message=message, conflict_resolutions=conflict_resolutions
            )
        except ValueError as e:
            if "uncommitted changes" in str(e).lower():
                print("Merge blocked by uncommitted local changes:")
                for file, diff in project.get_diffs().items():
                    print(file)
                    print(diff)
            raise
        if not _is_sequence_mismatch(errors):
            return success, conflicts, errors
        print(
            f"Sequence mismatch (branch changed during merge) - retrying in {delay}s "
            f"(attempt {attempt}/{attempts})"
        )
        time.sleep(delay)
    return project.merge_branch(message=message, conflict_resolutions=conflict_resolutions)


def merge_branch(base_path: str, branch_name: str, message: str) -> tuple[bool, str]:
    """Merge a branch in Agent Studio.
    Args:
        base_path: The file path to the Agent Studio project.
        branch_name: The branch name to merge.
        message: The message to use for the merge.

    Returns:
        A tuple of (success, message) where:
        - success: True if the merge was successful, False otherwise.
        - message: The error message if the merge failed
    """
    project = load_local_agent_studio_project(base_path, branch_name)

    if project.branch_id == "main":
        return False, "Cannot merge from the main branch."

    print("Attempting merge")
    success, conflicts, errors = _merge_with_retry(
        project,
        message=message,
    )
    messages = generate_messages(conflicts, errors)

    if errors:
        only_sync_errors = True
        for error in errors:
            lower_error = _get_error_message(error).lower()
            only_sync_errors &= (
                "duplicate name" in lower_error or "duplicate parameter name" in lower_error
            )

        if not only_sync_errors:
            return False, "\n".join(messages)

        print("Found duplicate name errors, attempting sync and merge")
        if not project.sync_ids_with_sandbox():
            return False, "Error: Failed to sync IDs with sandbox"

        success, conflicts, errors = _merge_with_retry(
            project,
            message=message,
        )
        messages = generate_messages(conflicts, errors)

        if errors:
            print("Failed to resolve errors automatically")
            return False, "\n".join(messages)

    # Go through all conflicts,
    # If they supported in Poly ADK then use our version
    if conflicts:
        conflict_resolutions = []
        for conflict in conflicts:
            conflict_path = _get_conflict_path(conflict)
            if _is_supported_conflict(SUPPORTED_CONFLICT_LOOKUP_TREE, conflict_path):
                conflict_resolutions.append(
                    {
                        "path": conflict_path,
                        "strategy": "theirs",
                    }
                )
        if conflict_resolutions:
            print("Found conflicts, trying to resolve them automatically")
            print(conflict_resolutions)
            success, conflicts, errors = _merge_with_retry(
                project,
                message=message,
                conflict_resolutions=conflict_resolutions,
            )
            messages = generate_messages(conflicts, errors)

        if conflicts or errors:
            print("Failed to resolve conflicts automatically")

    return success, "\n".join(messages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge Poly ADK/Agent Studio project changes from the specified branch."
    )
    parser.add_argument("base_path", type=str, help="The file path to the Agent Studio project.")
    parser.add_argument("branch_name", type=str, help="The branch name to merge from.")
    parser.add_argument("message", type=str, help="The message to use for the merge.")

    args = parser.parse_args()
    success, messages = merge_branch(args.base_path, args.branch_name, args.message)
    if success:
        print("Merge successful.")
        sys.exit(0)
    else:
        print("Merge failed:")
        print(messages)
        sys.exit(1)

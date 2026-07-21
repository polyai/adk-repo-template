import argparse
import sys

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

    print("Attempting merge")
    success, conflicts, errors = project.merge_branch(
        message=message,
    )

    messages = []
    if conflicts:
        for conflict in conflicts:
            messages.append(f"Conflict: {_get_conflict_path(conflict)}")

    if errors:
        only_sync_errors = True
        for error in errors:
            error_msg = _get_error_message(error)
            messages.append(f"Error: {error_msg}")
            lower_error = error_msg.lower()
            only_sync_errors &= (
                "duplicate name" in lower_error or "duplicate parameter name" in lower_error
            )

        if not only_sync_errors:
            return False, "\n".join(messages)

        print("Found duplicate name errors, attempting sync and merge")
        messages = []
        sync_success = project.sync_ids_with_sandbox()
        if not sync_success:
            messages.append("Error: Failed to sync IDs with sandbox")
            return False, "\n".join(messages)

        success, conflicts, errors = project.merge_branch(
            message=message,
        )

        for conflict in conflicts:
            messages.append(f"Conflict: {_get_conflict_path(conflict)}")

        for error in errors:
            messages.append(f"Error: {_get_error_message(error)}")

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
            messages = []
            success, conflicts, errors = project.merge_branch(
                message=message,
                conflict_resolutions=conflict_resolutions,
            )
            for error in errors:
                messages.append(f"Error: {_get_error_message(error)}")
            for conflict in conflicts:
                messages.append(f"Conflict: {_get_conflict_path(conflict)}")

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
